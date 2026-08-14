import html
import json
import re
from pathlib import Path
from typing import Any

INPUT = Path("data/processed/commands.json")
OUTPUT = Path("data/processed/dataset.jsonl")
REPORT = Path("data/processed/dataset_report.json")

MAX_DESCRIPTION_CHARS = 700
MAX_EXAMPLE_CHARS = 1200
MAX_PARAMETER_CHARS = 500
MAX_SYNTAX_CHARS = 800

dataset: list[dict[str, str]] = []
seen_pairs: set[tuple[str, str]] = set()


def normalize_spaces(text: str) -> str:
    """Fazla boşlukları temizler, kod bloklarının satırlarını korur."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    lines = []
    inside_code = False

    for line in text.splitlines():
        stripped = line.rstrip()

        if stripped.strip().startswith("```"):
            inside_code = not inside_code
            lines.append(stripped)
            continue

        if inside_code:
            lines.append(stripped)
        else:
            lines.append(re.sub(r"[ \t]+", " ", stripped).strip())

    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def remove_documentation_noise(text: str) -> str:
    """Microsoft Learn ve Markdown doküman kalıntılarını temizler."""
    if not text:
        return ""

    text = html.unescape(str(text))

    # HTML yorumları
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)

    # Markdown resim söz dizimi: ![alt metin](adres) -> tamamen kaldırılıyor
    # (bir ekran görüntüsünün alt metni düz metin cevapta anlamlı değil).
    # ÖNCE burada yapılmalı - aksi halde bir sonraki link dönüşümü sadece
    # "[alt metin](adres)" kısmını "alt metin"e çeviriyor, baştaki "!"
    # işaretini olduğu gibi bırakıyordu (ör. "!Screenshot of diskpart...").
    text = re.sub(r"!\[[^\]]*]\([^)]+\)", "", text)

    # Markdown linkleri: [metin](adres) -> metin
    text = re.sub(r"\[([^\]]+)]\([^)]+\)", r"\1", text)

    # AsciiDoc linkgit makrosu: linkgit:git-status[1] -> git-status
    text = re.sub(r"linkgit:([\w.-]+)\[\d+\]", r"\1", text)

    # AsciiDoc [verse] blok işareti (syntax bloklarının başında görünür)
    text = re.sub(r"^\[verse]\s*\n", "", text, flags=re.MULTILINE)

    # AsciiDoc blok-çapası: "[[id]]", genelde hemen ardından gelen bir
    # başlığa çapraz-referans hedefi olarak duruyor - gerçek metin değil
    # (ör. git-notes.adoc'ta "[[CONFIGURATION]]" bir örnek cevabının içine
    # sızıyordu). Satır başı/sonu şart koşulmuyor - bu noktaya gelen metin
    # genelde çoktan tek satıra düzleştirilmiş oluyor (orijinal satır
    # sonları boşluğa çevrilmiş), bu yüzden "[[id]]" metnin ortasında da
    # görünebiliyor.
    text = re.sub(r"\[\[[\w-]+]]", "", text)

    # tldr'ın mnemonic işaretleyicisi: "[l]istener" -> "listener"
    text = re.sub(r"\[([A-Za-z])](\w*)", r"\1\2", text)

    # Referans tipi link tanımları: [01]: example.md
    text = re.sub(
        r"^\s*\[[^\]]+]:\s*\S+.*$",
        "",
        text,
        flags=re.MULTILINE
    )

    # Microsoft Learn uyarı işaretleri
    text = re.sub(
        r"^\s*>\s*\[!(NOTE|IMPORTANT|WARNING|TIP|CAUTION)]\s*>?\s*",
        "",
        text,
        flags=re.MULTILINE | re.IGNORECASE
    )

    # Kalan blockquote işaretleri
    text = re.sub(r"^\s*>\s?", "", text, flags=re.MULTILINE)

    # AsciiDoc liste devam işareti: tek başına bir satırda duran '+'
    text = re.sub(r"\n\+\n", "\n", text)

    # For more information ile başlayan cümleler
    text = re.sub(
        r"For more information[^.!?\n]*(?:[.!?]|$)",
        "",
        text,
        flags=re.IGNORECASE
    )

    # See also bölümü ve sonrasını kaldır
    text = re.split(
        r"\n#{1,6}\s+(?:See also|Related links|Related content)\b",
        text,
        maxsplit=1,
        flags=re.IGNORECASE
    )[0]

    # CommonParameters bölümü ve sonrasını kaldır
    text = re.split(
        r"\n#{1,6}\s+CommonParameters\b",
        text,
        maxsplit=1,
        flags=re.IGNORECASE
    )[0]

    # Satır içinde kalmış CommonParameters açıklaması - SADECE satırın
    # kendisi (baştaki boşluk/# dışında) gerçekten "CommonParameters"
    # başlığıysa siliniyor. Önceki hali `(?:###\s*)?` opsiyonel olduğu
    # için satırın HERHANGİ bir yerinde geçen "CommonParameters"
    # kelimesini de eşleştiriyordu - bu da PowerShell syntax
    # bloklarındaki zararsız "[<CommonParameters>]" söz dizimi
    # yer tutucusunu (gerçek bir başlık değil) yakalayıp ondan sonraki
    # HER ŞEYİ (kapanış ``` dahil, sonraki tüm parametre setlerini)
    # sessizce siliyordu - "### Name (Default)" gibi yalnızca bir alt
    # başlıktan ibaret, kod bloğu tamamen kayıp "syntax" cevapları
    # üretiyordu (PowerShell kaynaklı 3.149 kayıttan 1.377'si etkilenmiş).
    text = re.sub(
        r"(?m)^\s*(?:#{1,6}\s*)?CommonParameters\s*$.*",
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL
    )

    # about_X.md gibi ham doküman yolları
    text = re.sub(
        r"(?:\.\.?/)*[\w./-]*about_[\w-]+\.md(?:#[\w-]+)?",
        "",
        text,
        flags=re.IGNORECASE
    )

    return normalize_spaces(text)


def truncate_at_sentence(text: str, max_chars: int) -> str:
    """Metni mümkünse cümle sınırından kısaltır."""
    text = text.strip()

    if len(text) <= max_chars:
        return text

    shortened = text[:max_chars]

    sentence_endings = [
        shortened.rfind(". "),
        shortened.rfind("! "),
        shortened.rfind("? "),
        shortened.rfind("\n\n")
    ]

    cut_position = max(sentence_endings)

    if cut_position >= int(max_chars * 0.5):
        shortened = shortened[:cut_position + 1]
    else:
        # Cümle sonu bulunamadıysa en azından kelime ortasında kesme.
        word_boundary = shortened.rfind(" ")

        if word_boundary >= int(max_chars * 0.5):
            shortened = shortened[:word_boundary]

    return shortened.rstrip(" ,;:-")


def first_sentences(text: str, count: int = 3) -> str:
    """İlk birkaç açıklama cümlesini alır."""
    text = remove_documentation_noise(text)

    if not text:
        return ""

    # Başlıkları kaldır
    text = re.sub(
        r"^\s*#{1,6}\s+.*$",
        "",
        text,
        flags=re.MULTILINE
    )

    text = normalize_spaces(text)

    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9`])", text)

    selected = []

    for sentence in sentences:
        sentence = sentence.strip()

        if not sentence:
            continue

        selected.append(sentence)

        if len(selected) >= count:
            break

    return " ".join(selected).strip()


def clean_description(synopsis: Any, description: Any) -> str:
    """
    Öncelikle kısa synopsis kullanılır.
    Synopsis yetersizse description'ın ilk cümleleri kullanılır.
    """
    synopsis_text = first_sentences(str(synopsis or ""), count=2)

    if len(synopsis_text) >= 25:
        return truncate_at_sentence(
            synopsis_text,
            MAX_DESCRIPTION_CHARS
        )

    description_text = first_sentences(
        str(description or ""),
        count=3
    )

    return truncate_at_sentence(
        description_text,
        MAX_DESCRIPTION_CHARS
    )


def extract_first_code_block(text: str) -> str:
    """İlk fenced code block'u bulur."""
    matches = re.findall(
        r"```(?:powershell|console|shell|bash|cmd|text|output)?\s*\n?"
        r"(.*?)```",
        text,
        flags=re.DOTALL | re.IGNORECASE
    )

    if not matches:
        return ""

    code = matches[0].strip()

    # Sadece output olan blokları syntax/örnek olarak alma
    if not code:
        return ""

    return code


