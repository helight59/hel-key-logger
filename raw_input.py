import ctypes;
import ctypes.wintypes as wt;
from dataclasses import dataclass;

user32 = ctypes.WinDLL('user32', use_last_error=True);

WM_INPUT = 0x00FF;
RID_INPUT = 0x10000003;

RIM_TYPEMOUSE = 0;
RIM_TYPEKEYBOARD = 1;
RIM_TYPEHID = 2;

RIDEV_INPUTSINK = 0x00000100;

# FIX: Python 3.10 wintypes may miss HRAWINPUT
HRAWINPUT = getattr(wt, 'HRAWINPUT', wt.HANDLE);

class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [
        ('usUsagePage', wt.USHORT),
        ('usUsage', wt.USHORT),
        ('dwFlags', wt.DWORD),
        ('hwndTarget', wt.HWND),
    ];

class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [
        ('dwType', wt.DWORD),
        ('dwSize', wt.DWORD),
        ('hDevice', wt.HANDLE),
        ('wParam', wt.WPARAM),
    ];

class RAWKEYBOARD(ctypes.Structure):
    _fields_ = [
        ('MakeCode', wt.USHORT),
        ('Flags', wt.USHORT),
        ('Reserved', wt.USHORT),
        ('VKey', wt.USHORT),
        ('Message', wt.UINT),
        ('ExtraInformation', wt.ULONG),
    ];

class RAWHID(ctypes.Structure):
    _fields_ = [
        ('dwSizeHid', wt.DWORD),
        ('dwCount', wt.DWORD),
    ];

class RAWINPUT_UNION(ctypes.Union):
    _fields_ = [
        ('keyboard', RAWKEYBOARD),
        ('hid', RAWHID),
    ];

class RAWINPUT(ctypes.Structure):
    _fields_ = [
        ('header', RAWINPUTHEADER),
        ('data', RAWINPUT_UNION),
    ];

RegisterRawInputDevices = user32.RegisterRawInputDevices;
RegisterRawInputDevices.argtypes = (ctypes.POINTER(RAWINPUTDEVICE), wt.UINT, wt.UINT);
RegisterRawInputDevices.restype = wt.BOOL;

GetRawInputData = user32.GetRawInputData;
GetRawInputData.argtypes = (HRAWINPUT, wt.UINT, wt.LPVOID, ctypes.POINTER(wt.UINT), wt.UINT);
GetRawInputData.restype = wt.UINT;

@dataclass(frozen=True)
class RawKeyboardEvent:
    hDevice: wt.HANDLE;
    VKey: int;
    MakeCode: int;
    Flags: int;
    Message: int;

@dataclass(frozen=True)
class RawHidEvent:
    hDevice: wt.HANDLE;
    sizeHid: int;
    count: int;
    data: bytes;

def register_default_devices(hwnd: wt.HWND) -> bool:
    regs = [
        (0x01, 0x06),  # Keyboard
        (0x0C, 0x01),  # Consumer Control
        (0x01, 0x80),  # System Control
        (0x01, 0x05),  # Gamepad
        (0x01, 0x04),  # Joystick
    ];
    devices = (RAWINPUTDEVICE * len(regs))();
    for i, (page, usage) in enumerate(regs):
        devices[i].usUsagePage = page;
        devices[i].usUsage = usage;
        devices[i].dwFlags = RIDEV_INPUTSINK;
        devices[i].hwndTarget = hwnd;
    return bool(RegisterRawInputDevices(devices, len(regs), ctypes.sizeof(RAWINPUTDEVICE)));

def parse_wm_input(lparam: wt.LPARAM) -> RawKeyboardEvent | RawHidEvent | None:
    size = wt.UINT(0);
    GetRawInputData(HRAWINPUT(lparam), RID_INPUT, None, ctypes.byref(size), ctypes.sizeof(RAWINPUTHEADER));
    if size.value == 0:
        return None;

    buf = (ctypes.c_byte * size.value)();
    res = GetRawInputData(HRAWINPUT(lparam), RID_INPUT, buf, ctypes.byref(size), ctypes.sizeof(RAWINPUTHEADER));
    if res == 0xFFFFFFFF:
        return None;

    raw = ctypes.cast(buf, ctypes.POINTER(RAWINPUT)).contents;

    if raw.header.dwType == RIM_TYPEKEYBOARD:
        kb = raw.data.keyboard;
        return RawKeyboardEvent(
            hDevice=raw.header.hDevice,
            VKey=int(kb.VKey),
            MakeCode=int(kb.MakeCode),
            Flags=int(kb.Flags),
            Message=int(kb.Message),
        );

    if raw.header.dwType == RIM_TYPEHID:
        hid = raw.data.hid;
        total = int(hid.dwCount * hid.dwSizeHid);
        base = ctypes.addressof(buf) + ctypes.sizeof(RAWINPUTHEADER) + ctypes.sizeof(RAWHID);
        data = ctypes.string_at(base, total);
        return RawHidEvent(
            hDevice=raw.header.hDevice,
            sizeHid=int(hid.dwSizeHid),
            count=int(hid.dwCount),
            data=data,
        );

    return None;