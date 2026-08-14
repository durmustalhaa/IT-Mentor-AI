import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

INPUT = Path("data/processed/documents.json")
OUTPUT = Path("data/processed/commands.json")


def wrap_code_block(text):
    text = text.strip()

    if not text:
        return ""

    # "text"/"output" etiketleri değil "bash" kullanılıyor: build_dataset.py'nin
    # remove_output_blocks() fonksiyonu terminal çıktısı dökümlerini temizlemek
    # için ```text/```output bloklarını siliyor - bu, asıl komutu da silerdi.
    return f"```bash\n{text}\n```"


# ---------------------------------------------------------------------------
# PowerShell / Windows docs: "## HEADING" sections, "### -Param" parameters
# ---------------------------------------------------------------------------

def extract_section(text, heading):
    """
    ## DESCRIPTION
    ## SYNTAX
    ## EXAMPLES
    gibi bölümleri çıkarır.
    """

    pattern = rf"##\s+{heading}\s*(.*?)(?=\n## |\Z)"

    match = re.search(
        pattern,
        text,
        re.DOTALL | re.IGNORECASE
    )

    if match:
        return match.group(1).strip()

    return ""


def extract_parameters(text):
    """
    PowerShell markdown dosyalarındaki

    ### -Path

    açıklamalarını yakalar.
    """

    parameters = []

    # Terminator eskiden sadece "\n### -X" (bir sonraki dash'li parametre
    # başlığı) veya "\n## " arıyordu - ama PowerShell dokümanlarının
    # PARAMETERS bölümü neredeyse her zaman dash'siz bir "### CommonParameters"
    # alt başlığıyla bitiyor (ör. "### -WhatIf" değil, düz "### CommonParameters").
    # Bu, bir cmdlet'in listelenen SON parametresinin açıklamasının, bu
    # başlığı ve altındaki ortak-parametre boilerplate metnini de yutmasına
    # yol açıyordu (2.193/34.565 parametre açıklaması etkilenmiş - neredeyse
    # her cmdlet'in son parametresi). Artık dash'li olsun olmasın HERHANGİ
    # bir "### " başlığı da bir sınır sayılıyor.
    matches = re.finditer(
        r"###\s+-(\S+)\s*(.*?)(?=\n###\s|\n## |\Z)",
        text,
        re.DOTALL | re.IGNORECASE
    )

    for match in matches:

        name = "-" + match.group(1).strip()

        description = match.group(2)

        # Kod bloklarını kaldır
        description = re.sub(
            r"```.*?```",
            "",
            description,
            flags=re.DOTALL
        )

        # Markdown linklerini sadeleştir
        description = re.sub(
            r"\[([^\]]+)\]\([^)]+\)",
            r"\1",
            description
        )

        description = description.replace("\n", " ")

        description = re.sub(
            r"\s+",
            " ",
            description
        ).strip()

        parameters.append({
            "name": name,
            "description": description
        })

    return parameters


def extract_markdown_table_parameters(text):
    """windows-docs'un klasik CMD komut referansları (netstat, schtasks,
    netsh, ping, ipconfig gibi - PowerShell cmdlet'i değil, geleneksel
    Windows komut satırı aracı) '### -ParamName' alt-başlık kalıbını değil,
    düz bir markdown tablosu kullanıyor: '## Parameters' ya da
    '### Parameters' başlığı altında '| Parameter | Description |'. Bu
    yüzden extract_parameters hep boş dönüyordu - 869 dosyadan 729'u bu
    tabloyu kullanıyor, hiçbiri parametre üretmiyordu.

    25 dosyada (netsh'in kendisi dahil) aynı tablo hiçbir başlık olmadan,
    düz metnin ortasında duruyor - başlık araması başarısız olursa, "|
    Parameter" ile başlayan herhangi bir tabloyu ikinci bir deneme olarak
    arıyoruz."""
    match = re.search(
        r"^#{2,3}\s+Parameters\s*\n+(.*?)(?=\n#{1,3}\s|\Z)",
        text,
        re.DOTALL | re.MULTILINE
    )

    if match:
        table_text = match.group(1)
    else:
        bare_match = re.search(
            r"^\|\s*Parameter\s*\|.*\n(?:^\|.*\n?)*",
            text,
            re.MULTILINE | re.IGNORECASE
        )

        if not bare_match:
            return []

        table_text = bare_match.group(0)

    parameters = []

    for row in table_text.strip().split("\n"):
        row = row.strip()

        if not row.startswith("|"):
            continue

        # Flag adının İÇİNDE gerçek bir pipe geçebiliyor - ya kaçışlı
        # (attrib'in "{+\|-}r" söz dizimi) ya da GitHub'ın tablo
        # işleyicisinin backtick içindeyken kaçışsız da tolere ettiği hali
        # (ktpass'in "`{-|+}`desonly" gibi). İkisini de hücre ayracı "|"
        # ile karışmasın diye bölmeden önce geçici bir yer tutucuya
        # çeviriyoruz - aksi halde split() yanlış hücrelere böler ve aynı
        # komuttaki tüm bu tarz flag'ler aynı anlamsız parçaya çakışıp
        # sahte "duplicate flag" üretiyordu.
        protected = re.sub(r"`[^`]*`", lambda m: m.group(0).replace("|", "\x00"), row)
        protected = protected.replace("\\|", "\x00")
        cells = [c.strip() for c in protected.strip("|").split("|")]
        cells = [c.replace("\x00", "|") for c in cells]

        if len(cells) < 2:
            continue

        name_cell, description_cell = cells[0], cells[-1]

        # Başlık satırı ve ayraç satırı ("--|--" ya da ":--|--:") atlanıyor.
        # Bazı sayfalarda (ör. bcdedit) TEK bir "### Parameters" yakalaması,
        # altında birden fazla "#### Alt Başlık" bölümünü de süpürüyor -
        # her birinin KENDİ başlık satırı var ama ilk sütunun adı her
        # zaman "Parameter" olmuyor (ör. "Option | Description"). Bu
        # yüzden başlık tespiti sadece ilk sütuna değil, ikinci sütunun
        # gerçekten "Description" yazıp yazmadığına da bakıyor - aksi
        # halde her tekrar eden başlık satırı "Option: Description" gibi
        # anlamsız, tekrarlayan sahte bir parametre üretiyordu.
        if (
            name_cell.lower() in ("parameter", "option", "name", "flag")
            and description_cell.lower() == "description"
        ):
            continue

        if set(name_cell) <= {"-", ":"}:
            continue

        # Bazı sayfalarda (ör. bitsadmin cache) "### Parameters" başlıklı
        # tablo aslında flag tanımlamıyor, her satırı ayrı bir alt-komut
        # SAYFASINA link veren bir indeks ("[bitsadmin cache and
        # help](bitsadmin-cache-and-help.md)" gibi) - docker'ın
        # "Subcommands" tablosuna denk gelir. Böyle satırlar flag değil,
        # atlanıyor (aksi halde her satırın ilk kelimesi aynı ortak
        # önekle - ör. "[bitsadmin" - çakışıp sahte "tekrarlayan flag"
        # üretiyordu).
        if re.match(r"^\[.+\]\(.+\)$", name_cell.strip()):
            continue

        # DocFX'in ":::no-loc text="-a":::" gibi lokalizasyon-dışı işaretleme
        # sözdizimi (birkaç dosyada, ör. netsh.md) - gerçek flag metnini
        # tırnak içinden çıkarıyoruz.
        no_loc_match = re.match(r':::no-loc\s+text="([^"]*)"', name_cell)

        if no_loc_match:
            name_cell = no_loc_match.group(1)

        tokens = name_cell.split()

        if not tokens:
            continue

        flag = tokens[0].strip("`*")

        description = re.sub(r"<[^>]+>", " ", description_cell)
        description = re.sub(r"\*\*([^*]+)\*\*", r"\1", description)
        description = re.sub(r"`([^`]+)`", r"\1", description)
        description = re.sub(r"\s+", " ", description).strip()

        if not flag or len(description) < 10:
            continue

        parameters.append({"name": flag, "description": description})

    return parameters


def strip_cmdlet_self_reference(text):
    """'The `Get-Process` cmdlet gets...' -> 'gets...' (isim tekrarını kaldırır)."""
    return re.sub(
        r"^(the\s+`[^`]+`\s+cmdlet\s+|this\s+cmdlet\s+)",
        "",
        text,
        flags=re.IGNORECASE
    )


def first_sentence_raw(text, max_chars=220):
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    text = strip_cmdlet_self_reference(text)

    if not text:
        return ""

    match = re.search(r"(.+?[.!?])(\s|$)", text)
    sentence = match.group(1) if match else text

    return sentence[:max_chars].strip()


# PowerShell'in kendi synopsis dili cmdlet-merkezli ("Copies an item from
# one location to another" - "copy a file" değil). En sık ihtiyaç duyulan
# sistem yönetimi cmdlet'leri için günlük ifadeler elle eklendi - git
# listesindeki gibi, uydurma değil, zaten doğru olan cmdlet'lere gerçek
# günlük dil karşılıkları.
CASUAL_POWERSHELL_INTENTS = {
    "Get-Process": [
        "see what programs are running",
        "check running processes in PowerShell",
    ],
    "Stop-Process": [
        "kill a process in PowerShell",
        "close a running program in PowerShell",
    ],
    "Get-Service": [
        "see what services are running in Windows",
        "check if a service is running",
    ],
    "Copy-Item": [
        "copy a file in PowerShell",
        "copy a folder in PowerShell",
    ],
    "Remove-Item": [
        "delete a file in PowerShell",
        "delete a folder in PowerShell",
    ],
    "New-Item": [
        "create a new file in PowerShell",
        "create a new folder in PowerShell",
    ],
    "Get-ChildItem": [
        "list files in a directory in PowerShell",
        "see whats in a folder in PowerShell",
    ],
    "Set-Location": [
        "change directory in PowerShell",
        "go to a different folder in PowerShell",
    ],
    "Get-Content": [
        "read a file in PowerShell",
        "view the contents of a file in PowerShell",
    ],
    "Start-Process": [
        "run a program in PowerShell",
        "launch an application in PowerShell",
    ],
    "Restart-Computer": [
        "restart my computer with PowerShell",
    ],
    "Rename-Item": [
        "rename a file in PowerShell",
    ],
    "Move-Item": [
        "move a file in PowerShell",
    ],
    "Test-Connection": [
        "ping a server in PowerShell",
        "check if a host is reachable",
    ],
    "Set-ExecutionPolicy": [
        "allow scripts to run in PowerShell",
    ],
    "Compress-Archive": [
        "zip a folder in PowerShell",
    ],
    "Expand-Archive": [
        "unzip a file in PowerShell",
    ],
}


def extract_frontmatter_description(text):
    """windows-docs makaleleri cmdlet formatında değil (## SYNOPSIS/DESCRIPTION
    başlığı yok), düz makale + YAML frontmatter. Frontmatter'daki
    'description:' alanı Microsoft'un kendi yazdığı temiz bir özet -
    SYNOPSIS/DESCRIPTION boş çıktığında buna düşülüyor."""
    frontmatter_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)

    if not frontmatter_match:
        return ""

    description_match = re.search(
        r"^description:\s*(.+)$", frontmatter_match.group(1), re.MULTILINE
    )

    if not description_match:
        return ""

    return description_match.group(1).strip().strip("'\"")


def parse_powershell_md(doc):
    text = doc["text"]

    title = ""

    for line in text.splitlines():

        line = line.strip()

        if line.startswith("# "):
            title = line[2:].strip()
            break

    command = doc["name"].replace("-", " ")

    description = extract_section(text, "DESCRIPTION")
    synopsis = extract_section(text, "SYNOPSIS")
    syntax = extract_section(text, "SYNTAX")
    examples = extract_section(text, "EXAMPLES")

    parameters = extract_parameters(text)

    if not parameters:
        parameters = extract_markdown_table_parameters(text)

    if not description and not synopsis:
        frontmatter_description = extract_frontmatter_description(text)

        if frontmatter_description:
            description = frontmatter_description

    # Synopsis 3. tekil şahıs bildirim kipinde ("Gets the processes...");
    # build_dataset.py bunu "I need a command that ..." kalıbına gömüyor.
    # Sadece gerçek cmdlet'ler (powershell-docs) için üretiliyor - windows-docs
    # makalelerinde "command" alanı dosya adından türetilmiş bir takma isim
    # (ör. "azure"), çalıştırılabilir bir komut değil; intent üretilirse
    # "You can use: azure" gibi yanıltıcı bir cevap ortaya çıkardı.
    intents = []

    if doc.get("source") == "powershell-docs":
        intent_phrase = (
            strip_cmdlet_self_reference(synopsis.strip())
            if len(synopsis.strip()) >= 25
            else first_sentence_raw(description)
        )

        if len(intent_phrase) >= 25:
            intents.append({
                "phrase": intent_phrase,
                "mood": "declarative",
                # "command" alanı soru metni için boşluklu ("Get Process");
                # gerçek çalıştırılabilir sözdizimi tireli haliyle
                # (doc["name"]) korunuyor.
                "command_hint": doc["name"]
            })

        for casual_phrase in CASUAL_POWERSHELL_INTENTS.get(doc["name"], []):
            intents.append({
                "phrase": casual_phrase,
                "mood": "imperative",
                "command_hint": doc["name"]
            })

    return title, command, description, synopsis, syntax, examples, parameters, intents


# ---------------------------------------------------------------------------
# Git docs: AsciiDoc format ("HEADING\n------\n" sections, "`-x`::" options)
# ---------------------------------------------------------------------------

def extract_adoc_section(text, heading):
    pattern = (
        rf"^{heading}\s*\n-{{2,}}\s*\n(.*?)"
        rf"(?=\n[A-Z][A-Z \-]{{2,}}\n-{{2,}}|\Z)"
    )

    match = re.search(
        pattern,
        text,
        re.MULTILINE | re.DOTALL
    )

    if match:
        return match.group(1).strip()

    return ""


