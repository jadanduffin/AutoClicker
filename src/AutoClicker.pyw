# AutoClicker: press the hotkey (default F6) anywhere to arm it; while armed, holding the left mouse button
# fires rapid left-clicks until you let go. Close the window to quit.
# Styled to Jadan Duffin's design system (ink ground, one orange, Schibsted Grotesk + JetBrains Mono).
import ctypes, json, os, shutil, subprocess, sys, threading, time, tkinter as tk, urllib.request
from ctypes import wintypes

VERSION = os.environ.get("AUTOCLICKER_VERSION", "1.0")  # build.ps1 reads this number; the env override only lets the update test pretend to be old
REPO = "jadanduffin/AutoClicker"  # GitHub releases are checked on launch for a newer AutoClicker-Setup.exe

user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
running = False  # armed by the hotkey
held = False     # the user's own left button is physically down
clicks = 0
OWN = 0x4A44  # tag on our injected clicks so the mouse hook ignores them and only sees the user's button
user32.mouse_event.argtypes = [wintypes.DWORD] * 4 + [ctypes.c_size_t]

INK, INK2, LINE = "#08090A", "#0E0F11", "#1E1F21"
FG, MUTED, MUTED2, ACCENT = "#F4F5F4", "#9A9DA3", "#696C72", "#FB4B1D"
SANS, MONO = "Schibsted Grotesk ExtraBold", "JetBrains Mono"
HERE = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))  # PyInstaller unpacks bundled files to _MEIPASS
MARK = os.path.join(HERE, "jd-icon-dark.png")
SETTINGS = os.path.join(os.environ["APPDATA"], "AutoClicker.json")

MODS = {0x11: "Ctrl", 0x10: "Shift", 0x12: "Alt"}
NOT_A_TRIGGER = {0x01, 0x1B, 0x5B, 0x5C, *MODS, *range(0xA0, 0xA6)}  # left click, Esc, Win keys, modifiers (incl. left/right variants)
MOUSE = {0x02: "Right click", 0x04: "Middle click", 0x05: "Mouse 4", 0x06: "Mouse 5"}
EXTENDED = {0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E, 0x6F}  # nav keys whose name needs the extended-key bit

hotkey = {"vk": 0x75, "mods": []}  # F6
try:
    hotkey = json.load(open(SETTINGS))
except Exception:
    pass

def key_name(vk):
    if vk in MOUSE:
        return MOUSE[vk]
    buf = ctypes.create_unicode_buffer(64)
    user32.GetKeyNameTextW((user32.MapVirtualKeyW(vk, 0) << 16) | ((vk in EXTENDED) << 24), buf, 64)
    return buf.value or f"Key {vk}"

def hotkey_name():
    return " + ".join([MODS[m] for m in hotkey["mods"]] + [key_name(hotkey["vk"])])

def down(vk):
    return user32.GetAsyncKeyState(vk) & 0x8000  # high bit = held right now (the low "pressed since" bit gets eaten by games)

def clicker():
    global clicks
    while True:
        if running and held:
            user32.mouse_event(2, 0, 0, 0, OWN)  # left down
            user32.mouse_event(4, 0, 0, 0, OWN)  # left up
            clicks += 1  # no sleep: Windows itself takes ~2 ms per click, so this already runs at the ceiling
        else:
            time.sleep(0.02)

