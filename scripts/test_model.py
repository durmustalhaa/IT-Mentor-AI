"""Komut satırından soru-cevap REPL'i. Tüm yükleme/arama/üretim mantığı
mentor_core.py'de - bkz. gui_app.py, aynı mantığı masaüstü penceresinden
çağırıyor."""

import sys

import mentor_core

mentor_core.load()

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
