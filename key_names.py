import ctypes;
import ctypes.wintypes as wt;

user32 = ctypes.WinDLL('user32', use_last_error=True);

MapVirtualKeyW = user32.MapVirtualKeyW;
MapVirtualKeyW.argtypes = (wt.UINT, wt.UINT);
MapVirtualKeyW.restype = wt.UINT;

GetKeyNameTextW = user32.GetKeyNameTextW;
GetKeyNameTextW.argtypes = (wt.LPARAM, wt.LPWSTR, wt.INT);
GetKeyNameTextW.restype = wt.INT;

MAPVK_VSC_TO_VK_EX = 3;

_WM_MAP = {
    0x0100: ('WM_KEYDOWN', 'msg_keydown'),
    0x0101: ('WM_KEYUP', 'msg_keyup'),
    0x0104: ('WM_SYSKEYDOWN', 'msg_syskeydown'),
    0x0105: ('WM_SYSKEYUP', 'msg_syskeyup'),
};

_VK_NAMES = {
    0x08: 'VK_BACK',
    0x09: 'VK_TAB',
    0x0D: 'VK_RETURN',
    0x10: 'VK_SHIFT',
    0x11: 'VK_CONTROL',
    0x12: 'VK_MENU',
    0x13: 'VK_PAUSE',
    0x14: 'VK_CAPITAL',
    0x1B: 'VK_ESCAPE',
    0x20: 'VK_SPACE',
    0x21: 'VK_PRIOR',
    0x22: 'VK_NEXT',
    0x23: 'VK_END',
    0x24: 'VK_HOME',
    0x25: 'VK_LEFT',
    0x26: 'VK_UP',
    0x27: 'VK_RIGHT',
    0x28: 'VK_DOWN',
    0x2C: 'VK_SNAPSHOT',
    0x2D: 'VK_INSERT',
    0x2E: 'VK_DELETE',
    0x5B: 'VK_LWIN',
    0x5C: 'VK_RWIN',
    0x5D: 'VK_APPS',
    0x90: 'VK_NUMLOCK',
    0x91: 'VK_SCROLL',
    0xA0: 'VK_LSHIFT',
    0xA1: 'VK_RSHIFT',
    0xA2: 'VK_LCONTROL',
    0xA3: 'VK_RCONTROL',
    0xA4: 'VK_LMENU',
    0xA5: 'VK_RMENU',
    0xA6: 'VK_BROWSER_BACK',
    0xA7: 'VK_BROWSER_FORWARD',
    0xA8: 'VK_BROWSER_REFRESH',
    0xA9: 'VK_BROWSER_STOP',
    0xAA: 'VK_BROWSER_SEARCH',
    0xAB: 'VK_BROWSER_FAVORITES',
    0xAC: 'VK_BROWSER_HOME',
    0xAD: 'VK_VOLUME_MUTE',
    0xAE: 'VK_VOLUME_DOWN',
    0xAF: 'VK_VOLUME_UP',
    0xB0: 'VK_MEDIA_NEXT_TRACK',
    0xB1: 'VK_MEDIA_PREV_TRACK',
    0xB2: 'VK_MEDIA_STOP',
    0xB3: 'VK_MEDIA_PLAY_PAUSE',
    0xB4: 'VK_LAUNCH_MAIL',
    0xB5: 'VK_LAUNCH_MEDIA_SELECT',
    0xB6: 'VK_LAUNCH_APP1',
    0xB7: 'VK_LAUNCH_APP2',
};

def vk_name(vk: int) -> str:
    if 0x30 <= vk <= 0x39:
        return f'VK_{chr(vk)}';
    if 0x41 <= vk <= 0x5A:
        return f'VK_{chr(vk)}';
    if 0x70 <= vk <= 0x87:
        return f'VK_F{vk - 0x6F}';
    return _VK_NAMES.get(vk, f'VK_0x{vk:02X}');

def msg_info(msg: int, i18n) -> tuple[str, str]:
    name_key = _WM_MAP.get(msg);
    if not name_key:
        return (f'0x{msg:04X}', i18n.t('msg_unknown'));
    name, key = name_key;
    return (name, i18n.t(key));

def flags_info(flags: int, i18n) -> str:
    parts = [];
    if flags & 0x01:
        parts.append(i18n.t('flag_break'));
    if flags & 0x02:
        parts.append(i18n.t('flag_e0'));
    if flags & 0x04:
        parts.append(i18n.t('flag_e1'));
    if not parts:
        return i18n.t('flags_none');
    return ', '.join(parts);

def scancode_key_name(make_code: int, flags: int) -> str:
    sc = int(make_code) & 0xFF;
    extended = 1 if (flags & 0x02) else 0;
    lparam = (sc << 16) | (extended << 24);
    buf = ctypes.create_unicode_buffer(128);
    n = GetKeyNameTextW(lparam, buf, 128);
    if n > 0:
        return buf.value;
    vk = MapVirtualKeyW(sc, MAPVK_VSC_TO_VK_EX);
    return vk_name(int(vk));