def parse_adoc_term_section(section_text):
    """Bir AsciiDoc tanım-listesi bölümünü (terim'::' + girintili açıklama
    bloğu tekrarları) ayrıştırır. Hem OPTIONS (bayraklar) hem COMMANDS
    (alt komutlar) bölümleri aynı sözdizimini kullanıyor."""
    parameters = []

    # Git'in AsciiDoc kaynağında terimler farklı şekillerde yazılıyor:
    # çoğu dosyada backtick içinde ("`--flag`::"), 91 dosyada backtick'siz
    # dash'li düz metin ("-i::", "-e <pattern>::" - git-clean, git-config,
    # git-cherry-pick, diff-options...), bazı COMMANDS bölümlerinde ise
    # (git-config'in "list"/"get"/"set"/"unset"... alt komutları gibi)
    # backtick'siz VE dash'siz düz metin ("list::", "get::"). Sadece
    # backtick kalıbını tanıyan eski regex 91 dosyadaki 1.076 dash'li
    # bayrak tanımını (backtick'li 1.873 ile karşılaştırınca ~%36'sı)
    # sessizce atlıyordu (ör. git rebase'in "-i"si), dash zorunluluğu da
    # git-config'in dash'siz alt komutlarını hiç yakalamıyordu. Üçü de
    # kabul ediliyor - bu bölümler zaten `extract_adoc_section` ile
    # OPTIONS/COMMANDS'a daraltılmış olduğundan, "::" ile biten herhangi
    # bir düz metin satırının gerçek bir tanım-listesi terimi olma
    # ihtimali güvenle kabul edilebilecek kadar yüksek.
    term_block_pattern = re.compile(
        r"(?:^(?:`[^`]+`|[^\n`][^\n]*?)::[ \t]*\n)+",
        re.MULTILINE
    )

    term_blocks = list(term_block_pattern.finditer(section_text))

    # Açıklama metni artık girintiye HİÇ bakmadan, "bu terim bloğunun
    # bitişinden bir SONRAKİ terim bloğunun başlangıcına (ya da bölüm
    # sonuna) kadar olan her şey" olarak alınıyor - AsciiDoc tanım
    # listesinde bu aralık zaten mantıksal olarak o terimin açıklaması.
    # Eski hal SADECE girintili satırları kabul ediyordu, bu da üç farklı
    # biçimi ayrı ayrı yamalamayı gerektiriyordu (girintili - normal;
    # terim ile açıklama arasında boş satır - git-stash'ın pop/apply/
    # push/show'u; ve HİÇ girintisiz, "+" ile devam eden düz paragraflar
    # - git-remote/git-worktree'nin çoğu, git-stash/git-submodule'ün bir
    # kısmı, toplam ~53 girdi). Blok-aralığı yaklaşımı üçünü de tek
    # seferde, biçime bakmaksızın doğru yakalıyor.
    for index, term_match in enumerate(term_blocks):

        flag_block = term_match.group(0)
        description_start = term_match.end()
        description_end = (
            term_blocks[index + 1].start()
            if index + 1 < len(term_blocks)
            else len(section_text)
        )
        description_block = section_text[description_start:description_end]

        raw_flag_pairs = re.findall(
            r"^(?:`([^`]+)`|([^\n`][^\n]*?))::[ \t]*$",
            flag_block,
            re.MULTILINE
        )
        raw_flags = [
            backtick_flag or bare_flag
            for backtick_flag, bare_flag in raw_flag_pairs
        ]

        # Dash'siz terimleri kabul etmek (git-config'in "list"/"get"/
        # "set"... alt komutları için gerekliydi) AsciiDoc'ın diğer
        # amaçlarla kullandığı tanım listelerini de yakalamaya başladı:
        # italik gösterim için alt çizgi ("_<branch-name>_::"), tek
        # tırnak ("'write'::"), kaçışlı "--" ("\--::"), ve - en önemlisi
        # - örnek komut satırları ("`git gui citool --nocommit`::") ya da
        # etkileşimli menü açıklamaları ("filter by pattern::") gibi
        # gerçek bir bayrak/alt komut adı OLMAYAN ama aynı "terim::"
        # sözdizimini kullanan içerik. Önce AsciiDoc'ın metin-biçimlendirme
        # işaretleri temizleniyor (alt çizgi/tek tırnak sarmalayıcılar,
        # kaçışlı tire), sonra "--stat[=<width>...]" -> --stat gibi
        # opsiyonel argüman ekleri kesiliyor.
        raw_flags = [flag.strip("_'").replace("\\-", "-") for flag in raw_flags]
        flags = [
            re.split(r"[\[=<(]", flag)[0].strip()
            for flag in raw_flags
        ]

        # Gerçek bir bayrak her zaman "-" ile başlar - bunlar doğrudan
        # kabul ediliyor (bir üst bayrağın kendi açıklamasındaki iç içe
        # değer listesiyle güvenilir bir yapısal ayrım yok, ama açıklama
        # metni onlar için de doğru, bkz. yukarıdaki not). Dash'siz
        # kalanlar için ise, gerçek bir alt komut adının basit bir
        # tanımlayıcı olması gerekir (harf/rakam/tire/nokta, BOŞLUK
        # YOK) - yukarıdaki temizlikten sonra hâlâ boşluk ya da tuhaf
        # noktalama içeren her şey (çoklu kelimelik menü açıklamaları,
        # tam örnek komut satırları, tek başına kalan "_" gibi
        # biçimlendirme kalıntıları) gerçek bir terim değildir.
        bare_identifier_pattern = re.compile(r"^[A-Za-z][\w.-]*$")
        flags = [
            flag for flag in flags
            if flag and (flag.startswith("-") or bare_identifier_pattern.match(flag))
        ]

        # AsciiDoc'ın "+" satırı (tek başına bir satırda), aynı liste
        # öğesine bağlı YENİ bir paragraf başlangıcını işaretler - görsel
        # bir işaret, metne dahil edilmiyor.
        description = " ".join(
            line.strip()
            for line in description_block.splitlines()
            if line.strip() and line.strip() != "+"
        )

        description = re.sub(r"\s+", " ", description).strip()

        if not description:
            continue

        for flag in flags:
            parameters.append({
                "name": flag,
                "description": description
            })

    return parameters


# OPTIONS dışında flag/alt-komut tanımlayabilen bölüm başlıkları - her biri
# ayrı bir git sayfası ailesinde keşfedildi, aynı "eksik bölüm" hatasının
# farklı bir görünümü:
#   - COMMANDS: git-stash/git-remote/git-worktree/git-submodule/git-config
#     gibi 17 dosyada gerçek alt komutlar (pop/push/apply/list/show...)
#     OPTIONS'tan ayrı, kendi COMMANDS bölümünde dokümante ediliyor.
#   - DESCRIPTION: git-reset gibi sayfalarda gerçek bayraklar (`--hard`/
#     `--soft`/`--mixed`) OPTIONS'ta değil, bir kavram anlatılırken
#     DESCRIPTION içinde tanımlanıyor.
#   - SEQUENCER SUBCOMMANDS: git-cherry-pick/git-revert'te `--continue`/
#     `--skip`/`--abort`/`--quit` kendi ayrı bölümünde.
#   - MODE OPTIONS: git-rebase'de aynı `--continue`/`--abort`/`--skip`
#     ailesi burada "MODE OPTIONS" başlığı altında (SEQUENCER SUBCOMMANDS
#     değil - git'in kendi sayfaları arasında bile tutarlı bir isimlendirme
#     yok).
#   - DEPRECATED MODES: git-config'in eski `-l`/`--list` sözdizimi (yeni
#     `git config list` alt komutunun yerini aldı) burada dokümante
#     ediliyor - gerçek kullanıcılar hâlâ bu eski sözdizimini yazıyor.
# DESCRIPTION/DEPRECATED MODES gibi çok çeşitli düz metin içeren bölümlerde
# yanlış eşleşme riski daha yüksek, ama parse_adoc_term_section'ın uyguladığı
# temiz-tanımlayıcı filtresi (dash'li her zaman kabul, dash'siz sadece
# boşluksuz/noktalamasız gerçek bir kelime ise) bunu güvenli tutuyor - aynı
# isim daha önceki bir bölümde zaten bulunduysa burada tekrar eklenmiyor.
ADOC_FALLBACK_PARAMETER_SECTIONS = (
    "COMMANDS",
    "DESCRIPTION",
    "SEQUENCER SUBCOMMANDS",
    "MODE OPTIONS",
    "DEPRECATED MODES",
)


def extract_adoc_parameters(text):
    parameters = []

    options_section = extract_adoc_section(text, "OPTIONS")

    if options_section:
        parameters.extend(parse_adoc_term_section(options_section))

    for section_title in ADOC_FALLBACK_PARAMETER_SECTIONS:
        section_text = extract_adoc_section(text, section_title)

        if not section_text:
            continue

        existing_names = {p["name"] for p in parameters}

        for entry in parse_adoc_term_section(section_text):
            if entry["name"] not in existing_names:
                parameters.append(entry)
                existing_names.add(entry["name"])

    return parameters


def convert_adoc_code_blocks(text):
    """AsciiDoc '------------' literal blokları ```text çitine çevirir."""
    return re.sub(
        r"-{4,}\s*\n(.*?)\n-{4,}",
        lambda m: wrap_code_block(m.group(1)),
        text,
        flags=re.DOTALL
    )


def resolve_adoc_conditionals(text, defined_attrs):
    """ifdef::attr[]...endif::attr[] ve ifndef::attr[]...endif::attr[]
    bloklarını, belgede tanımlanan attribute'lara göre çözer (blok
    koşulu sağlıyorsa içeriği bırakır, sağlamıyorsa siler)."""

    def replace_ifdef(match):
        attr, block = match.group(1), match.group(2)
        return block if attr in defined_attrs else ""

    def replace_ifndef(match):
        attr, block = match.group(1), match.group(2)
        return block if attr not in defined_attrs else ""

    text = re.sub(
        r"ifdef::([\w-]+)\[\]\n(.*?)endif::\1\[\]\n?",
        replace_ifdef, text, flags=re.DOTALL
    )
    text = re.sub(
        r"ifndef::([\w-]+)\[\]\n(.*?)endif::\1\[\]\n?",
        replace_ifndef, text, flags=re.DOTALL
    )

    return text


def resolve_git_includes(text, doc_dir):
    """git dokümanları OPTIONS bölümlerini genelde 'include::diff-options.adoc[]'
    gibi paylaşılan parça dosyalarından çekiyor - bunları çözmezsek
    git diff/log/fetch gibi komutların gerçek seçeneklerinin çoğu kayboluyor.
    Dahil edilen içerik, bu belgede tanımlanan (':attr: değer' satırlarıyla)
    attribute'lara göre ifdef/ifndef bloklarıyla filtreleniyor."""
    defined_attrs = set(re.findall(r"^:([\w-]+):\s*\S", text, re.MULTILINE))

    def replace_include(match):
        filename = match.group(1)
        include_path = doc_dir / filename

        if not include_path.exists():
            return ""

        try:
            included_text = include_path.read_text(
                encoding="utf-8", errors="ignore"
            )
        except OSError:
            return ""

        included_text = resolve_adoc_conditionals(included_text, defined_attrs)

        # Nadir iç içe include'lar çözülmeye çalışılmıyor, sadece temizleniyor.
        included_text = re.sub(r"include::[\w./-]+\[\]\n?", "", included_text)

        return included_text

    return re.sub(r"include::([\w./-]+)\[\]", replace_include, text)


# Git'in kendi başlıkları resmi/teknik dilde ("Update remote refs along
# with associated objects" - git push için). Yeni başlayanların gerçekte
# kullandığı günlük ifadeler ("upload", "download", "undo") bu kelimelerle
# hiç örtüşmüyor, hiçbir dokümantasyon kaynağı da bunları kullanmıyor - bu
# yüzden en sık aranan komutlar için elle eklendi. Uydurma bilgi değil,
# zaten doğru olan komutlara gerçek günlük dil karşılıkları ekleniyor.
CASUAL_GIT_INTENTS = {
    "git-push": [
        "upload my project to GitHub",
        "send my local commits to the remote repository",
        "publish my changes to GitHub",
    ],
    "git-pull": [
        "download the latest changes from the remote repository",
        "sync my local copy with GitHub",
        "get the newest updates from the remote",
    ],
    "git-clone": [
        "download a copy of a repository from GitHub",
        "copy a remote repository to my computer",
    ],
    "git-commit": [
        "save my changes with a message",
    ],
    "git-add": [
        "stage my changes for commit",
    ],
    "git-status": [
        "see what files have changed",
    ],
    "git-switch": [
        "switch to a different branch",
    ],
    "git-checkout": [
        "switch to a different branch",
    ],
    "git-merge": [
        "combine changes from another branch",
    ],
    "git-reset": [
        "undo my last change",
    ],
    "git-stash": [
        "temporarily save my uncommitted changes",
    ],
    "git-log": [
        "see the commit history",
    ],
    "git-branch": [
        "create a new branch",
    ],
    "git-remote": [
        "connect my local repository to GitHub",
    ],
}


def parse_git_adoc(doc):
    text = doc["text"]
    text = resolve_git_includes(text, Path(doc["path"]).parent)

    name_section = extract_adoc_section(text, "NAME")

    title = (
        name_section.splitlines()[0].strip()
        if name_section else doc["name"]
    )

    # SADECE ilk tire "git" ile alt komut adı arasındaki gerçek ayraç -
    # "git-log" -> "git log" doğru, ama 86 dosyada alt komutun KENDİ adı da
    # tire içeriyor ("git-cherry-pick", "git-diff-tree", "git-rev-list"...)
    # ve gerçekte "git cherry-pick"/"git diff-tree" olarak çalıştırılıyor,
    # "git cherry pick" diye bir komut yok. Eskiden TÜM tireler boşluğa
    # çevriliyordu, bu da bu 86 komutun retrieval'da hiç bulunamamasına yol
    # açıyordu (kullanıcı doğal, tireli haliyle sorduğunda komut adı
    # eşleşmiyordu - ör. "git cherry-pick --continue" alakasız bir bayrağın
    # cevabını dönüyordu).
    command = doc["name"].replace("-", " ", 1)

    description = extract_adoc_section(text, "DESCRIPTION")
    description = convert_adoc_code_blocks(description)

    synopsis_raw = extract_adoc_section(text, "SYNOPSIS")
    synopsis_raw = re.sub(
        r"^\[synopsis\]\s*\n?",
        "",
        synopsis_raw,
        flags=re.IGNORECASE
    )
    syntax = wrap_code_block(synopsis_raw)

    examples = extract_adoc_section(text, "EXAMPLES")
    examples = convert_adoc_code_blocks(examples)

    parameters = extract_adoc_parameters(text)

    # NAME bölümü "git-status - Show the working tree status" biçiminde;
    # " - " sonrası emir kipinde bir yetenek tanımı, intent kaynağı olarak kullanılıyor.
    intents = []

    # Sadece gerçek alt komutlar ("git-status.adoc") emir kipi bir yetenek
    # tanımına sahip; kavramsal belgeler ("gitattributes.adoc",
    # "gitprotocol-capabilities.adoc") isim tamlaması başlıklar içeriyor ve
    # "I want to ..." kalıbına gömüldüğünde bozuk cümle üretiyor.
    if doc["name"].startswith("git-") and " - " in title:
        capability_phrase = title.split(" - ", 1)[1].strip()

        if len(capability_phrase) >= 10:
            intents.append({
                "phrase": capability_phrase,
                "mood": "imperative"
            })

    for casual_phrase in CASUAL_GIT_INTENTS.get(doc["name"], []):
        intents.append({
            "phrase": casual_phrase,
            "mood": "imperative"
        })

    # Git'in kendi "SYNOPSIS" bölümü kısa bir açıklama değil, kullanım
    # satırıdır; PowerShell'deki gibi ayrı bir özet olmadığı için boş
    # bırakılıp description'a düşülüyor.
    return title, command, description, "", syntax, examples, parameters, intents


