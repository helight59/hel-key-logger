import ctypes;
import ctypes.wintypes as wt;

from setupapi import find_friendly_name_by_raw_path;

user32 = ctypes.WinDLL('user32', use_last_error=True);

RIDI_DEVICENAME = 0x20000007;
RIDI_DEVICEINFO = 0x2000000B;

RIM_TYPEMOUSE = 0;
RIM_TYPEKEYBOARD = 1;
RIM_TYPEHID = 2;

class RID_DEVICE_INFO_HID(ctypes.Structure):
    _fields_ = [
        ('dwVendorId', wt.DWORD),
        ('dwProductId', wt.DWORD),
        ('dwVersionNumber', wt.DWORD),
        ('usUsagePage', wt.USHORT),
        ('usUsage', wt.USHORT),
    ];

class RID_DEVICE_INFO_KEYBOARD(ctypes.Structure):
    _fields_ = [
        ('dwType', wt.DWORD),
        ('dwSubType', wt.DWORD),
        ('dwKeyboardMode', wt.DWORD),
        ('dwNumberOfFunctionKeys', wt.DWORD),
        ('dwNumberOfIndicators', wt.DWORD),
        ('dwNumberOfKeysTotal', wt.DWORD),
    ];

class RID_DEVICE_INFO_MOUSE(ctypes.Structure):
    _fields_ = [
        ('dwId', wt.DWORD),
        ('dwNumberOfButtons', wt.DWORD),
        ('dwSampleRate', wt.DWORD),
        ('fHasHorizontalWheel', wt.BOOL),
    ];

class RID_DEVICE_INFO_UNION(ctypes.Union):
    _fields_ = [
        ('mouse', RID_DEVICE_INFO_MOUSE),
        ('keyboard', RID_DEVICE_INFO_KEYBOARD),
        ('hid', RID_DEVICE_INFO_HID),
    ];

class RID_DEVICE_INFO(ctypes.Structure):
    _fields_ = [
        ('cbSize', wt.DWORD),
        ('dwType', wt.DWORD),
        ('u', RID_DEVICE_INFO_UNION),
    ];

GetRawInputDeviceInfoW = user32.GetRawInputDeviceInfoW;
GetRawInputDeviceInfoW.argtypes = (wt.HANDLE, wt.UINT, wt.LPVOID, ctypes.POINTER(wt.UINT));
GetRawInputDeviceInfoW.restype = wt.UINT;

def get_device_name(hdev: wt.HANDLE) -> str:
    size = wt.UINT(0);
    GetRawInputDeviceInfoW(hdev, RIDI_DEVICENAME, None, ctypes.byref(size));
    if size.value == 0:
        return '';
    buf = ctypes.create_unicode_buffer(size.value);
    GetRawInputDeviceInfoW(hdev, RIDI_DEVICENAME, buf, ctypes.byref(size));
    return buf.value;

def get_device_info(hdev: wt.HANDLE) -> RID_DEVICE_INFO | None:
    info = RID_DEVICE_INFO();
    info.cbSize = ctypes.sizeof(RID_DEVICE_INFO);
    size = wt.UINT(info.cbSize);
    res = GetRawInputDeviceInfoW(hdev, RIDI_DEVICEINFO, ctypes.byref(info), ctypes.byref(size));
    if res == 0xFFFFFFFF:
        return None;
    return info;

def classify_transport(dev_name: str) -> str:
    n = dev_name.upper();
    if 'HIDGATT' in n:
        return 'bt_gatt';
    if 'BTHENUM' in n or 'BTHLEDEVICE' in n or 'BLUETOOTH' in n:
        return 'bt';
    if n.startswith('\\\\?\\HID#VID_') or 'USB' in n:
        return 'usb_or_dongle';
    return 'unknown';

def get_friendly_device_name(raw_path: str) -> str | None:
    try:
        return find_friendly_name_by_raw_path(raw_path);
    except Exception:
        return None;