# AutoClicker: press the hotkey (default F6) anywhere to arm it; while armed, holding the left mouse button
# fires left-clicks (1-40 per second, set in Settings) until you let go. Tap Ctrl while armed to lock the clicking
# on without holding the button; tap Ctrl again (or disarm) to stop. Close the window to quit.
# Styled to Jadan Duffin's design system (ink ground, one orange, Schibsted Grotesk + JetBrains Mono).
import ctypes, json, os, shutil, subprocess, sys, threading, time, tkinter as tk, tkinter.font as tkfont, urllib.request, webbrowser
from ctypes import wintypes

VERSION = os.environ.get("AUTOCLICKER_VERSION", "1.3")  # build.ps1 reads this number; the env override only lets the update test pretend to be old
REPO = "jadanduffin/AutoClicker"  # GitHub releases are checked on launch for a newer AutoClicker-Setup.exe
REPO_URL = f"https://github.com/{REPO}"
MAX_CPS = 40

user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
running = False  # armed by the hotkey
held = False     # the user's own left button is physically down
locked = False   # Ctrl was tapped while armed: click without holding the button
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

settings = {"vk": 0x75, "mods": [], "cps": MAX_CPS}  # F6, full speed
try:
    settings.update(json.load(open(SETTINGS)))
except Exception:
    pass
settings["cps"] = min(MAX_CPS, max(1, int(settings["cps"])))

def save_settings():
    try:
        json.dump(settings, open(SETTINGS, "w"))
    except Exception:
        pass  # shortcut: unsaved settings still work for this run

def key_name(vk):
    if vk in MOUSE:
        return MOUSE[vk]
    if 0x7C <= vk <= 0x87:
        return f"F{vk - 0x6F}"  # F13-F24: Windows has no key name text for these
    buf = ctypes.create_unicode_buffer(64)
    user32.GetKeyNameTextW((user32.MapVirtualKeyW(vk, 0) << 16) | ((vk in EXTENDED) << 24), buf, 64)
    return buf.value or f"Key {vk}"

def hotkey_name():
    return " + ".join([MODS[m] for m in settings["mods"]] + [key_name(settings["vk"])])

def down(vk):
    return user32.GetAsyncKeyState(vk) & 0x8000  # high bit = held right now (the low "pressed since" bit gets eaten by games)

def clicker():
    global clicks
    while True:
        if running and (held or locked):
            t = time.perf_counter()
            user32.mouse_event(2, 0, 0, 0, OWN)  # left down
            user32.mouse_event(4, 0, 0, 0, OWN)  # left up
            clicks += 1
            time.sleep(max(0, 1 / settings["cps"] - (time.perf_counter() - t)))
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

def label(parent, text, **kw):
    kw = {"font": (MONO, 9), "fg": MUTED2, "bg": INK, "anchor": "w", **kw}
    return tk.Label(parent, text=text, **kw)

class Button(tk.Canvas):  # the design system's pill button: raised fill, hairline (or orange) stroke; tk.Label cannot round corners
    def __init__(self, parent, text, cmd, fg=MUTED, bg=INK2, outline=LINE):
        super().__init__(parent, bg=parent.cget("bg"), highlightthickness=0, cursor="hand2")
        self.text, self.cmd, self.fg, self.fill, self.outline = text, cmd, fg, bg, outline
        self.bind("<Button-1>", lambda _: self.cmd and self.cmd())
        self.draw()
    def config(self, **kw):  # same calls the old Label took: text / fg / cursor
        self.text, self.fg = kw.pop("text", self.text), kw.pop("fg", self.fg)
        tk.Canvas.config(self, **kw)
        self.draw()
    def draw(self):
        self.delete("all")
        h = 26; d = h - 2; w = tkfont.Font(font=(MONO, 9)).measure(self.text) + 30
        tk.Canvas.config(self, width=w, height=h)
        for box in ((1, 1, 1 + d, 1 + d), (w - 1 - d, 1, w - 1, 1 + d)):
            self.create_oval(*box, fill=self.fill, outline=self.fill)
        self.create_rectangle(1 + d / 2, 1, w - 1 - d / 2, 1 + d, fill=self.fill, outline=self.fill)
        self.create_arc(1, 1, 1 + d, 1 + d, start=90, extent=180, style="arc", outline=self.outline)
        self.create_arc(w - 1 - d, 1, w - 1, 1 + d, start=-90, extent=180, style="arc", outline=self.outline)
        for y in (1, 1 + d):
            self.create_line(1 + d / 2, y, w - 1 - d / 2, y, fill=self.outline)
        self.create_text(w / 2, h / 2, text=self.text, font=(MONO, 9), fill=self.fg)
