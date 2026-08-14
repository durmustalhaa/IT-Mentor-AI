# Roadmap

## Short Term

-   [x] Expand intent generation (template-based)
-   [x] Add grep/git specific intents
-   [x] Add Linux specific intents (curated tldr source)
-   [x] Fix example-generation bug (code being silently deleted)
-   [x] Retrain LoRA on the rebuilt dataset - done, multiple times
        (see 03_LoRA_Training.md for the full history including the
        3-epoch negative result)
-   [x] Add RAG - arrived earlier than planned once fine-tuning alone
        proved unable to fix exact-recall questions
-   [x] Add GNU coreutils as a complete-reference source (phase 1 of
        fixing partial Linux flag coverage)
-   [x] Add GNU grep as a complete-reference source (phase 2)
-   [x] Fix RAG's "related but doesn't answer the question" failure
        mode - command-scoped, case-sensitive exact-match retrieval,
        plus an honest fallback when the named command truly has no
        matching flag data (see 07_RAG.md)
-   [x] Fix nested-texinfo-table parsing (was silently dropping most
        of a command's flags for commands like `nl`)
-   [x] Fix commands with no native option docs (`dir`/`vdir`,
        checksum family) via generalized option-borrowing
-   [x] Fix macro-defined flags being invisible to the parser (33
        commands, +276 parameters recovered)
-   [x] Add Docker CLI as a complete-reference source (143 commands)
-   [x] Add systemd as a complete-reference source (16 files: CLI
        tools + most-used unit-file directive sets)
-   [x] Fix coreutils description quality (dangling sentences after
        stripped `@example` blocks, leaked `@menu` syntax, nested-
        macro-broken `@xref` stripping, several unhandled texinfo
        escapes)
-   [x] Fix ~869 already-cloned Windows CLI command docs (`netstat`,
        `schtasks`, `netsh`, `robocopy`, `attrib`...) silently
        producing zero parameters each - added a fallback table
        parser, recovered 4,793 parameters
-   [x] Add the Active Directory PowerShell module as a source -
        found it lives in a separate repo (`windows-powershell-docs`)
        that also covers `ScheduledTasks`, `NetSecurity`/Windows
        Firewall, DNS/DHCP, and networking (~140 modules total,
        curated to 10) - one addition closed four roadmap items at
        once, 8,257 parameters recovered, the largest single addition
        in the project
-   [x] Add nftables as a complete-reference source - reused the
        systemd DocBook parser directly after a small generalization
-   [x] Build a troff/man-page parser and add cron, iptables, and ufw
        as complete-reference sources (first new parser format since
        Docker/systemd/DocBook)
-   [x] Build an mdoc parser (BSD's distinct macro dialect, not
        compatible with troff-man) and add ssh/OpenSSH as a
        complete-reference source (`ssh`, `sshd`, `scp`, `sftp`,
        `ssh-keygen`, `ssh_config`/`sshd_config`, etc. - 519
        parameters across 15 manuals)
-   [x] Add apt as a complete-reference source - reused the systemd/
        nftables DocBook parser after a small entity-name
        generalization
-   [x] Build an RST parser and add dnf as a complete-reference
        source (CLI command reference + `dnf.conf` directives - 389
        parameters recovered between apt and dnf together) - closes
        every originally-identified tool-family gap
-   [x] Run a structured audit (10+ fresh questions per source) before
        committing to a retrain - found and fixed the four largest
        bugs in the project: nftables' add/delete/list/flush colliding
        across table/chain/rule, dnf's own commands never being parsed
        at all, 86 git subcommands with a hyphen in their own name
        being misnamed, and git flags/subcommands living outside every
        section the parser scanned
-   [x] Fix the retrieval-layer bugs the audit's own fixes surfaced -
        `find_mentioned_command` had no tiebreak for equal-length
        command names (`nft`/`dnf` could lose to unrelated same-length
        Windows commands `add`/`list`), PowerShell/Windows cmdlet names
        stored space-separated never matched their real hyphenated
        form in questions, and a known-command-but-unknown-specific-
        flag case had no honest fallback
-   [x] Repeat the structured audit with a second, fully fresh set of
        150 questions - found and fixed a real Docker example-
        extraction bug (`docker push`/`docker load` stored the wrong
        code block from a multi-step tutorial) plus two cosmetic
        markup leaks; confirmed two other findings (`net use` and two
        keyboard shortcuts) as genuine source-content gaps rather than
        bugs, deliberately left unfixed rather than hand-authored
-   [x] Repeat the structured audit a third time ("for the last time"),
        30 fresh questions per subject (438 total) - found no new
        dataset-content bugs, but five more retrieval-layer bugs in the
        same family as the equal-length-tiebreak fix: generic real
        command names (`list`/`add`) colliding with this project's own
        question templates; systemd's dot-separated man page names
        never matching natural space-separated phrasing; directive
        names only recognized immediately after a command name, missing
        natural sentence-initial phrasing; some directives being real
        data filed under a different, related man page systemd's own
        docs point to; and the shortcut pool being built from answer
        text instead of source, plus no exact-match check for key
        combos - letting genuinely missing shortcuts (`Ctrl+O` etc.)
        confidently return a different, wrong shortcut's answer. All
        five fixed and verified live; no dataset rebuild needed
-   [x] Fill every confirmed-fixable gap from the third audit by
        finding real sources online: the 22-command `net` family
        (Microsoft's archived `previous-versions` TechNet library, since
        the current windows-commands docs no longer carry most of them);
        `apt-key` (Debian's own currently-maintained man page,
        reconstructed as DocBook XML); `networkctl`/`busctl`/
        `machinectl`/`portablectl`/`resolvectl` (already-cloned files,
        just never added to the curation allowlist); and 2 of the 10
        missing keyboard shortcuts (`Windows key + Pause`, `Windows key
        + number` - both real, currently on Microsoft's own shortcuts
        page). `apt-get moo` and the other 8 `Ctrl+` shortcuts were
        confirmed to have no real source and correctly left alone.
        Also found and fixed, while rebuilding the pipeline for these:
        a real pre-existing bug in `parse_systemd_xml` (a shadowed loop
        variable silently corrupted the top-level description of every
        DocBook-family command with any parameters - `networkctl`,
        `apt-get`, `systemctl`, all of them), plus two smaller
        self-inflicted issues caught while verifying (a boilerplate
        `net help` row colliding across the new `net-*` files, and
        `"Windows key + 5"` not matching the new generic `"...+
        number"` shortcut record)
-   [x] Fix general chat/greetings being handled by the narrowly-tuned
        LoRA adapter (fabricated fake commands for "merhaba") - switched
        the generative fallback to run with the adapter disabled
        (`peft`'s built-in `model.disable_adapter()`), no retraining
        needed
-   [x] Generalize the `"service"`-vs-portablectl collision fix - any
        common verb that's also a real command name (`copy`, `rename`)
        was breaking natural "how do I..." questions the same way;
        added `INTENT_PHRASE_PATTERN` to skip command-scoping for any
        naturally-phrased intent question, regardless of which word
        triggered the false match
-   [x] Measure what fraction of real questions actually need the
        generative fallback (763 accumulated test questions: 89.9%
        direct match, 1.4% closest-match, 8.7% fallback) and close as
        many of the real gaps behind that 8.7% as practical: a bogus
        `"what is"` pseudo-command colliding with this project's own
        question template, git flags in two unscanned AsciiDoc
        sections, iptables' most-asked flags (previously excluded for
        a reason that turned out to be only half right), the whole
        checksum family (`b2sum`/`sha256sum` and siblings), two more
        nftables subcommands, and bundled short flags (`docker exec
        -it`, `ls -la`)
-   [x] ~~Retrain LoRA (`v7`)~~ - decided against, not "not yet done".
        Once it became clear the LoRA adapter's `use_adapter=True`
        branch was never actually reached by any code path anymore
        (RAG handles ~90% directly, and the generative fallback for
        the rest was deliberately switched to the base model - see
        03_LoRA_Training.md "LoRA Emekliye Ayrıldı"), retraining would
        produce an adapter nothing calls. Removed the adapter-loading
        code entirely rather than leave it as dead weight.
-   [x] Prepare the repository for a public GitHub upload (2026-08-13):
        added `LICENSE` (MIT, own code) and `ATTRIBUTION.md` +
        `THIRD_PARTY_LICENSES/` (per-source license breakdown and
        verbatim upstream texts, since the dataset/model are derived
        from GPL/GFDL/CC-BY/Apache/ISC/BSD-licensed documentation, not
        original work); added `.gitignore` (excludes `data/raw/`,
        keeps the actual dataset and models); deleted every old model
        checkpoint under `models/` (confirmed none were loaded by the
        live pipeline) and `scripts/train.py` (LoRA retired, not
        planned), trimming `peft`/`trl`/`datasets`/`accelerate` out of
        `requirements.txt` as a result. Researched real precedent
        (Thomson Reuters v. ROSS Intelligence, the GPL-propagates-to-
        AI-models debate, Feist v. Rural Telephone) before deciding
        this was reasonable-effort risk mitigation, not a guarantee -
        see 06_Decisions_Log.md.
-   [x] Found and fixed a real GitHub-blocking issue while doing the
        prep above: `data/processed/rag_index/embeddings.npy` is
        ~268MB, over GitHub's 100MB hard per-file limit - push would
        have been rejected outright. Excluded `rag_index/` (and the
        now-orphaned `documents.json` intermediate, ~67MB, unusable
        without the unpublished `data/raw/`) via `.gitignore`;
        `README.md` updated so `build_index.py` is a documented
        required setup step (~25s, regenerates the index from the
        published `dataset.jsonl`) instead of assuming the index ships
        with the repo.
-   [x] Add `install.bat` (one-click setup: checks for Python, `pip
        install`, builds the RAG index if missing, creates the desktop
        shortcut - fails with a clear message instead of silently
        installing anything if Python isn't found) and make
        `create_shortcut.ps1` auto-detect `pythonw.exe` instead of
        needing a hardcoded, machine-specific path. Testing this
        (without actually overwriting the working desktop shortcut)
        surfaced a real Windows gotcha: the first `python` match on
        PATH can be an empty Microsoft Store stub even when a real
        Python is also installed - fixed by scanning every PATH match
        for one with a real adjacent `pythonw.exe`, not just the
        first hit.
-   [ ] Shrink the remaining ~8.7% generative-fallback slice into RAG
        coverage - either by finding/adding real source data for
        genuinely missing gaps, or by injecting retrieved candidates
        into the fallback prompt instead of discarding them (see
        07_RAG.md Known Limitations #2). **Deferred by explicit user
        request (2026-08-13) - do not start until the user says go.**
-   [ ] Optional: `dpkg` (POD format) as a lower-priority follow-up
-   [ ] Optional: git's diff-options internal name collisions (~1,320
        pairs) - would need a context-tracking mechanism comparable to
        the nftables fix, but AsciiDoc has no equivalent marker to
        hang it on
-   [ ] Optional: recover very short but valid descriptions (like
        `docker network ls`'s "List networks") currently dropped by
        the 15-character minimum-answer-length filter, or flags only
        mentioned in prose rather than their own entry (like `apt
        list`'s `--all-versions`)
-   [ ] Optional: `apt-get moo` and the remaining 8 missing keyboard
        shortcuts (`Ctrl+O`/`+P`/`+S`/`+G`/`+J`/`+K`/`+M`/`+Q`,
        `Ctrl+Shift+T`) have no real source to draw from - would stay
        open indefinitely unless one surfaces

## Medium Term

-   [ ] Multilingual embedding model for the RAG index (Turkish
        queries currently route badly - deprioritized, not urgent)
-   [ ] Better evaluation benchmark - still ad hoc manual testing, no
        automated eval set
-   [ ] Validation dataset - not yet split out from training data

## Long Term

-   [x] Add RAG - done, see 07_RAG.md
-   [x] Desktop UI - a simple Tkinter window (`scripts/gui_app.py`)
        wrapping the same retrieval/generation logic as the CLI, now
        shared via a new `scripts/mentor_core.py` module so neither
        copy drifts from the other. Launched via a desktop shortcut
        (`scripts/create_shortcut.ps1`) pointing at `pythonw.exe`, so
        no console window opens and no VS Code is needed day-to-day.
        Custom icon at `assets/app_icon.ico`.
-   [ ] Semantic search - the RAG index already does this for
        dataset.jsonl; extending it to raw documentation would be a
        natural next step
-   [ ] Continuous documentation updates

## Important Lessons (updated)

**Volume is not the same as value.** Confirmed twice now: once with
the unfiltered tldr source (113K mostly-irrelevant examples), once
with the 3-epoch experiment (more repetition of the same data made
things worse, not better).

**A source can be "configured" and still contribute nothing.** Git's
AsciiDoc docs were invisible to a Markdown-only parser for a long
time before anyone checked category counts by source.

**Small models have a real, hard capacity ceiling for exact recall.**
No amount of prompt engineering, phrasing diversity, or extra epochs
made a 0.5B LoRA reliably memorize hundreds of exact multi-fact
answers - it wasn't a data or training problem, it was the wrong tool
for that sub-task. Retrieval solved in one pass what three separate
training attempts couldn't.

**"Similar" is not "correct."** Even retrieval isn't automatically
safe - a confidently-shown high-similarity match can still fail to
actually answer the question asked if the underlying data has a gap.
Confidence scores need to be interpreted per-question-type, not as a
single universal threshold.

**Data completeness is a per-source property, not a parsing
problem.** tldr-pages fundamentally does not contain grep's full
option list, no matter how the parser is written - fixing this
requires a different, more complete source (like coreutils' texinfo
manual), not cleverer regex.

**One bug found by hand often points at a whole bug class.**
`dirname`/`printenv` looking suspiciously flag-less during a manual
spot-check led to finding that ~20 shared texinfo macros were
invisible to the parser across 33 commands, not just those two -
worth checking "does this same root cause reproduce elsewhere"
every time, not just patching the reported example.

**Embeddings are close to case-blind.** No-dash intent questions
("ls l" vs "ls L") that differ only by letter case can map to nearly
identical vectors even when the real answers are completely
different - this needed explicit case-sensitive exact-match logic
outside the embedding model, not a better embedding model.

**The best next data source might already be cloned.** Went looking
for new sources for networking/scheduled-tasks/firewall coverage and
found the single biggest win wasn't a new source at all - `windows-
docs` already had ~869 classic CLI command references sitting in the
repo, silently parsed into zero-parameter records because of a format
mismatch nobody had checked for. Worth auditing what's already
indexed with 0 parameters before reaching for a new `git clone`.

**A general fix generalized too far.** The escaped-pipe-breaks-table-
split bug (Docker, then independently rediscovered in Windows CLI
docs) is now the third parser to hit some version of "a markdown/
texinfo table cell contains a literal delimiter character that needs
protecting before naive splitting" - worth treating as a known bug
class to check for by default whenever building a new table-based
parser, not just when it's reported.

**A repo's name undersells its contents.** `windows-powershell-docs`
sounds like a companion index to `PowerShell-Docs`; it's actually a
~140-module reference covering four different roadmap items at once
(AD, scheduled tasks, firewall, networking) that would otherwise have
been chased as four separate source investigations. Worth checking a
candidate repo's *actual directory listing* before assuming its scope
from its name or the one cmdlet that was searched for.

**Validate a new parser format against 2-3 real sources before
trusting it on the first one.** The troff/man parser looked complete
after `crontab` alone (10/10 correct), but `iptables` and `ufw`
immediately surfaced format variance (inline vs. macro-line flag
names, nested option lists) that crontab's simpler structure never
exercised. Building against multiple sources from the start - rather
than one now and "fix issues as they come up" later - caught bugs
before they shipped instead of after. The mdoc parser (ssh) confirmed
this again independently.

**A "strip known keywords" cleanup step is only safe on lines where
those keywords can only mean one thing.** The mdoc parser's word-level
macro-name stripping was correct for actual macro-invocation lines,
but applying the same rule to ordinary prose corrupted real sentences
- `on` and `An` are common English words that happen to collide with
mdoc macro names, and got silently deleted wherever they appeared as
normal vocabulary (`"specified on a per-host basis"` lost its `"on"`).
Any keyword-stripping approach needs to ask first whether the keyword
set could collide with the surrounding natural-language content, not
just whether it correctly matches the intended macro syntax.

**Recognizing a new case isn't the same as handling it everywhere it
matters.** The RST parser's `dnf.conf` bug had two layers: first, bare
identifier terms weren't recognized as valid entries at all (0
results); after fixing that, they *were* recognized, but a leftover
downstream filter written only for dashed CLI flags still discarded
them before they reached the output (still 0 results, same visible
symptom, different cause). A fix that changes what counts as "valid"
needs to be traced all the way through every later step that assumes
the old, narrower definition - checking the "is it recognized" step in
isolation wasn't enough to confirm the fix actually worked end to end.

**A rule that's right for the common case can be silently wrong for
an important minority case.** tldr's "replace every filename hyphen
with a space" rule is correct for genuine multi-word subcommands
(`docker-compose` -> "docker compose") but wrong for standalone
binaries that are actually typed with the hyphen (`ssh-keygen`,
`apt-get`, `systemd-analyze`) - and this went unnoticed since
ssh-keygen and systemd-analyze were first added, only surfacing when
apt/dnf's own merge was verified directly instead of assumed correct
from the addition alone. A blanket transformation applied uniformly
across a whole source deserves the same "does this generalize
correctly to every case, not just the one being looked at right now"
scrutiny as a new parser does.

**Small, targeted checks confirm a fix works; only broad, fresh
checks find what it didn't touch.** Every earlier pass this project
had validated fixes by re-checking the specific reported case (and
the accumulated regression set) - reasonable, but it meant entire
sources could sit with severe, basic-operation-level bugs
(nftables was wrong on 8 of 10 questions, dnf's own commands didn't
exist at all) indefinitely, because nothing had ever asked about
their most ordinary, common usage with new wording. A single
structured pass - 10+ never-before-used questions per source - found
more real bugs in one sitting than several prior sessions of
targeted spot-checking combined. Worth repeating periodically, not
just before a retrain.

**Tie-breaking on length alone is a silent trap once two real things
happen to be the same length.** `find_mentioned_command` sorted
candidate command names longest-first specifically to prefer
`"printf"` over `"pr"` - correct reasoning, but it quietly assumed
length differences would always exist. `"nft"` and `"add"` (a real,
unrelated Windows command) are the same length, so the tiebreak had
no signal to fall back on and picked arbitrarily. The fix (prefer
whichever match starts earliest in the text) is the more fundamentally
correct signal - it just wasn't needed until two same-length real
names collided in the same query, which took months of sources being
added before it happened by chance.

**Verify a fix by re-running the full regression set immediately, not
after the next unrelated change.** Two bugs this session were only
caught because live testing happened right after writing the fix, not
days later: a new branch was accidentally nested one level too deep
(inside a condition it could never coexist with, making it dead code
that silently never ran), and broadening a keyword pattern to fix one
case (`PrtScn`) regressed a different, already-validated one (`F2`) by
changing which candidate pool it searched. Both were invisible from
reading the diff alone - only running real queries against the actual
running system surfaced them.

**Not every gap found by an audit is a bug, and not every gap should
be closed the same way.** The second fresh-question audit found three
things that looked identical from the outside (a wrong or missing
answer) but needed three different responses: a real extraction bug
(fixed in code), and two genuine absences in the source material
itself (`net use`, two keyboard shortcuts) where the tempting "fix" -
writing a plausible-sounding paragraph from general knowledge - was
explicitly rejected. This project's entire reliability story rests on
every answer tracing back to something a real document said; quietly
authoring content to make a gap disappear would look identical to a
real fix in the dataset but would reintroduce, one row at a time, the
exact hallucination risk RAG was built to remove. A found gap is a
decision point (fix the code, find a better source, or document the
limit honestly), not automatically a to-do.

**A fix for one collision can create the opposite collision.** The
equal-length-tiebreak fix correctly made the earliest-mentioned command
name win - but that quietly assumed the earliest match is always the
real subject. This project's own question generator writes `"Can you
list all X flags?"`, putting a real-but-irrelevant Windows command
(`list`) BEFORE the actual subject by construction. The fix that closed
one gap opened a different one shaped exactly like it; catching it
needed a third audit, not just re-checking the second fix's own test
cases.

**A natural rephrasing of a real name can silently stop matching
anything.** Nobody asks about `systemd.service` using its literal
dot-separated man-page name - they say "systemd service unit". The
command existed in the data the whole time; the retrieval pattern
requiring an exact-including-punctuation substring match was the only
thing standing between a completely ordinary question and the right
answer, and it failed silently (by matching a different, real, wrong
command) rather than obviously.

**Source-internal cross-references are a legitimate place to widen a
search, not fabrication.** `User=`/`WorkingDirectory=` are real,
correctly-extracted data - just filed under `systemd.exec` because
that's where systemd's OWN documentation puts shared directives,
with every unit-type page explicitly pointing there. Teaching the
retrieval layer to follow a cross-reference the source already makes
explicit is different in kind from inventing an answer; the line is
whether the content still traces back to something a real document
said.

**A narrow, correctly-scoped search pool can still be too
self-similar for the embedding model to use safely.** Restricting
"what does Ctrl+O do?" to the ~150-record shortcut pool was necessary
but not sufficient - nearly every record in that pool is the same
four-word template with one letter changed, and the embedding model
scored a completely wrong letter's answer at 0.84 similarity, well
past the confidence threshold. Scoping reduces noise; it doesn't
substitute for an exact-match check when the pool itself is
homogeneous enough that "closest" stops meaning "correct".

**"No source" and "no source in the specific clone I already have" are
different claims - worth checking before writing off a gap.** `net
use` and `apt-key` were both documented as unfixable source gaps after
checking only the already-cloned repos. Neither claim held up once
actually searched for online: Microsoft still publishes a full archived
`net` command reference, just not in the actively-maintained repo this
project cloned from, and Debian still maintains `apt-key`'s man page
for current releases, just not in the specific upstream branch/version
in the local shallow clone. The lesson from the second audit ("not
every gap is a bug, don't hand-author content to fill it") still
holds - the addition here is that "hand-author" and "find the real,
already-published source" are different actions, and it's worth
trying the second one before accepting a gap as permanent.

**A bug can hide behind a question nobody happened to ask.** The
`parse_systemd_xml` description-shadowing bug had been silently
corrupting the top-level "what does X do?" answer for every DocBook
command with any parameters - the entire apt/systemd/nftables families
- since whenever those parsers were written. It survived three
separate structured audits (150 + 150 + 438 questions) because every
one of them asked about SUBCOMMANDS and FLAGS almost exclusively
("what does systemctl reload do?"), never the bare command name
("what does systemctl do?"). A bug doesn't have to be rare to go
undetected indefinitely; it just has to live in a question shape the
test suite never happens to construct. Worth deliberately including
the "bare command name" phrasing in future audit rounds, not just
flag/subcommand variants.

**Copying a source's own boilerplate verbatim can introduce a
collision the source's real editors already knew to avoid.** The 22
new `net-*.md` files initially included a `net help <command>` row
because the fetched Microsoft page listed it as a real Parameters-table
row - but the pre-existing, professionally-curated `net-user.md`
doesn't carry that same row even though its own source page has it
too. That was a signal, not a coincidence: the row is near-identical
boilerplate repeated across the whole command family, and including it
verbatim in 16 files at once created exactly the kind of generic-text
collision this project has hit before (`list`/`add` from the third
audit). Faithfulness to a source doesn't mean copying every row that
technically appears in it - matching what the ALREADY-CURATED sibling
files chose to keep is a better signal than the raw source alone.
