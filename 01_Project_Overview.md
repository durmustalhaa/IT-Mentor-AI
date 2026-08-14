# IT Mentor AI - Project Overview

## Vision

Build an offline AI assistant for IT operations that can answer
questions from Microsoft Learn, Git and Linux documentation using a
local LLM.

## Objectives

-   Offline inference
-   ~~LoRA fine-tuning~~ - tried, retired, see below and
    03_LoRA_Training.md
-   Clean, maintainable dataset pipeline
-   Retrieval (RAG) for exact-recall questions a small model can't
    reliably memorize
-   Desktop application
-   Intent-aware answers (user describes a goal, model recommends the
    right command), not just command lookup

## Architecture (current)

```
Sources -> Parser (format-specific) -> commands.json
         -> build_dataset.py -> dataset.jsonl
         -> build_index.py -> embedding index (knowledge: exact facts)
         -> test_model.py / gui_app.py: retrieve first, generate only
            as a low-confidence, clearly-labeled fallback (plain base
            model, no fine-tuning)
```

The original plan was "LoRA now, RAG later." RAG arrived sooner than
planned - testing showed a 0.5B LoRA cannot reliably memorize
exact multi-fact answers (full flag lists, exact keyboard shortcuts)
no matter how the dataset or training is tuned. See
06_Decisions_Log.md. LoRA was later retired from the pipeline entirely
(see 03_LoRA_Training.md "LoRA Emekliye Ayrıldı") - `scripts/train.py`
has been deleted along with the old model checkpoints under `models/`;
the diagram above no longer has a training step at all.

## Data Sources

-   **PowerShell-Docs** (Markdown, cmdlet reference folders only)
-   **Windows Server Docs** (Markdown, administration articles +
    ~869 classic CMD command references - `netstat`/`schtasks`/
    `netsh`/`attrib`/`robocopy`/`ping`/`ipconfig` etc., complete
    parameter tables)
-   **Git** (AsciiDoc, official `Documentation/` reference)
-   **Linux** (tldr-pages, curated allowlist of ~200 core sysadmin
    commands - curated examples, not an exhaustive reference)
