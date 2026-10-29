from __future__ import annotations

import ctypes
import json
import math
import os
import struct
import subprocess
import sys
import tempfile
import time
import tkinter as tk
from ctypes import wintypes
from tkinter import filedialog, messagebox

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VERSION = "v0.1"
APP_TITLE = "Let it Die Execute"

BG_COLOR = "#1a1d21"
ENTRY_BG = "#2a2e34"
ENTRY_BD = "#6a7078"
TEXT_FG = "#e6e8eb"
BTN_BG = "#d4d6d9"
BTN_FG = "#111111"
BTN_ACTIVE = "#b8bcc2"
BTN_RED = "#6e3030"
BTN_RED_FG = "#f0f0f0"

ASSET_BG_CANDIDATES = (
    "UI background.webp",
    "UI background.png",
    "Tower_of_Barbs_Painting_ready.png",
)
ASSET_CURSOR_CANDIDATES = (
    "let it die cursor.webp",
    "let it die cursor.png",
)
ASSET_ICON_CANDIDATES = (
    "uncle glasses ready.webp",
    "uncle glasses ready.png",
    "Lidico.webp",
)
ASSET_ICO_CANDIDATES = (
    "Lidico.ico",
    "lidico.ico",
)

DEFAULT_HOTKEY = ""   # empty = no shortcut until the user sets one
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def app_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def bundle_dir() -> str:
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", app_dir())
    return app_dir()


def find_asset(*names: str) -> str:
    roots = []
    for base in (bundle_dir(), app_dir(), os.getcwd()):
        if not base:
            continue
        roots.append(base)
        roots.append(os.path.join(base, "UI_Assets"))
    seen = set()
    for root in roots:
        norm = os.path.normpath(root)
        if norm in seen:
            continue
        seen.add(norm)
        for name in names:
            path = os.path.join(root, name)
            if os.path.isfile(path):
                return path
    return ""


def settings_path() -> str:
    return os.path.join(app_dir(), "settings.ini")


def exes_path() -> str:
    return os.path.join(app_dir(), "EXEs.json")


def lock_path() -> str:
    return os.path.join(app_dir(), "execute.lock")


# ---------------------------------------------------------------------------
# Images / cursor / chrome
# ---------------------------------------------------------------------------

def load_photo(path: str, size: tuple[int, int] | None = None):
    if not path or not os.path.isfile(path):
        return None
    try:
        from PIL import Image, ImageTk

        img = Image.open(path).convert("RGBA")
        if size:
            img = img.resize(size, Image.Resampling.LANCZOS)
        return ImageTk.PhotoImage(img)
    except Exception:
        try:
            return tk.PhotoImage(file=path)
        except Exception:
            return None


def image_to_cur(src_path: str, cur_path: str, size: int = 32) -> bool:
    """Convert png/webp to a .cur so Windows can use it as a cursor."""
    try:
        from PIL import Image

        img = Image.open(src_path).convert("RGBA")
        box = img.getbbox()
        if box:
            img = img.crop(box)
        img.thumbnail((size, size), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        canvas.paste(img, (0, 0))

        hx = hy = 0
        found = False
        for y in range(size):
            for x in range(size):
                if canvas.getpixel((x, y))[3] > 40:
                    hx, hy = x, y
                    found = True
                    break
            if found:
                break

        xor = bytearray()
        for y in range(size - 1, -1, -1):
            for x in range(size):
                r, g, b, a = canvas.getpixel((x, y))
                xor += bytes((b, g, r, a))

        row_and = ((size + 31) // 32) * 4
        and_mask = bytearray(row_and * size)
        for y in range(size):
            dest_y = size - 1 - y
            for x in range(size):
                if canvas.getpixel((x, y))[3] < 128:
                    and_mask[dest_y * row_and + (x >> 3)] |= 0x80 >> (x & 7)

        image = struct.pack("<IiiHHIIiiII", 40, size, size * 2, 1, 32, 0, len(xor), 0, 0, 0, 0)
        image += bytes(xor) + bytes(and_mask)
        header = struct.pack("<HHH", 0, 2, 1)
        entry = struct.pack("<BBBBHHII", size, size, 0, 0, hx, hy, len(image), 22)
        with open(cur_path, "wb") as fh:
            fh.write(header + entry + image)
        return True
    except Exception:
        return False


def image_to_ico(src_path: str, ico_path: str) -> bool:
    try:
        from PIL import Image

        Image.open(src_path).convert("RGBA").save(
            ico_path, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (256, 256)]
        )
        return True
    except Exception:
        return False


def apply_cursor(widget: tk.Misc, cur_path: str) -> None:
    if not cur_path or not os.path.isfile(cur_path):
        return
    path = os.path.abspath(cur_path)
    if sys.platform == "win32":
        try:
            user32 = ctypes.windll.user32
            user32.LoadCursorFromFileW.restype = ctypes.c_void_p
            handle = user32.LoadCursorFromFileW(path)
            if handle:
                user32.SetCursor.argtypes = [ctypes.c_void_p]
                hwnd = user32.GetParent(widget.winfo_id()) or widget.winfo_id()
                if hasattr(user32, "SetClassLongPtrW"):
                    user32.SetClassLongPtrW(hwnd, -12, handle)
                else:
                    user32.SetClassLongW(hwnd, -12, handle)
        except Exception:
            pass
    for spec in ("@" + path, "@" + path.replace("\\", "/")):
        try:
            widget.configure(cursor=spec)
            break
        except Exception:
            continue
    for child in widget.winfo_children():
        apply_cursor(child, cur_path)


def color_titlebar(win: tk.Misc) -> None:
    if sys.platform != "win32":
        return
    try:
        win.update_idletasks()
        user32 = ctypes.windll.user32
        hwnd = user32.GetParent(win.winfo_id()) or win.winfo_id()
        color = ctypes.c_int(0)
        dark = ctypes.c_int(1)
        dwm = ctypes.windll.dwmapi
        dwm.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(dark), 4)
        dwm.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(color), 4)
        dwm.DwmSetWindowAttribute(hwnd, 34, ctypes.byref(color), 4)
    except Exception:
        pass


