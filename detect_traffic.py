"""
Deteksi Keramaian Jalan (Traffic Density Detection)
Menggunakan YOLOv8 untuk mendeteksi kendaraan dari stream CCTV.

Tingkat keramaian ditentukan berdasarkan jumlah kendaraan terdeteksi:
  - Empty       : 0-8 kendaraan   (Almost empty street)
  - Low         : 9-20 kendaraan  (Only a few cars)
  - Medium      : 21-49 kendaraan (Slightly filled street)
  - High        : 50-99 kendaraan (Filled street or blocked lane)
  - Traffic Jam : >=100 kendaraan (Traffic almost not moving)

Mode:
  - HEADLESS = False : Menampilkan jendela video CCTV (default)
  - HEADLESS = True  : Berjalan di background tanpa jendela video,
                       hanya menyimpan data ke database.
                       Tekan Ctrl+C untuk menghentikan.

Tekan Q untuk keluar (hanya saat HEADLESS = False).
"""

import subprocess
import numpy as np
import cv2
import threading
import time
import queue
from ultralytics import YOLO
import database

# ═══════════════════════════════════════════════════════════════════════════════
# KONFIGURASI
# ═══════════════════════════════════════════════════════════════════════════════

URL = "https://cctv.balitower.co.id/Gelora-017-700470_3/tracks-v1/index.m3u8"

PIPE_W         = 1664
PIPE_H         = 1248
DISPLAY_FPS    = 20
FRAME_INTERVAL = 1.0 / DISPLAY_FPS
FRAME_SIZE     = PIPE_W * PIPE_H * 3
MAX_QUEUE      = 200
MIN_START      = 30

# YOLO config
YOLO_MODEL     = "yolov8n.pt"       # model nano — ringan & cepat
CONFIDENCE     = 0.35               # threshold confidence
DETECT_EVERY   = 3                  # deteksi setiap N frame (hemat CPU/GPU)

# Database config
DB_SAVE_INTERVAL = 60               # Simpan data ke PostgreSQL setiap N detik

# ─── Headless Mode ────────────────────────────────────────────────────────────
# True  = Berjalan di background tanpa jendela video (hemat CPU/GPU)
# False = Menampilkan jendela video CCTV seperti biasa
HEADLESS = False

# Kelas kendaraan dari COCO dataset (YOLOv8)
# 2=car, 3=motorcycle, 5=bus, 7=truck, 1=bicycle
VEHICLE_CLASSES = {1, 2, 3, 5, 7}
CLASS_NAMES = {
    1: "Sepeda",
    2: "Mobil",
    3: "Motor",
    5: "Bus",
    7: "Truk",
}

# Threshold keramaian
DENSITY_THRESHOLDS = [
    (8,   "Empty",       (0, 255, 0)),      # hijau
    (20,  "Low",         (0, 255, 180)),     # hijau-kuning
    (49,  "Medium",      (0, 255, 255)),     # kuning
    (99,  "High",        (0, 165, 255)),     # oranye
    (9999,"Traffic Jam", (0, 0, 255)),       # merah
]

# ═══════════════════════════════════════════════════════════════════════════════
# INISIALISASI FFMPEG
# ═══════════════════════════════════════════════════════════════════════════════

