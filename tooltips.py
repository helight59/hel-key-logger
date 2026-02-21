import tkinter as tk;

class Tooltip:
    def __init__(self, root: tk.Tk):
        self.root = root;
        self._tw = None;
        self._label = None;
        self._text = '';
        self._after_id = None;

    def hide(self):
        if self._after_id is not None:
            try:
                self.root.after_cancel(self._after_id);
            except Exception:
                pass
            self._after_id = None;

        if self._tw is not None:
            try:
                self._tw.destroy();
            except Exception:
                pass
            self._tw = None;
            self._label = None;
            self._text = '';

    def show(self, text: str, x_root: int, y_root: int):
        if not text:
            self.hide();
            return;

        if self._tw is None:
            tw = tk.Toplevel(self.root);
            tw.wm_overrideredirect(True);
            tw.attributes('-topmost', True);
            lbl = tk.Label(tw, text=text, justify='left', relief='solid', borderwidth=1, padx=8, pady=6);
            lbl.pack();
            self._tw = tw;
            self._label = lbl;
            self._text = text;
        else:
            if self._text != text:
                self._label.configure(text=text);
                self._text = text;

        self._tw.wm_geometry(f'+{x_root + 12}+{y_root + 16}');

    def show_delayed(self, text: str, x_root: int, y_root: int, delay_ms: int = 120):
        if self._after_id is not None:
            try:
                self.root.after_cancel(self._after_id);
            except Exception:
                pass
            self._after_id = None;

        self._after_id = self.root.after(delay_ms, lambda: self.show(text, x_root, y_root));