def clean_syntax(syntax: Any) -> str:
    text = remove_documentation_noise(str(syntax or ""))

    if not text:
        return ""

    code = extract_first_code_block(text)

    if code:
        result = f"```text\n{code}\n```"
    else:
        # Syntax alanında kod bloğu yoksa ilk paragrafı kullan
        result = text.split("\n\n", 1)[0].strip()

    return result[:MAX_SYNTAX_CHARS].strip()


def remove_output_blocks(text: str) -> str:
    """Örnek cevabındaki uzun terminal çıktılarını kaldırır."""
    return re.sub(
        r"```(?:output|text)\s*\n.*?```",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE
    )


def extract_first_example_section(text: str) -> str:
    """Example 1 bölümünü alır, Example 2 başladığında keser."""
    match = re.search(
        r"(?:^|\n)#{1,6}\s+Example\s+1\b.*?"
        r"(?=(?:\n#{1,6}\s+Example\s+2\b)|\Z)",
        text,
        flags=re.DOTALL | re.IGNORECASE
    )

    if match:
        return match.group(0).strip()

    return text


def clean_example(examples: Any) -> str:
    text = str(examples or "")

    if not text.strip():
        return ""

    text = remove_output_blocks(text)
    text = extract_first_example_section(text)
    text = remove_documentation_noise(text)

    # "Example 1" başlığını sadeleştir
    text = re.sub(
        r"^\s*#{1,6}\s+Example\s+\d+\s*[:\-–—]?\s*",
        "",
        text,
        count=1,
        flags=re.IGNORECASE
    )

    # Boş veya kod içermeyen çok uzun örnekleri engelle
    text = truncate_at_sentence(text, MAX_EXAMPLE_CHARS)

    return text.strip()


