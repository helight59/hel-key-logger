import ctypes;
import os;
import time;
import sys;
import tkinter as tk;
from tkinter import ttk;
from collections import deque;
import zlib;

from device_info import classify_transport, get_device_info, get_device_name, get_friendly_device_name;
from device_parse import parse_device_path;
from flags import load_flag_async;
from i18n import load_i18n, load_locale;
from raw_input import RawHidEvent, RawKeyboardEvent;
from raw_listener import RawInputListener;
from key_names import flags_info, msg_info, scancode_key_name, vk_name;
from tooltips import Tooltip;

MAX_LOG_CHARS = 1_400_000;

_VALUE_PALETTE = [
    '#f1f5f9', '#f8fafc', '#f3f4f6', '#f5f5f5', '#fafafa',
    '#f0fdf4', '#ecfdf5', '#f0fdfa', '#f7fee7', '#f8faf0',
    '#fdf2f8', '#fff1f2', '#fef2f2', '#fff7f7', '#fce7f3',
    '#f5f3ff', '#faf5ff', '#f3e8ff', '#fdf4ff', '#f6f4ff',
];

def now():
    return time.strftime('%H:%M:%S') + f'.{int((time.time() % 1) * 1000):03d}';

def _crc32(s: str) -> int:
    return zlib.crc32(s.encode('utf-8')) & 0xffffffff;

