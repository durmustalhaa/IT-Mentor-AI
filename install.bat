@echo off
REM IT Mentor AI - tek seferlik kurulum. Cift tiklaninca:
REM   1) Python kurulu mu kontrol eder (kurulu degilse SESSIZCE hicbir sey
REM      kurmaz, sadece nereden indirilecegini soyler)
REM   2) requirements.txt'i kurar
REM   3) RAG index'i yoksa olusturur (data/processed/dataset.jsonl'den)
REM   4) Masaustune "IT Mentor AI" kisayolunu birakir

where python >nul 2>nul
if errorlevel 1 (
    echo Python bulunamadi.
    echo Once Python'u kurun: https://www.python.org/downloads/
    echo Kurulumda "Add python.exe to PATH" secenegini isaretlemeyi unutmayin.
    pause
    exit /b 1
)

echo Bagimliliklar kuruluyor...
pip install -r requirements.txt
if errorlevel 1 (
    echo pip install basarisiz oldu, yukaridaki hataya bakin.
    pause
    exit /b 1
)

if not exist "data\processed\rag_index\embeddings.npy" (
    echo.
    echo RAG arama index'i olusturuluyor, bu ~25 saniye surebilir...
    python scripts\build_index.py
    if errorlevel 1 (
        echo Index olusturma basarisiz oldu, yukaridaki hataya bakin.
        pause
        exit /b 1
    )
)

echo.
echo Masaustu kisayolu olusturuluyor...
powershell -ExecutionPolicy Bypass -File scripts\create_shortcut.ps1

echo.
echo Kurulum tamamlandi. Masaustunde "IT Mentor AI" kisayolunu kullanabilirsiniz.
pause
