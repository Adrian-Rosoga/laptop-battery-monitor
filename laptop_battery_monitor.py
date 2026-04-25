"""
Tray-controlled background battery monitor for Windows 11.

This Python script creates a system tray icon with a menu to configure the background
monitoring thread, show status and exit. The monitor checks battery status at a
configurable interval and sends Telegram status reports.

Install command (run once on your machine to install dependencies):
    python -m pip install pystray pillow psutil telegram-send plyer tkinter

Run:
    python monitor.py

Notes:
If you enable Telegram in Settings, run telegram-send --configure to link a bot/chat
or provide a config path in the Settings UI.
tkinter is typically included with standard Windows Python; if missing, install
the appropriate Python installer/feature.

You can write the config file once to a known location on your computer:
telegram-send --configure --config ~/telegram-send.conf
"""

import threading
import time
import socket
import sys
import os
import json
import logging
import csv
import datetime
import ctypes
import ctypes.wintypes as _wt

try:
    import psutil
except Exception as e:
    logging.warning(f"psutil not available: {e}")
    psutil = None

try:
    import pystray
    from PIL import Image, ImageDraw, ImageFont
except Exception as e:
    logging.warning(f"pystray/PIL not available: {e}")
    pystray = None

try:
    import telegram_send
except Exception as e:
    logging.warning(f"telegram_send not available: {e}")
    telegram_send = None

try:
    import tkinter as tk
    from tkinter import messagebox
except Exception as e:
    logging.warning(f"tkinter not available: {e}")
    tk = None

try:
    import matplotlib
    import matplotlib.figure
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.patches import Patch
except Exception as e:
    logging.warning(f"matplotlib not available: {e}")
    plt = None

__version__ = "1.8"
HOSTNAME = socket.gethostname()
ALERT_BORDER = "🚨" * 10
#LOG_LEVEL = logging.DEBUG
LOG_LEVEL = logging.INFO
#LOG_LEVEL = logging.CRITICAL    # To actually disable logging output, set to CRITICAL and use logging.debug for all log messages in code

# Determine ROOT_DIR based on whether running as executable or script
if getattr(sys, 'frozen', False):
    # Running as a PyInstaller executable
    ROOT_DIR = os.path.dirname(sys.executable)
else:
    # Running as a Python script
    ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_PATH = os.path.join(ROOT_DIR, "monitor_config.json")
CSV_LOG_DIR = ROOT_DIR   # daily CSV files are written here


def _get_wifi_dbm():
    """Return current WiFi signal as (dbm, pct) or (None, None) if unavailable.

    Uses the Windows Native WiFi API (wlanapi.dll) via ctypes to read RSSI
    directly from the NIC driver.  This does NOT spawn netsh and does NOT
    touch the Windows Location Services API, so the 'Location in use' tray
    icon never appears.
    """
    try:
        class _GUID(ctypes.Structure):
            _fields_ = [('Data1', ctypes.c_ulong), ('Data2', ctypes.c_ushort),
                        ('Data3', ctypes.c_ushort), ('Data4', ctypes.c_ubyte * 8)]

        wlan = ctypes.WinDLL('wlanapi.dll')
        wlan.WlanOpenHandle.restype      = _wt.DWORD
        wlan.WlanOpenHandle.argtypes     = [_wt.DWORD, ctypes.c_void_p,
                                            ctypes.POINTER(_wt.DWORD),
                                            ctypes.POINTER(_wt.HANDLE)]
        wlan.WlanEnumInterfaces.restype  = _wt.DWORD
        wlan.WlanEnumInterfaces.argtypes = [_wt.HANDLE, ctypes.c_void_p,
                                            ctypes.POINTER(ctypes.c_void_p)]
        wlan.WlanQueryInterface.restype  = _wt.DWORD
        wlan.WlanQueryInterface.argtypes = [_wt.HANDLE, ctypes.POINTER(_GUID),
                                            ctypes.c_uint, ctypes.c_void_p,
                                            ctypes.POINTER(_wt.DWORD),
                                            ctypes.POINTER(ctypes.c_void_p),
                                            ctypes.POINTER(ctypes.c_uint)]
        wlan.WlanFreeMemory.restype      = None
        wlan.WlanFreeMemory.argtypes     = [ctypes.c_void_p]
        wlan.WlanCloseHandle.restype     = _wt.DWORD
        wlan.WlanCloseHandle.argtypes    = [_wt.HANDLE, ctypes.c_void_p]

        neg_ver = _wt.DWORD()
        handle  = _wt.HANDLE()
        if wlan.WlanOpenHandle(2, None, ctypes.byref(neg_ver), ctypes.byref(handle)) != 0:
            return None, None
        try:
            iface_ptr = ctypes.c_void_p()
            if wlan.WlanEnumInterfaces(handle, None, ctypes.byref(iface_ptr)) != 0:
                return None, None
            try:
                if not iface_ptr.value:
                    return None, None
                base = iface_ptr.value
                # WLAN_INTERFACE_INFO_LIST layout:
                #   DWORD dwNumberOfItems  (+0)
                #   DWORD dwIndex          (+4)
                #   WLAN_INTERFACE_INFO[0] (+8):
                #     GUID                 (16 bytes)
                #     WCHAR description[256] (512 bytes)
                #     DWORD isState
                num = ctypes.c_uint32.from_address(base).value
                if num == 0:
                    return None, None
                state = ctypes.c_uint32.from_address(base + 8 + 16 + 512).value
                if state != 1:          # wlan_interface_state_connected
                    return None, None
                guid = _GUID.from_address(base + 8)
                RSSI_OPCODE = 0x10000102  # wlan_intf_opcode_rssi
                data_size = _wt.DWORD()
                data_ptr  = ctypes.c_void_p()
                op_type   = ctypes.c_uint()
                if wlan.WlanQueryInterface(
                        handle, ctypes.byref(guid), RSSI_OPCODE, None,
                        ctypes.byref(data_size), ctypes.byref(data_ptr),
                        ctypes.byref(op_type)) != 0:
                    return None, None
                try:
                    dbm = ctypes.c_long.from_address(data_ptr.value).value
                    pct = min(100, max(0, 2 * (dbm + 100)))
                    return dbm, pct
                finally:
                    wlan.WlanFreeMemory(data_ptr)
            finally:
                wlan.WlanFreeMemory(iface_ptr)
        finally:
            wlan.WlanCloseHandle(handle, None)
    except Exception:
        return None, None


