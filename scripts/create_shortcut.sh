#!/bin/bash
# "IT Mentor AI" masaüstü/uygulama menüsü kısayolu (.desktop dosyası)
# oluşturur - create_shortcut.ps1'in Linux karşılığı. Yeniden
# çalıştırmak kısayolu günceller (var olanın üzerine aynı ayarlarla
# yazar).
#
# Python: proje kökünde bir "venv/" varsa onun python3'ü kullanılır
# (bağımlılıklar oradadır); yoksa PATH'teki sistem python3'üne düşer.

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ -x "$PROJECT_ROOT/venv/bin/python3" ]; then
    PYTHON="$PROJECT_ROOT/venv/bin/python3"
else
    PYTHON="$(command -v python3 || true)"
fi

if [ -z "$PYTHON" ]; then
    echo "HATA: Çalışan bir Python 3 kurulumu bulunamadı."
    echo "Kurun: sudo dnf install python3 python3-pip -y"
    exit 1
fi

GUI_SCRIPT="$PROJECT_ROOT/scripts/gui_app.py"
ICON_ICO="$PROJECT_ROOT/assets/app_icon.ico"
ICON_PNG="$PROJECT_ROOT/assets/app_icon.png"

# .desktop dosyaları .ico'yu güvenilir göstermiyor (masaüstü ortamına/
# icon temasına göre değişiyor) - Pillow zaten bir proje bağımlılığı
# (requirements.txt), tek seferlik PNG'ye çeviriyoruz. Pillow kurulu
# değilse (venv/sistem python'da yoksa) sessizce atlanır, .ico dosyası
# olduğu gibi denenir - hiçbir durumda kısayol oluşturmayı engellemez.
if [ ! -f "$ICON_PNG" ]; then
    "$PYTHON" -c "
from PIL import Image
Image.open('$ICON_ICO').save('$ICON_PNG')
" 2>/dev/null || true
fi

if [ -f "$ICON_PNG" ]; then
    ICON_PATH="$ICON_PNG"
else
    ICON_PATH="$ICON_ICO"
fi

DESKTOP_ENTRY="[Desktop Entry]
Type=Application
Name=IT Mentor AI
Comment=Offline IT-ops asistanı
Exec=\"$PYTHON\" \"$GUI_SCRIPT\"
Path=$PROJECT_ROOT
Icon=$ICON_PATH
Terminal=false
Categories=Utility;
"

APPS_DIR="$HOME/.local/share/applications"
mkdir -p "$APPS_DIR"
APPS_FILE="$APPS_DIR/it-mentor-ai.desktop"
printf '%s' "$DESKTOP_ENTRY" > "$APPS_FILE"
chmod +x "$APPS_FILE"

echo "Uygulama menüsüne eklendi: $APPS_FILE"

if [ -d "$HOME/Desktop" ]; then
    DESKTOP_FILE="$HOME/Desktop/it-mentor-ai.desktop"
    printf '%s' "$DESKTOP_ENTRY" > "$DESKTOP_FILE"
    chmod +x "$DESKTOP_FILE"

    # GNOME, masaüstündeki yeni .desktop dosyalarını varsayılan olarak
    # "güvenilmez" işaretleyip çift tıklamayı reddediyor (kullanıcının
    # sağ tıklayıp "Başlatmaya İzin Ver" demesi gerekiyor) - gio ile
    # bunu otomatik "güvenilir" işaretliyoruz. gio yoksa (GNOME dışı
    # bir masaüstü) sessizce atlanır, dosya yine de oradadır.
    if command -v gio >/dev/null 2>&1; then
        gio set "$DESKTOP_FILE" "metadata::trusted" "true" 2>/dev/null || true
    fi

    echo "Masaüstü simgesi oluşturuldu: $DESKTOP_FILE"
fi
