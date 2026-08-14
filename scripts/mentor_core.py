"""IT Mentor AI'nin RAG cevaplama mantığının paylaşılan çekirdeği.

Bu modül, önceden test_model.py'nin İÇİNDE (bir REPL script'i olarak)
yaşayan tüm yükleme/arama/üretim mantığını içeriyor - hem komut satırı
(test_model.py) hem de masaüstü arayüzü (gui_app.py) aynı, tek bir
doğrulanmış mantığı çağırıyor; mantık iki yerde ayrı ayrı bakım
gerektirmesin diye kopyalanmadı.

LoRA adaptörü (qwen-it-mentor-v6) BİLEREK kullanılmıyor - bkz.
03_LoRA_Training.md "LoRA Emekliye Ayrıldı". RAG artık gerçekçi
soruların ~%90'ını doğrudan, doğrulanmış veriden yanıtlıyor; kalan
kısımda da adaptör IT komut-referansı formatına o kadar dar
uyarlanmıştı ki sıradan bir "merhaba"ya bile sahte bir komut
uydurabiliyordu - temel Qwen2.5-0.5B-Instruct modeli tek başına daha
güvenli. Model dosyası hâlâ `models/qwen-it-mentor-v6` altında duruyor
(silinmedi), ama hiçbir kod yolu onu yüklemiyor."""

import json
import re
from pathlib import Path
from typing import Callable

import numpy as np
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from sentence_transformers import SentenceTransformer

MODEL_NAME = "Qwen/Qwen2.5-0.5B-Instruct"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# GPU'suz makinelerde (ör. GPU'suz bir Linux VM) sabit ".to(\"cuda\")"
# çağrısı direkt hataya düşüyordu - cihazı çalışma zamanında tespit
# ediyoruz. float16 çoğu CPU çekirdeğinde desteklenmiyor
# ("addmm_impl_cpu_" not implemented for 'Half' gibi hatalar veriyor),
# bu yüzden CPU'da float32'ye düşüyoruz; CUDA varsa float16 aynen
# kalıyor (VRAM tasarrufu için).
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
MODEL_DTYPE = torch.float16 if DEVICE == "cuda" else torch.float32

INDEX_DIR = Path("data/processed/rag_index")
EMBEDDINGS_PATH = INDEX_DIR / "embeddings.npy"
RECORDS_PATH = INDEX_DIR / "records.json"
COMMANDS_PATH = Path("data/processed/commands.json")

# Skor eşikleri (build_index.py ile aynı embedding modeliyle ölçüldü):
# gerçek eşleşmeler 0.70+, ilgisiz/veri-dışı sorular 0.50 altı çıkıyor.
HIGH_CONFIDENCE = 0.70
LOW_CONFIDENCE = 0.55

# Daraltılmış aramada (sadece flag ya da sadece kısayol kayıtları) gürültü
# zaten elendiği için, aynı mutlak skor daha güvenilir bir eşleşme anlamına
# gelir - eşikler bu yüzden global aramadan daha düşük.
RESTRICTED_HIGH_CONFIDENCE = 0.60
RESTRICTED_LOW_CONFIDENCE = 0.40

# Bu değişkenler load() çağrılana kadar None kalır - hem CLI hem GUI
# kendi başlangıcında load()'u bir kere çağırıp "yüklendi" durumuna geçirir.
embeddings = None
records = None
embedder = None
tokenizer = None
model = None

FLAG_PATTERN = re.compile(r"(?:^|\s)-{1,2}[A-Za-z][\w-]*\b")
FLAG_KEYWORDS = re.compile(r"\b(flag|parameter|parametre|option)\b", re.IGNORECASE)

SHORTCUT_KEYWORDS = re.compile(
    r"\b(shortcut|keybind|hotkey|key combo|keyboard|kısayol|tuş"
    r"|PrtScn|Print Screen)\b",
    re.IGNORECASE
)
SHORTCUT_COMBO_PATTERN = re.compile(
    r"\b(Windows\s+key|Windows\s+logo\s+key|Ctrl|Alt|Shift|Win)\s*\+", re.IGNORECASE
)
SHORTCUT_COMBO_EXTRACT = re.compile(
    r"((?:windows\s+logo\s+key|windows\s+key|win|ctrl|alt|shift)"
    r"(?:\s*\+\s*(?:windows\s+logo\s+key|windows\s+key|win|ctrl|alt|shift))*"
    r"\s*\+\s*[A-Za-z0-9]+(?:\s+arrow)?)",
    re.IGNORECASE
)