# ---------------------------------------------------------------------------
# Linux docs: tldr-pages Markdown format ("> desc", "- text:\n`cmd`" örnekleri)
# ---------------------------------------------------------------------------

def clean_tldr_placeholder(token):
    token = token.strip()

    if token.startswith("[") and token.endswith("]"):
        token = token[1:-1]

    if "|" in token:
        parts = [part.strip() for part in token.split("|")]
        long_forms = [part for part in parts if part.startswith("--")]
        return long_forms[0] if long_forms else parts[0]

    return f"<{token}>"


def clean_tldr_command(raw_command):
    return re.sub(
        r"\{\{(.*?)\}\}",
        lambda m: clean_tldr_placeholder(m.group(1)),
        raw_command
    )


def extract_single_flag(command_text):
    """Bir komut satırında TEK bir bayrak varsa onu döner; birden fazla
    bayrak varsa boş döner (açıklama hangisine ait belirsizleşir)."""
    flags = [
        token for token in command_text.split()
        if re.match(r"^-{1,2}[A-Za-z][\w-]*$", token)
    ]

    return flags[0] if len(flags) == 1 else ""


def parse_tldr_md(doc):
    text = doc["text"]

    title = ""

    for line in text.splitlines():

        if line.startswith("# "):
            title = line[2:].strip()
            break

    # git'in kendi AsciiDoc kaynağıyla aynı isimlendirme kuralı kullanılıyor
    # (bkz. parse_git_adoc) - "git-cherry-pick.md" gibi sayfalar da SADECE
    # ilk tireden bölünüyor ("git cherry-pick"), aksi halde iki kaynağın
    # aynı komut için ürettiği isimler örtüşmez ve merge_complementary_sources
    # tldr'nin gerçek örneklerini hiç bulamaz (docker-compose gibi tldr'nin
    # KENDİ çok-kelimeli alt-komut kuralını kullanan dosyalar için tam
    # tire->boşluk dönüşümü hâlâ doğru, sadece "git-" öneki özel).
    if doc["name"].startswith("git-"):
        command = doc["name"].replace("-", " ", 1)
    else:
        command = doc["name"].replace("-", " ")

    description_lines = [
        line[2:].strip()
        for line in text.splitlines()
        if line.startswith("> ")
        and not line.lower().startswith("> more information")
    ]

    description = " ".join(description_lines).strip()
    description = re.sub(r"`([^`]+)`", r"\1", description)

    pair_pattern = re.compile(
        r"^-\s+(.+?):\s*\n\n`(.+?)`\s*$",
        re.MULTILINE
    )

    example_blocks = []
    intents = []
    parameters = []
    seen_flags = set()
    first_command = ""

    for match in pair_pattern.finditer(text):

        explanation, raw_command = match.groups()

        cleaned_command = clean_tldr_command(raw_command)

        if not first_command:
            first_command = cleaned_command

        example_blocks.append(
            f"{explanation.strip()}:\n{wrap_code_block(cleaned_command)}"
        )

        # tldr'ın "ne yapmak istiyorsun -> hangi komut" eşleşmesi zaten hazır;
        # her satır ayrı bir intent örneği olarak kullanılıyor.
        if len(explanation.strip()) >= 10:
            intents.append({
                "phrase": explanation.strip(),
                "mood": "imperative",
                "command_hint": cleaned_command
            })

        # Satırda tek bir bayrak varsa, bu bayrağı o satırın açıklamasıyla
        # eşleştir (parametre sorularının kaynağı). Birden fazla bayrak
        # içeren satırlar atlanıyor - açıklama hangisine ait belirsiz olurdu.
        flag = extract_single_flag(cleaned_command)

        if flag and flag not in seen_flags and len(explanation.strip()) >= 10:
            seen_flags.add(flag)
            parameters.append({
                "name": flag,
                "description": explanation.strip()
            })

    examples = "\n\n".join(example_blocks)
    syntax = wrap_code_block(first_command) if first_command else ""

    return title, command, description, "", syntax, examples, parameters, intents


# ---------------------------------------------------------------------------
# Windows shortcuts: elle kaydedilmiş "# Section" / "## Shortcut" listesi.
# Diğer formatlardan farklı olarak TEK dosya BİRÇOK komut üretir.
# ---------------------------------------------------------------------------

def parse_shortcut_list(doc):
    text = doc["text"]

    entries = re.findall(
        r"^##\s+(.+?)\s*\n(.+?)(?=\n#{1,2}\s|\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL
    )

    records = []

    for shortcut, action in entries:
        shortcut = shortcut.strip()
        action = " ".join(action.split())

        if not shortcut or len(action) < 10:
            continue

        records.append({
            "command": shortcut,
            "title": shortcut,
            "description": action,
            "synopsis": "",
            "syntax": "",
            "examples": "",
            "parameters": [],
            "intents": [{
                "phrase": action,
                "mood": "imperative",
                "command_hint": shortcut
            }],
            "path": doc["path"]
        })

    return records


# ---------------------------------------------------------------------------
# GNU coreutils: tek bir .texi dosyasında "@node X invocation" ile ayrılan
# onlarca komut, her biri "@table @samp" içinde @optItem/@optItemx ile
# TAM seçenek listesine sahip (tldr'nin aksine eksiksiz bir referans).
# ---------------------------------------------------------------------------

def clean_texinfo(text):
    text = re.sub(r"@c\n[ \t]*", " ", text)
    text = re.sub(r"@dots\{\}", "...", text)
    text = text.replace("@{", "{").replace("@}", "}")

    # "@@" tek bir HARFİ HARFİNE "@" karakteri demek (texinfo'da "@" özel
    # karakter olduğu için kendisi de kaçışlanmalı) - ör. ls -F'nin
    # sembolik link göstergesi @samp{@@} ya da "$@@" gibi shell örnekleri.
    # "@ " (aşağıdaki) kuralından ÖNCE çalışması şart: "@@ for" gibi bir
    # dizide "@ " kuralı yanlışlıkla SADECE ikinci "@"+boşluğu yiyip
    # tesadüfen doğru görünen ama yanlış mekanizmayla üretilmiş bir sonuç
    # verirdi.
    text = text.replace("@@", "@")

    # "@*" satır sonu zorlayan texinfo komutu - düz metinde bir boşluğa
    # çevriliyor.
    text = text.replace("@*", " ")

    # texinfo'nun cümle sonu noktalama kaçış dizileri: "@." (kısaltmadan
    # sonra gerçekten cümle biten nokta, ör. "user ID@.") ve "@ " (normal
    # kelime arası boşluk, kısaltmadan sonra fazladan boşluk eklenmesin
    # diye, ör. "Thu Jul@ 9"). Kaldırılmazsa açıklamalarda ham "@" karakteri
    # kalıyordu (ör. "POSIX@.", "TERM@.").
    text = text.replace("@.", ".").replace("@:", "").replace("@ ", " ")

    text = re.sub(
        r"^[ \t]*@(pindex|cindex|findex|vindex|noindent).*$",
        "",
        text,
        flags=re.MULTILINE
    )

    # @macro{içerik} -> içerik (iç içe makroları çözmek için tekrar tekrar).
    # @xref/@pxref/@ref BİLEREK bu genel açma işleminin DIŞINDA tutuluyor
    # (negatif lookahead) - printf gibi komutlarda "@xref{..., @command{printf}
    # format directives, ...}" şeklinde xref argümanının İÇİNDE başka bir
    # makro geçebiliyor; iç makroyu (@command{printf} -> printf) düzleştirip
    # xref'in KENDİSİNİ olduğu gibi bırakıyoruz. Aksi halde xref'i de bu
    # genel döngüye dahil etseydik, xref tamamen SİLİNMEK yerine referans
    # metni ("Output Conversion Syntax,, printf format directives, libc,
    # The GNU C Library Reference Manual" gibi) ham haliyle açıklamaya
    # sızardı - istenen bu değil, xref tamamen kaldırılmalı.
    previous = None
    while previous != text:
        previous = text
        text = re.sub(r"@(?!xref\{|pxref\{|ref\{)[A-Za-z]+\{([^{}]*)\}", r"\1", text)

    # İç içe makrolar düzleştirildikten sonra xref'in kendi kapanış
    # parantezi artık [^}]* ile güvenle bulunabiliyor (araya giren bir
    # iç makronun kendi "}"si kalmadı).
    text = re.sub(r"@(xref|pxref|ref)\{[^}]*\}\.?", "", text)

    # Tek başına kalan, süslü parantezsiz makro satırları (@example, @end vs.)
    text = re.sub(r"^[ \t]*@\S+.*$", "", text, flags=re.MULTILINE)

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def extract_texi_synopsis(section_text):
    # Sadece ilk seçenek tablosundan ÖNCEki giriş metnine bakılıyor - yoksa
    # komutun (ls gibi) resmi bir "Synopsis:" örneği yoksa, alt bölümlerdeki
    # bir flag'in açıklamasına gömülü rastgele bir örnek "syntax" sanılabilir.
    intro_text = section_text.split("@table @samp")[0]

    match = re.search(r"@example\s*\n(.*?)\n@end example", intro_text, re.DOTALL)

    if not match:
        return ""

    code = clean_texinfo(match.group(1))

    return wrap_code_block(code) if code else ""


def extract_texi_description(section_text):
    before_table = section_text.split("@table @samp")[0]
    before_table = re.sub(
        r"@example.*?@end example", "", before_table, flags=re.DOTALL
    )

    # "@menu ... @end menu" bloğu texinfo'nun içindekiler-listesi sözdizimi
    # ("* Madde adı:: kısa açıklama" satırları) - "@menu"/"@end menu"
    # satırlarının kendisi "@" ile başladığı için clean_texinfo tarafından
    # siliniyor, ama aradaki "* ..." satırları @ ile başlamadığından ham
    # haliyle açıklamaya sızıyordu (ör. ls/join/ptx gibi çok alt-bölümlü
    # komutlarda çirkin, yarım "* General options in join:: ..." satırları
    # görünüyordu). Tüm blok baştan kaldırılıyor.
    before_table = re.sub(
        r"@menu.*?@end menu", "", before_table, flags=re.DOTALL
    )

    # @example bloğu kaldırılınca, onu tanıtan cümle boşta "...:" diye asılı
    # kalabiliyor (ör. tail: "prints a one-line header... consisting of:" -
    # gösterilecek örnek zaten kaldırıldığı için cümle hiç tamamlanmadan bir
    # sonraki paragrafa atlıyordu). Böyle, bir paragraf boşluğuyla hemen
    # ardından hiçbir şey gelmeyen (yani konusu kaldırılmış) iki nokta üst
    # üsteyle biten cümleler, bir önceki GERÇEK cümle sonuna kadar geriye
    # kırpılıyor. "Gerçek cümle sonu" sınırı bilerek dar tutuluyor (nokta+
    # boşluk, nokta+satır başı, ya da paragraf boşluğu) - ilk denemede
    # sadece "önceki karakter nokta mı" bakıyordu, bu da "~/.bashrc" gibi
    # dosya adlarındaki noktayı da cümle sonu sanıp dircolors/env gibi
    # komutların açıklamasını yanlış yerden kesip atıyordu.
    before_table = re.sub(
        r"(?:(?<=\n\n)|(?<=\. )|(?<=\.\n)|\A)[^.]*?:\s*\n\s*\n",
        "\n\n", before_table, flags=re.DOTALL
    )

    return clean_texinfo(before_table)


def extract_texi_parameters(section_text):
    """Satır satır, iç içe geçme derinliğini (nesting depth) takip ederek
    işler. Regex tabanlı "@table @samp...@end table" blok eşleştirmesi iç
    içe tablolarda yanılıyordu: nl gibi komutlarda bir seçeneğin (ör. -n
    format açıklaması) İÇİNDE, örnek göstermek için ikinci bir
    "@table @samp...@end table" bulunabiliyor - iç içe olduğunu bilmeyen bir
    regex, dış tablonun bittiğini bu iç tablonun kapanışında sanıp ondan
    sonraki tüm gerçek seçenekleri (nl için 9 flag çifti) sessizce
    kaybediyordu. Derinlik sayacıyla sadece en dış (depth==1) "@table @samp"
    gerçek seçenek tablosu olarak işleniyor; içindeki iç içe tablolar o an
    işlenen flag'in açıklamasının bir parçası sayılıyor."""
    parameters = []

    depth = 0
    in_option_table = False
    current_flags: list[str] = []
    current_description_lines: list[str] = []

    def flush():
        if not current_flags:
            return

        description = clean_texinfo("\n".join(current_description_lines))

        if len(description) < 10:
            return

        for flag in current_flags:
            parameters.append({"name": flag, "description": description})

    for line in section_text.split("\n"):
        stripped = line.strip()

        if stripped.startswith("@table"):
            depth += 1

            if depth == 1:
                in_option_table = stripped.startswith("@table @samp")

            continue

        if stripped.startswith("@end table"):
            if depth == 1:
                flush()
                current_flags = []
                current_description_lines = []
                in_option_table = False

            depth = max(0, depth - 1)
            continue

        if not in_option_table:
            continue

        if depth > 1:
            # İç içe tablo içeriği - şu an işlenen flag'in açıklamasına dahil.
            if current_flags:
                current_description_lines.append(line)
            continue

        opt_match = re.match(r"^@optItemx?\{[\w-]+,([^,}]+)", stripped)

        if opt_match:
            if current_description_lines:
                flush()
                current_flags = []
                current_description_lines = []

            # "-@var{width}" gibi soyut kısayol gösterimleri (gerçek bir
            # bayrak adı değil) atlanıyor - grep ayrıştırıcısındaki aynı kural.
            flag = opt_match.group(1).strip()

            if "@" not in flag:
                current_flags.append(flag)
        elif not stripped and current_description_lines:
            # Paragraf sonu - açıklama bitti. Bir sonraki @optItem'e kadar
            # gelen satırlar (ör. @choptH{chmod} gibi paylaşılan makrolar)
            # bu bayrağın açıklaması değil, yok sayılıyor.
            flush()
            current_flags = []
            current_description_lines = []
        elif current_flags:
            current_description_lines.append(line)

    return parameters


