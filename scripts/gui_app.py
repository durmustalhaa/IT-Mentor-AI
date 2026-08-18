"""IT Mentor AI masaüstü penceresi. Aynı mentor_core.py mantığını
(test_model.py'nin de kullandığı) basit bir Tkinter arayüzünden çağırır.

Model yüklemesi ve her cevap üretimi ayrı bir thread'de çalışır - ana
Tkinter thread'i (pencere) donmasın diye. pythonw.exe ile çalıştırılırsa
hiç konsol penceresi açılmaz (bkz. create_shortcut.ps1).

Sohbet alanı tek bir Text widget'ı değil, kaydırılabilir bir Canvas +
Frame ve her mesaj için ayrı bir widget - gerçek, içeriğe sarılan bir
"balon" görünümü Text widget'ının etiket arka planlarıyla mümkün değil
(denendi: arka plan justify/margin'den bağımsız her zaman tüm satır
genişliğini kaplıyor). Yuvarlak köşeler (balon, input kutusu, gönder
butonu, scrollbar) PIL ile yüksek çözünürlükte çizilip küçültülerek
(supersampling) anti-aliased PhotoImage olarak Canvas'a basılıyor -
Canvas'ın kendi create_polygon/create_oval'ı anti-alias yapmıyor,
kenarlar tırtıklı çıkıyordu (denendi, gözle görülür şekilde kötüydü)."""

import ctypes
import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont

from PIL import Image, ImageDraw, ImageTk

import mentor_core

WINDOW_TITLE = "IT Mentor AI"
ICON_PATH = Path(__file__).resolve().parent.parent / "assets" / "app_icon.ico"

# Minimalist cream/black palette - two base tones (BG, plus a darker
# bubble tint for the user's own messages) and two sparing semantic
# accents (DISCLAIMER_COLOR, SUCCESS_COLOR). No blue/bright accent, and
# no pure white anywhere - the black button IS the accent, ENTRY_BG is
# deliberately the same as BG (see references/palette.md in the
# ui-ux-pro-max skill - an earlier lighter fill read as "a white box").
BG = "#E8DFC5"
BUBBLE_BG = "#D6C8A3"
ENTRY_BG = "#E8DFC5"
OUTLINE_COLOR = "#C4B48C"
USER_COLOR = "#1B1916"
ANSWER_COLOR = "#2B2823"
STATUS_COLOR = "#8C8478"
ACCENT = "#1B1916"
ACCENT_PRESSED = "#3A342C"
DISCLAIMER_COLOR = "#9C7A3C"
SUCCESS_COLOR = "#5B6B4F"

DISCLAIMER_TEXT = (
    "Personal project, not an official resource - answers may be "
    "inaccurate. Verify before critical actions."
)

BUBBLE_RADIUS = 16
INPUT_HEIGHT = 54
SEND_BUTTON_SIZE = 44
SCROLLBAR_WIDTH = 6
SCROLLBAR_MIN_THUMB = 28
MOUSEWHEEL_PIXELS_PER_NOTCH = 60

_SUPERSAMPLE = 4

_ui_queue: "queue.Queue" = queue.Queue()


def _poll_queue(root):
    try:
        while True:
            action, payload = _ui_queue.get_nowait()
            action(payload)
    except queue.Empty:
        pass
    root.after(50, _poll_queue, root)