BARE_FLAG_TEMPLATE_PATTERNS = (
    re.compile(r"^what does (\S+) ([A-Za-z][\w-]*) do\??$", re.IGNORECASE),
    re.compile(r"^(\S+) ([A-Za-z][\w-]*) ne yapar\??$", re.IGNORECASE),
)

# "list"/"add"/"tab" gibi kelimeler Windows'ta gerçek, dokümante edilmiş
# komut adları ama aynı zamanda çok sıradan İngilizce kelimeler - "service"
# de aynı sınıfa girdi (SysV komutu + "a portable service image" gibi
# öbeklerin parçası). "rename"/"copy" da aynı: gerçek Windows komutları,
# ama "how do I..." kalıbıyla BAŞLAMAYAN ("windows rename file" gibi
# anahtar-kelime tarzı) sorularda INTENT_PHRASE_PATTERN devreye girmiyor -
# bu iki kelime tek başına eşleştiğinde de artık komuta hiç daraltılmıyor,
# tıpkı "how do I..." kalıbındaki hallerinde olduğu gibi. Böylece "how can
# i rename a file", "how can i rename a file windows" VE "windows rename
# file" HEPSİ aynı, tutarlı cevaba (global aramadaki en iyi eşleşmeye)
# gidiyor - kullanıcı soruyu nasıl yazarsa yazsın aynı sonucu almalı.
# Ayrıntılı gerekçe için bkz. find_mentioned_command.
GENERIC_WORD_COMMAND_NAMES = {"list", "add", "tab", "service", "rename", "copy"}

# "how can i copy a file over ssh?" gibi DOĞAL, niyet-biçimli sorular hiç
# "copy" komutunu SORMUYOR - asıl cevap başka bir komutun (scp) intent
# kaydında duruyor. Ama "copy" de Windows'ta gerçek, dokümante edilmiş bir
# komut adı (tıpkı "rename"/"service"/"list" gibi) - bu tür sorularda
# find_mentioned_command "copy"yu (ya da "rename"i, "how can i rename a
# selected item?" sorusunda olduğu gibi) yakalayıp TÜM aramayı o komutun
# dar, "intent" kategorisi HARİÇ tutulan havuzuna daraltıyordu - doğru
# cevap (scp'nin ya da F2'nin kendi intent kaydı) o havuzun dışında olduğu
# için hiç aranmadan eleniyordu. GENERIC_WORD_COMMAND_NAMES'e "copy"/
# "rename"/vs. tek tek eklemek yerine (bu liste sonsuza kadar büyürdü -
# "move", "find", "sort", "print", "more", "format"... Windows'ta neredeyse
# her sıradan fiil aynı zamanda gerçek bir komut), daha genel bir kural:
# soru açıkça "how do/can I..."/"I want to..." gibi DOĞAL bir niyet
# kalıbıyla başlıyorsa, komuta daraltma HİÇ uygulanmıyor - sınırsız global
# arama zaten bu tür sorular için ÖZEL OLARAK üretilmiş intent kayıtlarını
# yüksek skorla (0.75-0.98 arası, doğrulandı) buluyor.
INTENT_PHRASE_PATTERN = re.compile(
    r"^(how (do|can) i\b|how to\b|i want to\b|i need\b|what'?s the best way to\b)",
    re.IGNORECASE
)

# "what is a docker image?" gibi KAVRAM sorularının içinde geçen kelime
# ("image") bazen aynı zamanda gerçek bir komut/komut grubu adı oluyor
# ("docker image" alt komut grubu) - komuta daraltma uygulanınca tek
# eşleşme o komut grubunun "Manage images..." özet kaydı oluyor ve bu
# YÜKSEK güvenle (uyarısız) dönüyor, oysa soru kavramı soruyor, komutu
# değil. Veri setinde HİÇ "what is a/an ..." kalıplı soru yok (kontrol
# edildi) - yani bu kalıba uyan gerçek bir kullanıcı sorusu asla
# şablonlanmış bir komut sorusu olamaz, güvenle daraltmayı atlayabiliriz.
# Kapsamlı bir kavram/glossary veri kaynağı eklemek ayrı, daha büyük bir
# iş (bkz. 07_RAG.md) - bu sadece "confidently wrong" olmayı "dürüst
# düşük-güven" ile değiştiriyor.
CONCEPT_QUESTION_PATTERN = re.compile(r"^what is an? \b", re.IGNORECASE)

