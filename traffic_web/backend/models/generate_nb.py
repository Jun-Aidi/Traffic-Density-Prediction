import json

cells = [
    {"cell_type": "markdown", "metadata": {}, "source": ["# Prediksi Jangka Pendek (Short-Term Forecasting)\n", "Notebook ini difokuskan pada opsi 1: Memprediksi kondisi lalu lintas (volume kendaraan) untuk 15-60 menit ke depan menggunakan data histori yang kita miliki. Kita akan me-resample data menjadi interval 15 menit dan membuat fitur Lag (waktu sebelumnya) untuk memprediksi waktu berikutnya."]},
    {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": ["import pandas as pd\n", "import numpy as np\n", "import glob\n", "import matplotlib.pyplot as plt\n", "from sklearn.ensemble import RandomForestRegressor\n", "from sklearn.metrics import mean_absolute_error\n", "from sklearn.model_selection import train_test_split\n", "\n", "import warnings\n", "warnings.filterwarnings('ignore')\n", "\n", "# 1. Memuat Data dari collected_data\n", "data_path = '../collected_data/*.csv'\n", "files = glob.glob(data_path)\n", "\n", "cols = ['ID', 'Timestamp', 'Density', 'Total', 'Person', 'Car', 'Motorcycle', 'Bus', 'Truck']\n", "df_list = []\n", "\n", "for f in files:\n", "    df = pd.read_csv(f, names=cols)\n", "    df_list.append(df)\n", "\n", "# Menggabungkan semua data\n", "df_all = pd.concat(df_list, ignore_index=True)\n", "df_all['Timestamp'] = pd.to_datetime(df_all['Timestamp'])\n", "\n", "# Mengurutkan berdasarkan waktu (Time-Series harus urut waktu)\n", "df_all = df_all.sort_values('Timestamp').reset_index(drop=True)\n", "\n", "print(f\"Total baris data mentah: {len(df_all)}\")\n", "df_all.head()"]},
    {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": ["# 2. Resampling Data ke Interval 15 Menit\n", "# Karena data dicatat setiap ~5 detik, kita akan mengambil rata-rata jumlah kendaraan per 15 menit.\n", "df_all.set_index('Timestamp', inplace=True)\n", "\n", "# Resample rata-rata per 15 menit\n", "df_resampled = df_all[['Total', 'Car', 'Motorcycle']].resample('15T').mean()\n", "\n", "# Jika ada jam yang kosong (tidak ada rekaman), kita isi dengan interpolasi atau ffill\n", "df_resampled = df_resampled.interpolate(method='linear')\n", "df_resampled = df_resampled.dropna()\n", "\n", "print(f\"Total baris setelah resample 15 menit: {len(df_resampled)}\")\n", "df_resampled.head()"]},
    {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": ["# 3. Membuat Fitur Lag (Jendela Waktu ke Belakang)\n", "# Kita akan memprediksi 'Total' kendaraan di waktu T\n", "# berdasarkan 'Total' di T-1 (15 mnt lalu), T-2 (30 mnt lalu), dan T-3 (45 mnt lalu).\n", "\n", "df_features = df_resampled.copy()\n", "\n", "df_features['Lag_1'] = df_features['Total'].shift(1)  # 15 menit lalu\n", "df_features['Lag_2'] = df_features['Total'].shift(2)  # 30 menit lalu\n", "df_features['Lag_3'] = df_features['Total'].shift(3)  # 45 menit lalu\n", "df_features['Lag_4'] = df_features['Total'].shift(4)  # 60 menit lalu\n", "\n", "# Menambah fitur waktu untuk membantu model mengenali pola harian\n", "df_features['Hour'] = df_features.index.hour\n", "df_features['Minute'] = df_features.index.minute\n", "df_features['DayOfWeek'] = df_features.index.dayofweek\n", "\n", "# Hapus baris yang mengandung NaN akibat fungsi shift\n", "df_features = df_features.dropna()\n", "\n", "df_features.head()"]},
    {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": ["# 4. Membagi Data (Train dan Test)\n", "# Karena ini time-series, kita tidak boleh mengacak secara random (train_test_split biasa dengan shuffle=True).\n", "# Kita gunakan urutan waktu. Misalnya 80% data pertama untuk Train, 20% terakhir untuk Test.\n", "\n", "X = df_features[['Lag_1', 'Lag_2', 'Lag_3', 'Lag_4', 'Hour', 'Minute', 'DayOfWeek']]\n", "y = df_features['Total']\n", "\n", "split_idx = int(len(df_features) * 0.8)\n", "\n", "X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]\n", "y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]\n", "\n", "print(f\"Ukuran Train: {len(X_train)}\")\n", "print(f\"Ukuran Test: {len(X_test)}\")"]},
    {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": ["# 5. Melatih Model Machine Learning (Random Forest)\n", "model = RandomForestRegressor(n_estimators=100, random_state=42)\n", "model.fit(X_train, y_train)\n", "\n", "# Evaluasi\n", "y_pred = model.predict(X_test)\n", "mae = mean_absolute_error(y_test, y_pred)\n", "\n", "print(f\"Mean Absolute Error (MAE): {mae:.2f} kendaraan\")\n", "print(\"Artinya, prediksi kita rata-rata meleset sekitar {:.2f} kendaraan dari kondisi aslinya.\".format(mae))"]},
    {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": ["# 6. Visualisasi Hasil Prediksi\n", "plt.figure(figsize=(15, 5))\n", "plt.plot(y_test.index, y_test.values, label='Aktual (Ground Truth)', marker='.')\n", "plt.plot(y_test.index, y_pred, label='Prediksi (Random Forest)', marker='x', alpha=0.7)\n", "plt.title('Prediksi Volume Lalu Lintas vs Aktual (Data Test)')\n", "plt.xlabel('Waktu')\n", "plt.ylabel('Rata-rata Kendaraan per 15 Menit')\n", "plt.legend()\n", "plt.grid(True)\n", "plt.show()"]},
    {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": ["# 7. Simulasi Prediksi 15 Menit Kedepan dari Kondisi \"Sekarang\"\n", "# Anggap data_terakhir adalah kondisi jalanan saat ini.\n", "\n", "data_terakhir = df_features.iloc[-1:]\n", "\n", "print(\"Kondisi Terakhir (Saat ini):\")\n", "print(data_terakhir[['Total', 'Hour', 'Minute']])\n", "\n", "# Untuk memprediksi 15 menit KE DEPAN, nilai lag akan bergeser.\n", "fitur_selanjutnya = pd.DataFrame({\n", "    'Lag_1': [data_terakhir['Total'].values[0]],\n", "    'Lag_2': [data_terakhir['Lag_1'].values[0]],\n", "    'Lag_3': [data_terakhir['Lag_2'].values[0]],\n", "    'Lag_4': [data_terakhir['Lag_3'].values[0]],\n", "    'Hour': [(data_terakhir.index[-1] + pd.Timedelta(minutes=15)).hour],\n", "    'Minute': [(data_terakhir.index[-1] + pd.Timedelta(minutes=15)).minute],\n", "    'DayOfWeek': [(data_terakhir.index[-1] + pd.Timedelta(minutes=15)).dayofweek]\n", "})\n", "\n", "prediksi_depan = model.predict(fitur_selanjutnya)\n", "\n", "print(\"\\n--- PREDIKSI ---\")\n", "waktu_depan = data_terakhir.index[-1] + pd.Timedelta(minutes=15)\n", "print(f\"Prediksi rata-rata kendaraan pada {waktu_depan.strftime('%Y-%m-%d %H:%M')} adalah: {prediksi_depan[0]:.2f}\")"]}
]

notebook = {
    "cells": cells,
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3"
        },
        "language_info": {
            "codemirror_mode": {"name": "ipython", "version": 3},
            "file_extension": ".py",
            "mimetype": "text/x-python",
            "name": "python",
            "nbconvert_exporter": "python",
            "pygments_lexer": "ipython3",
            "version": "3.8.0"
        }
    },
    "nbformat": 4,
    "nbformat_minor": 4
}

with open("c:\\Users\\Fahrezi\\Documents\\KULIAH\\Semester 6\\IOT\\Traffic-Density-Prediction\\traffic_web\\backend\\models\\short_term_forecasting.ipynb", "w", encoding="utf-8") as f:
    json.dump(notebook, f, indent=2, ensure_ascii=False)
