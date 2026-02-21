import ctypes;
import ctypes.wintypes as wt;

setupapi = ctypes.WinDLL('setupapi', use_last_error=True);

DIGCF_PRESENT = 0x00000002;
DIGCF_DEVICEINTERFACE = 0x00000010;

SPDRP_DEVICEDESC = 0x00000000;
SPDRP_FRIENDLYNAME = 0x0000000C;

ERROR_NO_MORE_ITEMS = 259;

HRESULT = ctypes.c_long;
ULONG_PTR = ctypes.c_size_t;
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value;

class GUID(ctypes.Structure):
    _fields_ = [
        ('Data1', wt.DWORD),
        ('Data2', wt.WORD),
        ('Data3', wt.WORD),
        ('Data4', wt.BYTE * 8),
    ];

def _guid_from_str(s: str) -> GUID:
    g = GUID();
    ole32 = ctypes.OleDLL('ole32', use_last_error=True);
    IIDFromString = ole32.IIDFromString;
    IIDFromString.argtypes = (wt.LPCWSTR, ctypes.POINTER(GUID));
    IIDFromString.restype = HRESULT;
    hr = IIDFromString(s, ctypes.byref(g));
    if hr != 0:
        raise OSError(f'IIDFromString failed hr={hr}');
    return g;

GUID_DEVINTERFACE_HID = _guid_from_str('{4D1E55B2-F16F-11CF-88CB-001111000030}');

class SP_DEVINFO_DATA(ctypes.Structure):
    _fields_ = [
        ('cbSize', wt.DWORD),
        ('ClassGuid', GUID),
        ('DevInst', wt.DWORD),
        ('Reserved', ULONG_PTR),
    ];

class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    _fields_ = [
        ('cbSize', wt.DWORD),
        ('InterfaceClassGuid', GUID),
        ('Flags', wt.DWORD),
        ('Reserved', ULONG_PTR),
    ];

SetupDiGetClassDevsW = setupapi.SetupDiGetClassDevsW;
SetupDiGetClassDevsW.argtypes = (ctypes.POINTER(GUID), wt.LPCWSTR, wt.HWND, wt.DWORD);
SetupDiGetClassDevsW.restype = wt.HANDLE;

SetupDiEnumDeviceInterfaces = setupapi.SetupDiEnumDeviceInterfaces;
SetupDiEnumDeviceInterfaces.argtypes = (wt.HANDLE, wt.LPVOID, ctypes.POINTER(GUID), wt.DWORD, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA));
SetupDiEnumDeviceInterfaces.restype = wt.BOOL;

SetupDiGetDeviceInterfaceDetailW = setupapi.SetupDiGetDeviceInterfaceDetailW;
SetupDiGetDeviceInterfaceDetailW.argtypes = (wt.HANDLE, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA), wt.LPVOID, wt.DWORD, ctypes.POINTER(wt.DWORD), ctypes.POINTER(SP_DEVINFO_DATA));
SetupDiGetDeviceInterfaceDetailW.restype = wt.BOOL;

SetupDiGetDeviceRegistryPropertyW = setupapi.SetupDiGetDeviceRegistryPropertyW;
SetupDiGetDeviceRegistryPropertyW.argtypes = (wt.HANDLE, ctypes.POINTER(SP_DEVINFO_DATA), wt.DWORD, ctypes.POINTER(wt.DWORD), wt.LPBYTE, wt.DWORD, ctypes.POINTER(wt.DWORD));
SetupDiGetDeviceRegistryPropertyW.restype = wt.BOOL;

SetupDiDestroyDeviceInfoList = setupapi.SetupDiDestroyDeviceInfoList;
SetupDiDestroyDeviceInfoList.argtypes = (wt.HANDLE,);
SetupDiDestroyDeviceInfoList.restype = wt.BOOL;

def _get_reg_str(hinfo: wt.HANDLE, devinfo: SP_DEVINFO_DATA, prop: int) -> str | None:
    reg_type = wt.DWORD(0);
    needed = wt.DWORD(0);

    SetupDiGetDeviceRegistryPropertyW(hinfo, ctypes.byref(devinfo), prop, ctypes.byref(reg_type), None, 0, ctypes.byref(needed));
    if needed.value == 0:
        return None;

    buf = (wt.BYTE * needed.value)();
    ok = SetupDiGetDeviceRegistryPropertyW(
        hinfo,
        ctypes.byref(devinfo),
        prop,
        ctypes.byref(reg_type),
        ctypes.cast(buf, wt.LPBYTE),
        needed,
        ctypes.byref(needed),
    );
    if not ok:
        return None;

    raw = bytes(buf);
    try:
        s = raw.decode('utf-16le', errors='ignore').rstrip('\x00');
        return s if s else None;
    except Exception:
        return None;

def find_friendly_name_by_raw_path(raw_path: str) -> str | None:
    if not raw_path:
        return None;
    want = raw_path.strip().lower();

    hinfo = SetupDiGetClassDevsW(ctypes.byref(GUID_DEVINTERFACE_HID), None, None, DIGCF_PRESENT | DIGCF_DEVICEINTERFACE);
    if ctypes.c_void_p(hinfo).value == INVALID_HANDLE_VALUE:
        return None;

    try:
        idx = 0;
        while True:
            iface = SP_DEVICE_INTERFACE_DATA();
            iface.cbSize = ctypes.sizeof(SP_DEVICE_INTERFACE_DATA);

            ok = SetupDiEnumDeviceInterfaces(hinfo, None, ctypes.byref(GUID_DEVINTERFACE_HID), idx, ctypes.byref(iface));
            if not ok:
                err = ctypes.get_last_error();
                if err == ERROR_NO_MORE_ITEMS:
                    break;
                break;

            needed = wt.DWORD(0);
            devinfo = SP_DEVINFO_DATA();
            devinfo.cbSize = ctypes.sizeof(SP_DEVINFO_DATA);

            SetupDiGetDeviceInterfaceDetailW(hinfo, ctypes.byref(iface), None, 0, ctypes.byref(needed), ctypes.byref(devinfo));
            if needed.value:
                buf = (wt.BYTE * needed.value)();
                cb = 8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 6;
                ctypes.cast(buf, ctypes.POINTER(wt.DWORD)).contents.value = cb;

                ok2 = SetupDiGetDeviceInterfaceDetailW(hinfo, ctypes.byref(iface), ctypes.byref(buf), needed, ctypes.byref(needed), ctypes.byref(devinfo));
                if ok2:
                    p = ctypes.cast(ctypes.byref(buf, cb), wt.LPWSTR).value;
                    if p and p.strip().lower() == want:
                        name = _get_reg_str(hinfo, devinfo, SPDRP_FRIENDLYNAME);
                        if not name:
                            name = _get_reg_str(hinfo, devinfo, SPDRP_DEVICEDESC);
                        return name;

            idx += 1;

    finally:
        SetupDiDestroyDeviceInfoList(hinfo);

    return None;