# "selam"/"merhaba" gibi sıradan sohbet mesajları da RAG'da hiç eşleşme
# bulamadığı için düşük-güven fallback'e düşüyor, tıpkı gerçekten eğitim
# verisinde olmayan bir IT sorusu gibi (örn. "wobblesort nedir"). İkisi de
# aynı yoldan geçse de anlamları farklı: IT sorusunda "doğrulamadan
# güvenme" uyarısı kullanıcıyı modelin uydurmuş olabileceği konusunda
# bilgilendirdiği için gerekli (bkz. 07_RAG.md "confidently wrong" vs
# "honestly labeled guess"), ama sıradan bir selamlaşmada aynı uyarı hem
# anlamsız hem rahatsız edici - burada "eğitim verisi" diye bir kavram
# zaten yok. Bu yüzden sadece sohbet mesajlarında uyarı bastırılıyor.
#
# İki bilinen eksik canlı testte bulundu (bkz. 05_Roadmap.md, GUI
# ekran görüntüsüyle doğrulandı): (1) desen SADECE sorunun TAMAMI çıplak
# bir selamlaşma kelimesiyse eşleşiyordu (`^...$` - baştan sona) - "hello,
# i have a question for you" gibi doğal bir cümleye gömülü selamlaşma hiç
# yakalanmıyordu. (2) "how are you" hiç kapsanmıyordu, sadece Türkçe
# karşılıkları ("naber"/"nasılsın") vardı. Düzeltme: `$` çapasını
# kaldırıp sadece sorunun BAŞINDA bir selamlaşma olması yeterli kılındı
# (yine de `\b` ile korunuyor - "history" gibi bir kelimenin "hi" ile
# başlaması yüzünden yanlışlıkla eşleşmemesi için, "hi" sonrası "story"
# ile aynı kelimenin devamı olduğundan kelime sınırı orada oluşmuyor).
# Bu sadece DÜŞÜK-GÜVEN/generative-fallback dalındaki uyarı etiketini
# gösterip göstermeme kararını etkiliyor - gerçek RAG eşleşmesi bulunan
# hiçbir soruyu etkilemiyor (bu desen sadece o dalda kontrol ediliyor).
CASUAL_CHAT_PATTERN = re.compile(
    r"^(selam\w*|merhaba\w*|hey+|hi+|hello\w*|naber|n'aber|nasılsın\w*|"
    r"nasilsin\w*|iyi misin\w*|günaydın\w*|gunaydin\w*|iyi ak[sş]amlar\w*|"
    r"iyi geceler|te[sş]ekkür\w*|sa[gğ]ol\w*|thanks?\w*|thank you|"
    r"how are you\w*|how('s| is) it going\w*|"
    r"g[oö]r[uü][sş][uü]r[uü]z\w*|bye+|ho[sş][cç]a ?kal\w*|kimsin\w*|"
    r"nesin\w*|ne haber|selamlar)\b[\s!.,?]*",
    re.IGNORECASE
)

SYSTEMD_UNIT_TYPES = {
    "systemd.service", "systemd.socket", "systemd.mount",
    "systemd.timer", "systemd.path"
}
SYSTEMD_SHARED_DIRECTIVE_SOURCES = (
    "systemd.exec", "systemd.kill", "systemd.resource-control"
)

# Aşağıdaki, komuta/kısayola özgü arama yapıları load() içinde doldurulur -
# records/commands.json içeriğine bağlı oldukları için modül yüklenirken
# değil, load() çağrıldığında inşa edilir.
COMMAND_NAME_PATTERNS: list = []
COMMAND_BARE_FLAGS: dict = {}
COMMAND_PARAMETER_NAMES: dict = {}
SHORTCUT_SOURCE_COMMANDS: set = set()
SHORTCUT_LOOKUP: dict = {}
EXAMPLE_RECORD_BY_COMMAND: dict = {}
parameter_mask = None
shortcut_mask = None

_loaded = False


