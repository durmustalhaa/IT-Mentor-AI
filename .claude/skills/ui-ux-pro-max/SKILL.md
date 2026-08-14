---
name: ui-ux-pro-max
description: >
  IT Mentor AI's desktop UI design system (Tkinter, cream/black minimalist
  theme, English copy). Use whenever adding, modifying, or reviewing anything
  in scripts/gui_app.py, adding a new window/dialog/screen to the desktop
  app, or touching colors, fonts, spacing, widget styling, status/disclaimer
  text, or the model-loading/answer threading flow. Keeps new UI consistent
  with the existing look (BG #E8DFC5, BUBBLE_BG #D6C8A3, ACCENT #1B1916,
  Calibri / Consolas fonts, rounded Canvas-drawn shapes, no pure white
  anywhere) and with the thread-safe queue pattern that keeps the Tkinter
  main loop from freezing during model load/inference.
  Trigger on: "UI", "arayüz", "pencere", "widget", "tkinter", "gui_app",
  "tasarım", "renk", "font", "buton", "layout", "ekran ekle", or any request
  to change how the app looks or behaves visually.
license: MIT
---

# IT Mentor AI — Desktop UI Design System

This is a single-window **Tkinter** desktop app (`scripts/gui_app.py`), cream/
black themed, English-language, wrapping `mentor_core.py`'s model. It is not
a web app — there is no CSS, no dark mode, no responsive breakpoints.
Everything below is derived from the actual working code, not aspirational.

## Redesign history (2026-08-13)

The app was originally dark-themed (`#1e1e2e`) with Turkish copy. It went
through several passes in one session:

1. **Cream/black + English copy**, modeled on a Gemini-style reference
   (right-aligned user bubbles, borderless flowing answer text, a compact
   persistent disclaimer). This surfaced a real Tkinter constraint worth
   remembering: **a `Text` widget's tag `background` always fills the full
   line width**, regardless of `justify` or `lmargin1`/`lmargin2` —
   confirmed by testing, not assumed. A real content-hugging bubble is NOT
   achievable with a single `Text` widget's tags, which is why the chat
   area is a scrollable `Canvas` + `Frame` with one widget per message
   instead.
2. **Rounded corners, no pure white, Calibri font, an icon-only send
   button, a thin custom scrollbar, and a recolored native title bar** —
   a second pass, again against a reference screenshot. Rounded shapes
   need the same kind of workaround as the bubble did: Tkinter has no
   `border-radius`, so every rounded shape (bubble, input pill, scrollbar
   thumb) is drawn on a `Canvas` via a shared `_draw_rounded_rect` helper
   (`create_polygon(..., smooth=True)` with corner-cutting points). The
   classic `tk.Scrollbar` was tried and looked chunky/out of place, so it
   was replaced with a custom-drawn thin thumb. The native OS title bar
   was recolored via the Windows DWM API (`ctypes` + `DwmSetWindowAttribute`,
   Windows 11+ only, safely no-ops elsewhere).
3. **`ENTRY_BG` was corrected mid-pass** — an early version of the input
   pill used a noticeably lighter cream fill and the user flagged it as
   "reads as white, doesn't match the theme." Fixed by setting `ENTRY_BG`
   equal to `BG` and relying entirely on `OUTLINE_COLOR`'s border for the
   pill's visual definition, not a fill contrast.
4. **A third pass fixed a still-visible white box, jagged edges, and
   choppy scrolling.** The remaining white box turned out to be a
   different bug than #3 above: `tk.Entry` uses `disabledbackground`/
   `disabledforeground` (not `bg`/`fg`) while `state="disabled"`, which
   was never set, so the entry fell back to a system default color every
   time it was disabled (while loading, while awaiting an answer). The
   `create_polygon`/`create_oval`-based rounded shapes from pass 2 were
   never anti-aliased and looked jagged once actually looked at closely —
   replaced with PIL-rendered images (`_rounded_rect_image`/
   `_circle_image`, 4x supersampled then downscaled with `LANCZOS`) for
   every rounded/circular shape. Mouse wheel scrolling felt "frame by
   frame" because Tk's default scroll unit on this canvas was coarse —
   fixed with `yscrollincrement=1` plus a fixed pixel-per-notch handler.
5. **Answers became selectable.** The user wanted normal click-drag text
   selection + Ctrl+C copying on answers. A one-click "Copy" link was
   tried first and explicitly rejected — the user wanted real selection,
   not a shortcut around it. `Label` can't be selected at all in Tkinter,
   so `_add_answer` switched to a `Text` widget (`state="disabled"` blocks
   editing only, not selection/copy) with its height measured from the
   actual wrapped line count after layout, since `Text` has no
   `wraplength`-style auto-sizing. See `references/components.md`.

## Non-negotiables

1. **Cream/black theme only, no pure white anywhere.** Every surface uses
   `BG`, `BUBBLE_BG`, `ENTRY_BG`, or `OUTLINE_COLOR` — never a hardcoded hex
   not in the palette, and never white/near-white as a fill (see
   `references/palette.md` for why this was explicitly corrected once).
2. **English UI copy.** Labels, statuses, disclaimers — all English,
   terse/lowercase for status fragments, matching existing strings
   ("loading...", "thinking...", "ready"). See `references/tone-copy.md`.
