# Attribution & Third-Party Licenses

This project's own code (everything under `scripts/`, the desktop app, and
the numbered `01_`-`07_` documentation files) is original work by the author
and is released under the MIT License (see `LICENSE`).

**The training dataset (`data/processed/dataset.jsonl`,
`data/processed/commands.json`) and the trained model (`models/`) are
different.** Their content is extracted or derived from third-party
documentation sources, each under its own license. This file lists every
source, its license, and where a verbatim copy of that license's text can be
found in this repository (`THIRD_PARTY_LICENSES/`).

Nothing in this dataset is claimed as original work belonging exclusively to
this project - it is a structured, searchable re-packaging of publicly
available documentation, with each entry traceable back to a real source
document.

## Sources and Licenses

| Source | Upstream project | License | License text |
|---|---|---|---|
| PowerShell-Docs | github.com/MicrosoftDocs/PowerShell-Docs | CC-BY 4.0 (content) / MIT (code samples) | `THIRD_PARTY_LICENSES/CC-BY-4.0.txt` |
| Windows Server Docs | github.com/MicrosoftDocs/WindowsServerDocs | CC-BY 4.0 | `THIRD_PARTY_LICENSES/CC-BY-4.0.txt` |
| windows-powershell-docs | github.com/MicrosoftDocs/windows-powershell-docs | CC-BY 4.0 | `THIRD_PARTY_LICENSES/CC-BY-4.0.txt` |
| Git | github.com/git/git (`Documentation/`) | GPL-2.0 | `THIRD_PARTY_LICENSES/GPL-2.0.txt` |
| tldr-pages (Linux) | github.com/tldr-pages/tldr | CC-BY 4.0 | `THIRD_PARTY_LICENSES/CC-BY-4.0.txt` |
| GNU coreutils | git.savannah.gnu.org/git/coreutils (manual) | **GFDL 1.3** | `THIRD_PARTY_LICENSES/GFDL-1.3.texi` |
| GNU grep | git.savannah.gnu.org/git/grep (manual) | **GFDL 1.3** | `THIRD_PARTY_LICENSES/GFDL-1.3.texi` |
| Docker CLI | github.com/docker/cli | Apache 2.0 | `THIRD_PARTY_LICENSES/Apache-2.0.txt` |
| systemd | github.com/systemd/systemd (`man/`) | LGPL-2.1-or-later | `THIRD_PARTY_LICENSES/LGPL-2.1.txt` |
| nftables | github.com/Mic92/nftables | GPL-2.0 (v2 only, no "or later") | `THIRD_PARTY_LICENSES/GPL-2.0.txt` |
| cron/anacron | github.com/cronie-crond/cronie | ISC | `THIRD_PARTY_LICENSES/ISC.txt` |
| iptables | github.com/Distrotech/iptables | GPL-2.0 | `THIRD_PARTY_LICENSES/GPL-2.0.txt` |
| ufw | git.launchpad.net/ufw | GPL-3.0 | `THIRD_PARTY_LICENSES/GPL-3.0.txt` |
| OpenSSH | github.com/openssh/openssh-portable | BSD-style (permissive) | `THIRD_PARTY_LICENSES/BSD-OpenSSH.txt` |
| apt | github.com/Debian/apt | GPL-2.0+ | `THIRD_PARTY_LICENSES/GPL-2.0.txt` |
| dnf | github.com/rpm-software-management/dnf | GPL-2.0 | `THIRD_PARTY_LICENSES/GPL-2.0.txt` |
| Windows keyboard shortcuts | Microsoft's public "Keyboard shortcuts in Windows" support page | Microsoft content terms (reference use) | - |

## Base Model

The generative fallback (`scripts/mentor_core.py`) runs
`Qwen/Qwen2.5-0.5B-Instruct` from Hugging Face, unmodified, downloaded at
runtime - it is not redistributed as part of this repository.

- License: **Apache License 2.0**
- Source: https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct
- Copy: `THIRD_PARTY_LICENSES/Apache-2.0.txt`

The RAG embedding model (`sentence-transformers/all-MiniLM-L6-v2`) is used
the same way - downloaded at runtime, not redistributed, Apache 2.0 licensed.

## Important Notes on the Copyleft Sources

Several sources above (coreutils, grep, git, apt, dnf, iptables, nftables,
ufw, systemd) are licensed under **copyleft** terms (GFDL, GPL, or LGPL).
This project extracts short factual content from them - command names,
flag names, and brief descriptions/examples, restructured into a
question-answer dataset - rather than redistributing the original documents
themselves.

This repository is not legal advice, and the author is not a lawyer. If you
plan to redistribute this dataset or a model trained on it beyond personal/
research use, independent legal review is recommended, particularly for the
GFDL-licensed content (coreutils, grep), since the GNU Free Documentation
License has specific requirements for verbatim copying and derivative works
that go beyond simple attribution.
