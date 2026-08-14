import json
import re
from collections import Counter
from pathlib import Path
from statistics import mean, median

DATASET_PATH = Path("data/processed/dataset.jsonl")
REPORT_PATH = Path("data/processed/dataset_audit.json")
SUSPICIOUS_PATH = Path("data/processed/suspicious_examples.jsonl")

LONG_RESPONSE_LIMIT = 1500

link_pattern = re.compile(
    r"https?://|www\.|\]\(\.\.?/|Microsoft\.PowerShell|about_[A-Za-z_]+",
    re.IGNORECASE
)

syntax_pattern = re.compile(
    r"^\s*(```)?\s*[A-Za-z0-9_-]+\s+\[",
    re.IGNORECASE
)

records = []
invalid_lines = []

with DATASET_PATH.open("r", encoding="utf-8") as file:
    for line_number, line in enumerate(file, start=1):
        line = line.strip()

        if not line:
            continue

        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            invalid_lines.append(line_number)
            continue

        instruction = str(record.get("instruction", "")).strip()
        response = str(record.get("response", "")).strip()

        records.append({
            "line": line_number,
            "instruction": instruction,
            "response": response
        })

instruction_counts = Counter(
    record["instruction"].lower()
    for record in records
    if record["instruction"]
)

response_counts = Counter(
    record["response"].lower()
    for record in records
    if record["response"]
)

pair_counts = Counter(
    (
        record["instruction"].lower(),
        record["response"].lower()
    )
    for record in records
    if record["instruction"] and record["response"]
)

response_lengths = [
    len(record["response"])
    for record in records
    if record["response"]
]

empty_instruction_count = 0
empty_response_count = 0
long_response_count = 0
link_count = 0
syntax_only_count = 0
suspicious_examples = []

for record in records:
    instruction = record["instruction"]
    response = record["response"]

    reasons = []

    if not instruction:
        empty_instruction_count += 1
        reasons.append("empty_instruction")

    if not response:
        empty_response_count += 1
        reasons.append("empty_response")

    if len(response) > LONG_RESPONSE_LIMIT:
        long_response_count += 1
        reasons.append("long_response")

    if link_pattern.search(response):
        link_count += 1
        reasons.append("documentation_link")

    response_without_code_fence = response.replace("```", "").strip()

    if (
        len(response_without_code_fence.splitlines()) <= 3
        and syntax_pattern.search(response_without_code_fence)
    ):
        syntax_only_count += 1
        reasons.append("syntax_only")

    if reasons:
        suspicious_examples.append({
            "line": record["line"],
            "instruction": instruction,
            "response": response,
            "reasons": reasons
        })

report = {
    "dataset_path": str(DATASET_PATH),
    "total_records": len(records),
    "invalid_json_lines": len(invalid_lines),
    "invalid_line_numbers": invalid_lines[:100],

    "empty_instructions": empty_instruction_count,
    "empty_responses": empty_response_count,

    "duplicate_instructions": sum(
        count - 1
        for count in instruction_counts.values()
        if count > 1
    ),
    "duplicate_responses": sum(
        count - 1
        for count in response_counts.values()
        if count > 1
    ),
    "duplicate_pairs": sum(
        count - 1
        for count in pair_counts.values()
        if count > 1
    ),

    "responses_with_documentation_links": link_count,
    "syntax_only_responses": syntax_only_count,
    "responses_over_1500_characters": long_response_count,

    "average_response_characters": (
        round(mean(response_lengths), 2)
        if response_lengths else 0
    ),
    "median_response_characters": (
        median(response_lengths)
        if response_lengths else 0
    ),
    "maximum_response_characters": (
        max(response_lengths)
        if response_lengths else 0
    ),

    "suspicious_example_count": len(suspicious_examples)
}

REPORT_PATH.write_text(
    json.dumps(report, ensure_ascii=False, indent=2),
    encoding="utf-8"
)

with SUSPICIOUS_PATH.open("w", encoding="utf-8") as file:
    for example in suspicious_examples:
        file.write(
            json.dumps(example, ensure_ascii=False) + "\n"
        )

print("\nDataset denetimi tamamlandı.\n")

for key, value in report.items():
    if key != "invalid_line_numbers":
        print(f"{key}: {value}")

print("\nRapor:", REPORT_PATH)
print("Şüpheli kayıtlar:", SUSPICIOUS_PATH)