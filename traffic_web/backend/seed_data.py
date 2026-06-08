import os
import psycopg2
from dotenv import load_dotenv
import datetime
import random
from database import get_connection

def seed_data():
    conn = get_connection()
    if conn is None:
        print("Gagal terhubung ke database.")
        return
        
    cur = conn.cursor()
    
    now = datetime.datetime.now()
    
    # Menentukan range waktu (Kemarin 23:06 sampai Hari ini 11:00)
    # Jika sekarang belum jam 11 pagi, maka targetnya adalah kemarin jam 23 sampai hari ini jam 11
    start_time = datetime.datetime(now.year, now.month, now.day, 23, 6) - datetime.timedelta(days=1)
    end_time = datetime.datetime(now.year, now.month, now.day, 11, 0)
    
    # Pastikan start_time selalu di belakang end_time
    if start_time > end_time:
        start_time -= datetime.timedelta(days=1)
        
    current_time = start_time
    
    insert_query = '''
        INSERT INTO traffic_history (
            timestamp, density_status, total_vehicles, bicycle_count, car_count, motorcycle_count, bus_count, truck_count
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    '''
    
    records = []
    print(f"Mengumpulkan data dummy dari {start_time.strftime('%Y-%m-%d %H:%M:%S')} hingga {end_time.strftime('%Y-%m-%d %H:%M:%S')}...")
    
    while current_time <= end_time:
        # Membuat variasi kemacetan berdasarkan jam
        hour = current_time.hour
        if 7 <= hour <= 10 or 16 <= hour <= 19:
            # Jam sibuk (pagi/sore)
            total = random.randint(45, 80)
            status = "Macet" if total >= 50 else "Sedang"
        elif 0 <= hour <= 4:
            # Tengah malam (sepi)
            total = random.randint(2, 12)
            status = "Lancar"
        else:
            # Jam biasa
            total = random.randint(15, 35)
            status = "Lancar" if total < 20 else "Sedang"
            
        # Distribusi jenis kendaraan (perkiraan)
        car = int(total * 0.4)
        motor = int(total * 0.45)
        bus = int(total * 0.05)
        truck = int(total * 0.05)
        bike = total - (car + motor + bus + truck)
        
        records.append((current_time, status, total, bike, car, motor, bus, truck))
        
        # Tambah waktu 10 detik (Sesuai dengan interval YOLO kita)
        current_time += datetime.timedelta(seconds=10)
        
    try:
        # Eksekusi insert banyak data sekaligus
        cur.executemany(insert_query, records)
        conn.commit()
        print(f"[Seed] Berhasil memasukkan {len(records)} baris data dummy ke database.")
    except Exception as e:
        print(f"[Seed] Gagal memasukkan data: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    seed_data()
