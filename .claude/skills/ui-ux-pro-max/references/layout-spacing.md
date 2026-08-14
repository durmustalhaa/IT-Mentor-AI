# Layout & Spacing

The window uses plain `pack()` geometry management — no `grid()`, no
`place()` — for the top-level sections. Only reach for `grid()` if a
genuinely two-dimensional layout is added, and scope it to that one
sub-frame.

## Window

- `root.geometry("780x660")` — default size.
- `root.minsize(480, 420)` — floor below which the layout would break.
- Five vertical sections, packed top-to-bottom: **header** → **chat area**
  (`fill="both", expand=True` — the only one that expands) → **disclaimer
  label** → **input row**.
- The native Windows title bar is recolored to match the palette via
  `_set_native_title_bar_color()` (DWM API, Windows 11+, see
  `references/components.md`) — this is OS-level chrome, not a Tk widget,
  but it's part of the same visual system and should stay in sync if `BG`/
  `USER_COLOR` change.

## Rounded corners: PIL-rendered, not `create_polygon`

Tkinter has no native `border-radius`. **First attempt** used
`Canvas.create_polygon(..., smooth=True)` with corner-cutting points — this
rounds the shape geometrically, but Tk's Canvas primitives aren't
anti-aliased, so the curved edges came out visibly jagged/pixelated
(explicit user feedback: "tırtıklı", comparing against a reference
screenshot). **Fixed by rendering with PIL instead** — draw at 4x
resolution (`_SUPERSAMPLE`), then downscale with `Image.LANCZOS`, which
*does* anti-alias:

```python
def _rounded_rect_image(width, height, radius, fill, outline=None, outline_width=0):
    width, height = max(1, round(width)), max(1, round(height))
    ss = _SUPERSAMPLE
    img = Image.new("RGBA", (width * ss, height * ss), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    ow = outline_width * ss
    inset = ow / 2
    draw.rounded_rectangle(
        [inset, inset, width * ss - 1 - inset, height * ss - 1 - inset],
        radius=radius * ss, fill=fill, outline=outline, width=round(ow) if ow else 0
    )
    img = img.resize((width, height), Image.LANCZOS)
    return ImageTk.PhotoImage(img)


def _circle_image(diameter, fill):
    diameter = max(1, round(diameter))
    ss = _SUPERSAMPLE
    img = Image.new("RGBA", (diameter * ss, diameter * ss), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([0, 0, diameter * ss - 1, diameter * ss - 1], fill=fill)
    img = img.resize((diameter, diameter), Image.LANCZOS)
    return ImageTk.PhotoImage(img)
```

Usage is always the same three steps: generate the image, **keep a
reference to it** (Tkinter's `PhotoImage` is garbage-collected the instant
nothing in Python references it, even though the `Canvas` is still
displaying it — every call site stashes it as an arbitrary attribute on
the canvas itself, e.g. `self.entry_canvas.bg_image = bg_image`, purely to
keep it alive), then `canvas.create_image(x, y, anchor="nw", image=...)`.
**Any new rounded/circular shape reuses these two helpers** — don't go
back to `create_polygon`/`create_oval` for anything meant to look smooth,
and don't drop the "keep a reference" step or the shape will render once
and then vanish on the next event loop tick.

`Pillow` is a real runtime dependency now (`requirements.txt`) because of
this — it wasn't before the redesign (it was only used in a one-off
scratch script to generate `assets/app_icon.ico`).

**Radius clamped to half the shorter side inside PIL's own
`rounded_rectangle`** — passing `radius=h/2` (input pill, scrollbar thumb)
always produces a full stadium/pill shape regardless of exact height.

## The scrollable chat area

See `references/components.md` for the full `Canvas`/`Frame` setup and why
a plain `Text` widget can't produce a real content-hugging bubble.

- `chat_outer`'s padding is `padx=(28, 20), pady=8` — the `20` on the right
  leaves room for the thin custom scrollbar (see below) plus its own `6`px
  gap, without the scrollbar sitting flush against the window edge.
