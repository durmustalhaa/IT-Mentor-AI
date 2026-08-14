import json
from pathlib import Path

from config import RAW_DIR, SOURCES

OUTPUT = Path("data/processed/documents.json")

documents = []

for source_name, source in SOURCES.items():

    # Aynı klonlanmış repoyu FARKLI bir format/allowed_dirs ile ikinci kez
    # taramak gerektiğinde (ör. iptables-docs'un ana man sayfaları
    # troff-man, ama extensions/*.man parça dosyaları ayrı bir parser
    # istiyor), "repo" anahtarı hangi fiziksel klasörün kullanılacağını
    # source_name'den AYRI belirtebiliyor - yoksa iki SOURCES girdisi aynı
    # repoyu paylaşamazdı (repo_path her zaman source_name'den türerdi).
    repo_path = RAW_DIR / source.get("repo", source_name)

    if not repo_path.exists():
        print(f"[UYARI] {repo_path} bulunamadı.")
        continue

    # Çoğu kaynakta tek uzantı yeterli (".md", ".texi") ama klasik man
    # sayfalarında (cron gibi) aynı klasörde ".1"/".5"/".8" gibi birden
    # fazla bölüm numarası uzantısı bir arada bulunuyor - "extension" bu
    # yüzden hem tek string hem liste kabul ediyor.
    extensions = source.get("extension", ".md")

    if isinstance(extensions, str):
        extensions = [extensions]

    doc_format = source.get("format", "powershell-md")
    recursive = source.get("recursive", True)
    allowed_names = source.get("allowed_names")

    for allowed_dir in source["allowed_dirs"]:

        search_path = repo_path / allowed_dir

        if not search_path.exists():
            print(f"[UYARI] {search_path} bulunamadı.")
            continue

        glob_fn = search_path.rglob if recursive else search_path.glob

        for extension in extensions:
            for file in glob_fn(f"*{extension}"):

                if allowed_names is not None and file.stem.lower() not in allowed_names:
                    continue

                try:
                    text = file.read_text(
                        encoding="utf-8",
                        errors="ignore"
                    )

                except Exception:
                    continue

                documents.append({
                    "source": source_name,
                    "format": doc_format,
                    "path": str(file),
                    "name": file.stem,
                    "text": text
                })

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

with open(
    OUTPUT,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        documents,
        f,
        ensure_ascii=False,
        indent=2
    )

print(f"\nToplam {len(documents)} belge indekslendi.")