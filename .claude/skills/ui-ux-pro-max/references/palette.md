# Palette

All colors are defined as module-level constants at the top of
`scripts/gui_app.py`. This is the complete set — do not introduce a new hex
literal inline in a widget call; add a named constant here (and in the code)
instead.

| Constant | Hex | Used for | Contrast role |
|---|---|---|---|
| `BG` | `#E8DFC5` | Root window, header, chat area, input pill fill, send-button icon color | Base surface — warm, deliberately not-too-light cream |
| `BUBBLE_BG` | `#D6C8A3` | User's own question bubble | Darker cream, one clear step down from `BG` — this is what makes the bubble read as a distinct surface, no border needed on it |
| `ENTRY_BG` | `#E8DFC5` (same value as `BG`) | Input field fill | Deliberately identical to `BG` — an earlier version used a lighter, near-white tone here and it read as "a white box that doesn't belong," which the user explicitly flagged. The input pill is now defined entirely by `OUTLINE_COLOR`'s border, not by a fill contrast. If `BG` ever changes, update this alongside it (or just reference `BG` directly instead of a separate constant, if this file is ever refactored). |
| `OUTLINE_COLOR` | `#C4B48C` | Input pill border, scrollbar thumb | The one mid-tone accent between `BG` and `USER_COLOR` — used for anything that needs to read as "structural chrome" (a boundary, a scroll handle) without being a full-strength text/action color |
| `USER_COLOR` | `#1B1916` | User's own question text, window title, native title bar text | Near-black, warm undertone (not pure `#000000`) |
| `ANSWER_COLOR` | `#2B2823` | Model's answer text | Slightly softer than `USER_COLOR` |
| `STATUS_COLOR` | `#8C8478` | Status label ("loading...", "thinking...") | Muted warm gray, secondary-information tone |
| `ACCENT` | `#1B1916` | Send button circle background, native title bar background | Black, not a bright/blue accent |
| `ACCENT_PRESSED` | `#3A342C` | Reserved for a pressed/active state (not currently wired up — the send button is a `Canvas`, not a `tk.Button`, so it has no built-in `activebackground`; if hover/press feedback is added later, this is the color to use) | Lighter warm charcoal |
| `DISCLAIMER_COLOR` | `#9C7A3C` | Persistent disclaimer label | Muted gold/ochre |
| `SUCCESS_COLOR` | `#5B6B4F` | Status label once ready ("ready") | Muted sage green |

## Rules for adding a color

1. **Reuse before adding.** If the new element is another status message,
   use `STATUS_COLOR`. Another notice, use `DISCLAIMER_COLOR`. A new
   structural/chrome element (border, handle, divider), use `OUTLINE_COLOR`
   before inventing a near-duplicate shade.
2. **New semantic role → new named constant**, defined next to the existing
   ones at the top of the file, `SCREAMING_SNAKE_CASE`.
3. **Never hardcode a hex string** more than once.
4. **No pure white, anywhere.** This was a deliberate, explicit correction
   during the redesign (`PANEL_BG = "#FFFFFF"` was removed entirely) — every
   surface, including input fields, uses a cream-family tone. If a new
   surface needs to look "raised" or "distinct," reach for contrast via
   `BUBBLE_BG` (darker) or an `OUTLINE_COLOR` border, not a lighter/whiter
   fill.
5. **No blue/bright accent color exists on purpose.** The palette is
   deliberately two base tones (cream family + near-black) plus a chrome
   accent (`OUTLINE_COLOR`) and two sparing semantic accents (disclaimer
   gold, success sage). Don't add a third "brand" accent color for a new
   primary action — reuse `ACCENT` (black).
6. **Contrast**: fixed light/cream theme, no accessibility toggle — hold
   every new text color to the same bar the existing ones clear
   (~4.5:1 against `BG`/`BUBBLE_BG`).

## Why `BG` got darker mid-redesign

The first pass used a lighter cream (`#F3EEE3`). The user asked for a
"slightly darker cream" as a follow-up refinement — this is why `BG`,
`BUBBLE_BG`, and `ENTRY_BG`'s values look like a cohesive family rather than
arbitrary choices: they were re-tuned together in one pass. If asked to
darken/lighten the theme again, shift all three together, keeping
`BUBBLE_BG` one visible step darker than `BG` and `ENTRY_BG` matching `BG`
exactly (see the `ENTRY_BG` row above for why).
