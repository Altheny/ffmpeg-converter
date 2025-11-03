# ffmpeg_gui.pyw – Wersja 0.2.0 (pełna, działająca)
# Tray zamknięty, 0 procesów, tryby bez "+", combobox z opisami

import os
import subprocess
from subprocess import CREATE_NO_WINDOW, STARTUPINFO, STARTF_USESHOWWINDOW, SW_HIDE
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
import re
import pickle
import sys
import logging
from functools import partial
import appdirs
import json
from PIL import Image
import pystray
from pystray import MenuItem as item
import atexit

# --- Tryb debug ---
DEBUG_MODE = "--debug" in sys.argv
LOG_FILE = "debug.log" if DEBUG_MODE else None
if DEBUG_MODE:
    logging.basicConfig(filename=LOG_FILE, level=logging.DEBUG, format="[%(asctime)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
else:
    logging.basicConfig(level=logging.CRITICAL)
log = logging.getLogger()
log.debug("START: FFmpeg Converter v0.2.0")

# --- AppData & Style ---
APP_NAME = "FFmpegConverter"
CONFIG_DIR = appdirs.user_data_dir(APP_NAME)
os.makedirs(CONFIG_DIR, exist_ok=True)
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.pkl")
STYLES_DIR = "styles"
DEFAULT_STYLE = {
    "bg": "#1e1e1e", "fg": "#ffffff", "entry_bg": "#2d2d2d",
    "button_bg": "#4caf50", "button_fg": "#ffffff",
    "progress_bg": "#4caf50", "status_fg": "#00ff00",
    "title": "FFmpeg Converter v0.2.0"
}

def ensure_default_style():
    if not os.path.exists(STYLES_DIR):
        os.makedirs(STYLES_DIR)
    dark_path = os.path.join(STYLES_DIR, "dark.css")
    if not os.path.exists(dark_path):
        with open(dark_path, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_STYLE, f, indent=2)

def load_style(style_name):
    path = os.path.join(STYLES_DIR, f"{style_name}.css")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                user = json.load(f)
            user["title"] = user.get("title", f"FFmpeg Converter v0.2.0 ({style_name})")
            return user
        except:
            pass
    return DEFAULT_STYLE.copy()

def get_available_styles():
    ensure_default_style()
    return sorted([f.replace(".css", "") for f in os.listdir(STYLES_DIR) if f.lower().endswith(".css")])

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "rb") as f:
                data = pickle.load(f)
            if data.get("selected_style") not in get_available_styles():
                return {"selected_style": "dark"}
            return data
        except Exception as e:
            log.error(f"Config load error: {e}")
    return {"selected_style": "dark"}

def save_config(data):
    try:
        with open(CONFIG_FILE, "wb") as f:
            pickle.dump(data, f)
    except Exception as e:
        log.error(f"Config save error: {e}")

def format_size_with_spaces(value: str) -> str:
    if not value.isdigit(): return value
    return "".join(" " + d if i > 0 and i % 3 == 0 else d for i, d in enumerate(reversed(value)))[::-1]

# --- Parsowanie postępu ---
def parse_duration_from_ffmpeg(line: str) -> float:
    match = re.search(r'Duration: (\d{2}):(\d{2}):(\d{2})\.(\d{2})', line)
    if match:
        h, m, s, ms = map(int, match.groups())
        return h * 3600 + m * 60 + s + ms / 100
    return None

def parse_current_time(line: str) -> float:
    match = re.search(r'time=([0-9:.]+)', line)
    if match:
        return sum(float(x) * 60 ** i for i, x in enumerate(reversed(match.group(1).split(":"))))
    return None

# --- Mapowanie trybów (bez +) ---
MODE_DISPLAY = {
    "1": "1 - Oryginał audio napisy",
    "11": "11 - Oryginał audio",
    "12": "12 - Oryginał napisy",
    "13": "13 - Oryginał ___1",
    "14": "14 - Oryginał ___2",
    "2": "2 - Oryginał",
    "3": "3 - 2560x1440",
    "4": "4 - 1920x1080",
    "5": "5 - 1280x720",
    "6": "6 - 640x360",
    "7": "7 - 320x180",
    "8": "8 - 50%",
    "9": "9 - 25%",
    "111": "111 - mp3"
}

