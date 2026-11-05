# AutoClicker: press the hotkey (default F6) anywhere to arm it; while armed, holding the left mouse button
# fires left-clicks (1-40 per second, set in Settings) until you let go. Tap Ctrl while armed to lock the clicking
# on without holding the button; tap Ctrl again (or disarm) to stop. Close the window to quit.
# Styled to Jadan Duffin's design system (ink ground, one orange, Schibsted Grotesk + JetBrains Mono).
import ctypes, json, os, shutil, subprocess, sys, threading, time, tkinter as tk, urllib.request, webbrowser
from ctypes import wintypes
from PIL import Image, ImageDraw, ImageFilter, ImageTk

VERSION = os.environ.get("AUTOCLICKER_VERSION", "1.9")  # build.ps1 reads this number; the env override only lets the update test pretend to be old
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
ICON = os.path.join(HERE, "AutoClicker.ico")  # title bar, taskbar and the header mark
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

# low-level keyboard hook for the Ctrl lock: tk's 10 ms poll really runs every 16-33 ms on Windows, so a quick tap could fall between polls
class KBDLL(ctypes.Structure):
    _fields_ = [("vkCode", wintypes.DWORD), ("scanCode", wintypes.DWORD), ("flags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]
ctrl_tapped = False  # set on a Ctrl press edge, consumed by poll_lock
ctrl_down = False

@HOOKPROC
def key_hook(code, wparam, lparam):
    global ctrl_tapped, ctrl_down
    if code >= 0 and ctypes.cast(lparam, ctypes.POINTER(KBDLL)).contents.vkCode in (0x11, 0xA2, 0xA3):  # Ctrl, left, right
        is_down = wparam in (0x100, 0x104)  # WM_KEYDOWN / WM_SYSKEYDOWN; held keys repeat these, so only the first counts
        if is_down and not ctrl_down:
            ctrl_tapped = True
        ctrl_down = is_down
    return user32.CallNextHookEx(None, code, wparam, lparam)
khook = user32.SetWindowsHookExW(13, key_hook, kernel32.GetModuleHandleW(None), 0)  # WH_KEYBOARD_LL

# per-monitor: we draw at each monitor's real pixel size, so Windows never stretches the window (a 150% monitor showed it blurred)
user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
root = tk.Tk()
root.title("AutoClicker")
root.configure(bg=INK)
root.attributes("-topmost", True)
root.resizable(False, False)
if os.path.exists(ICON):
    root.iconbitmap(ICON)
root.update()
ctypes.windll.dwmapi.DwmSetWindowAttribute(user32.GetParent(root.winfo_id()), 20, ctypes.byref(ctypes.c_int(1)), 4)  # dark title bar

U = 1.0  # screen pixels per design pixel: 1 on a 100% monitor, 1.5 on a 150% one. build() sets it; every size below goes through px() or face()
def px(n):
    return round(n * U)
def face(family, pt):  # a font at pt points of the design; negative size = pixels, since tk's own point scaling only knows the main monitor
    return (family, -round(pt * 4 / 3 * U))

def label(parent, text, **kw):
    kw = {"font": face(MONO, 9), "fg": MUTED2, "bg": INK, "anchor": "w", **kw}
    return tk.Label(parent, text=text, **kw)

def rule(parent):  # hairline between sections
    tk.Frame(parent, bg=LINE, height=max(1, int(U))).pack(fill="x", pady=(px(20), px(12)))

SS = 4  # curves are painted 4x too large, then shrunk: the canvas draws its own ovals and arcs with stepped edges
SOFT = 0.35  # edge softness in design pixels, a blur before shrinking: 0 is hard-edged, 0.7 looks like Windows stretching the window on a 150% monitor
def smooth(w, h, paint):  # paint(draw, s) draws the shape at scale s on the ink ground; returns a w x h tk image with soft edges
    im = Image.new("RGB", (w * SS, h * SS), INK)
    paint(ImageDraw.Draw(im), SS)
    return ImageTk.PhotoImage(im.filter(ImageFilter.GaussianBlur(SOFT * U * SS)).resize((w, h), Image.BOX))

class Button(tk.Canvas):  # the design system's pill button: raised fill, hairline (or orange) stroke; tk.Label cannot round corners
    def __init__(self, parent, text, cmd, fg=MUTED, bg=INK2, outline=LINE):
        super().__init__(parent, bg=parent.cget("bg"), highlightthickness=0, cursor="hand2")
        self.text, self.cmd, self.fg, self.fill, self.outline, self.stroke = text, cmd, fg, bg, outline, outline
        self.bind("<Button-1>", lambda _: self.cmd and self.cmd())
        self.bind("<Enter>", lambda _: self.hover(ACCENT))  # the stroke goes orange under the pointer
        self.bind("<Leave>", lambda _: self.hover(self.outline))
        self.draw()
    def hover(self, color):
        self.stroke = color
        self.draw()
    def config(self, **kw):  # same calls the old Label took: text / fg / cursor
        self.text, self.fg = kw.pop("text", self.text), kw.pop("fg", self.fg)
        tk.Canvas.config(self, **kw)
        self.draw()
    def draw(self):
        self.delete("all")
        f = face(MONO, 9)
        h = px(26); w = int(self.tk.call("font", "measure", f, self.text)) + px(30)
        tk.Canvas.config(self, width=w, height=h)
        m = round(SS * U)  # one design pixel in the oversized drawing: the margin round the pill, and the stroke's width
        self.img = smooth(w, h, lambda d, s: d.rounded_rectangle((m, m, w * s - m - 1, h * s - m - 1), radius=h * s, fill=self.fill, outline=self.stroke, width=m))
        self.create_image(0, 0, image=self.img, anchor="nw")
        self.create_text(w / 2, h / 2, text=self.text, font=f, fill=self.fg)
button = Button

def open_repo():
    webbrowser.open(REPO_URL)

images = []  # tk drops an image that nothing in Python references, so keep every one
def header(parent, name, right_text, right_cmd):
    head = tk.Frame(parent, bg=INK)
    head.pack(fill="x")
    try:
        im = Image.open(ICON)  # Pillow opens the .ico at its largest size
        m = im.width * 0.14  # trim the ink tile's margin: it is the same colour as the ground, and the hand should fill the mark
        images.append(ImageTk.PhotoImage(im.crop((m, m, im.width - m, im.height - m)).resize((px(28), px(28)), Image.LANCZOS)))
        tk.Label(head, image=images[-1], bg=INK).pack(side="left", padx=(0, px(10)))
    except Exception:
        pass  # shortcut: no icon file on this machine, skip the mark
    label(head, name, font=face(SANS, 14), fg=FG).pack(side="left")  # the view's title: brand display face, sentence case
    button(head, right_text, right_cmd).pack(side="right")

def mix(a, b, t):  # blend two hex colours: the glow is painted as opaque rings on the ink ground
    return "#%02x%02x%02x" % tuple(round(int(a[i:i + 2], 16) * (1 - t) + int(b[i:i + 2], 16) * t) for i in (1, 3, 5))

class StateBar(tk.Canvas):  # the one orange fill per view, styled like the design system's primary button: a pill with an orange-tinted glow
    GLOW, H = 20, 60  # design pixels: glow reach (centred on the pill: offset down, it read as a smeared drop shadow), pill height
    def __init__(self, parent):
        g, h = px(self.GLOW), px(self.H)
        super().__init__(parent, width=100, height=h + 2 * g, bg=INK, highlightthickness=0)
        self.g, self.h, self.text, self.on = g, h, "OFF", False
        self.bind("<Configure>", lambda _: self.draw())
    def set(self, text, on):
        self.text, self.on = text, on
        self.draw()
    def draw(self):
        self.delete("all")
        g, h, w = self.g, self.h, self.winfo_width()
        if w < 2 * g + h:
            return  # not laid out yet: too narrow to hold a pill
        def paint(d, s):
            def pill(k, color):  # the pill grown by k on every side
                d.rounded_rectangle(((g - k) * s, (g - k) * s, (w - g + k) * s - 1, (g + h + k) * s - 1), radius=(h / 2 + k) * s, fill=color)
            if self.on:
                for k in range(g, 0, -1):  # faint outer ring first, brightening towards the pill: peaks near 24% orange
                    pill(k, mix(INK, ACCENT, 0.24 * (1 - k / g) ** 2))
            pill(0, ACCENT if self.on else INK2)
        self.img = smooth(w, h + 2 * g, paint)
        self.create_image(0, 0, image=self.img, anchor="nw")
        self.create_text(w / 2, g + h / 2, text=self.text, font=face(SANS, 22), fill=INK if self.on else MUTED)  # ink text on orange

def set_cps(v):
    settings["cps"] = int(float(v))
    speed_label.config(text=f"{settings['cps']} / SEC")
    save_settings()

class Slider(tk.Canvas):  # hairline track with a knob; tk.Scale cannot colour its knob apart from its background
    def __init__(self, parent, lo, hi, cmd):
        super().__init__(parent, width=100, height=px(24), bg=INK, highlightthickness=0, cursor="hand2")  # stretches to the view; keeps both views the same width
        self.lo, self.hi, self.cmd, self.v = lo, hi, cmd, lo
        k, m = px(16), round(SS * U)
        self.knob = smooth(k, k, lambda d, s: d.ellipse((m, m, k * s - m - 1, k * s - m - 1), fill=FG, outline=INK, width=m))
        self.bind("<Configure>", lambda _: self.draw())
        for ev in ("<Button-1>", "<B1-Motion>"):
            self.bind(ev, self.drag)
    def set(self, v):
        self.v = min(self.hi, max(self.lo, int(v)))
        self.draw()
        self.cmd(self.v)
    def drag(self, e):
        self.set(round(self.lo + (e.x - px(8)) / (self.winfo_width() - px(16)) * (self.hi - self.lo)))
    def draw(self):
        self.delete("all")
        e, y = px(8), px(12)
        w = self.winfo_width() - 2 * e
        x = e + (self.v - self.lo) / (self.hi - self.lo) * w
        self.create_line(e, y, e + w, y, fill=LINE, width=px(2))
        self.create_line(e, y, x, y, fill=FG, width=px(2))
        self.create_image(x, y, image=self.knob)

latest = {}  # newer release found by check_update: tag + installer url
on_settings = False  # which view is up; build() puts the same one back

def build():  # makes every widget at the scale of the monitor the window is on; run again when it lands on a monitor with another scale
    global U, capturing, main, state, value, key_line, settings_view, key_label, set_btn, hint, speed_label, slider, upd_row, upd_label, upd_btn
    U = user32.GetDpiForWindow(user32.GetParent(root.winfo_id())) / 96
    capturing = False
    for w in root.winfo_children():
        w.destroy()
    images.clear()

    # ---------- main view ----------
    main = tk.Frame(root, bg=INK, padx=px(24), pady=px(20))
    header(main, "AutoClicker", "SETTINGS", lambda: show(settings_view))
    state = StateBar(main)
    state.pack(fill="x", pady=(px(22), 0))
    value = tk.Label(main, text="0", font=face(SANS, 48), fg=FG, bg=INK, anchor="w")
    value.pack(fill="x", pady=(px(16), 0))
    label(main, "CLICKS / SEC").pack(fill="x")
    rule(main)
    label(main, "HOTKEY").pack(fill="x")
    key_line = label(main, "", fg=FG, font=face(MONO, 11))
    key_line.pack(fill="x", pady=(px(4), 0))
    label(main, "arms it · then hold left mouse to click").pack(fill="x", pady=(px(4), 0))
    label(main, "Ctrl locks the clicking on · Ctrl again stops").pack(fill="x")

    # ---------- settings view ----------
    settings_view = tk.Frame(root, bg=INK, padx=px(24), pady=px(20))
    header(settings_view, "Settings", "BACK", lambda: show(main))
    label(settings_view, "HOTKEY").pack(fill="x", pady=(px(22), 0))
    row = tk.Frame(settings_view, bg=INK)
    row.pack(fill="x", pady=(px(4), 0))
    key_label = label(row, "", fg=FG, font=face(MONO, 11))
    key_label.pack(side="left", fill="x", expand=True)
    set_btn = button(row, "SET", lambda: start_capture())
    set_btn.pack(side="right")
    hint = label(settings_view, "arms the clicker from any app")
    hint.pack(fill="x", pady=(px(4), 0))
    rule(settings_view)
    speed_row = tk.Frame(settings_view, bg=INK)
    speed_row.pack(fill="x")
    label(speed_row, "SPEED").pack(side="left")
    speed_label = label(speed_row, "", fg=FG, anchor="e")
    speed_label.pack(side="right")
    slider = Slider(settings_view, 1, MAX_CPS, set_cps)
    slider.pack(fill="x", pady=(px(8), 0))
    slider.set(settings["cps"])
    label(settings_view, f"clicks per second · max {MAX_CPS}").pack(fill="x", pady=(px(4), 0))
    rule(settings_view)
    src_row = tk.Frame(settings_view, bg=INK)
    src_row.pack(fill="x")
    label(src_row, f"v{VERSION} · open source").pack(side="left", padx=(0, px(16)))
    button(src_row, "VIEW SOURCE", open_repo).pack(side="right")

    root.update_idletasks()  # both views get the larger of their two sizes, so the window never jumps when switching
    W, H = (max(v.winfo_reqwidth() for v in (main, settings_view)), max(v.winfo_reqheight() for v in (main, settings_view)))
    for v in (main, settings_view):
        v.config(width=W, height=H)
        v.pack_propagate(False)

    # ---------- update stripe (bottom of main view, hidden until a newer release exists) ----------
    upd_row = tk.Frame(root, bg=ACCENT, padx=px(24), pady=px(12))
    upd_label = tk.Label(upd_row, text=f"v{latest['tag']} available" if latest else "", font=face(MONO, 9), fg=FG, bg=ACCENT, anchor="w")
    upd_label.pack(side="left", fill="x", expand=True)
    upd_btn = button(upd_row, "UPDATE", lambda: install_update(), fg=FG, bg=INK)
    upd_btn.pack(side="right")

    show_hotkey()
    show_state()
    show(settings_view if on_settings else main)

pending = None
def follow_monitor(e):  # the window moved or changed size: once it comes to rest, check which monitor it is on
    global pending
    if e.widget is root:
        if pending:
            root.after_cancel(pending)
        pending = root.after(250, rescale)

def rescale():  # redraw at the new monitor's scale, if it changed
    if user32.GetDpiForWindow(user32.GetParent(root.winfo_id())) / 96 != U:
        cx = root.winfo_x() + root.winfo_width() / 2
        build()
        root.update_idletasks()
        # grow or shrink about the centre: from the corner, the new size could tip most of the window back onto the old monitor and flip the scale again
        root.geometry(f"+{round(cx - root.winfo_reqwidth() / 2)}+{root.winfo_y()}")

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
    show(settings_view if on_settings else main)

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

def show(view):
    global on_settings
    on_settings = view is settings_view
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
    state.set(("LOCKED" if locked else "ARMED") if running else "OFF", running)

def poll_lock():  # a Ctrl tap while armed toggles lock; skipped when Ctrl is part of the hotkey, that press means arm/disarm
    global locked, ctrl_tapped
    if ctrl_tapped and running and 0x11 not in settings["mods"]:
        locked = not locked
        show_state()
    ctrl_tapped = False

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

build()
root.bind("<Configure>", follow_monitor)
threading.Thread(target=clicker, daemon=True).start()
threading.Thread(target=check_update, daemon=True).start()
poll()
update_rate()
root.mainloop()
