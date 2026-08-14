# Dataset Pipeline

## Current Pipeline

download_sources.py -> index_documents.py -> documents.json ->
extract_commands.py -> commands.json -> build_dataset.py ->
dataset.jsonl -> audit_dataset.py -> dataset_audit.json ->
build_index.py -> RAG embedding index

## Sources and Formats

| Source | Format | Notes |
|---|---|---|
| powershell-docs | `powershell-md` | Restricted to real cmdlet reference folders |
| windows-docs | `powershell-md` | Administration articles |
| git-docs | `git-adoc` | AsciiDoc parser; top-level `Documentation/*.adoc` only |
| linux-docs | `tldr-md` | Curated to ~200 real sysadmin commands via `allowed_names` in config.py |
| windows-shortcuts | `shortcut-list` | Manually sourced from Microsoft's official keyboard-shortcuts page (not a git repo); one file, many records |
| coreutils-docs | `coreutils-texi` | GNU coreutils texinfo manual; one file, ~103 records; merged with matching tldr records |
| grep-docs | `gnu-table-texi` | GNU grep's own texinfo manual; same `@table @option`/`@item`/`@itemx` convention as most GNU manuals (different macro style than coreutils' custom `@optItem`) |
| docker-docs | `docker-cli-md` | docker/cli's own generated Markdown reference; one file per command, ~181 files -> 143 deduplicated records |
| systemd-docs | `systemd-docbook-xml` | systemd's own DocBook XML manual; curated allowlist of 21 files (CLI tools + most-used unit-file directive sets) out of 484 total |
| windows-docs | `powershell-md` (table fallback) | Also covers ~869 classic CMD command references under `administration/windows-commands/` - same source/format as PowerShell docs, but these use a Markdown *table* for parameters instead of PowerShell's `### -ParamName` subheading style, handled by a fallback extractor |
| windows-powershell-docs | `powershell-md` | Separate Microsoft repo, same `### -ParamName` format as powershell-docs - zero new parser code; curated to 10 Windows Server role modules (`ActiveDirectory`, `ScheduledTasks`, `NetSecurity`, DNS/DHCP, networking, `GroupPolicy`) out of ~140 available |
| nftables-docs | `systemd-docbook-xml` | nftables' own DocBook XML manual (`doc/nft.xml`) - same format as systemd, same parser, one small generalization (splits `-h/--help`-style combined short/long options, which systemd's convention never uses) |
| cron-docs, iptables-docs, ufw-docs | `troff-man` | Classic troff/man-page macros (`.TH`/`.SH`/`.TP`/`.B`/`\fB...\fP`) - the first new parser format built specifically for this round; three different upstream projects, same macro convention |
| ssh-docs | `mdoc-man` | OpenSSH's own manuals in BSD mdoc (`.Sh`/`.Nm`/`.Bl`/`.It Fl`/`.Ar`/`.Xr`...) - a *different* macro dialect from troff-man, not reusable; second new parser format this round |
| apt-docs | `systemd-docbook-xml` | apt's own DocBook XML manuals - same format as systemd/nftables, same parser; entity-name regex generalized for apt's dotted/hyphenated names (`&apt-author.jgunthorpe;`) |
| dnf-docs | `dnf-rst` | dnf's own reStructuredText manual - a definition-list style (`` ``term`` `` + indented paragraph); third new parser format, curated to the 2 files that are CLI/config reference (not Python API docs) |

Three source formats now produce **multiple** command records from a
single file (`shortcut-list`, `coreutils-texi`, `gnu-table-texi`)
instead of the usual one-record-per-file - handled via a separate
`MULTI_RECORD_PARSERS` dispatch path in `extract_commands.py`. Docker,
systemd, and windows-powershell-docs add more multi-file-per-source
formats (one record per file, some with their own parsers, some
reusing an existing one).

## Why coreutils, grep, Docker, and systemd Were Added

tldr-pages is a curated "common examples" cheatsheet, not an
exhaustive option reference - `grep`'s tldr page shows 8 example
usages, not its ~30 real flags. No amount of parsing improves this;
the source itself doesn't have the data. GNU coreutils' texinfo
manual documents every option for `ls`/`cp`/`mv`/`rm`/`chmod`/`chown`/
`df`/`du`/etc. completely, in one repo; GNU grep's own texinfo manual
does the same for grep. docker/cli publishes its own generated
Markdown CLI reference (complete option tables per command). systemd
publishes its own DocBook XML manual (`systemctl`, `journalctl`,
unit-file directives). Each needed its own parser (different upstream
project, different format), plus a merge step: the complete-reference
source supplies description/syntax/complete parameter list, tldr (if
present for the same command) contributes its real usage examples and
intent phrases into the same record.

**A separate, unplanned discovery:** while looking for new
"scheduled tasks / networking / firewall" sources, found that
`windows-docs` already contained ~869 classic Windows CLI command
references (`netstat`, `schtasks`, `netsh`, `attrib`, `robocopy`,
`ping`, `ipconfig`...) that were already being indexed and parsed -
just silently producing **zero parameters each**, because their
Markdown uses a table for the parameter list instead of PowerShell's
subheading convention, and the existing parser only recognized the
latter. Added a fallback table extractor - no new source needed, this
content was already cloned. Recovered 4,793 parameters this way alone
(more than every other source addition in this project combined).

**A second, much bigger version of the same discovery:** the
`MicrosoftDocs/windows-powershell-docs` repo (separate from
`PowerShell-Docs`) turned out to cover ~140 Windows Server role
modules - not just `ActiveDirectory`, but `ScheduledTasks`,
`NetSecurity` (Windows Firewall), DNS/DHCP, and general networking
too, all in the exact same Markdown format already supported. One
source addition closed four of the topics originally being chased
individually. Curated to 10 directly-relevant modules (~695 cmdlets,
8,257 parameters) rather than all ~140 (most are extremely narrow -
`ShieldedVMTemplate`, `HgsAttestation`, etc.).

**Nothing left incomplete from the original gap list.** apt and dnf
were added last, closing package managers - the final identified tool
family. `dpkg` (POD format docs) remains an optional, lower-priority
follow-up: it's a lower-level tool most users interact with through
apt anyway, and POD would be a fourth new parser format for
comparatively low marginal value.

## Bugs Found and Fixed (chronological)

1. **Git was never actually used.** Original pipeline only globbed
   `*.md`; git's docs are AsciiDoc. Fixed with a dedicated parser.
2. **Example code was being silently deleted.** ```` ```text ````-tagged
   git/Linux command blocks were caught by the output-cleaning regex
   meant for terminal-output dumps. Re-tagged as ```` ```bash ````.
3. **Parameter questions were too rigid.** Only one phrasing per flag
   existed; casual phrasing ("grep i" without a dash) failed even
   though "grep -i" worked. Expanded to 6 phrasing variants per flag.
4. **tldr had zero structured parameter data.** Added single-flag
   extraction from tldr's own example bullets (multi-flag bullets are
   skipped - attributing a combined description to one flag would be
   wrong).
5. **texinfo nested braces broke flag extraction.** Options like
   `--reference=@var{ref_file}` have a nested macro inside the
   argument; a naive `[^}]*` regex stopped at the inner `}`. Rewrote
   as a line-based parser that only needs the flag name, not the full
   macro span.
6. **Shared texinfo macros bled into descriptions.** GNU coreutils
   documents common options (`--help`, `--version`) via shared macros
   (`@choptH{cmd}`) inserted *after* a blank line following each
   option's real text. The parser was absorbing these macro lines
   into the previous option's description. Fixed by treating a blank
   line as the end of the current option's text.
7. **Stripped `@xref` left orphan periods.** `@xref{...}.` becomes
   just `.` on its own line once the reference is removed. Fixed to
   consume the trailing period too.
8. **RAG retrieval couldn't distinguish "topically related" from
   "actually answers this."** `"what does grep -i do"` scored high
   similarity against `"what does grep do"` (general description) and
   got shown confidently, without a caveat, even when the specific
   flag wasn't the real answer. **Fixed** - see item 12 below and
   07_RAG.md. Category-aware filtering wasn't enough by itself; needed
   command-name scoping too.
9. **texinfo nested tables silently dropped flags.** `extract_texi_parameters`
   used a non-greedy regex (`@table @samp(.*?)@end table`) to find one
   command's option block. Some commands (`nl`, others) have a SECOND,
   NESTED `@table @samp...@end table` inside one option's own
   description (to illustrate a format choice) - the regex matched the
   inner `@end table` and silently lost every flag documented after it
   (`nl` kept only 1 of 11 flag pairs). Rewrote as a depth-tracking
   line-by-line parser; only a `depth == 1` `@end table` ends the real
   option block. Same bug existed in grep's own parser
   (`extract_gnu_table_parameters`), fixed identically.
10. **Commands with no native option docs stayed empty.**
    `md5sum`/`b2sum`/`sha1sum` and `dir`/`vdir` don't document their
    own options - the texinfo source just says "see cksum" / "see ls"
    via a checksum macro or `@xref{X invocation}`. Generalized the
    existing checksum-specific borrow logic into a generic
    `borrows_from` mechanism: any command whose section has no
    parameters of its own but an `@xref{X invocation}` reference
    copies `X`'s parameter list (and syntax, if its own is also
    empty).