def set_app_id() -> None:
    """Own AppUserModelID so the taskbar uses this window's icon, not Python's."""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Grimfuldev.LID.Execute")
    except Exception:
        pass


def stable_icon(swap: str = "") -> str:
    """Return a real .ico that will still exist after Explorer refreshes.
    Copies/converts into app_dir/app_icon.ico so the path never moves.
    """
    dest = os.path.join(app_dir(), "app_icon.ico")
    src = (swap or "").strip()
    if not (src and os.path.isfile(src)):
        src = find_asset(*ASSET_ICO_CANDIDATES) or find_asset(*ASSET_ICON_CANDIDATES)
    if not src or not os.path.isfile(src):
        return dest if os.path.isfile(dest) else ""
    try:
        if src.lower().endswith(".ico"):
            if os.path.abspath(src) != os.path.abspath(dest):
                import shutil
                shutil.copyfile(src, dest)
            return dest
        if image_to_ico(src, dest):
            return dest
    except Exception:
        pass
    return src if src.lower().endswith(".ico") else ""


def apply_window_chrome(win: tk.Misc, swap_ico: str = "") -> None:
    try:
        win.tk_setPalette(background=BG_COLOR, foreground=TEXT_FG)
    except Exception:
        pass

    ico = stable_icon(swap_ico)
    photo = load_photo(ico, (32, 32)) if ico else None
    if not photo:
        icon_src = find_asset(*ASSET_ICON_CANDIDATES)
        photo = load_photo(icon_src, (32, 32)) if icon_src else None
    if photo:
        try:
            win.iconphoto(True, photo)
            win._icon_photo = photo
        except Exception:
            pass
    if ico and os.path.isfile(ico):
        try:
            win.iconbitmap(ico)
        except Exception:
            pass
        # Also push the icon to the taskbar button (big and small)
        if sys.platform == "win32":
            try:
                user32 = ctypes.windll.user32
                user32.LoadImageW.restype = ctypes.c_void_p
                user32.LoadImageW.argtypes = [
                    ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint,
                    ctypes.c_int, ctypes.c_int, ctypes.c_uint,
                ]
                hwnd = user32.GetParent(win.winfo_id()) or win.winfo_id()
                big = user32.LoadImageW(None, ico, 1, 32, 32, 0x0010)
                small = user32.LoadImageW(None, ico, 1, 16, 16, 0x0010)
                if big:
                    user32.SendMessageW(hwnd, 0x0080, 1, big)   # ICON_BIG
                if small:
                    user32.SendMessageW(hwnd, 0x0080, 0, small)  # ICON_SMALL
            except Exception:
                pass

    color_titlebar(win)

    cur_src = find_asset(*ASSET_CURSOR_CANDIDATES)
    if cur_src:
        cur = os.path.join(tempfile.gettempdir(), "lid_execute.cur")
        if image_to_cur(cur_src, cur):
            apply_cursor(win, cur)
            win.after(80, lambda: apply_cursor(win, cur))


# ---------------------------------------------------------------------------
# Settings / JSON
# ---------------------------------------------------------------------------

def load_settings() -> dict:
    data = {
        "hotkey": DEFAULT_HOTKEY,
        "start_minimized": False,
        "grace_time": 3,
        "disable_shortcut": False,
        "wait_between_launches": 3,
        "swap_app_thumbnail": "",
        "disable_self_launch": False,
        "self_close_after_all_launch": False,
        "hide_exe_path_in_ui": False,
    }
    path = settings_path()
    if not os.path.isfile(path):
        return data
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key, value = key.strip().lower().replace(" ", "_"), value.strip()
                if key == "hotkey":
                    data["hotkey"] = value[0] if value else ""
                elif key == "start_minimized":
                    data["start_minimized"] = value.lower() in ("1", "true", "yes")
                elif key == "grace_time":
                    try:
                        data["grace_time"] = max(0, int(value))
                    except ValueError:
                        pass
                elif key == "disable_shortcut":
                    data["disable_shortcut"] = value.lower() in ("1", "true", "yes")
                elif key == "wait_between_launches":
                    data["wait_between_launches"] = normalize_wait(value)
                elif key == "swap_app_thumbnail":
                    data["swap_app_thumbnail"] = clean_path(value)
                elif key == "disable_self_launch":
                    data["disable_self_launch"] = value.lower() in ("1", "true", "yes")
                elif key == "self_close_after_all_launch":
                    data["self_close_after_all_launch"] = value.lower() in ("1", "true", "yes")
                elif key == "hide_exe_path_in_ui":
                    data["hide_exe_path_in_ui"] = value.lower() in ("1", "true", "yes")
    except OSError:
        pass
    return data


def clean_path(value: str) -> str:
    """Strip quotes, leading/trailing space, and normalize slashes."""
    text = (value or "").strip().strip('"').strip("'").strip()
    if not text:
        return ""
    text = text.replace("/", "\\")
    while "\\\\" in text:
        text = text.replace("\\\\", "\\")
    return text