def _load_with_offline_fallback(loader: Callable[[bool], object], on_progress):
    """Hugging Face önbelleği zaten diskte varsa hiç ağa çıkmadan
    yükler. `loader`, tek bir `local_files_only: bool` parametresi alan
    bir fonksiyon - bu parametreyi doğrudan from_pretrained()/
    SentenceTransformer()'a geçiyoruz, çünkü HF_HUB_OFFLINE/
    TRANSFORMERS_OFFLINE ortam değişkenlerini burada (load() içinde,
    yani transformers/sentence_transformers zaten import EDİLDİKTEN
    SONRA) set etmenin hiçbir etkisi yok - bu kütüphaneler o değişkeni
    kendi import anında bir kere okuyup sabitliyor, sonradan
    değiştirmek onları etkilemiyor (denendi, işe yaramadı - internet
    yokken yine donuyordu). local_files_only ise her çağrıda taze
    okunan gerçek bir fonksiyon parametresi, bu sorunu yaşamıyor. Önce
    local_files_only=True ile dener; sadece önbellekte hiç dosya yoksa
    (gerçek ilk çalıştırma) ağa izin verip indiriyor."""
    try:
        return loader(True)
    except OSError:
        on_progress("Downloading model files (first run, internet required)...")
        return loader(False)


def load(on_progress: Callable[[str], None] = print) -> None:
    """RAG indeksini ve modeli belleğe yükler. Hem test_model.py hem
    gui_app.py başlangıçta bunu bir kere çağırır. on_progress, ilerleme
    mesajlarını CLI'da print() ile, GUI'de ise bir durum etiketini
    güncelleyen bir fonksiyonla göstermek için kullanılır."""
    global embeddings, records, embedder, tokenizer, model
    global COMMAND_NAME_PATTERNS, COMMAND_BARE_FLAGS, COMMAND_PARAMETER_NAMES
    global SHORTCUT_SOURCE_COMMANDS, SHORTCUT_LOOKUP, EXAMPLE_RECORD_BY_COMMAND
    global parameter_mask, shortcut_mask, _loaded

    if _loaded:
        return

    on_progress("Loading search index...")

    embeddings = np.load(EMBEDDINGS_PATH)

    with RECORDS_PATH.open("r", encoding="utf-8") as f:
        records = json.load(f)

    with COMMANDS_PATH.open("r", encoding="utf-8") as f:
        commands_data = json.load(f)

    on_progress("Loading embedding model...")

    embedder = _load_with_offline_fallback(
        lambda local_files_only: SentenceTransformer(
            EMBEDDING_MODEL, local_files_only=local_files_only
        ),
        on_progress
    )

    parameter_categories = {"parameter", "overview"}
    parameter_mask = np.array(
        [r["category"] in parameter_categories for r in records]
    )

    # PowerShell/Windows cmdlet'leri veri setinde boşluklu saklanıyor ("get
    # item"), ama kullanıcıların doğal yazdığı hal tireli ("Get-Item") -
    # boşluklu her isim için ek olarak tireli bir varyant kaydediliyor.
    # systemd'nin man page adları nokta ile ayrılıyor ("systemd.service")
    # ama doğal cümleler boşluklu yazıyor ("systemd service unit") - nokta
    # içeren isimler için de boşluklu bir varyant kaydediliyor.
    command_names = {r["command"].lower() for r in records if r.get("command")}
    pattern_pairs = []

    for name in command_names:
        if not name:
            continue

        pattern_pairs.append(
            (name, re.compile(r"(?<![\w-])" + re.escape(name) + r"(?![\w-])"))
        )

        if " " in name:
            hyphenated = name.replace(" ", "-")
            pattern_pairs.append(
                (name, re.compile(r"(?<![\w-])" + re.escape(hyphenated) + r"(?![\w-])"))
            )

        if "." in name:
            spaced = name.replace(".", " ")
            pattern_pairs.append(
                (name, re.compile(r"(?<![\w-])" + re.escape(spaced) + r"(?![\w-])"))
            )

    COMMAND_NAME_PATTERNS = sorted(pattern_pairs, key=lambda pair: len(pair[0]), reverse=True)

    SHORTCUT_SOURCE_COMMANDS = {
        c.get("command") for c in commands_data
        if "shortcut" in (c.get("path") or "").lower()
    }
    shortcut_mask = np.array([
        r.get("command") in SHORTCUT_SOURCE_COMMANDS for r in records
    ])

    for i, r in enumerate(records):
        if r.get("command") in SHORTCUT_SOURCE_COMMANDS:
            SHORTCUT_LOOKUP.setdefault(
                normalize_shortcut_text(r["command"]), []
            ).append(i)

    for r in records:
        for pattern in BARE_FLAG_TEMPLATE_PATTERNS:
            match = pattern.match(r["instruction"].strip())
            if match:
                cmd = match.group(1).lower()
                COMMAND_BARE_FLAGS.setdefault(cmd, set()).add(match.group(2))
                break

    for cmd in commands_data:
        cname = (cmd.get("command") or "").lower()
        if not cname:
            continue
        for p in cmd.get("parameters") or []:
            pname = p.get("name", "")
            if pname:
                COMMAND_PARAMETER_NAMES.setdefault(cname, set()).add(pname)

    # Bir komutun "example" kaydı (gerçek, kaynaktan çekilmiş kullanım
    # örnekleri - bkz. find_example_snippet) genelde aynı komut için
    # birden fazla dilde (en/tr) tekrarlanıyor, ama response'u aynı -
    # ilk görüleni tutmak yeterli.
    for i, r in enumerate(records):
        if r.get("category") == "example":
            cname = (r.get("command") or "").lower()
            if cname:
                EXAMPLE_RECORD_BY_COMMAND.setdefault(cname, i)

    on_progress("Loading tokenizer...")

    tokenizer = _load_with_offline_fallback(
        lambda local_files_only: AutoTokenizer.from_pretrained(
            MODEL_NAME, local_files_only=local_files_only
        ),
        on_progress
    )

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    on_progress("Loading base model...")

    model = _load_with_offline_fallback(
        lambda local_files_only: AutoModelForCausalLM.from_pretrained(
            MODEL_NAME, dtype=MODEL_DTYPE, local_files_only=local_files_only
        ),
        on_progress
    )
    model = model.to(DEVICE)
    model.eval()

    on_progress("Model ready.")
    _loaded = True