def clean_parameter_description(description: Any) -> str:
    text = first_sentences(str(description or ""), count=3)

    return truncate_at_sentence(
        text,
        MAX_PARAMETER_CHARS
    )


def clean_intent_phrase(phrase: Any) -> str:
    text = remove_documentation_noise(str(phrase or ""))
    text = normalize_spaces(text)
    return text.rstrip(" .!")


def lowered_first(text: str) -> str:
    if not text:
        return text

    return text[0].lower() + text[1:]


def bare_flag(parameter_name: str) -> str:
    """'-i' -> 'i', '--ignore-case' -> 'ignore-case'. Karmaşık olanlarda ('--porcelain[=<v>]') boş döner."""
    stripped = parameter_name.lstrip("-")

    if re.match(r"^[A-Za-z0-9-]+$", stripped):
        return stripped

    return ""


# Grep gibi komutlarda 80+ gerçek flag olabiliyor (GNU kılavuzları uzun
# cümlelerle açıklıyor); tam açıklamayı kullanırsak eski 1200 karakterlik
# sınır ilk birkaç flag'ten sonra listeyi sessizce kesiyordu. Bunun yerine
# her flag için KISA bir özet kullanılıyor, üst sınır da en büyük gerçek
# komutu (86 flag) rahatça karşılayacak şekilde yükseltildi - hiçbir flag
# sessizce atlanmasın diye.
MAX_OVERVIEW_CHARS = 15000
MAX_OVERVIEW_ENTRY_CHARS = 110


def summarize_for_overview(description: str) -> str:
    """Genel listede her flag için tek, kısa bir cümle - tam açıklama
    ayrı parametre sorusunda zaten mevcut."""
    sentence = first_sentences(description, count=1)
    return truncate_at_sentence(sentence, MAX_OVERVIEW_ENTRY_CHARS)


