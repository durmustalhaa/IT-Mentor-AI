# RAG (Retrieval-Augmented Generation)

## Why

3-epoch experiment (see 03_LoRA_Training.md) proved that more
training doesn't fix exact-recall questions ("list every flag of X",
"what does keyboard shortcut Y do") - it's a knowledge-storage
problem, not a behaviour problem, and a 0.5B LoRA doesn't have the
capacity to reliably memorize hundreds of exact multi-fact answers.
Concrete failures before RAG: `grep` overview hallucinated fictional
flags (`--line-increment`, `--max-line-length` - don't exist);
`F2` got a completely unrelated made-up answer despite being in the
training data 3 times over.

## Design

No vector database needed at this scale (~170K records). Brute-force
cosine similarity over a single in-memory matrix is fast enough.

1. `scripts/build_index.py` - embeds every `dataset.jsonl` instruction
   with `sentence-transformers/all-MiniLM-L6-v2`, saves
   `data/processed/rag_index/embeddings.npy` + `records.json`. Rerun
   whenever `dataset.jsonl` changes (~25 seconds for 170K records).
2. `scripts/test_model.py` - embeds the user's question, finds the
   closest match by dot product (embeddings are normalized), routes
   by similarity score. Flag-shaped questions go through an extra
   command-scoping step first (below) before this score is even
   computed.

| Score | Behaviour |
|---|---|
| >= 0.70 (global) / 0.60 (command-scoped) | Show the real trained answer directly, no caveat |
| 0.55-0.70 (global) / 0.40-0.60 (scoped) | Show the real trained answer with a "closest match, may not be exact" caveat |
| below that | No reliable data - fall back to LoRA generation, but label it "unverified guess" |

Scoped questions use lower thresholds than global search because
noise is already eliminated by the scoping step - the same absolute
score means a more reliable match once the search space is narrowed
to one command. Thresholds were picked empirically: real matches
scored 0.70-1.00 in testing, genuinely out-of-scope questions
(`wobblesort`, `failover cluster`) scored 0.32-0.51. There is no LLM
call at all on the high/medium confidence path - the answer is
retrieved verbatim from the same `dataset.jsonl` that was already
audited for quality, so it can't hallucinate.

## Command-Scoped, Case-Sensitive Retrieval

Plain similarity search isn't enough for flag-specific questions -
two different reasons, both found via live testing rather than
inspection:

1. **Cross-command contamination.** `"what does the -w flag do in
   printf?"` (printf has no `-w`) matched `od`'s or `pr`'s real `-w`
   data with high confidence, because nothing checked that the
   matched record's command was actually the one named in the query.
2. **Case blindness.** No-dash, casual questions (`"ls l"` vs
   `"ls L"`) differ only by a single letter's case, and the embedding
   model barely distinguishes them - 107 (command, letter) pairs in
   the dataset have genuinely different answers for the two cases.

Fix, in three parts (`scripts/test_model.py`):

-   Every `dataset.jsonl` row is tagged with its source `command`
    (added in `build_dataset.py`).
-   `find_mentioned_command()` matches a known command name in the
    query using word-boundary-safe regex (`(?<![\w-])name(?![\w-])`).
    Originally sorted longest-name-first and returned the first match,
    with length as the only priority signal - broke down for
    EQUAL-length names: `"nft"` and `"add"` (a real, unrelated Windows
    CLI command) are both 3 characters, so `"what does nft add rule
    do?"` could non-deterministically resolve to `"add"` instead of
    `"nft"`, scoping the whole search to the wrong command (same story
    for `"dnf"` losing to the real Windows `"list"` command). Fixed by
    scanning ALL matching command names and preferring whichever one
    starts EARLIEST in the question text, falling back to length only
    on a true tie - the real command is always named before any
    flag/subcommand word in this project's "what does X Y do?"
    phrasing, so position is a far more reliable signal than length
    alone. Also now registers a hyphenated variant for every
    space-stored command name (PowerShell/Windows cmdlets are stored
    as `"get item"`, but real syntax and natural questions always use
    `"Get-Item"`) so flag questions about them can be command-scoped at
    all - previously fell through to fully unscoped search every time.
-   If a command is named, search is restricted to only that
    command's `parameter`/`overview` records
    (`find_command_scoped_candidates`). Within that scope, an exact,
    case-sensitive, word-boundary flag match is tried first
    (`find_exact_flag_within`) - both for dashed flags (`-w`) and
    bare, no-dash flags (`find_bare_flag_after_command`). The bare-flag
    check went through two iterations: the first only recognized the
    literal generation-template phrasing ("X do?"/"X ne yapar?"), which
    missed freeform sentences ("how can i use grep E" still fell
    through to unscoped search and got the wrong case). Fixed by
    checking the word immediately after the mentioned command against
    that command's *actual* known bare-flag set (built from the
    dataset itself) - works regardless of sentence structure, so
    `"ls l"` and `"ls L"` resolve to different, correct records however
    they're phrased.