def find_mentioned_command(question: str):
    question_lower = question.lower()
    candidates = []

    for name, pattern in COMMAND_NAME_PATTERNS:
        match = pattern.search(question_lower)

        if match:
            candidates.append((name, match.start()))

    if not candidates:
        return None

    non_generic = [c for c in candidates if c[0] not in GENERIC_WORD_COMMAND_NAMES]
    pool = non_generic or candidates

    best_name = None
    best_start = None
    best_length = -1

    for name, start in pool:
        if (
            best_start is None
            or start < best_start
            or (start == best_start and len(name) > best_length)
        ):
            best_name = name
            best_start = start
            best_length = len(name)

    return best_name


def find_command_scoped_candidates(mentioned_command: str):
    return [
        i for i in range(len(records))
        if parameter_mask[i]
        and records[i].get("command", "").lower() == mentioned_command
    ]


def find_command_all_category_candidates(mentioned_command: str):
    return [
        i for i in range(len(records))
        if records[i].get("command", "").lower() == mentioned_command
        and records[i].get("category") != "intent"
    ]


def find_exact_flag_within(flag: str, candidate_indices: list):
    boundary_pattern = re.compile(r"(?<![\w-])" + re.escape(flag) + r"(?![\w-])")

    exact = [
        i for i in candidate_indices
        if boundary_pattern.search(records[i]["instruction"])
    ]

    return exact or None


BUNDLED_SHORT_FLAGS_PATTERN = re.compile(r"^-([A-Za-z]{2,})$")


def find_bundled_short_flags_within(flag: str, candidate_indices: list):
    """"docker exec -it ..." gibi sorularda "-it" aslında "-i" + "-t"nin
    kabuk kısayolu birleştirilmiş hali - kendi başına, ayrı dokümante
    edilmiş bir bayrak değil (aynı kısayol grep/tar/ls gibi birçok POSIX
    aracında da var: "-la", "-xvf"...). "-it" hiçbir kaydın adında
    birebir geçmediği için find_exact_flag_within hep boş dönüyor, soru
    gerçek veri (hem -i hem -t zaten dokümante) varken bile ham modelin
    tahminine düşüyordu. Token TEK tireli ve 2+ harfliyse (çift tireli
    "--foo" DEĞİLSE), her harfi ayrı bir bayrak ("-i", "-t") sayıp
    GERÇEKTEN var olanları arıyoruz - hangisi sorulan soruya en yakınsa
    (embedding aşamasında) o kazanıyor."""
    match = BUNDLED_SHORT_FLAGS_PATTERN.match(flag)

    if not match:
        return None

    combined: list[int] = []
    seen = set()

    for letter in match.group(1):
        for i in find_exact_flag_within(f"-{letter}", candidate_indices) or []:
            if i not in seen:
                seen.add(i)
                combined.append(i)

    return combined or None


