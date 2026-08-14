#!/bin/bash
# IT Mentor AI - tek seferlik kurulum (Linux). Çalıştırınca:
#   1) python3 kurulu mu kontrol eder (kurulu değilse SESSİZCE hiçbir
#      şey kurmaz, sadece nereden kurulacağını söyler)
#   2) bir "venv/" oluşturur (yoksa) ve requirements.txt'i kurar
#   3) RAG index'i yoksa oluşturur (data/processed/dataset.jsonl'den)
#   4) Uygulama menüsüne/masaüstüne "IT Mentor AI" kısayolunu bırakır
#
# Not: requirements.txt'teki "torch" varsayılan (CUDA'lı) sürümü
# kurar - GPU'suz bir makinede de çalışır, sadece gereksiz yere büyük
# iner. Daha küçük/hızlı bir kurulum istersen bu script'ten önce elle:
#   python3 -m venv venv && venv/bin/pip install torch --index-url https://download.pytorch.org/whl/cpu

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 bulunamadı."
    echo "Kurun: sudo dnf install python3 python3-pip -y   (Rocky/RHEL/Fedora)"
    echo "       sudo apt install python3 python3-venv -y  (Debian/Ubuntu)"
    exit 1
fi

if [ ! -d "venv" ]; then
    echo "Sanal ortam (venv) oluşturuluyor..."
    python3 -m venv venv
fi

echo "Bağımlılıklar kuruluyor..."
venv/bin/pip install -r requirements.txt

if [ ! -f "data/processed/rag_index/embeddings.npy" ]; then
    echo
    echo "RAG arama index'i oluşturuluyor, boyuta ve donanıma göre birkaç dakika sürebilir..."
    venv/bin/python scripts/build_index.py
fi

echo
echo "Kısayol oluşturuluyor..."
bash scripts/create_shortcut.sh

echo
echo 'Kurulum tamamlandı. Uygulama menüsünden (ya da varsa masaüstünden) "IT Mentor AI"yı açabilirsiniz.'