MODE_VALUES = list(MODE_DISPLAY.keys())
MODE_LABELS = [MODE_DISPLAY[k] for k in MODE_VALUES]

def get_mode_key(display_label: str) -> str:
    for k, v in MODE_DISPLAY.items():
        if v == display_label:
            return k
    return "11"

# --- MODUŁY KONWERSJI ---
def get_output_name(input_file: str, mode: str) -> str:
    base = os.path.splitext(input_file)[0]
    if mode == "111":
        return f"{base}_ff.mp3"
    if mode in ["3", "4", "5", "6", "7"]:
        scale_map = {"3": "2560", "4": "1920", "5": "1280", "6": "640", "7": "320"}
        return f"{base}_{scale_map[mode]}x_ff.mkv"
    if mode == "8": return f"{base}_50_ff.mkv"
    if mode == "9": return f"{base}_25_ff.mkv"
    return f"{base}_ff.mkv"

def build_ffmpeg_command(input_file: str, output_file: str, mode: str, crf: str, preset: str) -> list:
    cmd = ["ffmpeg", "-y", "-i", input_file]
    if mode != "111":
        cmd += ["-c:v", "libx265", "-crf", crf, "-preset", preset, "-threads", "0"]
        if mode in ["1", "11", "12", "2"]:
            cmd += ["-map", "0:v", "-map", "0:a?", "-c:a", "copy"]
            if mode == "1": cmd += ["-map", "0:s?"]
        elif mode in ["3", "4", "5", "6", "7", "8", "9"]:
            scale_filters = {"3": "2560", "4": "1920", "5": "1280", "6": "640", "7": "320", "8": "iw/2", "9": "iw/4"}
            scale = scale_filters[mode]
            cmd += ["-vf", f"scale={scale}:-2", "-c:a", "aac", "-b:a", "128k"]
    cmd.append(output_file)
    return cmd