3. **Never block the Tk main thread.** Model load and inference run in
   `threading.Thread`, results flow back via the `_ui_queue` +
   `root.after(50, _poll_queue, root)` pattern. See
   `references/interaction-threading.md`.
4. **Reuse tokens, don't invent them.** Colors, fonts, and spacing are
   defined once at module level and referenced everywhere. A new widget
   needing a new visual role gets a new named constant, not an inline hex.
5. **User messages are bubbles, answers are plain flowing text.** This
   asymmetry is intentional — don't add a bubble/background to answer
   text, and don't remove the bubble from user questions.
6. **Rounded/circular shapes are PIL-rendered (`_rounded_rect_image`/
   `_circle_image`), never `Canvas.create_polygon`/`create_oval`.** Tk's
   raw Canvas primitives aren't anti-aliased and looked visibly jagged
   (explicit user feedback) — every rounded surface (bubble, input pill,
   scrollbar thumb, send button) is drawn at 4x resolution and downscaled.
   `Pillow` is a real `requirements.txt` dependency because of this. See
   `references/layout-spacing.md`, including the "keep a reference to the
   PhotoImage or it vanishes" gotcha.
7. **There is no "Ask" button.** The send control is a circular `Canvas`
   button that only appears once the entry has text (see
   `references/components.md`). Don't reintroduce a permanent text button
   as "the" submit control.
8. **Disclaimer stays intact, but small and persistent.** `DISCLAIMER_TEXT`
   is a single always-visible small-font label above the input row, not a
   one-time chat message. Don't drop its substance (no accuracy guarantee,
   verify before critical actions) even when rewording.

## Quick reference (see `references/` for the full detail)

| Token | Value | Role |
|---|---|---|
| `BG` | `#E8DFC5` | Window background, chat area background, send-button icon color |
| `BUBBLE_BG` | `#D6C8A3` | User's own question bubble background |
| `ENTRY_BG` | `#E8DFC5` (= `BG`) | Input pill fill — intentionally not a distinct color, see redesign history |
| `OUTLINE_COLOR` | `#C4B48C` | Input pill border, scrollbar thumb |
| `USER_COLOR` | `#1B1916` | User's question text, window title, native title bar text |
| `ANSWER_COLOR` | `#2B2823` | Model answer text |
| `STATUS_COLOR` | `#8C8478` | Status label ("loading...", "thinking...") |
| `ACCENT` | `#1B1916` | Send button circle, native title bar background — black, not a bright color |
| `DISCLAIMER_COLOR` | `#9C7A3C` | Persistent disclaimer label text |
| `SUCCESS_COLOR` | `#5B6B4F` | "ready" status text |

Fonts: **Calibri** for all UI chrome (labels, status, entry, bubble text),
**Consolas** for model answers (monospace reads better for command output),
12pt base, 18pt bold for the window title, 10pt for the disclaimer. Full
rules: `references/typography.md`.

## Adding a new UI element — checklist

1. Does an equivalent already exist? Reuse its exact color/font constants,
   don't restyle.
2. New color role? Add one named constant at the top of the file, never an
   inline literal in a widget call — and never introduce white/near-white.
3. New rounded shape? Use `_draw_rounded_rect(canvas, x1, y1, x2, y2, radius, **kwargs)` —
   don't hand-roll another rounding technique.
4. New long-running action (network, disk, model call)? Runs in a
   `threading.Thread(daemon=True)`, posts results through `_ui_queue`. Never
   call Tk widget methods from a background thread directly.
5. New message type in the chat area? Follow `_add_question`/`_add_answer`'s
   pattern — a row `Frame` packed into `chat_frame`, with the message
   packed `side="right"` (bubble) or `side="left"` (plain) depending on
   whether it's "the user's own input" or "system/model output." Call
   `self._scroll_to_bottom()` after adding.
6. New window/dialog? Same `BG`, same icon (`ICON_PATH`), same font objects,
   and consider whether it needs `_set_native_title_bar_color()` too.
7. Disabling/enabling controls during async work — mirror `_on_submit`'s
   `self._ready` flag pattern, not a widget `state`, since the send control
   is a `Canvas` with no built-in disabled state.
8. Errors surfaced to the user go through the same chat flow as answers
   (`f"Something went wrong: {exc}"` via `_add_answer`), not a popup,
   unless the error is blocking enough to need one.

## Reference files

- `references/palette.md` — full color rationale, contrast notes, why
  there's no white, when to add a new color vs. reuse one.
- `references/typography.md` — font objects, sizing scale, why Calibri.
- `references/layout-spacing.md` — `pack()` conventions, padding values,
  the `_draw_rounded_rect` helper, the custom scrollbar, the input pill,
  window sizing.
- `references/components.md` — recipes for the existing widgets (header +
  native title bar, scrollable chat area, question bubble, answer row,
  persistent disclaimer, input pill + send button) and how to extend them.
- `references/interaction-threading.md` — the load/answer threading + queue
  pattern in full, plus how to add a new async action safely.
- `references/tone-copy.md` — English microcopy conventions: status verbs,
  disclaimer requirements, error phrasing, register.
