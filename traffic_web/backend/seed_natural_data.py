import os
import csv
import psycopg2
from dotenv import load_dotenv
import datetime
from database import get_connection

def seed_natural_data():
    conn = get_connection()
    if conn is None:
        print("Gagal terhubung ke database.")
        return
        
    cur = conn.cursor()
    
    # Path file CSV
    csv_files = [
        r"c:\Users\Fahrezi\Documents\KULIAH\Semester 6\IOT\Traffic-Density-Prediction\traffic_data_collection\collected_data\Senin.csv",
        r"c:\Users\Fahrezi\Documents\KULIAH\Semester 6\IOT\Traffic-Density-Prediction\traffic_data_collection\collected_data\Selasa.csv"
    ]
    
    records = []
    now = datetime.datetime.now()
    yesterday = now - datetime.timedelta(days=1)
    
    for file_path in csv_files:
        if not os.path.exists(file_path):
            print(f"File tidak ditemukan: {file_path}")
            continue
            
        print(f"Membaca file: {file_path}")
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) < 9:
                    continue
                
                try:
                    # Format: 1,2026-06-01 06:08:42.482917,Empty,5,0,5,0,0,0
                    dt_str = row[1]
                    if '.' in dt_str:
                        orig_dt = datetime.datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S.%f")
                    else:
                        orig_dt = datetime.datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
                        
                    hour = orig_dt.hour
                    minute = orig_dt.minute
                    
                    # Filter jam 23:06 - 11:00
                    if hour == 23 and minute >= 6:
                        # Jam 23:06 - 23:59 (Set ke tanggal kemarin)
                        new_dt = orig_dt.replace(year=yesterday.year, month=yesterday.month, day=yesterday.day)
                    elif hour < 11 or (hour == 11 and minute == 0):
                        # Jam 00:00 - 11:00 (Set ke tanggal hari ini)
                        new_dt = orig_dt.replace(year=now.year, month=now.month, day=now.day)
                    else:
                        # Diluar rentang 23:06 - 11:00
                        continue
                        
                    status = row[2]
                    total = int(row[3])
                    bike = int(row[4])
                    car = int(row[5])
                    motor = int(row[6])
                    bus = int(row[7])
                    truck = int(row[8])
                    
                    records.append((new_dt, status, total, bike, car, motor, bus, truck))
                except Exception as e:
                    # Skip error parsing
                    pass
                    
    if not records:
        print("Tidak ada data yang sesuai dengan rentang waktu 23:06 - 11:00 di dalam file CSV.")
        return
        
    insert_query = '''
        INSERT INTO traffic_history (
            timestamp, density_status, total_vehicles, bicycle_count, car_count, motorcycle_count, bus_count, truck_count
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    '''
    
    print(f"Menyisipkan {len(records)} baris data natural ke database...")
    try:
        cur.executemany(insert_query, records)
        conn.commit()
        print(f"[Seed] Berhasil memasukkan {len(records)} baris data natural ke database.")
    except Exception as e:
        print(f"[Seed] Gagal memasukkan data: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    seed_natural_data()