button = Button

def open_repo():
    webbrowser.open(REPO_URL)

images = []  # tk drops an image that nothing in Python references, so keep every one
def header(parent, name, right_text, right_cmd, outline=LINE):
    head = tk.Frame(parent, bg=INK)
    head.pack(fill="x")
    try:
        from PIL import Image, ImageTk
        images.append(ImageTk.PhotoImage(Image.open(MARK).resize((28, 28), Image.LANCZOS)))
        logo = tk.Label(head, image=images[-1], bg=INK, cursor="hand2")
        logo.pack(side="left", padx=(0, 10))
        logo.bind("<Button-1>", lambda _: open_repo())
    except Exception:
        pass  # shortcut: no Pillow or no mark on this machine, skip the logo
    title = label(head, name, cursor="hand2")
    title.pack(side="left")
    title.bind("<Button-1>", lambda _: open_repo())
    button(head, right_text, right_cmd, outline=outline).pack(side="right")

# ---------- main view ----------
main = tk.Frame(root, bg=INK, padx=24, pady=20)
header(main, "AUTOCLICKER", "SETTINGS", lambda: show(settings_view), outline=ACCENT)

# the one orange fill per view: a full-width notice bar that lights up while clicking
state = tk.Label(main, text="OFF", font=(SANS, 22), fg=MUTED, bg=INK2, pady=14)
state.pack(fill="x", pady=(22, 0))

value = tk.Label(main, text="0", font=(SANS, 48), fg=FG, bg=INK, anchor="w")
value.pack(fill="x", pady=(16, 0))
label(main, "CLICKS / SEC").pack(fill="x")

tk.Frame(main, bg=LINE, height=1).pack(fill="x", pady=(20, 12))
label(main, "HOTKEY").pack(fill="x")
key_line = label(main, "", fg=FG, font=(MONO, 11))
key_line.pack(fill="x", pady=(4, 0))
label(main, "arms it · then hold left mouse to click").pack(fill="x", pady=(4, 0))
label(main, "Ctrl locks the clicking on · Ctrl again stops").pack(fill="x")

# ---------- settings view ----------
settings_view = tk.Frame(root, bg=INK, padx=24, pady=20)
header(settings_view, "SETTINGS", "BACK", lambda: show(main))

label(settings_view, "HOTKEY").pack(fill="x", pady=(22, 0))
row = tk.Frame(settings_view, bg=INK)
row.pack(fill="x", pady=(4, 0))
key_label = label(row, "", fg=FG, font=(MONO, 11))
key_label.pack(side="left", fill="x", expand=True)
set_btn = button(row, "SET", lambda: start_capture())
set_btn.pack(side="right")
hint = label(settings_view, "arms the clicker from any app")
hint.pack(fill="x", pady=(4, 0))

tk.Frame(settings_view, bg=LINE, height=1).pack(fill="x", pady=(20, 12))
speed_row = tk.Frame(settings_view, bg=INK)
speed_row.pack(fill="x")
label(speed_row, "SPEED").pack(side="left")
speed_label = label(speed_row, "", fg=FG, anchor="e")
speed_label.pack(side="right")

def set_cps(v):
    settings["cps"] = int(float(v))
    speed_label.config(text=f"{settings['cps']} / SEC")
    save_settings()

class Slider(tk.Canvas):  # hairline track with a knob; tk.Scale cannot colour its knob apart from its background
    def __init__(self, parent, lo, hi, cmd):
        super().__init__(parent, width=100, height=24, bg=INK, highlightthickness=0, cursor="hand2")  # stretches to the view; keeps both views the same width
        self.lo, self.hi, self.cmd, self.v = lo, hi, cmd, lo
        self.bind("<Configure>", lambda _: self.draw())
        for ev in ("<Button-1>", "<B1-Motion>"):
            self.bind(ev, self.drag)
    def set(self, v):
        self.v = min(self.hi, max(self.lo, int(v)))
        self.draw()
        self.cmd(self.v)
    def drag(self, e):
        self.set(round(self.lo + (e.x - 8) / (self.winfo_width() - 16) * (self.hi - self.lo)))
    def draw(self):
        self.delete("all")
        w = self.winfo_width() - 16
        x = 8 + (self.v - self.lo) / (self.hi - self.lo) * w
        self.create_line(8, 12, 8 + w, 12, fill=LINE, width=2)
        self.create_line(8, 12, x, 12, fill=FG, width=2)
        self.create_oval(x - 7, 5, x + 7, 19, fill=FG, outline=INK)