# Birçok komut (cp, mv, ln, du, ls, chmod, head, tail, sort, uniq, cut...)
# kendi seçeneklerini doğrudan @optItem{...} ile değil, ortak bir kısayol
# makrosuyla (ör. @optZero{dirname}, @choptH{chmod}) tanımlıyor. Bu makrolar
# "@macro X{...} ... @end macro" bloğunda TANIMLANIYOR ama kullanım
# yerlerinde sadece çağrı olarak (@optZero{dirname}) görünüyor - metni hiç
# genişletmeden extract_texi_parameters'a versek, bu makroyla tanımlanan
# TÜM flag'ler (20 farklı makro, onlarca komutta kullanılıyor) sessizce
# kayboluyor. dirname/printenv denetiminde fark edildi: ikisi de gerçekte
# -z/--zero (veya -0/--null) flag'ine sahipken 0 parametreyle çıkıyorlardı.
def expand_texi_macros(text: str) -> str:
    macro_pattern = re.compile(
        r"^@macro\s+(\w+)(?:\{([^}]*)\})?\s*\n(.*?)\n@end macro\s*$",
        re.MULTILINE | re.DOTALL
    )

    # optItem/optItemx zaten extract_texi_parameters'ın anladığı hedef biçim -
    # bunları da genişletirsek @item/@itemx'e dönüşür ve parser'ı ayrıca
    # değiştirmek gerekir. Bunun yerine SADECE bunlara sarılı kısayol
    # makrolarını (optZero, choptH gibi) genişletip @optItem{...} çağrısında
    # duruyoruz - mevcut parser hiç değişmeden çalışmaya devam ediyor.
    do_not_expand = {"optItem", "optItemx", "optAnchor"}

    macros = {}

    for match in macro_pattern.finditer(text):
        name = match.group(1)

        if name in do_not_expand:
            continue

        params = (
            [p.strip() for p in match.group(2).split(",")]
            if match.group(2) else []
        )
        macros[name] = (params, match.group(3))

    text = macro_pattern.sub("", text)

    # İç içe makro çağrılarını çözmek için birkaç kez tekrarlanıyor (ör.
    # optNull kendi içinde ayrı bir makro olan outputNUL'u çağırıyor).
    for _ in range(6):
        any_change = False

        for name, (params, body) in macros.items():
            if params:
                call_pattern = re.compile(r"@" + re.escape(name) + r"\{([^}]*)\}")
            else:
                call_pattern = re.compile(r"@" + re.escape(name) + r"\b")

            def substitute(match, params=params, body=body):
                if not params:
                    return body

                args = [a.strip() for a in match.group(1).split(",")]
                args += [""] * (len(params) - len(args))
                expanded = body

                for param_name, arg_value in zip(params, args):
                    expanded = expanded.replace(f"\\{param_name}\\", arg_value)

                return expanded

            text, n = call_pattern.subn(substitute, text)

            if n:
                any_change = True

        if not any_change:
            break

    return text


def parse_coreutils_texi(doc):
    text = expand_texi_macros(doc["text"])

    # "sha2 utilities" tek bir @node altında DÖRT komutu (sha224sum/256sum/
    # 384sum/512sum) birlikte belgeliyor - standart "@node X invocation"
    # kalıbına uymadığı için (ne "invocation" ile bitiyor ne TEK bir komut
    # adı taşıyor) aşağıdaki bölme deseni bunu hiç ayrı bir bölüm saymıyordu,
    # içeriği bir ÖNCEKİ komutun (sha1sum) bölümüne sessizce karışıyordu.
    # Bilinen TEK istisna olduğu için (diğer "@node X utilities" başlığı
    # alakasız bir bölüm) ayrıca isimlendirilerek bölme noktasına ekleniyor.
    sections = re.split(
        r"(?=^@node\s+\S+\s+invocation\s*$)|(?=^@node\s+sha2\s+utilities\s*$)",
        text, flags=re.MULTILINE
    )

    records = []

    for section in sections:
        sha2_match = re.match(r"^@node\s+sha2\s+utilities\s*$", section, re.MULTILINE)

        if sha2_match:
            # Bu bölümde gerçek bir flag/seçenek tanımı YOK - sadece genel
            # bir açıklama ve cksum'un ortak seçeneklerine yönlendirme
            # (aşağıdaki borrows_from mantığıyla aynı şekilde çözülüyor).
            description = extract_texi_description(section)

            for pindex_match in re.finditer(r"^@pindex\s+(\S+)\s*$", section, re.MULTILINE):
                records.append({
                    "command": pindex_match.group(1),
                    "title": f"{pindex_match.group(1)}: Print or check SHA-2 digests",
                    "description": description,
                    "synopsis": "",
                    "syntax": "",
                    "examples": "",
                    "parameters": [],
                    "intents": [],
                    "path": doc["path"],
                    "_borrows_from": "cksum" if "cksum common options" in section else None
                })

            continue

        node_match = re.match(
            r"^@node\s+(\S+)\s+invocation\s*$", section, re.MULTILINE
        )

        if not node_match:
            continue

        command_name = node_match.group(1)

        title_match = re.search(
            r"^@section\s+@command\{([^}]*)\}:\s*(.+)$", section, re.MULTILINE
        )

        # "@node Multi-call invocation" gerçek bir komut değil, coreutils'in
        # multi-call binary mekanizmasını anlatan bir bölüm başlığı - @section
        # satırındaki gerçek @command{} adı ("coreutils") node adından
        # ("Multi-call") farklı. Bu bölümün açıklaması ayrıca kendi @menu
        # listesini de (cat/tac/nl/od...) içine karıştırıp bozuk bir metin
        # üretiyor, bu yüzden gerçek bir komutmuş gibi kaydedilmemeli.
        if title_match and title_match.group(1) != command_name:
            continue

        title = title_match.group(2).strip() if title_match else command_name

        description = extract_texi_description(section)
        syntax = extract_texi_synopsis(section)
        parameters = extract_texi_parameters(section)

        # Bazı komutlar kendi seçeneklerini tanımlamıyor, başka bir komuta
        # ("md5sum" -> "cksum" düz @xref üzerinden, "dir"/"vdir" -> "ls")
        # "bkz." diyor. Aşağıda, hedef komutun parametreleri bu kayda
        # kopyalanıyor - aksi halde bu komutlar hiç flag'siz kalırdı.
        #
        # "cksum common options" ifadesi ("@ref{cksum common options}"
        # texinfo çapraz-referansının expand_texi_macros'tan SONRA bile
        # düz metin olarak kalan hali - @ref bir makro değil, hiç
        # genişletilmiyor) tüm checksum ailesinde (md5sum/sha1sum/b2sum/
        # cksum'un kendisi) aynen geçiyor - eskiden kontrol edilen
        # "@checksumUsage{" değişkeni bu noktada zaten genişletilmiş
        # olduğu için HİÇBİR ZAMAN eşleşmiyordu (ölü kod). Bu ifade,
        # "xref var VE kendi parametresi hiç yok" şartından FARKLI olarak,
        # b2sum gibi KENDİ EK bir seçeneği (-l/--length) olsa BİLE devreye
        # giriyor - b2sum'un "-l" dışındaki TÜM diğer bayrakları (-c,
        # --check, -b, --binary...) bu ayrım olmadan hiç eklenmiyordu,
        # çünkü "not parameters" şartı zaten dolu bir listeyle karşılaşınca
        # hiç denemiyordu. Birleştirme adımı zaten sadece EKSİK isimleri
        # ekliyor (var olanın üstüne yazmıyor), bu yüzden ikisini birlikte
        # kullanmak güvenli.
        borrows_from = None

        if "cksum common options" in section:
            borrows_from = "cksum"
        else:
            xref_match = re.search(r"@xref\{(\S+) invocation", section)

            if xref_match and not parameters:
                borrows_from = xref_match.group(1)

        if not description and not parameters:
            continue

        intents = []

        if len(title) >= 10:
            intents.append({
                "phrase": title,
                "mood": "imperative",
                "command_hint": command_name
            })

        records.append({
            "command": command_name,
            "title": title,
            "description": description,
            "synopsis": "",
            "syntax": syntax,
            "examples": "",
            "parameters": parameters,
            "intents": intents,
            "path": doc["path"],
            "_borrows_from": borrows_from
        })

    records_by_command = {r["command"]: r for r in records}

    for record in records:
        source_name = record.pop("_borrows_from")
        source_record = records_by_command.get(source_name) if source_name else None

        if source_record:
            existing_names = {p["name"] for p in record["parameters"]}

            for p in source_record["parameters"]:
                if p["name"] not in existing_names:
                    record["parameters"].append(dict(p))

            if not record["syntax"]:
                record["syntax"] = source_record["syntax"]

    return records


# ---------------------------------------------------------------------------
# Standart GNU texinfo kılavuzu (grep gibi): coreutils'in aksine TEK dosya
# TEK komutu belgeliyor, özel makro yok - standart @table @option / @item /
# @itemx kullanıyor, seçenekler birden fazla @table bloğuna (Matching
# Control, Output Control vb.) dağılmış durumda.
# ---------------------------------------------------------------------------

def extract_gnu_table_parameters(text):
    """coreutils ayrıştırıcısındaki aynı iç-içe-tablo sorunundan (bkz.
    extract_texi_parameters) etkilenmemek için derinlik takibiyle işleniyor -
    grep.texi'de de bir seçenek açıklamasının içinde örnek amaçlı iç içe bir
    @table bulunuyor."""
    parameters = []

    depth = 0
    in_option_table = False
    current_flags: list[str] = []
    current_description_lines: list[str] = []

    def flush():
        if not current_flags:
            return

        description = clean_texinfo("\n".join(current_description_lines))

        if len(description) < 10:
            return

        for flag in current_flags:
            parameters.append({"name": flag, "description": description})

    for line in text.split("\n"):
        stripped = line.strip()

        if stripped.startswith("@table"):
            depth += 1

            if depth == 1:
                in_option_table = stripped.startswith("@table @option")

            continue

        if stripped.startswith("@end table"):
            if depth == 1:
                flush()
                current_flags = []
                current_description_lines = []
                in_option_table = False

            depth = max(0, depth - 1)
            continue

        if not in_option_table:
            continue

        if depth > 1:
            if current_flags:
                current_description_lines.append(line)
            continue

        item_match = re.match(r"^@itemx?\s+(\S+)", stripped)

        if item_match:
            if current_description_lines:
                flush()
                current_flags = []
                current_description_lines = []

            # "-e @var{patterns}" -> -e ; "--color[=@var{WHEN}]" -> --color
            flag = re.split(r"[\[=]", item_match.group(1))[0].strip()

            # "-@var{num}" gibi genel/soyut kısayol kalıpları (gerçek bir
            # flag adı değil, ör. "-C 5" yerine "-5" yazılabildiğini
            # gösteren bir gösterim) - literal bir bayrak adı olmadığı
            # için atlanıyor.
            if flag and "@" not in flag:
                current_flags.append(flag)
        elif stripped.startswith("@opindex"):
            continue
        elif not stripped and current_description_lines:
            flush()
            current_flags = []
            current_description_lines = []
        elif current_flags:
            current_description_lines.append(line)

    return parameters


def parse_gnu_manual_texi(doc):
    text = doc["text"]

    command_name = doc["name"]

    title_match = re.search(
        r"^@title\s+(?:GNU\s+)?\S+:\s*(.+)$", text, re.MULTILINE | re.IGNORECASE
    )
    title = title_match.group(1).strip() if title_match else command_name

    description_match = re.search(
        r"^@node Introduction\s*\n@chapter Introduction\s*\n(.*?)(?=\n@node )",
        text,
        re.DOTALL | re.MULTILINE
    )
    description = (
        clean_texinfo(description_match.group(1)) if description_match else ""
    )

    syntax_match = re.search(
        r"^@node Invoking\b.*?@example\s*\n(.*?)\n@end example",
        text,
        re.DOTALL | re.MULTILINE
    )
    syntax = ""

    if syntax_match:
        code = clean_texinfo(syntax_match.group(1))
        syntax = wrap_code_block(code) if code else ""

    parameters = extract_gnu_table_parameters(text)

    if not description and not parameters:
        raise ValueError("gnu-manual-texi: tanınabilir içerik bulunamadı")

    intents = []

    if len(title) >= 10:
        intents.append({
            "phrase": title,
            "mood": "imperative",
            "command_hint": command_name
        })

    return title, command_name, description, "", syntax, "", parameters, intents


def parse_docker_option_row(row: str):
    # Açıklama metninin İÇİNDE kaçışlı bir pipe geçebiliyor (ör. "format:
    # <name\|uid>[:<group\|gid>]") - satırı hücre ayracı "|" ile bölmeden
    # önce bunu geçici bir yer tutucuya çevirmezsek, split() gerçek hücre
    # sayısını yanlış sayar ve açıklama son "\|"den sonraki kısma
    # (ör. sadece "gid>])") kesilip kalır.
    protected = row.replace("\\|", "\x00")
    cells = [c.strip() for c in protected.strip().strip("|").split("|")]

    if len(cells) < 4:
        return []

    name_cell, description_cell = cells[0], cells[-1]

    # Zenginleştirilmiş sayfalarda (container_run.md gibi) flag adları düz
    # `-w` yerine markdown link ile [`-w`](#workdir) şeklinde yazılıyor -
    # linki soyup sadece flag adını almak gerekiyor.
    flags = []

    for piece in name_cell.split(","):
        piece = piece.strip()
        link_match = re.match(r"^\[(.+)\]\([^)]*\)$", piece)

        if link_match:
            piece = link_match.group(1)

        flag = piece.strip("` ")

        if flag:
            flags.append(flag)

    description = description_cell.replace("<br>", "\n").replace("\x00", "|").strip()

    if not flags or len(description) < 5:
        return []

    return [{"name": flag, "description": description} for flag in flags]


