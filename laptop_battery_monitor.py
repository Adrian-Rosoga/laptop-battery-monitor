"""
Tray-controlled background monitor for Windows 11.

This script creates a system tray icon with a menu to Start/Stop the background
monitoring thread, Show Status, and Exit. The background task polls battery
information using `psutil` as an example workload.

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

try:
    import psutil
except Exception:
    psutil = None

try:
    import pystray
    from PIL import Image, ImageDraw, ImageFont
except Exception:
    pystray = None

try:
    import telegram_send
except Exception:
    telegram_send = None

try:
    import tkinter as tk
    from tkinter import messagebox
except Exception:
    tk = None

__version__ = "1.1"
HOSTNAME = socket.gethostname()

# Determine ROOT_DIR based on whether running as executable or script
if getattr(sys, 'frozen', False):
    # Running as a PyInstaller executable
    ROOT_DIR = os.path.dirname(sys.executable)
else:
    # Running as a Python script
    ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_PATH = os.path.join(ROOT_DIR, "monitor_config.json")


def make_icon_image(size=128, color1=(0, 122, 204), color2=(255, 255, 255), percentage=None, plugged=False):
    """Generate a simple square icon with a battery-like glyph and optional percentage text.
    
    Args:
        size: Icon size in pixels
        color1: Primary color (unused, kept for compatibility)
        color2: Secondary color (unused, kept for compatibility)
        percentage: Battery percentage to display
        plugged: Whether the laptop is charging (True = light green, False = light yellow)
    """
    image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    
    # Draw background based on charging status
    # Light green (144, 238, 144) if charging, light yellow (255, 255, 0) if not
    bg_color = (144, 238, 144, 255) if plugged else (255, 255, 0, 255)
    draw.rectangle((0, 0, size, size), fill=bg_color)
    
    # draw.ellipse((0, 0, size, size), fill=color1)
    # pad = size // 6
    # left = pad
    # top = pad * 2
    # right = size - pad
    # bottom = size - pad * 2
    # draw.rectangle((left, top, right - pad // 2, bottom), fill=color2)
    # draw.rectangle((right - pad // 2, top + (pad // 2), right, bottom - (pad // 2)), fill=color2)
    
    # Draw percentage text if provided
    if percentage is not None:
        try:
            # Try to use a bold system font with larger size to fill the icon
            font_size = int(size * 0.7)
            # Try common system fonts
            font = None
            for font_name in ['arial.ttf', 'ariblk.ttf', 'arial black.ttf', 'calibrib.ttf']:
                try:
                    font = ImageFont.truetype(font_name, font_size)
                    break
                except Exception:
                    try:
                        font = ImageFont.truetype(f"C:\\Windows\\Fonts\\{font_name}", font_size)
                        break
                    except Exception:
                        continue
            
            if font is None:
                # Fallback to default font if no TTF found
                try:
                    font = ImageFont.load_default()
                except Exception:
                    font = None
            
            if font:
                text = f"{int(percentage)}"
                bbox = draw.textbbox((0, 0), text, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                x = (size - text_width) // 2
                y = (size - text_height) // 2
                # Draw text in red
                draw.text((x, y), text, fill=(255, 0, 0, 255), font=font)
        except Exception:
            pass
    
    return image


DEFAULT_CONFIG = {
    "threshold": 20,
    "interval": 1,
    "telegram_enabled": False,
    "telegram_conf": None
}
DEFAULT_CONFIG["resend_minutes"] = 5


def load_config():
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
            DEFAULT_CONFIG.update(cfg)
    except Exception:
        pass
    return dict(DEFAULT_CONFIG)


def save_config(cfg):
    try:
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        print("Failed to save config:", e)


def send_telegram_async_NOT_SENDING(message, conf=None):
    """Send telegram message in background if telegram_send is available."""
    if telegram_send is None:
        print("telegram_send not installed; message:", message)
        return

    def _send():
        try:
            if conf:
                telegram_send.send(messages=[message], conf=conf)
            else:
                telegram_send.send(messages=[message])
        except Exception as e:
            print("Failed to send telegram message:", e)

    threading.Thread(target=_send, daemon=True).start()


def send_telegram_async(message, conf=None):
    import asyncio
    full = f"[{HOSTNAME}] {message}"
    if conf:
        asyncio.run(telegram_send.send(messages=[full], conf=conf))
    else:
        asyncio.run(telegram_send.send(messages=[full]))


class SettingsWindow:
    def __init__(self, parent, config, on_save=None):
        self.parent = parent
        self.config = config
        self.on_save = on_save
        if tk is None:
            raise RuntimeError("tkinter not available")

        self.root = tk.Tk()
        self.root.title("Battery Monitor Settings")
        self.root.geometry("320x300")

        tk.Label(self.root, text="Low battery threshold (%)").pack(anchor='w', padx=8, pady=(8, 0))
        self.threshold_var = tk.StringVar(value=str(self.config.get('threshold', 20)))
        tk.Entry(self.root, textvariable=self.threshold_var).pack(fill='x', padx=8)

        tk.Label(self.root, text="Check interval (s)").pack(anchor='w', padx=8, pady=(8, 0))
        self.interval_var = tk.StringVar(value=str(self.config.get('interval', 1)))
        tk.Entry(self.root, textvariable=self.interval_var).pack(fill='x', padx=8)

        self.telegram_var = tk.BooleanVar(value=bool(self.config.get('telegram_enabled')))
        tk.Checkbutton(self.root, text="Enable Telegram alerts", variable=self.telegram_var).pack(anchor='w', padx=8, pady=(8, 0))

        tk.Label(self.root, text="telegram-send config file (optional)").pack(anchor='w', padx=8, pady=(8, 0))
        self.telegram_conf_var = tk.StringVar(value=str(self.config.get('telegram_conf') or ""))
        tk.Entry(self.root, textvariable=self.telegram_conf_var).pack(fill='x', padx=8)
        
        tk.Label(self.root, text="Resend Low-Battery Telegram alert every (minutes)").pack(anchor='w', padx=8, pady=(8, 0))
        self.resend_var = tk.StringVar(value=str(self.config.get('resend_minutes', 5)))
        tk.Entry(self.root, textvariable=self.resend_var).pack(fill='x', padx=8)

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
            self.config['telegram_enabled'] = bool(self.telegram_var.get())
            conf = self.telegram_conf_var.get().strip()
            self.config['telegram_conf'] = conf if conf else None
            save_config(self.config)
            if self.on_save:
                self.on_save(self.config)
            save_message = f"Settings saved to:\n{CONFIG_PATH}"
            messagebox.showinfo("Settings", save_message)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def test_telegram(self):
        if not self.config.get('telegram_enabled'):
            messagebox.showwarning("Telegram", "Telegram is not enabled in settings")
            return
        msg = f"Test from {HOSTNAME}"
        send_telegram_async(msg, conf=self.config.get('telegram_conf'))
        messagebox.showinfo("Telegram", "Test message sent (if configured)")

    def close(self):
        self.root.destroy()


class TrayMonitor:
    def __init__(self, config=None):
        self.config = config or load_config()
        self._thread = None
        self._stop_event = threading.Event()
        self._last_alert_time = None
        self._low_start_time = None
        self._was_low = False
        self._running = False

        self.icon = None
        if pystray:
            image = make_icon_image(size=512, percentage=100, plugged=True)
            menu = pystray.Menu(
                pystray.MenuItem('Monitoring Enabled', self.toggle_monitoring, checked=lambda item: self._running),
                pystray.MenuItem('Show Status', self.show_status),
                pystray.MenuItem('Settings', self.open_settings),
                pystray.MenuItem('About', self.show_about),
                pystray.MenuItem('Exit', self.exit)
            )
            self.icon = pystray.Icon(f"monitor_{HOSTNAME}", image, f"Battery Monitor: {HOSTNAME}", menu)

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
        self._notify(f"Monitoring started on {HOSTNAME}")

    def stop_monitoring(self, icon=None, item=None):
        if not self._running:
            return
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)
        self._running = False
        self._notify(f"Monitoring stopped on {HOSTNAME}")

    def show_status(self, icon=None, item=None):
        status = "Running" if self._running else "Stopped"
        info = self._get_battery_info() if psutil else None
        msg = f"{HOSTNAME}: {status}"
        if info:
            msg += f" — Battery {info['percent']}% {'(plugged)' if info['plugged'] else ''}"
        # include time since last low-battery alert if available
        try:
            last = self._last_alert_time
            if last is not None:
                secs = int(time.time() - last)
                mins = secs // 60
                s = secs % 60
                msg += f" — last alert: {mins}m {s}s ago"
        except Exception:
            pass
        self._notify(msg)

    def show_about(self, icon=None, item=None):
        """Show About dialog with clickable GitHub link."""
        if tk is None:
            self._notify("tkinter not available; cannot open About dialog.")
            return
        
        def _show_about():
            about_window = tk.Tk()
            about_window.title("About")
            about_window.geometry("400x220")
            about_window.resizable(False, False)
            
            # Title and version
            title_label = tk.Label(about_window, text=f"Laptop Battery Monitor v{__version__}", font=("Arial", 12, "bold"))
            title_label.pack(pady=10)
            
            # Description
            desc_label = tk.Label(about_window, text="Monitors battery status and sends Telegram alerts when low.\nConfigurable threshold, interval, and Telegram integration.", justify=tk.CENTER)
            desc_label.pack(pady=5)
            
            # Clickable GitHub link
            def open_github():
                import webbrowser
                webbrowser.open("https://github.com/Adrian-Rosoga/laptop-battery-monitor")
            
            github_link = tk.Label(about_window, text="GitHub Repository", fg="blue", cursor="hand2", font=("Arial", 10, "underline"))
            github_link.pack(pady=5)
            github_link.bind("<Button-1>", lambda e: open_github())
            
            # Credits
            credits_label = tk.Label(about_window, text="Adrian Rosoga (actually GPT-5 mini and Claude Haiku 4.5)\nFebruary 2026", font=("Arial", 9))
            credits_label.pack(pady=10)
            
            # Close button
            close_button = tk.Button(about_window, text="Close", command=about_window.destroy)
            close_button.pack(pady=10)
            
            about_window.mainloop()
        
        threading.Thread(target=_show_about, daemon=True).start()

    def open_settings(self, icon=None, item=None):
        if tk is None:
            self._notify("tkinter not available; cannot open settings.")
            return
        # open settings window in a separate thread so pystray loop isn't blocked
        def _open():
            win = SettingsWindow(None, self.config, on_save=self._on_config_save)
            win.root.mainloop()

        threading.Thread(target=_open, daemon=True).start()

    def _on_config_save(self, cfg):
        self.config = cfg

    def exit(self, icon=None, item=None):
        self.stop_monitoring()
        
        # Send exit Telegram message if enabled
        if self.config.get('telegram_enabled'):
            exit_msg = f"Monitoring stopped on {HOSTNAME}"
            send_telegram_async(exit_msg, conf=self.config.get('telegram_conf'))
        
        if self.icon:
            self.icon.stop()

    def run(self):
        if not pystray:
            print("pystray or PIL not installed. Install with: pip install pystray pillow")
            return
        try:
            self.icon.run()
        except KeyboardInterrupt:
            self.exit()

    def _get_battery_info(self):
        if not psutil:
            return None
        bat = psutil.sensors_battery()
        if bat is None:
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
        """Update the tray icon with current battery percentage and charging status."""
        try:
            if self.icon and pystray:
                image = make_icon_image(size=512, percentage=percentage, plugged=plugged)
                self.icon.icon = image
        except Exception:
            pass

    def _monitor_loop(self):
        icon_update_counter = 0
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
                now = time.time()
                
                # Update icon with battery percentage and charging status
                self._update_icon(percent, plugged=plugged)
                
                if (not plugged) and (percent <= threshold):
                    # Enter low state and send (or resend) low-battery alert
                    if (self._last_alert_time is None) or ((now - self._last_alert_time) >= resend_seconds):
                        msg = f"Battery low on {HOSTNAME}: {percent}%"
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
                    if self._was_low and (percent > threshold):
                        # recovered from low -> notify, include time low
                        duration = None
                        if self._low_start_time is not None:
                            duration = int(now - self._low_start_time)
                        if duration is not None:
                            mins = duration // 60
                            secs = duration % 60
                            dur_text = f"was low for {mins}m {secs}s"
                        else:
                            dur_text = ""
                        rec_msg = f"Battery recovered on {HOSTNAME}: {percent}%"
                        if dur_text:
                            rec_msg += f" — {dur_text}"
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

    def _notify(self, message):
        try:
            from plyer import notification
            notification.notify(title="Battery Monitor", message=message, timeout=5)
            return
        except Exception:
            pass

        try:
            if self.icon:
                self.icon.notify(message)
                return
        except Exception:
            pass
        print(message)


if __name__ == '__main__':
    cfg = load_config()
    monitor = TrayMonitor(config=cfg)
    # start monitoring automatically on launch
    monitor.start_monitoring()
    
    # Send startup Telegram message if enabled
    if cfg.get('telegram_enabled'):
        startup_msg = f"Monitoring started on {HOSTNAME}"
        send_telegram_async(startup_msg, conf=cfg.get('telegram_conf'))
    
    monitor.run()