def _wifi_text_color(dbm):
    """Return an RGBA text colour for the WiFi icon based on signal strength.

    Icon uses a light grey background; the number's colour signals quality:
        >= -55  Excellent  →  vivid green      (0, 170, 60)
        >= -65  Good       →  yellow-green     (110, 180, 0)
        >= -75  Fair       →  dark orange      (210, 110, 0)
        <  -75  Poor       →  red              (210, 30, 30)
        None    No WiFi    →  medium grey      (120, 120, 120)
    """
    if dbm is None:
        return (120, 120, 120, 255)
    if dbm >= -55:
        return (0, 170, 60, 255)
    if dbm >= -65:
        return (110, 180, 0, 255)
    if dbm >= -75:
        return (210, 110, 0, 255)
    return (210, 30, 30, 255)


def _load_font(size, pt):
    """Load a bold TrueType font at *pt* points, falling back to the PIL default."""
    for name in ['calibrib.ttf', 'arial.ttf', 'ariblk.ttf', 'arial black.ttf']:
        for path in [name, f'C:\\Windows\\Fonts\\{name}']:
            try:
                return ImageFont.truetype(path, pt)
            except Exception:
                continue
    try:
        return ImageFont.load_default()
    except Exception:
        return None


def make_icon_image(size=128, color1=(0, 122, 204), color2=(255, 255, 255), percentage=None, plugged=False):
    """Battery tray icon — large % number on green (plugged) or yellow (unplugged) background."""
    image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    bg_color = (144, 238, 144, 255) if plugged else (255, 255, 0, 255)
    draw.rectangle((0, 0, size, size), fill=bg_color)
    if percentage is not None:
        try:
            font = _load_font(size, int(size * 1.0))
            if font:
                draw.text((size // 2, size // 2), f"{int(percentage)}",
                          fill=(255, 0, 0, 255), font=font, anchor="mm")
        except Exception as e:
            logging.debug(f"Error creating battery icon image: {e}")
    return image


def make_wifi_icon_image(size=128, dbm=None):
    """WiFi tray icon — light grey background, dBm number in signal-quality colour.

    Light background keeps the number readable at any quality level.
    The number colour signals quality (see _wifi_text_color):
        >= -55  Excellent  →  vivid green
        >= -65  Good       →  yellow-green
        >= -75  Fair       →  dark orange
        <  -75  Poor       →  red
        None    No WiFi    →  grey
    A dark outer border distinguishes this icon from the battery icon.
    """
    image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, size, size), fill=(225, 225, 225, 255))
    # Dark outer border — visually separates from the battery icon
    bw = max(6, size // 18)
    draw.rectangle((0, 0, size - 1, size - 1),
                   outline=(40, 40, 40, 255), width=bw)
    text_color = _wifi_text_color(dbm)
    try:
        label = f"{dbm}" if dbm is not None else "—"
        # Inner usable width after subtracting both border edges + small padding
        max_w = size - 2 * bw - max(4, size // 30)
        pt = int(size * 0.88)
        font = _load_font(size, pt)
        # Shrink font until the label fits horizontally
        while font and pt > 10:
            bbox = font.getbbox(label)
            if (bbox[2] - bbox[0]) <= max_w:
                break
            pt = int(pt * 0.88)
            font = _load_font(size, pt)
        if font:
            draw.text((size // 2, int(size * 0.48)), label,
                      fill=text_color, font=font, anchor="mm")
    except Exception as e:
        logging.debug(f"Error creating wifi icon image: {e}")
    return image


DEFAULT_CONFIG = {
    "threshold": 20,
    "interval": 1,
    "telegram_enabled": False,
    "telegram_conf": None,
    "logging_enabled": False,
    "data_log_interval": 60,
    "data_log_retention_days": 30,
    "disk_alert_enabled": True,
    "disk_alert_threshold": 90,
    "disk_alert_time": "07:00",
}
DEFAULT_CONFIG["resend_minutes"] = 5


def load_config():
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
            DEFAULT_CONFIG.update(cfg)
    except Exception as e:
        logging.debug(f"Could not load config from {CONFIG_PATH}: {e}")
    return dict(DEFAULT_CONFIG)


class _SafeStreamHandler(logging.StreamHandler):
    """StreamHandler that writes UTF-8 bytes directly to stdout.buffer.

    On Windows the TextIOWrapper over stdout uses the console code page
    (cp1252), which cannot encode emoji.  Writing encoded bytes directly to
    the underlying binary buffer bypasses that codec entirely; modern
    PowerShell / Windows Terminal can display UTF-8 natively.  If the buffer
    is unavailable we fall back to 'replace' encoding.  Either way this
    handler never raises and never prints '--- Logging error ---'.
    """
    def emit(self, record):
        try:
            msg = self.format(record)
            stream = self.stream
            buf = getattr(stream, 'buffer', None)
            if buf is not None:
                try:
                    stream.flush()          # drain any text already buffered
                except Exception:
                    pass
                buf.write((msg + self.terminator).encode('utf-8', errors='replace'))
                buf.flush()
            else:
                enc = getattr(stream, 'encoding', None) or 'ascii'
                stream.write(msg.encode(enc, errors='replace').decode(enc) + self.terminator)
                stream.flush()
        except Exception:
            pass  # console is convenience only; never surface handler errors


def setup_logging(enabled, date_str=None):
    """Configure logging based on settings. Safe to call multiple times (e.g. at midnight)."""
    if enabled:
        if date_str is None:
            date_str = datetime.date.today().strftime('%Y-%m-%d')
        log_filename = f'battery_monitor_{date_str}.log'
        handlers = [logging.FileHandler(os.path.join(ROOT_DIR, log_filename))]
        if sys.stdout is not None:
            try:
                handlers.append(_SafeStreamHandler(sys.stdout))
            except Exception:
                pass
        logging.basicConfig(
            force=True,
            level=LOG_LEVEL,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=handlers
        )
        # Silence any handler that still can't encode emoji (e.g. lastResort stderr).
        # The file log captures everything; console output is convenience only.
        logging.raiseExceptions = False
        # Suppress verbose third-party debug logs
        for noisy in ('matplotlib', 'telegram', 'httpcore', 'httpx', 'PIL'):
            logging.getLogger(noisy).setLevel(logging.WARNING)
    else:
        logging.disable(logging.CRITICAL)


def save_config(cfg):
    try:
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        logging.error(f"Failed to save config: {e}")
        print("Failed to save config:", e)


def _resolve_telegram_conf(conf=None):
    """Return conf path to use: explicit conf, or fallback to telegram-send.conf in ROOT_DIR."""
    if conf:
        return conf
    local_conf = os.path.join(ROOT_DIR, 'telegram-send.conf')
    if os.path.isfile(local_conf):
        return local_conf
    return None


def send_telegram_async(message, conf=None):
    import asyncio
    try:
        full = f"[{HOSTNAME}]\n{message}"
        resolved = _resolve_telegram_conf(conf)
        if resolved:
            asyncio.run(telegram_send.send(messages=[full], conf=resolved))
        else:
            asyncio.run(telegram_send.send(messages=[full]))
    except Exception as e:
        logging.error(f"Failed to send Telegram message: {e}")


class SettingsWindow:
    def __init__(self, parent, config, on_save=None):
        self.parent = parent
        self.config = config
        self.on_save = on_save
        if tk is None:
            raise RuntimeError("tkinter not available")

        self.root = tk.Tk()
        self.root.title("Battery Monitor Settings")
        self.root.geometry("320x560")

        tk.Label(self.root, text="Low battery threshold (%)").pack(anchor='w', padx=8, pady=(8, 0))
        self.threshold_var = tk.StringVar(value=str(self.config.get('threshold', 20)))
        tk.Entry(self.root, textvariable=self.threshold_var).pack(fill='x', padx=8)

        tk.Label(self.root, text="Check interval (seconds)").pack(anchor='w', padx=8, pady=(8, 0))
        self.interval_var = tk.StringVar(value=str(self.config.get('interval', 1)))
        tk.Entry(self.root, textvariable=self.interval_var).pack(fill='x', padx=8)

        self.telegram_var = tk.BooleanVar(value=bool(self.config.get('telegram_enabled')))
        tk.Checkbutton(self.root, text="Enable Telegram alerts", variable=self.telegram_var).pack(anchor='w', padx=8, pady=(8, 0))

        tk.Label(self.root, text="Config file telegram-send (optional)").pack(anchor='w', padx=8, pady=(8, 0))
        self.telegram_conf_var = tk.StringVar(value=str(self.config.get('telegram_conf') or ""))
        tk.Entry(self.root, textvariable=self.telegram_conf_var).pack(fill='x', padx=8)
        
        tk.Label(self.root, text="Send Low-Battery Telegram alert every (minutes)").pack(anchor='w', padx=8, pady=(8, 0))
        self.resend_var = tk.StringVar(value=str(self.config.get('resend_minutes', 5)))
        tk.Entry(self.root, textvariable=self.resend_var).pack(fill='x', padx=8)

        tk.Label(self.root, text="Data log interval (seconds)").pack(anchor='w', padx=8, pady=(8, 0))
        self.data_log_interval_var = tk.StringVar(value=str(self.config.get('data_log_interval', 60)))
        tk.Entry(self.root, textvariable=self.data_log_interval_var).pack(fill='x', padx=8)

        tk.Label(self.root, text="Data log retention (days)").pack(anchor='w', padx=8, pady=(8, 0))
        self.data_log_retention_var = tk.StringVar(value=str(self.config.get('data_log_retention_days', 30)))
        tk.Entry(self.root, textvariable=self.data_log_retention_var).pack(fill='x', padx=8)

        self.logging_var = tk.BooleanVar(value=bool(self.config.get('logging_enabled')))
        tk.Checkbutton(self.root, text="Enable logging", variable=self.logging_var).pack(anchor='w', padx=8, pady=(8, 0))

        tk.Label(self.root, text="─" * 38).pack(anchor='w', padx=8, pady=(8, 0))

        self.disk_alert_var = tk.BooleanVar(value=bool(self.config.get('disk_alert_enabled', True)))
        tk.Checkbutton(self.root, text="Enable daily disk space alert", variable=self.disk_alert_var).pack(anchor='w', padx=8, pady=(4, 0))

        tk.Label(self.root, text="Disk usage alert threshold (%)").pack(anchor='w', padx=8, pady=(8, 0))
        self.disk_threshold_var = tk.StringVar(value=str(self.config.get('disk_alert_threshold', 90)))
        tk.Entry(self.root, textvariable=self.disk_threshold_var).pack(fill='x', padx=8)

        tk.Label(self.root, text="Disk alert time (HH:MM, 24h)").pack(anchor='w', padx=8, pady=(8, 0))
        self.disk_alert_time_var = tk.StringVar(value=str(self.config.get('disk_alert_time', '07:00')))
        tk.Entry(self.root, textvariable=self.disk_alert_time_var).pack(fill='x', padx=8)

        frm = tk.Frame(self.root)
        frm.pack(fill='x', padx=8, pady=10)
        tk.Button(frm, text="Save", command=self.save).pack(side='left')
        tk.Button(frm, text="Test Telegram", command=self.test_telegram).pack(side='left', padx=8)
        tk.Button(frm, text="Close", command=self.close).pack(side='right')

    def save(self):
        try:
            self.config['threshold'] = int(self.threshold_var.get())
            self.config['interval'] = int(self.interval_var.get())
            self.config['resend_minutes'] = int(self.resend_var.get())
            self.config['data_log_interval'] = int(self.data_log_interval_var.get())
            self.config['data_log_retention_days'] = int(self.data_log_retention_var.get())
            self.config['telegram_enabled'] = bool(self.telegram_var.get())
            self.config['logging_enabled'] = bool(self.logging_var.get())
            conf = self.telegram_conf_var.get().strip()
            self.config['telegram_conf'] = conf if conf else None
            self.config['disk_alert_enabled'] = bool(self.disk_alert_var.get())
            self.config['disk_alert_threshold'] = int(self.disk_threshold_var.get())
            self.config['disk_alert_time'] = self.disk_alert_time_var.get().strip()
            save_config(self.config)
            if self.on_save:
                self.on_save(self.config)
            save_message = f"ℹ️  Settings saved to:\n{CONFIG_PATH}"
            messagebox.showinfo("Settings", save_message)
        except Exception as e:
            logging.error(f"Error saving settings: {e}")
            messagebox.showerror("Error", str(e))

    def test_telegram(self):
        if not self.config.get('telegram_enabled'):
            messagebox.showwarning("Telegram", "⚠️ Telegram is not enabled in settings")
            return
        msg = f"ℹ️ Test message"
        send_telegram_async(msg, conf=self.config.get('telegram_conf'))
        messagebox.showinfo("Telegram", "ℹ️ Test message sent (if configured)")

    def close(self):
        self.root.quit()


class TrayMonitor:
    def __init__(self, config=None):
        self.config = config or load_config()
        setup_logging(self.config.get('logging_enabled', False))
        self._thread = None
        self._stop_event = threading.Event()
        self._last_alert_time = None
        self._low_start_time = None
        self._was_low = False
        self._running = False
        self._last_csv_time = None
        self._current_day = None
        self._disk_alert_sent_date = None
        self._wifi_dbm = None          # last known WiFi dBm; None = no WiFi / not yet read
        self._open_windows = []  # track open tkinter windows for clean exit

        self.icon = None
        self.wifi_icon = None
        if pystray:
            image = make_icon_image(size=512, percentage=100, plugged=True)
            menu = pystray.Menu(
                pystray.MenuItem('Monitoring Enabled', self.toggle_monitoring, checked=lambda item: self._running),
                pystray.MenuItem('Show Status', self.show_status),
                pystray.MenuItem('Show Graph', self.show_graph, default=True),
                pystray.MenuItem('Settings', self.open_settings),
                pystray.MenuItem('About', self.show_about),
                pystray.MenuItem('Exit', self.exit)
            )
            self.icon = pystray.Icon(f"monitor_{HOSTNAME}", image, f"Battery Monitor v{__version__}: {HOSTNAME}", menu)
            wifi_image = make_wifi_icon_image(size=512, dbm=None)
            self.wifi_icon = pystray.Icon(f"wifi_{HOSTNAME}", wifi_image, "WiFi")

    def toggle_monitoring(self, icon=None, item=None):
        """Toggle monitoring on/off."""
        if self._running:
            self.stop_monitoring()
        else:
            self.start_monitoring()

    def start_monitoring(self, icon=None, item=None):
        if self._running:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        self._running = True
        self._notify(f"[{HOSTNAME}] ▶️ Battery monitoring started")
        # Rotate old CSV logs on startup
        threading.Thread(target=self._rotate_csv_logs, daemon=True).start()

    def stop_monitoring(self, icon=None, item=None):
        if not self._running:
            return
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)
        self._running = False
        self._notify(f"[{HOSTNAME}] ⏹️ Monitoring stopped")

    def show_status(self, icon=None, item=None):
        status = "Running" if self._running else "Stopped"
        info = self._get_battery_info() if psutil else None
        msg = f"{HOSTNAME}: {status}"
        if info:
            msg += f" — Battery {info['percent']}% {'(Plugged)' if info['plugged'] else ''}"
        # include time since last low-battery alert if available
        try:
            last = self._last_alert_time
            if last is not None:
                secs = int(time.time() - last)
                mins = secs // 60
                s = secs % 60
                msg += f"\nLast alert: {mins}m {s}s ago"
        except Exception as e:
            logging.debug(f"Error getting status info: {e}")
        self._notify(msg)

    def show_about(self, icon=None, item=None):
        """Show About dialog with clickable GitHub link."""
        if tk is None:
            self._notify("tkinter not available; cannot open About dialog.")
            return
        
        def _show_about():
            about_window = tk.Tk()
            about_window.title("About")
            about_window.geometry("400x320")
            about_window.resizable(False, False)
            
            # Title and version
            title_label = tk.Label(about_window, text=f"Laptop Battery Monitor v{__version__}", font=("Arial", 12, "bold"))
            title_label.pack(pady=10)
            
            # Description
            desc_label = tk.Label(about_window, text="Monitors battery status and sends Telegram alerts when low.\nConfigurable threshold, interval and Telegram integration.", justify=tk.CENTER)
            desc_label.pack(pady=5)
            
            # Clickable GitHub link
            def open_github():
                import webbrowser
                webbrowser.open("https://github.com/Adrian-Rosoga/laptop-battery-monitor")
            
            github_link = tk.Label(about_window, text="GitHub Repository", fg="blue", cursor="hand2", font=("Arial", 10, "underline"))
            github_link.pack(pady=5)
            github_link.bind("<Button-1>", lambda e: open_github())
            
            # Credits
            credits_label = tk.Label(about_window, text="Adrian Rosoga\n(actually GPT-5 mini\nClaude Haiku 4.5\nClaude Opus 4.6\nClaude Sonnet 4.6\n...)\nFebruary 2026", font=("Arial", 10))
            credits_label.pack(pady=10)
            
            # Close button — use quit() not destroy() so cleanup can run on this thread
            close_button = tk.Button(about_window, text="Close", command=about_window.quit)
            close_button.pack(pady=10)
            about_window.protocol("WM_DELETE_WINDOW", about_window.quit)
            
            about_window.mainloop()

            import gc
            gc.collect()
            about_window.destroy()
        
        threading.Thread(target=_show_about, daemon=True).start()

    def show_graph(self, icon=None, item=None):
        """Show the battery graph for today in an interactive popup with zoom/pan and cursor values."""
        if tk is None:
            self._notify("tkinter not available; cannot show graph.")
            return

        def _show():
            import math
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

            date_str = datetime.date.today().strftime('%Y-%m-%d')
            csv_path = os.path.join(CSV_LOG_DIR, f'battery_log_{date_str}.csv')
            logging.info(f"Show Graph: using data file {csv_path}")

            result = self._build_graph_figure(date_str)
            if result is None:
                self._notify("No graph data available for today.")
                return
            fig, ax, plot_times, plot_battery, plot_cpu = result

            win = tk.Tk()
            self._open_windows.append(win)
            win.title(f"Battery Graph \u2014 {date_str}")
            win.attributes("-topmost", True)

            # Resize figure to screen width
            screen_w = win.winfo_screenwidth()
            dpi = fig.dpi
            fig.set_size_inches(screen_w / dpi, fig.get_size_inches()[1])
            fig.tight_layout()

            canvas = FigureCanvasTkAgg(fig, master=win)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

            toolbar = NavigationToolbar2Tk(canvas, win)
            toolbar.update()
            # Suppress the default "(x, y)" coordinate display in the toolbar
            toolbar.set_message = lambda msg: None

            # Status bar showing nearest data point values under cursor
            status_var = tk.StringVar(value="  Move cursor over graph to see values")
            status_bar = tk.Label(win, textvariable=status_var, anchor='w',
                                  relief=tk.SUNKEN, font=("Courier", 14, "bold"), padx=6)
            status_bar.pack(fill=tk.X, side=tk.BOTTOM)

            def on_motion(event):
                if event.inaxes != ax or event.xdata is None:
                    status_var.set("  Move cursor over graph to see values")
                    return
                t = mdates.num2date(event.xdata).replace(tzinfo=None)
                n = len(plot_times)
                if n < 2:
                    return
                # Cursor outside the data range entirely → no data
                if t < plot_times[0] or t > plot_times[-1]:
                    status_var.set(f"  Time: {t.strftime('%H:%M:%S')}    Battery: N/A    CPU: N/A")
                    return
                # Binary search for the two plot points that bracket the cursor time.
                # plot_times includes NaN sentinel datetimes at gap midpoints, so the
                # bracketing pair tells us definitively whether the cursor is in a gap.
                import bisect
                i = bisect.bisect_right(plot_times, t) - 1
                i = max(0, min(i, n - 2))   # clamp so i and i+1 are both valid
                bat_l = plot_battery[i]
                bat_r = plot_battery[i + 1]
                in_gap = (isinstance(bat_l, float) and math.isnan(bat_l)) or \
                         (isinstance(bat_r, float) and math.isnan(bat_r))
                if in_gap:
                    status_var.set(f"  Time: {t.strftime('%H:%M:%S')}    Battery: N/A    CPU: N/A")
                else:
                    # Snap to whichever bracketing point is closer
                    if abs((plot_times[i] - t).total_seconds()) <= abs((plot_times[i + 1] - t).total_seconds()):
                        pt, bat, cpu = plot_times[i], bat_l, plot_cpu[i]
                    else:
                        pt, bat, cpu = plot_times[i + 1], bat_r, plot_cpu[i + 1]
                    status_var.set(
                        f"  Time: {pt.strftime('%H:%M:%S')}    Battery: {bat:.1f}%    CPU: {cpu:.1f}%"
                    )

            canvas.mpl_connect('motion_notify_event', on_motion)

            def _close():
                if win in self._open_windows:
                    self._open_windows.remove(win)
                win.quit()  # exits mainloop; Tcl interpreter stays alive until win.destroy()

            win.protocol("WM_DELETE_WINDOW", _close)
            win.bind("<Escape>", lambda e: _close())
            win.focus_force()
            # Remove the minimize button via Windows API
            try:
                import ctypes
                GWL_STYLE    = -16
                WS_MINIMIZEBOX = 0x00020000
                win.update()  # ensure the window handle exists
                hwnd = int(win.frame(), 16)
                style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_STYLE)
                ctypes.windll.user32.SetWindowLongW(hwnd, GWL_STYLE, style & ~WS_MINIMIZEBOX)
            except Exception:
                pass
            win.mainloop()

            # mainloop has returned — we're still on this thread with the Tcl interpreter alive.
            # We must finalize ALL tkinter-linked objects (BooleanVar, StringVar, Image, etc.)
            # HERE, on this thread, BEFORE win.destroy() kills the interpreter.
            # Otherwise Python's cyclic GC may call Variable.__del__ later on a different
            # thread → "RuntimeError: main thread is not in main loop".
            import gc

            # 1. Patch filter_destroy to a no-op BEFORE nulling canvas.figure.
            #    filter_destroy (bound to the canvas widget's <Destroy> event by matplotlib)
            #    accesses canvas.figure._canvas_callbacks — if canvas.figure is already None
            #    it raises AttributeError.  Replacing the method on the instance means it
            #    can never crash regardless of when the <Destroy> event fires.
            try:
                canvas.filter_destroy = lambda event: None
            except Exception:
                pass
            try:
                # Use bind() to *replace* the <Destroy> callback with a no-op.
                # unbind() only removes widget-instance bindings; bind() overwrites
                # the callback regardless of how matplotlib registered it, so
                # filter_destroy can never run (and crash) after this point.
                canvas.get_tk_widget().bind('<Destroy>', lambda e: None)
            except Exception:
                pass

            # 2. Break circular references so CPython ref-counting can immediately collect:
            #    fig.canvas ↔ canvas.figure  and  toolbar.canvas ↔ canvas.toolbar
            for obj, attr in [(fig, 'canvas'), (canvas, 'toolbar'), (canvas, 'figure')]:
                try:
                    setattr(obj, attr, None)
                except Exception:
                    pass

            # 2. Destroy the toolbar widget — releases Tcl-side BooleanVar/Image resources
            #    so the Tcl interpreter no longer holds them.
            try:
                toolbar.destroy()
            except Exception:
                pass

            # 3. Drop all local Python references; with cycles broken, CPython's ref-counting
            #    finalizes Variable.__del__ immediately on this thread.
            try:
                del status_bar, status_var, toolbar, canvas, fig, ax
                del plot_times, plot_battery, plot_cpu
            except Exception:
                pass

            # 4. One GC pass to catch anything ref-counting missed.
            gc.collect()

            # 5. Now it's safe to destroy the interpreter — no live Python objects reference it.
            win.destroy()

        threading.Thread(target=_show, daemon=True).start()

    def open_settings(self, icon=None, item=None):
        if tk is None:
            self._notify("tkinter not available; cannot open settings.")
            return
        # open settings window in a separate thread so pystray loop isn't blocked
        def _open():
            win = SettingsWindow(None, self.config, on_save=self._on_config_save)
            self._open_windows.append(win.root)
            win.root.protocol("WM_DELETE_WINDOW", win.root.quit)
            win.root.mainloop()
            if win.root in self._open_windows:
                self._open_windows.remove(win.root)
            import gc
            gc.collect()
            win.root.destroy()

        threading.Thread(target=_open, daemon=True).start()

    def _on_config_save(self, cfg):
        self.config = cfg

    def exit(self, icon=None, item=None):
        self.stop_monitoring()
        # Close any open tkinter windows cleanly to avoid GC errors on daemon threads
        for win in list(self._open_windows):
            try:
                win.after(0, win.quit)  # quit exits mainloop; thread then does its own destroy
            except Exception:
                pass
        self._open_windows.clear()
        
        # Get battery info before stopping
        info = self._get_battery_info()

        threshold = int(self.config.get('threshold', 20))
        if self.config.get('telegram_enabled'):
            if info:
                exit_msg = f"⏹️ Monitoring stopped\n🔋 Battery {info['percent']}% (Alert at {threshold}%)\n{'🔌 Plugged' if info['plugged'] else '⚡ Unplugged'}"
            else:
                exit_msg = "⏹️ Monitoring stopped"
            try:
                send_telegram_async(exit_msg, conf=self.config.get('telegram_conf'))
                time.sleep(2.0)  # Give Telegram time to send
            except Exception as e:
                logging.error(f"Failed to send exit Telegram message: {e}")
        
        # Send exit notification
        if info:
            self._notify(f"⏹️ Monitoring stopped\n🔋 Battery {info['percent']}% (Alert at {threshold}%)\n{'🔌 Plugged' if info['plugged'] else '⚡ Unplugged'}")
        else:
            self._notify("⏹️ Monitoring stopped")
        
        time.sleep(1.0)  # Give notification time to display
        
        if self.icon:
            self.icon.stop()
        if self.wifi_icon:
            self.wifi_icon.stop()

    def run(self):
        if not pystray:
            print("pystray or PIL not installed. Install with: pip install pystray pillow")
            return
        try:
            # Run the WiFi icon in a daemon thread; the battery icon runs on the main thread.
            if self.wifi_icon:
                threading.Thread(target=self.wifi_icon.run, daemon=True).start()
            self.icon.run()
        except KeyboardInterrupt:
            self.exit()

    def _get_battery_info(self):
        if not psutil:
            return None
        try:
            bat = psutil.sensors_battery()
            if bat is None:
                return None
        except Exception as e:
            logging.error(f"Error getting battery info: {e}")
            return None
        secs = bat.secsleft
        if secs == psutil.POWER_TIME_UNKNOWN or secs == psutil.POWER_TIME_UNLIMITED:
            time_left = None
        else:
            hours = secs // 3600
            minutes = (secs % 3600) // 60
            time_left = f"{hours}h {minutes}m"
        return {"percent": bat.percent, "plugged": bat.power_plugged, "time_left": time_left}

    def _update_icon(self, percentage, plugged=False):
        """Update the battery tray icon with current percentage and charging status."""
        try:
            if self.icon and pystray:
                image = make_icon_image(size=512, percentage=percentage, plugged=plugged)
                self.icon.icon = image
        except Exception as e:
            logging.debug(f"Failed to update battery icon: {e}")

    def _update_wifi_icon(self, dbm):
        """Update the WiFi tray icon with current dBm value."""
        try:
            if self.wifi_icon and pystray:
                image = make_wifi_icon_image(size=512, dbm=dbm)
                if dbm is not None:
                    if dbm >= -55:
                        quality = "Excellent"
                    elif dbm >= -65:
                        quality = "Good"
                    elif dbm >= -75:
                        quality = "Fair"
                    else:
                        quality = "Poor"
                    status_line = f"WiFi: {dbm} dBm  ({quality})"
                else:
                    status_line = "WiFi: not connected"
                ranges = (
                    "\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\n"
                    "Signal ranges:\n"
                    "  \u2265 \u221255 dBm  \u2192  Excellent\n"
                    "  \u2265 \u221265 dBm  \u2192  Good\n"
                    "  \u2265 \u221275 dBm  \u2192  Fair\n"
                    "  < \u221275 dBm   \u2192  Poor"
                )
                self.wifi_icon.icon = image
                self.wifi_icon.title = f"{status_line}\n{ranges}"
        except Exception as e:
            logging.debug(f"Failed to update wifi icon: {e}")

    def _rotate_csv_logs(self):
        """Delete daily CSV and log files older than data_log_retention_days."""
        retention = int(self.config.get('data_log_retention_days', 30))
        cutoff = datetime.date.today() - datetime.timedelta(days=retention)
        try:
            for fname in os.listdir(CSV_LOG_DIR):
                if fname.startswith('battery_log_') and fname.endswith('.csv'):
                    date_part = fname[len('battery_log_'):-len('.csv')]
                elif fname.startswith('battery_monitor_') and fname.endswith('.log'):
                    date_part = fname[len('battery_monitor_'):-len('.log')]
                else:
                    continue
                try:
                    file_date = datetime.date.fromisoformat(date_part)
                except ValueError:
                    continue
                if file_date < cutoff:
                    fpath = os.path.join(CSV_LOG_DIR, fname)
                    try:
                        os.remove(fpath)
                        logging.info(f"Rotated old file: {fname}")
                    except Exception as e:
                        logging.warning(f"Could not remove {fname}: {e}")
        except Exception as e:
            logging.error(f"Failed to rotate logs: {e}")

    def _write_csv_row(self, timestamp, battery_percent, cpu_percent, charging):
        """Append a data row to today's dated CSV file, writing the header on first creation."""
        date_str = timestamp[:10]  # 'YYYY-MM-DD'
        csv_path = os.path.join(CSV_LOG_DIR, f'battery_log_{date_str}.csv')
        file_exists = os.path.isfile(csv_path)
        try:
            with open(csv_path, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(['timestamp', 'battery_percent', 'cpu_percent', 'charging'])
                writer.writerow([timestamp, battery_percent, cpu_percent, charging])
        except Exception as e:
            logging.error(f"Failed to write CSV log: {e}")

    def _build_graph_figure(self, date_str):
        """Load CSV data and build a matplotlib figure. Returns (fig, ax, plot_times, plot_battery, plot_cpu) or None."""
        if plt is None:
            logging.warning("matplotlib not available; skipping graph generation")
            return None
        csv_path = os.path.join(CSV_LOG_DIR, f'battery_log_{date_str}.csv')
        rows = []
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    rows.append(row)
        except FileNotFoundError:
            logging.info(f"No CSV file for {date_str}, skipping graph")
            return None
        except Exception as e:
            logging.error(f"Failed to read CSV for graph: {e}")
            return None
        if not rows:
            logging.info(f"No CSV data for {date_str}, skipping graph")
            return None
        try:
            import math
            times = [datetime.datetime.strptime(r['timestamp'], '%Y-%m-%d %H:%M:%S') for r in rows]
            battery = [float(r['battery_percent']) for r in rows]
            cpu = [float(r['cpu_percent']) for r in rows]
            charging = [str(r.get('charging', 'false')).strip().lower() in ('true', '1', 'yes') for r in rows]

            # Insert NaN breaks where the gap between consecutive points exceeds
            # 2× the data_log_interval (computer was likely asleep or stopped).
            gap_threshold_s = int(self.config.get('data_log_interval', 60)) * 2
            plot_times, plot_battery, plot_cpu = [], [], []
            for i in range(len(times)):
                plot_times.append(times[i])
                plot_battery.append(battery[i])
                plot_cpu.append(cpu[i])
                if i + 1 < len(times):
                    gap = (times[i + 1] - times[i]).total_seconds()
                    if gap > gap_threshold_s:
                        plot_times.append(times[i] + datetime.timedelta(seconds=gap / 2))
                        plot_battery.append(math.nan)
                        plot_cpu.append(math.nan)

            fig = matplotlib.figure.Figure(figsize=(14, 5))
            ax = fig.add_subplot(1, 1, 1)

            # Shade background: light yellow for discharging, light green for charging
            ax.set_facecolor('#fffde7')
            for i, ch in enumerate(charging):
                if ch:
                    t_start = times[i]
                    if i + 1 < len(times):
                        gap = (times[i + 1] - times[i]).total_seconds()
                        if gap > gap_threshold_s:
                            continue  # sleep/stop gap — don't draw misleading span
                        t_end = times[i + 1]
                    else:
                        t_end = times[i]
                    ax.axvspan(t_start, t_end, alpha=0.09, color='green')

            ax.plot(plot_times, plot_battery, label='Battery %', color='steelblue', linewidth=3.0)
            ax.plot(plot_times, plot_cpu, label='CPU %', color='tomato', linewidth=1.2, alpha=0.85)
            ax.set_ylim(0, 105)
            ax.set_ylabel('Percent (%)')
            ax.set_xlabel('Time')
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            fig.autofmt_xdate()
            legend_elements = [
                plt.Line2D([0], [0], color='steelblue', linewidth=3.0, label='Battery %'),
                plt.Line2D([0], [0], color='tomato', linewidth=1.2, label='CPU %'),
                Patch(facecolor='#fffde7', edgecolor='gray', alpha=0.9, label='Discharging'),
                Patch(facecolor='green', alpha=0.35, label='Charging'),
            ]
            ax.legend(handles=legend_elements, loc='upper right')
            ax.set_title(f'Battery & CPU — {date_str} — {HOSTNAME}')
            ax.set_xlim(times[0], times[-1])
            ax.grid(True, axis='y', alpha=0.3)
            ax.grid(True, axis='x', alpha=0.07)
            fig.tight_layout()
            return fig, ax, plot_times, plot_battery, plot_cpu
        except Exception as e:
            logging.error(f"Failed to build graph figure for {date_str}: {e}")
            return None

    def _generate_graph(self, date_str):
        """Generate a daily PNG graph for the given date (YYYY-MM-DD). Returns path or None."""
        result = self._build_graph_figure(date_str)
        if result is None:
            return None
        fig, ax, plot_times, plot_battery, plot_cpu = result
        try:
            graph_path = os.path.join(ROOT_DIR, f'battery_log_{date_str}.png')
            fig.savefig(graph_path, dpi=100)
            return graph_path
        except Exception as e:
            logging.error(f"Failed to save graph for {date_str}: {e}")
            return None
        finally:
            fig.clf()

    def _send_graph_telegram(self, graph_path, date_str):
        """Send the daily graph image via Telegram."""
        if not self.config.get('telegram_enabled'):
            return
        if not graph_path or not os.path.isfile(graph_path):
            return
        import asyncio
        caption = f"[{HOSTNAME}] 📊 Daily battery & CPU report for {date_str}"
        conf = _resolve_telegram_conf(self.config.get('telegram_conf'))
        try:
            async def _send():
                with open(graph_path, 'rb') as f:
                    if conf:
                        await telegram_send.send(images=[f], captions=[caption], conf=conf)
                    else:
                        await telegram_send.send(images=[f], captions=[caption])
            asyncio.run(_send())
        except Exception as e:
            logging.error(f"Failed to send graph via Telegram: {e}")

    def _generate_and_send_graph(self, date_str):
        """Generate the daily graph and send it via Telegram."""
        graph_path = self._generate_graph(date_str)
        if graph_path:
            self._send_graph_telegram(graph_path, date_str)

    def _check_disk_space(self):
        """Check all local fixed drives and send a Telegram alert for any at/above the threshold."""
        if not psutil:
            return
        threshold = int(self.config.get('disk_alert_threshold', 90))
        conf = self.config.get('telegram_conf')
        try:
            for part in psutil.disk_partitions(all=False):
                # Skip optical drives and network mounts; only physical/local drives
                if 'cdrom' in part.opts or part.fstype == '':
                    continue
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                except (PermissionError, OSError):
                    continue
                pct = usage.percent
                free_gb = usage.free / (1024 ** 3)
                total_gb = usage.total / (1024 ** 3)
                drive = part.device.rstrip('\\').rstrip('/')
                logging.info(f"Disk check: {drive} at {pct:.1f}%")
                if pct >= threshold:
                    msg = f"{ALERT_BORDER}\n💾 Drive {drive} at {pct:.0f}% (Threshold alert {threshold}%) - {free_gb:.1f} GB free of {total_gb:.0f} GB\n{ALERT_BORDER}"
                    logging.warning(msg)
                    if self.config.get('telegram_enabled'):
                        send_telegram_async(msg, conf=conf)
                    self._notify(msg)
        except Exception as e:
            logging.error(f"Failed to check disk space: {e}")

    def _monitor_loop(self):
        icon_update_counter = 0
        wifi_poll_counter = 0
        WIFI_POLL_INTERVAL = 5  # poll WiFi every 5 loop iterations (= seconds when interval=1)
        while not self._stop_event.is_set():
            # refresh config each loop in case user changed settings
            cfg = load_config()
            self.config.update(cfg)
            interval = int(self.config.get('interval', 1))
            threshold = int(self.config.get('threshold', 20))
            resend_minutes = int(self.config.get('resend_minutes', 5))
            resend_seconds = resend_minutes * 60

            info = self._get_battery_info()
            if info:
                percent = info['percent']
                plugged = info['plugged']
                time_left = info.get('time_left')
                now = time.time()

                # Midnight rollover detection — generate graph for completed day
                today = datetime.date.today()
                if self._current_day is not None and today != self._current_day:
                    completed_day = self._current_day.strftime('%Y-%m-%d')
                    threading.Thread(target=self._generate_and_send_graph, args=(completed_day,), daemon=True).start()
                    threading.Thread(target=self._rotate_csv_logs, daemon=True).start()
                    setup_logging(self.config.get('logging_enabled', False))
                self._current_day = today

                # Daily disk space check
                if self.config.get('disk_alert_enabled', True):
                    disk_alert_time_str = self.config.get('disk_alert_time', '07:00')
                    try:
                        h, m = map(int, disk_alert_time_str.split(':'))
                        now_dt = datetime.datetime.now()
                        alert_dt = now_dt.replace(hour=h, minute=m, second=0, microsecond=0)
                        if now_dt >= alert_dt and self._disk_alert_sent_date != today:
                            self._disk_alert_sent_date = today
                            threading.Thread(target=self._check_disk_space, daemon=True).start()
                    except Exception as e:
                        logging.error(f"Disk alert time parse error: {e}")

                # CSV logging
                data_log_interval = int(self.config.get('data_log_interval', 60))
                if (self._last_csv_time is None) or ((now - self._last_csv_time) >= data_log_interval):
                    # Use interval=1 on the first call so psutil has a real time window to measure;
                    # interval=None on subsequent calls uses the delta from the previous call.
                    cpu_interval = 1 if self._last_csv_time is None else None
                    cpu_percent = psutil.cpu_percent(interval=cpu_interval) if psutil else 0.0
                    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    self._write_csv_row(timestamp, percent, cpu_percent, plugged)
                    self._last_csv_time = now

                # Update battery icon
                self._update_icon(percent, plugged=plugged)

                # Poll WiFi every WIFI_POLL_INTERVAL seconds and update the wifi tray icon
                wifi_poll_counter += 1
                if wifi_poll_counter >= WIFI_POLL_INTERVAL:
                    wifi_poll_counter = 0
                    dbm, _pct = _get_wifi_dbm()
                    self._wifi_dbm = dbm
                    self._update_wifi_icon(dbm)
                
                if (not plugged) and (percent <= threshold):
                    # Enter low state and send (or resend) low-battery alert
                    if (self._last_alert_time is None) or ((now - self._last_alert_time) >= resend_seconds):
                        msg = f"{ALERT_BORDER}\n🪫 Battery low: {percent}% (Alert at {threshold}%)\n⚡ Unplugged"
                        if time_left:
                            msg += f"\n⏱️ ~{time_left} remaining"
                        msg += f"\n{ALERT_BORDER}"
                        if self.config.get('telegram_enabled'):
                            send_telegram_async(msg, conf=self.config.get('telegram_conf'))
                        self._notify(msg)
                        self._last_alert_time = now
                    # record when low state started
                    if self._low_start_time is None:
                        self._low_start_time = now
                    self._was_low = True
                else:
                    # not currently low (either plugged or percent > threshold)
                    if self._was_low and ((percent > threshold) or plugged):
                        # recovered from low -> notify, include time low
                        duration = None
                        if self._low_start_time is not None:
                            duration = int(now - self._low_start_time)
                        if duration is not None:
                            mins = duration // 60
                            secs = duration % 60
                            dur_text = f"Was low for {mins}m {secs}s"
                        else:
                            dur_text = ""
                        rec_msg = f"� Battery recovered: {percent}% (Alert at {threshold}%)"
                        if dur_text:
                            rec_msg += f"\n{dur_text}"
                        if self.config.get('telegram_enabled'):
                            send_telegram_async(rec_msg, conf=self.config.get('telegram_conf'))
                        self._notify(rec_msg)
                    if plugged:
                        # if plugged we also clear low state and last alert
                        self._was_low = False
                        self._last_alert_time = None
                        self._low_start_time = None
                    else:
                        # still not low (but not plugged) -> clear low state
                        if percent > threshold:
                            self._was_low = False
                            self._low_start_time = None

            for _ in range(int(interval)):
                if self._stop_event.is_set():
                    break
                time.sleep(1)

    def _disk_summary_lines(self):
        """Return a list of strings like 'C: at 89.7% - 95.8 GB free of 929 GB' for all local drives."""
        if not psutil:
            return []
        lines = []
        try:
            for part in psutil.disk_partitions(all=False):
                if 'cdrom' in part.opts or part.fstype == '':
                    continue
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                except (PermissionError, OSError):
                    continue
                drive = part.device.rstrip('\\').rstrip('/')
                pct = usage.percent
                free_gb = usage.free / (1024 ** 3)
                total_gb = usage.total / (1024 ** 3)
                lines.append(f"💾 Drive {drive} at {pct:.1f}% - {free_gb:.1f} GB free of {total_gb:.0f} GB")
        except Exception as e:
            logging.error(f"Failed to get disk summary: {e}")
        return lines

    def _notify(self, message):
        try:
            from plyer import notification
            notification.notify(title="Battery Monitor", message=message, timeout=5)
            return
        except Exception as e:
            logging.debug(f"Failed to use plyer notification: {e}")

        try:
            if self.icon:
                self.icon.notify(message)
                return
        except Exception as e:
            logging.debug(f"Failed to use pystray notification: {e}")
        print(message)


if __name__ == '__main__':
    cfg = load_config()
    monitor = TrayMonitor(config=cfg)
    # start monitoring automatically on launch
    monitor.start_monitoring()
    
    # Send startup Telegram message then graphs (in order) in one thread
    if cfg.get('telegram_enabled'):
        info = monitor._get_battery_info()
        threshold = int(cfg.get('threshold', 20))
        now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if info:
            startup_msg = f"▶️ Battery Monitor v{__version__} \u2014 {now_str}\n\n🔋 Battery {info['percent']}% (Alert at {threshold}%)\n{'🔌 Plugged' if info['plugged'] else '⚡ Unplugged'}"
            if info.get('time_left'):
                startup_msg += f"\n⏱️ ~{info['time_left']} remaining"
        else:
            startup_msg = f"▶️ Battery Monitor v{__version__} \u2014 {now_str}"
        disk_lines = monitor._disk_summary_lines()
        if disk_lines:
            startup_msg += "\n" + "\n".join(disk_lines)
        yesterday = (datetime.date.today() - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
        today_str = datetime.date.today().strftime('%Y-%m-%d')
        def _send_startup():
            send_telegram_async(startup_msg, conf=cfg.get('telegram_conf'))
            monitor._generate_and_send_graph(yesterday)
            monitor._generate_and_send_graph(today_str)
        threading.Thread(target=_send_startup, daemon=True).start()
    
    monitor.run()