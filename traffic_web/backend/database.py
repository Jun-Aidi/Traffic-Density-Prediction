import os
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_connection():
    """Membuat koneksi ke database PostgreSQL berdasarkan variabel .env"""
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", "osa153uj54"),
            dbname=os.getenv("DB_NAME", "traffic_db_v1")
        )
        return conn
    except Exception as e:
        print(f"[DB] Error connecting to PostgreSQL: {e}")
        return None

def init_db():
    """Inisialisasi database (membuat tabel jika belum ada)"""
    conn = get_connection()
    if conn is None:
        return
    
    try:
        cur = conn.cursor()
        create_table_query = '''
        CREATE TABLE IF NOT EXISTS traffic_history (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            density_status VARCHAR(50),
            total_vehicles INTEGER,
            bicycle_count INTEGER,
            car_count INTEGER,
            motorcycle_count INTEGER,
            bus_count INTEGER,
            truck_count INTEGER
        )
        '''
        cur.execute(create_table_query)
        conn.commit()
        cur.close()
        print("[DB] Tabel 'traffic_history' siap digunakan.")
    except Exception as e:
        print(f"[DB] Gagal membuat tabel: {e}")
    finally:
        conn.close()

def insert_traffic_data(density_status, total, bicycle, car, motorcycle, bus, truck):
    """Insert detection data into the database"""
    conn = get_connection()
    if conn is None:
        return
    
    try:
        cur = conn.cursor()
        insert_query = '''
        INSERT INTO traffic_history (
            density_status, total_vehicles, bicycle_count, car_count, motorcycle_count, bus_count, truck_count
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        '''
        cur.execute(insert_query, (density_status, total, bicycle, car, motorcycle, bus, truck))
        conn.commit()
        cur.close()
        print(f"[DB] Data saved: {density_status} ({total} vehicles)")
    except Exception as e:
        print(f"[DB] Failed to save data: {e}")
    finally:
        conn.close()

def get_average_traffic(start_min, end_min):
    """Mengambil rata-rata jumlah kendaraan dari X menit yang lalu hingga Y menit yang lalu"""
    conn = get_connection()
    if conn is None:
        return 0.0
    
    try:
        cur = conn.cursor()
        query = '''
            SELECT AVG(total_vehicles) 
            FROM traffic_history 
            WHERE timestamp >= NOW() - INTERVAL '%s minutes' 
              AND timestamp < NOW() - INTERVAL '%s minutes'
        '''
        cur.execute(query, (start_min, end_min))
        result = cur.fetchone()[0]
        cur.close()
        return float(result) if result else 0.0
    except Exception as e:
        print(f"[DB] Gagal membaca average data: {e}")
        return 0.0
    finally:
        conn.close()

def get_hourly_history():
    """Mengambil riwayat kemacetan per jam untuk grafik (contoh 24 jam terakhir)"""
    conn = get_connection()
    if conn is None:
        return []
    
    try:
        cur = conn.cursor()
        query = '''
            SELECT 
                EXTRACT(HOUR FROM timestamp) as hour,
                AVG(total_vehicles) as avg_vehicles
            FROM traffic_history
            WHERE timestamp >= NOW() - INTERVAL '24 hours'
            GROUP BY EXTRACT(HOUR FROM timestamp)
            ORDER BY hour ASC
        '''
        cur.execute(query)
        rows = cur.fetchall()
        cur.close()
        
        data = []
        for row in rows:
            hour_str = f"{int(row[0]):02d}"
            avg_val = int(row[1])
            data.append({
                "hour": hour_str,
                "value": avg_val,
                "high": avg_val >= 50
            })
        return data
    except Exception as e:
        print(f"[DB] Gagal membaca hourly history: {e}")
        return []
    finally:
        conn.close()

# Tambahkan ini di paling bawah database.py
if __name__ == "__main__":
    print("Menyiapkan database...")
    init_db()

