import base64;
import threading;
import urllib.request;
import tkinter as tk;

_LANG_TO_FLAG = {
    'en': 'us',
    'ru': 'ru',
    'de': 'de',
    'fr': 'fr',
    'es': 'es',
    'it': 'it',
    'pt': 'pt',
    'nl': 'nl',
    'pl': 'pl',
    'tr': 'tr',
    'uk': 'ua',
    'zh': 'cn',
    'ja': 'jp',
    'ko': 'kr',
};

def _flag_url(lang: str) -> str | None:
    code = _LANG_TO_FLAG.get(lang.lower());
    if not code:
        return None;
    return f'https://flagcdn.com/w40/{code}.png';

def load_flag_async(root: tk.Tk, lang: str, on_done):
    url = _flag_url(lang);
    if not url:
        root.after(0, lambda: on_done(None));
        return;

    def make_img_on_ui_thread(png_bytes: bytes):
        try:
            b64 = base64.b64encode(png_bytes).decode('ascii');
            img = tk.PhotoImage(data=b64);
            on_done(img);
        except Exception:
            on_done(None);

    def worker():
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'hel-key-logger'});
            with urllib.request.urlopen(req, timeout=2.5) as resp:
                data = resp.read();
            root.after(0, lambda: make_img_on_ui_thread(data));
        except Exception:
            root.after(0, lambda: on_done(None));

    threading.Thread(target=worker, daemon=True).start();