"""
FastAPI WebSocket Server — Traffic Density Detection Dashboard
Membaca stream CCTV, menjalankan YOLO, dan mengirim hasil ke React via WebSocket.
"""

import subprocess
import numpy as np
import threading
import time
import asyncio
import select
import torch
from ultralytics import YOLO
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import Traffic_Data_Collection.database as database
from dotenv import load_dotenv

load_dotenv()

# ═══════════════════════════════════════════════════════════════════════════════
# KONFIGURASI
# ═══════════════════════════════════════════════════════════════════════════════

URL          = "https://cctv.balitower.co.id/Gelora-017-700470_3/tracks-v1/index.m3u8"
PIPE_W       = 1664
PIPE_H       = 1248
FRAME_SIZE   = PIPE_W * PIPE_H * 3
YOLO_MODEL   = "yolov8s.pt"
CONFIDENCE   = 0.15              # confidence lebih rendah untuk kendaraan cepat/partial
DETECT_EVERY = 1                  # deteksi setiap frame

VEHICLE_CLASSES = {1, 2, 3, 5, 7}
CLASS_NAMES = {1: "Sepeda", 2: "Mobil", 3: "Motor", 5: "Bus", 7: "Truk"}
DENSITY_THRESHOLDS = [
    (5,   "SEPI"),
    (15,  "NORMAL"),
    (30,  "RAMAI"),
    (999, "PADAT"),
]
DB_SAVE_INTERVAL = 10   # detik
BROADCAST_INTERVAL = 0.15  # ~7 kali per detik
STREAM_TIMEOUT = 30  # detik — timeout jika tidak ada data frame dalam 30 detik
STREAM_RECONNECT_DELAY = 5  # detik

# ═══════════════════════════════════════════════════════════════════════════════
# FASTAPI APP
# ═══════════════════════════════════════════════════════════════════════════════