def normalize_wait(value) -> int:
    """Seconds between launches. Decimals round up. Anything under 1 becomes 1."""
    try:
        n = float(str(value).strip())
    except (TypeError, ValueError):
        return 3
    if n < 0:
        return 1
    return max(1, math.ceil(n))


def save_settings(hotkey: str, start_minimized: bool, grace_time: int = 3,
                  disable_shortcut: bool = False, wait_between_launches: int = 3,
                  swap_app_thumbnail: str = "", disable_self_launch: bool = False,
                  self_close_after_all_launch: bool = False,
                  hide_exe_path_in_ui: bool = False) -> None:
    path = settings_path()
    lines = [
        "# Let it Die Execute settings",
        "# hotkey = one character that hides/shows the window (empty = no shortcut)",
        "# start_minimized = true  -> start with the window hidden (ignored if hotkey is empty)",
        "# grace_time = seconds of countdown before the stack launches (0 = skip)",
        "# disable_shortcut = true  -> hide/show hotkey does nothing",
        "# wait_between_launches = seconds between each exe (min 1, decimals round up)",
        "# Swap_App_Thumbnail = full path to an .ico to use instead of the default icon",
        "# disable_self_launch = true  -> do not auto-launch the stack on start",
        "# Self_close_after_ALL_launch = true  -> exit after the startup stack finishes",
        "# Hide_exe_path_in_UI = true  -> show only the exe name in the list",
        f"hotkey={hotkey or DEFAULT_HOTKEY}",
        f"start_minimized={'true' if start_minimized else 'false'}",
        f"grace_time={int(grace_time)}",
        f"disable_shortcut={'true' if disable_shortcut else 'false'}",
        f"wait_between_launches={int(wait_between_launches)}",
        f"Swap_App_Thumbnail={swap_app_thumbnail}",
        f"disable_self_launch={'true' if disable_self_launch else 'false'}",
        f"Self_close_after_ALL_launch={'true' if self_close_after_all_launch else 'false'}",
        f"Hide_exe_path_in_UI={'true' if hide_exe_path_in_ui else 'false'}",
    ]
    try:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    except OSError:
        pass


def load_exes() -> list[dict]:
    path = exes_path()
    if not os.path.isfile(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, list):
            return []
        out = []
        for item in data:
            if not isinstance(item, dict):
                continue
            out.append({
                "path": str(item.get("path") or ""),
                "active": bool(item.get("active", True)),
                "game": bool(item.get("game", False)),
            })
        return out
    except (OSError, json.JSONDecodeError):
        return []


def save_exes(items: list[dict]) -> None:
    path = exes_path()
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(items, fh, indent=2)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Registered hotkey. Windows sends the key to this window, so Explorer
# never sees an unhandled key and does not beep. Works while hidden.
# ---------------------------------------------------------------------------

_HOTKEY_ID = 0xE01
_HOTKEY_PRESSED = False
_WNDPROC = None
_OLD_WNDPROC = None
_HOTKEY_HWND = None

WM_HOTKEY = 0x0312
GWL_WNDPROC = -4


def hotkey_text(hotkey: str) -> str:
    return f"Hide UI: {hotkey}" if hotkey else "Hide UI: none"


def _vk_from_char(ch: str) -> int:
    if not ch:
        return 0  # no shortcut
    ch = ch[0]
    if ch == "-":
        return 0xBD
    if ch == "=":
        return 0xBB
    try:
        return ctypes.windll.user32.VkKeyScanW(ord(ch)) & 0xFF
    except Exception:
        return 0xBD


def _window_hwnd(win: tk.Misc) -> int:
    try:
        win.update_idletasks()
    except Exception:
        pass
    user32 = ctypes.windll.user32
    hwnd = user32.GetParent(win.winfo_id()) or win.winfo_id()
    return int(hwnd)


