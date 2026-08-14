# Component recipes

Recipes for the widgets that already exist in `scripts/gui_app.py`, plus how
to extend each one without breaking its established pattern.

## Header + native title bar

```python
header = tk.Frame(root, bg=BG)
header.pack(fill="x", padx=28, pady=(20, 8))
tk.Label(header, text="IT Mentor AI", bg=BG, fg=USER_COLOR,
          font=self.title_font).pack(side="left")
self.status_label = tk.Label(header, text="loading...", bg=BG,
                               fg=STATUS_COLOR, font=self.ui_font)
self.status_label.pack(side="right")
```

- Title pinned left, status pinned right, single row. No divider line below
  it — borderless, matching the Gemini-style reference the theme is based
  on.

**The OS window title bar itself is also recolored**, via
`_set_native_title_bar_color(root, BG, USER_COLOR)`, called once from
`__init__` with `root.after(50, ...)` (needs the window to actually exist
at the OS level first):

```python
def _set_native_title_bar_color(root, bg_hex, text_hex):
    if sys.platform != "win32":
        return
    try:
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        def to_colorref(hex_color):
            r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
            return r | (g << 8) | (b << 16)
        DWMWA_CAPTION_COLOR, DWMWA_TEXT_COLOR = 35, 36
        caption, text = ctypes.c_int(to_colorref(bg_hex)), ctypes.c_int(to_colorref(text_hex))
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_CAPTION_COLOR, ctypes.byref(caption), ctypes.sizeof(caption))
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_TEXT_COLOR, ctypes.byref(text), ctypes.sizeof(text))
    except Exception:
        pass
```

- Uses `DWMWA_CAPTION_COLOR`/`DWMWA_TEXT_COLOR` (Windows 11 build 22000+
  only) — silently no-ops on older Windows via the bare `except Exception`,
  which is intentional here (title bar color is cosmetic, never worth a
  crash).
- **`GetParent(root.winfo_id())`, not `root.winfo_id()` directly** — the
  raw `winfo_id()` handle is a child/drawing-surface handle and
  `DwmSetWindowAttribute` fails on it (`E_HANDLE`, confirmed while
  building this); `GetParent` walks up to the actual top-level window
  handle DWM expects. If a second window (`Toplevel`) ever needs the same
  treatment, reuse this exact function — don't re-derive the handle
  differently.
- **Verifying this visually is hard in an automated/headless context** —
  `PrintWindow`-based screenshots (used elsewhere for testing this app)
  don't reliably capture DWM-composited non-client area changes. If you
  need to confirm a title-bar-color change worked, either check the
  `DwmSetWindowAttribute` return value directly (`0` = success) or ask for
  a real screenshot from someone looking at the actual screen — don't
  trust a `PrintWindow` capture's title bar as evidence either way.

## Chat area (scrollable, bubble-based)

See `references/layout-spacing.md` for the full `Canvas`/`Frame`/custom-
scrollbar setup. Each message is its own row:

```python
def _add_question(self, text: str):
    row = tk.Frame(self.chat_frame, bg=BG)
    row.pack(fill="x", pady=(10, 2))

    measurer = tk.Label(row, text=text, font=self.ui_font, wraplength=420, justify="left")
    measurer.update_idletasks()
    text_w, text_h = measurer.winfo_reqwidth(), measurer.winfo_reqheight()
    measurer.destroy()

    pad_x, pad_y = 18, 12
    canvas_w, canvas_h = text_w + pad_x * 2, text_h + pad_y * 2
    bubble = tk.Canvas(row, width=canvas_w, height=canvas_h, bg=BG, highlightthickness=0, borderwidth=0)
    bubble.pack(side="right")
    bg_image = _rounded_rect_image(canvas_w, canvas_h, BUBBLE_RADIUS, BUBBLE_BG)
    bubble.bg_image = bg_image  # keep a reference alive - see references/layout-spacing.md
    bubble.create_image(0, 0, anchor="nw", image=bg_image)
    bubble.create_text(canvas_w / 2, canvas_h / 2, text=text, font=self.ui_font,
                         fill=USER_COLOR, width=text_w, justify="left", anchor="center")
    self._scroll_to_bottom()

def _add_answer(self, text: str):
    row = tk.Frame(self.chat_frame, bg=BG)
    row.pack(fill="x", pady=(2, 18))
    answer_text = tk.Text(row, bg=BG, fg=ANSWER_COLOR, font=self.mono_font, wrap="word",
                            relief="flat", borderwidth=0, highlightthickness=0, padx=0, pady=0,
                            insertbackground=ANSWER_COLOR, selectbackground=OUTLINE_COLOR,
                            selectforeground=USER_COLOR, cursor="xterm", height=1)
    answer_text.pack(side="left", fill="x", expand=True)
    answer_text.insert("1.0", text)
    answer_text.update_idletasks()
    line_count = max(1, int(answer_text.count("1.0", "end", "displaylines")[0]))
    answer_text.configure(height=line_count, state="disabled")
    self._scroll_to_bottom()
```

- **Question bubbles are pure `Canvas` drawing** (a PIL-rendered rounded-
  rect image + `create_text` on top), not a `Label` — a `Label` can't have
  rounded corners, and a raw `Canvas.create_polygon` rounded rect isn't
  anti-aliased (see `references/layout-spacing.md` for why PIL renders
  every rounded shape now, not `create_polygon`). The two-step "measure
  with a throwaway `Label`, then draw on a `Canvas` sized to match"
  pattern exists because Tkinter's word-wrap logic lives in `Label`/`Text`,
  not in `Canvas.create_text` — reusing a real widget just to measure,
  then discarding it, is cheaper than reimplementing word-wrap.
