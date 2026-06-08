"""
Enhanced Detection dengan Motion Tracking untuk Kendaraan Cepat
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Menggabungkan:
1. YOLO detector (deteksi objek)
2. Motion detector (tangkap kendaraan cepat antar frame)
3. Object tracking (reduce flickering, stabilkan deteksi)

Gunakan script ini untuk menguji performa deteksi kendaraan cepat sebelum
integrate ke server utama.
"""

import subprocess
import numpy as np
import cv2
import time
import queue
from ultralytics import YOLO
import threading
from Traffic_Data_Collection.motion_detector import MotionDetector


# ═══════════════════════════════════════════════════════════════════════════════
# KONFIGURASI
# ═══════════════════════════════════════════════════════════════════════════════

URL = "https://cctv.balitower.co.id/Gelora-017-700470_3/tracks-v1/index.m3u8"

PIPE_W         = 1664
PIPE_H         = 1248
DISPLAY_FPS    = 20
FRAME_INTERVAL = 1.0 / DISPLAY_FPS
FRAME_SIZE     = PIPE_W * PIPE_H * 3
MAX_QUEUE      = 100
MIN_START      = 15

# YOLO config - OPTIMIZED UNTUK FAST VEHICLES
YOLO_MODEL     = "yolov8n.pt"
CONFIDENCE     = 0.25               # Rendah untuk tangkap kendaraan cepat
DETECT_EVERY   = 1                  # SETIAP frame, tidak skip
IMGSZ          = 800                # Lebih besar untuk detail

# Motion Detection config
ENABLE_MOTION_DETECTION = True      # Enable deteksi gerakan cepat
MOTION_SENSITIVITY = 0.35           # 0.0-1.0, lebih rendah = lebih sensitif
MOTION_MIN_AREA = 300               # Pixel^2, ukuran minimum area gerakan

# Vehicle classes (COCO dataset)
VEHICLE_CLASSES = {1, 2, 3, 5, 7}  # bicycle, car, motorcycle, bus, truck
CLASS_NAMES = {
    1: "Sepeda",
    2: "Mobil",
    3: "Motor",
    5: "Bus",
    7: "Truk",
}

HEADLESS = False                    # True untuk background mode


# ═══════════════════════════════════════════════════════════════════════════════
# FRAME READER THREAD
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
stop_event = threading.Event()


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
# INITIALIZE MODELS
# ═══════════════════════════════════════════════════════════════════════════════

print(f"[INIT] Loading YOLO model ({YOLO_MODEL})...")
model = YOLO(YOLO_MODEL)
print("[INIT] YOLO model loaded.")

if ENABLE_MOTION_DETECTION:
    print("[INIT] Initializing Motion Detector...")
    motion_detector = MotionDetector(
        sensitivity=MOTION_SENSITIVITY,
        min_area=MOTION_MIN_AREA
    )
    print("[INIT] Motion Detector ready.")


