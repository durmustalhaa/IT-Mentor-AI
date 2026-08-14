# Interaction & threading pattern

Tkinter's `mainloop()` runs on one thread. Model loading and inference in
`mentor_core` are slow (seconds), so both run off the main thread - this
file is the pattern for doing that safely, and it's the single most
important rule in this skill: **breaking it freezes the whole window.**
Unchanged by the cream/black redesign - this is architecture, not visual
design.

## The queue

```python
_ui_queue: "queue.Queue" = queue.Queue()

def _poll_queue(root):
    try:
        while True:
            action, payload = _ui_queue.get_nowait()
            action(payload)
    except queue.Empty:
        pass
    root.after(50, _poll_queue, root)
```

- A single module-level `Queue` carries `(callback, payload)` pairs from
  background threads to the main thread.
- `_poll_queue` runs on the main thread via `root.after(50, ...)` -
  re-scheduling itself every 50ms, draining whatever's queued.
- Background threads **never** call a widget method directly. They call
  `_ui_queue.put((self._some_ui_method, data))` and the main thread invokes
  it on the next poll.

## Model load flow

```python
threading.Thread(target=self._load_model, daemon=True).start()

def _load_model(self):
    def progress(message: str):
        _ui_queue.put((self._set_status, message))
    mentor_core.load(on_progress=progress)
    _ui_queue.put((self._on_ready, None))
```

- Started once, in `__init__`, `daemon=True` so it doesn't block process
  exit.
- Progress callbacks during load post status updates through the queue
  (e.g. "loading...", "loading tokenizer...", "loading base model...",
  "model ready." - see `mentor_core.py`'s `on_progress` calls).
- Completion posts `_on_ready`, which sets `self._ready = True` and
  re-enables the entry field. (It no longer shows the disclaimer at this
  point - the disclaimer is now a persistent label set up in `__init__`,
  not something injected on ready - see `references/components.md`.)

## Answer flow (per-question)

```python
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
    except Exception as exc:
        answer = f"Something went wrong: {exc}"
    _ui_queue.put((self._show_answer, answer))

def _show_answer(self, answer: str):
    self._add_answer(answer)
    self.status_label.configure(text="ready", fg=SUCCESS_COLOR)
    self.entry.configure(state="normal")
    self.entry.focus_set()
    self._ready = True
```

Note: `_on_submit` itself runs on the **main thread** (it's a Tk event
callback, bound to both the entry's `<Return>` and the send button's
`<Button-1>` - see `references/components.md`), so it's fine for it to
touch widgets directly - disabling input, echoing the question via
`_add_question`, and starting the background thread all happen
synchronously before the slow work begins. Only `_answer` (which does the
actual slow model call) runs off-thread, and it talks back exclusively
through the queue.

`self._ready` (a plain flag, not a widget `state`) is what actually gates
double-submission now - the send button is a `Canvas`, which has no
built-in disabled state the way `tk.Button` does, so `_on_submit` checks
`self._ready` explicitly at the top instead of relying on a disabled
button being unclickable.

## Rules for any new async action

1. **Kick-off happens on the main thread** (inside a button command / event
   binding) - disable whatever controls should be locked during the work,
   echo any immediate feedback, *then* start the thread.
2. **The thread body does the slow work only** - no direct widget access.
   Wrap risky calls in `try/except Exception` and turn failures into a
   user-facing string, matching the `_answer` pattern, rather than letting
   an exception die silently in a daemon thread.
3. **Every result goes through `_ui_queue.put((callback, payload))`** - never
   `self.some_widget.configure(...)` from inside the thread function. This
   includes `_add_question`/`_add_answer` - they create/pack new widgets,
   which is exactly the kind of direct Tk manipulation that must stay on
   the main thread; only call them from a queued callback or from a
   main-thread event handler like `_on_submit`.
4. **The completion callback re-enables what kick-off disabled** and resets
   status back to a ready/neutral state - symmetric with `_show_answer`,
   including setting `self._ready = True` again.
5. **Threads are `daemon=True`** so a background task never prevents the app
   from closing.
6. Don't introduce a second polling loop - if a new async source is added,
   feed it through the existing `_ui_queue` rather than creating another
   `Queue` + `after()` pair.