11. **A documentation section was mistaken for a command.**
    `@node Multi-call invocation` documents coreutils' multi-call
    binary mechanism, not a real utility - but the section-splitting
    regex captured "Multi-call" as if it were a command name, and its
    description came out corrupted (an unrelated `@menu` bullet list
    leaked into it). Fixed by comparing the node name against the
    real `@command{X}` name in the section's `@section` line; they
    only disagree for this one section.
12. **Shortcut option-macros were invisible to the parser.** ~20
    commands (`cp`, `mv`, `ls`, `chmod`, `chown`, `head`, `tail`,
    `sort`, `uniq`, `cut`, `dirname`, `printenv`, `mkfifo`, `mknod`...)
    define some of their options via a shared macro call
    (`@optZero{dirname}`, `@choptH{chmod}`) instead of a literal
    `@optItem{...}`. The parser only recognized the literal form, so
    every macro-defined flag was silently missing - found while
    manually auditing `dirname`/`printenv` (both looked like they had
    zero real options; both actually have one: `-z`/`--zero` and
    `-0`/`--null`). Added a general texinfo macro-expansion pass
    (recursive, handles macros that call other macros) that runs
    before parsing; recovered 276 missing parameters across 33
    commands.
13. **Cross-command flag contamination in retrieval.** A query naming
    a real flag of one command (`what does the -w flag do in
    printf?` - printf has no `-w`) could retrieve a different
    command's same-named flag (`od`'s or `pr`'s `-w`) with high
    confidence, because nothing verified the matched record's
    `command` field matched the one named in the question. Fixed by
    tagging every dataset row with its source `command` and adding
    command-scoped, word-boundary-verified retrieval - see 07_RAG.md.
14. **Case-only flag questions were ambiguous to the embedding
    model.** Casual/intent-style questions without a dash (`"ls l"`
    vs `"ls L"`) differ only by letter case, and the embedding model
    barely distinguishes them - 107 different (command, letter) pairs
    in the dataset have genuinely different answers for the lowercase
    vs. uppercase form (`ls l` = long format, `ls L` = dereference
    symlinks). First fix only covered the exact generation-template
    phrasing ("X do?"/"X ne yapar?") - freeform questions ("how can i
    use grep E") still fell through uncovered. Fixed properly by
    checking the word after the mentioned command against that
    command's *actual* known bare-flag set (built from the dataset
    itself), which works for any sentence structure - see 07_RAG.md.
15. **Docker table cells lost content to markdown-link-wrapped flag
    names.** Some Docker doc pages write flag names as
    `[`-w`](#workdir)` instead of plain `` `-w` `` - the link wrapper
    survived into the flag name. Stripped it before parsing.
16. **A stale, off-topic paragraph was chosen as a command's
    description.** For `docker`, the page's short one-line summary
    ("The base command for the Docker CLI") was being overridden by a
    longer but *unrelated* `## Description` section (about sudo
    permissions) because the description-selection heuristic simply
    preferred whichever text was longer. Dropped that heuristic -
    always use the short, reliably-on-topic summary.
17. **A deduplication fix collapsed unrelated data across the whole
    dataset.** Docker documents some commands twice (`docker build`
    appears under both `builder_build.md` and `image_build.md`, both
    resolving to the same short alias). The fix to keep only the
    richer one was first written generically ("same command name,
    same source -> keep the biggest") and it silently collapsed
    PowerShell's *intentional* multi-version cmdlet records (the same
    cmdlet documented separately for 5.1/7.4/7.5/7.6/7.7) from 2,438
    down to 585. Caught immediately via the per-source count check;
    scoped the fix to `docker-docs` only.
18. **systemd's inconsistent section titles hid most of its options.**
    `extract_texi_parameters`-style title-matching (looking for a
    section literally called "Options") works for most coreutils
    commands but not systemd's DocBook manual, which spreads options
    across differently-named sections per page (`journalctl`: "Source
    Options"/"Filtering Options"/"Output Options"/...; `systemd.exec`:
    "Paths"/"Sandboxing"/"Scheduling"/... - no "Options" in the title
    at all). Fixed by scanning the whole document for `<varlistentry>`
    elements directly and classifying by tag content
    (`<option>`/`<varname>` = real flag, `<command>` = subcommand,
    not title text). Recovered `journalctl` (0->107),
    `systemd.exec` (0->216), `systemd.unit` (0->124 parameters).
19. **Prose-embedded command names were miscounted as subcommands.**
    systemd docs use `<command>` tags for inline formatting inside
    regular sentences too (e.g. "systemd currently has..."), not just
    inside real subcommand definitions - `systemctl`'s subcommand list
    picked up "systemd" as if it were one of its own subcommands.
    Restricted subcommand extraction to `<command>` tags that appear
    inside a `<term>` (an actual definition), not anywhere in prose.
20. **Same command documented in two unrelated sources, never
    merged.** `systemctl`/`journalctl`/`hostnamectl`/`timedatectl`
    exist both in the new systemd source (complete) and in the
    curated tldr allowlist (partial examples) - the merge step that
    already combined coreutils/grep with tldr didn't know about
    `systemd-docs`, so these stayed as two disconnected records.
    Extended `COMPLETE_REFERENCE_SOURCES` to include `systemd-docs`
    and `docker-docs`. While fixing this, found the *same* gap already
    existed for `cat`/`dd`/`df`/`head`/`kill`/`nl` (tldr documents
    each of these twice - once under `pages/common`, once under
    `pages/linux` - and the merge only absorbed the first tldr match,
    leaving the second as an orphan duplicate). Fixed generally: all
    matching tldr records now merge into the reference record, not
    just the first one.
21. **Coreutils descriptions ended mid-sentence.** Stripping a
    texinfo `@example` block (a config file example a sentence
    introduces with "...as follows:") left the introducing sentence
    dangling with nothing after it (`tail`: "...consisting of:" then
    nothing). Trimmed the dangling sentence back to the last real
    sentence boundary - carefully scoped to real boundaries (period +
    space/newline, or a paragraph break) after an early version
    mistook the "." inside `~/.bashrc`-style filenames for a sentence
    end and cut `dircolors`/`env`'s descriptions off mid-word.
22. **texinfo `@menu` (table-of-contents) blocks leaked raw into
    descriptions.** Unlike `@example`, nothing stripped `@menu...@end
    menu` blocks - commands with several option subsections (`ls`,
    `join`, `ptx`) had ugly, half-rendered `* Item:: description`
    lines inside their description text. Stripped the whole block.
23. **Nested macros broke `@xref` stripping.** `printf`'s description
    has `@xref{..., @command{printf} format directives, ...}` - a
    macro nested inside the cross-reference's own arguments. The
    xref-removal regex stopped at the *inner* macro's closing brace,
    leaving raw reference text and a stray `}` in the output.
    Reordered so nested macros are flattened first, xref stripping
    runs last. Also added handling for several previously-unhandled
    texinfo escapes leaking into descriptions as raw characters:
    `@.`/`@:` (sentence-ending punctuation), `@ ` (literal space),
    `@@` (literal `@`), `@*` (forced line break).
24. **windows-commands parameter tables had the same escaped-pipe bug
    as Docker (twice over), plus two new bugs of their own.** Found
    while building the new table-fallback parser for the ~869
    windows-commands files: (a) `attrib`'s `` `{+\|-}r` `` flag syntax
    hit the exact same escaped-pipe-breaks-the-split bug already fixed
    for Docker; (b) `ktpass` uses the *same* pipe unescaped but inside
    backticks (`` `{-|+}` ``), which GitHub's table renderer tolerates
    but a naive split doesn't - both needed protecting before
    splitting on `|`. (c) Some "Parameters" tables are actually
    subcommand *indexes* linking to separate pages (`bitsadmin cache`
    -> `[bitsadmin cache and help](...)` per row) rather than real
    flag definitions - every row was colliding into the same fake
    flag name. (d) Multi-subsection pages (`bcdedit`) repeat their
    table header once per subsection, and the header's first column
    isn't always literally "Parameter" (sometimes "Option") - unrecog-
    nized repeated headers were captured as fake parameters named
    after the header text. Fixed all four; recovered 4,793 real
    parameters across 869 files (by far the largest single recovery
    in this project up to that point).
25. **A dedup fix targeting Docker's `docker build` alias-fanout
    almost hid an unrelated find.** Not a new bug itself, but while
    scoping the fix to `docker-docs` only (see decision entry below),
    the audit habit of checking per-source counts is what caught the
    PowerShell regression before it shipped - documented here as a
    process note more than a data bug.
26. **`windows-powershell-docs`'s ~2,438-cmdlet scale mostly needed no
    fixes at all** - reusing the already-hardened `powershell-md`
    parser meant only 5 minor issues surfaced across 695 new records
    (3 empty `about_*` conceptual topics, 1 empty parameter
    description, 1 duplicate flag name) - a useful data point that
    the parser-reuse strategy (vs. writing something new per source)
    pays off once a format has been battle-tested.
