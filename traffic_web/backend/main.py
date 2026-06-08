import subprocess
import numpy as np
import threading
import time
import asyncio
import select
import torch
import joblib
import pandas as pd
import datetime
from ultralytics import YOLO
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, Response
import urllib.request
from dotenv import load_dotenv
import database

load_dotenv()

# =============================================================================
# KONFIGURASI AI YOLO
# =============================================================================
URL          = "https://cctv.balitower.co.id/Gelora-017-700470_3/tracks-v1/index.m3u8"
PIPE_W       = 1664
PIPE_H       = 1248
FRAME_SIZE   = PIPE_W * PIPE_H * 3
YOLO_MODEL   = "yolov8s.pt"
CONFIDENCE   = 0.15
DETECT_EVERY = 1

VEHICLE_CLASSES = {1, 2, 3, 5, 7}
CLASS_NAMES = {1: "Sepeda", 2: "Mobil", 3: "Motor", 5: "Bus", 7: "Truk"}

DB_SAVE_INTERVAL = 10   # Simpan ke DB setiap 10 detik
STREAM_TIMEOUT = 30
STREAM_RECONNECT_DELAY = 5

app = FastAPI(title="Traffic Radar API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================================
# LOAD RANDOM FOREST MODEL
# =============================================================================
try:
    rf_model = joblib.load('models/rf_traffic_model.pkl')
    print("[RF] Model Random Forest berhasil dimuat.")
except Exception as e:
    print(f"[RF] Gagal memuat model Random Forest: {e}")
    rf_model = None

# =============================================================================
# SHARED STATE
# =============================================================================
latest_data = {
    "location": "Gelora 0-17",
    "density_per_5s": 0,
    "status_id": "Lancar",
    "status_en": "Low",
    "last_update": ""
}
data_lock = threading.Lock()

def get_density_mapping(count: int):
    if count < 8:
        return "Lancar", "Low"
    elif count < 20:
        return "Lancar", "Low"
    elif count < 50:
        return "Sedang", "Medium"
    else:
        return "Macet", "High"

# =============================================================================
# THREAD DETEKSI YOLO (Background)
# =============================================================================
def detection_thread():
    global latest_data

    print("[YOLO] Memuat model...")
    model = YOLO(YOLO_MODEL)
    
    device = "0" if torch.cuda.is_available() else "cpu"
    model.to(device)
    
    if torch.cuda.is_available():
        print(f"[YOLO] Menggunakan GPU: {torch.cuda.get_device_name(0)}")
    else:
        print("[YOLO] Menggunakan CPU.")

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
    last_count      = 0
    last_class_counts = {}

    while True:
        try:
            if process.poll() is not None:
                print("[Stream] ffmpeg terputus. Reconnecting...")
                time.sleep(STREAM_RECONNECT_DELAY)
                process = make_ffmpeg_process()
                continue

            raw = process.stdout.read(FRAME_SIZE)
            
            if not raw or len(raw) < FRAME_SIZE:
                print("[Stream] Incomplete frame or stream disconnected. Reconnecting...")
                process.terminate()
                try: process.wait(timeout=5)
                except: process.kill()
                time.sleep(STREAM_RECONNECT_DELAY)
                process = make_ffmpeg_process()
                continue

            frame = np.frombuffer(raw, np.uint8).reshape((PIPE_H, PIPE_W, 3)).copy()
            frame_counter += 1

            if frame_counter % DETECT_EVERY == 0:
                results = model.predict(
                    frame,
                    conf=CONFIDENCE,
                    classes=list(VEHICLE_CLASSES),
                    verbose=False,
                    imgsz=800,
                    device=device,
                )

                class_counts = {}
                if results and results[0].boxes is not None and len(results[0].boxes) > 0:
                    cls_tensor   = results[0].boxes.cls.cpu().numpy()
                    for cls in cls_tensor:
                        name = CLASS_NAMES.get(int(cls), "?")
                        class_counts[name] = class_counts.get(name, 0) + 1
                    
                    last_count = len(results[0].boxes)
                else:
                    last_count = 0
                    
                last_class_counts = class_counts

            status_id, status_en = get_density_mapping(last_count)

            with data_lock:
                latest_data = {
                    "location": "Gelora 0-17",
                    "density_per_5s": last_count,
                    "status_id": status_id,
                    "status_en": status_en,
                    "last_update": time.strftime("%Y-%m-%d %H:%M:%S")
                }

            now = time.time()
            if now - last_db_save >= DB_SAVE_INTERVAL:
                database.insert_traffic_data(
                    density_status=status_id,
                    total=last_count,
                    bicycle=last_class_counts.get("Sepeda", 0),
                    car=last_class_counts.get("Mobil", 0),
                    motorcycle=last_class_counts.get("Motor", 0),
                    bus=last_class_counts.get("Bus", 0),
                    truck=last_class_counts.get("Truk", 0)
                )
                last_db_save = now

        except Exception as e:
            print(f"[Stream] Error: {e}")
            try: process.terminate(); process.wait(timeout=5)
            except: process.kill()
            time.sleep(STREAM_RECONNECT_DELAY)
            process = make_ffmpeg_process()

# =============================================================================
# STARTUP
# =============================================================================
@app.on_event("startup")
def startup_event():
    print("[DB] Menginisialisasi database...")
    database.init_db()
    print("[Stream] Memulai deteksi CCTV di background...")
    threading.Thread(target=detection_thread, daemon=True).start()

# =============================================================================
# ENDPOINTS UTAMA
# =============================================================================
@app.get("/")
def read_root():
    return {"message": "Traffic Radar API is running"}

@app.get("/api/traffic/current")
def get_current():
    with data_lock:
        return dict(latest_data)

@app.get("/api/traffic/prediction")
def get_pred():
    """
    Returns AI prediction for the next 15 minutes using the RF Model.
    """
    if rf_model is None:
        return {"status": "Model Tidak Tersedia", "desc": "Gagal memuat model Machine Learning."}

    lag_1 = database.get_average_traffic(15, 0)
    lag_2 = database.get_average_traffic(30, 15)
    lag_3 = database.get_average_traffic(45, 30)
    lag_4 = database.get_average_traffic(60, 45)

    # Jika db kosong sama sekali, fallback ke latest count
    if lag_1 == 0:
        lag_1 = latest_data["density_per_5s"]

    target_time = datetime.datetime.now() + datetime.timedelta(minutes=15)
    hour = target_time.hour
    minute = target_time.minute
    day_of_week = target_time.weekday()

    features = pd.DataFrame({
        'Lag_1': [lag_1],
        'Lag_2': [lag_2],
        'Lag_3': [lag_3],
        'Lag_4': [lag_4],
        'Hour': [hour],
        'Minute': [minute],
        'DayOfWeek': [day_of_week]
    })

    try:
        pred_val = rf_model.predict(features)[0]
    except Exception as e:
        print(f"[RF Error] {e}")
        pred_val = lag_1

    # Terjemahkan pred_val ke status teks
    if pred_val < 20:
        status = "Kondisi Stabil (Lancar)"
        desc = f"Diprediksi tetap lancar dengan rata-rata {pred_val:.0f} kendaraan dalam 15 menit ke depan."
    elif pred_val < 50:
        status = "Potensi Kepadatan Naik"
        desc = f"Volume meningkat. Diprediksi ada sekitar {pred_val:.0f} kendaraan dalam 15 menit ke depan."
    else:
        status = "Rawan Macet"
        desc = f"Kondisi padat diprediksi bertahan dengan estimasi {pred_val:.0f} kendaraan pada 15 menit ke depan."

    return {
        "status": status,
        "desc": desc,
        "predicted_value": round(pred_val, 1)
    }

@app.get("/api/traffic/history")
def get_history():
    """
    Returns hourly data for the chart from database.
    """
    return database.get_hourly_history()

# =============================================================================
# CCTV PROXY ENDPOINTS (CORS BYPASS)
# =============================================================================
@app.get("/api/proxy/{path:path}")
def proxy_hls(path: str, request: Request):
    target_url = "https://cctv.balitower.co.id/" + path
    if request.url.query:
        target_url += "?" + request.url.query
    
    req = urllib.request.Request(target_url, headers={
        'User-Agent': 'Mozilla/5.0',
        'Referer': 'https://cctv.balitower.co.id/'
    })
    
    try:
        response = urllib.request.urlopen(req)
        content_type = response.headers.get('Content-Type', 'application/octet-stream')
        def iterfile():
            while True:
                chunk = response.read(65536)
                if not chunk: break
                yield chunk
        return StreamingResponse(iterfile(), media_type=content_type)
    except Exception as e:
        return Response(content=str(e), status_code=500)

@app.get("/api/cctv")
def get_cctv_player():
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>CCTV Player</title>
        <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
        <style>body, html { margin: 0; padding: 0; width: 100%; height: 100%; background: black; overflow: hidden; }</style>
    </head>
    <body>
        <video id="video" autoplay muted controls style="width: 100%; height: 100%; object-fit: cover;"></video>
        <script>
            var video = document.getElementById('video');
            var url = '/api/proxy/Gelora-017-700470_3/tracks-v1/index.m3u8';
            if (Hls.isSupported()) {
                var hls = new Hls({ debug: false });
                hls.loadSource(url);
                hls.attachMedia(video);
                hls.on(Hls.Events.MANIFEST_PARSED, function() {
                    video.play().catch(e => console.log("Autoplay prevented:", e));
                });
            } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
                video.src = url;
                video.addEventListener('loadedmetadata', function() {
                    video.play().catch(e => console.log("Autoplay prevented:", e));
                });
            }
        </script>
    </body>
    </html>
    """
    return Response(content=html_content, media_type="text/html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