slider = Slider(settings_view, 1, MAX_CPS, set_cps)
slider.pack(fill="x", pady=(8, 0))
slider.set(settings["cps"])
label(settings_view, f"clicks per second · max {MAX_CPS}").pack(fill="x", pady=(4, 0))

tk.Frame(settings_view, bg=LINE, height=1).pack(fill="x", pady=(20, 12))
src_row = tk.Frame(settings_view, bg=INK)
src_row.pack(fill="x")
label(src_row, f"v{VERSION} · open source").pack(side="left", padx=(0, 16))
button(src_row, "VIEW SOURCE", open_repo).pack(side="right")

# ---------- update stripe (bottom of main view, hidden until a newer release exists) ----------
upd_row = tk.Frame(root, bg=ACCENT, padx=24, pady=12)
upd_label = tk.Label(upd_row, text="", font=(MONO, 9), fg=FG, bg=ACCENT, anchor="w")
upd_label.pack(side="left", fill="x", expand=True)
upd_btn = button(upd_row, "UPDATE", lambda: install_update(), fg=FG, bg=INK)
upd_btn.pack(side="right")
latest = {}

def install_update():
    upd_btn.config(text="DOWNLOADING", fg=MUTED, cursor="arrow")
    upd_btn.cmd = None
    def go():
        path = os.path.join(os.environ["TEMP"], "AutoClicker-Setup.exe")
        try:
            req = urllib.request.Request(latest["url"], headers={"User-Agent": "AutoClicker"})
            with urllib.request.urlopen(req, timeout=30) as r, open(path, "wb") as f:
                shutil.copyfileobj(r, f)
            # the installer takes over; it closes this copy and replaces it. Drop PyInstaller's _PYI_* variables: the
            # installer would hand them to the new exe, which then takes itself for our child and refuses to start.
            subprocess.Popen([path], env={k: v for k, v in os.environ.items() if not k.startswith("_PYI_")})
            root.after(0, root.destroy)
        except Exception:
            root.after(0, lambda: (upd_btn.config(text="FAILED · RETRY", fg=FG, cursor="hand2"), setattr(upd_btn, "cmd", install_update)))
    threading.Thread(target=go, daemon=True).start()

def show_update():
    upd_label.config(text=f"v{latest['tag']} available")
    show(current)

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

current = main
def show(view):
    global current
    current = view
    for w in (main, settings_view, upd_row):
        w.pack_forget()
    view.pack(fill="x")
    if view is main and latest:
        upd_row.pack(side="bottom", fill="x")

# ---------- hotkey ----------
capturing = False
was_down = False

def show_hotkey():
    key_label.config(text=hotkey_name(), fg=FG)
    key_line.config(text=hotkey_name())
    hint.config(text="arms the clicker from any app")

def start_capture():
    global capturing, was_down
    capturing, was_down = True, True
    key_label.config(text="press a key, combo or mouse button", fg=MUTED)
    hint.config(text="Esc cancels")

def toggle():
    global running, locked
    running, locked = not running, False
    show_state()

def show_state():
    state.config(text=("LOCKED" if locked else "ARMED") if running else "OFF", fg=FG if running else MUTED, bg=ACCENT if running else INK2)

ctrl_was_down = False
def poll_lock():  # a Ctrl tap while armed toggles lock; skipped when Ctrl is part of the hotkey, that press means arm/disarm
    global locked, ctrl_was_down
    is_down = bool(down(0x11))
    if is_down and not ctrl_was_down and running and 0x11 not in settings["mods"]:
        locked = not locked
        show_state()
    ctrl_was_down = is_down

def poll():
    global capturing, was_down
    if capturing:
        if down(0x1B):
            capturing = False
            show_hotkey()
        else:
            for vk in range(0x02, 0xFF):
                if vk not in NOT_A_TRIGGER and down(vk):
                    settings.update(vk=vk, mods=[m for m in MODS if down(m)])
                    save_settings()
                    capturing = False
                    show_hotkey()
                    break
    else:
        is_down = down(settings["vk"]) and all(down(m) for m in settings["mods"])
        if is_down and not was_down:
            toggle()
        was_down = is_down
        poll_lock()
    root.after(10, poll)

def update_rate():
    global clicks
    value.config(text=str(clicks * 2))
    clicks = 0
    root.after(500, update_rate)

show_hotkey()
show(main)
threading.Thread(target=clicker, daemon=True).start()
threading.Thread(target=check_update, daemon=True).start()
poll()
update_rate()
root.mainloop()