- After adding any message widget, call `self._scroll_to_bottom()`
  (`update_idletasks()`, recompute `scrollregion`, then
  `yview_moveto(1.0)`) — skipping this leaves the canvas scrolled to the
  top even though it has scrollable content, looking empty.

## Custom scrollbar (not `tk.Scrollbar`)

A classic `tk.Scrollbar` was tried first and looked chunky/out of place
against the rest of the design (explicit user feedback, compared against a
reference screenshot of a thin minimal scroll indicator). Replaced with a
6px-wide `Canvas` (`SCROLLBAR_WIDTH`) drawing its own thumb:

```python
self.scrollbar_canvas = tk.Canvas(chat_outer, width=SCROLLBAR_WIDTH, bg=BG, highlightthickness=0, borderwidth=0)
self.scrollbar_canvas.pack(side="right", fill="y", padx=(6, 0))
self.scrollbar_canvas.bind("<Configure>", lambda _e: self._redraw_scrollbar())
self.scrollbar_canvas.bind("<Button-1>", self._on_scrollbar_drag)
self.scrollbar_canvas.bind("<B1-Motion>", self._on_scrollbar_drag)

self.chat_canvas.configure(yscrollcommand=self._on_scroll_update)
```

`_on_scroll_update(first, last)` is what Tk normally hands to a real
`Scrollbar`'s `.set()` — here it's redirected to store `(first, last)` as
fractions and redraw. `_redraw_scrollbar()` draws a PIL-rendered rounded
thumb (`OUTLINE_COLOR`, via `_rounded_rect_image` — see above) sized/
positioned from those fractions, enforces `SCROLLBAR_MIN_THUMB = 28`px so
a very long chat doesn't shrink the thumb below a draggable size, and
draws **nothing at all** when `last - first >= 0.999` (content fits,
nothing to scroll — no empty track shown, unlike a real `Scrollbar` which
always shows a full-height trough). `_on_scrollbar_drag` converts a
click/drag's `event.y` directly to a `yview_moveto` fraction — no separate
"page up/down" click zones, just drag-anywhere-in-the-track. **If this
needs richer behavior later (click above/below thumb to page, keyboard
scroll), extend these two methods — don't reintroduce a real `Scrollbar`
alongside them.**

**Mouse wheel scrolling is pixel-based, not Tk's default chunky "units."**
`self.chat_canvas.configure(yscrollincrement=1)` makes one "unit" equal one
pixel, and the wheel handler scrolls a fixed
`MOUSEWHEEL_PIXELS_PER_NOTCH = 60` px per notch:
```python
self.chat_canvas.bind_all("<MouseWheel>", lambda e: self.chat_canvas.yview_scroll(
    int(-1 * (e.delta / 120) * MOUSEWHEEL_PIXELS_PER_NOTCH), "units"
))
```
Without `yscrollincrement=1`, Tk's default unit size on a canvas with a
large scrollregion is much coarser, which is what made scrolling look
"frame by frame" / choppy (explicit user feedback) before this was set.

## The input pill

`self.entry_canvas` is a `Canvas` sized to the input row's height
(`INPUT_HEIGHT = 54`), redrawn on every resize:

```python
def _redraw_entry_background(self, event=None):
    w = self.entry_canvas.winfo_width()
    h = self.entry_canvas.winfo_height()
    self.entry_canvas.delete("bg")
    if w <= 4 or h <= 4:
        return
    bg_image = _rounded_rect_image(w, h, radius=h / 2, fill=ENTRY_BG, outline=OUTLINE_COLOR, outline_width=2)
    self.entry_canvas.bg_image = bg_image  # keep a reference alive
    self.entry_canvas.create_image(0, 0, anchor="nw", image=bg_image, tags="bg")
    self.entry_canvas.tag_lower("bg")
    entry_width = max(10, int(w - 40))
    if self._entry_window_id is None:
        self._entry_window_id = self.entry_canvas.create_window(20, h / 2, window=self.entry, anchor="w", width=entry_width)
    else:
        self.entry_canvas.coords(self._entry_window_id, 20, h / 2)
        self.entry_canvas.itemconfig(self._entry_window_id, width=entry_width)
```

