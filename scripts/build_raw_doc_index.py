"""Ham dokümantasyon (data/processed/documents.json) üzerinde İKİNCİ bir
semantik arama indeksi oluşturur - ana RAG indeksinden (dataset.jsonl
üzerinde, build_index.py) tamamen ayrı. Amaç: yapılandırılmış dataset'in
hiçbir eşleşme bulamadığı sorularda (mentor_core.py'nin generative
fallback'ine düşmeden önce), kaynak dokümanların HAM metninde ilgili bir
paragraf var mı diye bakmak - hiçbir şey uydurmadan, sadece dataset'e hiç
çıkarılmamış ama kaynakta duran bağlam/açıklamaları yakalamak için.

Kayıtlar dataset.jsonl'deki gibi "doğrulanmış soru-cevap" değil, ham
kaynak metninden düz paragraflar - mentor_core.py bunları her zaman
"kaynak dokümandan alıntı, doğrulanmış değil" etiketiyle gösterir.

build_index.py ile aynı artımlı mantık: paragraf metni değişmediği
sürece önceki embedding'i yeniden kullanır.

Kullanım: python scripts/build_raw_doc_index.py
"""

import json
import re
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

DOCUMENTS_PATH = Path("data/processed/documents.json")
INDEX_DIR = Path("data/processed/raw_doc_index")
EMBEDDINGS_PATH = INDEX_DIR / "embeddings.npy"
CHUNKS_PATH = INDEX_DIR / "chunks.json"

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

MIN_CHUNK_LEN = 100
MAX_CHUNK_LEN = 1000

# "The definition of the systemd units can be inspected in the following
# files:" tarzı kısa, tek başına ANLAMSIZ referans cümleleri (asıl içerik
# başka bir paragrafta/listede, bu sadece ona giriş yapıyor) - canlı testte
# bulundu: 76 karakterlik böyle bir cümle, gerçek/faydalı 135+ karakterlik
# parçalardan daha YÜKSEK benzerlik skoru alabiliyor (sorudaki kelimeleri
# birebir tekrarladığı için), embedding skoru tek başına bunu ayıramıyor.
# MIN_CHUNK_LEN'i 60'tan 100'e çıkarmak bu spesifik örneği zaten eliyor
# (135+ olan gerçek örnekler etkilenmiyor); bu regex ek bir güvenlik katmanı
# - ":" ile biten VE kısa olan parçaları da ayrıca eliyor.
REFERENTIAL_TRAILING_COLON = re.compile(r".{0,40}:$")

_BACKTICK = chr(96)


def clean_paragraph(text: str) -> str:
    """Format-bağımsız, hafif bir temizlik - Markdown/HTML/texinfo/troff
    işaretlemesinin çoğunu kaba ama güvenli bir şekilde temizler. Bu bir
    fallback katmanı için, ana dataset kadar özenli/format-özel bir
    parser gerekmiyor - amaç okunabilir bir paragraf elde etmek, mükemmel
    bir extraction değil."""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
    text = re.sub("[*_" + _BACKTICK + "]{1,3}", "", text)

    # texinfo (@node/@section...) ve troff/mdoc (.SH/.TP/.B...) makro
    # satırları - ikisi de satır başında @ ya da . ile başlayan bir
    # harfle ayırt ediliyor.
    lines = [
        line for line in text.split("\n")
        if not re.match(r"^[.@][A-Za-z]", line.strip())
    ]
    text = "\n".join(lines)

    return re.sub(r"\s+", " ", text).strip()


def is_junk(text: str) -> bool:
    """Tablo satırları (çok fazla '|') ve büyük ölçüde alfanümerik
    olmayan (menü/TOC/ayraç yığını) parçaları eliyor."""
    if not text:
        return True

    if text.count("|") > 5:
        return True

    alnum = sum(c.isalnum() for c in text)

    if (alnum / len(text)) < 0.5:
        return True

    return bool(REFERENTIAL_TRAILING_COLON.search(text))


print("Ham dokümanlar yükleniyor...")

with DOCUMENTS_PATH.open("r", encoding="utf-8") as f:
    docs = json.load(f)

print(f"{len(docs)} doküman parçalara bölünüyor...")

chunks = []

for doc in docs:
    for paragraph in re.split(r"\n\s*\n", doc["text"]):
        cleaned = clean_paragraph(paragraph)

        if len(cleaned) < MIN_CHUNK_LEN or is_junk(cleaned):
            continue

        chunks.append({
            "text": cleaned[:MAX_CHUNK_LEN],
            "path": doc["path"],
            "source": doc["source"]
        })

print(f"{len(chunks)} parça oluşturuldu.")

# Önceki indeksten hâlâ geçerli embedding'leri yeniden kullan - aynı
# mantık build_index.py'de zaten var (bkz. o dosyadaki yorum).
vector_by_text = {}

if EMBEDDINGS_PATH.exists() and CHUNKS_PATH.exists():
    try:
        old_embeddings = np.load(EMBEDDINGS_PATH)

        with CHUNKS_PATH.open("r", encoding="utf-8") as f:
            old_chunks = json.load(f)

        if len(old_chunks) == len(old_embeddings):
            for old_chunk, vector in zip(old_chunks, old_embeddings):
                vector_by_text[old_chunk["text"]] = vector
    except (OSError, json.JSONDecodeError, KeyError):
        pass

unique_texts = {c["text"] for c in chunks}
missing_texts = sorted(unique_texts - vector_by_text.keys())

if vector_by_text:
    reused = len(unique_texts) - len(missing_texts)
    print(
        f"{reused} benzersiz parça önceki indeksten yeniden kullanılıyor, "
        f"{len(missing_texts)} yeni/değişmiş parça encode edilecek."
    )

if missing_texts:
    print("Embedding modeli yükleniyor...")
    model = SentenceTransformer(EMBEDDING_MODEL)

    print("Yeni/değişmiş parçalar için embedding'ler hesaplanıyor...")
    new_vectors = model.encode(
        missing_texts,
        batch_size=128,
        show_progress_bar=True,
        normalize_embeddings=True
    )

    for text, vector in zip(missing_texts, new_vectors):
        vector_by_text[text] = vector
else:
    print("Hiçbir parça değişmemiş, embedding hesaplamaya gerek yok.")

embeddings = np.stack(
    [vector_by_text[c["text"]] for c in chunks]
).astype("float32")

INDEX_DIR.mkdir(parents=True, exist_ok=True)

np.save(EMBEDDINGS_PATH, embeddings)

with CHUNKS_PATH.open("w", encoding="utf-8") as f:
    json.dump(chunks, f, ensure_ascii=False)

print(f"\nHam doküman indeksi oluşturuldu: {len(chunks)} parça")
print(f"Embedding'ler: {EMBEDDINGS_PATH}")
print(f"Parçalar: {CHUNKS_PATH}")