27. **nftables' combined short/long option syntax needed a small
    parser generalization.** systemd always uses a separate `<term>`
    per alias (`-u` and `--unit=` as two elements); nftables' `nft.xml`
    writes both in one `<option>-h/--help</option>`. Generalized the
    shared DocBook flag-extraction to split on `/` when present -
    verified first that none of the 16 curated systemd files use `/`
    inside a real `<term>` (only inside cross-reference prose, which
    isn't parsed as a flag anyway), so the change was safe for both.
28. **A new troff/man-page parser needed several rounds of ground-
    truth fixes before it was trustworthy**, building it against
    `cron`, `iptables`, and `ufw` together surfaced format variance
    within troff itself: (a) flag names are written two different
    ways depending on the project - a dedicated `.B "flag"` macro
    line (crontab) vs. plain text with inline `\fB...\fP`/`\fR`
    escapes (iptables, ufw) - both needed support; (b) iptables
    nests a second `.TP` list *inside* one option's own description
    (documenting table names under `-t`) - unhandled, this would have
    created spurious top-level fake flags, fixed with the same
    depth-tracking approach used for coreutils' nested texinfo tables;
    (c) bracketed negation/separator punctuation (`[!]`, `/`, `,`)
    was getting bolded in the source for visual emphasis and picked
    up as if it were a real flag name - filtered out anything with no
    letters or digits; (d) the first working version of description
    extraction grabbed only the *first line* of the DESCRIPTION
    section, which is frequently a single word before troff's
    word-level italic/bold macros split the rest of the sentence
    across lines (`crontab` came out as literally `"A"`) - fixed to
    accumulate the whole first paragraph; (e) that fix then over-
    corrected the other way for `crontab.5`, absorbing the *entire*
    multi-paragraph DESCRIPTION section (8,860 characters) because
    troff often separates paragraphs with a `.PP` macro rather than a
    blank line, which the stop-condition didn't recognize - fixed to
    treat `.PP` as an equal paragraph-break signal.
29. **A file's own name lied about what it was inside `commands.json`
    when it had a double extension.** `iptables.8.in` (an autoconf
    template) was being completely dropped from the dataset - pathlib
    `.stem` only strips the *last* suffix, giving `"iptables.8"`,
    which didn't match the `allowed_names={"iptables", ...}` filter
    checking for plain `"iptables"`. Removed the filter for that
    source (the directory itself is already narrow) rather than
    trying to special-case every double-extension pattern.
30. **The mdoc parser needed three fixes before `ssh`'s data could be
    trusted**, found by validating against all 15 OpenSSH manuals
    rather than just `ssh.1`: (a) mdoc composes macros on a single
    line (`.Oo Ar bind_address : Oc`) more freely than troff - a
    first attempt at cleaning this leaked raw macro names as if they
    were content; (b) the fix for that was too broad and started
    treating *any* token matching a macro name as removable, including
    on ordinary prose lines where `on`/`An` are just common English
    words, not macro calls (`"specified on a per-host basis"` was
    losing its `"on"`) - restricted macro-name stripping to lines that
    are actually macro invocations; (c) `ssh`'s `-L` flag lists 4
    argument-syntax variants as 4 separate `.It Fl L` entries before
    giving one shared description after the last one - without special
    handling, 3 of the 4 dataset entries would have had no real
    description text, only the syntax pattern - fixed by merging
    consecutive `.It` entries for the same flag instead of treating
    each as a new one. Also found and fixed a list-closing bug
    (`.El` wasn't ending the current entry, so `sftp`'s last
    interactive command absorbed the entire SEE ALSO/bibliography
    section that followed it into its own "description").
31. **The RST parser's comma-splitting for multi-alias flags broke on
    a flag's own argument syntax.** `dnf`'s `--whatdepends
    <capability>[,<capability>...]` was split into two fake entries
    at the comma *inside* the argument hint, producing a bogus
    `<capability>...]` parameter alongside the real flag - fixed by
    only accepting split pieces that themselves start with `-` as
    real aliases, discarding the rest as argument-syntax fragments.
32. **The same RST parser initially returned zero results for
    `dnf.conf`.** Config directives there are written the same way as
    CLI flags (`` ``term`` `` + indented paragraph) but without a
    leading `-` (`` ``cachedir`` ``, not `` ``--cachedir`` ``) -
    broadened the "is this a real entry" check to also accept bare
    identifier-shaped terms, not just dash-prefixed ones. A second,
    easy-to-miss version of the same bug remained after that: the
    code recognized bare identifiers as valid entries but then still
    ran them through the flag-only `-`-prefix filter when building the
    alias list, silently discarding every one of them anyway - fixed
    by only applying that filter to actual dashed flags.
33. **Adding apt/dnf to `COMPLETE_REFERENCE_SOURCES` surfaced two
    older, unrelated merge bugs.** Checking that apt/dnf's new records
    actually merged with their tldr counterparts (rather than assuming
    it, per the project's verification standard) found they hadn't:
    `apt-docs`/`dnf-docs` were never added to
    `COMPLETE_REFERENCE_SOURCES` in the first place, so
    `merge_complementary_sources` never even looked for a tldr match -
    `apt`, `apt-get`, `apt-cache`, and `dnf` each sat as two separate,
    unmerged records (full parameters + zero examples on one side,
    real examples + almost no parameters on the other). Fixed by
    adding both sources to the tuple. That fix then exposed a second,
    older bug that predates today's work: tldr's own parser
    (`parse_tldr_md`) blindly converts every hyphen in a filename to a
    space (`command = doc["name"].replace("-", " ")`) - correct for
    genuine multi-word subcommands (`docker-compose.md` -> "docker
    compose", a real two-word invocation), but wrong for standalone
    binaries that are actually typed with the hyphen
    (`ssh-keygen.md` -> "ssh keygen", `apt-get.md` -> "apt get",
    `systemd-analyze.md` -> "systemd analyze"). Since the reference
    parsers (DocBook/mdoc) correctly keep these hyphenated, the tldr
    counterpart landed under a different, wrong command name and could
    never merge - silently orphaning real examples for `ssh-keygen`,
    `apt-get`, `apt-cache`, and `systemd-analyze` since each of those
    sources was added. Fixed in `merge_complementary_sources` (not in
    `parse_tldr_md`, to avoid touching the genuinely-correct
    space-conversion for real subcommands): before merging, any
    hyphenated reference-only command now also checks for a
    same-named-but-spaced group that consists *entirely* of tldr
    records, and folds those in instead of leaving them as a separate,
    wrongly-named entry. Net effect: apt/apt-get/apt-cache/dnf/
    ssh-keygen/systemd-analyze all now have exactly one merged record
    each with both full parameters and real examples; total dropped
    slightly (162,294 -> 162,234) as the orphaned duplicate entries
    were absorbed rather than left as separate junk rows.
34. **DocBook tools' own subcommands were never captured as
    retrievable data.** Live-testing `"what does systemd-analyze blame
    do?"` after the merge fix above returned an unrelated
    systemd.exec sandboxing answer instead - the DocBook parser only
    ever turned `<option>`/`<varname>` terms into parameter records; a
    tool's subcommands were folded into the main description as a
    one-line name summary and then nowhere else. Two different XML
    structures needed separate handling: `systemctl`/`loginctl`-style
    tools list subcommands as `<term><command>` entries inside a
    "Commands" `<variablelist>` (the name was already being read for
    the summary line - now the matching `<listitem>` description is
    captured too and added as its own parameter-like record);
    `systemd-analyze`-style tools instead document each subcommand in
    its own `<refsect2>` titled with the full invocation
    (`<title><command>systemd-analyze blame</command></title>`) and
    have no "Commands" section at all - needed a second extraction
    path that matches on the refsect2 title's leading command name and
    takes its first direct `<para>` as the description. 754 new
    training examples recovered across the systemd tools that have
    subcommands (162,234 -> 162,988).
35. **A dedicated dataset-wide audit for leftover markup found one
    more real bug: unhandled mdoc escape sequences leaking into
    ssh-docs text.** Prompted by reaching ~163K rows, ran a broader
    scan across the *entire* dataset (not just the sources touched
    today) looking for known leftover-markup signatures from every
    parser format this project has ever built. Most hits were false
    positives from the detection regexes themselves (`@example.com`
    email addresses matching a texinfo-macro pattern, git's own
    `<placeholder>` argument notation matching DocBook tag names,
    triple-backtick code fences matching an RST-backtick pattern,
    shell `# comments` inside example code matching a Markdown-heading
    pattern) - each was checked against full context before being
    dismissed, not assumed safe from the sample alone. One was real:
    `mdoc_clean_line` (the ssh/OpenSSH parser) never stripped any
    backslash escape at all - `\&`, `\-`, `\e`, `\%`, `\(em`/`\(en`,
    `\*(Lt`/`\*(Gt`/`\*(Ge`/`\*(Le` all passed straight into the
    dataset verbatim (e.g. `ssh -e`'s answer literally contained "Ql
    \&." instead of "."). Root cause for the worst instance (`Ql`
    appearing as a bare leftover word) traced to `.Pq Ql \&.` - a
    macro line whose *nested* macro token `Ql` (mdoc's "quote a
    literal" macro) was simply missing from `MDOC_MACRO_NAMES`, the
    same bug class as the earlier `.Oo`/`.Oc` composition fix, just
    one macro name that hadn't come up in the original 15-manual
    validation pass. Fixed by adding `Ql` to the macro-name set and
    adding a general escape-substitution pass (safe unconditionally,
    since none of these escapes are real English words the way
    `on`/`An` were). A related instance needed a second fix:
    `mdoc_item_name` (extracts a `.It`'s flag/command name) reads its
    token directly without going through `mdoc_clean_line` at all, so
    sftp's `\&!`/`\&?` interactive commands kept their escape prefix
    in the *name* field even after the description-level fix - needed
    the same `\&` strip applied there too. 85 dataset rows across 15
    distinct descriptions fixed (ssh, sftp, ssh-keygen, ssh_config,
    sshd_config); verified live via RAG before and after, plus the
    full existing regression set. No dataset-size change - pure text
    cleanup, not new/removed records.
36. **Manually reviewing live answers (not an automated regex sweep)
    found a much bigger bug: a cleanup regex was silently deleting
    ~44% of all PowerShell "syntax" answers.** `remove_documentation_noise`
    (in `build_dataset.py`, applied to every text field including
    syntax) had a step meant to strip a real "### CommonParameters"
    doc heading, written as `r"(?:###\s*)?CommonParameters.*$"` with
    `re.DOTALL` - the leading group being *optional* meant it matched
    the word "CommonParameters" ANYWHERE, including harmless inline
    `[<CommonParameters>]` syntax placeholders that appear in nearly
    every standard PowerShell cmdlet's own syntax block - and then
    deleted everything from that point to the end of the string,
    including the closing code fence and every other parameter-set
    variant. The visible symptom was a "syntax" answer that was just a
    bare `### Name (Default)` heading with the actual command syntax
    gone. Affected 1,377 of 3,149 PowerShell-sourced records (44%).
    Fixed by anchoring the pattern to only match when "CommonParameters"
    is the entire content of its own line (a real heading), not an
    inline mention. Found while spot-checking a live answer to
    `"what is the syntax of Get-Process?"` during a manual review the
    user asked for (a question list per source, to check responses
    directly) - a reminder that live spot-checks catch bugs that
    format-specific regex audits don't, since this had nothing to do
    with any of the earlier leftover-markup patterns.
37. **The same review surfaced a second, larger, unrelated bug in
    git's AsciiDoc parser: ~36% of git's own documented flags were
    silently dropped for using a different, undocumented style.**
    `git rebase -i` returned a completely unrelated answer
    (`--rerere-autoupdate`) - not a retrieval bug, but a data
    *completeness* bug: `git rebase` had only 2 parameters captured
    total, and `-i`/`--interactive` wasn't one of them.
    `extract_adoc_parameters`'s term-line regex only recognized
    backtick-wrapped flag terms (`` `--flag`:: ``), but 91 of git's own
    `.adoc` files (git-clean, git-config, git-cherry-pick,
    diff-options...) write their flag terms bare, without backticks
    (`-i::`, `--interactive::`, `-e <pattern>::`) - 1,076 flag lines
    written this way, next to 1,873 backtick-wrapped ones, meaning
    roughly a third of git's documented flags across ~90 files were
    invisible to the dataset from the start. Fixed by generalizing the
    term-line pattern to accept either style. Recovering this also
    surfaced a smaller, pre-existing side issue: some `` `flag`:: ``
    term lines are actually *nested enum values* for a parent flag's
    argument (e.g. `--word-diff[=<mode>]`'s `color`/`plain`/`porcelain`
    values, each documented with their own backtick term line, same as
    the systemd "short"/"pretty" quirk found earlier) or a garbled
    positional-argument placeholder (`` `(<mbox>|<Maildir>)...`:: ``
    reduced to a bare "(" by the existing argument-hint stripping) -
    102 such non-flag entries reached `parameters` this way. First fix
    attempt filtered anything not starting with `-` - too broad, see
    item 38 below.
38. **The item-37 dash filter was itself wrong, and fixing it properly
    surfaced two more real gaps in the same parser.** `git stash pop`
    still returned a wrong answer after item 37's fix - turned out
    `git stash`'s own subcommands (`pop`/`push`/`apply`/`list`/`show`/
    `branch`/`clear`/`drop`) use the exact same bare-word term syntax
    as the 102 nested-enum-value entries filtered out above, so the
    blanket `startswith("-")` filter discarded real, useful data along
    with the junk - no reliable syntactic signal distinguishes a real
    dash-less subcommand from a nested value-option, both share
    identical term-line syntax. Reverted the filter; fixed the actual
    root cause of the 102 junk entries instead (added `(` to the
    argument-hint-stripping character class - cleanly empties the
    pure-placeholder case and correctly recovers `mailmap` from
    `` `mailmap (<bool>)`:: ``) and accepted the remaining
    nested-value-option entries as-is, since their description text is
    still accurate, just imprecisely labeled as a "flag". Separately,
    `git stash`'s subcommands turned out to live in their own
    `COMMANDS` section (17 files have one: `git-stash`, `git-remote`,
    `git-worktree`, `git-submodule`, `git-config`...) that
    `extract_adoc_parameters` never read at all - added a second
    extraction pass reusing the same term-parsing logic. That still
    missed `pop`/`apply`/`push`/`show` specifically: the same file
    puts a blank line between the term and description for some
    entries but not others (`clear`, right below `pop`, has none) -
    fixed by tolerating an optional blank line. A fourth, unrelated bug
    surfaced while cross-checking `Remove-Item -WhatIf`'s answer during
    the same review: the *PowerShell* parameter extractor's
    section-boundary lookahead only recognized dash-prefixed headings
    as a stop point, so the last documented parameter of nearly every
    cmdlet absorbed the trailing dash-less `### CommonParameters`
    boilerplate section - 2,193 parameter descriptions affected, fixed
    by treating any `### ` heading as a boundary. Logged a fifth,
    smaller gap as a known open issue rather than fix it in the same
    pass: ~53 subcommand entries in `git-remote`/`git-worktree` use a
    third description format - flush-left, no blank line - that the
    blank-line-tolerant regex still couldn't handle.
39. **Closed the flush-left gap from item 38 by replacing the
    indentation-dependent regex entirely, which then needed its own
    follow-up fix.** Rather than patch in a third special case, rewrote
    `parse_adoc_term_section` to stop caring about indentation/blank
    lines at all: find every term marker in the section, and take
    everything between one term and the next as its description,
    regardless of formatting. This correctly handles all three known
    variants (indented, blank-line-separated, flush-left) in one pass,
    and as a side effect properly recovered the second half of
    multi-paragraph descriptions that used AsciiDoc's `+` continuation
    marker (previously truncated at the first paragraph, e.g.
    `git push --force`'s answer). It also exposed a second, related
    gap while checking `git config get`/`set`/`unset`: some `COMMANDS`
    sections write subcommand terms bare AND without a leading dash
    (`list::`, not `` `list`::`` or `-list::``), which neither existing
    branch of the term-matching regex covered. Broadening the pattern
    to accept any non-backtick text ending in `::` fixed that, but
    immediately over-matched: AsciiDoc uses the identical `term::`
    syntax for other things within the same sections - italicized
    argument placeholders (`_<branch-name>_::`), single-quoted terms
    (`'write'::`), escaped literals (`` \--::``), and, most riskily,
    full example command lines and interactive-menu descriptions
    (`` `git gui citool --nocommit`::``, `filter by pattern::`) that
    are not subcommand names at all. Fixed with a two-part rule: strip
    AsciiDoc's quote/italic wrapper characters and unescape `\-` before
    cleanup (recovers `write`, `verify`, `--` correctly), then require
    any bare (non-dash) result to match a plain identifier pattern (no
    spaces, no stray punctuation) - dash-prefixed terms are still
    accepted unconditionally as before. Verified this converged to
    zero false positives by scanning every non-dash parameter name
    across the entire git-docs source for the same problem, not just
    the reported case. Net effect across items 38-39: git-docs
    parameters went from roughly 2,300 to over 3,500; dataset grew from
    162,988 to 171,559.

40. **A structured 150-question audit (10+ new, previously-unused
    questions per source) found four more real bugs, bigger in scope
    than anything the manual spot-checks had caught.** User asked for
    a systematic check across every source with fresh questions before
    committing to a retrain. Findings, worst first:
    - **nftables was badly broken - 8 of 10 test questions wrong.**
      `nft add rule`, `nft delete table`, `nft list ruleset` etc. all
      returned wrong or hallucinated answers. Root cause: nftables
      documents `add`/`delete`/`list`/`flush` separately for tables,
      chains, and rules, but the DocBook parser captured all of them
      as flat, identically-named entries with no context - "add"
      collided three ways. Fixed by tracking the nearest preceding
      `<cmdsynopsis>`'s `<command>` element (table/chain/rule) as
      context, but only doing a two-pass collision check first: only
      qualify a bare term (e.g. `add` -> `add table`) if it actually
      has more than one distinct description in the document,
      otherwise leave it alone. The naive single-pass "always qualify
      with nearest context" version was tried first and broke unrelated,
      non-colliding entries (address families, verdict statements)
      that don't have their own preceding cmdsynopsis and inherited a
      stale, wrong context from much earlier in the document.
    - **dnf's own commands (`install`/`remove`/`search`/`list`/
      `clean`...) were never captured at all - only its flags were.**
      dnf documents commands in a completely different RST structure
      (`| Command: ``install``` metadata line + its own syntax +
      explanation block) than its flags (simple double-backtick
      definition list) - the existing parser only ever handled the
      flag structure. Built a second RST parser
      (`parse_dnf_command_reference`) for this structure, recovering
      28 commands, some with multiple sub-syntaxes of their own (`dnf
      clean dbcache`/`expire-cache`/`metadata`/`packages`/`all`).
    - **86 git subcommands with a hyphen in their own name were
      misnamed** (same root cause as an earlier session's tldr fix,
      but for git's own AsciiDoc parser this time): `git-cherry-pick`
      -> "git cherry pick" instead of "git cherry-pick", same for
      `git-diff-tree`, `git-rev-list`, `git-ls-files`... Fixed by
      splitting the filename on only the FIRST hyphen, not every
      hyphen - applied to both `parse_git_adoc` and the tldr parser's
      git-specific carve-out for merge consistency.
    - **Some git flags/subcommands live outside every section the
      parser reads.** `git reset --hard`/`--soft`/`--mixed` are
      defined inside DESCRIPTION (explaining the concept of "modes"),
      not OPTIONS; `git cherry-pick --continue`/`--abort`/`--skip`
      live in a dedicated "SEQUENCER SUBCOMMANDS" section (shared with
      `git revert`). Added both as additional sections
      `extract_adoc_parameters` scans, same dedup-by-name merge as
      COMMANDS.
    Verified all four live, plus the accumulated regression set. Net
    effect: dataset grew from 171,559 to 172,126.
41. **Verifying the four fixes above surfaced two MORE bugs, one a
    genuine pre-existing data-quality issue, one a bug in a fix from
    THIS SAME session.** `git config get`/`git stash pop` still
    returned wrong answers after item 40's git fix, and `nft add
    rule`/`dnf list` still returned wrong answers after item 40's
    nftables/dnf fixes - none of these were data problems (the correct
    rows existed in `dataset.jsonl`), they were retrieval bugs in
    `test_model.py`'s `find_mentioned_command`. Root cause: it only
    ever returned the FIRST matching command name from a length-sorted
    list, with no tiebreak for names of EQUAL length - and `nft`
    happens to be the same length as `add` (a real, unrelated Windows
    CLI command from `windows-docs`), so "what does nft add rule do?"
    non-deterministically matched "add" instead of "nft", scoping the
    whole search to the wrong command. Same story for `dnf` vs `list`
    (also a real Windows command). Fixed by picking the match that
    starts EARLIEST in the question text instead of just the first one
    found - the real command is always mentioned before flags/verbs in
    the "what does X Y do?" phrasing this project uses throughout.
    Separately, a NEW bug in `bare_flag()`-derived short-question
    generation (`build_dataset.py`) was found: dnf's Options section
    contains flags that actually belong to a subcommand
    (`repoquery`'s own `-l, --list`, misattributed to top-level `dnf`
    since the RST parser doesn't scope by subcommand) - its bare-flag
    short form ("list") collided with the real `list` COMMAND's own
    identically-phrased question, producing two `dataset.jsonl` rows
    for "What does dnf list do?" with contradictory answers. Fixed by
    skipping bare-flag short-question generation whenever the result
    would collide with another parameter's own full name in the same
    command - a general guard, not dnf-specific. ~2,041 examples
    removed dataset-wide by this guard (duplicate_instructions actually
    *dropped*, confirming most of what was removed was exactly this
    kind of collision, not lost diversity). Net effect: 172,126 ->
    170,085.
42. **A second structured 150-question audit (fully fresh questions,
    none reused from the first) found a real data-extraction bug plus
    two confirmed source-content gaps.** `docker push` and `docker
    load`'s stored "examples" were the WRONG code block from a
    multi-step walkthrough - `parse_docker_cli_md`'s example extraction
    took the first ` ```console ` block found anywhere in the whole
    document, regardless of what it showed. For commands documented as
    multi-step tutorials (check state -> run prerequisite -> run the
    actual command), the first block is often a "before" snapshot or a
    setup step, not the command being documented - `docker push`'s
    example was literally `docker container commit ...` (a
    prerequisite), `docker load`'s was `docker image ls` output (an
    empty "before" state). Fixed by scoping the search to the `##
    Examples` section specifically and preferring the first code block
    that actually invokes the command (checking all of its declared
    aliases, since docs mix the short and long form across steps,
    e.g. `docker push` vs `docker image push`) - falling back to the
    first block only if none match, so already-correct multi-step
    examples (`docker attach`, `docker commit`, `docker logs`, `docker
    port`, `docker rmi` - all legitimately show a real setup step
    before the real command in the SAME block) were verified unchanged.
    Separately confirmed two genuine, non-code-fixable gaps: `net use`
    (and every other `net` subcommand except `net print`/`net user`) is
    simply absent from the cloned `windows-docs` repo, not a parsing
    issue; and two tested Windows shortcuts (`Windows key + Pause`,
    `Windows key + Number`) are absent from the manually-curated
    `windows-shortcuts` source file. Neither was hand-authored to fill
    the gap - this project's whole reliability model depends on every
    answer tracing back to a real source, so inventing plausible-
    sounding content for a gap would be a worse outcome than the gap
    itself. Also fixed two unrelated cosmetic leaks found in the same
    audit: Markdown image syntax (`![alt](url)`) was only having its
    `[alt](url)` portion converted, leaving a stray `!` in front (e.g.
    a diskpart example read "!Screenshot of..."); and AsciiDoc's
    `[[anchor-id]]` cross-reference markers (e.g. `[[CONFIGURATION]]`
    in `git-notes.adoc`) weren't stripped at all, since the existing
    Markdown-link cleanup regex doesn't recognize this syntax - fixed
    generally (not anchored to line start, since by the time this text
    is cleaned it's often already been flattened to one line) rather
    than just for the one reported case. 170,085 -> 170,081 (a few
    image-only "examples" that are now empty were correctly dropped
    rather than left in as `!`-prefixed junk).

43. **A third, 438-question fresh audit (30 new questions per subject,
    "for the last time") found no new dataset-content bugs, but five
    more retrieval bugs in `test_model.py` - all in the same family as
    item 41 (a real answer exists in `dataset.jsonl`, but the query-time
    scoping logic hands back the wrong record) - plus confirmed several
    more genuine, non-code-fixable source gaps.
    - **The `find_mentioned_command` generic-word fix went too far in
      the OTHER direction.** `"list"`/`"add"` are real, documented
      Windows commands (diskpart/diskshadow subcommands, only ever
      meaningful inside that interactive shell, e.g. `DISKPART> list
      disk`) that happen to collide with this project's own question
      templates ("Can you **list** all X flags?"). Because `list`
      started earlier in the question than the actual subject
      (`"can you list all grep options?"`), the item-41 earliest-
      position tiebreak picked the irrelevant Windows command every
      time. Fixed with a small `GENERIC_WORD_COMMAND_NAMES = {"list",
      "add", "tab"}` set: any OTHER real command name found in the
      question is preferred over these three; they're only used when
      they're the *sole* match (so a genuinely bare `"what does list
      do?"` still resolves correctly).
    - **systemd's own man pages are dot-separated (`systemd.service`),
      but nobody phrases a question that way.** `"what does Restart do
      in a systemd service unit?"` never matched `systemd.service` as a
      command at all - only the unrelated, real SysV `service` command
      (word-boundary matched inside "systemd **service** unit") did,
      scoping the whole search to the wrong tool entirely. Fixed by
      registering an additional space-separated pattern variant for
      every dot-separated command name, mirroring the existing space-
      to-hyphen variant added for PowerShell cmdlets - `"systemd
      service"` now matches and outranks bare `"service"` by starting
      earlier in the sentence.
    - **Directive names like `Restart=`/`ExecStart=` were only found if
      they appeared immediately after the command name.** The existing
      bare-flag detector only checks the word right after a matched
      command; natural phrasing like `"what does Restart do in a
      systemd service unit?"` puts the directive name at the START of
      the sentence instead. Added `find_named_parameter_token`, which
      checks whether ANY standalone word in the question matches one of
      the command's own parameter names (with or without the trailing
      `=`) - if exactly one does, that's treated as a certain match
      regardless of position.
    - **Some systemd unit directives are real, correctly-extracted data
      - just filed under a different, related man page than the one a
      natural question names.** `User=`/`WorkingDirectory=`/
      `Environment=` etc. are genuinely documented under
      `systemd.exec`, not `systemd.service` - systemd's own
      per-unit-type man pages explicitly say "see systemd.exec(5)" for
      these shared execution-environment directives, so a service-unit
      question about them isn't wrong, it's just naming the wrong page.
      Added `find_systemd_shared_directive`: for the five unit-type
      commands (`systemd.service`/`.socket`/`.mount`/`.timer`/`.path`),
      if a named directive isn't found under the unit type itself, the
      three pages systemd's own docs point to (`systemd.exec`,
      `systemd.kill`, `systemd.resource-control`) are checked next.
      This follows a cross-reference the source documents make
      explicitly - not invented content.
    - **The keyboard-shortcut pool (`shortcut_mask`) was built by
      scanning each record's ANSWER text for a key-combo pattern, not
      by checking where the record actually came from.** Several
      correct shortcut answers don't happen to repeat a key name in
      their own text (e.g. PrtScn's answer is "Select a region of the
      screen..." - it never says "PrtScn"), so they were silently
      excluded from the restricted pool their own question should have
      matched against, sending bare questions like `"what does PrtScn
      do?"` to an unrestricted search that lost to an unrelated DOSKEY
      entry. Rebuilt the mask from the record's source path
      (`windows-shortcuts/shortcuts.md`) instead - exact and, per a
      direct check, collision-free with every other command in the
      dataset.
    - **No-space key-combo phrasing (`"Ctrl+O"`) wasn't recognized as a
      shortcut question at all, and even once recognized, the narrow
      shortcut pool was too self-similar for the embedding model to
      tell combos apart.** Every stored shortcut instruction is a
      near-identical template (`"What does Ctrl + X do?"`), so within
      that pool alone a totally wrong record (e.g. Ctrl+A's answer) can
      score 0.84 against a query for a DIFFERENT, unrelated letter -
      well past the confidence threshold, with no hedge. This is worse
      than a normal wrong answer because it looks fully confident.
      Fixed two ways: (1) added a `SHORTCUT_COMBO_PATTERN` so any
      `Ctrl+`/`Alt+`/`Shift+`/`Win+` text (space or no space) is
      recognized as a shortcut question even without an explicit word
      like "shortcut"; (2) added `find_exact_shortcut_pool`, which
      extracts the combo and requires it to match a real stored
      shortcut *exactly* before trusting the pool at all - if the combo
      isn't in the source (confirmed for `Ctrl+O`/`+P`/`+S`/`+G`/`+J`/
      `+K`/`+M`/`+Q`, `Ctrl+Shift+T`, all genuinely absent from
      `shortcuts.md`), the honest "no data" fallback is used instead of
      guessing inside the self-similar pool.
    All fixes are retrieval-layer only (`test_model.py`) - no dataset
    rebuild, `170,081` unchanged. Also confirmed, and deliberately NOT
    hand-authored: `apt-key` is entirely absent from the cloned
    `apt-docs` source (no `apt-key.8.xml` in the repo at all); the
    `apt-get moo` easter egg isn't documented in `apt-get.8.xml` (the
    string "moo" there is only part of an unrelated example); `apt
    list`'s `--all-versions` is mentioned only in prose inside the
    `list` subcommand's own description, not as its own extractable
    option entry (same class as the earlier `docker network ls`
    short-description gap); and `networkctl`/`busctl`/`machinectl`/
    `portablectl`/`resolvectl` were never curated as systemd sources at
    all (only the 16 files listed in `COMPLETE_REFERENCE_SOURCES` are).
44. **Went back through the round-43 gap list and closed every one that
    had a real, findable source - without hand-authoring anything.**
    - **The `net` command family (22 subcommands: `use`, `view`,
      `share`, `start`, `stop`, `accounts`, `session`, `localgroup`,
      `group`, `config`, `time`, `computer`, `file`, `name`, `pause`,
      `send`, `statistics`, `continue`, `help`, `helpmsg`, plus the
      already-present `print`/`user`) turned out to be a genuine
      Microsoft documentation gap, not a cloning mistake - the live
      `windows-server/administration/windows-commands/net-*` pages
      404 for all of these today; Microsoft stopped maintaining
      individual reference pages for most of the `net` family. The
      content still exists, just archived - Microsoft's own
      `previous-versions` TechNet library (`learn.microsoft.com/
      previous-versions/...`) keeps a full `net use`/`net view`/...
      reference for Windows XP through Server 2012 R2. Fetched all 22,
      rebuilt them as local `.md` files in the exact frontmatter/
      `## Syntax`/`## Parameters`/`## Examples` shape the existing
      `net-user.md`/`net-print.md` already use, so no new parser code
      was needed.
    - **`apt-key` has no man page in the cloned `apt-docs` repo at all**
      (confirmed: not in git history either, since the local clone is
      shallow at the latest release - `apt-key` was fully removed from
      upstream once it was deprecated). Debian still ships and
      maintains `apt-key(8)` for currently-supported releases
      (bookworm) on `manpages.debian.org`, so that page was used to
      reconstruct `apt-key.8.xml` in the same DocBook structure as the
      real `apt-*.8.xml` files (`refsect1`/`variablelist`/
      `varlistentry` - no new parser needed here either).
    - **`networkctl`/`busctl`/`machinectl`/`portablectl`/`resolvectl`
      were never a real source gap** - the XML files already existed
      in the systemd sparse checkout (`data/raw/systemd-docs/man/`),
      they just weren't in `config.py`'s 16-name `allowed_names`
      curation list. Added all 5; no download needed.
    - **`Windows key + Pause` and `Windows key + number` are real,
      currently-documented shortcuts** on Microsoft's own "Keyboard
      shortcuts in Windows" support page - added both to
      `windows-shortcuts/shortcuts.md` verbatim. Separately confirmed
      that `Ctrl+O`/`+P`/`+S`/`+G`/`+J`/`+K`/`+M`/`+Q` and
      `Ctrl+Shift+T` are genuinely NOT on that page either (checked
      directly) - these aren't a source gap, they're app-specific
      behavior Microsoft's own OS-level shortcut reference correctly
      doesn't claim as universal, so they were left undocumented
      rather than invented.
    - **Rebuilding the pipeline with the new `apt-key`/systemd-tool
      sources surfaced a real, pre-existing bug affecting the ENTIRE
      apt/systemd/nftables DocBook family, not just the new files.**
      `parse_systemd_xml`'s two flag-collection loops
      (`for flag, description, _ in raw_entries:` and
      `for flag, description, object_type in raw_entries:`) reused the
      name `description` - the same name the function uses earlier for
      the command's own top-level summary (from its `Description`
      refsect1). Python has no block scoping, so after these loops ran,
      the outer `description` was silently overwritten with whatever
      the LAST processed flag's description happened to be - `"what
      does networkctl do?"` was returning `--stdin`'s description, not
      networkctl's real one. Individual flag/subcommand answers were
      unaffected (each is bound fresh within its own loop iteration) -
      only the bare, top-level "what does X do?" question for any
      DocBook-family command that has at least one flag was silently
      wrong. Not caught earlier because every prior audit round asked
      about SUBCOMMANDS (`"what does systemctl reload do?"`) almost
      exclusively, never the bare command name. Fixed by renaming the
      loop variables (`flag_description`); spot-checked correct across
      `networkctl`, `apt-key`, `systemctl`, `apt-get`, `nft`,
      `systemd.service`, and `journalctl` after the fix.
    - **A second, self-inflicted bug found while verifying the fix
      above:** the 22 new `net-*.md` files initially included a
      boilerplate `net help <command>` row (copied faithfully from the
      Microsoft source's own Parameters table) in every file - since
      it's nearly identical text repeated 16 times, it created a
      generic "net" parameter collision that won over the real
      top-level description for several commands (`"what does net use
      do?"` was returning `"Displays help for the specified net
      command"`). The genuinely-curated `net-user.md` doesn't carry
      this row even though the original TechNet source has the same
      line - confirming its removal from the reference article was an
      intentional editorial choice, not an oversight. Removed the row
      from all 16 affected files.
    - **A third, narrower retrieval gap found while spot-testing the
      new shortcuts:** `"Windows key + 5"` (a literal digit) returned a
      confident but wrong answer (`Windows key + A`'s), because (1)
      `SHORTCUT_COMBO_PATTERN` only recognized bare `Win+`, not
      `Windows key +`/`Windows logo key +`, so the question never even
      reached the shortcut-scoped search, and (2) the stored record
      uses the generic placeholder `"Windows key + number"` (matching
      how Microsoft's own page documents all ten digits as one entry),
      which no specific digit query would match exactly. Fixed both:
      broadened the trigger pattern, and added a digit -> `"number"`
      fallback in `find_exact_shortcut_pool` when an exact digit match
      isn't found.
    Net effect: 170,081 -> 171,687. No previously-passing regression
    question broke across any of these fixes.
45. **A 150-question spot check of just the newly-added sources (20
    fresh questions per subject: `net`, `apt-key`, `networkctl`,
    `busctl`, `machinectl`, `portablectl`, `resolvectl`, plus 10 more
    for the 2 new shortcuts) found one real retrieval bug and confirmed
    the rest of the new content is solid.** Every direct question about
    any of the new commands by name (`"what does networkctl list
    do?"`, `"what does apt-key add do?"`, `"what does portablectl
    attach do?"`...) was correct. The one real bug: intent-phrased
    questions that don't name a tool at all but happen to contain the
    word "service" as part of an unrelated noun phrase (`"how do i
    attach a **portable service** image?"`) were hijacked by the real,
    unrelated SysV `service` command, the same way `"can you **list**
    all X flags?"` was hijacked by Windows' `list` in the previous
    round - `service` just hadn't been common enough in earlier test
    phrasing to surface it. Added `"service"` to
    `GENERIC_WORD_COMMAND_NAMES`, and additionally changed the
    all-category command-scoping branch to skip scoping entirely for
    any generic-word match (previously, being the *sole* candidate was
    enough to trigger scoping even for these risky words) - unlike
    `list`/`add`/`tab`, "service" is essentially never the deliberate
    subject of a natural-language question, so scoping to its own
    narrow pool is close to strictly harmful. Verified the bare `"what
    does service do?"` case (where scoping used to help) still resolves
    correctly via unrestricted global search, since the near-exact
    dataset record wins on its own. Also confirmed, not fixed (both
    correctly and honestly disclosed as low-confidence, not confidently
    wrong): `resolvectl log-level` and `busctl --user`/`--system` are
    real options documented only via a cross-file `xi:include` this
    project's DocBook parser doesn't resolve (a new instance of the
    same parser-completeness class as `apt list --all-versions`); and
    `machinectl stop` is documented only as prose ("stop as an alias
    for poweroff"), not its own extractable entry. Retrieval-layer only
    - no dataset rebuild.
46. **The "service" collision from item 45 turned out to be one
    instance of a much bigger, previously-undetected bug class, found
    while live-testing the new desktop GUI (see 01_Project_Overview.md
    "Desktop UI").** `"how can i copy a file over ssh?"` - a
    previously-validated, documented-as-working intent question -
    silently returned Windows' `copy` command reference instead of the
    real answer (`scp`'s own intent record). Root cause: `"copy"` is,
    like `"service"`/`"list"`/`"add"`/`"tab"` before it, a real,
    documented Windows command name that ALSO happens to be an
    everyday English verb - any natural "how do/can I copy/rename/
    move/... X" question that mentions one of these words gets scoped
    to that command's own (intent-excluded) records, permanently
    hiding the real answer, which usually lives under a completely
    different command's intent record. Continuing to add individual
    words to `GENERIC_WORD_COMMAND_NAMES` doesn't scale - nearly every
    common file-operation verb (`copy`, `rename`, `move`, `sort`,
    `find`, `print`, `more`, `format`...) is also a real Windows
    command name. Fixed with a general rule instead: added an
    `INTENT_PHRASE_PATTERN` that recognizes natural intent phrasing
    ("how do/can I...", "I want to...", "I need...") and skips
    command-scoping entirely for any question matching it, regardless
    of which word triggered the false command match - verified
    unrestricted global search finds the correct record with
    0.75-0.98 similarity in every case checked, well above the
    confidence threshold. Bare, non-intent-phrased questions about the
    same words (`"what does copy do?"`, `"what does service do?"`)
    were verified unaffected - they still scope normally. This fix
    also fully covers the `"service"`/portablectl case from item 45
    without needing that word-specific addition, though `"service"`
    stays in `GENERIC_WORD_COMMAND_NAMES` since that set also feeds a
    separate tiebreak in `find_mentioned_command`. Retrieval-layer
    only, no dataset rebuild; full regression set re-verified clean.
47. **Measured what fraction of realistic questions actually need the
    generative fallback, then chased down the two biggest contributors
    to that number.** Re-ran ~763 unique questions accumulated across
    this session's audit rounds against the live pipeline: 89.9% got a
    direct RAG match, 1.4% a disclosed "closest match", and 8.7% fell
    through to generation - already a strong number, but two real bugs
    were hiding in that 8.7%.
    - **A conceptual Windows Server article got extracted as a fake
      command literally named `"what is"`.** `windows-docs`' broad,
      recursive scan of `WindowsServerDocs` swept in a glossary article
      titled "What is Windows Admin Center" (`understand/what-is.md`),
      and the space-for-hyphen filename convention turned its title
      into a registered "command" called `what is`. This collided with
      this project's OWN `"What is the syntax of {name}?"` question
      template - since `find_mentioned_command` prefers whichever match
      starts earliest, `"what is"` (position 0) always beat the real
      command name that followed it, so EVERY "what is the syntax of
      X?" question for ANY command was silently misrouted to this
      content-free article instead of the real, already-present syntax
      data (confirmed: `grep`, `nft`, `docker build`, `Get-Process`,
      `ForEach-Object` all had correct syntax data the whole time - this
      was purely a routing bug, not a gap). A sibling `overview.md`
      pattern (9 separate files, one bogus `"overview"` command) was
      found and excluded the same way while checking for other
      instances of this pattern - confirmed no other bogus command name
      collides with any of this project's own question-template
      prefixes. Fixed by excluding both from `extract_commands.py`'s
      result set entirely, since neither is a real, executable command.
    - **Several real git flags live in section titles the AsciiDoc
      parser had never scanned before.** `git rebase --abort`/
      `--continue` are documented under `"MODE OPTIONS"` (a different
      heading than `git-cherry-pick`'s `"SEQUENCER SUBCOMMANDS"`, even
      though it's the same continue/abort/skip family - git's own docs
      aren't consistent about this across commands); `git config
      --list` is documented under `"DEPRECATED MODES"` (superseded by
      `git config list`, but still what most users actually type).
      Refactored the four near-identical section-scanning blocks in
      `extract_adoc_parameters` into one loop over
      `ADOC_FALLBACK_PARAMETER_SECTIONS` and added both new section
      titles to it - no behavior change for the existing four sections,
      just easier to extend the next time a fifth one turns up.
    Both fixes verified live (git and PowerShell/Docker/grep/nft syntax
    families all correct, full regression set clean) and rebuilt through
    the whole pipeline. 171,687 -> 171,775.
48. **Chased down the rest of the generative-fallback contributors from
    item 47's measurement, aiming to close as many genuine data gaps as
    possible (as opposed to relying on the model's own guess) - found
    four more real, fixable issues, one of them a large one.**
    - **iptables' most commonly-asked flags (`--dport`, `--sport`,
      `--tcp-flags`, `--syn`, `--state`...) were never in the dataset at
      all - not because they're undocumented, but because the file that
      documents them (`iptables-extensions.8.in`) had been deliberately
      excluded.** That earlier exclusion decision was half right: the
      *assembled* extensions man page really does get built at compile
      time from 94 separate fragment files via `@TARGET@`/`@MATCH@`
      include-markers, which would need a real parser to resolve. What
      the earlier note missed is that each of those 94 fragment files
      (`extensions/*.man`) is already a complete, self-contained troff
      document in its own right - no `@TARGET@`/`@MATCH@` resolution
      needed, just the existing `.TP`-block scanner pointed at each
      file directly. Added a new `iptables-extension-man` format
      (reusing `extract_troff_options` with no section-scoping, since
      these fragments have no `.SH` headers at all) and a new
      `iptables-extensions-docs` source pointed at the same cloned repo
      via a new `"repo"` override key in `config.py` (needed since two
      sources can't previously share one physical clone under different
      scan rules). `libxt_*`/`libipt_*` files attribute to `iptables`,
      `libip6t_*` to `ip6tables`. Result: iptables went from 59 to 332
      unique documented parameters.
    - **`b2sum` and the whole SHA-2 family (`sha224sum`/`sha256sum`/
      `sha384sum`/`sha512sum`) were missing the checksum flags they
      share with `md5sum`/`sha1sum`/`cksum` (`-c`/`--check`, `--status`,
      `--tag`...), for two separate reasons.** `b2sum` has one genuinely
      own flag (`-l`/`--length`) but the borrowing logic's
      `not parameters` gate skipped it entirely once it saw that ANY
      native parameter existed - not knowing that having one own flag
      doesn't mean a command doesn't ALSO need the shared ones. The
      SHA-2 family doesn't even have that problem to hit, because it
      isn't documented under a `@node X invocation` at all - GNU groups
      all four together under one `@node sha2 utilities`, which the
      section-splitting regex never recognized as a boundary, so all
      four silently vanished into whichever adjacent command's section
      happened to come first. Fixed the gate by keying off a more
      specific, always-present signal (the literal phrase "cksum common
      options", which is what `@ref{cksum common options}` reduces to
      after macro expansion - the borrowing logic's *previous* signal,
      `@checksumUsage{`, could never fire post-expansion since macro
      *calls* get replaced by their expanded bodies before this check
      ever runs, making that branch dead code that happened to work
      anyway for commands reached via the separate `@xref` fallback);
      added `sha2 utilities` as a second, narrowly-scoped section
      boundary and generate one record per `@pindex` name found inside
      it. `b2sum` went from 1 parameter to 23; `sha256sum` and its
      three siblings went from not existing as coreutils records at all
      (only a single tldr-sourced `--check`) to the same full 23.
    - **nft's `describe`/`export`/`monitor` subcommands use two more
      `<refsect2>` title patterns the existing systemd/nftables
      subcommand scanner didn't recognize** (a bare `"X command"` title
      for `describe`, and bare one-word titles for `export`/`monitor`
      nested under a `refsect1` titled "Additional commands") - neither
      uses the `<command>` name embedded in the title the way
      `systemd-analyze blame`-style entries do. Added narrowly-scoped
      detection for both (the second pattern requires an exact
      `"Additional commands"` parent title specifically to avoid
      catching unrelated bare-word refsect2 titles elsewhere, like
      nft's own "Queue statement"). Caught one self-inflicted bug while
      verifying: the naive first-`<para>`-in-the-section approach grabs
      whichever paragraph wraps the `<cmdsynopsis>` for `describe`
      (producing a garbled "describe expression" instead of the real
      explanation) - fixed by skipping any paragraph whose only child
      is a bare `<cmdsynopsis>`.
    - **Bundled single-dash short flags (`docker exec -it`, `ls -la`)
      were never recognized as `-i` + `-t` / `-l` + `-a` - both flags
      were already correctly documented individually, just never
      reachable under their combined shell-convention spelling.** This
      one is retrieval-layer, not a data gap: added
      `find_bundled_short_flags_within` to `mentor_core.py`, which
      splits a `-XY` token into individual `-X`/`-Y` flags and reuses
      the existing exact-match search across whichever of them are real
      - applies to any complete-reference command, not just Docker.
    All four verified live and against the full regression set; three
    needed a pipeline rebuild (iptables/checksum/nft), the fourth was
    retrieval-only. 171,775 -> 174,623.
49. **Two more retrieval-layer fixes, both found while building and
    live-testing the desktop GUI (see 01_Project_Overview.md "Desktop
    UI") - out of order with the item above chronologically, but
    recorded here since they weren't written up at the time.**
    - **The `"service"`/portablectl collision from item 46 was one
      instance of a much bigger pattern: any common English verb that's
      ALSO a real Windows command name breaks natural "how do/can I..."
      questions.** `"how can i copy a file over ssh?"` - previously a
      documented working example - silently started returning Windows'
      `copy` command instead of `scp`'s real intent answer, because
      `"copy"` (like `"rename"`, `"list"`, `"add"`, `"tab"`,
      `"service"` before it) is also a real command name. Rather than
      keep enumerating individual words into `GENERIC_WORD_COMMAND_NAMES`
      forever, added `INTENT_PHRASE_PATTERN` - any question matching a
      natural intent-question opener ("how do/can I...", "I want to...",
      "I need...") skips command-scoping entirely, regardless of which
      incidental word triggered the false match. Verified this fixes
      `copy`/`rename`/`service` uniformly (0.75-0.98 similarity on
      unrestricted search in every case checked) without regressing
      bare "what does X do?" questions about the same words. A related
      phrasing-consistency gap surfaced right after: `"windows rename
      file"` (no "how do I" opener) still routed differently than `"how
      can i rename a file"` - added `"rename"`/`"copy"` to
      `GENERIC_WORD_COMMAND_NAMES` too, so bare mentions of these words
      never trigger narrow command-scoping either, matching how
      `"service"`/`"list"`/`"add"`/`"tab"` already worked.
    - **The LoRA adapter was so narrowly specialized on the IT
      command-reference format that it couldn't hold a normal
      conversation - asking it "merhaba" produced a fabricated fake
      command reference (a "kimsin sen" command that doesn't exist).**
      Since this only matters for the already-disclosed "no data, this
      is a guess" fallback path, and `peft` (the LoRA library already
      in use) ships `model.disable_adapter()` as a context manager that
      runs the SAME loaded model with the adapter weights switched off
      - no separate model file, no retraining, no extra memory - this
      was a one-line fix: `generate_with_model` now takes a
      `use_adapter` flag, and the fallback path passes `False`. The
      base model handles greetings and off-topic chat naturally
      ("Merhaba! Size nasıl yardımcı olabilirim?") instead of
      hallucinating fake commands. Trade-off, confirmed by comparing
      both on real gap questions: for genuinely obscure but real IT
      questions (e.g. `Get-Item -ErrorAction`), the LoRA-adapted model
      was sometimes more specific/accurate since it's locked into the
      IT-reference format - the base model is vaguer but never invents
      a fake authoritative-looking reference. Given the fallback path
      is already labeled "don't trust this," judged the safety
      improvement worth the precision trade for the cases that stay in
      generative fallback after everything else in this document is
      fixed.
    Both retrieval-layer only, no dataset change.

## Scale History

| Stage | Examples | Note |
|---|---|---|
| Original | 12,702 | Baseline before this pass |
| Unfiltered Linux source | 113,348 | Included ~6,600 irrelevant tldr commands (`yacas`, `wine reg copy`...) - reverted |
| Curated Linux + intent category | 19,408 | Right-sized |
| + parameter phrasing diversity + overview category | 41,060 | |
| + Windows shortcuts | 41,644 | |
| + GNU coreutils (complete option lists) | 45,996 | |
| + GNU grep (complete option list) | ~60,464 | Also includes nested-table and borrows_from fixes |
| + `command` field on every row (for scoped retrieval) | 63,713 | No new examples, metadata only |
| + macro-expansion fix (276 recovered parameters) | 64,387 | |
| + Docker CLI (143 commands) | ~70,810 | |
| + systemd (16 files) | ~74,782 | Also includes coreutils description-quality fixes |
| + windows-commands table-parser fallback (4,793 recovered parameters) | 98,667 | |
| + windows-powershell-docs (695 cmdlets: AD, ScheduledTasks, NetSecurity, DNS/DHCP, networking, GroupPolicy) | ~155,013 | Largest single addition in the project |
| + nftables + troff/man parser (cron, iptables, ufw) | 156,330 | First new parser format (troff) since project start |
| + ssh/OpenSSH + mdoc parser (519 parameters, 15 manuals) | 159,106 | Second new parser format |
| + apt (reused DocBook parser) + dnf + new RST parser (389 parameters, 4 files) | 162,294 | Third new parser format; closes every originally-identified tool-family gap |
| + fix apt/dnf missing from `COMPLETE_REFERENCE_SOURCES`, plus the tldr hyphen-to-space merge bug (ssh-keygen, apt-get, apt-cache, systemd-analyze) | 162,234 | No new source; orphaned duplicate records absorbed into their correct merged record |
| + capture DocBook tools' own subcommands as retrievable data (systemctl, journalctl, loginctl, timedatectl, systemd-analyze...) | 162,988 | No new source; recovers subcommand descriptions that were previously only a name in a summary sentence |
| + fix mdoc escape-sequence leaks (ssh-docs) | 162,988 | No new source; pure text cleanup |
| + fix PowerShell `CommonParameters` syntax-deletion bug + git bare-flag (non-backtick) parsing bug | 169,736 | No new source; two sizeable data-completeness bugs found via manual live-question review |
| + fix git `COMMANDS`-section gap, git term/description blank-line bug, PowerShell parameter `CommonParameters` bleed | 170,666 | No new source; found while investigating the two bugs above, not a separate pass |
| + rewrite git term-parsing to handle flush-left descriptions + bare/dash-less subcommand terms | 171,559 | No new source; closes the item-38 known gap, plus one more found while fixing it |
| + dnf command-reference parser, nftables add/delete/list/flush disambiguation, git hyphen-naming fix (86 commands), git DESCRIPTION/SEQUENCER SUBCOMMANDS flags | 172,126 | No new source; found via a structured 150-question audit across every source |
| + fix `find_mentioned_command`'s equal-length tiebreak (nft/dnf losing to unrelated Windows commands), fix a bare-flag short-question collision (dnf `list`) | 170,085 | No new source; a retrieval bug and a duplicate-question guard, both found while verifying the row above |
| + fix Docker's example-extraction bug (`docker push`/`docker load`), strip image-alt-text and AsciiDoc anchor leaks | 170,081 | No new source; a second fresh-question audit's one real code bug plus two cosmetic leaks (net use / two Windows shortcuts confirmed as genuine source gaps, not fixed) |
| + fix five retrieval-layer bugs found by a third, 438-question audit (generic-word command collisions, dot/space command-name mismatch, position-independent directive matching, systemd shared-directive cross-reference, source-grounded + exact-match shortcut scoping) | 170,081 | No new source; `test_model.py` only, dataset unchanged. Confirmed more genuine source gaps (`apt-key`, `apt-get moo`, `apt list --all-versions`, `networkctl`/`busctl`/`machinectl`/`portablectl`/`resolvectl`, 8 more missing keyboard shortcuts), none fabricated |
| + fill the confirmed-fixable gaps: 22-command `net` family (archived Microsoft docs), `apt-key` (Debian's current manpage), 5 systemd CLI tools (already-cloned files, just uncurated), 2 keyboard shortcuts; plus fix a description-corrupting bug affecting the whole apt/systemd/nftables DocBook family | 171,687 | New sources: `net-*.md` (22 files), `apt-key.8.xml`, 5 systemd `allowed_names` entries, 2 shortcut entries. Also one real parser bug fix (`parse_systemd_xml` variable shadowing) and two retrieval fixes (`net help` boilerplate collision, digit-shortcut matching) |
| + exclude two bogus "commands" extracted from conceptual Windows Server articles (`what is`, `overview`) that collided with this project's own question templates; recover git flags documented under two previously-unscanned AsciiDoc section titles (`MODE OPTIONS`, `DEPRECATED MODES`) | 171,775 | No new source; found via measuring the generative-fallback rate (8.7% of ~763 real test questions) and tracing its two largest contributors |
| + add the 94-fragment iptables extensions source (`--dport`/`--sport`/`--tcp-flags`/`--syn`/`--state`...), fix the checksum-family borrowing gate (`b2sum`, `sha224/256/384/512sum`), recover two more nftables `<refsect2>` subcommand title patterns (`describe`/`export`/`monitor`); plus a retrieval-layer fix for bundled short flags (`docker exec -it`, `ls -la`) | **174,623** | New source: `iptables-extensions-docs` (94 `.man` fragments, reusing the troff-man option scanner directly - no include-marker resolution needed). Also two parser bug fixes (checksum borrowing gate, nft subcommand paragraph selection) and one general retrieval fix |

## Current Category Breakdown

description 9,242 / syntax 5,280 / example 4,494 / parameter 142,264 /
overview 9,216 / intent 4,127. Total: 174,623.

## New Category: intent (unchanged design, for reference)

Template-based, not LLM-generated, to avoid the hallucination risk of
the two abandoned LLM-generator scripts earlier in this project:
- tldr: each command's own example bullets become direct pairs
- Git: capability phrase from the doc title, restricted to real
  subcommands (`git-*`) - conceptual docs like `gitattributes` have
  noun-phrase titles that don't fit the imperative template
- PowerShell/Windows: synopsis reused in a grammar-safe frame needing
  no verb conjugation
- Windows shortcuts: the action description becomes the intent phrase

## New Category: overview

Lists *all* known parameters for a command in one answer (only when
the underlying data actually has them - see the coreutils addition
above for why this used to be thin for Linux commands).