def parse_docker_cli_md(doc):
    text = doc["text"]

    # index.md gibi gerçek bir komut sayfası olmayan dosyalarda bu işaretçi
    # yok - docs/reference/commandline'daki OTOMATİK ÜRETİLMİŞ komut
    # sayfalarının hepsinde var, güvenilir bir "gerçek komut mu" sinyali.
    if "<!---MARKER_GEN_START-->" not in text:
        raise ValueError("docker-cli-md: üretilmiş komut sayfası değil")

    title_match = re.match(r"^#\s+(.+)$", text.strip(), re.MULTILINE)
    title = title_match.group(1).strip() if title_match else doc["name"]

    alias_match = re.search(r"^### Aliases\s*\n\s*\n(.+)$", text, re.MULTILINE)
    aliases = (
        [a.strip("` ") for a in alias_match.group(1).split(",")]
        if alias_match else []
    )

    # Birçok komut aynı anda hem eski düz isimle (run.md) hem yeni
    # namespaced isimle (container_run.md) iki ayrı dosyada duplike
    # ediliyor - namespaced olan HER ZAMAN daha zengin (Description +
    # Examples de içeriyor). Düz (alt çizgisiz) dosya bir Aliases
    # bölümüne sahipse, daha zengin bir namespaced kopyası olduğu
    # anlamına gelir - bu dosya atlanıyor, işi namespaced kopya yapacak.
    if "_" not in doc["name"] and aliases:
        return "", "", "", "", "", "", [], []

    if aliases:
        command_name = min(aliases, key=len)
    elif doc["name"] == "docker":
        command_name = "docker"
    else:
        command_name = "docker " + doc["name"].replace("_", " ")

    # MARKER_GEN_START'tan sonraki ilk paragraf - Cobra'nın "Short" alanından
    # otomatik üretiliyor, her zaman komutla ilgili ve güvenilir. Ayrıca bir
    # "## Description" bölümü de var ama içeriği tutarsız - bazı sayfalarda
    # gerçekten komutu anlatan daha ayrıntılı bir metin (container_run.md),
    # bazılarında ise komutla ilgisiz bir yan not (docker.md'nin
    # "## Description"ı komut açıklaması değil, sudo izin ayarları hakkında) -
    # "daha uzun olanı tercih et" güvenilmez çıktı, bu yüzden sadece kısa,
    # her zaman doğru olan özet kullanılıyor.
    short_desc_match = re.search(
        r"<!---MARKER_GEN_START-->\s*\n(.+?)\n\n", text, re.DOTALL
    )
    description = short_desc_match.group(1).strip() if short_desc_match else ""

    subcommand_match = re.search(
        r"^### Subcommands\s*\n\s*\n(.+?)\n\n", text, re.DOTALL | re.MULTILINE
    )

    if subcommand_match:
        sub_names = re.findall(r"^\|\s*\[`([\w-]+)`\]", subcommand_match.group(1), re.MULTILINE)

        if sub_names:
            description = (description + " Subcommands: " + ", ".join(sub_names) + ".").strip()

    options_match = re.search(
        r"^### Options\s*\n\s*\n(.+?)\n\n", text, re.DOTALL | re.MULTILINE
    )

    parameters = []

    if options_match:
        rows = options_match.group(1).strip().split("\n")[2:]  # başlık + ayraç satırı atla

        for row in rows:
            parameters.extend(parse_docker_option_row(row))

    # Eskiden belgedeki İLK ```console bloğu neresi olursa olsun alınıyordu
    # - çok adımlı bir anlatımda (ör. "docker push") ilk blok genelde
    # komutun kendisi değil, bir ÖN HAZIRLIK adımı oluyor ("docker
    # container commit ..." - önce yeni bir imaj oluştur, SONRA push et).
    # "docker load" için de ilk blok gerçek komuttan önceki bir "önce"
    # durumu gösteriyordu ("docker image ls" - henüz hiçbir şey
    # yüklenmemiş). Artık "## Examples" bölümü içindeki TÜM kod
    # bloklarından, gerçekten "$ docker ..." ile bu komutu (ya da
    # aliaslarından birini) çağıran İLK blok seçiliyor - yoksa (nadir)
    # ilk bloğa geri dönülüyor, önceki davranışla aynı.
    examples_section = extract_section(text, "Examples")
    code_blocks = re.findall(
        r"```console\n(.*?)\n```", examples_section, re.DOTALL
    )

    alias_names = aliases if aliases else [command_name]
    command_line_pattern = re.compile(
        r"^\$\s+(?:" + "|".join(re.escape(a) for a in alias_names) + r")\b",
        re.MULTILINE
    )

    example_text = next(
        (block for block in code_blocks if command_line_pattern.search(block)),
        code_blocks[0] if code_blocks else ""
    )

    examples = wrap_code_block(example_text) if example_text else ""

    syntax = wrap_code_block(f"{command_name} [OPTIONS]")

    if not description and not parameters:
        return "", "", "", "", "", "", [], []

    intents = []

    if len(description) >= 10:
        intents.append({
            "phrase": description.split(".")[0].strip(),
            "mood": "declarative",
            "command_hint": command_name
        })

    return title, command_name, description, "", syntax, examples, parameters, intents