def install_hook(vk: int, win: tk.Misc | None = None) -> None:
    """Register the key with Windows and catch WM_HOTKEY on the Tk window."""
    global _WNDPROC, _OLD_WNDPROC, _HOTKEY_HWND
    uninstall_hook()
    if win is None or not vk:
        return
    hwnd = _window_hwnd(win)
    if not hwnd:
        return
    _HOTKEY_HWND = hwnd
    user32 = ctypes.windll.user32

    if _OLD_WNDPROC is None:
        LRESULT = ctypes.c_ssize_t
        WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

        def _wndproc(h, msg, wparam, lparam):
            global _HOTKEY_PRESSED
            if msg == WM_HOTKEY and wparam == _HOTKEY_ID:
                _HOTKEY_PRESSED = True
                return 0
            if _OLD_WNDPROC:
                return user32.CallWindowProcW(_OLD_WNDPROC, h, msg, wparam, lparam)
            return 0

        _WNDPROC = WNDPROC(_wndproc)
        user32.SetWindowLongPtrW.restype = ctypes.c_void_p
        user32.CallWindowProcW.restype = LRESULT
        user32.CallWindowProcW.argtypes = [ctypes.c_void_p, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        _OLD_WNDPROC = user32.SetWindowLongPtrW(hwnd, GWL_WNDPROC, _WNDPROC)

    ok = user32.RegisterHotKey(hwnd, _HOTKEY_ID, 0, vk)
    if not ok:
        user32.RegisterHotKey(hwnd, _HOTKEY_ID, 0x4000, vk)


def uninstall_hook() -> None:
    try:
        if _HOTKEY_HWND:
            ctypes.windll.user32.UnregisterHotKey(_HOTKEY_HWND, _HOTKEY_ID)
    except Exception:
        pass


def consume_hotkey() -> bool:
    global _HOTKEY_PRESSED
    if _HOTKEY_PRESSED:
        _HOTKEY_PRESSED = False
        return True
    return False


# ---------------------------------------------------------------------------
# Lock
# ---------------------------------------------------------------------------

def write_lock() -> None:
    try:
        with open(lock_path(), "w", encoding="utf-8") as fh:
            fh.write(str(os.getpid()))
    except OSError:
        pass


def clear_lock() -> None:
    """Remove the lock only if it still belongs to this process."""
    path = lock_path()
    try:
        if not os.path.isfile(path):
            return
        owner = int(open(path, "r", encoding="utf-8").read().strip() or "0")
        if owner == os.getpid():
            os.remove(path)
    except Exception:
        pass


def close_previous() -> None:
    """Close an already-running launcher. Does not touch any other program."""
    path = lock_path()
    if not os.path.isfile(path):
        return
    try:
        old = int(open(path, "r", encoding="utf-8").read().strip() or "0")
    except Exception:
        return
    if old <= 0 or old == os.getpid():
        return
    h = ctypes.windll.kernel32.OpenProcess(0x1000, False, old)
    if not h:
        return
    ctypes.windll.kernel32.CloseHandle(h)
    try:
        subprocess.run(
            ["taskkill", "/PID", str(old), "/F"],
            creationflags=NO_WINDOW,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return
    # wait until that process is gone so its cleanup cannot delete our lock
    for _ in range(20):
        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, old)
        if not h:
            break
        ctypes.windll.kernel32.CloseHandle(h)
        time.sleep(0.1)


# ---------------------------------------------------------------------------
# Launch / kill
# ---------------------------------------------------------------------------

def game_from_steam(steam_exe: str) -> str:
    """steam.exe folder -> steamapps\\common\\LET IT DIE\\Binaries\\Win64\\BrgGame-Steam.exe"""
    if not steam_exe or not os.path.isfile(steam_exe):
        return ""
    steam_dir = os.path.dirname(os.path.abspath(steam_exe))
    game = os.path.join(
        steam_dir, "steamapps", "common", "LET IT DIE",
        "Binaries", "Win64", "BrgGame-Steam.exe",
    )
    return game if os.path.isfile(game) else ""


def launch_exe(path: str) -> bool:
    """Launch path. Return False if it was already running or could not start."""
    if not path or not os.path.isfile(path):
        return False
    image = os.path.basename(path)
    if process_running(image):
        return False
    try:
        subprocess.Popen([path], cwd=os.path.dirname(path) or None, close_fds=True)
        return True
    except Exception:
        return False


def process_pids(image: str) -> list[int]:
    """PIDs of an exe. Does not use IMAGENAME eq, which only matches 25 characters."""
    want = (image or "").strip().lower()
    if not want:
        return []
    try:
        out = subprocess.check_output(
            ["tasklist", "/FO", "CSV", "/NH"],
            creationflags=NO_WINDOW,
            stderr=subprocess.DEVNULL,
            text=True,
            errors="ignore",
        )
    except Exception:
        return []
    pids = []
    for line in out.splitlines():
        line = line.strip()
        if not line or not line.startswith('"'):
            continue
        parts = [p.strip().strip('"') for p in line.split('","')]
        if len(parts) < 2:
            continue
        if parts[0].lower() == want and parts[1].isdigit():
            pids.append(int(parts[1]))
    return pids


def process_running(image: str) -> bool:
    return bool(process_pids(image))


def kill_image(image: str) -> None:
    for pid in process_pids(image):
        try:
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/F"],
                creationflags=NO_WINDOW,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass


def launcher_target() -> str:
    return sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__)


def create_shortcut(swap: str = "") -> str:
    """Drop a desktop shortcut. Icon is the custom Swap_App_Thumbnail if set."""
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    if not os.path.isdir(desktop):
        desktop = os.path.join(os.environ.get("USERPROFILE", ""), "Desktop")
    lnk = os.path.join(desktop, "Let it Die Execute.lnk")
    work = app_dir()
    custom = clean_path(swap) or load_settings().get("swap_app_thumbnail", "")
    icon = ""
    if custom and os.path.isfile(custom):
        icon = stable_icon(custom) or custom
    else:
        icon = stable_icon("")
    q = lambda s: s.replace("'", "''")
    if getattr(sys, "frozen", False):
        target = sys.executable
        args = ""
    else:
        py = sys.executable
        pyw = py[:-4] + "w.exe" if py.lower().endswith("python.exe") else py
        if not os.path.isfile(pyw):
            pyw = py
        target = pyw
        args = f'"{os.path.abspath(__file__)}"'
    # Delete the old link so Explorer cannot keep its cached icon.
    try:
        if os.path.isfile(lnk):
            os.remove(lnk)
    except OSError:
        pass
    icon_line = f"$s.IconLocation = '{q(icon)},0'" if icon and os.path.isfile(icon) else ""
    args_line = f"$s.Arguments = '{q(args)}'" if args else ""
    ps = (
        "$w = New-Object -ComObject WScript.Shell\n"
        f"$s = $w.CreateShortcut('{q(lnk)}')\n"
        f"$s.TargetPath = '{q(target)}'\n"
        f"{args_line}\n"
        f"$s.WorkingDirectory = '{q(work)}'\n"
        "$s.WindowStyle = 1\n"
        f"{icon_line}\n"
        "$s.Save()\n"
        "Add-Type -Namespace Win32 -Name Native -MemberDefinition '"
        "[DllImport(\"shell32.dll\")] public static extern void SHChangeNotify(int e, uint f, System.IntPtr a, System.IntPtr b);'\n"
        "[Win32.Native]::SHChangeNotify(0x8000000, 0x1000, [IntPtr]::Zero, [IntPtr]::Zero)\n"
    )
    subprocess.check_call(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
        creationflags=NO_WINDOW,
    )
    return lnk


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