def build_overview(parameters: list) -> str:
    """Tüm parametreleri tek bir listede toplar; aynı açıklamayı paylaşan
    takma adlar ('-s'/'--short') tek satırda birleştirilir."""
    grouped: dict[str, list[str]] = {}
    order: list[str] = []

    for parameter in parameters:
        if not isinstance(parameter, dict):
            continue

        parameter_name = str(parameter.get("name", "")).strip()
        parameter_description = summarize_for_overview(
            str(parameter.get("description") or "")
        )

        if not parameter_name or not parameter_description:
            continue

        if parameter_description not in grouped:
            grouped[parameter_description] = []
            order.append(parameter_description)

        if parameter_name not in grouped[parameter_description]:
            grouped[parameter_description].append(parameter_name)

    lines = []
    total = 0

    for description in order:
        flags = ", ".join(grouped[description])
        line = f"- {flags}: {description}"

        if lines and total + len(line) + 1 > MAX_OVERVIEW_CHARS:
            break

        lines.append(line)
        total += len(line) + 1

    return "\n".join(lines)


def normalize_for_deduplication(text: str) -> str:
    # casefold() KULLANILMIYOR: "rm -r" ve "rm -R" gibi büyük/küçük harfle
    # ayrılan, gerçekten farklı sorular aynı cevabı paylaşınca (çoğu zaman
    # eş anlamlı flag'ler için olur) casefold ikisini "aynı soru" sanıp
    # -R'nin sorusunu sessizce siliyordu - bir sorun değil, veri kaybıydı.
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def add(question: str, answer: str, category: str, command: str = "") -> None:
    question = normalize_spaces(str(question))
    answer = normalize_spaces(str(answer))

    if not question or not answer:
        return

    if len(answer) < 15:
        return

    if len(question) > 300:
        return

    pair_key = (
        normalize_for_deduplication(question),
        normalize_for_deduplication(answer)
    )

    if pair_key in seen_pairs:
        return

    seen_pairs.add(pair_key)

    dataset.append({
        "instruction": question,
        "response": answer,
        "category": category,
        # Hangi komuta ait olduğunu işaretliyor - RAG'de "-w flag'i printf'te
        # ne yapar" gibi sorularda, printf'in kendi -w'si olmasa bile başka
        # bir komutun -w'sü (ör. od) yanlışlıkla "kesin eşleşme" sayılmasın
        # diye. Sadece etiketleme amaçlı, embedding hesaplamasına girmiyor.
        "command": command
    })


with INPUT.open("r", encoding="utf-8") as file:
    commands = json.load(file)


