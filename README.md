# IT Mentor AI

Offline çalışan bir IT-ops asistanı: Git, Linux, Windows, Docker,
systemd, networking ve daha fazlası hakkındaki soruları, gerçek
dokümantasyondan (RAG) veya (veri yoksa) yerel bir dil modelinden
cevaplıyor. İnternet bağlantısı sadece ilk kurulumda model indirmek
için gerekiyor, sonrasında tamamen offline çalışır.

## Kurulum (Windows, hızlı yol)

Python (https://www.python.org/downloads/, "Add python.exe to PATH"
işaretli) kuruluysa, `windows_setup.bat`'a çift tıklamak yeterli:
bağımlılıkları kurar, RAG index'ini oluşturur, masaüstüne "IT Mentor
AI" kısayolunu bırakır. Script şeffaf - içinde sadece `pip install`,
`build_index.py` ve `create_shortcut.ps1` çağrıları var, hiçbir şeyi
sessizce kurmuyor; Python bulunamazsa sadece nereden indireceğini
söyleyip çıkıyor.

## Kurulum (Linux, hızlı yol)

Python 3 kuruluysa (`sudo dnf install python3 python3-pip -y` gibi),
`linux_setup.sh`'i çalıştırmak yeterli:
```
bash linux_setup.sh
```
`windows_setup.bat`'ın Linux karşılığı, aynı adımları izliyor: bir
`venv/` oluşturur, bağımlılıkları kurar, RAG index'ini oluşturur,
uygulama menüsüne (ve varsa masaüstüne) "IT Mentor AI" kısayolunu
bırakır (`.desktop` dosyası - Windows'taki `.lnk` kısayolunun Linux
karşılığı). GPU'suz bir makinedeysen ve daha küçük/hızlı bir kurulum
istersen, `linux_setup.sh`'ten önce `torch`'un CPU-only sürümünü elle
kurabilirsin - script'in kendi içindeki not'a bakabilirsin.

## Kurulum (elle)

```
pip install -r requirements.txt
python scripts/build_index.py
```

Dataset (`data/processed/dataset.jsonl`, `commands.json`) bu repoda
hazır geliyor. RAG arama index'i (`data/processed/rag_index/`) repoda
**yok** - `embeddings.npy` GitHub'ın dosya boyutu limitini aştığı için
dahil edilmedi, `build_index.py` ile ~25 saniyede yerelde üretiliyor
(dataset değişmediği sürece tek seferlik).

Kaynaklardan itibaren dataset'i sıfırdan yeniden üretmek istersen
`scripts/download_sources.py` ile başlayan pipeline kullanılabilir
(`scripts/index_documents.py` -> `extract_commands.py` ->
`build_dataset.py` -> `build_index.py`).

## Çalıştırma

`windows_setup.bat`/`linux_setup.sh` kullandıysan masaüstündeki (ya da
uygulama menüsündeki) kısayol yeterli. Elle çalıştırmak istersen:

**Masaüstü penceresi (GUI):**
```
python scripts/gui_app.py
```

**Terminal (CLI):**
```
python scripts/test_model.py
```

(Linux'ta `venv` kullandıysan `venv/bin/python` ile.)

İkisi de proje kök dizininden çalıştırılmalı (dosya yolları göreceli).
İlk çalıştırmada `Qwen2.5-0.5B-Instruct` ve embedding modeli Hugging
Face'ten otomatik indirilir (internet gerekir), sonraki çalıştırmalar
tamamen offline'dır.

## Masaüstü kısayolunu tek başına yeniden oluşturma

`windows_setup.bat`/`linux_setup.sh` bunu zaten yapıyor; sadece
kısayolu yenilemek istersen:

**Windows:**
```
powershell -File scripts\create_shortcut.ps1
```
`pythonw.exe`, PATH'teki `python` ile aynı klasörden otomatik
bulunuyor - elle yol girmen gerekmiyor.

**Linux:**
```
bash scripts/create_shortcut.sh
```
Proje kökünde bir `venv/` varsa onun Python'ı kullanılır, yoksa
PATH'teki `python3`'e düşer.

## Lisans

Bu projenin kendi kodu MIT lisanslı (`LICENSE`). Dataset ve model,
üçüncü parti dokümantasyon kaynaklarından türetildiği için kendi
lisanslarına tabi - bkz. `ATTRIBUTION.md`.