class FFmpegGUI:
    def __init__(self, root):
        self.root = root
        self.config = load_config()
        self.selected_style = self.config.get("selected_style", "dark")
        self.style = load_style(self.selected_style)
        self.root.title(self.style["title"])
        self.root.geometry("680x600")
        self.root.configure(bg=self.style["bg"])
        self.root.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)

        self.crf_var = tk.StringVar(value="23")
        self.preset_var = tk.StringVar(value="medium")
        self.choice_label_var = tk.StringVar(value=MODE_DISPLAY["11"])
        self.choice_key = "11"
        self.handle_mkv_var = tk.BooleanVar(value=False)
        self.directory_var = tk.StringVar(value=os.getcwd())
        self.total_progress_var = tk.DoubleVar(value=0)
        self.file_progress_var = tk.DoubleVar(value=0)
        self.log_var = tk.StringVar(value="Gotowy.")
        self.running_process = None
        self.total_files = 0
        self.current_file_index = 0

        self.icon = None
        self.create_widgets()
        self.apply_style()
        self.create_tray_icon()

        atexit.register(self.cleanup_tray)

    def cleanup_tray(self):
        if self.icon:
            try:
                self.icon.stop()
            except:
                pass

    def create_tray_icon(self):
        image = Image.new('RGB', (64, 64), color=(73, 109, 137))
        self.icon = pystray.Icon("FFmpegConverter", image, "FFmpeg Converter", menu=pystray.Menu(
            item('Otwórz', self.show_window),
            item('Zamknij', self.quit_app)
        ))

    def minimize_to_tray(self):
        self.root.withdraw()
        if self.icon:
            self.icon.visible = True
            self.icon.run_detached()

    def show_window(self, icon=None, item=None):
        self.root.deiconify()
        self.root.lift()
        if self.icon:
            self.icon.visible = False

    def quit_app(self, icon=None, item=None):
        if self.running_process and self.running_process.poll() is None:
            self.running_process.terminate()
            try: self.running_process.wait(timeout=3)
            except: self.running_process.kill()
        self.cleanup_tray()
        self.root.quit()

    def apply_style(self):
        self.root.configure(bg=self.style["bg"])
        for widget in self.root.winfo_children():
            self._recolor(widget)

    def _recolor(self, widget):
        try:
            if isinstance(widget, (tk.Label, tk.Checkbutton)):
                widget.configure(bg=self.style["bg"], fg=self.style["fg"])
            elif isinstance(widget, tk.Entry):
                widget.configure(bg=self.style["entry_bg"], fg=self.style["fg"], insertbackground=self.style["fg"])
            elif isinstance(widget, tk.Button):
                if "START" in widget.cget("text"):
                    widget.configure(bg=self.style["button_bg"], fg=self.style["button_fg"])
                else:
                    widget.configure(bg="#3a3a3a", fg=self.style["fg"])
            elif isinstance(widget, tk.Frame):
                widget.configure(bg=self.style["bg"])
        except: pass
        for child in widget.winfo_children():
            self._recolor(child)

    def create_widgets(self):
        menubar = tk.Menu(self.root)
        style_menu = tk.Menu(menubar, tearoff=0)
        for name in get_available_styles():
            style_menu.add_command(label=name.capitalize(), command=partial(self.change_style, name))
        menubar.add_cascade(label="Styl", menu=style_menu)
        self.root.config(menu=menubar)

        main_frame = tk.Frame(self.root, bg=self.style["bg"])
        main_frame.pack(pady=10, padx=15, fill=tk.BOTH, expand=True)

        tk.Label(main_frame, text="CRF (19-33):", fg=self.style["fg"], bg=self.style["bg"]).pack(anchor="w")
        tk.Entry(main_frame, textvariable=self.crf_var, bg=self.style["entry_bg"], fg=self.style["fg"], insertbackground=self.style["fg"]).pack(fill=tk.X, pady=2)

        tk.Label(main_frame, text="Preset:", fg=self.style["fg"], bg=self.style["bg"]).pack(anchor="w", pady=(10,0))
        ttk.Combobox(main_frame, textvariable=self.preset_var, values=["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow", "placebo"]).pack(fill=tk.X, pady=2)

        tk.Label(main_frame, text="Tryb:", fg=self.style["fg"], bg=self.style["bg"]).pack(anchor="w", pady=(10,0))
        self.mode_combo = ttk.Combobox(main_frame, textvariable=self.choice_label_var, values=MODE_LABELS, state="readonly", width=50)
        self.mode_combo.pack(fill=tk.X, pady=2)
        self.mode_combo.bind("<<ComboboxSelected>>", self.on_mode_selected)

        tk.Checkbutton(main_frame, text="MKV", variable=self.handle_mkv_var, fg=self.style["fg"], bg=self.style["bg"], selectcolor=self.style["entry_bg"]).pack(anchor="w", pady=5)

        tk.Label(main_frame, text="Katalog:", fg=self.style["fg"], bg=self.style["bg"]).pack(anchor="w", pady=(10,0))
        dir_frame = tk.Frame(main_frame, bg=self.style["bg"])
        dir_frame.pack(fill=tk.X, pady=2)
        tk.Entry(dir_frame, textvariable=self.directory_var, bg=self.style["entry_bg"], fg=self.style["fg"]).pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Button(dir_frame, text="Przeglądaj", command=self.browse_directory, bg="#3a3a3a", fg=self.style["fg"]).pack(side=tk.RIGHT, padx=(5,0))

        tk.Label(main_frame, text="Postęp całkowity:", fg=self.style["fg"], bg=self.style["bg"]).pack(anchor="w", pady=(15,0))
        self.total_progress = ttk.Progressbar(main_frame, variable=self.total_progress_var, maximum=100)
        self.total_progress.pack(fill=tk.X, pady=2)

        tk.Label(main_frame, text="Postęp pliku:", fg=self.style["fg"], bg=self.style["bg"]).pack(anchor="w", pady=(8,0))
        self.file_progress = ttk.Progressbar(main_frame, variable=self.file_progress_var, maximum=100)
        self.file_progress.pack(fill=tk.X, pady=2)

        status_frame = tk.Frame(main_frame, bg=self.style["bg"])
        status_frame.pack(fill=tk.X, pady=5)
        tk.Label(status_frame, text="Status:", fg=self.style["progress_bg"], bg=self.style["bg"], font=("Arial", 10, "bold")).pack(anchor="w")
        tk.Label(status_frame, textvariable=self.log_var, fg=self.style["status_fg"], bg=self.style["bg"], font=("Courier", 11)).pack(fill=tk.X)

        tk.Button(main_frame, text="START", command=self.start_conversion, bg=self.style["button_bg"], fg=self.style["button_fg"], font=("Arial", 12, "bold"), height=2).pack(pady=15, fill=tk.X)

    def on_mode_selected(self, event=None):
        selected_label = self.choice_label_var.get()
        self.choice_key = get_mode_key(selected_label)

    def change_style(self, name):
        if name not in get_available_styles():
            return
        self.selected_style = name
        self.style = load_style(name)
        self.config["selected_style"] = name
        save_config(self.config)
        self.root.title(self.style["title"])
        self.apply_style()

    def browse_directory(self):
        d = filedialog.askdirectory()
        if d: self.directory_var.set(d)

    def log_message(self, message: str):
        size_match = re.search(r'size=\s*([0-9]+)\s*(KiB|KB)', message, re.I)
        time_match = re.search(r'time=([0-9:.]+)', message)
        speed_match = re.search(r'speed=([0-9.]+)x', message)
        size_str = f"size=   {format_size_with_spaces(size_match.group(1))} {size_match.group(2)}" if size_match else ""
        time_str = f"time={time_match.group(1)}" if time_match else ""
        speed_str = f"speed={speed_match.group(1)}x" if speed_match else ""
        parts = [s for s in [size_str, time_str, speed_str] if s]
        if parts:
            self.log_var.set("   ".join(parts))

    def start_conversion(self):
        if not self.validate_inputs(): return
        self.total_progress_var.set(0)
        self.file_progress_var.set(0)
        self.log_var.set("Startuję...")
        threading.Thread(target=self.run_conversion, daemon=True).start()

    def validate_inputs(self):
        try:
            return 19 <= int(self.crf_var.get()) <= 33
        except:
            messagebox.showerror("Błąd", "CRF: 19–33")
            return False

    def run_conversion(self):
        try:
            os.chdir(self.directory_var.get())
        except Exception as e:
            self.log_var.set(f"Błąd: {e}")
            return

        exts = ['.mp4', '.mpg', '.mpeg', '.avi', '.flv', '.wmv', '.mov', '.mts', '.mts1', '.webm', '.mkv_']
        if self.handle_mkv_var.get(): exts.append('.mkv')
        files = [f for f in os.listdir() if any(f.lower().endswith(e) for e in exts)]
        if not files:
            self.log_var.set("Brak plików.")
            return

        self.total_files = len(files)
        self.current_file_index = 0

        for i, f in enumerate(files, 1):
            self.current_file_index = i
            self.process_file(f)
            self.total_progress_var.set((i / self.total_files) * 100)
        self.log_var.set("Zakończono.")

    def process_file(self, input_file: str):
        mode = self.choice_key
        crf = self.crf_var.get()
        preset = self.preset_var.get()
        output_file = get_output_name(input_file, mode)
        cmd = build_ffmpeg_command(input_file, output_file, mode, crf, preset)

        try:
            startupinfo = STARTUPINFO()
            startupinfo.dwFlags |= STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = SW_HIDE

            self.running_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                universal_newlines=True,
                creationflags=CREATE_NO_WINDOW,
                startupinfo=startupinfo
            )

            file_duration = 0.0
            for line in self.running_process.stdout:
                if not file_duration:
                    file_duration = parse_duration_from_ffmpeg(line) or 0.0
                current_time = parse_current_time(line) or 0.0
                if file_duration > 0:
                    progress = min(100, (current_time / file_duration) * 100)
                    self.file_progress_var.set(progress)
                self.log_message(line)

            self.running_process.wait(timeout=300)
            self.running_process = None
            self.file_progress_var.set(100)

        except subprocess.TimeoutExpired:
            self.running_process.kill()
            self.log_var.set("Timeout: proces zabity")
        except Exception as e:
            self.log_var.set(f"Błąd: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = FFmpegGUI(root)
    try:
        root.mainloop()
    finally:
        app.cleanup_tray()
    log.debug("ZAMKNIĘTO PROGRAM")