ffmpeg_cmd = [
    "ffmpeg",
    "-loglevel", "quiet",
    "-i", URL,
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

# ═══════════════════════════════════════════════════════════════════════════════
# THREAD PEMBACA FRAME
# ═══════════════════════════════════════════════════════════════════════════════

def reader_thread():
    """Baca frame dari ffmpeg secara kontinu."""
    while not stop_event.is_set():
        raw = process.stdout.read(FRAME_SIZE)
        if len(raw) < FRAME_SIZE:
            stop_event.set()
            break
        frame = np.frombuffer(raw, np.uint8).reshape((PIPE_H, PIPE_W, 3)).copy()
        try:
            frame_queue.put(frame, timeout=2)
        except queue.Full:
            pass

thread = threading.Thread(target=reader_thread, daemon=True)
thread.start()

# ═══════════════════════════════════════════════════════════════════════════════
# LOAD MODEL YOLO
# ═══════════════════════════════════════════════════════════════════════════════

print(f"Loading YOLO model ({YOLO_MODEL})...")
model = YOLO(YOLO_MODEL)
print("Model loaded.")

# ═══════════════════════════════════════════════════════════════════════════════
# FUNGSI UTILITAS
# ═══════════════════════════════════════════════════════════════════════════════

def get_density_info(count):
    """Tentukan level keramaian berdasarkan jumlah kendaraan."""
    for threshold, label, color in DENSITY_THRESHOLDS:
        if count <= threshold:
            return label, color
    return "Traffic Jam", (0, 0, 255)


def draw_detections(frame, boxes, classes, confidences):
    """Gambar bounding box dan label pada frame."""
    for box, cls, conf in zip(boxes, classes, confidences):
        x1, y1, x2, y2 = map(int, box)
        label = CLASS_NAMES.get(int(cls), "?")
        color = (255, 200, 0)

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        text = f"{label} {conf:.0%}"
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(frame, (x1, y1 - th - 6), (x1 + tw + 4, y1), color, -1)
        cv2.putText(frame, text, (x1 + 2, y1 - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    return frame


def draw_overlay(frame, vehicle_count, fps_display, buffer_size, class_counts):
    """Gambar panel info keramaian di atas frame."""
    density_label, density_color = get_density_info(vehicle_count)

    # Panel atas
    panel_h = 90
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (420, panel_h), (30, 30, 30), -1)
    cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

    # Status keramaian
    cv2.putText(frame, f"Status: {density_label}", (10, 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, density_color, 2)

    # Jumlah kendaraan
    cv2.putText(frame, f"Kendaraan: {vehicle_count}", (10, 55),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

    # Detail per kelas
    detail_parts = []
    for cls_id, name in CLASS_NAMES.items():
        cnt = class_counts.get(cls_id, 0)
        if cnt > 0:
            detail_parts.append(f"{name}:{cnt}")
    detail_text = "  ".join(detail_parts) if detail_parts else "-"
    cv2.putText(frame, detail_text, (10, 78),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

    # FPS & buffer (pojok kanan atas)
    info = f"FPS:{fps_display:.0f} | Buf:{buffer_size}/{MAX_QUEUE}"
    (tw, _), _ = cv2.getTextSize(info, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
    cv2.putText(frame, info, (frame.shape[1] - tw - 10, 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 80), 1)

    # Bar indikator keramaian
    bar_x, bar_y, bar_w, bar_h = 10, panel_h + 10, 400, 18
    fill_ratio = min(vehicle_count / 100.0, 1.0)
    cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h),
                  (80, 80, 80), -1)
    cv2.rectangle(frame, (bar_x, bar_y),
                  (bar_x + int(bar_w * fill_ratio), bar_y + bar_h),
                  density_color, -1)
    cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h),
                  (200, 200, 200), 1)

    return frame


# ═══════════════════════════════════════════════════════════════════════════════
# LOOP UTAMA
# ═══════════════════════════════════════════════════════════════════════════════

if not HEADLESS:
    cv2.namedWindow("Traffic Density - CCTV", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Traffic Density - CCTV", 1280, 960)

print("\n[DB] Menginisialisasi Database...")
database.init_db()

print(f"\nBuffering... (menunggu {MIN_START} frame)")
while frame_queue.qsize() < MIN_START and not stop_event.is_set():
    time.sleep(0.05)

print(f"Stream aktif | {DISPLAY_FPS} fps | Resolusi: {PIPE_W}x{PIPE_H}")
print(f"Deteksi setiap {DETECT_EVERY} frame | Confidence: {CONFIDENCE}")
if HEADLESS:
    print("Mode: HEADLESS (background) — Tekan Ctrl+C untuk menghentikan\n")
else:
    print("Mode: DISPLAY (tampilan video aktif) — Tekan Q untuk keluar\n")

fps_count       = 0
fps_display     = 0.0
fps_timer       = time.perf_counter()
next_frame_time = time.perf_counter()
last_frame      = None
frame_counter   = 0

# State deteksi terakhir (dipakai ulang antar frame)
last_boxes       = []
last_classes     = []
last_confidences = []
last_count       = 0
last_class_counts = {}

last_db_save_time = time.perf_counter()

while not stop_event.is_set():
    now = time.perf_counter()

    if HEADLESS:
        # Mode background: tidak ada jendela, cukup tunggu interval frame
        sleep_time = next_frame_time - now
        if sleep_time > 0:
            time.sleep(sleep_time)
    else:
        # Mode tampilan: gunakan cv2.waitKey untuk handle event keyboard
        wait_ms = max(1, int((next_frame_time - now) * 1000))
        if cv2.waitKey(wait_ms) & 0xFF == ord("q"):
            stop_event.set()
            break

    if time.perf_counter() < next_frame_time:
        continue

    next_frame_time += FRAME_INTERVAL

    try:
        last_frame = frame_queue.get_nowait()
    except queue.Empty:
        pass

    if last_frame is None:
        continue

    frame = last_frame.copy()
    frame_counter += 1

    # ─── Deteksi YOLO (setiap N frame) ───────────────────────────────────
    if frame_counter % DETECT_EVERY == 0:
        results = model.predict(
            frame,
            conf=CONFIDENCE,
            classes=list(VEHICLE_CLASSES),
            verbose=False,
            imgsz=640,
        )

        if results and results[0].boxes is not None and len(results[0].boxes) > 0:
            boxes_tensor = results[0].boxes.xyxy.cpu().numpy()
            cls_tensor   = results[0].boxes.cls.cpu().numpy()
            conf_tensor  = results[0].boxes.conf.cpu().numpy()

            last_boxes       = boxes_tensor
            last_classes     = cls_tensor
            last_confidences = conf_tensor
            last_count       = len(boxes_tensor)

            # Hitung per kelas
            last_class_counts = {}
            for c in cls_tensor:
                cid = int(c)
                last_class_counts[cid] = last_class_counts.get(cid, 0) + 1
        else:
            last_boxes       = []
            last_classes     = []
            last_confidences = []
            last_count       = 0
            last_class_counts = {}

    # ─── Gambar hasil deteksi & overlay (hanya saat tidak HEADLESS) ─────────
    fps_count += 1
    elapsed = time.perf_counter() - fps_timer
    if elapsed >= 1.0:
        fps_display = fps_count / elapsed
        fps_count   = 0
        fps_timer   = time.perf_counter()

    if not HEADLESS:
        if len(last_boxes) > 0:
            frame = draw_detections(frame, last_boxes, last_classes, last_confidences)
        frame = draw_overlay(frame, last_count, fps_display,
                             frame_queue.qsize(), last_class_counts)

    # ─── Save to Database (every DB_SAVE_INTERVAL seconds) ──────────────
    if now - last_db_save_time >= DB_SAVE_INTERVAL:
        density_label, _ = get_density_info(last_count)
        bicycle    = last_class_counts.get(1, 0)
        car        = last_class_counts.get(2, 0)
        motorcycle = last_class_counts.get(3, 0)
        bus        = last_class_counts.get(5, 0)
        truck      = last_class_counts.get(7, 0)
        
        # Run in separate thread to avoid frame lag during insert
        threading.Thread(
            target=database.insert_traffic_data,
            args=(density_label, last_count, bicycle, car, motorcycle, bus, truck),
            daemon=True
        ).start()
        
        last_db_save_time = now

    if not HEADLESS:
        cv2.imshow("Traffic Density - CCTV", frame)

# ═══════════════════════════════════════════════════════════════════════════════
# CLEANUP
# ═══════════════════════════════════════════════════════════════════════════════

process.terminate()
thread.join(timeout=2)
if not HEADLESS:
    cv2.destroyAllWindows()

density_label, _ = get_density_info(last_count)
print(f"\nStream ditutup.")
print(f"Status terakhir: {density_label} ({last_count} kendaraan)")
print(f"FPS terakhir: {fps_display:.1f}")
