import json
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

DATASET_PATH = Path("data/processed/dataset.jsonl")
INDEX_DIR = Path("data/processed/rag_index")
EMBEDDINGS_PATH = INDEX_DIR / "embeddings.npy"
RECORDS_PATH = INDEX_DIR / "records.json"

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


print("Dataset yükleniyor...")

records = []

with DATASET_PATH.open("r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()

        if not line:
            continue

        records.append(json.loads(line))

print(f"{len(records)} soru-cevap çifti indekslenecek.")

print("Embedding modeli yükleniyor (ilk çalıştırmada indirilir)...")
model = SentenceTransformer(EMBEDDING_MODEL)

instructions = [r["instruction"] for r in records]

print("Embedding'ler hesaplanıyor...")
embeddings = model.encode(
    instructions,
    batch_size=128,
    show_progress_bar=True,
    normalize_embeddings=True
)

INDEX_DIR.mkdir(parents=True, exist_ok=True)

np.save(EMBEDDINGS_PATH, embeddings.astype("float32"))

with RECORDS_PATH.open("w", encoding="utf-8") as f:
    json.dump(records, f, ensure_ascii=False)

print(f"\nİndeks oluşturuldu: {len(records)} kayıt")
print(f"Embedding'ler: {EMBEDDINGS_PATH}")
print(f"Kayıtlar: {RECORDS_PATH}")