-   **GNU coreutils** (texinfo manual - complete option lists for
    ~103 commands, e.g. `ls`/`cp`/`mv`/`chmod`/`df`, merged with
    tldr's real examples for the same commands)
-   **GNU grep** (its own texinfo manual - complete option list,
    same parser pattern as coreutils; replaced grep's old
    tldr-only partial flag coverage)
-   **Docker CLI** (docker/cli's own generated Markdown reference -
    143 commands/subcommands, complete option tables)
-   **systemd** (its own DocBook XML manual - `systemctl`,
    `journalctl`, `systemd-analyze`, `loginctl`, `timedatectl`,
    `hostnamectl` plus the most-used unit-file directive references:
    `systemd.service`, `systemd.timer`, `systemd.socket`,
    `systemd.exec`, `systemd.unit`, etc.)
-   **Windows Server PowerShell modules** (`windows-powershell-docs` -
    a separate Microsoft repo from PowerShell-Docs, same `###
    -ParamName` Markdown convention; `ActiveDirectory`,
    `ScheduledTasks`, `NetSecurity`/Windows Firewall, `DhcpServer`,
    `DnsServer`, `DnsClient`, `NetTCPIP`, `NetAdapter`,
    `NetConnection`, `GroupPolicy` - ~695 cmdlets)
-   **nftables** (its own DocBook XML manual, `nft` - reuses the
    systemd parser directly)
-   **cron, iptables, ufw** (their own classic troff/man-page
    manuals - `crontab`/`cron`/`anacron`/`cronnext`,
    `iptables`/`ip6tables` + save/restore/apply helpers, `ufw`; first
    sources needing a new troff/man-macro parser in this project)
-   **OpenSSH** (its own BSD mdoc manuals - `ssh`, `sshd`, `scp`,
    `sftp`, `ssh-keygen`, `ssh-agent`, `ssh-add`, `ssh-keyscan`,
    `ssh_config`, `sshd_config`, etc.; mdoc is a different macro
    dialect from troff/man, needed its own parser)
-   **apt** (its own DocBook XML manuals - `apt`, `apt-get`,
    `apt-cache`, `apt-mark`, `apt.conf`, `sources.list`, etc.; reuses
    the systemd/nftables DocBook parser with one small generalization
    for entity names)
-   **dnf** (its own reStructuredText manual - CLI command reference
    and `dnf.conf` configuration reference; needed a new RST parser)
-   **Windows keyboard shortcuts** (manually sourced from Microsoft's
    official support page - not a git repo, no complete-reference
    source exists as a clonable repo)

## Status

Dataset: 174,623 examples across 6 categories. RAG retrieval is live
in `test_model.py`/`gui_app.py` (both thin wrappers around the shared
`scripts/mentor_core.py`), with command-scoped, case-sensitive
exact-match routing for flag-specific questions (see 07_RAG.md). Every
dataset row is tagged with its source `command` for this routing.
Every tool-family gap originally identified in this project is now
covered by a complete-reference source (dpkg's POD-format docs remain
an optional, lower-priority follow-up - apt's own CLI already covers
the Debian/Ubuntu day-to-day experience). Measured directly: ~90%+ of
realistic questions get a real RAG-retrieved answer; the rest fall
back to the plain base model (Qwen2.5-0.5B-Instruct, no LoRA - the
adapter is no longer loaded at all, see 03_LoRA_Training.md "LoRA
Emekliye Ayrıldı") rather than the IT-specialized one, since the
adapter's narrow training made it fabricate fake commands for anything
outside its format. See 04_Testing_Results.md for current known
issues.

## Desktop UI

A simple Tkinter window (`scripts/gui_app.py`) launches from a desktop
shortcut (`scripts/create_shortcut.ps1`, `pythonw.exe`, no console
window) with its own icon (`assets/app_icon.ico`) - day-to-day use no
longer requires opening VS Code or a terminal.

`install.bat` (project root) wraps first-time setup for anyone who
clones the repo: checks for Python, runs `pip install`, builds the RAG
index if missing, and calls `create_shortcut.ps1` - one double-click,
no manual steps, nothing installed silently (if Python isn't found it
just prints where to get it and exits). `create_shortcut.ps1` no
longer needs a hardcoded path either - it auto-detects `pythonw.exe`
from whichever `python` resolves on PATH, skipping Windows' empty
Microsoft Store stub if a real Python is also installed (found via
testing before this was assumed to work).

## Publishing (GitHub) - Prep Done (2026-08-13)

The repository was cleaned up ahead of a public GitHub upload:

-   `LICENSE` (MIT, covers this project's own code only) and
    `ATTRIBUTION.md` (per-source license breakdown for the
    dataset/model, since those are derived from third-party
    documentation under their own licenses - GPL, GFDL, CC-BY, Apache,
    ISC, BSD) added, with verbatim upstream license texts under
    `THIRD_PARTY_LICENSES/`.
-   `.gitignore` added - excludes `data/raw/` (huge cloned doc repos,
    regenerable via `scripts/download_sources.py`), keeps
    `data/processed/` (the actual dataset/index) and `models/`.
-   All old model checkpoints deleted (`models/` is now empty) -
    confirmed harmless since the live pipeline never loaded any of
    them (see 03_LoRA_Training.md).
-   `scripts/train.py` deleted (LoRA training is retired, not planned
    - see 03_LoRA_Training.md) along with its now-unused dependencies
    (`peft`, `trl`, `datasets`, `accelerate`) from `requirements.txt`.
-   Remaining `scripts/` are either the live app
    (`mentor_core.py`/`test_model.py`/`gui_app.py`/
    `create_shortcut.ps1`) or the dataset pipeline kept for future
    updates (`download_sources.py` -> `index_documents.py` ->
    `extract_commands.py` -> `build_dataset.py` -> `build_index.py`,
    plus the QA tools `audit_dataset.py`/`sample_audit_examples.py`).