class Block(tk.Frame):
    def __init__(self, master, path: str, active: bool, on_delete, on_up, on_down,
                 game: bool = False, hide_path: bool = False):
        super().__init__(master, bg="#14171b" if game else BG_COLOR)
        self.on_delete = on_delete
        self.on_up = on_up
        self.on_down = on_down
        self.game = game
        self.hide_path = hide_path
        self.real_path = path or ""
        self.var_active = tk.BooleanVar(value=active)
        self.var_path = tk.StringVar(value=self._shown())
        bg = "#14171b" if game else BG_COLOR

        self.chk = tk.Checkbutton(
            self, variable=self.var_active, bg=bg, fg=TEXT_FG,
            activebackground=bg, activeforeground=TEXT_FG,
            selectcolor="#3a3e44",
        )
        self.chk.pack(side="left", padx=(4, 2))

        if game:
            tk.Label(
                self, text="steam.exe", bg=bg, fg=TEXT_FG,
                font=("Segoe UI", 9, "bold"),
            ).pack(side="left", padx=(0, 6))

        self.entry = tk.Entry(
            self, textvariable=self.var_path, state="readonly", width=60,
            bg=ENTRY_BG, fg=TEXT_FG, readonlybackground=ENTRY_BG,
            relief="solid", bd=1, font=("Segoe UI", 9),
        )
        self.entry.pack(side="left", fill="x", expand=True, padx=4, ipady=3)

        self.btn_browse = tk.Button(
            self, text="Browse", command=self.browse,
            bg=BTN_BG, fg=BTN_FG, activebackground=BTN_ACTIVE, activeforeground=BTN_FG,
            relief="solid", bd=1, font=("Segoe UI", 9), padx=8,
        )
        self.btn_browse.pack(side="left", padx=2)

        if not game:
            self.btn_up = tk.Button(
                self, text="▲", command=lambda: self.on_up(self),
                bg=BTN_BG, fg=BTN_FG, activebackground=BTN_ACTIVE, activeforeground=BTN_FG,
                relief="solid", bd=1, font=("Segoe UI", 9), width=3,
            )
            self.btn_up.pack(side="left", padx=1)

            self.btn_down = tk.Button(
                self, text="▼", command=lambda: self.on_down(self),
                bg=BTN_BG, fg=BTN_FG, activebackground=BTN_ACTIVE, activeforeground=BTN_FG,
                relief="solid", bd=1, font=("Segoe UI", 9), width=3,
            )
            self.btn_down.pack(side="left", padx=1)

        self.btn_del = tk.Button(
            self, text="✕", command=self.delete,
            bg=BTN_RED, fg=BTN_RED_FG, activebackground="#a02828",
            relief="solid", bd=1, font=("Segoe UI", 9, "bold"), width=3,
        )
        self.btn_del.pack(side="left", padx=(2, 4))

    def _shown(self) -> str:
        if not self.real_path:
            return ""
        if self.hide_path:
            return os.path.basename(self.real_path)
        return self.real_path

    def set_hide(self, hide: bool) -> None:
        self.hide_path = bool(hide)
        self.var_path.set(self._shown())

    def set_real(self, path: str) -> None:
        self.real_path = (path or "").replace("/", "\\")
        self.var_path.set(self._shown())

    def browse(self) -> None:
        if self.game:
            path = filedialog.askopenfilename(
                title="Select steam.exe",
                filetypes=[("steam.exe", "steam.exe"), ("Executable", "*.exe"), ("All files", "*.*")],
            )
            if not path:
                return
            game = game_from_steam(path)
            if game:
                self.set_real(game)
            else:
                self.set_real("")
                messagebox.showwarning(
                    APP_TITLE,
                    "Could not find BrgGame-Steam.exe next to that steam.exe.\n"
                    "Expected:\nsteamapps\\common\\LET IT DIE\\Binaries\\Win64\\BrgGame-Steam.exe",
                )
            return
        path = filedialog.askopenfilename(
            title="Select executable",
            filetypes=[("Executable", "*.exe"), ("All files", "*.*")],
        )
        if path and path.lower().endswith(".exe"):
            self.set_real(path)

    def delete(self) -> None:
        if self.game:
            self.set_real("")
            return
        self.on_delete(self)

    def data(self) -> dict:
        return {
            "path": self.real_path.strip(),
            "active": bool(self.var_active.get()),
            "game": self.game,
        }