def find_bare_flag_after_command(question: str, mentioned_command: str):
    pattern = re.compile(
        r"(?<![\w-])" + re.escape(mentioned_command) + r"(?![\w-])"
        r"\s+([A-Za-z][\w-]*)",
        re.IGNORECASE
    )
    match = pattern.search(question)

    if not match:
        return None

    token = match.group(1)
    known_flags = COMMAND_BARE_FLAGS.get(mentioned_command)

    if known_flags and token in known_flags:
        return token

    tail = question[match.end():]

    if re.match(r"\s*(?:do\??|ne\s+yapar\??)(?:\s|$)", tail, re.IGNORECASE):
        return token

    return None


def find_named_parameter_token(question: str, mentioned_command: str):
    known = COMMAND_PARAMETER_NAMES.get(mentioned_command)

    if not known:
        return None

    tokens = re.findall(r"[A-Za-z][\w-]*", question)
    matches = {
        token for token in tokens
        if token in known or (token + "=") in known
    }

    if len(matches) == 1:
        return matches.pop()

    return None


def find_systemd_shared_directive(question: str, mentioned_command: str):
    if mentioned_command not in SYSTEMD_UNIT_TYPES:
        return None

    for source in SYSTEMD_SHARED_DIRECTIVE_SOURCES:
        token = find_named_parameter_token(question, source)

        if token:
            return source, token

    return None


def looks_like_shortcut_question(question: str) -> bool:
    return bool(
        SHORTCUT_KEYWORDS.search(question) or SHORTCUT_COMBO_PATTERN.search(question)
    )


def normalize_shortcut_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"\bwindows\s+logo\s+key\b", "winkey", text)
    text = re.sub(r"\bwindows\s+key\b", "winkey", text)
    text = re.sub(r"\bwin\b", "winkey", text)
    return re.sub(r"\s+", "", text)


def find_exact_shortcut_pool(question: str):
    match = SHORTCUT_COMBO_EXTRACT.search(question)

    if not match:
        return None, False

    key = normalize_shortcut_text(match.group(1))
    pool = SHORTCUT_LOOKUP.get(key)

    if not pool and re.search(r"\d$", key):
        generalized_key = re.sub(r"\d+$", "number", key)
        pool = SHORTCUT_LOOKUP.get(generalized_key)

    return (pool, True) if pool else (None, True)


def retrieve(question: str, restrict_mask=None):
    query_vector = embedder.encode([question], normalize_embeddings=True)[0]

    if restrict_mask is not None:
        indices = np.where(restrict_mask)[0]
        similarities = embeddings[restrict_mask] @ query_vector
        best_local_index = int(np.argmax(similarities))
        best_index = int(indices[best_local_index])
        return records[best_index], float(similarities[best_local_index])

    similarities = embeddings @ query_vector
    best_index = int(np.argmax(similarities))

    return records[best_index], float(similarities[best_index])


def generate_with_model(question: str) -> str:
    """RAG'ın hiçbir iyi eşleşme bulamadığı sorularda temel Qwen2.5-
    0.5B-Instruct modelinden (LoRA adaptörü YOK - bkz. modül başındaki
    not) cevap üretir."""
    messages = [{"role": "user", "content": question}]

    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )

    inputs = tokenizer(text, return_tensors="pt").to(DEVICE)

    with torch.inference_mode():
        outputs = model.generate(
            **inputs,
            max_new_tokens=256,
            do_sample=False,
            repetition_penalty=1.1,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id
        )

    generated_tokens = outputs[0][inputs["input_ids"].shape[1]:]

    return tokenizer.decode(generated_tokens, skip_special_tokens=True)


# ~%3.7 kayıtta (bkz. 07_RAG.md Known Limitations #6) kaynak metindeki
# liste satır sonları extraction sırasında kaybolmuş - "Valid types
# include: - 'bool' - 'int' - 'expiry-date'" gibi tek, uzun ve okunması
# zor bir cümleye dönüşmüş. 2+ tekrar eden " - " (boşluk-tire-boşluk)
# güvenilir bir liste sinyali - normal bir cümle-arası tire ("bu önemli
# - çünkü ...") tek başına 1 kere geçer, gerçek bir liste 2+ kere
# tekrar eder; bu sinyal zaten Known Limitations #6'nın kendi
# tespitinde kullanıldı. "overview" gibi zaten satır satır ayrılmış ama
# sıkışık duran listelerde de (her flag kendi satırında, ama aralarında
# boş satır yok) öğeler arasına nefes payı ekliyoruz.
LIST_DASH_PATTERN = re.compile(r" - ")
BULLET_LINE_PATTERN = re.compile(r"\n(?=- )")


