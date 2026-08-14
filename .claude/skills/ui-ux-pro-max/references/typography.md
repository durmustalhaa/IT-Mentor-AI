# Typography

Five `tkfont.Font` objects are created once in `App.__init__` and reused
everywhere. Never pass a raw `("Segoe UI", 11)` tuple to a new widget if one
of these already fits — reuse the object so a future size/family change is
one edit, not a grep-and-replace.

| Font object | Family | Size | Weight | Used for |
|---|---|---|---|---|
| `self.mono_font` | Consolas | 11 | regular | Model answer text (`_add_answer`) — monospace reads better for command/code-heavy output |
| `self.ui_font` | Calibri | 12 | regular | Status label, entry field, question bubble text — general chrome and the user's own words |
| `self.bold_font` | Calibri | 12 | bold | The send button's arrow glyph (`"↑"` drawn via `create_text`) |
| `self.title_font` | Calibri | 18 | bold | Window title label only |
| `self.small_font` | Calibri | 10 | regular | The persistent disclaimer label — deliberately smaller since it's secondary, always-on chrome, not primary content |

**Calibri, not Segoe UI.** Changed during the redesign — the user referenced
a ChatGPT-style screenshot and asked for a similar warmer, more humanist
feel than Segoe UI's default Windows-UI look. Calibri was picked
specifically because it ships with Windows/Office by default (no font
file to bundle, no licensing question) while reading noticeably softer
than Segoe UI. If a closer match to that reference is wanted later, the
actual font in that kind of reference is usually a paid/non-system font
(e.g. Söhne) — that would require bundling a `.ttf` and loading it via
`ctypes`/`AddFontResourceEx`, a meaningfully bigger change than swapping
a `family=` string. The user was asked and explicitly chose the
system-font route over bundling one.

## Rules

1. **Base size is 12pt.** Don't drop below it for anything meant to be read
   continuously (answers, questions, status) — this is a desktop app with no
   pinch-zoom, so small text is a real accessibility problem, not a
   stylistic risk. The 10pt disclaimer is the one deliberate exception,
   because it's short, secondary, and always visible rather than something
   the user reads closely every time.
2. **Calibri is the UI voice, Consolas is the model's voice.** Keep that
   split: anything the app itself is saying (labels, status, disclaimer,
   and — notably — the user's own question bubble, since that's the user's
   input being echoed, not the model's output) is Calibri; anything that's
   the model's generated output (`_add_answer`) is Consolas. Don't mix them
   within the same semantic role.
3. **Bold is reserved for the send icon glyph and the window title.**
   There's no "Ask" button anymore (see `references/components.md`) — the
   only bold text left is the `"↑"` glyph on the circular send button and
   the title label. The user's question is NOT bold (it was in an earlier
   version) — it's distinguished by the bubble background and
   right-alignment instead, so don't add bold back to it.
4. **New font need?** Create it once as `self.<role>_font = tkfont.Font(...)`
   in `__init__` next to the existing five, name it by role
   (`self.error_font`, not `self.font2`), and reuse the object everywhere
   that role appears.
