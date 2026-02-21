import re;

_RE_VID = re.compile(r'VID_([0-9A-Fa-f]{4})');
_RE_PID = re.compile(r'PID_([0-9A-Fa-f]{4})');
_RE_MI = re.compile(r'&MI_([0-9A-Fa-f]{2})');
_RE_GUID = re.compile(r'\{([0-9A-Fa-f-]{36})\}\s*$');

def parse_device_path(path: str | None) -> dict:
    s = (path or '').strip();
    vid = None;
    pid = None;
    mi = None;
    guid = None;

    m = _RE_VID.search(s);
    if m:
        vid = m.group(1).upper();

    m = _RE_PID.search(s);
    if m:
        pid = m.group(1).upper();

    m = _RE_MI.search(s);
    if m:
        mi = m.group(1).upper();

    m = _RE_GUID.search(s);
    if m:
        guid = m.group(1).lower();

    return {
        'vid': vid,
        'pid': pid,
        'mi': mi,
        'guid': guid,
        'path': s if s else None,
    };