def reflow_answer_text(text: str) -> str:
    """Dataset'ten gelen metnin İÇERİĞİNE hiç dokunmadan, sadece satır
    sonlarını düzenleyerek okunabilirliğini artırır - kelime eklenmez/
    çıkarılmaz, sadece nereye satır/boş satır konacağı değişir."""
    if len(LIST_DASH_PATTERN.findall(text)) >= 2:
        text = LIST_DASH_PATTERN.sub("\n- ", text)

    text = BULLET_LINE_PATTERN.sub("\n\n", text)
    return re.sub(r"\n{3,}", "\n\n", text)


def find_example_snippet(command: str, flag: str):
    """Bir flag/parametre sorusunun cevabına, varsa dataset'teki
    GERÇEK bir kullanım örneğini eklemek için kullanılır - hiçbir şey
    uydurulmuyor, sadece "example" kategorisinde zaten duran, aynı
    komuta ait bir kaydın ilgili parçası birleştiriliyor. Bir komutun
    example kaydı genelde tek bir cevapta birden çok flag'i ayrı ayrı
    örnekliyor (boş satırla ayrılmış "açıklama + ```bash bloğu"
    parçaları halinde) - sorulan flag'in GEÇTİĞİ İLK parçayı
    döndürüyoruz, tüm bloğu değil (ilgisiz örneklerle cevabı
    şişirmemek için). Eşleşme yoksa None döner, hiçbir şey eklenmez."""
    idx = EXAMPLE_RECORD_BY_COMMAND.get(command)

    if idx is None:
        return None

    boundary_pattern = re.compile(r"(?<![\w-])" + re.escape(flag) + r"(?![\w-])")

    for block in records[idx]["response"].split("\n\n"):
        if boundary_pattern.search(block):
            return block.strip()

    return None


