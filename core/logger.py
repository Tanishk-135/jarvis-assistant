import time
import os
import subprocess
import psutil
from datetime import datetime
from pynput import keyboard, mouse
import pygetwindow as gw
import pyautogui

# 📁 Setup paths
today_str = datetime.now().strftime("%Y-%m-%d")
log_folder = "E:/Personalized AI/data/raw"
screenshot_folder = f"E:/Personalized AI/data/screenshots/{today_str}"
log_file = os.path.join(log_folder, f"activity_log_{today_str}.txt")

os.makedirs(log_folder, exist_ok=True)
os.makedirs(screenshot_folder, exist_ok=True)

# 📅 Init log file if needed
if not os.path.exists(log_file):
    with open(log_file, "w", encoding="utf-8") as f:
        f.write("# Log started for this session\n")
    print(f"✅ Log created: {log_file}")
else:
    print(f"✅ Log already exists: {log_file}")

# 🚁 Interaction tracker
last_input_time = time.time()
last_logged_app = ""
last_logged_state = ""
last_screenshot_time = 0

def on_press(key):
    global last_input_time
    last_input_time = time.time()

def on_click(x, y, button, pressed):
    if pressed:
        global last_input_time
        last_input_time = time.time()

keyboard.Listener(on_press=on_press).start()
mouse.Listener(on_click=on_click).start()

# 🚪 Active window on PC
def get_active_window():
    try:
        return gw.getActiveWindow().title
    except:
        return "Unknown"

# 🔍 Classify state
def classify_state():
    idle_seconds = time.time() - last_input_time
    active_app = get_active_window()
    return ("idle", active_app) if idle_seconds > 600 else ("active", active_app)

# 📱 Detect phone activity via ADB
def get_foreground_app_phone():
    try:
        result = subprocess.check_output(
            ["adb", "shell", "dumpsys", "window", "windows"],
            stderr=subprocess.DEVNULL
        ).decode("utf-8").lower()

        for line in result.splitlines():
            if "mCurrentFocus" in line or "mFocusedApp" in line:
                parts = line.strip().split("/")
                if len(parts) > 1:
                    return parts[0].split()[-1]  # package name
        return None
    except Exception as e:
        print("[ADB Error] Could not get phone app:", e)
        return None

# 📸 Screenshot

def take_screenshot(app):
    ts = datetime.now().strftime("%H-%M-%S")
    safe_name = "".join(c for c in app if c.isalnum() or c in (" ", "_", "-")).strip()
    filename = f"{ts}__{safe_name}.png"
    filepath = os.path.join(screenshot_folder, filename)
    try:
        pyautogui.screenshot(filepath)
    except Exception as e:
        print(f"[Screenshot Error] {e}")

# 🧰 Logger

def log_event(state, pc_app, phone_app, force_snapshot=False):
    global last_screenshot_time
    now = datetime.now()
    now_str = now.strftime("[%I:%M %p]")

    with open(log_file, "a", encoding="utf-8") as f:
        if state == "idle":
            f.write(f"{now_str} Idle for 10+ min\n")
        else:
            if last_logged_state == "idle":
                f.write(f"{now_str} Back active: PC=\"{pc_app}\" | Phone=\"{phone_app}\"\n")
            elif pc_app != last_logged_app:
                f.write(f"{now_str} Switched PC App: \"{pc_app}\" | Phone=\"{phone_app}\"\n")
            elif force_snapshot:
                f.write(f"{now_str} Snapshot: \"{pc_app}\" | Phone=\"{phone_app}\"\n")
            else:
                f.write(f"{now_str} Active: \"{pc_app}\" | Phone=\"{phone_app}\"\n")

    if force_snapshot or pc_app != last_logged_app:
        take_screenshot(pc_app)
        last_screenshot_time = time.time()

# 🔄 Main loop
while True:
    state, pc_app = classify_state()
    phone_app = get_foreground_app_phone() or "None"
    now = time.time()

    should_snapshot = (state == "active") and ((now - last_screenshot_time) >= 60)

    if (
        state != last_logged_state or
        pc_app != last_logged_app or
        should_snapshot
    ):
        log_event(state, pc_app, phone_app, force_snapshot=should_snapshot)
        last_logged_state = state
        last_logged_app = pc_app

    time.sleep(10)