class App:
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.abspath(__file__));
        self.i18n, self.available_locales = load_i18n(self.base_dir, fallback='en');
        self.i18n_en = load_locale(self.base_dir, 'en', fallback='en');

        self.root = tk.Tk();
        self.root.title(self.i18n.t('app_title'));
        self.root.geometry('1200x680');

        self._flag_img = None;

        self._set_window_icon();
        self._devices = {};
        self._device_keys_sorted = [];
        self._selected_device_key = None;
        self._dev_pretty_to_key = {};

        self._cache = {};

        self._pending_events = deque();
        self._drain_scheduled = False;

        self.tooltip = Tooltip(self.root);
        self._tt_last = None;

        self._alt_idx = 0;

        self._entries = [];
        self._entries_chars = 0;

        self._build_topbar();
        self._build_log();
        self._build_footer();

        self.listener = RawInputListener(self._on_event_from_listener);
        self.listener.start();

        self._write_intro();
        self.log_block(model={'type': 'info', 'key': 'registered_devices'}, kind='info');

        self.root.protocol('WM_DELETE_WINDOW', self.on_close);

        self._set_flag_for_lang(self.i18n.tag);
        self._rebuild_device_dropdown();

    def resource_path(self, rel_path: str) -> str:
        base = getattr(sys, '_MEIPASS', os.path.abspath(os.path.dirname(__file__)));
        return os.path.join(base, rel_path);

    def _set_window_icon(self):
        try:
            ico_path = self.resource_path(os.path.join('assets', 'window.ico'));
            self.root.iconbitmap(ico_path);
        except Exception:
            pass


    # ---------- UI ----------

    def _build_topbar(self):
        bar = ttk.Frame(self.root);
        bar.pack(fill='x', padx=8, pady=6);

        self.lang_label = ttk.Label(bar, text='Language');
        self.lang_label.pack(side='left');

        self.lang_var = tk.StringVar(value=self.i18n.tag);
        langs = sorted(self.available_locales.keys());
        self.lang_combo = ttk.Combobox(bar, textvariable=self.lang_var, values=langs, state='readonly', width=8);
        self.lang_combo.pack(side='left', padx=(8, 12));
        self.lang_combo.bind('<<ComboboxSelected>>', self._on_lang_changed);

        self.flag_label = ttk.Label(bar);
        self.flag_label.pack(side='left', padx=(0, 16));

        self.dev_label = ttk.Label(bar, text='Device');
        self.dev_label.pack(side='left');

        self.dev_var = tk.StringVar(value='*');
        self.dev_combo = ttk.Combobox(bar, textvariable=self.dev_var, values=['*'], state='readonly', width=52);
        self.dev_combo.pack(side='left', padx=(8, 12));
        self.dev_combo.bind('<<ComboboxSelected>>', self._on_device_changed);

        self.clear_btn = ttk.Button(bar, text='Clear', command=self._clear_log);
        self.clear_btn.pack(side='right', padx=(8, 0));

    def _build_log(self):
        frame = ttk.Frame(self.root);
        frame.pack(fill='both', expand=True, padx=8, pady=(0, 0));

        self.text = tk.Text(frame, wrap='none', undo=True, state='disabled');
        self.text.pack(side='left', fill='both', expand=True);

        self.text.configure(selectbackground='#214283', selectforeground='#dadce3');

        yscroll = ttk.Scrollbar(frame, orient='vertical', command=self.text.yview);
        yscroll.pack(side='right', fill='y');
        self.text.configure(yscrollcommand=yscroll.set);

        self._install_copy_bindings();
        self._install_context_menu();
        self._install_tooltips();
        self._install_tags();

    def _build_footer(self):
        foot = ttk.Frame(self.root);
        foot.pack(fill='x', padx=8, pady=6);

        self.footer = ttk.Label(foot, text='By Helight');
        self.footer.pack(side='right');

    def _install_tags(self):
        self.text.tag_configure('sep', foreground='#9a9a9a');
        self.text.tag_configure('mono', font=('Consolas', 10));
        self.text.tag_configure('param', font=('Segoe UI', 10, 'bold'));

        self.text.tag_configure('alt0', background='#eef7ee');
        self.text.tag_configure('alt1', background='#eef2ff');
        self.text.tag_configure('alt2', background='#f7f2ee');

        self.text.tag_configure('qmark', font=('Segoe UI', 10, 'bold'), foreground='#3b3b3b');

        for i, bg in enumerate(_VALUE_PALETTE):
            self.text.tag_configure(f'val{i}', background=bg, foreground='#000000');

        try:
            self.text.tag_raise('sel');
        except Exception:
            pass

    def _install_copy_bindings(self):
        self.text.bind('<Button-1>', lambda _e: self.text.focus_set());
        self.text.bind('<Control-c>', lambda _e: (self.text.event_generate('<<Copy>>'), 'break')[1]);
        self.text.bind('<Control-C>', lambda _e: (self.text.event_generate('<<Copy>>'), 'break')[1]);
        self.text.bind('<Control-Insert>', lambda _e: (self.text.event_generate('<<Copy>>'), 'break')[1]);
        self.text.bind('<Key>', lambda _e: 'break');

    def _install_context_menu(self):
        self._menu = tk.Menu(self.root, tearoff=0);
        self._menu.add_command(label='Copy', command=lambda: self.text.event_generate('<<Copy>>'));
        self._menu.add_command(label='Select all', command=self._select_all);

        def popup(e):
            try:
                if not self.text.tag_ranges('sel'):
                    self.text.mark_set('insert', f'@{e.x},{e.y}');
                self._menu.tk_popup(e.x_root, e.y_root);
            finally:
                try:
                    self._menu.grab_release();
                except Exception:
                    pass

        self.text.bind('<Button-3>', popup);

    # ---------- Tooltip fallback logic ----------

    def _tt_text(self, tt_key: str) -> str:
        s = self.i18n.t(tt_key);
        if s and s != tt_key:
            return s;
        s2 = self.i18n_en.t(tt_key);
        if s2 and s2 != tt_key:
            return s2;
        return '';

    def _has_tt(self, tt_key: str) -> bool:
        return self._tt_text(tt_key) != '';

    def _install_tooltips(self):
        self._tooltip_map = {
            'q_vendor_id': ('tt_vendor_id',),
            'q_product_id': ('tt_product_id',),
            'q_interface': ('tt_interface',),
            'q_guid': ('tt_guid',),
            'q_path': ('tt_path',),
            'q_handle': ('tt_handle',),
            'q_transport': ('tt_transport',),
            'q_vkey': ('tt_vkey',),
            'q_scancode': ('tt_scancode',),
            'q_flags': ('tt_flags',),
            'q_msg': ('tt_msg',),
        };

        def on_leave(_e):
            self._tt_last = None;
            self.tooltip.hide();

        def on_motion(e):
            idx = self.text.index(f'@{e.x},{e.y}');
            tags = self.text.tag_names(idx);

            hit = None;
            for t in tags:
                if t in self._tooltip_map:
                    tt_key = self._tooltip_map[t][0];
                    if self._has_tt(tt_key):
                        hit = t;
                    break

            if not hit:
                self._tt_last = None;
                self.tooltip.hide();
                return;

            if self._tt_last == hit:
                return;

            self._tt_last = hit;
            tt_key = self._tooltip_map[hit][0];
            self.tooltip.show_delayed(self._tt_text(tt_key), e.x_root, e.y_root, delay_ms=500);

        self.text.bind('<Leave>', on_leave);
        self.text.bind('<Motion>', on_motion);

    # ---------- Controls ----------

    def _select_all(self):
        self.text.tag_add('sel', '1.0', 'end-1c');
        self.text.focus_set();

    def _clear_log(self):
        self._entries = [];
        self._entries_chars = 0;
        self.text.configure(state='normal');
        self.text.delete('1.0', 'end');
        self.text.configure(state='disabled');

    def _write_intro(self):
        self._append_plain(self.i18n.t('intro_1') + '\n');
        self._append_plain(self.i18n.t('intro_2') + '\n\n');

    def _apply_i18n(self):
        self.root.title(self.i18n.t('app_title'));
        self.lang_label.configure(text='Language' if self.i18n.tag == 'en' else 'Язык');
        self.dev_label.configure(text='Device' if self.i18n.tag == 'en' else 'Устройство');
        self.clear_btn.configure(text='Clear' if self.i18n.tag == 'en' else 'Очистить');

        self._rebuild_devices_names();
        self._rebuild_device_dropdown();

    def _set_flag_for_lang(self, lang: str):
        def on_done(img):
            self._flag_img = img;
            self.flag_label.configure(image=img or '');

        load_flag_async(self.root, lang, on_done);

    def _on_lang_changed(self, _evt):
        tag = (self.lang_var.get() or 'en').lower();
        self.i18n = load_locale(self.base_dir, tag, fallback='en');
        self._apply_i18n();
        self._set_flag_for_lang(self.i18n.tag);
        self._rerender_from_entries();

    def _selected_device_key_from_combo(self) -> str | None:
        pretty = (self.dev_var.get() or '').strip();
        if not pretty:
            return None;
        key = self._dev_pretty_to_key.get(pretty);
        if not key or key == '*':
            return None;
        return key;

    def _on_device_changed(self, _evt):
        self._selected_device_key = self._selected_device_key_from_combo();
        self._rerender_from_entries();

    def _rebuild_device_dropdown(self):
        all_label = '*';
        all_display = 'All devices' if self.i18n.tag == 'en' else 'Все устройства';

        displays = {all_label: all_display};
        for k in self._device_keys_sorted:
            displays[k] = self._devices.get(k, k);

        pretty_values = [f"{all_label} | {all_display}"];
        for k in self._device_keys_sorted:
            pretty_values.append(f"{k} | {displays[k]}");

        cur_key = self._selected_device_key if self._selected_device_key is not None else all_label;
        cur_pretty = f"{cur_key} | {displays.get(cur_key, all_display)}" if cur_key != all_label else f"{all_label} | {all_display}";

        self._dev_pretty_to_key = {};
        for v in pretty_values:
            key_part = v.split('|', 1)[0].strip();
            self._dev_pretty_to_key[v] = key_part;

        self.dev_combo.configure(values=pretty_values);
        self.dev_var.set(cur_pretty);

    # ---------- Device naming (locale-aware) ----------

    def _device_display_name(self, friendly: str, vid: str | None, pid: str | None) -> str:
        if friendly:
            return friendly;

        tpl = self.i18n.t('hid_device_vidpid');
        if tpl == 'hid_device_vidpid':
            tpl = "HID Device ({vid}:{pid})";

        if vid and pid:
            return tpl.format(vid=vid, pid=pid);

        base = self.i18n.t('hid_device');
        return base if base != 'hid_device' else 'HID Device';

    def _rebuild_devices_names(self):
        self._devices = {};
        for _kint, meta in self._cache.items():
            key = meta.get('key') or f"0x{_kint:X}";
            friendly = meta.get('friendly') or '';
            vid = meta.get('vid');
            pid = meta.get('pid');
            shown = self._device_display_name(friendly, vid, pid);
            self._devices[key] = shown;
        self._device_keys_sorted = sorted(self._devices.keys());

    # ---------- Logging core ----------

    def _append_plain(self, s: str):
        self.text.configure(state='normal');
        self.text.insert('end', s);
        self.text.see('end');
        self.text.configure(state='disabled');

    def _push_entry(self, entry: dict):
        t = entry.get('text', '');
        self._entries.append(entry);
        self._entries_chars += len(t);

        while self._entries_chars > MAX_LOG_CHARS and self._entries:
            e0 = self._entries.pop(0);
            self._entries_chars -= len(e0.get('text', ''));

    def _entry_matches_filters(self, entry: dict) -> bool:
        if self._selected_device_key is None:
            return True;
        return entry.get('device_key') == self._selected_device_key;

    def _rerender_from_entries(self):
        self.text.configure(state='normal');
        self.text.delete('1.0', 'end');

        self._alt_idx = 0;
        for e in self._entries:
            if not self._entry_matches_filters(e):
                continue;
            self._render_entry(e);

        self.text.see('end');
        self.text.configure(state='disabled');

    def log_block(self, body: str | None = None, model: dict | None = None, kind: str = 'event', device_name: str | None = None, device_key: str | None = None, device_path: str | None = None):
        entry = {
            'kind': kind,
            'text': body or '',
            'model': model,
            'device_name': device_name or '',
            'device_key': device_key or '',
            'device_path': device_path or '',
        };

        if model is not None:
            entry['text'] = '';

        self._push_entry(entry);

        if not self._entry_matches_filters(entry):
            return;

        self.text.configure(state='normal');
        self._render_entry(entry);
        self.text.see('end');
        self.text.configure(state='disabled');

    def _render_entry(self, entry: dict):
        alt_tag = ('alt0', 'alt1', 'alt2')[self._alt_idx % 3];
        self._alt_idx = (self._alt_idx + 1) % 3;

        sep = '─' * 96;

        if entry.get('model') is not None:
            body = self._render_model(entry['model']);
        else:
            body = entry.get('text', '');

        block_start = self.text.index('end');
        self.text.insert('end', sep + '\n', ('sep', alt_tag));
        self.text.insert('end', body + '\n', (alt_tag, 'mono'));
        self.text.insert('end', sep + '\n\n', ('sep', alt_tag));

        self._tag_last_block_qmarks(block_start);
        self._tag_last_block_formatting(block_start);

        try:
            self.text.tag_raise('sel');
        except Exception:
            pass

    def _tag_last_block_formatting(self, block_start: str):
        end = self.text.index('end-1c');

        line_start = block_start;
        try:
            line_start = self.text.index(f'{line_start} lineend+1c');
        except Exception:
            return;

        while self.text.compare(line_start, '<', end):
            line_end = self.text.index(f'{line_start} lineend');
            raw = self.text.get(line_start, line_end);

            if raw and raw[0] != '─':
                sep_pos = raw.find(':');
                if sep_pos != -1:
                    k_start = line_start;
                    k_end = f'{line_start}+{sep_pos + 1}c';
                    self.text.tag_add('param', k_start, k_end);

                    val_start = k_end;
                    if self.text.get(val_start, f'{val_start}+1c') == ' ':
                        val_start = f'{val_start}+1c';

                    if self.text.compare(val_start, '<', line_end):
                        val = self.text.get(val_start, line_end);
                        p = _crc32(raw[:sep_pos] + '|' + val) % len(_VALUE_PALETTE);
                        self.text.tag_add(f'val{p}', val_start, line_end);

            try:
                line_start = self.text.index(f'{line_end}+1c');
            except Exception:
                break

    def _tag_last_block_qmarks(self, block_start: str):
        end = self.text.index('end-1c');

        pairs = [
            ('q_handle', 'tt_handle'),
            ('q_transport', 'tt_transport'),
            ('q_vendor_id', 'tt_vendor_id'),
            ('q_product_id', 'tt_product_id'),
            ('q_interface', 'tt_interface'),
            ('q_guid', 'tt_guid'),
            ('q_path', 'tt_path'),
            ('q_vkey', 'tt_vkey'),
            ('q_scancode', 'tt_scancode'),
            ('q_flags', 'tt_flags'),
            ('q_msg', 'tt_msg'),
        ];

        if not any(self._has_tt(tt) for _q, tt in pairs):
            return;

        cur = block_start;
        while True:
            qpos = self.text.search('(?)', cur, stopindex=end);
            if not qpos:
                break
            qend = f'{qpos}+3c';
            self.text.tag_add('qmark', qpos, qend);

            line_start = self.text.index(f'{qpos} linestart');
            prefix = self.text.get(line_start, qpos);

            def add(tag, tt_key):
                if self._has_tt(tt_key):
                    self.text.tag_add(tag, qpos, qend);

            if 'VKey' in prefix or self.i18n.t('vkey') in prefix:
                add('q_vkey', 'tt_vkey');
            elif 'Scan' in prefix or 'Скан' in prefix or self.i18n.t('makecode') in prefix:
                add('q_scancode', 'tt_scancode');
            elif 'Flags' in prefix or 'Флаг' in prefix or self.i18n.t('flags') in prefix:
                add('q_flags', 'tt_flags');
            elif 'Message' in prefix or 'Сообщ' in prefix or self.i18n.t('msg') in prefix:
                add('q_msg', 'tt_msg');
            elif self.i18n.t('device_handle') in prefix:
                add('q_handle', 'tt_handle');
            elif self.i18n.t('device_transport') in prefix:
                add('q_transport', 'tt_transport');
            elif self.i18n.t('device_vid') in prefix:
                add('q_vendor_id', 'tt_vendor_id');
            elif self.i18n.t('device_pid') in prefix:
                add('q_product_id', 'tt_product_id');
            elif self.i18n.t('device_mi') in prefix:
                add('q_interface', 'tt_interface');
            elif self.i18n.t('device_guid') in prefix:
                add('q_guid', 'tt_guid');
            elif self.i18n.t('device_path') in prefix:
                add('q_path', 'tt_path');

            cur = qend;

    # ---------- Model rendering (re-renders on locale change) ----------

    def _mk_label(self, label: str, tt_key: str) -> str:
        return f"{label} (?)" if self._has_tt(tt_key) else label;

    def _transport_label(self, transport_key: str) -> str:
        tr_map = {
            'bt': self.i18n.t('transport_bt'),
            'bt_gatt': self.i18n.t('transport_bt_gatt'),
            'usb_or_dongle': self.i18n.t('transport_usb_or_dongle'),
            'unknown': self.i18n.t('transport_unknown'),
        };
        return tr_map.get(transport_key, self.i18n.t('transport_unknown'));

    def _group_title(self, kind: str) -> str:
        if self.i18n.tag == 'ru':
            if kind == 'keycodes':
                return 'Параметры события клавиши';
        if kind == 'keycodes':
            return 'Key event parameters';
        return '';

    def _render_device_details_from_model(self, m: dict) -> str:
        name = self._device_display_name(m.get('friendly', ''), m.get('vid'), m.get('pid'));
        tr = self._transport_label(m.get('transport_key', 'unknown'));

        lines = [];
        lines.append(f"{self.i18n.t('device_name')}: {name}");
        lines.append(f"{self._mk_label(self.i18n.t('device_handle'), 'tt_handle')}: {m.get('handle', '-')}");
        lines.append(f"{self._mk_label(self.i18n.t('device_transport'), 'tt_transport')}: {tr}");
        lines.append(f"{self._mk_label(self.i18n.t('device_vid'), 'tt_vendor_id')}: {m.get('vid') or '-'}");
        lines.append(f"{self._mk_label(self.i18n.t('device_pid'), 'tt_product_id')}: {m.get('pid') or '-'}");
        lines.append(f"{self._mk_label(self.i18n.t('device_mi'), 'tt_interface')}: {m.get('mi') or '-'}");
        lines.append(f"{self._mk_label(self.i18n.t('device_guid'), 'tt_guid')}: {m.get('guid') or '-'}");
        lines.append(f"{self._mk_label(self.i18n.t('device_path'), 'tt_path')}: {m.get('path') or '-'}");

        if (m.get('handle') or '').lower() == '0x0':
            lines.append(f"{self.i18n.t('desc')}: {self.i18n.t('unknown_device_note')}");

        return '\n'.join(lines);

    def _render_model(self, model: dict) -> str:
        t = model.get('type')

        if t == 'info' and model.get('key') == 'registered_devices':
            return f"[{now()}] {self.i18n.t('registered')}: Keyboard, ConsumerControl, SystemControl, Gamepad, Joystick";

        if t in ('kbd', 'hid', 'other'):
            prefix = f"[{model.get('ts')}] [{self._transport_label(model.get('transport_key', 'unknown'))}]";
            dev = self._render_device_details_from_model(model);

            vidpid = model.get('vidpid') or '';
            if t == 'kbd':
                vkey_lbl = self._mk_label(self.i18n.t('vkey'), 'tt_vkey');
                sc_lbl = self._mk_label(self.i18n.t('makecode'), 'tt_scancode');
                fl_lbl = self._mk_label(self.i18n.t('flags'), 'tt_flags');
                msg_lbl = self._mk_label(self.i18n.t('msg'), 'tt_msg');

                msg_n, msg_d = msg_info(int(model.get('message', 0)), self.i18n);
                flags_d = flags_info(int(model.get('flags', 0)), self.i18n);

                return (
                    f"{prefix} {self.i18n.t('keyboard')}{vidpid}\n"
                    f"{dev}\n"
                    f"{self.i18n.t('key_name')}: {model.get('key_human')}\n\n"
                    f"{self._group_title('keycodes')}:\n"
                    f"{vkey_lbl}: {model.get('vkey_hex')} ({model.get('vk_name')})\n"
                    f"{sc_lbl}: {model.get('make_hex')}\n"
                    f"{fl_lbl}: {model.get('flags_hex')} ({flags_d})\n"
                    f"{msg_lbl}: {model.get('msg_hex')} ({msg_n})\n"
                    f"{self.i18n.t('desc')}: {msg_d}"
                );

            if t == 'hid':
                return (
                    f"{prefix} {self.i18n.t('hid')}{vidpid}\n"
                    f"{dev}\n"
                    f"{self.i18n.t('sizehid')}: {model.get('sizehid')} {self.i18n.t('count')}: {model.get('count')} {self.i18n.t('bytes')}: {model.get('bytes')}\n"
                    f"{self.i18n.t('data_sample')}: {model.get('sample')}"
                );

            return f"{prefix} {self.i18n.t('other')}\n{dev}";

        return model.get('text', '');

    # ---------- Shutdown ----------

    def on_close(self):
        try:
            try:
                self.listener.stop();
            except Exception:
                pass
        finally:
            self.root.destroy();

    # ---------- Raw input pipeline ----------

    def _on_event_from_listener(self, ev):
        self._pending_events.append(ev);
        if self._drain_scheduled:
            return;
        self._drain_scheduled = True;
        self.root.after(0, self._drain_pending);

    def _drain_pending(self):
        self._drain_scheduled = False;
        while True:
            try:
                ev = self._pending_events.popleft();
            except IndexError:
                break
            self._handle_event(ev);

    def _device_meta_by_handle(self, hdev):
        key_int = int(ctypes.cast(hdev, ctypes.c_void_p).value or 0);
        key = f"0x{key_int:X}";
        if key_int in self._cache:
            return self._cache[key_int];

        raw_path = get_device_name(hdev);
        info = get_device_info(hdev);
        tr_key = classify_transport(raw_path);
        parsed = parse_device_path(raw_path);

        friendly = (get_friendly_device_name(raw_path) or '').strip();

        vid = parsed.get('vid');
        pid = parsed.get('pid');
        if not vid or not pid:
            if info and getattr(info, 'dwType', None) == 2:
                vid = f"{info.u.hid.dwVendorId:04X}";
                pid = f"{info.u.hid.dwProductId:04X}";

        shown = self._device_display_name(friendly, vid, pid);

        meta = {
            'key': key,
            'raw_path': raw_path,
            'friendly': friendly,
            'vid': vid,
            'pid': pid,
            'transport_key': tr_key,
            'vidpid': '',
            'parsed': parsed,
            'name': shown,
        };

        if info and info.dwType == 2:
            v = info.u.hid.dwVendorId;
            p = info.u.hid.dwProductId;
            up = info.u.hid.usUsagePage;
            u = info.u.hid.usUsage;
            meta['vidpid'] = f" VID={v:04X} PID={p:04X} UP={up:02X} U={u:02X}";

        self._cache[key_int] = meta;

        if key not in self._devices:
            self._devices[key] = shown;
            self._device_keys_sorted = sorted(self._devices.keys());
            self._rebuild_device_dropdown();

        return meta;

    def _handle_event(self, ev):
        meta = self._device_meta_by_handle(ev.hDevice);

        if self._selected_device_key is not None and meta['key'] != self._selected_device_key:
            return;

        p = meta.get('parsed') or {};
        mbase = {
            'ts': now(),
            'handle': meta.get('key'),
            'transport_key': meta.get('transport_key', 'unknown'),
            'friendly': meta.get('friendly', ''),
            'vid': p.get('vid') or meta.get('vid'),
            'pid': p.get('pid') or meta.get('pid'),
            'mi': p.get('mi'),
            'guid': p.get('guid'),
            'path': p.get('path') or meta.get('raw_path'),
            'vidpid': meta.get('vidpid', ''),
        };

        if isinstance(ev, RawKeyboardEvent):
            vk_n = vk_name(ev.VKey);
            key_human = scancode_key_name(ev.MakeCode, ev.Flags);

            model = {
                **mbase,
                'type': 'kbd',
                'key_human': key_human,
                'vkey_hex': f"0x{ev.VKey:02X}",
                'vk_name': vk_n,
                'make_hex': f"0x{ev.MakeCode:02X}",
                'flags': int(ev.Flags),
                'flags_hex': f"0x{ev.Flags:02X}",
                'message': int(ev.Message),
                'msg_hex': f"0x{ev.Message:04X}",
            };

            self.log_block(
                model=model,
                kind='kbd',
                device_name=meta.get('name') or '',
                device_key=meta.get('key') or '',
                device_path=meta.get('raw_path') or '',
            );
            return;

        if isinstance(ev, RawHidEvent):
            sample = ev.data[:min(len(ev.data), 64)].hex(' ');

            model = {
                **mbase,
                'type': 'hid',
                'sizehid': int(ev.sizeHid),
                'count': int(ev.count),
                'bytes': int(len(ev.data)),
                'sample': sample,
            };

            self.log_block(
                model=model,
                kind='hid',
                device_name=meta.get('name') or '',
                device_key=meta.get('key') or '',
                device_path=meta.get('raw_path') or '',
            );
            return;

        model = {**mbase, 'type': 'other'};
        self.log_block(
            model=model,
            kind='other',
            device_name=meta.get('name') or '',
            device_key=meta.get('key') or '',
            device_path=meta.get('raw_path') or '',
        );

    def run(self):
        self.root.mainloop();