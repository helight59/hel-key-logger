import json;
import os;

class I18n:
    def __init__(self, tag: str, data: dict, fallback_data: dict):
        self.tag = tag;
        self._data = data or {};
        self._fallback = fallback_data or {};

    def t(self, key: str) -> str:
        if key in self._data:
            return self._data[key];
        if key in self._fallback:
            return self._fallback[key];
        return key;

def _read_json(path: str) -> dict:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f);
    except Exception:
        return {};

def load_i18n(base_dir: str, fallback: str = 'en'):
    i18n_dir = os.path.join(base_dir, 'i18n');
    fallback_path = os.path.join(i18n_dir, f'{fallback}.json');
    fallback_data = _read_json(fallback_path);

    locales = {};
    try:
        for fn in os.listdir(i18n_dir):
            if not fn.endswith('.json'):
                continue;
            tag = fn[:-5].lower();
            locales[tag] = os.path.join(i18n_dir, fn);
    except Exception:
        pass

    tag = fallback;
    data = fallback_data;

    return I18n(tag, data, fallback_data), locales;

def load_locale(base_dir: str, tag: str, fallback: str = 'en'):
    i18n_dir = os.path.join(base_dir, 'i18n');
    fallback_data = _read_json(os.path.join(i18n_dir, f'{fallback}.json'));

    norm = (tag or fallback).lower();
    data = _read_json(os.path.join(i18n_dir, f'{norm}.json'));
    if not data:
        norm = fallback;
        data = fallback_data;

    return I18n(norm, data, fallback_data);