# ═══════════════════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def draw_yolo_detections(frame, boxes, classes, confidences, color=(255, 200, 0)):
    """Draw YOLO detections - solid color."""
    for box, cls, conf in zip(boxes, classes, confidences):
        x1, y1, x2, y2 = map(int, box)
        label = CLASS_NAMES.get(int(cls), "?")
        
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        text = f"{label} {conf:.0%}"
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(frame, (x1, y1 - th - 6), (x1 + tw + 4, y1), color, -1)
        cv2.putText(frame, text, (x1 + 2, y1 - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    return frame


def draw_motion_detections(frame, boxes, color=(0, 255, 255)):
    """Draw motion-detected regions - cyan dashed."""
    for box in boxes:
        x1, y1, x2, y2 = map(int, box)
        # Dashed rectangle untuk distinguish dari YOLO
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2, cv2.LINE_8)
        text = "MOTION"
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)
        cv2.rectangle(frame, (x1, y1 - th - 4), (x1 + tw + 2, y1), color, -1)
        cv2.putText(frame, text, (x1 + 1, y1 - 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)
    return frame


def draw_info_panel(frame, yolo_count, motion_count, total_count, motion_score, fps_val):
    """Draw info panel."""
    panel_h = 110
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (550, panel_h), (30, 30, 30), -1)
    cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
    
    y_pos = 25
    cv2.putText(frame, f"YOLO Detections: {yolo_count}", (10, y_pos),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 200, 0), 1)
    
    if ENABLE_MOTION_DETECTION:
        y_pos += 25
        color = (0, 255, 255) if motion_count > 0 else (100, 100, 100)
        cv2.putText(frame, f"Motion Detections: {motion_count}", (10, y_pos),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 1)
        
        y_pos += 25
        motion_pct = motion_score * 100
        color = (0, 165, 255) if motion_pct > 5 else (100, 100, 100)
        cv2.putText(frame, f"Motion Score: {motion_pct:.1f}%", (10, y_pos),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 1)
    
    y_pos += 25
    cv2.putText(frame, f"Total Vehicles: {total_count}", (10, y_pos),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 100), 1)
    
    y_pos += 25
    cv2.putText(frame, f"FPS: {fps_val:.1f}", (10, y_pos),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 80), 1)
    
    # Instructions
    info_text = "[Q] Exit | [S] Save Screenshot | Motion=CYAN, YOLO=GOLD"
    (tw, _), _ = cv2.getTextSize(info_text, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)
    cv2.putText(frame, info_text, (frame.shape[1] - tw - 10, frame.shape[0] - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
    
    return frame


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN LOOP
# ═══════════════════════════════════════════════════════════════════════════════

if not HEADLESS:
    cv2.namedWindow("Enhanced Traffic Detection - Fast Vehicles", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Enhanced Traffic Detection - Fast Vehicles", 1280, 960)

print(f"\n[START] Buffering... (waiting {MIN_START} frames)")
while frame_queue.qsize() < MIN_START and not stop_event.is_set():
    time.sleep(0.05)

print(f"[START] Stream active | {DISPLAY_FPS} fps | Resolution: {PIPE_W}x{PIPE_H}")
print(f"[START] YOLO: conf={CONFIDENCE}, imgsz={IMGSZ}, every={DETECT_EVERY} frame")
if ENABLE_MOTION_DETECTION:
    print(f"[START] Motion Detector: sensitivity={MOTION_SENSITIVITY}, min_area={MOTION_MIN_AREA}")
print("[START] Ready. Press Q to exit.\n")

fps_count = 0
fps_display = 0.0
fps_timer = time.perf_counter()
next_frame_time = time.perf_counter()
last_frame = None
frame_counter = 0

# State deteksi
yolo_boxes = []
yolo_classes = []
yolo_confidences = []
motion_regions = []
motion_score = 0.0

last_db_save_time = time.perf_counter()
screenshot_counter = 0

try:
    while not stop_event.is_set():
        now = time.perf_counter()
        
        if not HEADLESS:
            wait_ms = max(1, int((next_frame_time - now) * 1000))
            key = cv2.waitKey(wait_ms) & 0xFF
            if key == ord("q"):
                print("\n[EXIT] User pressed Q")
                stop_event.set()
                break
            elif key == ord("s"):
                # Save screenshot
                screenshot_counter += 1
                filename = f"detection_screenshot_{screenshot_counter}.png"
                cv2.imwrite(filename, last_frame if last_frame is not None else np.zeros((PIPE_H, PIPE_W, 3)))
                print(f"[SCREENSHOT] Saved: {filename}")
        else:
            sleep_time = next_frame_time - now
            if sleep_time > 0:
                time.sleep(sleep_time)
        
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
        
        # ─── YOLO Detection ──────────────────────────────────────────────
        if frame_counter % DETECT_EVERY == 0:
            results = model.predict(
                frame,
                conf=CONFIDENCE,
                classes=list(VEHICLE_CLASSES),
                verbose=False,
                imgsz=IMGSZ,
            )
            
            yolo_boxes = []
            yolo_classes = []
            yolo_confidences = []
            
            if results and results[0].boxes is not None and len(results[0].boxes) > 0:
                boxes_tensor = results[0].boxes.xyxy.cpu().numpy()
                cls_tensor = results[0].boxes.cls.cpu().numpy()
                conf_tensor = results[0].boxes.conf.cpu().numpy()
                
                yolo_boxes = boxes_tensor
                yolo_classes = cls_tensor
                yolo_confidences = conf_tensor
        
        # ─── Motion Detection ────────────────────────────────────────────
        motion_regions = []
        motion_score = 0.0
        
        if ENABLE_MOTION_DETECTION:
            motion_regions, _, motion_score = motion_detector.detect_motion(frame)
        
        # ─── Combine detections ──────────────────────────────────────────
        total_vehicles = len(yolo_boxes) + len(motion_regions)
        
        # ─── FPS calculation ────────────────────────────────────────────
        fps_count += 1
        elapsed = time.perf_counter() - fps_timer
        if elapsed >= 1.0:
            fps_display = fps_count / elapsed
            fps_count = 0
            fps_timer = time.perf_counter()
        
        # ─── Draw frame ────────────────────────────────────────────────
        display_frame = frame.copy()
        
        # Draw YOLO boxes
        display_frame = draw_yolo_detections(display_frame, yolo_boxes, yolo_classes, yolo_confidences)
        
        # Draw motion boxes
        if ENABLE_MOTION_DETECTION and len(motion_regions) > 0:
            display_frame = draw_motion_detections(display_frame, motion_regions)
        
        # Draw info panel
        display_frame = draw_info_panel(
            display_frame,
            len(yolo_boxes),
            len(motion_regions),
            total_vehicles,
            motion_score,
            fps_display
        )
        
        if not HEADLESS:
            cv2.imshow("Enhanced Traffic Detection - Fast Vehicles", display_frame)

except KeyboardInterrupt:
    print("\n[EXIT] Ctrl+C pressed")
    stop_event.set()

finally:
    if not HEADLESS:
        cv2.destroyAllWindows()
    process.terminate()
    print("[CLEANUP] Resources released.")
    print("[INFO] Detection logs saved. Check FPS and motion detection rates above.")
