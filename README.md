# IT Mentor AI

Offline çalışan bir IT-ops asistanı: Git, Linux, Windows, Docker,
systemd, networking ve daha fazlası hakkındaki soruları, gerçek
dokümantasyondan (RAG) veya (veri yoksa) yerel bir dil modelinden
cevaplıyor. İnternet bağlantısı sadece ilk kurulumda model indirmek
için gerekiyor, sonrasında tamamen offline çalışır.

## Kurulum (Windows, hızlı yol)

Python (https://www.python.org/downloads/, "Add python.exe to PATH"
işaretli) kuruluysa, `install.bat`'a çift tıklamak yeterli:
bağımlılıkları kurar, RAG index'ini oluşturur, masaüstüne "IT Mentor
AI" kısayolunu bırakır. Script şeffaf - içinde sadece `pip install`,
`build_index.py` ve `create_shortcut.ps1` çağrıları var, hiçbir şeyi
sessizce kurmuyor; Python bulunamazsa sadece nereden indireceğini
söyleyip çıkıyor.

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

`install.bat` kullandıysan masaüstündeki kısayol yeterli. Elle
çalıştırmak istersen:

**Masaüstü penceresi (GUI):**
```
python scripts/gui_app.py
```

**Terminal (CLI):**
```
python scripts/test_model.py
```

İkisi de proje kök dizininden çalıştırılmalı (dosya yolları göreceli).
İlk çalıştırmada `Qwen2.5-0.5B-Instruct` ve embedding modeli Hugging
Face'ten otomatik indirilir (internet gerekir), sonraki çalıştırmalar
tamamen offline'dır.

## Masaüstü kısayolunu tek başına yeniden oluşturma

`install.bat` bunu zaten yapıyor; sadece kısayolu yenilemek istersen:
```
powershell -File scripts\create_shortcut.ps1
```
`pythonw.exe`, PATH'teki `python` ile aynı klasörden otomatik
bulunuyor - elle yol girmen gerekmiyor.

## Lisans

Bu projenin kendi kodu MIT lisanslı (`LICENSE`). Dataset ve model,
üçüncü parti dokümantasyon kaynaklarından türetildiği için kendi
lisanslarına tabi - bkz. `ATTRIBUTION.md`.