def strip_ns(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def docbook_text(el) -> str:
    """Bir elementin İÇİNDEKİ tüm metni (iç içe <option>/<varname>/<emphasis>
    gibi satır-içi etiketleri de dahil ederek) tek bir düz metne çevirir.
    <citerefentry> (ör. "systemd" + manvolnum "1") özel olarak "systemd(1)"
    şeklinde biçimlendiriliyor - kaynak XML'de ikisi arasında boşluk
    olmadığından, düz itertext() bunu "systemd1" diye bitiştirirdi."""
    parts = []

    def walk(node):
        if node.text:
            parts.append(node.text)

        for child in node:
            if strip_ns(child.tag) == "citerefentry":
                title_el = child.find("refentrytitle")
                vol_el = child.find("manvolnum")
                name = (title_el.text or "").strip() if title_el is not None else ""
                vol = (vol_el.text or "").strip() if vol_el is not None else ""
                parts.append(f"{name}({vol})" if vol else name)
            else:
                walk(child)

            if child.tail:
                parts.append(child.tail)

    walk(el)
    return "".join(parts)


def preprocess_docbook_xml(text: str) -> str:
    """systemd'nin XML kılavuzları, build sırasında meson tarafından
    doldurulan özel entity'ler kullanıyor (&MOUNT_PATH; gibi,
    custom-entities.ent.in şablonundan). Bu depoda derleme yapılmadığı
    için o dosya hâlâ "{{MOUNT_PATH}}" gibi doldurulmamış placeholder'lar
    içeriyor - ElementTree'nin DOCTYPE'taki dış entity referansını
    çözmesini beklemek yerine, DOCTYPE bloğunu tamamen kaldırıp geriye
    kalan herhangi bir özel entity'yi (&isim;) sadece "isim" olarak
    düz metne çeviriyoruz. Standart XML entity'leri (&amp; vb.) dokunulmadan
    kalıyor.

    apt'nin entity adları systemd'den daha karmaşık - nokta/tire
    içerebiliyor (ör. &apt-author.jgunthorpe;, &synopsis-command-apt-get;)
    - entity adı deseni bunu da kapsayacak şekilde genişletildi."""
    text = re.sub(r"<!DOCTYPE[^>]*\[.*?\]>", "", text, flags=re.DOTALL)
    text = re.sub(
        r"&(?!amp;|lt;|gt;|quot;|apos;|#)([\w][\w.-]*);", r"\1", text
    )
    return text


def parse_systemd_xml(doc):
    text = preprocess_docbook_xml(doc["text"])
    root = ET.fromstring(text)

    refname_el = root.find(".//refname")
    command_name = (refname_el.text or "").strip() if refname_el is not None else doc["name"]

    if not command_name:
        raise ValueError("systemd-docbook-xml: refname bulunamadı")

    purpose_el = root.find(".//refpurpose")
    title = docbook_text(purpose_el).strip() if purpose_el is not None else command_name

    description = ""

    for refsect1 in root.iter("refsect1"):
        title_el = refsect1.find("title")

        if title_el is not None and (title_el.text or "").strip() == "Description":
            first_para = refsect1.find("para")

            if first_para is not None:
                description = docbook_text(first_para).strip()

            break

    if not description:
        description = title

    # systemctl gibi araçlarda "Commands" bölümü alt komutları listeler
    # (docker'ın "Subcommands" tablosuna denk gelen kısım) - kısa bir özet
    # cümlesi olarak açıklamaya eklenmesinin YANI SIRA, her alt komutun
    # kendi açıklaması da "parametre" gibi ayrı bir soru-cevap kaydı
    # üretebilsin diye subcommands listesine toplanıyor. Önceden sadece
    # isimler özet cümlesine ekleniyor, kendi açıklamaları hiç
    # kaydedilmiyordu - "systemd-analyze blame ne yapar?" gibi sorular bu
    # yüzden hiçbir zaman doğru cevap bulamıyordu (flag/varname olmadıkları
    # için parametre listesinden bilerek dışlanıyorlardı, ama yerine hiçbir
    # şey konmamıştı).
    command_names = []
    subcommands = []

    for refsect1 in root.iter("refsect1"):
        title_el = refsect1.find("title")

        if title_el is not None and (title_el.text or "").strip() == "Commands":
            # SADECE <term> içindeki <command> gerçek bir alt komut adı -
            # <listitem><para> içindeki düz metinde de biçimlendirme için
            # <command> kullanılıyor (ör. "systemd currently has..." cümlesi
            # içinde), bunlar refsect1.iter("command") ile yanlışlıkla
            # alt komut sanılıp listeye karışıyordu.
            for entry in refsect1.iter("varlistentry"):
                entry_names = []

                for term in entry.findall("term"):
                    term_command = term.find("command")
                    name = (term_command.text or "").strip() if term_command is not None else ""

                    if name and name not in command_names:
                        command_names.append(name)

                    if name and name not in entry_names:
                        entry_names.append(name)

                listitem = entry.find("listitem")
                first_para = listitem.find("para") if listitem is not None else None
                sub_description = docbook_text(first_para).strip() if first_para is not None else ""

                if entry_names and len(sub_description) >= 10:
                    for entry_name in entry_names:
                        subcommands.append({
                            "name": entry_name,
                            "description": sub_description
                        })

            break

    if command_names:
        description = (
            description + " Commands: " + ", ".join(command_names[:25]) + "."
        ).strip()

    # systemd-analyze gibi bazı sayfalarda alt komutlar hiç "Commands"
    # varlistentry'si kullanmıyor - her biri kendi <refsect2>'sinde,
    # başlığı tam çağrı biçimini içeren bir <command> olarak dokümante
    # ediliyor (ör. "<title><command>systemd-analyze blame</command></title>").
    # Başlık, komutun kendi adıyla başlıyorsa (biçimlendirme etiketleri
    # temizlendikten sonra) gerçek bir alt komut kabul ediliyor; ilk
    # kelimesi alt komutun adı, refsect2'nin ilk doğrudan <para>'sı da
    # açıklaması oluyor.
    existing_subcommand_names = {s["name"] for s in subcommands}

    for refsect2 in root.iter("refsect2"):
        title_el = refsect2.find("title")

        if title_el is None:
            continue

        title_command_el = title_el.find("command")

        if title_command_el is None:
            continue

        title_command_text = docbook_text(title_command_el).strip()
        prefix = command_name + " "

        if not title_command_text.startswith(prefix):
            continue

        remainder = title_command_text[len(prefix):].strip()
        sub_name = remainder.split()[0] if remainder else ""

        if not sub_name or not re.match(r"^[A-Za-z0-9][\w-]*$", sub_name):
            continue

        first_para = refsect2.find("para")
        sub_description = docbook_text(first_para).strip() if first_para is not None else ""

        if sub_name in existing_subcommand_names or len(sub_description) < 10:
            continue

        subcommands.append({"name": sub_name, "description": sub_description})
        existing_subcommand_names.add(sub_name)

    # nftables gibi kaynaklarda bazı ek komutlar (describe/export/monitor)
    # yukarıdaki "systemd-analyze blame" tarzı <command> etiketli başlığı
    # HİÇ kullanmıyor - iki farklı, daha zayıf işaretli örüntü var: (1)
    # başlığı SADECE "X command" olan bir refsect2 (ör. "describe
    # command"), (2) üst refsect1'i tam olarak "Additional commands"
    # başlıklı bir bölümün İÇİNDEKİ salt sözcük başlıklı refsect2'ler (ör.
    # "export", "monitor"). Yanlış eşleşmeyi önlemek için HER İKİSİ de dar
    # kapsamlı tutuluyor: ilki sadece " command" son ekiyle biten İKİ
    # kelimelik başlıklarla, ikincisi sadece üst bölüm başlığı birebir
    # "Additional commands" olduğunda tetikleniyor - başka bir refsect1
    # içindeki alakasız salt sözcük başlıkları (ör. "Queue statement" gibi
    # bir kural ifadesi, komut değil) bu yüzden hiç etkilenmiyor.
    for refsect1 in root.iter("refsect1"):
        refsect1_title_el = refsect1.find("title")
        refsect1_title_text = (
            (refsect1_title_el.text or "").strip()
            if refsect1_title_el is not None else ""
        )

        for refsect2 in refsect1.findall("refsect2"):
            title_el = refsect2.find("title")

            if title_el is None or title_el.find("command") is not None:
                continue

            title_text = docbook_text(title_el).strip()
            title_words = title_text.split()
            sub_name = None

            if len(title_words) == 2 and title_words[1] == "command":
                sub_name = title_words[0]
            elif (
                refsect1_title_text == "Additional commands"
                and re.match(r"^[A-Za-z][\w-]*$", title_text)
            ):
                sub_name = title_text

            if not sub_name or sub_name in existing_subcommand_names:
                continue

            # nft'nin "describe command" gibi bölümlerinde İLK <para>
            # sadece <cmdsynopsis>'i sarmalıyor ("describe expression" gibi
            # anlamsız, çıplak bir söz dizimi metni) - asıl açıklama İKİNCİ
            # <para>'da. Sadece <cmdsynopsis> içeren para'lar atlanıp asıl
            # metin taşıyan İLK para alınıyor.
            sub_description = ""

            for para in refsect2.findall("para"):
                if para.find("cmdsynopsis") is not None and len(list(para)) == 1:
                    continue

                sub_description = docbook_text(para).strip()

                if sub_description:
                    break

            if len(sub_description) < 10:
                continue

            subcommands.append({"name": sub_name, "description": sub_description})
            existing_subcommand_names.add(sub_name)

    # CLI aracı ise (systemctl, journalctl...) <cmdsynopsis> var; unit dosyası
    # direktif referansı ise (systemd.service gibi) yok - o durumda syntax
    # boş kalıyor (ls'in kendi Synopsis örneği olmadığında olduğu gibi).
    cmdsynopsis = root.find(".//cmdsynopsis")
    is_cli_tool = cmdsynopsis is not None
    syntax = wrap_code_block(f"{command_name} [OPTIONS]") if is_cli_tool else ""

    # "Options" başlıklı TÜM refsect1'lerin İÇİNDEKİ (iç içe olsa bile)
    # varlistentry'ler toplanıyor - bazı sayfalarda ([Service] Section
    # Options gibi) tek bir büyük Options bölümü var, iç içe alt başlık yok.
    parameters = []

    # systemd'nin bölüm başlıkları hiç tutarlı değil - bazı sayfalarda düz
    # "Options", bazılarında "[Unit] Section Options", journalctl'de "Source
    # Options"/"Filtering Options"/"Output Options" gibi 5 ayrı başlık,
    # systemd.exec'te ise "Paths"/"Sandboxing"/"Scheduling" gibi "Options"
    # kelimesi hiç geçmeyen tamamen tematik başlıklar var. Başlık metnine
    # güvenmek yerine TÜM belgedeki her varlistentry taranıyor; bir entry
    # SADECE <term> içinde <option> ya da <varname> varsa (yani gerçekten
    # bir flag/direktifse) parametre sayılıyor - <command> içeren
    # varlistentry'ler (ör. systemctl'in "Commands" bölümündeki alt
    # komutlar) otomatik elenir, çünkü flags listesi boş kalır.
    #
    # nftables'ta (nft.xml) "add"/"delete"/"list"/"flush" gibi bayrak-suz
    # eylem kelimeleri table/chain/rule gibi FARKLI nesne tipleri için AYNI
    # isimle tekrar tekrar tanımlanıyor (üçü de "add" - biri tabloya, biri
    # zincire, biri kurala ekleme anlamında). Bunu ayırt edebilecek tek
    # bağlam, o varlistentry'den önceki en yakın <cmdsynopsis>'in <command>
    # öğesi (ör. "table"/"chain") - ama bu bağlam SADECE gerçekten çakışan
    # terimler için güvenilir: bazı variablelist'lerin (adres ailesi listesi,
    # verdict ifadeleri gibi) kendi önlerinde hiç cmdsynopsis yok, bu yüzden
    # "en yakın önceki" belgenin çok daha önceki, alakasız bir bölümünden
    # kalma bir bağlamı miras alıyor (ör. "accept"/"drop" verdict'leri
    # yanlışlıkla "ct" ile, "ip"/"ip6" adres aileleri hatalı bir şablon
    # kalıntısıyla nitelenmeye çalışıyordu). Bu yüzden İKİ geçişli:
    # önce TÜM ham (nitelemesiz) isimler + bağlamlarıyla toplanıyor, SADECE
    # aynı ham isim belgede birden fazla kez FARKLI açıklamayla geçiyorsa
    # (gerçek bir çakışma varsa) o isimler bağlamla nitelendiriliyor -
    # aksi halde bayrak adı hiç dokunulmadan bırakılıyor.
    current_object_type = None
    raw_entries = []

    for element in root.iter():
        tag = strip_ns(element.tag)

        if tag == "cmdsynopsis":
            command_el = element.find("command")

            if command_el is not None:
                current_object_type = docbook_text(command_el).strip()

            continue

        if tag != "varlistentry":
            continue

        entry = element
        flags = []

        for term in entry.findall("term"):
            option_el = term.find("option")
            varname_el = term.find("varname")
            flag_el = option_el if option_el is not None else varname_el
            flag_text = docbook_text(flag_el).strip() if flag_el is not None else ""

            if not flag_text:
                continue

            # systemd her alias için AYRI bir <term> kullanırken (ör.
            # "-u" ve "--unit=" iki ayrı <term>), nftables'ın nft.xml'i
            # kısa/uzun formu TEK bir <option> içinde "/" ile birleştirip
            # yazıyor (ör. "-h/--help", "-n/--numeric"). "/" varsa ayrı
            # flag'lere bölünüyor - systemd'nin 16 dosyasının hiçbirinde
            # gerçek bir <term> içinde "/" geçmediği doğrulandı, bu yüzden
            # bu genelleme systemd için güvenli/etkisiz.
            if "/" in flag_text:
                flags.extend(part for part in flag_text.split("/") if part)
            else:
                flags.append(flag_text)

        listitem = entry.find("listitem")
        first_para = listitem.find("para") if listitem is not None else None
        param_description = docbook_text(first_para).strip() if first_para is not None else ""

        if not flags or len(param_description) < 10:
            continue

        for flag in flags:
            raw_entries.append((flag, param_description, current_object_type))

    # UYARI: bu iki döngü ÖNCEDEN "description" adlı bir döngü değişkeni
    # kullanıyordu - fonksiyonun en üstünde Description bölümünden
    # hesaplanan ASIL komut açıklamasıyla AYNI isim, Python'da blok kapsamı
    # olmadığı için döngü bittiğinde dıştaki "description" son işlenen
    # parametrenin açıklamasıyla SESSİZCE eziliyordu - "networkctl ne
    # yapar?" gibi üst seviye bir soru, gerçek "networkctl may be used to
    # query..." yerine son parametrenin (ör. "--stdin") açıklamasını
    # döndürüyordu. Bu, parametresi olan HER DocBook komutunu (apt/systemd/
    # nftables ailesinin tamamı) etkileyen, sessiz bir veri bozulmasıydı -
    # parametre kayıtlarının kendisi etkilenmiyordu (her turda doğru flag'e
    # taze bağlanıyordu), sadece üst seviye "description" kategorisi
    # bozuluyordu. Fark edilmemesinin sebebi: önceki denetim turları hep
    # ALT KOMUTLARI ("systemctl reload ne yapar?") sordu, komutun KENDİSİNİ
    # ("systemctl ne yapar?") neredeyse hiç sormadı.
    descriptions_by_flag: dict[str, set[str]] = {}

    for flag, flag_description, _ in raw_entries:
        descriptions_by_flag.setdefault(flag, set()).add(flag_description)

    for flag, flag_description, object_type in raw_entries:
        name = flag

        if (
            len(descriptions_by_flag.get(flag, ())) > 1
            and object_type
            and not flag.startswith("-")
            and object_type not in flag.split()
        ):
            name = f"{flag} {object_type}"

        parameters.append({"name": name, "description": flag_description})

    existing_parameter_names = {p["name"] for p in parameters}

    for subcommand in subcommands:
        if subcommand["name"] not in existing_parameter_names:
            parameters.append(subcommand)
            existing_parameter_names.add(subcommand["name"])

    example_text = ""

    for refsect1 in root.iter("refsect1"):
        title_el = refsect1.find("title")

        if title_el is not None and (title_el.text or "").strip() == "Examples":
            listing = refsect1.find(".//programlisting")

            if listing is not None:
                example_text = docbook_text(listing).strip()

            break

    examples = wrap_code_block(example_text) if example_text else ""

    if not description and not parameters:
        raise ValueError("systemd-docbook-xml: tanınabilir içerik bulunamadı")

    intents = []

    if len(title) >= 10:
        intents.append({
            "phrase": title,
            "mood": "declarative",
            "command_hint": command_name
        })

    return title, command_name, description, "", syntax, examples, parameters, intents


# ---------------------------------------------------------------------------
# Klasik troff/man sayfası makroları (.TH/.SH/.TP/.B/.I/\fB.../\fP) - cron,
# iptables, ufw gibi araçların resmi kılavuzları hâlâ bu formatta. DocBook/
# Markdown/Texinfo'dan farklı olarak flag adı iki farklı şekilde yazılabiliyor:
# crontab tarzı ayrı ".B "flag"" makro satırı, ya da iptables/ufw tarzı düz
# metin içinde gömülü "\fB-flag\fP" kaçış dizisi. İkisi de destekleniyor.
# ---------------------------------------------------------------------------

def troff_clean_line(line: str) -> str:
    line = line.rstrip()

    if line.startswith('.\\"'):
        return ""

    if line.startswith("."):
        parts = line.split(None, 1)
        macro = parts[0][1:]
        rest = parts[1] if len(parts) > 1 else ""

        if macro in (
            "PP", "br", "nf", "fi", "TP", "sp", "in", "RS", "RE",
            "SH", "SS", "TH", "MT", "ME"
        ):
            return ""

        if macro in ("B", "I", "BR", "IR", "RB", "RI", "BI", "IB"):
            line = rest
        else:
            return ""

    line = (
        line.replace("\\-", "-").replace("\\ ", " ").replace("\\&", "")
        .replace("\\(em", "-")
    )
    line = (
        line.replace("\\fB", "").replace("\\fI", "")
        .replace("\\fR", "").replace("\\fP", "")
    )
    line = re.sub(r'"([^"]*)"', r"\1", line)

    return line.strip()


def extract_troff_flag_names(line: str):
    stripped = line.strip()

    if re.match(r"^\.(B|BR|BI)\b", stripped):
        cleaned = troff_clean_line(line)
        return [cleaned] if cleaned and re.search(r"[A-Za-z0-9]", cleaned) else []

    # iptables/ufw tarzı: flag adı ".TP" sonrası düz metin satırında
    # \fB...\fP/\fR kaçışlarıyla gömülü (birden fazla olabilir, ör.
    # "-h, --help"). Sadece harf/rakam İÇERMEYEN eşleşmeler (ör. koşullu
    # negasyon göstergesi "[\fB!\fP]", ya da "address[/mask]" gösterimindeki
    # "\fB/\fP") gerçek bir flag değil, eleniyor.
    bold_matches = re.findall(r"\\fB(.*?)\\f[PR]", line)
    flags = []

    for match in bold_matches:
        match = match.replace("\\-", "-").strip()

        if match and re.search(r"[A-Za-z0-9]", match):
            flags.append(match)

    return flags


def extract_troff_sections(text: str):
    sections = {}
    current_title = None
    current_lines: list[str] = []

    for line in text.split("\n"):
        match = re.match(r'^\.SH\s+"?([^"]*)"?\s*$', line)

        if match:
            if current_title:
                sections[current_title] = "\n".join(current_lines)

            current_title = match.group(1).strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_title:
        sections[current_title] = "\n".join(current_lines)

    return sections


def extract_troff_options(section_text: str):
    """".TP" ile başlayan her blok bir flag tanımı. ".RS"/".RE" (girinti
    başlangıç/bitiş) derinliği takip ediliyor - iptables gibi kaynaklarda bir
    flag'in kendi açıklaması İÇİNDE örnek göstermek için iç içe ".TP" listesi
    olabiliyor (coreutils'teki nested @table sorununun troff karşılığı); bu
    iç listeler yeni bir üst-düzey flag değil, üstteki flag'in açıklamasının
    bir parçası sayılıyor (derinlik > 0 iken)."""
    parameters = []
    depth = 0
    current_flags: list[str] = []
    current_description_lines: list[str] = []

    def flush():
        if not current_flags:
            return

        description = " ".join(l for l in current_description_lines if l).strip()
        description = re.sub(r"\s+", " ", description)

        if len(description) < 10:
            return

        for flag in current_flags:
            parameters.append({"name": flag, "description": description})

    lines = section_text.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith(".RS"):
            depth += 1
            i += 1
            continue

        if stripped.startswith(".RE"):
            depth = max(0, depth - 1)
            i += 1
            continue

        if re.match(r"^\.TP\b", stripped):
            if depth == 0:
                flush()
                current_flags = []
                current_description_lines = []
                i += 1

                while i < len(lines) and lines[i].strip() == "":
                    i += 1

                if i < len(lines):
                    if re.match(r"^\.(B|BR|BI)\b", lines[i].strip()):
                        while i < len(lines) and re.match(r"^\.(B|BR|BI)\b", lines[i].strip()):
                            current_flags.extend(extract_troff_flag_names(lines[i]))
                            i += 1
                    else:
                        current_flags.extend(extract_troff_flag_names(lines[i]))
                        i += 1

                continue
            else:
                cleaned = troff_clean_line(line)

                if cleaned and current_flags:
                    current_description_lines.append(cleaned)

                i += 1
                continue

        cleaned = troff_clean_line(line)

        if cleaned and current_flags:
            current_description_lines.append(cleaned)

        i += 1

    flush()

    return parameters


def parse_troff_man(doc):
    text = doc["text"]

    # Dosya adından komut adı: "crontab.1" -> "crontab", "iptables.8.in"
    # (autoconf .in şablonu) -> "iptables" (hem .in hem bölüm numarası
    # ayrıca kesiliyor, pathlib .stem sadece SON uzantıyı keser).
    command_name = re.sub(r"\.\d[a-z]?(\.in)?$", "", doc["name"])
    command_name = re.sub(r"\.in$", "", command_name)

    title_match = re.search(
        r"^\.SH\s+NAME\s*\n(.+?)$", text, re.MULTILINE
    )
    title = troff_clean_line(title_match.group(1)) if title_match else command_name

    if " - " in title:
        title = title.split(" - ", 1)[-1].strip()
    elif " — " in title:
        title = title.split(" — ", 1)[-1].strip()

    sections = extract_troff_sections(text)

    # Troff'ta bir cümle kelime kelime İTALİK/KALIN makrolara bölünebiliyor
    # (ör. "A\n.I crontab\nfile contains instructions..." - üç ayrı satır,
    # tek bir cümle). Sadece İLK satırı almak "A" gibi anlamsız tek
    # kelimelik bir açıklama üretiyordu - ilk paragrafın SONUNA kadar tüm
    # satırlar birleştiriliyor. Paragraf sonu boş satır OLMAYABİLİR - çoğu
    # man sayfası paragraflar arasında ".PP" makrosu kullanıyor (boş satır
    # değil), bu yüzden ikisi de durma sinyali sayılıyor - aksi halde
    # ".PP" ile ayrılmış TÜM bölüm (bazı dosyalarda 8000+ karakter) tek
    # "açıklama" sanılıyordu.
    description_text = sections.get("DESCRIPTION", "")
    description_lines: list[str] = []

    for line in description_text.split("\n"):
        stripped = line.strip()

        if (stripped == "" or stripped.startswith(".PP")) and description_lines:
            break

        cleaned = troff_clean_line(line)

        if cleaned:
            description_lines.append(cleaned)

    description = re.sub(r"\s+", " ", " ".join(description_lines)).strip()

    options_text = sections.get("OPTIONS", "")
    parameters = extract_troff_options(options_text)

    if not description and not parameters:
        raise ValueError("troff-man: tanınabilir içerik bulunamadı")

    intents = []

    if len(title) >= 10:
        intents.append({
            "phrase": title,
            "mood": "declarative",
            "command_hint": command_name
        })

    return title, command_name, description, "", "", "", parameters, intents


# ---------------------------------------------------------------------------
# iptables'ın match/target UZANTI belgeleri (extensions/*.man) - `--dport`/
# `--sport`/`--tcp-flags`/`--syn` gibi çok yaygın sorulan bayraklar buradan
# geliyor, ana `iptables.8.in`'de HİÇ yok (sadece "-p tcp kullanılırsa bu
# bayraklar da kullanılabilir" diye üstünkörü bahsediliyor). Bu 94 dosya
# bilinçli olarak dışarıda bırakılmıştı (bkz. config.py'deki eski not) -
# gerekçe "gerçek içerik extensions/*.man'de ve @TARGET@/@MATCH@ include-
# marker'larıyla build zamanında birleştiriliyor, ayrı bir parser gerekir"
# idi. Bu doğru ama eksik bir gerekçeydi: birleştirilen PARÇALARIN HER
# BİRİ zaten kendi başına geçerli, tam bir troff `.TP` bloklar dizisi -
# @TARGET@/@MATCH@ mekanizmasını hiç çözmeye gerek yok, her dosya
# extract_troff_options'a doğrudan (bölüm başlığı aramadan, çünkü bu
# parça dosyalarda hiç `.SH` yok) verilebiliyor.
#
# Üç dosya adı öneki farklı hedef komutlara ait: `libxt_*` (iptables VE
# ip6tables'ın PAYLAŞTIĞI uzantılar, ör. tcp/udp/state/limit) ve
# `libipt_*` (sadece IPv4/iptables'a özgü, ör. MASQUERADE) ikisi de
# `iptables`'a; `libip6t_*` (sadece IPv6/ip6tables'a özgü) `ip6tables`'a
# ekleniyor.
def parse_iptables_extension_man(doc):
    filename = doc["name"]

    if filename.startswith("libip6t_"):
        command_name = "ip6tables"
    else:
        command_name = "iptables"

    parameters = extract_troff_options(doc["text"])

    if not parameters:
        raise ValueError("iptables-extension-man: tanınabilir içerik bulunamadı")

    return "", command_name, "", "", "", "", parameters, []


# ---------------------------------------------------------------------------
# BSD mdoc makroları (.Sh/.Nm/.Nd/.Bl/.It Fl/.Ar/.Xr...) - ssh/OpenSSH'ın
# kendi kılavuzları bu formatta. GNU troff/man'in .TH/.SH/.TP/.B kalıbından
# TAMAMEN farklı bir makro sözlüğü kullanıyor, yukarıdaki troff-man parser'ı
# burada hiç işe yaramıyor - ayrı bir parser gerekti.
# ---------------------------------------------------------------------------

MDOC_MACRO_NAMES = {
    "Pp", "Sh", "Ss", "Dd", "Dt", "Os", "Bl", "El", "It", "Sm", "Bd", "Ed",
    "Bk", "Ek", "Nm", "Nd", "Ar", "Cm", "Ic", "Pa", "Ev", "Va", "Em", "No",
    "Ux", "Bx", "Dq", "Sq", "Op", "Oo", "Oc", "Sy", "In", "Li", "Fa", "Ft",
    "Fn", "Dv", "Ns", "Xo", "Xc", "Xr", "Fl", "An", "Aq", "Bq", "Brq", "Pq",
    "Fx", "Nx", "Ox", "Bt", "Ud", "Lk", "Mt", "off", "on", "Ql",
}

MDOC_STRUCTURAL_ONLY = {
    "Pp", "Sh", "Ss", "Dd", "Dt", "Os", "Bl", "El", "It", "Bk", "Ek"
}


def mdoc_clean_line(line: str) -> str:
    line = line.rstrip()

    if line.startswith('.\\"') or line.startswith("'"):
        return ""

    # mdoc/troff kaçış dizileri - bazılarının hiç görsel karşılığı yok
    # ("\&" bir sonraki karakterin makro/noktalama olarak yanlış
    # yorumlanmasını önleyen görünmez işaret, "\%" bir heceleme ipucu),
    # bazılarının düz bir karşılığı var ("\-" gerçek bir tire, "\e"
    # geçerli kaçış karakterinin kendisi yani ters eğik çizgi, "\ "
    # satır sonunda bölünmeyen boşluk). Hepsi hem makro satırlarında
    # hem düz metinde koşulsuz uygulanıyor - hiçbiri İngilizce kelime
    # ile çakışma riski taşımıyor ("on"/"An" makro-adı çakışmasından
    # farklı olarak, bunlar gerçek metin karakteri değil.
    line = line.replace("\\&", "").replace("\\%", "")
    line = line.replace("\\-", "-").replace("\\e", "\\").replace("\\ ", " ")
    line = line.replace("\\(em", "-").replace("\\(en", "-")
    line = line.replace("\\*(Lt", "<").replace("\\*(Gt", ">")
    line = line.replace("\\*(Ge", ">=").replace("\\*(Le", "<=")

    # Düz metin (mdoc makro satırı değil) hiç dokunulmadan bırakılıyor -
    # aksi halde "on"/"An" gibi bazı makro adları sıradan İngilizce
    # kelimelerle çakışıp normal cümlelerden siliniyordu ("specified on a
    # per-host basis" -> "specified a per-host basis" gibi anlam bozan
    # bir hataya yol açıyordu). Makro-adı çakışması SADECE gerçek makro
    # satırlarında (başında "." olan) bir tehlike.
    if not line.startswith("."):
        return line.strip()

    tokens = line.split()
    macro = tokens[0][1:]
    tokens = tokens[1:]

    if macro in MDOC_STRUCTURAL_ONLY:
        return ""

    # Kalan token'lardan, kendisi de bilinen bir makro adıyla eşleşenler
    # atılıyor - tek satırda iç içe makro kompozisyonu olabiliyor (ör.
    # ".Oo Ar bind_address : Oc" - "Ar"/"Oo"/"Oc" birer makro çağrısı,
    # sadece "bind_address" ve ":" gerçek metin).
    kept = [t for t in tokens if t not in MDOC_MACRO_NAMES]
    kept = [t.rstrip(",") for t in kept if t]
    text = " ".join(kept)

    if macro == "Fl" and text:
        text = "-" + text

    return text.strip()


def mdoc_item_name(it_line: str):
    """".It Fl X" -> "-X" (CLI flag). ".It Cm Name" -> "Name" (ssh_config
    gibi config dosyalarının direktifleri - tire almaz). ".It Ic Name" ->
    "Name" (sftp gibi etkileşimli kabuk komutları)."""
    tokens = it_line.split()[1:]

    if len(tokens) < 2:
        return None

    marker, name = tokens[0], tokens[1]

    # mdoc kaynağı bazen isme kaçış öneki ekliyor (ör. sftp'nin "!" ve
    # "?" etkileşimli komutları ".It Ic \&! .../.It Ic \&?" şeklinde
    # yazılmış - "\&" makro işlemcisinin baştaki noktalamayı yanlış
    # yorumlamasını önleyen görünmez bir işaret, isme dahil değil).
    name = name.replace("\\&", "")

    if marker == "Fl":
        return "-" + name

    if marker in ("Cm", "Ic"):
        return name

    return None


def extract_mdoc_options(text: str):
    """".Bl"/".El" (liste aç/kapa) derinliği takip ediliyor - troff'un
    nested @table/.TP sorunuyla aynı sınıf: ssh.1'de bir flag'in kendi
    açıklaması içinde ayrı bir iç liste olabiliyor, bunlar yeni bir
    üst-düzey flag değil. Ayrıca aynı flag arka arkaya birden fazla ".It"
    ile farklı sözdizim varyantlarını gösterebiliyor (ssh'ın -L'si 4 farklı
    argüman kalıbını 4 ayrı ".It Fl L" olarak listeleyip gerçek açıklamayı
    sadece SONUNCUSUNDAN sonra bir kere yazıyor) - flag değişmediyse
    flush ETMEDEN devam ediliyor."""
    parameters = []
    depth = 0
    current_flags: list[str] = []
    current_description_lines: list[str] = []

    def flush():
        if not current_flags:
            return

        description = " ".join(l for l in current_description_lines if l).strip()
        description = re.sub(r"\s+", " ", description)

        if len(description) < 10:
            return

        for flag in current_flags:
            parameters.append({"name": flag, "description": description})

    lines = text.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith(".Bl"):
            depth += 1
            i += 1
            continue

        if stripped.startswith(".El"):
            depth = max(0, depth - 1)

            # En dıştaki liste kapandığında (depth 1 -> 0) açık kalan
            # girişi kapatmak ŞART - aksi halde bu dosyanın son listesiyse,
            # SEE ALSO/kaynakça gibi listeyle hiç ilgisi olmayan sonraki
            # TÜM içerik son maddenin açıklamasına sızmaya devam ederdi
            # (sftp'nin son komutu "?" de tam olarak bu oldu - kaynakça
            # metni onun açıklamasına eklenmişti).
            if depth == 0:
                flush()
                current_flags = []
                current_description_lines = []

            i += 1
            continue

        if stripped.startswith(".It"):
            item_name = mdoc_item_name(stripped)

            if item_name and depth == 1:
                if current_flags != [item_name]:
                    flush()
                    current_flags = [item_name]
                    current_description_lines = []
            elif current_flags:
                cleaned = mdoc_clean_line(line)

                if cleaned:
                    current_description_lines.append(cleaned)

            i += 1
            continue

        cleaned = mdoc_clean_line(line)

        if cleaned and current_flags:
            current_description_lines.append(cleaned)

        i += 1

    flush()

    return parameters


def parse_mdoc_man(doc):
    text = doc["text"]

    command_name = re.sub(r"\.\d[a-z]?$", "", doc["name"])

    nd_match = re.search(r"^\.Nd\s+(.+)$", text, re.MULTILINE)
    title = mdoc_clean_line(nd_match.group(0)) if nd_match else command_name

    # ".Sh DESCRIPTION"in ilk paragrafı - ".Pp" ya da bir sonraki ".Sh"a
    # kadar. ssh.1 gibi bazı kılavuzlarda flag'ler ayrı bir OPTIONS
    # bölümünde değil, DESCRIPTION'ın İÇİNDE ".Bl -tag" ile geliyor - bu
    # yüzden description'ı SADECE ilk paragrafla sınırlamak (aşağıda),
    # parametre taramasını (extract_mdoc_options) ise TÜM belge üzerinde
    # çalıştırmak gerekiyor.
    desc_match = re.search(
        r"^\.Sh DESCRIPTION\s*\n(.*?)(?=^\.Sh |\Z)", text, re.DOTALL | re.MULTILINE
    )
    description_lines: list[str] = []

    if desc_match:
        for line in desc_match.group(1).split("\n"):
            stripped = line.strip()

            if (stripped == "" or stripped.startswith(".Pp")) and description_lines:
                break

            cleaned = mdoc_clean_line(line)

            if cleaned:
                description_lines.append(cleaned)

    description = re.sub(r"\s+", " ", " ".join(description_lines)).strip()

    parameters = extract_mdoc_options(text)

    if not description and not parameters:
        raise ValueError("mdoc-man: tanınabilir içerik bulunamadı")

    intents = []

    if len(title) >= 10:
        intents.append({
            "phrase": title,
            "mood": "declarative",
            "command_hint": command_name
        })

    return title, command_name, description, "", "", "", parameters, intents


# ---------------------------------------------------------------------------
# reStructuredText "tanım listesi" biçimi - dnf'in kendi kılavuzu
# (command_ref.rst/conf_ref.rst) bu formatta: çift ters tırnak içinde bir
# terim satırı (ör. "``-b, --best``" ya da tiresiz bir config direktifi
# "``cachedir``"), ardından 4 boşluk girintili bir açıklama bloğu.
# ---------------------------------------------------------------------------

def clean_rst_text(text: str) -> str:
    text = re.sub(r":ref:`([^<`]+?)(?:\s*<[^>]+>)?`", r"\1", text)
    text = re.sub(r"``([^`]+)``", r"\1", text)
    # RST'nin tek ters tırnaklı referans/link sözdizimi (ör. "`DNF`_",
    # "`YUM`_") - çift ters tırnaklı kod biçimlendirmesinden FARKLI, ayrıca
    # temizlenmesi gerekiyor.
    text = re.sub(r"`([^`]+)`_", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = text.replace("\\", "")
    return text


def parse_rst_options(text: str):
    parameters = []
    lines = text.split("\n")
    i = 0
    current_flags: list[str] = []
    current_description_lines: list[str] = []

    def flush():
        if not current_flags:
            return

        description = " ".join(
            l.strip() for l in current_description_lines if l.strip()
        )
        description = clean_rst_text(description)
        description = re.sub(r"\s+", " ", description).strip()

        if len(description) < 10:
            return

        for flag in current_flags:
            parameters.append({"name": flag, "description": description})

    term_pattern = re.compile(r"^``(.+)``\s*$")

    while i < len(lines):
        line = lines[i]

        if line and not line[0].isspace():
            match = term_pattern.match(line.strip())
            term_text = match.group(1).strip() if match else None

            is_flag_term = bool(term_text and term_text.startswith("-"))
            # conf_ref.rst gibi dosyalarda terim tiresiz, düz bir config
            # direktifi adı oluyor (ör. "allow_vendor_change", "cachedir") -
            # bunlar da gerçek bir "parametre" sayılmalı; "dnf alias
            # [options] [list] [<name>...]" gibi kullanım örnekleri (boşluk/
            # köşeli parantez içerdiği için) elenir.
            is_bare_identifier = bool(
                term_text and re.match(r"^[A-Za-z_][\w.]*$", term_text)
            )

            if is_flag_term or is_bare_identifier:
                flush()
                current_flags = []

                if is_bare_identifier:
                    current_flags = [term_text]
                else:
                    for piece in term_text.split(","):
                        piece = piece.strip().split("=")[0].split(" ")[0]

                        # ör. "--whatdepends <capability>[,<capability>...]"
                        # - flag'in KENDİ argüman gösterimindeki virgül,
                        # çoklu-alias ayracıyla karışmasın diye sadece "-"
                        # ile başlayan parçalar gerçek alias sayılıyor.
                        if piece.startswith("-"):
                            current_flags.append(piece)

                current_description_lines = []
                i += 1
                continue
            else:
                if current_flags:
                    flush()
                    current_flags = []
                    current_description_lines = []

                i += 1
                continue

        if current_flags:
            current_description_lines.append(line)

        i += 1

    flush()

    return parameters


# dnf-docs'ta sadece bu iki dosya alınıyor (config.py'de allowed_names ile
# kısıtlı) - komut adları dosya adından türetilemeyeceği için (command_ref
# -> "dnf" komutunun tamamı, conf_ref -> dnf.conf yapılandırma dosyası)
# elle eşleniyor.
RST_FILE_TO_COMMAND = {
    "command_ref": "dnf",
    "conf_ref": "dnf.conf",
}


def parse_dnf_command_reference(text: str):
    """command_ref.rst'nin "Commands" bölümü (`install`, `remove`,
    `search`, `list`, `clean`... - dnf'in asıl alt komutları) `parse_rst_options`'ın
    hedeflediği "``term``" + girintili paragraf biçiminden TAMAMEN farklı bir
    yapı kullanıyor: her komut "| Command: ``install``" gibi bir metadata
    satırıyla başlıyor, ardından gerçek çağrı sözdizimi kendi başına bir
    satırda "``dnf [options] install <spec>...``" şeklinde, açıklaması da
    onun altında girintili. `parse_rst_options` sadece tire ile başlayan ya
    da çıplak tek-kelimelik terimleri tanıdığı için bu satırları (boşluk/
    köşeli parantez içerdikleri için) sessizce atlıyordu - "dnf install",
    "dnf remove", "dnf search", "dnf list" gibi en temel 28 komutun hiçbiri
    veri setinde yoktu."""
    parameters = []

    section_match = re.search(
        r"^={3,}\nCommands\n={3,}\n(.*?)(?=\n={3,}\n\S)",
        text,
        re.MULTILINE | re.DOTALL
    )

    if not section_match:
        return parameters

    section_text = section_match.group(1)

    command_anchor_pattern = re.compile(r"^\| Command:\s*``([^`]+)``\s*$", re.MULTILINE)
    anchors = list(command_anchor_pattern.finditer(section_text))

    syntax_line_pattern = re.compile(r"^``(dnf[^`]*)``\s*$")
    # "dnf [options] install <spec>..." -> "install" ; "dnf clean dbcache" ->
    # "clean dbcache" ; "dnf [options] search [--all] <keywords>..." ->
    # "search" (ilk köşeli parantez/açı parantezinde durur, o noktadan sonrası
    # bir bayrak ya da yer tutucu argüman, komut adının parçası değil).
    compound_name_pattern = re.compile(
        r"^dnf\s+(?:\[[^\]]*\]\s*)*([A-Za-z][\w-]*(?:\s+[A-Za-z][\w-]*)*)"
    )

    for index, anchor in enumerate(anchors):
        base_name = anchor.group(1).strip()
        block_start = anchor.end()
        block_end = anchors[index + 1].start() if index + 1 < len(anchors) else len(section_text)
        block_lines = section_text[block_start:block_end].split("\n")

        i = 0

        # Metadata satırlarını atla ("| Aliases: ...", "| Deprecated aliases: ...").
        # "anchor.end()" satır sonundaki "\n"dan HEMEN önce durduğu için
        # block_lines[0] boş bir kalıntı oluyor - bu yüzden boş satırlar ve
        # "|" ile başlayan satırlar TEK bir döngüde birlikte atlanıyor,
        # aksi halde döngü ilk boş satırda durup asıl metadata satırlarına
        # (ör. "| Aliases: ...") hiç ulaşmıyordu.
        while i < len(block_lines):
            stripped = block_lines[i].strip()

            if stripped == "" or stripped.startswith("|"):
                i += 1
                continue

            break

        # Sözdizimi satırlarından ÖNCE düz bir paragraf varsa (ör. "clean"
        # komutunun genel açıklaması), bu paragraf komutun kendi (alt-kelimesiz)
        # açıklaması olarak kaydediliyor.
        general_lines = []

        while i < len(block_lines):
            stripped_line = block_lines[i].strip()

            if not stripped_line:
                if general_lines:
                    break
                i += 1
                continue

            if syntax_line_pattern.match(stripped_line):
                break

            # ".. _label:" gibi salt referans-hedefi satırları ("module"
            # komutunda olduğu gibi) gerçek metin içermiyor - atlanıyor
            # (ne eklenip ne de paragrafı bitirsin diye kullanılıyor).
            # ".. warning:: metin" gibi uyarı direktifleri ise gerçek,
            # anlamlı bir cümle taşıyor - sadece direktif işaretleyicisi
            # kesilip metni tutuluyor.
            if re.match(r"^\.\.\s+_[\w-]+:\s*$", stripped_line):
                i += 1
                continue

            admonition_match = re.match(
                r"^\.\.\s+\w+::\s*(.*)$", stripped_line
            )

            if admonition_match:
                stripped_line = admonition_match.group(1).strip()

                if not stripped_line:
                    i += 1
                    continue

            general_lines.append(stripped_line)
            i += 1

        if general_lines:
            general_description = clean_rst_text(" ".join(general_lines))
            general_description = re.sub(r"\s+", " ", general_description).strip()

            if len(general_description) >= 10:
                parameters.append({"name": base_name, "description": general_description})

        # Şimdi bloktaki HER "``dnf ...``" sözdizimi satırını + altındaki
        # girintili açıklamayı kendi (muhtemelen bileşik) adıyla yakala.
        while i < len(block_lines):
            line = block_lines[i]
            syntax_match = syntax_line_pattern.match(line.strip())

            if not syntax_match:
                i += 1
                continue

            name_match = compound_name_pattern.match(syntax_match.group(1).strip())
            entry_name = name_match.group(1).strip() if name_match else base_name
            i += 1

            entry_lines = []

            while i < len(block_lines) and (block_lines[i].startswith((" ", "\t")) or not block_lines[i].strip()):
                if block_lines[i].strip():
                    entry_lines.append(block_lines[i].strip())
                elif entry_lines:
                    break
                i += 1

            entry_description = clean_rst_text(" ".join(entry_lines))
            entry_description = re.sub(r"\s+", " ", entry_description).strip()

            if len(entry_description) >= 10:
                parameters.append({"name": entry_name, "description": entry_description})

    return parameters


def parse_dnf_rst(doc):
    text = doc["text"]

    command_name = RST_FILE_TO_COMMAND.get(doc["name"])

    if not command_name:
        raise ValueError("dnf-rst: tanınmayan dosya")

    desc_match = re.search(
        r"^={3,}\s*\n\s*Description\s*\n={3,}\s*\n(.*?)(?=\n={3,}|\Z)",
        text, re.DOTALL | re.MULTILINE
    )
    description_lines: list[str] = []

    if desc_match:
        for line in desc_match.group(1).split("\n"):
            stripped = line.strip()

            if stripped == "" and description_lines:
                break

            if stripped and not stripped.startswith(".."):
                description_lines.append(clean_rst_text(stripped))

    description = re.sub(r"\s+", " ", " ".join(description_lines)).strip()

    syntax_match = re.search(r"^``(dnf[^`]*)``\s*$", text, re.MULTILINE)
    syntax = wrap_code_block(syntax_match.group(1)) if syntax_match else ""

    parameters = parse_rst_options(text)

    if command_name == "dnf":
        existing_names = {p["name"] for p in parameters}

        for entry in parse_dnf_command_reference(text):
            if entry["name"] not in existing_names:
                parameters.append(entry)
                existing_names.add(entry["name"])

    if not description and not parameters:
        raise ValueError("dnf-rst: tanınabilir içerik bulunamadı")

    title = f"DNF {'command reference' if command_name == 'dnf' else 'configuration reference'}"

    intents = []

    return title, command_name, description, "", syntax, "", parameters, intents


FORMAT_PARSERS = {
    "powershell-md": parse_powershell_md,
    "git-adoc": parse_git_adoc,
    "tldr-md": parse_tldr_md,
    "gnu-manual-texi": parse_gnu_manual_texi,
    "docker-cli-md": parse_docker_cli_md,
    "troff-man": parse_troff_man,
    "iptables-extension-man": parse_iptables_extension_man,
    "mdoc-man": parse_mdoc_man,
    "dnf-rst": parse_dnf_rst,
    "systemd-docbook-xml": parse_systemd_xml,
}

# Bu formatlar tek dosyadan birden fazla tam kayıt (dict) üretir; standart
# 8'li tuple sözleşmesini kullanmaz, doğrudan sonuç listesine eklenir.
MULTI_RECORD_PARSERS = {
    "shortcut-list": parse_shortcut_list,
    "coreutils-texi": parse_coreutils_texi,
}


with open(INPUT, "r", encoding="utf-8") as f:
    documents = json.load(f)

results = []

for doc in documents:

    doc_format = doc.get("format", "powershell-md")

    # tldr-pages, sembol/operatör isimli sayfalar da içeriyor (!.md, $.md...);
    # bunlar gerçek komut olmadığı için atlanıyor.
    if doc_format == "tldr-md" and not re.match(r"^[A-Za-z0-9]", doc["name"]):
        continue

    if doc_format in MULTI_RECORD_PARSERS:
        try:
            results.extend(MULTI_RECORD_PARSERS[doc_format](doc))
        except Exception:
            pass
        continue

    parser = FORMAT_PARSERS.get(doc_format, parse_powershell_md)

    try:
        title, command, description, synopsis, syntax, examples, parameters, intents = (
            parser(doc)
        )
    except Exception:
        continue

    if not command.strip():
        continue

    # windows-docs geniş bir dizini (WindowsServerDocs) yinelemeli taradığı
    # için "what-is.md"/"overview.md" gibi KAVRAMSAL, gerçek bir komutu
    # belgelemeyen makaleler de birer "command" gibi görünüyor. "what is"
    # özellikle tehlikeli: bu projenin kendi "What is the syntax of X?"
    # soru şablonuyla birebir başlıyor - find_mentioned_command en erken
    # başlayan eşleşmeyi tercih ettiği için, TÜM "what is the syntax of
    # grep/nft/docker build/..." soruları gerçek komut hiç aranmadan bu
    # içeriksiz makaleye yönlendiriliyordu (doğrulandı: grep/nft/docker
    # build'in kendi syntax verisi zaten mevcuttu, sorun tamamen buydu).
    # Bunlar gerçek, çalıştırılabilir bir komut değil - dışarıda bırakılıyor.
    if command.strip().lower() in {"what is", "overview"}:
        continue

    results.append({

        "command": command,

        "title": title,

        "description": description,

        "synopsis": synopsis,

        "syntax": syntax,

        "examples": examples,

        "parameters": parameters,

        "intents": intents,

        "path": doc["path"]

    })


# Tam referans kaynağı olan (eksiksiz seçenek listesi sağlayan) kaynaklar.
# Yeni bir "gnu-manual-texi" tarzı kaynak eklendiğinde buraya eklenmeli.
COMPLETE_REFERENCE_SOURCES = (
    "coreutils-docs", "grep-docs", "systemd-docs", "docker-docs",
    "nftables-docs", "cron-docs", "iptables-docs", "ufw-docs", "ssh-docs",
    "apt-docs", "dnf-docs"
)


def merge_complementary_sources(records):
    """Tam referans kaynağı (coreutils/grep gibi, eksiksiz seçenek listesi)
    ve tldr (gerçek kullanım örnekleri) aynı komut için ayrı kayıt kalırsa
    aynı soruya çelişen/eksik iki cevap üretilir. İkisini birleştirir:
    açıklama/syntax/parametreler referans kaynaktan, örnekler/niyetler
    tldr'den."""
    by_command: dict[str, list[dict]] = {}
    order: list[str] = []

    for record in records:
        name = record["command"]

        if name not in by_command:
            by_command[name] = []
            order.append(name)

        by_command[name].append(record)

    # tldr, "docker-compose" gibi çok kelimeli alt-komutları "docker
    # compose"a çevirdiği aynı kuralla "ssh-keygen"/"apt-get" gibi tek
    # parça, gerçekten tireli komutları da boşluklu isme çeviriyor.
    # Referans kaynak (DocBook/mdoc/vs.) gerçek tireyi koruduğu için bu
    # komutların tldr karşılığı farklı bir grup adı altında kalıp hiç
    # birleşmiyordu (ör. "apt-get" 91 parametre + 0 örnek, "apt get"
    # ayrı, birleşmemiş bir kayıt olarak 918 örnekle kalıyordu). Önce
    # hangi boşluklu grupların salt tldr'den ibaret olduğu ve bir
    # tireli referans karşılığı bulunduğu belirleniyor, sonra o
    # gruplar tireli isim altında birleştirilip ayrı emit edilmiyor.
    consumed_spaced_names: set[str] = set()
    extra_tldr_by_name: dict[str, list[dict]] = {}

    for name in order:
        if "-" not in name:
            continue

        group = by_command[name]
        has_reference = any(
            any(src in r["path"] for src in COMPLETE_REFERENCE_SOURCES)
            for r in group
        )
        has_own_tldr = any("linux-docs" in r["path"] for r in group)

        if not has_reference or has_own_tldr:
            continue

        spaced_name = name.replace("-", " ")
        spaced_group = by_command.get(spaced_name)

        if not spaced_group:
            continue

        if all("linux-docs" in r["path"] for r in spaced_group):
            consumed_spaced_names.add(spaced_name)
            extra_tldr_by_name[name] = spaced_group

    merged = []

    for name in order:
        if name in consumed_spaced_names:
            continue

        group = by_command[name]

        reference_records = [
            r for r in group
            if any(src in r["path"] for src in COMPLETE_REFERENCE_SOURCES)
        ]
        tldr_records = [r for r in group if "linux-docs" in r["path"]]
        tldr_records = tldr_records + extra_tldr_by_name.get(name, [])

        if reference_records and tldr_records:
            base = reference_records[0]

            # tldr aynı komut için birden fazla sayfa içerebiliyor (ör.
            # "cat" hem pages/common hem pages/linux altında ayrı ayrı var) -
            # sadece İLKİNİ birleştirip ikincisini "remaining"de bırakmak,
            # aynı komut için tekrar eden, birleştirilmemiş bir kayıt daha
            # üretiyordu. Artık TÜM tldr kayıtları birleştiriliyor.
            for extra in tldr_records:
                base["examples"] = base["examples"] or extra["examples"]
                base["intents"] = (base.get("intents") or []) + (extra.get("intents") or [])

            merged.append(base)

            remaining = [
                r for r in group
                if r is not reference_records[0] and r not in tldr_records
            ]
            merged.extend(remaining)
        else:
            merged.extend(group)

    return merged


def dedupe_docker_alias_fanout(records):
    """docker-docs'a ÖZGÜ bir durum: bazı komutlar birden fazla namespace
    altında belgeleniyor ve ikisi de kendi Aliases listesinde AYNI en kısa
    ismi veriyor (ör. 'docker build' hem builder_build.md hem
    image_build.md'de, ikisi de 'docker build'e daralıyor) - parser bunu
    dosya bazında bilemez. SADECE docker-docs kaynağı içinde, aynı komut
    adında birden fazla kayıt kalırsa en çok parametreye sahip olanı
    tutuluyor.
    Diğer kaynaklara DOKUNULMUYOR: powershell-docs gibi kaynaklarda aynı
    komut adı (ör. Get-Process) kasıtlı olarak birden fazla sürüm
    klasöründe (5.1, 7.4, 7.5...) ayrı ayrı belgeleniyor - bunlar gerçek,
    korunması gereken ayrı kayıtlar, çakışma değil. Aynı şekilde Windows
    'dir' ile GNU 'dir' de farklı kaynaklardan gelen, kasıtlı olarak ayrı
    tutulan isim çakışmaları."""
    docker_records = [r for r in records if "docker-docs" in r["path"]]
    other_records = [r for r in records if "docker-docs" not in r["path"]]

    by_command: dict[str, list[dict]] = {}
    order: list[str] = []

    for record in docker_records:
        name = record["command"]

        if name not in by_command:
            by_command[name] = []
            order.append(name)

        by_command[name].append(record)

    deduped_docker = []

    for name in order:
        group = by_command[name]

        if len(group) == 1:
            deduped_docker.append(group[0])
            continue

        best = max(group, key=lambda r: (len(r["parameters"]), len(r["description"])))
        deduped_docker.append(best)

    return other_records + deduped_docker


results = merge_complementary_sources(results)
results = dedupe_docker_alias_fanout(results)

OUTPUT.parent.mkdir(
    parents=True,
    exist_ok=True
)

with open(OUTPUT, "w", encoding="utf-8") as f:

    json.dump(
        results,
        f,
        indent=2,
        ensure_ascii=False
    )

print(f"{len(results)} komut işlendi.")