The actual `tk.Entry` is a real, functional widget embedded inside the
canvas via `create_window` — the canvas only supplies the rounded/outlined
background image behind it. `tag_lower("bg")` keeps the background image
behind the embedded entry window on every redraw (Canvas z-order isn't
automatic when items are re-created). **`ENTRY_BG` equals `BG` exactly** —
the pill has no fill contrast of its own, only the `OUTLINE_COLOR` border
defines its edge (see `references/palette.md` for why — an earlier
lighter fill read as "a white box," which was explicitly rejected).

**The `tk.Entry` also needs `disabledbackground`/`disabledforeground` set
explicitly**, not just `bg`/`fg`:
```python
self.entry = tk.Entry(self.entry_canvas, textvariable=self.entry_var, bg=ENTRY_BG, fg=USER_COLOR,
                        disabledbackground=ENTRY_BG, disabledforeground=USER_COLOR,
                        insertbackground=USER_COLOR, font=self.ui_font,
                        relief="flat", borderwidth=0, highlightthickness=0)
```
Classic (non-`ttk`) `tk.Entry` swaps to `disabledbackground`/
`disabledforeground` while `state="disabled"`, ignoring `bg`/`fg`
entirely. Without setting these, the entry fell back to a system default
(light gray/white) every time it was disabled (while the model is loading,
and while waiting for an answer) — which is exactly the "white box" the
user pointed out, and it's a *different* bug from the `ENTRY_BG` color
choice documented in `references/palette.md` (that one was about the
enabled-state fill being too light; this one is about the disabled state
not respecting the fill color at all). Both needed fixing.

If a second bordered/rounded input-like control is ever needed, follow
this same pattern (sizing `Canvas` + `_rounded_rect_image` +
`create_window`-embedded real widget, remembering `disabledbackground` if
it's ever disabled) rather than trying to style a plain `tk.Entry`'s
`relief`/`highlightthickness` to fake rounding — that doesn't work in
Tkinter.

## Padding conventions

| Location | Value | Notes |
|---|---|---|
| Header frame | `padx=28, pady=(20, 8)` | Outer margin |
| Chat area (`chat_outer`) | `padx=(28, 20), pady=8` | Right side reserves room for the thin scrollbar |
| Disclaimer label | `padx=28, pady=(0, 8)` | Matches the horizontal margin used everywhere |
| Input row frame | `padx=28, pady=(0, 26)` | Larger bottom margin at window edge |
| Question bubble canvas | `pad_x, pad_y = 18, 12` (computed into the canvas's own size, not `Canvas` padding) | Internal inset within the bubble |
| Send button gap | `padx=(10, 0)` on `pack` | Space between the input pill and the send button once it appears |

**Rule of thumb:** outer window margin is `28`, inter-element gaps are
`8–10`. A new top-level section follows the `28` outer margin.

## Message row spacing (inside `chat_frame`)

- Question row: `pady=(10, 2)`.
- Answer row: `pady=(2, 18)`.

## Sizing constants

| Constant | Value | Role |
|---|---|---|
| `BUBBLE_RADIUS` | `16` | Question bubble corner radius |
| `INPUT_HEIGHT` | `54` | Input pill height — its radius (`(h-4)/2`) is derived from this, always a full stadium shape |
| `SEND_BUTTON_SIZE` | `44` | Circular send button diameter |
| `SCROLLBAR_WIDTH` | `6` | Custom scrollbar track width |
| `SCROLLBAR_MIN_THUMB` | `28` | Minimum draggable thumb height |

Bubble/answer `wraplength`: `420` for question bubbles, `660` for answer
text — fixed values tuned to the default `780`px window width, not
dynamically recalculated on resize.
