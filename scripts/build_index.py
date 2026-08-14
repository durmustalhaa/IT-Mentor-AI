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

# Önceki indeksten hâlâ geçerli olan embedding'leri yeniden kullan. Bir
# embedding SADECE "instruction" metninin bir fonksiyonu - aynı instruction
# daha önce encode edilmişse (response/category/command alanları değişmiş
# olsa bile) o vektör hâlâ doğru, baştan encode etmeye gerek yok. Böylece
# dataset'e birkaç satır eklemek/düzenlemek gibi küçük bir değişiklikte
# ~175K kaydın hepsini değil, sadece GERÇEKTEN yeni/değişmiş instruction'ları
# yeniden hesaplıyoruz - GPU'suz bir makinede bu, tam yeniden derlemenin
# onlarca dakikasını saniyelere indiriyor.
vector_by_instruction = {}

if EMBEDDINGS_PATH.exists() and RECORDS_PATH.exists():
    try:
        old_embeddings = np.load(EMBEDDINGS_PATH)

        with RECORDS_PATH.open("r", encoding="utf-8") as f:
            old_records = json.load(f)

        if len(old_records) == len(old_embeddings):
            for old_record, vector in zip(old_records, old_embeddings):
                vector_by_instruction[old_record["instruction"]] = vector
    except (OSError, json.JSONDecodeError, KeyError):
        pass  # Bozuk/eksik eski indeks - sıfırdan encode edilecek.

unique_instructions = {r["instruction"] for r in records}
missing_instructions = sorted(unique_instructions - vector_by_instruction.keys())

if vector_by_instruction:
    reused = len(unique_instructions) - len(missing_instructions)
    print(
        f"{reused} benzersiz instruction önceki indeksten yeniden "
        f"kullanılıyor, {len(missing_instructions)} yeni/değişmiş "
        f"instruction encode edilecek."
    )

if missing_instructions:
    print("Embedding modeli yükleniyor (ilk çalıştırmada indirilir)...")
    model = SentenceTransformer(EMBEDDING_MODEL)

    print("Yeni/değişmiş kayıtlar için embedding'ler hesaplanıyor...")
    new_vectors = model.encode(
        missing_instructions,
        batch_size=128,
        show_progress_bar=True,
        normalize_embeddings=True
    )

    for instruction, vector in zip(missing_instructions, new_vectors):
        vector_by_instruction[instruction] = vector
else:
    print("Hiçbir instruction değişmemiş, embedding hesaplamaya gerek yok.")

embeddings = np.stack(
    [vector_by_instruction[r["instruction"]] for r in records]
).astype("float32")

INDEX_DIR.mkdir(parents=True, exist_ok=True)

np.save(EMBEDDINGS_PATH, embeddings)

with RECORDS_PATH.open("w", encoding="utf-8") as f:
    json.dump(records, f, ensure_ascii=False)

print(f"\nİndeks oluşturuldu: {len(records)} kayıt")
print(f"Embedding'ler: {EMBEDDINGS_PATH}")
print(f"Kayıtlar: {RECORDS_PATH}")