class GraceSplash(tk.Toplevel):
    """Countdown before the stack launches.
    Button / X cancels the launch and continues into the program.
    """

    def __init__(self, master: tk.Tk, seconds: int, swap_ico: str = ""):
        super().__init__(master)
        self.title(f"{APP_TITLE} {VERSION}")
        self.geometry("640x360")
        self.resizable(False, False)
        self.result = "go"
        self.left = max(1, int(seconds))
        self._after = None
        self._count_id = None
        self._msg_id = None

        self.cv = tk.Canvas(self, width=640, height=360, highlightthickness=0, bd=0)
        self.cv.pack(fill="both", expand=True)

        bg_path = find_asset(*ASSET_BG_CANDIDATES)
        photo = load_photo(bg_path, (640, 360)) if bg_path else None
        if photo:
            self._bg = photo
            self.cv.create_image(0, 0, image=photo, anchor="nw")
        else:
            self.cv.configure(bg=BG_COLOR)

        # text drawn on the canvas — no solid panel behind it
        self._count_id = self.cv.create_text(
            320, 130, text=str(self.left), fill=TEXT_FG,
            font=("Segoe UI", 48, "bold"),
        )
        self._msg_id = self.cv.create_text(
            320, 200, text="Cancel launch stack and continue",
            fill=TEXT_FG, font=("Segoe UI", 13),
        )
        btn = tk.Button(
            self.cv, text="Cancel launch stack", command=self.cancel,
            bg=BTN_BG, fg=BTN_FG, activebackground=BTN_ACTIVE, activeforeground=BTN_FG,
            font=("Segoe UI", 10), relief="solid", bd=1, padx=16, pady=4,
        )
        self.cv.create_window(320, 250, window=btn)

        apply_window_chrome(self, swap_ico)
        # X does the same as the button: skip the stack, open the program
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        # transient shows the parent; skip it when the parent is meant to stay hidden
        if master.winfo_viewable():
            self.transient(master)
        self.grab_set()
        self.lift()
        self.focus_force()
        self._tick()

    def _tick(self) -> None:
        if self.left <= 0:
            self.result = "go"
            self.destroy()
            return
        self.cv.itemconfigure(self._count_id, text=str(self.left))
        self.left -= 1
        self._after = self.after(1000, self._tick)

    def cancel(self) -> None:
        if self._after:
            try:
                self.after_cancel(self._after)
            except Exception:
                pass
        self.result = "cancel"
        self.destroy()