-   If a command is named but has zero matching flag data (like
    printf and `-w`), the answer is forced to the honest "unverified
    guess" fallback - it never silently falls through to a different
    command's answer. This same honest fallback now ALSO triggers when
    the command has *other* flag data but not the *specific* one asked
    about (e.g. `Get-Item -ErrorAction` - a generic PowerShell common
    parameter, never documented per-cmdlet) - previously this case
    wasn't caught at all, and a scoped-but-wrong flag (`-UseTransaction`
    in this example) could win by embedding similarity within the small
    scoped pool and be shown with full, unwarranted confidence.
-   Non-flag questions that still name a known command (`"what does
    docker network ls do?"`) are now ALSO scoped, to that command's
    records across every category, not just parameter/overview -
    previously only flag-shaped questions got any scoping at all, so
    even a distinctive multi-word command name could lose to an
    unrelated record in fully global search despite the correct answer
    existing in the dataset. Deliberately skipped when the question
    contains `"+"` (key-combo notation like `"Alt+Tab"`) - a first
    version applied this unconditionally and broke the well-established
    `"Alt+Tab"` answer, which was already working correctly via plain
    global search, by scoping it to an unrelated real command literally
    named `"Tab"`.

## Validated Fixes (before/after)

| Question | Before RAG | After RAG |
|---|---|---|
| `what does F2 do?` | "Start an interactive shell session..." (wrong) | "Rename the selected item" (correct, 1.00 similarity) |
| `can you list grep commands and what they do?` | Invented flags that don't exist | Real 5 flags, correct |
| `how do i open file explorer quickly` | `Ctrl + Shift + E` (wrong shortcut) | `Windows key + E` (correct) |
| `what does the wobblesort command do?` (fake command) | Confidently wrong description | Labeled "no reliable data, unverified guess" |
| `what does the -w flag do in printf?` (printf has no `-w`) | Confidently returned `od`'s or `pr`'s real `-w` data | Labeled "no reliable data, unverified guess" |
| `what does ls l do?` vs `what does ls L do?` | Could return either answer regardless of which was asked (embedding is near case-blind) | Correctly resolves to `-l` (long format) vs `-L` (dereference symlinks) respectively |
| `how can i use grep E?` (freeform, not the exact template phrasing) | Fell through to unscoped search, returned grep `-e`'s data instead of `-E`'s | Correctly resolves to `-E` (extended regex) |
| `what does Get-ADUser -Filter do?`, `Register-ScheduledTask`, `New-NetFirewallRule`, `Get-DnsServerZone` | No data at all (source didn't exist) | Correct, exact answers from `windows-powershell-docs` |
| `what does crontab -e do?`, `iptables -A`, `ufw enable`, `nft --numeric` | No data at all (source didn't exist) | Correct, exact answers from the new troff-man and DocBook sources |
| `what does ssh -A do?`, `scp -r`, `StrictHostKeyChecking` in `ssh_config`, `ssh-keygen -t` | No data at all (source didn't exist) | Correct, exact answers from the new mdoc source |
| `what does dnf --best do?`, `cachedir` in `dnf.conf`, `apt-get -y`, `apt-cache search` | No data at all (source didn't exist) | Correct, exact answers from the new DocBook (apt) and RST (dnf) sources |
| `what does apt-get -y do?`, `ssh-keygen -t`, `apt-cache search` | Full parameter data existed but the matching real-world tldr example was orphaned under a wrongly-named duplicate record (`"apt get"`, `"ssh keygen"`, `"apt cache"`) and never reached the answer | Single merged record per command, real examples included |
| `what does systemd-analyze blame do?`, `systemctl status`, `journalctl -f` | Subcommand names were known but their descriptions were never stored - fell through to an unrelated answer | Correct subcommand description returned |
| `what is the syntax of Get-Process?` | A cleanup regex bug deleted the actual syntax, leaving only a bare `### Name (Default)` heading (affected 44% of PowerShell records) | Full, correct syntax code block |
| `what does git rebase -i do?` | Wrong, unrelated answer (`--rerere-autoupdate`) - `-i` wasn't in the dataset at all, only 2 of git rebase's real flags were | Correct "make a list of commits to rebase interactively" answer |
| `what does the -WhatIf parameter of Remove-Item do?` | Correct start, but the answer had "### CommonParameters" and its whole boilerplate paragraph appended (affected the last documented parameter of nearly every PowerShell cmdlet) | Clean two-sentence answer, nothing appended |
| `what does git stash pop do?` | Wrong, unrelated answer - git's own subcommands (`pop`/`push`/`apply`...) live in a `COMMANDS` section the parser never read | Correct "remove a single stashed state..." answer |
| `what does git config get do?`, `git remote add`, `git worktree list` | No data (subcommand terms written without backticks or a dash weren't recognized at all) | Correct answers for all three |
| `what does nft add rule do?`, `nft delete table`, `nft list ruleset` | Wrong/hallucinated answers (8 of 10 nftables test questions), including one that returned unrelated Windows disk-management content | Correct, object-type-disambiguated answers |
| `what does dnf install do?`, `dnf remove`, `dnf search`, `dnf list`, `dnf clean all` | No data at all - dnf's own commands were never parsed, only its flags were; `dnf clean all` fell back to a Windows disk-wipe description | Correct answers for all of dnf's 28 documented commands |
| `what does git cherry-pick --continue do?`, `git diff-tree`, `git rev-list` | Wrong, unrelated answers - 86 git subcommands with a hyphen in their own name were stored as "git cherry pick" etc., not matching how anyone actually types them | Correct answers, command names now match real usage |
| `what does git reset --hard do?`, `git cherry-pick --continue`/`--abort` | No data - these flags live in `DESCRIPTION`/"SEQUENCER SUBCOMMANDS" sections the parser never scanned | Correct answers |
| `what does dnf list do?` (again, after the dnf fix above) | Still wrong - `find_mentioned_command` had no tiebreak for equal-length command names, so `"dnf"` sometimes lost to the real, unrelated Windows `"list"` command | Correctly scoped to `dnf`, correct answer |
| `what does the -ErrorAction parameter of Get-Item do?` | Confidently wrong (`-UseTransaction`'s answer) with no caveat - `Get-Item` (hyphenated, as anyone types it) never matched the dataset's `"get item"` (space-stored) command name, so no scoping ever applied | Honestly labeled low-confidence guess instead of a confident wrong answer |
| `can you list all grep options?`, `can you list all nft flags?` | Wrong - matched Windows' own (real but unrelated) `list` diskpart command, since it appeared earlier in the sentence than the actual subject | Correctly scoped to `grep`/`nft`, full flag list returned |
| `what does Restart do in a systemd service unit?`, `ExecStart`, `TimeoutStartSec` | Wrong - `"service"` (a real, unrelated SysV command) matched instead of `systemd.service`, since the dataset stores the dotted man-page name and nobody phrases a question that way | Correctly scoped to `systemd.service`, exact directive answer |
| `what does User do in a systemd service unit?`, `WorkingDirectory`, `Environment` | Wrong - these directives are real data, but filed under `systemd.exec` (per systemd's own cross-references), which the search never checked | Correct answer, found via the shared-directive pages systemd's own docs point to |
| `what does PrtScn do?` (bare, no "shortcut"/"keyboard" keyword) | Fell through to unrestricted search and lost to an unrelated DOSKEY entry - the shortcut pool was built from each answer's own text, and this one doesn't repeat "PrtScn" | Correctly scoped to the shortcut pool (now built from source path, not answer text), correct answer |
| `what does Ctrl+O do?`, `Ctrl+P`, `Ctrl+S` (genuinely missing from the source) | Confidently wrong - returned a different shortcut's answer (e.g. `Ctrl+A`'s) at 0.84 similarity, since the shortcut pool is almost entirely one repeated template and the model can't reliably tell single letters apart within it | Honestly labeled low-confidence guess instead of a confident wrong answer |
| `what does apt-key list do?` | Wrong - `apt-key` wasn't a known command (missing from the source entirely), so only the generic `list` matched | `apt-key` added as a real source (reconstructed from Debian's own currently-maintained man page); now correctly resolves to `apt-key`'s own `list` subcommand |
| `what does networkctl do?`, `apt-key do?`, `systemctl do?`, `apt-get do?` (bare command name, not a subcommand/flag) | Silently wrong for any DocBook-family command with parameters - `parse_systemd_xml` had two loop variables both named `description`, so the real top-level summary was overwritten by whichever flag was processed last (e.g. `networkctl`'s bare description returned `--stdin`'s text instead) | Fixed at the source (renamed the shadowing loop variables) and rebuilt; correct top-level description for every affected command |
| `what does net use do?`, `net view`, `net share`, `net start`, `net accounts`... (22 subcommands) | No data at all - only `net print`/`net user` existed in the source | Added from Microsoft's own archived reference; correct, exact answers |
| `what does Windows key + Pause do?`, `Windows key + 5` | No data (missing shortcut); `+ 5` also failed even after the shortcut was added, since `SHORTCUT_COMBO_PATTERN` didn't recognize `"Windows key +"` (only bare `"Win+"`) and the stored record uses a generic `"...+ number"` placeholder | Shortcut added from Microsoft's live shortcuts page; retrieval broadened to recognize `"Windows key +"`/`"Windows logo key +"`, plus a digit -> `"number"` fallback so any specific digit matches the generic record |
| `how do i attach a portable service image?`, `how do i detach a portable service?` (portablectl intent questions that never name the tool) | Wrong - hijacked by the real, unrelated SysV `service` command, matched as an incidental substring of "portable **service** image" | `"service"` added to `GENERIC_WORD_COMMAND_NAMES`; the all-category scoping branch now skips scoping entirely for any generic-word match instead of only deprioritizing it when another candidate exists - correctly resolves to `portablectl` (or an honest low-confidence guess) instead of confidently returning `service`'s answer |
| `how can i copy a file over ssh?`, `how can i rename a selected item?` (natural intent questions containing a word that's also a real Windows command name) | Wrong - `"copy"` and `"rename"` are real Windows commands, so these got scoped to `copy`'s/`rename`'s own records instead of the real answer (`scp`'s intent record, `F2`'s shortcut record) - the same failure as the `service` row above, but for words never added to `GENERIC_WORD_COMMAND_NAMES` | Added `INTENT_PHRASE_PATTERN` ("how do/can I...", "I want to...", "I need...") - any question matching it skips command-scoping entirely, since unrestricted global search reliably finds the right intent record (0.75-0.98 similarity, verified) regardless of which incidental word triggered the false match. Generalizes the fix above instead of enumerating every common verb that's also a command name |

| `what does -it mean in docker exec?`, `what does -la do in ls?` | No data - `-i`/`-t` and `-l`/`-a` were both already documented individually, but the bundled shell-convention spelling (`-it`, `-la`) never matched anything exact, so these fell to the generative fallback despite the real data existing | `find_bundled_short_flags_within` splits a `-XY` token into individual `-X`/`-Y` and reuses the existing exact-match search - works for any complete-reference command, not just Docker |
| `what does iptables --dport do?`, `what does sha256sum -c do?`, `what does nft describe do?` | No data - `--dport` lived in a deliberately-excluded source (`iptables-extensions.8.in`'s real content, `extensions/*.man`); `sha256sum` wasn't a coreutils record at all (grouped under a shared `sha2 utilities` node the parser never split on); `describe` used a `<refsect2>` title pattern the subcommand scanner didn't recognize | All three added as real data (94-fragment iptables extensions source, checksum-family borrowing gate fix, two more nft subcommand title patterns) - see 02_Dataset_Pipeline.md items 48-49 for the full list found in this pass |
| `what is the -QueryDialect parameter of Invoke-CimMethod?`, `what is the -Filter parameter of Copy-Item?`, any answer sourced from a record containing markdown `**bold**` | Literal `**` characters shown to the user (e.g. "The acceptable values are: **WQL** or **CQL**") - `answer_question()` only ever stripped code-fence markers, never bold markers, and the GUI/CLI render plain text, not markdown | Found via a 25-record random spot-check of `dataset.jsonl` prompted by the user asking "are these answers actually understandable, not just present in the source data" - quantified at 12,630 of 174,623 records (7.2%). Fixed with a second `re.sub` pass in `answer_question()` stripping `**text**` to `text`, verified against the exact examples found plus a regression set |
| `what is a docker image?`, `what is a registry in docker?` | Confidently wrong, no caveat - matched the `docker image`/bare `docker` command's own overview record ("Manage images... Subcommands: build, history...", "docker [OPTIONS]") instead of answering the concept, because the question text is nearly identical by embedding to "what does docker image do?" and the dataset has zero real conceptual/glossary content to compete with the wrong match (see Known Limitations #6 below) | Added `CONCEPT_QUESTION_PATTERN` (`^what is an? `) - confirmed via a full dataset scan that this exact phrasing never occurs in any existing question template, so it's safe to treat as a signal with no legitimate scoped-command questions to break. When it matches AND a command name is incidentally present in the question, the answer is forced to the honest low-confidence fallback instead of trusting the retrieval score - the base model's own general knowledge then gives a genuinely good conceptual answer. `what is a container?` (no literal "docker" in the question, so no command is detected as mentioned) is only partially fixed by this - still matches the wrong record, but now with the "closest match, may not be exact" caveat instead of full confidence, since scoring naturally landed in the medium band this time |

## Known Limitations (not yet fixed)

1. **Turkish queries route badly.** `all-MiniLM-L6-v2` is
   English-focused; a Turkish question about `grep` matched `mtr`
   (traceroute) instead. Fix would be swapping to a multilingual
   embedding model (e.g. `paraphrase-multilingual-MiniLM-L12-v2`) and
   rebuilding the index - deprioritized for now, not urgent.
2. **The low-confidence fallback path ignores retrieval entirely.**
   When no good match is found, `generate_with_model()` asks the raw
   model the bare question with no retrieved context injected - the
   one place RAG's grounding would help most (a genuinely unclear
   question) is where it currently contributes nothing. A standard
   RAG design would inject the top few candidates into the prompt
   instead of discarding them. Not implemented - would need the
   fallback path restructured and re-tested against the small model's
   ability to read and cite injected context correctly. (This path now
   runs the plain base model - the LoRA adapter isn't loaded at all
   anymore, see 03_LoRA_Training.md "LoRA Emekliye Ayrıldı" - which
   fixed a worse problem, the adapter fabricating fake commands for
   anything outside its trained format, but doesn't change this
   particular limitation.) **Planned next** (2026-08-13): shrink this
   ~8.7% generative-fallback slice further so more of it resolves
   through real retrieved data instead of free generation - explicitly
   deferred, not started, pending the user's go-ahead (see
   05_Roadmap.md).
3. **git's diff-options family has ~1,320 internal name collisions.**
   `diff-options.adoc` (shared by `git diff`, `git diff-index`,
   `git diff-tree`...) defines the same bare value name ("no", "plain",
   "default"...) more than once, meaning something different depending
   on which parent flag introduces it. Unlike nftables, AsciiDoc has no
   `<cmdsynopsis>`-equivalent marker to hang disambiguating context on
   - would need a comparably-designed but separate mechanism. Affects
   overview/list-style answers for this command family; individual
   named-flag questions are unaffected.
4. **A handful of very short but valid descriptions get silently
   dropped.** `docker network ls`'s real description ("List networks",
   13 characters) never reaches the dataset because `build_dataset.py`
   rejects any answer under 15 characters - meant to catch garbage
   extraction results, not deliberately terse real ones. ~57 similarly
   short commands exist, but most are genuine low-value truncations
   (not complete real answers) - fixing this needs a way to tell them
   apart, not just a lower length threshold. `apt list --all-versions`
   is the same class of gap for a different reason: it's real, but only
   ever mentioned in prose inside the `list` subcommand's own
   description, not as its own extractable option entry.
5. **The `apt-get moo` easter egg and 8 keyboard shortcuts genuinely
   have no source at all.** `apt-get moo` isn't documented in
   `apt-get.8.xml` (it was never meant to be documented anywhere); and
   `Ctrl+O`/`+P`/`+S`/`+G`/`+J`/`+K`/`+M`/`+Q`/`Ctrl+Shift+T` aren't on
   Microsoft's own live "Keyboard shortcuts in Windows" page either
   (confirmed directly - these are app-specific behaviors, not
   OS-guaranteed shortcuts). Both handled gracefully (an honest
   low-confidence guess, not a confident wrong answer) rather than
   fabricated. `apt-key`, the `net` command family, 5 systemd CLI tools,
   and 2 other keyboard shortcuts were previously in this category but
   turned out to have real, findable sources - see the Validated Fixes
   table above.
6. **Multi-item markdown lists collapse into a confusing run-on line.**
   ~6,392 of 174,623 records (3.7%) contain 2+ ` - ` sequences with no
   newline in `response` - the source markdown's line breaks between list
   items were lost somewhere in extraction/dataset-building, so e.g. "Valid
   types include: -- - 'bool' - 'int' - 'expiry-date'..." reads as one
   run-on sentence instead of a clear list. Found in the same spot-check
   that found the `**bold**` issue (see the Validated Fixes table).
   **Deliberately not auto-fixed yet** - unlike stripping `**`, reliably
   telling "a dash that starts a list item" apart from "a dash used
   mid-sentence" (hyphenated words, ranges, etc.) from the flattened text
   alone is genuinely ambiguous; a wrong heuristic could silently mangle
   more answers than it fixes. Needs a decision on approach (fix at
   extraction time so line breaks survive, vs. a carefully-scoped display-
   time heuristic) before touching it.
7. **No conceptual/glossary content exists at all - every source is a
   command/flag reference, not a tutorial.** There is no dataset entry
   anywhere answering "what is a Docker image", "what is a container",
   "what is a registry", etc. - confirmed by direct search, zero hits.
   This is true across the whole project, not just Docker: every source
   was chosen specifically for complete command/flag coverage (see
   01_Project_Overview.md's Data Sources list), never for the separate
   conceptual/getting-started documentation the same tools also publish
   (e.g. Docker's own docs.docker.com guides, git's `gitglossary`).
   Practical effect: any question phrased as a genuine concept lookup
   rather than a command lookup either (a) risks a wrong match against a
   same-named command's reference entry (see the `CONCEPT_QUESTION_PATTERN`
   fix above, which catches the worst case but not every phrasing), or
   (b) falls through to the ungrounded generative fallback - which,
   encouragingly, tends to answer basic IT concepts (what's a Docker
   image, a container, a registry) reasonably well from the base model's
   own general knowledge, since these are common enough terms. **Not
   fixed, deliberately** - adding real glossary sources is a separate,
   larger scoping decision the user chose not to take on in the same pass
   as the quick retrieval fix above.

## Dependencies

`sentence-transformers` added to `requirements.txt` (was empty
before this addition; now lists all real project dependencies).
Updated again 2026-08-13: `peft`/`trl`/`datasets`/`accelerate` removed
after `scripts/train.py` was deleted (LoRA retired, see
03_LoRA_Training.md) - `requirements.txt` now only lists what the live
RAG/generation pipeline actually imports (`torch`, `transformers`,
`sentence-transformers`, `numpy`).
