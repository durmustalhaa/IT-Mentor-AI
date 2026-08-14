# Testing Results

## Status

RAG is live and validated against the current (174,623-example)
index. Measured directly against ~763 realistic questions: ~90%+ get
a real RAG-retrieved answer (not a generated guess) - see
02_Dataset_Pipeline.md items 47-49 for how this was measured and the
gaps closed as a result. `qwen-it-mentor-v6` (the LoRA adapter) is no
longer loaded anywhere in the live pipeline - the remaining ~8.7%
generative fallback runs the plain base model instead (see
03_LoRA_Training.md "LoRA Emekliye Ayrıldı"), so the old "model
predates most of the dataset" staleness concern no longer applies:
there's no LoRA-adapted knowledge left in the pipeline to go stale.
Shrinking that ~8.7% slice further is planned but deferred by
explicit user request - see 05_Roadmap.md.

## What Works Well

-   Intent-mapping for well-covered commands: "I want to copy a file
    over ssh" -> `scp ...`, "how do i lock my computer" -> `Windows
    key + L`, "how do i see whats using up my disk space" -> `df`
-   Exact recall via RAG for anything with real trained data:
    keyboard shortcuts, full flag lists for coreutils/grep/Docker/
    systemd/nftables commands, `git`/PowerShell parameter questions,
    classic Windows CLI tools (`netstat`, `schtasks`, `netsh`,
    `robocopy`, `ping`, `attrib`...), Windows Server PowerShell
    modules (`Get-ADUser`, `Register-ScheduledTask`,
    `New-NetFirewallRule`, `Get-DnsServerZone`...), Linux
    firewall/scheduling tools (`crontab`, `iptables`, `ufw`), OpenSSH
    (`ssh`, `sshd`, `scp`, `sftp`, `ssh-keygen`, `ssh_config`
    directives, etc.), and now package managers (`apt-get`,
    `apt-cache`, `apt-mark`, `dnf`, `dnf.conf` directives)
-   Command-scoped, case-sensitive flag disambiguation: `ls -l` vs
    `ls -L`, `rm -R`, `grep -i` vs `grep -I`, and the same questions
    phrased without a dash and in freeform sentences (`"ls l"`,
    `"how can i use grep E"`) all route to the correct flag, not a
    same-letter flag from an unrelated command
-   Honest refusal for genuinely out-of-scope questions (fake
    commands, topics with no training data, or a real command asked
    about a flag it doesn't have) instead of confident hallucination

## Known Issues (open)

### `apt-get moo` and `apt list --all-versions` still have no dedicated source

`apt-get moo` is a genuine, undocumented easter egg - it isn't in
`apt-get.8.xml` at all (the string "moo" there only appears inside an
unrelated example for `satisfy`), and unlike `apt-key` there is no
official man page anywhere to reconstruct from, since it was never
meant to be documented. Not fixed, and likely never will be without
hand-authoring, which this project avoids. `apt list --all-versions`
is real but only mentioned in prose inside the `list` subcommand's own
description block, not as an extractable `<option>` entry of its own -
same class of gap as the `docker network ls` issue below (a parser
completeness problem, not a missing source).

### git's own diff-options family has ~1,320 internal name collisions

Discovered while verifying the 150-question audit's fixes: git's
`diff-options.adoc` (shared by `git diff`, `git diff-index`,
`git diff-files`, `git diff-tree`...) defines the SAME bare value name
("no", "plain", "default"...) more than once, each meaning something
different depending on which parent flag introduces it (`--color-moved`
vs `--ignore-*`-family options). No `<cmdsynopsis>`-style marker exists
in AsciiDoc to hang disambiguating context on the way the nftables fix
does for DocBook - would need a comparable but separately-designed
mechanism. Not fixed - affects overview/list-style answers for the
git diff-comparison family, individual named-flag questions are
unaffected.

### A handful of very short but valid descriptions get silently
    dropped

`docker network ls`'s real description ("List networks", 13 characters)
never reached the dataset because `build_dataset.py`'s `add()` rejects
any answer under 15 characters (meant to catch empty/garbage extraction
results, not deliberately terse real ones) - the command falls back to
its nearest scoped match (a `-f`/`--filter` flag's description) instead
of an honest "no data" or the real short answer. Checking the scope
found ~57 similarly-short commands, but most of those are genuinely
low-value single-word truncations (PowerShell `about_*` provider
topics), not complete real answers like this one - fixing it properly
needs a way to tell "terse but complete" apart from "truncated junk",
not just a lower length threshold. Not fixed.

### Turkish queries route badly

The embedding model (`all-MiniLM-L6-v2`) is English-focused. A
Turkish query about searching a file's contents matched `mtr`
(traceroute) instead of `grep`. Deprioritized per explicit decision -
not currently important for this project's usage.

### No remaining tool-family gaps from the original list

Every tool family originally identified as a gap (coreutils, grep,
Docker, systemd, classic Windows CLI, Active Directory/networking/
firewall PowerShell modules, nftables, cron, iptables, ufw,
ssh/OpenSSH, apt, dnf) now has a complete-reference source. `dpkg`
(POD format) is an optional, lower-priority follow-up - not part of
the original gap list, and most users interact with the Debian
package system through `apt` rather than `dpkg` directly.

## Resolved Since Last Update

-   Git was never in the dataset at all -> fixed, real git data now
    present and tested
-   grep intent was entirely absent -> fixed via curated Linux source,
    then fully fixed with grep's own texinfo manual (complete flag
    list, not just tldr examples)
-   Overview category hallucinated fictional content -> fixed via RAG
    (was not fixable via more training - see the 3-epoch experiment)
-   F2 and other Windows shortcuts answered with unrelated made-up
    text -> fixed via the windows-shortcuts source + RAG
-   RAG couldn't tell "related" from "actually answers this" (`what
    does grep -i do?` falling back to grep's general description) ->
    fixed via command-scoped retrieval + case-sensitive exact-match
    (see 07_RAG.md)
-   Cross-command flag contamination (`printf -w` returning `od`'s or
    `pr`'s `-w`) -> fixed via the same command-scoping mechanism, plus
    an honest "this command has no such flag" fallback when the named
    command genuinely has no matching data
-   Case-only flag ambiguity in no-dash intent questions (`"ls l"` vs
    `"ls L"` - 107 (command, letter) pairs affected) -> fixed
-   `nl` and other commands with nested texinfo tables silently
    losing most of their flags -> fixed (depth-tracking parser)
-   `dir`/`vdir` and checksum commands (`md5sum` etc.) having zero
    documented options -> fixed (generalized option-borrowing)
-   A bogus "Multi-call" command entry with a corrupted description ->
    fixed (removed)
-   33 commands (`cp`, `mv`, `ls`, `chmod`, `sort`... ) silently
    missing macro-defined flags -> fixed (texinfo macro expansion,
    +276 parameters recovered)
-   Coreutils descriptions ending mid-sentence or leaking raw texinfo
    syntax (`tail`, `ls`, `join`, `printf`, `dircolors`...) -> fixed
    (dangling-sentence trim, `@menu` stripping, nested-macro-safe
    `@xref` removal, several unhandled escape sequences)
-   Docker/systemd added as new complete-reference sources (143 + 16
    commands) - each surfaced its own bugs along the way (markdown-
    link-wrapped flag names, wrong description selected, a
    cross-source dedup fix that briefly regressed PowerShell's
    multi-version records, systemd's inconsistent section titles
    hiding most of its options) -> all fixed, see
    02_Dataset_Pipeline.md items 15-20
-   ~869 already-cloned Windows CLI command docs (`netstat`,
    `schtasks`, `netsh`, `attrib`, `robocopy`...) were silently
    producing zero parameters each due to a table-format the parser
    didn't recognize -> fixed with a fallback table extractor, plus 4
    more bugs found along the way (escaped/backtick-protected pipes
    breaking table splits, fake subcommand-index tables mistaken for
    flags, repeated table headers mistaken for flags) -> 4,793
    parameters recovered
-   Active Directory, Windows Firewall, DNS/DHCP, and networking
    PowerShell coverage was entirely absent -> fixed by adding
    `windows-powershell-docs` (a separate Microsoft repo covering ~140
    Windows Server role modules, curated to 10 directly relevant
    ones) - reused the already-hardened PowerShell parser as-is,
    8,257 parameters recovered across 695 cmdlets, the single largest
    addition in the project
-   nftables added via the same DocBook parser already built for
    systemd, after generalizing it to handle nftables' combined
    `-h/--help`-style option syntax (systemd always uses separate
    `<term>` elements per alias)
-   cron, iptables, and ufw still had no complete-reference source ->
    built a new troff/man-page parser and validated it against all
    three together; found and fixed 5 format-variance bugs along the
    way (two different flag-name conventions, nested option lists
    that would have produced fake top-level flags, bolded punctuation
    mistaken for flag names, and two separate description-extraction
    bugs - first grabbing only a truncated first word, then
    over-correcting to swallow an entire 8,860-character multi-
    paragraph section)
-   ssh/OpenSSH still had no complete-reference source -> built a
    second new parser (mdoc, a different macro dialect from
    troff-man) and validated against all 15 OpenSSH manuals together;
    fixed a macro-composition leak, a broad word-stripping bug that
    was corrupting ordinary prose (`on`/`An` collided with real macro
    names), a multi-syntax-variant flag (`ssh -L`) that would have
    produced 3 content-less duplicate entries, and a list-closing bug
    that let one command's description absorb the entire trailing
    bibliography section - 519 parameters recovered across 15 manuals
-   apt and dnf (package managers) still had no complete-reference
    source -> apt reused the existing DocBook parser (same format as
    systemd/nftables, only needed a small entity-name generalization);
    dnf needed a third new parser (reStructuredText definition lists)
    - fixed a comma-splitting bug where a flag's own argument syntax
    (`--whatdepends <capability>[,<capability>...]`) was mistaken for
    multiple aliases, and a two-part bug that silently produced zero
    parameters for `dnf.conf`'s dash-less config directives - 389
    parameters recovered across 4 files, closing the last
    originally-identified tool-family gap
-   Verifying the apt/dnf merge found `apt-docs`/`dnf-docs` were never
    added to `COMPLETE_REFERENCE_SOURCES`, so `apt`/`apt-get`/
    `apt-cache`/`dnf` each sat as two unmerged records -> fixed, which
    then surfaced an older, unrelated bug affecting `ssh-keygen` and
    `systemd-analyze` too: tldr's parser converts every filename
    hyphen to a space, which is correct for real subcommands
    (`docker-compose` -> "docker compose") but silently orphaned the
    tldr examples for standalone hyphenated binaries whose reference
    source correctly keeps the hyphen -> fixed in the merge step
    itself so real subcommand naming wasn't touched
-   Old Invoke-Command/AzureAD concern - no longer reproduces
    (upstream docs changed)
-   Subcommands weren't captured as retrievable data for DocBook-based
    tools - `"what does systemd-analyze blame do?"` fell through to an
    unrelated answer because the parser only ever extracted
    `<option>`/`<varname>` terms as parameters; a tool's own
    subcommands (`blame`, `verify`, `time`...) were folded into the
    main description as a one-line summary only, never captured as
    their own retrievable entry. Two different underlying XML
    structures needed handling: some tools (`systemctl`, `loginctl`)
    list subcommands in a "Commands" varlistentry - already partially
    read for the summary line, now also captured with each entry's own
    description; others (`systemd-analyze`) document each subcommand
    in its own `<refsect2>` titled with the full invocation
    (`systemd-analyze blame`) and no "Commands" section at all - needed
    a second extraction path matching on the refsect2 title's leading
    command name. Dataset grew by 754 examples (162,234 -> 162,988)
    from the recovered subcommand descriptions across the systemd
    tools that have them.
-   A manual live-question review (user-requested, before committing
    to a retrain) found and fixed several real bugs no automated audit
    had caught: a `build_dataset.py` regex was deleting 44% of
    PowerShell "syntax" answers (matched the harmless
    `[<CommonParameters>]` syntax placeholder as if it were a real doc
    heading, then deleted everything after it, including the closing
    code fence); the same root cause corrupted 2,193 PowerShell
    parameter descriptions (the LAST documented parameter of nearly
    every cmdlet absorbed the trailing "### CommonParameters"
    boilerplate section, because the extraction regex's section
    terminator only recognized dash-prefixed headings); git's AsciiDoc
    parser only recognized backtick-wrapped flag terms, silently
    dropping ~36% of git's own documented flags across 91 files that
    write them bare (`-i::` instead of `` `-i`::``) - `git rebase -i`
    had only 2 of its real ~58 flags; and several git commands
    (`git stash`, `git submodule`, `git remote`, `git worktree`,
    `git config`...) document real subcommands in a separate
    `COMMANDS` section that was never read at all, in three different
    description formats (indented, blank-line-separated, and
    flush-left) and with or without a leading dash - `git stash pop`
    and `git config get` both returned wrong or missing answers. The
    term-parsing was rewritten from an indentation-dependent regex to
    windowing between consecutive term markers (format-agnostic), which
    initially over-matched other AsciiDoc definition lists (example
    command lines, interactive-menu descriptions) as if they were real
    subcommands - fixed with a bare-identifier check (dash-prefixed
    terms are always accepted; bare terms must look like a real
    identifier, no spaces or stray punctuation). All fixed and verified
    live; dataset grew from 162,988 to 171,559.
-   A structured, 150-question audit (10+ fresh questions per source,
    none reused from earlier checks) found the four largest bugs of
    the project so far: nftables was badly broken (8 of 10 test
    questions wrong - `add`/`delete`/`list`/`flush` collide across
    table/chain/rule with no disambiguating context); dnf's own
    commands (`install`/`remove`/`search`/`list`/`clean`...) were
    never captured at all, only its flags were (a completely different
    RST structure the parser never targeted); 86 git subcommands with
    a hyphen in their own name were misnamed (`git cherry-pick` stored
    as "git cherry pick", breaking retrieval for very common commands
    like `git-diff-tree`, `git-rev-list`); and several git flags/
    subcommands live in sections (`DESCRIPTION`, "SEQUENCER
    SUBCOMMANDS") the parser never scanned (`git reset --hard`, `git
    cherry-pick --continue`). All four fixed and verified live -
    dataset grew from 171,559 to 172,126. Verifying these fixes then
    surfaced a genuine retrieval bug (`find_mentioned_command` had no
    tiebreak for equal-length command names, so `nft`/`dnf` sometimes
    lost to unrelated same-length Windows commands `add`/`list`) and a
    duplicate-question bug (a bare-flag short-question collided with a
    real command's identically phrased question) - both fixed; dataset
    settled at 170,085 after removing the collision-guard's duplicates.
-   A second, fully fresh 150-question audit found one real code bug:
    `docker push`/`docker load`'s stored examples were the wrong code
    block from a multi-step tutorial (a "before" state or prerequisite
    step, not the command itself) - fixed by scoping to the `##
    Examples` section and preferring a block that actually invokes the
    command or one of its aliases. Also fixed two cosmetic leaks
    (Markdown image alt-text, AsciiDoc `[[anchor]]` markers). Two other
    findings were confirmed as genuine source-content gaps rather than
    bugs - `net use` and most other `net` subcommands are absent from
    the cloned `windows-docs` repo entirely, and two keyboard shortcuts
    (`Windows key + Pause`, `Windows key + Number`) aren't in the
    curated shortcuts file - deliberately left unfixed rather than
    hand-authoring plausible content, since every answer in this
    dataset is meant to trace back to a real source. Dataset: 170,085
    -> 170,081.
-   A third, 438-question audit (30 fresh questions per subject) found
    no new dataset-content bugs, but five more `test_model.py`
    retrieval bugs in the same family as the equal-length-tiebreak fix
    above: `"list"`/`"add"` (real but niche Windows diskpart/diskshadow
    commands) colliding with this project's own "can you **list** all X
    flags?" question template; systemd's dot-separated man page names
    (`systemd.service`) never matching natural space-separated phrasing
    ("systemd service unit"), losing to an unrelated real `service`
    command; directive names (`Restart=`) only being recognized
    immediately after a command name, missing natural phrasing that
    puts them at the start of the sentence; some directives
    (`User=`/`WorkingDirectory=`) being real data filed under a
    different, related systemd man page (`systemd.exec`) that the unit-
    type page itself points to; and the keyboard-shortcut pool being
    built from each answer's own text (missing shortcuts whose answer
    doesn't repeat a key name) with no exact-match check, so genuinely
    missing combos like `Ctrl+O` confidently returned a different,
    wrong shortcut's answer instead of an honest "no data". All five
    fixed and verified live, plus the full accumulated regression set;
    no dataset rebuild needed (170,081 unchanged - retrieval-layer
    only). Also confirmed, and left unfixed per the same no-fabrication
    principle: `apt-key` (no man page in the source at all), `apt-get
    moo` (undocumented easter egg), `apt list --all-versions` (real but
    only in prose, not an extractable option entry),
    `networkctl`/`busctl`/`machinectl`/`portablectl`/`resolvectl`
    (never curated as systemd sources), and 8 more missing keyboard
    shortcuts beyond the original 2 (`Ctrl+O`/`+P`/`+S`/`+G`/`+J`/`+K`/
    `+M`/`+Q`, `Ctrl+Shift+T`).
-   Went back through that gap list and closed every one that had a
    real, findable source: the 22-command `net` family (`net use`,
    `net view`, `net share`, `net start`/`stop`, `net accounts`... -
    Microsoft's own current windows-commands docs 404 for these, but
    a full archived reference for all of them still exists on
    `learn.microsoft.com/previous-versions`, so all 22 were fetched
    and added as local source files); `apt-key` (Debian still
    maintains and publishes its man page for currently-supported
    releases, just not in the specific upstream repo/version this
    project cloned - reconstructed as DocBook XML from that page);
    `networkctl`/`busctl`/`machinectl`/`portablectl`/`resolvectl`
    (the XML files were already sitting in the local systemd
    checkout, just never added to the curation allowlist); and 2 of
    the 10 missing keyboard shortcuts (`Windows key + Pause`,
    `Windows key + number` - both genuinely documented on Microsoft's
    live shortcuts page). `apt-get moo` and the 8 remaining `Ctrl+`
    shortcuts were confirmed to have no real source at all and were
    correctly left alone. While rebuilding the pipeline for these new
    sources, found and fixed a real, pre-existing bug affecting the
    WHOLE apt/systemd/nftables family: `parse_systemd_xml` had two
    loop variables named `description`, silently shadowing the
    command's own top-level description with its last-processed
    flag's description whenever the command had any parameters -
    `"what does networkctl do?"` was returning a flag description, not
    networkctl's real summary. Also fixed two smaller issues caught
    while verifying: a copy-pasted `net help <command>` boilerplate
    row that collided across all 16 new `net-*` files (removed, since
    the pre-existing `net-user.md` doesn't carry it either - it's an
    intentional editorial omission in the real source, not an
    oversight), and `"Windows key + 5"` not matching the newly-added
    generic `"Windows key + number"` shortcut record (fixed by
    broadening the shortcut trigger pattern and adding a digit ->
    `"number"` fallback). Dataset: 170,081 -> 171,687.
-   A 150-question spot check of just the new sources (20 questions
    each for `net`, `apt-key`, `networkctl`, `busctl`, `machinectl`,
    `portablectl`, `resolvectl`, plus 10 for the new shortcuts) found
    the content itself solid - every direct by-name question was
    correct - but one real retrieval bug: intent questions that never
    name a tool but happen to contain the word "service" as part of an
    unrelated phrase (`"how do i attach a portable service image?"`)
    were hijacked by the real, unrelated SysV `service` command, same
    root cause as the `list`/`grep` collision from the prior round.
    Fixed by adding `"service"` to `GENERIC_WORD_COMMAND_NAMES` and
    making the all-category scoping branch skip scoping entirely for
    any generic-word match, not just deprioritize it when another
    candidate exists.
-   Live-testing the new desktop GUI surfaced a bigger version of the
    same bug: `"how can i copy a file over ssh?"` - previously listed
    above as a working example - silently broke, returning Windows'
    `copy` command instead of `scp`'s real intent answer, because
    `"copy"` is also a real command name. Rather than keep adding
    individual words to `GENERIC_WORD_COMMAND_NAMES`, added a general
    `INTENT_PHRASE_PATTERN` that skips command-scoping entirely for any
    naturally-phrased intent question ("how do/can I...", "I want
    to...") - verified this fixes `copy`, `rename` (`"how can i rename
    a selected item?"` now correctly finds `F2`), and the `service`
    case above, without regressing bare "what does X do?" questions
    about those same words.