for command_record in commands:
    name = str(command_record.get("command", "")).strip()

    if not name:
        continue

    description = clean_description(
        command_record.get("synopsis"),
        command_record.get("description")
    )

    syntax = clean_syntax(
        command_record.get("syntax")
    )

    example = clean_example(
        command_record.get("examples")
    )

    parameters = command_record.get("parameters") or []

    # Açıklama soruları
    if description:
        add(
            f"What does {name} do?",
            description,
            "description",
            name
        )

        add(
            f"{name} ne işe yarar?",
            description,
            "description",
            name
        )

    # Syntax soruları
    if syntax:
        add(
            f"What is the syntax of {name}?",
            syntax,
            "syntax",
            name
        )

        add(
            f"{name} syntax nedir?",
            syntax,
            "syntax",
            name
        )

    # Kullanım örnekleri
    if example:
        add(
            f"Can you give me an example of how to use {name}?",
            example,
            "example",
            name
        )

        add(
            f"{name} için bir kullanım örneği verir misin?",
            example,
            "example",
            name
        )

    # Parametre soruları
    # "--list" gibi bir bayrağın kısa/tiresiz sorusu ("What does dnf list
    # do?") bare_flag() ile üretiliyor - ama bazı kaynaklarda (dnf'in
    # repoquery gibi alt komutlarına ait bayrakları OPTIONS taramasında
    # üst düzey "dnf" komutuna bağlanıyor) bu kısa hal, AYNI komutun kendi
    # gerçek "list" alt komutuyla birebir çakışıyor - iki farklı, çelişen
    # cevaplı "What does dnf list do?" satırı üretiliyordu. Aynı komutun
    # gerçek parametre isimleriyle (tiresiz haliyle) çakışan kısa-form
    # soruları baştan atlanıyor; asıl, tam isimli soru zaten üretiliyor.
    existing_parameter_names_lower = {
        str(p.get("name", "")).strip().lower()
        for p in parameters
        if isinstance(p, dict) and p.get("name")
    }

    for parameter in parameters:
        if not isinstance(parameter, dict):
            continue

        parameter_name = str(
            parameter.get("name", "")
        ).strip()

        parameter_description = clean_parameter_description(
            parameter.get("description")
        )

        if not parameter_name or not parameter_description:
            continue

        add(
            f"What does the {parameter_name} parameter of {name} do?",
            parameter_description,
            "parameter",
            name
        )

        add(
            f"{name} komutundaki {parameter_name} parametresi ne işe yarar?",
            parameter_description,
            "parameter",
            name
        )

        add(
            f"What does {name} {parameter_name} do?",
            parameter_description,
            "parameter",
            name
        )

        add(
            f"What is the {parameter_name} flag for in {name}?",
            parameter_description,
            "parameter",
            name
        )

        # Tire/parametre kelimesi olmadan gündelik ifade: "grep i ne yapar"
        short_flag = bare_flag(parameter_name)

        if short_flag and short_flag.lower() in existing_parameter_names_lower:
            short_flag = ""

        if short_flag:
            add(
                f"What does {name} {short_flag} do?",
                parameter_description,
                "parameter",
                name
            )

            add(
                f"{name} {short_flag} ne yapar?",
                parameter_description,
                "parameter",
                name
            )

    # Tüm parametreleri tek seferde listeleyen genel bakış sorusu
    overview = build_overview(parameters)

    if overview and len(parameters) >= 2:
        add(
            f"Can you list {name} commands and what they do?",
            overview,
            "overview",
            name
        )

        add(
            f"What are all the options for {name}?",
            overview,
            "overview",
            name
        )

        add(
            f"Can you list all {name} flags?",
            overview,
            "overview",
            name
        )

        add(
            f"{name} komutunun tüm parametrelerini listeler misin?",
            overview,
            "overview",
            name
        )

    # Niyet soruları: "şunu yapmak istiyorum" -> "şu komutu kullanabilirsin"
    for intent in command_record.get("intents") or []:
        if not isinstance(intent, dict):
            continue

        phrase = clean_intent_phrase(intent.get("phrase"))

        if len(phrase) < 10:
            continue

        command_hint = str(intent.get("command_hint", "")).strip()
        answer_command = command_hint if command_hint else name

        response = f"You can use:\n```bash\n{answer_command}\n```"

        lowered_phrase = lowered_first(phrase)

        if intent.get("mood") == "declarative":
            add(
                f"I need a command that {lowered_phrase}.",
                response,
                "intent",
                name
            )
        else:
            add(
                f"How do I {lowered_phrase}?",
                response,
                "intent",
                name
            )

            add(
                f"I want to {lowered_phrase}.",
                response,
                "intent",
                name
            )


OUTPUT.parent.mkdir(parents=True, exist_ok=True)

with OUTPUT.open("w", encoding="utf-8") as file:
    for row in dataset:
        file.write(
            json.dumps(row, ensure_ascii=False) + "\n"
        )


category_counts: dict[str, int] = {}

for row in dataset:
    category = row["category"]
    category_counts[category] = category_counts.get(category, 0) + 1


report = {
    "input_command_records": len(commands),
    "output_training_examples": len(dataset),
    "removed_duplicate_pairs": (
        # Bu değer, add çağrılarının toplamı tutulmadığı için
        # yalnızca benzersiz çift sayısını temsil eder.
        "Exact duplicate pairs were automatically removed."
    ),
    "category_counts": category_counts,
    "limits": {
        "description_characters": MAX_DESCRIPTION_CHARS,
        "example_characters": MAX_EXAMPLE_CHARS,
        "parameter_characters": MAX_PARAMETER_CHARS,
        "syntax_characters": MAX_SYNTAX_CHARS,
        "overview_characters": MAX_OVERVIEW_CHARS
    }
}

REPORT.write_text(
    json.dumps(report, ensure_ascii=False, indent=2),
    encoding="utf-8"
)

print("\nDataset V2 oluşturuldu.")
print(f"Girdi komut kaydı: {len(commands)}")
print(f"Eğitim örneği: {len(dataset)}")
print(f"Çıktı: {OUTPUT}")
print(f"Rapor: {REPORT}")

print("\nKategori dağılımı:")

for category, count in category_counts.items():
    print(f"  {category}: {count}")