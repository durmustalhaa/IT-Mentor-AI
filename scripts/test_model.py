"""Komut satırından soru-cevap REPL'i. Tüm yükleme/arama/üretim mantığı
mentor_core.py'de - bkz. gui_app.py, aynı mantığı masaüstü penceresinden
çağırıyor."""

import sys

import mentor_core

mentor_core.load()

if mentor_core.index_is_stale:
    print(
        "⚠ The search index doesn't match the current dataset.jsonl "
        "(it changed since the index was last built). Answers may be "
        "missing recent updates - run 'python scripts/build_index.py' "
        "to refresh it.\n"
    )

print("Type 'exit' to quit.\n")

while True:
    question = input("You: ").strip()

    if question.lower() == "exit":
        break

    if not question:
        continue

    display_answer = mentor_core.answer_question(question)

    safe_answer = display_answer.encode(
        sys.stdout.encoding or "utf-8", errors="replace"
    ).decode(sys.stdout.encoding or "utf-8")

    print(f"\nModel: {safe_answer}\n")