app = FastAPI(title="Traffic Density API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ═══════════════════════════════════════════════════════════════════════════════
# SHARED STATE
# ═══════════════════════════════════════════════════════════════════════════════

latest_data = {
    "timestamp": "",
    "density_status": "SEPI",
    "total_vehicles": 0,
    "class_counts": {},
    "boxes": [],       # koordinat ternormalisasi [0.0 - 1.0]
    "labels": [],
}
data_lock = threading.Lock()

# ═══════════════════════════════════════════════════════════════════════════════
# WEBSOCKET MANAGER
# ═══════════════════════════════════════════════════════════════════════════════

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"[WS] Client terhubung. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        print(f"[WS] Client terputus. Total: {len(self.active_connections)}")

    async def broadcast(self, data: dict):
        failed = []
        for connection in self.active_connections:
            try:
                await connection.send_json(data)
            except Exception:
                failed.append(connection)
        for conn in failed:
            self.active_connections.remove(conn)


manager = ConnectionManager()

# ═══════════════════════════════════════════════════════════════════════════════
# UTILITY
# ═══════════════════════════════════════════════════════════════════════════════

def get_density_status(count: int) -> str:
    for threshold, label in DENSITY_THRESHOLDS:
        if count <= threshold:
            return label
    return "PADAT"

# ═══════════════════════════════════════════════════════════════════════════════
# THREAD DETEKSI YOLO (berjalan di background)
# ═══════════════════════════════════════════════════════════════════════════════

def detection_thread():
    global latest_data

    print("[YOLO] Memuat model...")
    model = YOLO(YOLO_MODEL)
    
    # Tentukan device: GPU (cuda) jika tersedia, fallback ke CPU
    device = "0" if torch.cuda.is_available() else "cpu"
    model.to(device)
    
    if torch.cuda.is_available():
        print(f"[YOLO] Model loaded pada GPU: {torch.cuda.get_device_name(0)}")
        print(f"[YOLO] CUDA Capability: {torch.cuda.get_device_capability(0)}")
        print(f"[YOLO] GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
        
        # ─── GPU Warm-up: Run dummy inference untuk activate GPU ──────────
        print("[YOLO] 🔥 GPU Warm-up... (running dummy inference)")
        dummy_frame = np.zeros((PIPE_H, PIPE_W, 3), dtype=np.uint8)
        for _ in range(2):  # 2x dummy inference
            _ = model.predict(dummy_frame, conf=0.5, imgsz=800, device=device, verbose=False)
        print("[YOLO] GPU Warm-up selesai. GPU seharusnya sudah aktif.")
        torch.cuda.empty_cache()  # Clear GPU cache
    else:
        print("[YOLO] ⚠️ CUDA tidak terdeteksi, menggunakan CPU (performa lebih lambat)")
    print("[YOLO] Model siap.")

    def make_ffmpeg_process():
        cmd = [
            "ffmpeg", "-loglevel", "quiet",
            "-i", URL,
            "-f", "rawvideo",
            "-pix_fmt", "bgr24",
            "-vf", f"scale={PIPE_W}:{PIPE_H}",
            "pipe:1"
        ]
        return subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=FRAME_SIZE * 8
        )

    process = make_ffmpeg_process()
    print("[Stream] Membaca CCTV stream...")

    frame_counter   = 0
    last_db_save    = time.time()
    last_boxes      = []
    last_labels     = []
    last_count      = 0
    last_class_counts = {}
    last_read_time = time.time()  # Tracking waktu frame terakhir dibaca

    while True:
        try:
            # ─── Health check: Pastikan proses ffmpeg masih berjalan ─────────
            if process.poll() is not None:
                print("[Stream] ⚠️ Proses ffmpeg terputus. Mencoba reconnect...")
                time.sleep(STREAM_RECONNECT_DELAY)
                process = make_ffmpeg_process()
                last_read_time = time.time()
                continue

            # ─── Gunakan select dengan timeout untuk membaca frame ──────────
            ready, _, _ = select.select([process.stdout], [], [], STREAM_TIMEOUT)
            
            if not ready:
                # Timeout — tidak ada data dalam STREAM_TIMEOUT detik
                print(f"[Stream] ⏱️ Timeout {STREAM_TIMEOUT}s, tidak ada data. Reconnecting...")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                time.sleep(STREAM_RECONNECT_DELAY)
                process = make_ffmpeg_process()
                last_read_time = time.time()
                continue

            # ─── Baca frame ─────────────────────────────────────────────────
            raw = process.stdout.read(FRAME_SIZE)
            
            if len(raw) < FRAME_SIZE:
                print(f"[Stream] ⚠️ Incomplete frame ({len(raw)}/{FRAME_SIZE} bytes). Reconnecting...")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                time.sleep(STREAM_RECONNECT_DELAY)
                process = make_ffmpeg_process()
                last_read_time = time.time()
                continue

            last_read_time = time.time()
            frame = np.frombuffer(raw, np.uint8).reshape((PIPE_H, PIPE_W, 3)).copy()
            frame_counter += 1

            # ─── Jalankan YOLO setiap N frame ────────────────────────────────────
            if frame_counter % DETECT_EVERY == 0:
                results = model.predict(
                    frame,
                    conf=CONFIDENCE,
                    classes=list(VEHICLE_CLASSES),
                    verbose=False,
                    imgsz=800,
                    device=device,
                )

                boxes_norm   = []
                labels       = []
                class_counts = {}

                if results and results[0].boxes is not None and len(results[0].boxes) > 0:
                    boxes_tensor = results[0].boxes.xyxy.cpu().numpy()
                    cls_tensor   = results[0].boxes.cls.cpu().numpy()
                    conf_tensor  = results[0].boxes.conf.cpu().numpy()

                    for box, cls, conf in zip(boxes_tensor, cls_tensor, conf_tensor):
                        x1, y1, x2, y2 = box
                        # Normalisasi ke [0.0 - 1.0] agar fleksibel di berbagai ukuran layar
                        boxes_norm.append([
                            round(float(x1 / PIPE_W), 5),
                            round(float(y1 / PIPE_H), 5),
                            round(float(x2 / PIPE_W), 5),
                            round(float(y2 / PIPE_H), 5),
                        ])
                        cid  = int(cls)
                        name = CLASS_NAMES.get(cid, "?")
                        labels.append(f"{name} {conf:.0%}")
                        class_counts[name] = class_counts.get(name, 0) + 1

                last_boxes        = boxes_norm
                last_labels       = labels
                last_count        = len(boxes_norm)
                last_class_counts = class_counts

            density = get_density_status(last_count)

            # ─── Update shared state ─────────────────────────────────────────────
            with data_lock:
                latest_data = {
                    "timestamp":      time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "density_status": density,
                    "total_vehicles": last_count,
                    "class_counts":   last_class_counts,
                    "boxes":          last_boxes,
                    "labels":         last_labels,
                }

            # ─── Simpan ke Database secara berkala ───────────────────────────────
            now = time.time()
            if now - last_db_save >= DB_SAVE_INTERVAL:
                bicycles    = last_class_counts.get("Sepeda", 0)
                cars        = last_class_counts.get("Mobil", 0)
                motorcycles = last_class_counts.get("Motor", 0)
                buses       = last_class_counts.get("Bus", 0)
                trucks      = last_class_counts.get("Truk", 0)
                threading.Thread(
                    target=database.insert_traffic_data,
                    args=(density, last_count, bicycles, cars, motorcycles, buses, trucks),
                    daemon=True,
                ).start()
                last_db_save = now

        except Exception as e:
            print(f"[Stream] ❌ Error dalam detection_thread: {e}")
            try:
                process.terminate()
                process.wait(timeout=5)
            except:
                process.kill()
            time.sleep(STREAM_RECONNECT_DELAY)
            process = make_ffmpeg_process()
            last_read_time = time.time()

# ═══════════════════════════════════════════════════════════════════════════════
# BROADCAST LOOP (coroutine — kirim data ke semua WebSocket client)
# ═══════════════════════════════════════════════════════════════════════════════

async def broadcast_loop():
    while True:
        await asyncio.sleep(BROADCAST_INTERVAL)
        if manager.active_connections:
            with data_lock:
                data = dict(latest_data)
                # Pastikan lists dapat di-JSON-serialize
                data["boxes"]  = [list(b) for b in data["boxes"]]
                data["labels"] = list(data["labels"])
            await manager.broadcast(data)

# ═══════════════════════════════════════════════════════════════════════════════
# STARTUP
# ═══════════════════════════════════════════════════════════════════════════════

@app.on_event("startup")
async def startup_event():
    print("[DB] Inisialisasi database...")
    database.init_db()
    threading.Thread(target=detection_thread, daemon=True).start()
    asyncio.create_task(broadcast_loop())
    print("[Server] Siap! Buka http://localhost:8000/docs untuk dokumentasi API.")

# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/")
def root():
    return {"status": "running", "message": "Traffic Density API", "docs": "/docs"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Tetap terbuka, menunggu pesan apapun dari client (keep-alive)
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.get("/api/history")
async def get_history(limit: int = 100):
    """Ambil data historis kepadatan dari PostgreSQL."""
    try:
        conn = database.get_connection()
        if conn is None:
            return JSONResponse({"error": "Gagal terhubung ke database"}, status_code=500)

        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, timestamp, density_status, total_vehicles,
                   car_count, motorcycle_count, bus_count, truck_count
            FROM traffic_history_h2
            ORDER BY timestamp DESC
            LIMIT %s
            """,
            (limit,),
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()

        return [
            {
                "id":               row[0],
                "timestamp":        row[1].strftime("%Y-%m-%d %H:%M:%S"),
                "density_status":   row[2],
                "total_vehicles":   row[3],
                "car_count":        row[4],
                "motorcycle_count": row[5],
                "bus_count":        row[6],
                "truck_count":      row[7],
            }
            for row in rows
        ]
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/status")
def get_status():
    """Snapshot data deteksi terkini (tanpa WebSocket)."""
    with data_lock:
        return dict(latest_data)