- **Answer rows are a `Text` widget, not a `Label`.** This was a
  deliberate change — `Label` cannot be text-selected at all in Tkinter,
  and the user explicitly wanted normal click-drag selection + Ctrl+C
  copying on answers (an inline "Copy" link was tried first and
  explicitly rejected in favor of real selection). `state="disabled"` on
  a `Text` widget blocks *editing* only — selection and copying still
  work normally, which is exactly "read-only but selectable." No bubble/
  background (`bg=BG`, blends into the page) — that asymmetry (user =
  bubble, model = plain text) is still intentional, only the widget type
  changed.
- **`Text` has no auto-height-to-content the way `Label`'s `wraplength`
  does.** After inserting the text, `update_idletasks()` forces layout,
  then `answer_text.count("1.0", "end", "displaylines")[0]` gives the
  actual wrapped line count, which becomes the widget's `height` (in text
  lines). Do this *before* setting `state="disabled"` — line counting
  needs the widget briefly writable-and-laid-out first. Skipping this
  step leaves either dead space (height too tall) or clipped text (height
  too short/default).
- Question bubbles do NOT need this treatment (no selection was
  requested for the user's own echoed question) — only answers changed.
- Always call `self._scroll_to_bottom()` after adding a row.

## Persistent disclaimer

```python
self.disclaimer_label = tk.Label(root, text=DISCLAIMER_TEXT, bg=BG,
                                   fg=DISCLAIMER_COLOR, font=self.small_font,
                                   wraplength=720, justify="left")
self.disclaimer_label.pack(fill="x", padx=28, pady=(0, 8))
```

Packed directly on `root`, between the chat area and the input row — not
inside the scrolling chat transcript. See `references/tone-copy.md` for
why the text itself is short.

## Input pill + send button

See `references/layout-spacing.md` for the full rounded-pill `Canvas` +
embedded-`Entry` code. The button side:

```python
self.entry_var = tk.StringVar()
self.entry = tk.Entry(self.entry_canvas, textvariable=self.entry_var, bg=ENTRY_BG, fg=USER_COLOR,
                        disabledbackground=ENTRY_BG, disabledforeground=USER_COLOR,
                        insertbackground=USER_COLOR, font=self.ui_font,
                        relief="flat", borderwidth=0, highlightthickness=0)
self.entry.bind("<Return>", self._on_submit)
self.entry_var.trace_add("write", self._on_entry_change)

self.send_canvas = tk.Canvas(input_row, width=SEND_BUTTON_SIZE, height=SEND_BUTTON_SIZE,
                               bg=BG, highlightthickness=0, borderwidth=0, cursor="hand2")
circle_image = _circle_image(SEND_BUTTON_SIZE, ACCENT)
self.send_canvas.circle_image = circle_image  # keep a reference alive
self.send_canvas.create_image(0, 0, anchor="nw", image=circle_image)
self.send_canvas.create_text(SEND_BUTTON_SIZE / 2, SEND_BUTTON_SIZE / 2 - 1, text="↑", fill=ENTRY_BG, font=self.bold_font)
self.send_canvas.bind("<Button-1>", self._on_submit)

def _on_entry_change(self, *_args):
    has_text = bool(self.entry_var.get().strip())
    if has_text and not self._send_visible:
        self.send_canvas.pack(side="right", padx=(10, 0))
        self._send_visible = True
    elif not has_text and self._send_visible:
        self.send_canvas.pack_forget()
        self._send_visible = False
```

- **There is no "Ask" button anymore.** This was a deliberate removal —
  the send control is a circular `Canvas` button (black circle, `"↑"`
  glyph) that's `pack_forget()`-hidden by default and only `pack()`-ed in
  once the entry has non-whitespace text, via a `StringVar.trace_add`.
  Don't reintroduce a permanently-visible text button; if a new always-
  visible action is needed, it's a different control, not a replacement
  for this one.
- **Readiness is tracked with a plain `self._ready` flag, not widget
  `state`.** A `Canvas` has no built-in `state="disabled"` the way
  `tk.Button`/`tk.Entry` do, so `_on_submit` checks `self._ready` first
  and returns early if the model isn't loaded or an answer is still
  pending — this is the actual gate now, not a disabled-button visual.
  `self.entry` still gets `state="disabled"` too (keeps it from accepting
  keystrokes while "thinking"), and clearing it after submit naturally
  hides the send button again via the same trace.
- `<Return>` on the entry and `<Button-1>` on the send canvas both call
  `_on_submit` — keep both wired to any future submit-path change, don't
  let them diverge.
- No placeholder text inside the entry field — not implemented, Tkinter's
  `Entry` has no native placeholder support, and it wasn't asked for.

## Adding a genuinely new screen/dialog

There's currently one window. If a second window (e.g. a settings dialog)
is needed:

- Use `tk.Toplevel(root)`, not a second `tk.Tk()`.
- Set the same `BG`, reuse `self.ui_font`/etc. from the parent `App`
  instance rather than recreating `tkfont.Font` objects.
- Set the same icon: `if ICON_PATH.exists(): toplevel.iconbitmap(str(ICON_PATH))`
  guarded by the same `try/except tk.TclError`.
- If it should also get the recolored title bar, call
  `_set_native_title_bar_color(toplevel, BG, USER_COLOR)` on it too — the
  function takes any `Tk`/`Toplevel`, not just the main window.
- Keep it modal only if it truly blocks the main flow
  (`toplevel.transient(root); toplevel.grab_set()`).
