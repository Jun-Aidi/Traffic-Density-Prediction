@echo off
echo ============================================
echo  Setup Virtual Environment - Traffic Detect
echo ============================================
echo.

REM Buat virtual environment
echo [1/3] Membuat virtual environment...
python -m venv venv
if errorlevel 1 (
    echo ERROR: Gagal membuat venv. Pastikan Python 3.8+ terinstall.
    pause
    exit /b 1
)

REM Aktivasi venv
echo [2/3] Mengaktifkan venv...
call venv\Scripts\activate.bat

REM Install dependensi
echo [3/3] Menginstall dependensi...
pip install --upgrade pip
pip install numpy opencv-python ultralytics

echo.
echo ============================================
echo  Setup selesai!
echo ============================================
echo.
echo Untuk menjalankan:
echo   1. call venv\Scripts\activate.bat
echo   2. python detect_traffic.py
echo.
echo Atau langsung jalankan: run.bat
echo.
pause
