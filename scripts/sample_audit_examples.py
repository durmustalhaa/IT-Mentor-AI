import json
import random
from collections import defaultdict
from pathlib import Path

INPUT_PATH = Path("data/processed/suspicious_examples.jsonl")
OUTPUT_PATH = Path("data/processed/audit_samples.json")

SAMPLES_PER_REASON = 10
RANDOM_SEED = 42

random.seed(RANDOM_SEED)

examples_by_reason = defaultdict(list)

with INPUT_PATH.open("r", encoding="utf-8") as file:
    for line in file:
        line = line.strip()

        if not line:
            continue

        record = json.loads(line)

        for reason in record.get("reasons", []):
            examples_by_reason[reason].append(record)

sampled_examples = {}

for reason, examples in examples_by_reason.items():
    sample_size = min(SAMPLES_PER_REASON, len(examples))

    sampled_examples[reason] = random.sample(
        examples,
        sample_size
    )

OUTPUT_PATH.write_text(
    json.dumps(
        sampled_examples,
        ensure_ascii=False,
        indent=2
    ),
    encoding="utf-8"
)

print("Örnekleme tamamlandı.")

for reason, examples in sampled_examples.items():
    print(f"{reason}: {len(examples)} örnek")

print("Dosya:", OUTPUT_PATH)