class App:
    def __init__(self):
        self.settings = load_settings()
        self.hotkey = self.settings.get("hotkey") or DEFAULT_HOTKEY
        self.start_minimized_ini = bool(self.settings.get("start_minimized"))
        self.start_minimized = self.start_minimized_ini
        # no hotkey means there is no way to bring a hidden window back
        if self.start_minimized and not self.hotkey:
            self.start_minimized = False
            self._ignored_minimized = True
        else:
            self._ignored_minimized = False
        self.grace_time = int(self.settings.get("grace_time", 3))
        self.wait_between = normalize_wait(self.settings.get("wait_between_launches", 3))
        self.swap_ico = self.settings.get("swap_app_thumbnail", "")
        self.disable_self_launch = bool(self.settings.get("disable_self_launch"))
        self.disable_shortcut = bool(self.settings.get("disable_shortcut"))
        self.self_close_after_launch = bool(self.settings.get("self_close_after_all_launch"))
        self.hide_exe_path = bool(self.settings.get("hide_exe_path_in_ui"))
        self.ui_visible = not self.start_minimized
        self.blocks: list[Block] = []
        self.separators: list[tk.Frame] = []
        self.game_block: Block | None = None

        self.root = tk.Tk()
        self.root.title(f"{APP_TITLE} {VERSION}")
        self.root.geometry("1040x560")
        self.root.configure(bg=BG_COLOR)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        # hide before anything is drawn so start_minimized never flashes a window
        if self.start_minimized:
            self.root.withdraw()

        # background
        self.bg_label = None
        self.bg_photo = None
        bg_path = find_asset(*ASSET_BG_CANDIDATES)
        if bg_path:
            self.bg_photo = load_photo(bg_path, (1040, 560))
            if self.bg_photo:
                self.bg_label = tk.Label(self.root, image=self.bg_photo, bd=0)
                self.bg_label.place(x=0, y=0, relwidth=1, relheight=1)
                self.bg_label.lower()

        # top bar
        top = tk.Frame(self.root, bg=BG_COLOR)
        top.pack(fill="x", padx=12, pady=(12, 4))
        tk.Label(top, text=f"{APP_TITLE} {VERSION}", bg=BG_COLOR, fg=TEXT_FG,
                 font=("Segoe UI", 14, "bold")).pack(side="left")
        self.hk_label = tk.Label(
            top, text=hotkey_text(self.hotkey), bg=BG_COLOR, fg=TEXT_FG,
            font=("Segoe UI", 10), cursor="hand2",
        )
        self.hk_label.pack(side="right")
        self.hk_label.bind("<Button-1>", lambda e: self.start_capture())

        self.var_disable_launch = tk.BooleanVar(value=self.disable_self_launch)
        self.chk_disable_launch = tk.Checkbutton(
            top, text="Disable self-launch", variable=self.var_disable_launch,
            command=self.on_disable_launch_toggle,
            bg=BG_COLOR, fg=TEXT_FG, activebackground=BG_COLOR, activeforeground=TEXT_FG,
            selectcolor="#3a3e44", font=("Segoe UI", 9),
        )
        self.chk_disable_launch.pack(side="right", padx=(0, 16))

        self.var_hide_path = tk.BooleanVar(value=self.hide_exe_path)
        self.chk_hide_path = tk.Checkbutton(
            top, text="Hide exe path", variable=self.var_hide_path,
            command=self.on_hide_path_toggle,
            bg=BG_COLOR, fg=TEXT_FG, activebackground=BG_COLOR, activeforeground=TEXT_FG,
            selectcolor="#3a3e44", font=("Segoe UI", 9),
        )
        self.chk_hide_path.pack(side="right", padx=(0, 12))

        tk.Button(
            top, text="Create shortcut", command=self.make_shortcut,
            bg=BG_COLOR, fg=TEXT_FG, activebackground=BG_COLOR, activeforeground=TEXT_FG,
            relief="solid", bd=1, highlightthickness=1, highlightbackground="#6a7078",
            font=("Segoe UI", 9), padx=8, pady=1,
        ).pack(side="right", padx=(0, 8))

        # scrollable blocks area
        container = tk.Frame(self.root, bg=BG_COLOR)
        container.pack(fill="both", expand=True, padx=12, pady=6)
        self.canvas = tk.Canvas(container, bg=BG_COLOR, highlightthickness=0)
        self.scroll = tk.Scrollbar(container, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=BG_COLOR)
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.inner_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scroll.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scroll.pack(side="right", fill="y")
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Configure>", self._stretch_inner)

        # bottom buttons
        bottom = tk.Frame(self.root, bg=BG_COLOR)
        bottom.pack(fill="x", padx=12, pady=(4, 12))
        tk.Button(bottom, text="+", command=self.add_block, bg=BTN_BG, fg=BTN_FG,
                  activebackground=BTN_ACTIVE, activeforeground=BTN_FG,
                  font=("Segoe UI", 12, "bold"), width=4, relief="solid", bd=1).pack(side="left", padx=4)
        tk.Button(bottom, text="Save EXEs", command=self.save, bg=BTN_BG, fg=BTN_FG,
                  activebackground=BTN_ACTIVE, activeforeground=BTN_FG,
                  font=("Segoe UI", 10), relief="solid", bd=1, padx=10).pack(side="left", padx=4)
        tk.Button(bottom, text="Open all active", command=self.launch_active, bg=BTN_BG, fg=BTN_FG,
                  activebackground=BTN_ACTIVE, activeforeground=BTN_FG,
                  font=("Segoe UI", 10), relief="solid", bd=1, padx=10).pack(side="left", padx=4)
        tk.Button(bottom, text="Close all", command=self.close_all, bg=BTN_BG, fg=BTN_FG,
                  activebackground=BTN_ACTIVE, activeforeground=BTN_FG,
                  font=("Segoe UI", 10), relief="solid", bd=1, padx=10).pack(side="right", padx=4)
        tk.Button(bottom, text="Close", command=self.on_close, bg=BTN_BG, fg=BTN_FG,
                  activebackground=BTN_ACTIVE, activeforeground=BTN_FG,
                  font=("Segoe UI", 10), relief="solid", bd=1, padx=10).pack(side="right", padx=4)

        self.status = tk.Label(
            self.root, text="", bg=BG_COLOR, fg="#b8bcc4",
            font=("Segoe UI", 9), anchor="w",
        )
        self.status.pack(fill="x", padx=16, pady=(0, 8))
        self._status_after = None

        apply_window_chrome(self.root, self.swap_ico)
        # re-apply cursor after all widgets exist
        cur_src = find_asset(*ASSET_CURSOR_CANDIDATES)
        if cur_src:
            cur = os.path.join(tempfile.gettempdir(), "lid_execute.cur")
            if os.path.isfile(cur):
                apply_cursor(self.root, cur)
        if not self.disable_shortcut:
            if self.hotkey:
                install_hook(_vk_from_char(self.hotkey), self.root)
        else:
            self.hk_label.configure(text="Hide UI: disabled")

        # load existing
        game_item = {"path": "", "active": True}
        others = []
        for item in load_exes():
            if item.get("game"):
                game_item = item
            else:
                others.append(item)
        self.game_block = Block(
            self.inner, game_item.get("path", ""), game_item.get("active", True),
            self.remove_block, self.move_up, self.move_down, game=True,
            hide_path=self.hide_exe_path,
        )
        for item in others:
            self.add_block(item.get("path", ""), item.get("active", True))
        if not others:
            self.refresh_layout()

        # countdown shows whenever grace_time > 0, even if start_minimized.
        # grace_time = 0 is the only way to skip it.
        launched = False
        if not self.disable_self_launch and self.grace_time > 0:
            splash = GraceSplash(self.root, self.grace_time, self.swap_ico)
            self.root.wait_window(splash)
            if getattr(splash, "result", "go") == "go":
                self.launch_active()
                launched = True
        elif not self.disable_self_launch:
            self.launch_active()
            launched = True

        if self.start_minimized:
            self.root.withdraw()
            self.ui_visible = False
        else:
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
            self.ui_visible = True

        if self._ignored_minimized:
            self.set_status("start minimized ignored: no hotkey set")

        self.root.after(100, self.poll_hotkey)
        self.capturing = False
        if launched and self.self_close_after_launch:
            self.root.after(400, self.on_close)

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _stretch_inner(self, event) -> None:
        self.canvas.itemconfigure(self.inner_id, width=event.width)

    def add_block(self, path: str = "", active: bool = True) -> None:
        block = Block(
            self.inner, path, active, self.remove_block, self.move_up, self.move_down,
            hide_path=self.hide_exe_path,
        )
        self.blocks.append(block)
        self.refresh_layout()

    def refresh_layout(self) -> None:
        for sep in self.separators:
            sep.destroy()
        self.separators.clear()
        if self.game_block:
            self.game_block.pack_forget()
        for block in self.blocks:
            block.pack_forget()
        if self.game_block:
            self.game_block.pack(fill="x", pady=(4, 2), padx=4)
            sep = tk.Frame(self.inner, bg="#000000", height=2)
            sep.pack(fill="x", padx=8, pady=(4, 4))
            self.separators.append(sep)
        for i, block in enumerate(self.blocks):
            if i:
                sep = tk.Frame(self.inner, bg="#000000", height=2)
                sep.pack(fill="x", padx=8, pady=(2, 2))
                self.separators.append(sep)
            block.pack(fill="x", pady=4, padx=4)

    def move_up(self, block: Block) -> None:
        i = self.blocks.index(block) if block in self.blocks else -1
        if i <= 0:
            return
        self.blocks[i - 1], self.blocks[i] = self.blocks[i], self.blocks[i - 1]
        self.refresh_layout()

    def move_down(self, block: Block) -> None:
        i = self.blocks.index(block) if block in self.blocks else -1
        if i < 0 or i >= len(self.blocks) - 1:
            return
        self.blocks[i + 1], self.blocks[i] = self.blocks[i], self.blocks[i + 1]
        self.refresh_layout()

    def remove_block(self, block: Block) -> None:
        if block in self.blocks:
            self.blocks.remove(block)
        block.destroy()
        self.refresh_layout()

    def make_shortcut(self) -> None:
        swap = load_settings().get("swap_app_thumbnail", "") or self.swap_ico
        try:
            lnk = create_shortcut(swap)
        except Exception as exc:
            self.set_status(f"shortcut failed: {exc}")
            return
        used = os.path.basename(swap) if swap else "default"
        self.set_status(f"shortcut created with {used}: {lnk}")

    def on_disable_launch_toggle(self) -> None:
        self.disable_self_launch = bool(self.var_disable_launch.get())
        self.persist_settings()
        self.set_status("self-launch disabled" if self.disable_self_launch else "self-launch enabled")

    def on_hide_path_toggle(self) -> None:
        self.hide_exe_path = bool(self.var_hide_path.get())
        if self.game_block:
            self.game_block.set_hide(self.hide_exe_path)
        for block in self.blocks:
            block.set_hide(self.hide_exe_path)
        self.persist_settings()
        self.set_status("showing exe names only" if self.hide_exe_path else "showing full paths")

    def persist_settings(self) -> None:
        save_settings(
            self.hotkey, self.start_minimized_ini, self.grace_time,
            self.disable_shortcut, self.wait_between, self.swap_ico,
            self.disable_self_launch, self.self_close_after_launch,
            self.hide_exe_path,
        )

    def set_status(self, text: str) -> None:
        self.status.configure(text=text)
        if self._status_after:
            try:
                self.root.after_cancel(self._status_after)
            except Exception:
                pass
        self._status_after = self.root.after(5000, self.clear_status)

    def clear_status(self) -> None:
        self._status_after = None
        if self.root.winfo_exists():
            self.status.configure(text="")

    def save(self) -> None:
        items = []
        if self.game_block:
            items.append(self.game_block.data())
        items += [b.data() for b in self.blocks if b.data()["path"]]
        save_exes(items)
        n = sum(1 for i in items if i.get("path"))
        self.set_status(f"saved {n} executable(s)")

    def launch_active(self) -> None:
        started = []
        first = True
        order = []
        if self.game_block:
            order.append(self.game_block)
        order += self.blocks
        for b in order:
            d = b.data()
            if not d["active"] or not d["path"]:
                continue
            image = os.path.basename(d["path"])
            if process_running(image):
                continue
            if not first and self.wait_between > 0:
                time.sleep(self.wait_between)
            if launch_exe(d["path"]):
                started.append(image)
                first = False
        if started:
            self.set_status("opened " + ", ".join(started))

    def close_all(self) -> None:
        closed = []
        for b in self.blocks:
            path = b.data()["path"]
            if not path:
                continue
            image = os.path.basename(path)
            if process_running(image):
                kill_image(image)
                closed.append(image)
        if closed:
            self.set_status("closed " + ", ".join(closed))

    def on_close(self) -> None:
        uninstall_hook()
        clear_lock()
        self.root.destroy()

    def toggle_ui(self) -> None:
        if self.ui_visible:
            self.root.withdraw()
            self.ui_visible = False
        else:
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
            self.ui_visible = True

    def start_capture(self) -> None:
        self.capturing = True
        self.hk_label.configure(text="Press a key...")
        self.root.bind("<Key>", self._capture_key)

    def _capture_key(self, event) -> None:
        if not self.capturing:
            return
        ch = event.char
        if ch and ch.isprintable() and len(ch) == 1:
            self.hotkey = ch
            self.settings["hotkey"] = ch
            save_settings(self.hotkey, self.start_minimized_ini, self.grace_time,
                          self.disable_shortcut, self.wait_between, self.swap_ico,
                          self.disable_self_launch, self.self_close_after_launch,
                          self.hide_exe_path)
            if not self.disable_shortcut:
                install_hook(_vk_from_char(ch), self.root)
            self.hk_label.configure(text=hotkey_text(self.hotkey))
        else:
            self.hk_label.configure(text=hotkey_text(self.hotkey))
        self.capturing = False
        self.root.unbind("<Key>")

    def poll_hotkey(self) -> None:
        if not self.disable_shortcut and consume_hotkey():
            self.toggle_ui()
        if self.root.winfo_exists():
            self.root.after(80, self.poll_hotkey)

    def run(self) -> None:
        self.root.mainloop()


def main() -> int:
    set_app_id()
    close_previous()
    write_lock()
    # ensure settings file exists
    s = load_settings()
    if not os.path.isfile(settings_path()):
        save_settings(
            s.get("hotkey", DEFAULT_HOTKEY),
            s.get("start_minimized", False),
            s.get("grace_time", 3),
            s.get("disable_shortcut", False),
            s.get("wait_between_launches", 3),
            s.get("swap_app_thumbnail", ""),
            s.get("disable_self_launch", False),
            s.get("self_close_after_all_launch", False),
            s.get("hide_exe_path_in_ui", True),
        )
    try:
        App().run()
    finally:
        uninstall_hook()
        clear_lock()
    return 0


if __name__ == "__main__":
    sys.exit(main())