# low-level mouse hook: the only way to see the real button while we are injecting clicks ourselves
class MSLL(ctypes.Structure):
    _fields_ = [("pt", wintypes.POINT), ("mouseData", wintypes.DWORD), ("flags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]
HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
user32.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
user32.CallNextHookEx.restype = ctypes.c_ssize_t
user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
user32.SetWindowsHookExW.restype = wintypes.HHOOK
kernel32.GetModuleHandleW.restype = wintypes.HMODULE  # default int return truncates the 64-bit handle (error 126)

@HOOKPROC
def mouse_hook(code, wparam, lparam):
    global held
    if code >= 0 and wparam in (0x201, 0x202) and ctypes.cast(lparam, ctypes.POINTER(MSLL)).contents.dwExtraInfo != OWN:
        held = wparam == 0x201  # WM_LBUTTONDOWN / WM_LBUTTONUP from the user
    return user32.CallNextHookEx(None, code, wparam, lparam)
hook = user32.SetWindowsHookExW(14, mouse_hook, kernel32.GetModuleHandleW(None), 0)  # WH_MOUSE_LL, needs this thread's message loop (tk's)

root = tk.Tk()
root.title("AutoClicker")
root.configure(bg=INK)
root.attributes("-topmost", True)
root.resizable(False, False)
if os.path.exists(os.path.join(HERE, "AutoClicker.ico")):
    root.iconbitmap(os.path.join(HERE, "AutoClicker.ico"))
root.update()
ctypes.windll.dwmapi.DwmSetWindowAttribute(user32.GetParent(root.winfo_id()), 20, ctypes.byref(ctypes.c_int(1)), 4)  # dark title bar

body = tk.Frame(root, bg=INK, padx=24, pady=20)
body.pack()

head = tk.Frame(body, bg=INK)
head.pack(fill="x")
try:
    from PIL import Image, ImageTk
    mark = ImageTk.PhotoImage(Image.open(MARK).resize((28, 28), Image.LANCZOS))
    tk.Label(head, image=mark, bg=INK).pack(side="left", padx=(0, 10))
except Exception:
    pass  # shortcut: no Pillow or no mark on this machine, skip the logo
tk.Label(head, text="AUTOCLICKER", font=(MONO, 9), fg=MUTED2, bg=INK).pack(side="left")

# the one orange fill per view: a full-width notice bar that lights up while clicking
state = tk.Label(body, text="OFF", font=(SANS, 22), fg=MUTED, bg=INK2, pady=14)
state.pack(fill="x", pady=(22, 0))

value = tk.Label(body, text="0", font=(SANS, 48), fg=FG, bg=INK, anchor="w")
value.pack(fill="x", pady=(16, 0))
tk.Label(body, text="CLICKS / SEC", font=(MONO, 9), fg=MUTED2, bg=INK, anchor="w").pack(fill="x")

tk.Frame(body, bg=LINE, height=1).pack(fill="x", pady=(20, 12))
tk.Label(body, text="HOTKEY", font=(MONO, 9), fg=MUTED2, bg=INK, anchor="w").pack(fill="x")
row = tk.Frame(body, bg=INK)
row.pack(fill="x", pady=(4, 0))
key_label = tk.Label(row, text="", font=(MONO, 11), fg=FG, bg=INK, anchor="w")
key_label.pack(side="left", fill="x", expand=True)
set_btn = tk.Label(row, text="SET", font=(MONO, 9), fg=MUTED, bg=INK2, padx=12, pady=4, cursor="hand2")
set_btn.pack(side="right")
HINT = "arms it · then hold left mouse to click"
hint = tk.Label(body, text=HINT, font=(MONO, 9), fg=MUTED2, bg=INK, anchor="w")
hint.pack(fill="x", pady=(10, 0))

# update notice: hidden until a newer release exists on GitHub
upd_row = tk.Frame(body, bg=INK)
upd_label = tk.Label(upd_row, text="", font=(MONO, 9), fg=MUTED, bg=INK, anchor="w")
upd_label.pack(side="left", fill="x", expand=True)
upd_btn = tk.Label(upd_row, text="UPDATE", font=(MONO, 9), fg=ACCENT, bg=INK2, padx=12, pady=4, cursor="hand2")
upd_btn.pack(side="right")
latest = {}

def install_update(_=None):
    upd_btn.config(text="DOWNLOADING", fg=MUTED, cursor="arrow")
    upd_btn.unbind("<Button-1>")
    def go():
        path = os.path.join(os.environ["TEMP"], "AutoClicker-Setup.exe")
        try:
            req = urllib.request.Request(latest["url"], headers={"User-Agent": "AutoClicker"})
            with urllib.request.urlopen(req, timeout=30) as r, open(path, "wb") as f:
                shutil.copyfileobj(r, f)
            subprocess.Popen([path])  # the installer takes over; it closes this copy and replaces it
            root.after(0, root.destroy)
        except Exception:
            root.after(0, lambda: (upd_btn.config(text="FAILED · RETRY", fg=ACCENT, cursor="hand2"), upd_btn.bind("<Button-1>", install_update)))
    threading.Thread(target=go, daemon=True).start()

def show_update():
    upd_label.config(text=f"v{latest['tag']} available")
    upd_btn.bind("<Button-1>", install_update)
    tk.Frame(body, bg=LINE, height=1).pack(fill="x", pady=(16, 12))
    upd_row.pack(fill="x")

def check_update():
    try:
        req = urllib.request.Request(f"https://api.github.com/repos/{REPO}/releases/latest", headers={"User-Agent": "AutoClicker"})
        rel = json.load(urllib.request.urlopen(req, timeout=5))
        tag = rel["tag_name"].lstrip("v")
        if tuple(map(int, tag.split("."))) > tuple(map(int, VERSION.split("."))):
            latest.update(tag=tag, url=next(a["browser_download_url"] for a in rel["assets"] if a["name"].endswith("Setup.exe")))
            root.after(0, show_update)
    except Exception:
        pass  # offline, rate-limited or no release yet: say nothing

capturing = False
was_down = False

def show_hotkey():
    key_label.config(text=hotkey_name(), fg=FG)
    hint.config(text=HINT)

def start_capture(_=None):
    global capturing, was_down
    capturing, was_down = True, True
    key_label.config(text="press a key, combo or mouse button", fg=MUTED)
    hint.config(text="Esc cancels")

set_btn.bind("<Button-1>", start_capture)

def toggle():
    global running
    running = not running
    state.config(text="ARMED" if running else "OFF", fg=FG if running else MUTED, bg=ACCENT if running else INK2)

def poll():
    global capturing, was_down, hotkey
    if capturing:
        if down(0x1B):
            capturing = False
            show_hotkey()
        else:
            for vk in range(0x02, 0xFF):
                if vk not in NOT_A_TRIGGER and down(vk):
                    hotkey = {"vk": vk, "mods": [m for m in MODS if down(m)]}
                    try:
                        json.dump(hotkey, open(SETTINGS, "w"))
                    except Exception:
                        pass  # shortcut: unsaved hotkey still works for this run
                    capturing = False
                    show_hotkey()
                    break
    else:
        is_down = down(hotkey["vk"]) and all(down(m) for m in hotkey["mods"])
        if is_down and not was_down:
            toggle()
        was_down = is_down
    root.after(10, poll)

def update_rate():
    global clicks
    value.config(text=str(clicks * 2))
    clicks = 0
    root.after(500, update_rate)

show_hotkey()
threading.Thread(target=clicker, daemon=True).start()
threading.Thread(target=check_update, daemon=True).start()
poll()
update_rate()
root.mainloop()