def _rounded_rect_image(width, height, radius, fill, outline=None, outline_width=0):
    """Anti-aliased yuvarlak dikdörtgen: _SUPERSAMPLE kat büyük çizilip
    LANCZOS ile küçültülüyor - Canvas.create_polygon'un tırtıklı
    kenarlarının çözümü."""
    width, height = max(1, round(width)), max(1, round(height))
    ss = _SUPERSAMPLE
    img = Image.new("RGBA", (width * ss, height * ss), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    ow = outline_width * ss
    inset = ow / 2
    draw.rounded_rectangle(
        [inset, inset, width * ss - 1 - inset, height * ss - 1 - inset],
        radius=radius * ss, fill=fill, outline=outline,
        width=round(ow) if ow else 0
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


def _set_native_title_bar_color(root, bg_hex, text_hex):
    """Windows 11'de pencere başlık çubuğunu palet rengine boyar. Eski
    Windows sürümlerinde DWM bu özelliği desteklemiyor - sessizce
    hiçbir şey yapmadan geçer, hata fırlatmaz."""
    if sys.platform != "win32":
        return

    try:
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())

        def to_colorref(hex_color):
            r = int(hex_color[1:3], 16)
            g = int(hex_color[3:5], 16)
            b = int(hex_color[5:7], 16)
            return r | (g << 8) | (b << 16)

        DWMWA_CAPTION_COLOR = 35
        DWMWA_TEXT_COLOR = 36
        caption = ctypes.c_int(to_colorref(bg_hex))
        text = ctypes.c_int(to_colorref(text_hex))
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_CAPTION_COLOR, ctypes.byref(caption), ctypes.sizeof(caption)
        )
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_TEXT_COLOR, ctypes.byref(text), ctypes.sizeof(text)
        )
    except Exception:
        pass


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self._ready = False
        self._entry_window_id = None
        self._send_visible = False
        self._scroll_first = 0.0
        self._scroll_last = 1.0

        root.title(WINDOW_TITLE)

        if ICON_PATH.exists():
            try:
                root.iconbitmap(str(ICON_PATH))
            except tk.TclError:
                pass

        root.geometry("780x660")
        root.minsize(480, 420)
        root.configure(bg=BG)
        root.after(50, lambda: _set_native_title_bar_color(root, BG, USER_COLOR))

        self.mono_font = tkfont.Font(family="Consolas", size=11)
        self.ui_font = tkfont.Font(family="Calibri", size=12)
        self.bold_font = tkfont.Font(family="Calibri", size=12, weight="bold")
        self.title_font = tkfont.Font(family="Calibri", size=18, weight="bold")
        self.small_font = tkfont.Font(family="Calibri", size=10)

        header = tk.Frame(root, bg=BG)
        header.pack(fill="x", padx=28, pady=(20, 8))
        tk.Label(
            header, text="IT Mentor AI", bg=BG, fg=USER_COLOR, font=self.title_font
        ).pack(side="left")
        self.status_label = tk.Label(
            header, text="loading...", bg=BG, fg=STATUS_COLOR, font=self.ui_font
        )
        self.status_label.pack(side="right")

        # Scrollable chat area: Canvas + inner Frame, one widget per
        # message (see module docstring for why not a plain Text
        # widget). The scrollbar is a thin custom-drawn indicator, not
        # a classic tk.Scrollbar - the default widget looked chunky
        # and out of place against the rest of the design; see
        # _redraw_scrollbar/_on_scroll_update. yscrollincrement=1 plus
        # a fixed pixel-per-notch mousewheel handler makes scrolling
        # move smoothly instead of jumping in Tk's default large
        # "unit" steps.
        chat_outer = tk.Frame(root, bg=BG)
        chat_outer.pack(fill="both", expand=True, padx=(28, 20), pady=8)

        self.scrollbar_canvas = tk.Canvas(
            chat_outer, width=SCROLLBAR_WIDTH, bg=BG, highlightthickness=0, borderwidth=0
        )
        self.scrollbar_canvas.pack(side="right", fill="y", padx=(6, 0))
        self.scrollbar_canvas.bind("<Configure>", lambda _e: self._redraw_scrollbar())
        self.scrollbar_canvas.bind("<Button-1>", self._on_scrollbar_drag)
        self.scrollbar_canvas.bind("<B1-Motion>", self._on_scrollbar_drag)

        self.chat_canvas = tk.Canvas(chat_outer, bg=BG, highlightthickness=0, borderwidth=0)
        self.chat_canvas.configure(yscrollcommand=self._on_scroll_update, yscrollincrement=1)
        self.chat_canvas.pack(side="left", fill="both", expand=True)

        self.chat_frame = tk.Frame(self.chat_canvas, bg=BG)
        self.chat_window = self.chat_canvas.create_window((0, 0), window=self.chat_frame, anchor="nw")

        self.chat_frame.bind(
            "<Configure>",
            lambda _e: self.chat_canvas.configure(scrollregion=self.chat_canvas.bbox("all"))
        )
        self.chat_canvas.bind(
            "<Configure>",
            lambda e: self.chat_canvas.itemconfig(self.chat_window, width=e.width)
        )
        # Windows/macOS deliver wheel scroll as <MouseWheel> with a
        # signed e.delta (multiples of 120 per notch). X11 (Linux)
        # never sends <MouseWheel> at all - wheel scroll arrives as
        # <Button-4>/<Button-5> press events instead, one per notch,
        # no delta - binding only <MouseWheel> left the wheel doing
        # nothing on Linux (confirmed live: GUI opened and worked on
        # Rocky Linux/GNOME, but scrolling the chat area had no effect
        # at all). Both are bound so either platform's event reaches
        # the same scroll handler.
        self.chat_canvas.bind_all(
            "<MouseWheel>",
            lambda e: self.chat_canvas.yview_scroll(
                int(-1 * (e.delta / 120) * MOUSEWHEEL_PIXELS_PER_NOTCH), "units"
            )
        )
        self.chat_canvas.bind_all(
            "<Button-4>",
            lambda e: self.chat_canvas.yview_scroll(-MOUSEWHEEL_PIXELS_PER_NOTCH, "units")
        )
        self.chat_canvas.bind_all(
            "<Button-5>",
            lambda e: self.chat_canvas.yview_scroll(MOUSEWHEEL_PIXELS_PER_NOTCH, "units")
        )

        # Small, persistent disclaimer pinned above the input box -
        # always visible, doesn't scroll away or eat chat space.
        self.disclaimer_label = tk.Label(
            root,
            text=DISCLAIMER_TEXT,
            bg=BG,
            fg=DISCLAIMER_COLOR,
            font=self.small_font,
            wraplength=720,
            justify="left"
        )
        self.disclaimer_label.pack(fill="x", padx=28, pady=(0, 8))

        input_row = tk.Frame(root, bg=BG)
        input_row.pack(fill="x", padx=28, pady=(0, 26))

        self.entry_canvas = tk.Canvas(
            input_row, height=INPUT_HEIGHT, bg=BG, highlightthickness=0, borderwidth=0
        )
        self.entry_canvas.pack(side="left", fill="x", expand=True)

        self.entry_var = tk.StringVar()
        self.entry = tk.Entry(
            self.entry_canvas,
            textvariable=self.entry_var,
            bg=ENTRY_BG,
            fg=USER_COLOR,
            # tk.Entry uses disabledbackground/-foreground (NOT bg/fg)
            # while state="disabled" - without these it fell back to
            # Windows' default light-gray/white disabled-field look,
            # which is exactly the "white box" the user flagged.
            disabledbackground=ENTRY_BG,
            disabledforeground=USER_COLOR,
            insertbackground=USER_COLOR,
            font=self.ui_font,
            relief="flat",
            borderwidth=0,
            highlightthickness=0
        )
        self.entry.bind("<Return>", self._on_submit)
        self.entry.configure(state="disabled")
        self.entry_var.trace_add("write", self._on_entry_change)

        self.entry_canvas.bind("<Configure>", self._redraw_entry_background)

        # Circular send button - not packed until there's text to send
        # (see _on_entry_change). A round black button with an arrow
        # glyph, matching the "icon appears while typing" request.
        self.send_canvas = tk.Canvas(
            input_row, width=SEND_BUTTON_SIZE, height=SEND_BUTTON_SIZE,
            bg=BG, highlightthickness=0, borderwidth=0, cursor="hand2"
        )
        circle_image = _circle_image(SEND_BUTTON_SIZE, ACCENT)
        self.send_canvas.circle_image = circle_image  # keep a reference alive
        self.send_canvas.create_image(0, 0, anchor="nw", image=circle_image)
        self.send_canvas.create_text(
            SEND_BUTTON_SIZE / 2, SEND_BUTTON_SIZE / 2 - 1,
            text="↑", fill=ENTRY_BG, font=self.bold_font
        )
        self.send_canvas.bind("<Button-1>", self._on_submit)

        threading.Thread(target=self._load_model, daemon=True).start()

    def _redraw_entry_background(self, event=None):
        w = self.entry_canvas.winfo_width()
        h = self.entry_canvas.winfo_height()
        self.entry_canvas.delete("bg")

        if w <= 4 or h <= 4:
            return

        bg_image = _rounded_rect_image(
            w, h, radius=h / 2, fill=ENTRY_BG, outline=OUTLINE_COLOR, outline_width=2
        )
        self.entry_canvas.bg_image = bg_image  # keep a reference alive
        self.entry_canvas.create_image(0, 0, anchor="nw", image=bg_image, tags="bg")
        self.entry_canvas.tag_lower("bg")

        entry_width = max(10, int(w - 40))
        if self._entry_window_id is None:
            self._entry_window_id = self.entry_canvas.create_window(
                20, h / 2, window=self.entry, anchor="w", width=entry_width
            )
        else:
            self.entry_canvas.coords(self._entry_window_id, 20, h / 2)
            self.entry_canvas.itemconfig(self._entry_window_id, width=entry_width)

    def _on_scroll_update(self, first, last):
        self._scroll_first, self._scroll_last = float(first), float(last)
        self._redraw_scrollbar()

    def _redraw_scrollbar(self):
        self.scrollbar_canvas.delete("thumb")
        h = self.scrollbar_canvas.winfo_height()
        w = self.scrollbar_canvas.winfo_width()

        if h <= 1 or w <= 1 or self._scroll_last - self._scroll_first >= 0.999:
            return

        y1 = self._scroll_first * h
        y2 = self._scroll_last * h

        if y2 - y1 < SCROLLBAR_MIN_THUMB:
            mid = (y1 + y2) / 2
            y1 = max(0, mid - SCROLLBAR_MIN_THUMB / 2)
            y2 = min(h, y1 + SCROLLBAR_MIN_THUMB)

        thumb_image = _rounded_rect_image(w, y2 - y1, radius=w / 2, fill=OUTLINE_COLOR)
        self.scrollbar_canvas.thumb_image = thumb_image  # keep a reference alive
        self.scrollbar_canvas.create_image(0, y1, anchor="nw", image=thumb_image, tags="thumb")

    def _on_scrollbar_drag(self, event):
        h = self.scrollbar_canvas.winfo_height()

        if h <= 1:
            return

        fraction = max(0.0, min(1.0, event.y / h))
        self.chat_canvas.yview_moveto(fraction)

    def _on_entry_change(self, *_args):
        has_text = bool(self.entry_var.get().strip())

        if has_text and not self._send_visible:
            self.send_canvas.pack(side="right", padx=(10, 0))
            self._send_visible = True
        elif not has_text and self._send_visible:
            self.send_canvas.pack_forget()
            self._send_visible = False

    def _load_model(self):
        def progress(message: str):
            _ui_queue.put((self._set_status, message))

        mentor_core.load(on_progress=progress)
        _ui_queue.put((self._on_ready, None))

    def _set_status(self, message: str):
        self.status_label.configure(text=message, fg=STATUS_COLOR)

    def _on_ready(self, _):
        self.status_label.configure(text="ready", fg=SUCCESS_COLOR)
        self.entry.configure(state="normal")
        self.entry.focus_set()
        self._ready = True

        # dataset.jsonl bir `git pull` ile değişip build_index.py yeniden
        # çalıştırılmamışsa (bkz. mentor_core.dataset_hash) - eskiden bu
        # sessizce eski veriyle çalışmaya devam ediyordu, hiç uyarı yoktu.
        if mentor_core.index_is_stale:
            self._add_answer(
                "⚠ The search index doesn't match the current "
                "dataset.jsonl (it changed since the index was last "
                "built). Answers may be missing recent updates - run "
                "'python scripts/build_index.py' to refresh it."
            )

    def _add_question(self, text: str):
        row = tk.Frame(self.chat_frame, bg=BG)
        row.pack(fill="x", pady=(10, 2))

        measurer = tk.Label(row, text=text, font=self.ui_font, wraplength=420, justify="left")
        measurer.update_idletasks()
        text_w = measurer.winfo_reqwidth()
        text_h = measurer.winfo_reqheight()
        measurer.destroy()

        pad_x, pad_y = 18, 12
        canvas_w = text_w + pad_x * 2
        canvas_h = text_h + pad_y * 2

        bubble = tk.Canvas(
            row, width=canvas_w, height=canvas_h, bg=BG, highlightthickness=0, borderwidth=0
        )
        bubble.pack(side="right")
        bg_image = _rounded_rect_image(canvas_w, canvas_h, BUBBLE_RADIUS, BUBBLE_BG)
        bubble.bg_image = bg_image  # keep a reference alive
        bubble.create_image(0, 0, anchor="nw", image=bg_image)

        # create_text yerine gerçek bir Text widget - Canvas metin
        # öğeleri (create_text) Tkinter'da Label'dan bile daha kısıtlı,
        # HİÇ seçilemiyor/kopyalanamıyor. _add_answer'ın Label yerine
        # Text kullanma sebebiyle (yukarıdaki yorum) aynı ders burada da
        # geçerliydi ama hiç uygulanmamıştı - kullanıcı canlı testte
        # kendi mesajlarını kopyalayamadığını bildirdi. state="disabled"
        # sadece düzenlemeyi engelliyor, seçim/Ctrl+C çalışmaya devam
        # ediyor.
        question_text = tk.Text(
            bubble,
            bg=BUBBLE_BG,
            fg=USER_COLOR,
            font=self.ui_font,
            wrap="word",
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            padx=0,
            pady=0,
            insertbackground=USER_COLOR,
            selectbackground=OUTLINE_COLOR,
            selectforeground=USER_COLOR,
            cursor="xterm"
        )
        question_text.insert("1.0", text)
        question_text.configure(state="disabled")
        bubble.create_window(
            canvas_w / 2, canvas_h / 2, anchor="center", window=question_text,
            width=text_w, height=text_h
        )

        self._scroll_to_bottom()

    def _add_answer(self, text: str):
        row = tk.Frame(self.chat_frame, bg=BG)
        row.pack(fill="x", pady=(2, 18))

        # A Text widget, not a Label - Labels can't be text-selected at
        # all in Tkinter. state="disabled" blocks EDITING only; click-drag
        # selection and Ctrl+C copying still work normally on a disabled
        # Text widget, which is exactly "read-only but selectable."
        answer_text = tk.Text(
            row,
            bg=BG,
            fg=ANSWER_COLOR,
            font=self.mono_font,
            wrap="word",
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            padx=0,
            pady=0,
            insertbackground=ANSWER_COLOR,
            selectbackground=OUTLINE_COLOR,
            selectforeground=USER_COLOR,
            cursor="xterm",
            height=1
        )
        answer_text.pack(side="left", fill="x", expand=True)
        answer_text.insert("1.0", text)

        # Text has no auto-height-to-content like Label's wraplength -
        # measure the wrapped line count after layout and resize the
        # widget to match, so it doesn't leave a scrollbar/dead space.
        answer_text.update_idletasks()
        line_count = max(1, int(answer_text.count("1.0", "end", "displaylines")[0]))
        answer_text.configure(height=line_count, state="disabled")

        self._scroll_to_bottom()

    def _scroll_to_bottom(self):
        self.chat_frame.update_idletasks()
        self.chat_canvas.configure(scrollregion=self.chat_canvas.bbox("all"))
        self.chat_canvas.yview_moveto(1.0)

    def _on_submit(self, _event=None):
        if not self._ready:
            return

        question = self.entry.get().strip()

        if not question:
            return

        self._ready = False
        self.entry.delete(0, "end")
        self.entry.configure(state="disabled")
        self.status_label.configure(text="thinking...", fg=STATUS_COLOR)

        self._add_question(question)

        threading.Thread(target=self._answer, args=(question,), daemon=True).start()

    def _answer(self, question: str):
        try:
            answer = mentor_core.answer_question(question)
        except Exception as exc:  # noqa: BLE001 - arayüzde göstermek için genel yakalama
            answer = f"Something went wrong: {exc}"

        _ui_queue.put((self._show_answer, answer))

    def _show_answer(self, answer: str):
        self._add_answer(answer)
        self.status_label.configure(text="ready", fg=SUCCESS_COLOR)
        self.entry.configure(state="normal")
        self.entry.focus_set()
        self._ready = True


def main():
    root = tk.Tk()
    App(root)
    root.after(50, _poll_queue, root)
    root.mainloop()


if __name__ == "__main__":
    main()
