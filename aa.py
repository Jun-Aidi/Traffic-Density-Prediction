import subprocess
import numpy as np
import cv2
import threading
import time
import queue

URL = "https://cctv.balitower.co.id/Gelora-017-700470_3/tracks-v1/index.m3u8"

PIPE_W         = 1664
PIPE_H         = 1248
DISPLAY_FPS    = 20          # cocok dengan fps sumber (20fps)
FRAME_INTERVAL = 1.0 / DISPLAY_FPS
FRAME_SIZE     = PIPE_W * PIPE_H * 3
MAX_QUEUE      = 200         # buffer ~10 detik — cukup untuk jeda antar segment HLS
MIN_START      = 30          # tunggu 30 frame sebelum mulai tampil (~1.5 detik)

ffmpeg_cmd = [
    "ffmpeg",
    "-loglevel", "quiet",
    "-i", URL,               # tanpa nobuffer/low_delay — HLS butuh buffering internal
    "-f", "rawvideo",
    "-pix_fmt", "bgr24",
    "-vf", f"scale={PIPE_W}:{PIPE_H}",
    "pipe:1"
]

process = subprocess.Popen(
    ffmpeg_cmd,
    stdout=subprocess.PIPE,
    stderr=subprocess.DEVNULL,
    bufsize=FRAME_SIZE * 8
)

frame_queue = queue.Queue(maxsize=MAX_QUEUE)
stop_event  = threading.Event()

def reader_thread():
    """Baca frame dari ffmpeg; JANGAN drop — biarkan queue penuh sampai display konsumsi."""
    while not stop_event.is_set():
        raw = process.stdout.read(FRAME_SIZE)
        if len(raw) < FRAME_SIZE:
            stop_event.set()
            break
        frame = np.frombuffer(raw, np.uint8).reshape((PIPE_H, PIPE_W, 3)).copy()
        # Blokir sampai ada slot kosong (max 2 detik), jangan drop frame
        try:
            frame_queue.put(frame, timeout=2)
        except queue.Full:
            pass  # hanya drop jika benar-benar stuck

thread = threading.Thread(target=reader_thread, daemon=True)
thread.start()

cv2.namedWindow("Live CCTV", cv2.WINDOW_NORMAL)
cv2.resizeWindow("Live CCTV", 1280, 960)

# Tunggu buffer terisi dulu sebelum mulai tampil
print(f"Buffering... (menunggu {MIN_START} frame)")
while frame_queue.qsize() < MIN_START and not stop_event.is_set():
    time.sleep(0.05)
print(f"Stream dibuka | {DISPLAY_FPS} fps | Res: {PIPE_W}x{PIPE_H}")
print("Tekan Q untuk keluar")

fps_count       = 0
fps_display     = 0.0
fps_timer       = time.perf_counter()
next_frame_time = time.perf_counter()
last_frame      = None

while not stop_event.is_set():
    now     = time.perf_counter()
    wait_ms = max(1, int((next_frame_time - now) * 1000))
    if cv2.waitKey(wait_ms) & 0xFF == ord("q"):
        stop_event.set()
        break

    if time.perf_counter() < next_frame_time:
        continue

    next_frame_time += FRAME_INTERVAL

    # Ambil frame baru; jika kosong sementara, freeze frame terakhir (bukan pause)
    try:
        last_frame = frame_queue.get_nowait()
    except queue.Empty:
        pass

    if last_frame is None:
        continue

    frame = last_frame

    # Hitung FPS
    fps_count += 1
    elapsed = time.perf_counter() - fps_timer
    if elapsed >= 1.0:
        fps_display = fps_count / elapsed
        fps_count   = 0
        fps_timer   = time.perf_counter()

    label = f"FPS: {fps_display:.1f}  |  Buffer: {frame_queue.qsize()}/{MAX_QUEUE}"
    cv2.rectangle(frame, (0, 0), (310, 28), (0, 0, 0), -1)
    cv2.putText(frame, label, (6, 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 80), 2)
    cv2.imshow("Live CCTV", frame)

process.terminate()
thread.join(timeout=2)
cv2.destroyAllWindows()
print(f"Stream ditutup. FPS terakhir: {fps_display:.1f}")