-   The LoRA adapter was found to have lost general conversational
    ability entirely - asking it "merhaba" fabricated a fake command
    reference instead of greeting back. Switched the generative
    fallback to run with the adapter disabled (`peft`'s
    `model.disable_adapter()`, no retraining needed) - see
    03_LoRA_Training.md.
-   Measured the actual generative-fallback rate directly (763 real
    test questions accumulated across every audit round this session):
    89.9% direct RAG match, 1.4% disclosed closest-match, 8.7%
    generative fallback. Traced and fixed the two biggest contributors
    (a bogus `"what is"` pseudo-command colliding with this project's
    own question template, git flags in unscanned AsciiDoc sections),
    then went further and closed four more real gaps found while
    reviewing what was left: iptables' most-asked flags (`--dport`,
    `--sport`, `--tcp-flags`...) via a previously-excluded-for-the-
    wrong-reason source, the whole checksum family (`b2sum`,
    `sha256sum` and siblings), two more nftables subcommands
    (`describe`/`export`/`monitor`), and bundled short flags
    (`docker exec -it`, `ls -la`). See 02_Dataset_Pipeline.md items
    47-49 for full detail. Dataset: 171,775 -> 174,623.

## Next Testing Pass

-   Retrain the LoRA model (`v7`) on the current 174,623-example
    dataset - the model has never seen more than half of the current
    data; worth reconsidering given the size of the gap
-   Optional: `dpkg` (POD format) as a lower-priority follow-up to
    apt/dnf
