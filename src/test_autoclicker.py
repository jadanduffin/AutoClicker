# Self-check: launch the app, arm it with F6, hold the left button, expect a burst of app-made clicks, release, expect silence.
# Counts the app's own clicks through a low-level mouse hook (they carry the 0x4A44 tag), so cursor position does not matter.
# Usage: python test_autoclicker.py [path\to\AutoClicker.exe]   (no arg = run the .pyw next to this file)
import ctypes, os, subprocess, sys, time
from ctypes import wintypes
user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
def windows(title):  # every top-level window with this title, so the test can tell its own copy from one the user has open
    found = []
    @ctypes.WINFUNCTYPE(ctypes.c_int, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _):
        buf = ctypes.create_unicode_buffer(64); user32.GetWindowTextW(hwnd, buf, 64)
        if user32.IsWindowVisible(hwnd) and buf.value == title: found.append(hwnd)
        return 1
    user32.EnumWindows(cb, 0)
    return found
OWN = 0x4A44
app_clicks = 0

class MSLL(ctypes.Structure):
    _fields_ = [("pt", wintypes.POINT), ("mouseData", wintypes.DWORD), ("flags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]
HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
user32.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
user32.CallNextHookEx.restype = ctypes.c_ssize_t
user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
user32.SetWindowsHookExW.restype = wintypes.HHOOK
kernel32.GetModuleHandleW.restype = wintypes.HMODULE
@HOOKPROC
def hook(code, wparam, lparam):
    global app_clicks
    if code >= 0 and wparam == 0x201 and ctypes.cast(lparam, ctypes.POINTER(MSLL)).contents.dwExtraInfo == OWN:
        app_clicks += 1
    return user32.CallNextHookEx(None, code, wparam, lparam)
assert user32.SetWindowsHookExW(14, hook, kernel32.GetModuleHandleW(None), 0), "hook failed"

msg = wintypes.MSG()
def pump(seconds):  # the hook only fires while this thread pumps messages
    t0 = time.time()
    while time.time() - t0 < seconds:
        while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
            user32.TranslateMessage(ctypes.byref(msg)); user32.DispatchMessageW(ctypes.byref(msg))
        time.sleep(0.002)

SETTINGS = os.path.join(os.environ["APPDATA"], "AutoClicker.json")  # the test presses F6 and expects full speed, so force both and restore after
saved = open(SETTINGS).read() if os.path.exists(SETTINGS) else None
open(SETTINGS, "w").write('{"vk": 117, "mods": [], "cps": 40}')
import atexit
atexit.register(lambda: open(SETTINGS, "w").write(saved) if saved is not None else os.remove(SETTINGS))
before = set(windows("AutoClicker"))
app = subprocess.Popen(sys.argv[1:] or [sys.executable, os.path.join(os.path.dirname(__file__), "AutoClicker.pyw")])
for _ in range(60):  # a one-file exe unpacks first, so wait for the window rather than a fixed time
    pump(0.25)
    new = set(windows("AutoClicker")) - before
    if new: break
else: raise SystemExit("AutoClicker window never appeared")
pump(1.5)
hwnd = new.pop()
user32.SetCursorPos(-2900, 500)  # park over the app's own window on the second monitor so stray clicks hit nothing important
user32.SetWindowPos(hwnd, None, -3000, 200, 0, 0, 0x0001 | 0x0004); pump(0.3)
user32.keybd_event(0x75, 0, 0, 0); time.sleep(0.05); user32.keybd_event(0x75, 0, 2, 0)  # F6: arm
pump(1)
armed_only = app_clicks  # armed but button not held: must be silent
user32.mouse_event(2, 0, 0, 0, 0)  # "user" presses and holds the left button (no OWN tag, so the app treats it as real)
pump(3)
on_count = app_clicks - armed_only
user32.mouse_event(4, 0, 0, 0, 0)  # release
pump(0.3); before = app_clicks
pump(1)
after_release = app_clicks - before
def tap_ctrl():
    user32.keybd_event(0x11, 0, 0, 0); time.sleep(0.05); user32.keybd_event(0x11, 0, 2, 0)
tap_ctrl(); pump(0.3); before = app_clicks  # lock on: clicks without any button held
pump(2)
lock_count = app_clicks - before
tap_ctrl(); pump(0.3); before = app_clicks  # lock off
pump(1)
after_unlock = app_clicks - before
user32.keybd_event(0x75, 0, 0, 0); time.sleep(0.05); user32.keybd_event(0x75, 0, 2, 0)  # disarm
pump(0.3)
user32.PostMessageW(hwnd, 0x10, 0, 0); pump(1)  # WM_CLOSE: a one-file exe is parent+child, terminate() would orphan the child
print(f"armed, not holding (1s): {armed_only} ; holding (3s): {on_count} -> {on_count/3:.0f}/sec ; after release (1s): {after_release}")
print(f"Ctrl lock (2s): {lock_count} -> {lock_count/2:.0f}/sec ; after Ctrl again (1s): {after_unlock}")
assert armed_only == 0 and 100 <= on_count <= 125 and after_release == 0, "FAIL"  # 40/sec cap: 3 s of holding is ~120 clicks
assert 65 <= lock_count <= 85 and after_unlock == 0, "FAIL (Ctrl lock)"
print("PASS")