def answer_question(question: str) -> str:
    """Bir soruyu yanıtlar - test_model.py'nin REPL döngüsündeki ana
    mantığın birebir aynısı, sadece terminale print etmek yerine temiz
    (kod bloğu işaretleri kaldırılmış) cevap metnini döndürüyor."""
    if not _loaded:
        raise RuntimeError("mentor_core.load() önce çağrılmalı.")

    exact_pool = None
    restrict_mask = None
    known_command_without_data = False
    mentioned_command = None
    token_for_exact_match = None

    if looks_like_shortcut_question(question):
        restrict_mask = shortcut_mask
        exact_shortcut_pool, was_combo = find_exact_shortcut_pool(question)

        if was_combo:
            if exact_shortcut_pool:
                exact_pool = exact_shortcut_pool
            else:
                known_command_without_data = True

    else:
        mentioned_command = find_mentioned_command(question)

        flag_match = FLAG_PATTERN.search(question)
        flag_token = flag_match.group(0).strip() if flag_match else None

        bare_flag_token = None
        if not flag_token and mentioned_command:
            bare_flag_token = (
                find_bare_flag_after_command(question, mentioned_command)
                or find_named_parameter_token(question, mentioned_command)
            )

            if not bare_flag_token:
                shared = find_systemd_shared_directive(question, mentioned_command)

                if shared:
                    mentioned_command, bare_flag_token = shared

        is_flag_question = bool(
            flag_token or bare_flag_token or FLAG_KEYWORDS.search(question)
        )

        if is_flag_question:
            if mentioned_command:
                command_scoped = find_command_scoped_candidates(mentioned_command)

                if command_scoped:
                    scoped_mask = np.zeros(len(records), dtype=bool)
                    scoped_mask[command_scoped] = True
                    restrict_mask = scoped_mask

                    token_for_exact_match = flag_token or bare_flag_token
                    if token_for_exact_match:
                        exact_pool = find_exact_flag_within(
                            token_for_exact_match, command_scoped
                        )

                        if not exact_pool:
                            exact_pool = find_bundled_short_flags_within(
                                token_for_exact_match, command_scoped
                            )

                        if not exact_pool:
                            known_command_without_data = True
                else:
                    known_command_without_data = True
            else:
                restrict_mask = parameter_mask

        elif mentioned_command and "+" not in question:
            stripped_question = question.strip()
            is_intent_phrased = bool(INTENT_PHRASE_PATTERN.match(stripped_question))
            is_concept_phrased = bool(CONCEPT_QUESTION_PATTERN.match(stripped_question))

            if is_concept_phrased:
                # "what is a docker image?" ile "what does docker image
                # do?" neredeyse aynı embedding'e sahip - daraltmayı
                # atlamak yetmiyor, kayıt sınırsız aramada da kazanıyor
                # (veri setinde rakip bir kavram açıklaması yok, bkz.
                # CONCEPT_QUESTION_PATTERN'in üstündeki not). Komut adıyla
                # çakışan bir kavram sorusunu güvenle yanıtlamak yerine
                # dürüst fallback'e yönlendiriyoruz.
                known_command_without_data = True
            elif (
                mentioned_command not in GENERIC_WORD_COMMAND_NAMES
                and not is_intent_phrased
            ):
                all_category_scoped = find_command_all_category_candidates(
                    mentioned_command
                )

                if all_category_scoped:
                    scoped_mask = np.zeros(len(records), dtype=bool)
                    scoped_mask[all_category_scoped] = True
                    restrict_mask = scoped_mask

    if known_command_without_data:
        match, score = None, -1.0
    elif exact_pool:
        query_vector = embedder.encode([question], normalize_embeddings=True)[0]
        sims = embeddings[exact_pool] @ query_vector
        best_local = int(np.argmax(sims))
        match, score = records[exact_pool[best_local]], float(sims[best_local])
    else:
        match, score = retrieve(question, restrict_mask=restrict_mask)

    if restrict_mask is not None:
        high_confidence, low_confidence = (
            RESTRICTED_HIGH_CONFIDENCE, RESTRICTED_LOW_CONFIDENCE
        )
    else:
        high_confidence, low_confidence = HIGH_CONFIDENCE, LOW_CONFIDENCE

    if score >= high_confidence:
        answer = reflow_answer_text(match["response"])

    elif score >= low_confidence:
        answer = (
            f"(Closest match found - may not be exact)\n\n"
            f"{reflow_answer_text(match['response'])}"
        )

    else:
        # RAG'ın hiçbir iyi eşleşme bulamadığı HER durumda (hem sıradan
        # sohbet hem gerçekten eğitim verisi olmayan bir IT sorusu)
        # temel model kullanılıyor - LoRA adaptörü artık hiç yüklenmiyor
        # bile (bkz. modül başındaki not / 03_LoRA_Training.md "LoRA
        # Emekliye Ayrıldı"). Eskiden burada LoRA'yı devrede tutmak
        # "merhaba" gibi bir mesaja bile sahte bir komut referansı
        # uydurmasına yol açıyordu ("kimsin sen komutu Kerberos bileti
        # oluşturur" gibi) - temel model sohbet mesajlarını doğal
        # yanıtlarken IT sorularında da "uydurma bir referans makalesi"
        # yerine "bilmiyorum" tarzı daha dürüst bir cevap veriyor.
        generated = generate_with_model(question)
        if CASUAL_CHAT_PATTERN.match(question.strip()):
            answer = generated
        else:
            answer = (
                f"(No solid data on this topic - attempting a general "
                f"answer, don't trust this without verifying)\n\n"
                f"{generated}"
            )

    # Belirli bir flag sorusu gerçek veriden yanıtlandıysa (yukarıdaki
    # iki "gerçek veri" dalından biri, generative fallback DEĞİL) ve
    # dataset'te o flag'i gösteren GERÇEK bir kullanım örneği varsa,
    # cevaba ekliyoruz - hiçbir şey uydurulmuyor, sadece zaten
    # "example" kategorisinde duran, doğrulanmış bir kayıt birleştirilir.
    if score >= low_confidence and token_for_exact_match and mentioned_command:
        example = find_example_snippet(mentioned_command, token_for_exact_match)
        if example:
            answer = f"{answer}\n\nExample:\n{example}"

    answer = re.sub(r"```[\w-]*\n?", "", answer)
    # Kaynak markdown'daki **kalın** işaretleri düz metin arayüzde
    # (GUI/CLI, markdown render etmiyor) çift yıldız olarak kalıyordu -
    # ~174K kayıttan %7.2'sinde bulundu, işareti kaldırıp metni koru.
    answer = re.sub(r"\*\*(.+?)\*\*", r"\1", answer)
    return answer.strip()
