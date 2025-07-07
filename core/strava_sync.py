import json
from datetime import datetime, timedelta
import re
import os
import subprocess
import pytesseract
from PIL import Image
import time
from pathlib import Path

file_path = Path("E:/Jarvis/health_logs/health_data.json")
package_name = "com.ido.noise"

# Path to Tesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def extract_stress_info_from_full_image(screenshot_path: str):
    try:
        # Load full image
        img = Image.open(screenshot_path)

        # OCR the whole image
        ocr = pytesseract.image_to_string(img)
        print("[DEBUG] Full OCR for STRESS:\n", ocr)

        # Match "Average 31" or "Avg: 31" or "31 Normal"
        avg_match = re.search(r"Average\s+(\d{1,3})", ocr, re.IGNORECASE)
        if not avg_match:
            avg_match = re.search(r"Avg(?:erage)?\s*[:\-]?\s*(\d{1,3})", ocr, re.IGNORECASE)
        if not avg_match:
            avg_match = re.search(r"\b(\d{1,3})\s+Normal\b", ocr, re.IGNORECASE)

        # Match range like "15–56", "15 - 56", or "15~56"
        range_match = re.search(r"(\d{1,3})\s*[-–~]\s*(\d{1,3})", ocr)

        # Extract values
        avg = int(avg_match.group(1)) if avg_match else None
        low = int(range_match.group(1)) if range_match else None
        high = int(range_match.group(2)) if range_match else None

        # Fallback: estimate average if not found but range is available
        if avg is None and low is not None and high is not None:
            avg = round((low + high) / 2)

        return str(avg) if avg is not None else "?", f"{low}–{high}" if low and high else "?"

    except Exception as e:
        print(f"[ERROR] Failed to extract stress info: {e}")
        return "?", "?"


def pull_and_read_screen(screen_type: str, label: str = "the screen") -> str:
    os.system("adb shell screencap -p /sdcard/ss_temp.png")
    os.system("adb pull /sdcard/ss_temp.png")
    img = Image.open("ss_temp.png")
    ocr_text = pytesseract.image_to_string(img)
    print(f"\n[DEBUG] OCR for {label.upper()}:\n{ocr_text}\n{'-' * 40}")
    return ocr_text


def extract_heart_data(text):
    bpm_avg = re.search(r"Average\s+(\d+)", text)
    bpm_range = re.search(r"(\d{2,3})-(\d{2,3})\s*bpm", text)
    
    return {
        "avg_bpm": int(bpm_avg.group(1)) if bpm_avg else None,
        "min_bpm": int(bpm_range.group(1)) if bpm_range else None,
        "max_bpm": int(bpm_range.group(2)) if bpm_range else None
    }

def extract_stress_data(ocr_text):
    lines = ocr_text.splitlines()
    avg_stress = "?"
    min_stress = "?"
    max_stress = "?"

    for i, line in enumerate(lines):
        # Look for the "Average Min. ~ Max." line
        if "Average" in line and ("Min" in line or "~" in line):
            # Check next line
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                nums = re.findall(r"\d{2,3}", next_line)
                if nums:
                    avg_stress = nums[0]

        # Look for range anywhere
        if re.search(r"(\d+)\s*[-~]\s*(\d+)", line):
            match = re.search(r"(\d+)\s*[-~]\s*(\d+)", line)
            if match:
                min_stress = match.group(1)
                max_stress = match.group(2)

    return {
        "avg_stress": int(avg_stress) if avg_stress.isdigit() else None,
        "min_stress": int(min_stress) if min_stress.isdigit() else None,
        "max_stress": int(max_stress) if max_stress.isdigit() else None
    }

def extract_sleep_data(text):
    bedtime = re.search(r"Bedtime\s+(\d{1,2}:\d{2}\s*[AP]M)", text)
    wake_time = re.search(r"Wake-up time\s+(\d{1,2}:\d{2}\s*[AP]M)", text)
    
    return {
        "bedtime": bedtime.group(1) if bedtime else "?",
        "wake_time": wake_time.group(1) if wake_time else "?"
    }

def wait_until_noisefit_detected(timeout_seconds=60):
    print("[*] Waiting for NoiseFit Assist to be active...")
    start_time = time.time()
    
    while time.time() - start_time < timeout_seconds:
        if noisefit_is_open():
            return True
        else:
            print("[x] Not detected. Retrying...")

    print("[!] Timeout reached. Could not detect NoiseFit Assist.")
    return False

def noisefit_is_open():
    take_screenshot("check.png")
    text = ocr_text("check.png")
    print("[OCR Check] Text:", text[:200])  # Print partial text for debug
    return "NoiseFit Assist" in text

log_folder = Path("health_logs")
log_folder.mkdir(exist_ok=True)
DATA_FILE = log_folder / "health_data.json"

def update_health_data(date_str, heart, stress, sleep=None):
    # Load existing data or start fresh
    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {}

    # Ensure key exists
    if date_str not in data:
        data[date_str] = {}

    # Update heart and stress if available
    if heart:
        data[date_str].update({
            "avg_bpm": heart.get("avg_bpm"),
            "min_bpm": heart.get("min_bpm"),
            "max_bpm": heart.get("max_bpm"),
        })
    if stress:
        data[date_str].update({
            "avg_stress": stress.get("avg_stress"),
            "min_stress": stress.get("min_stress"),
            "max_stress": stress.get("max_stress"),
        })
    if sleep:
        data[date_str].update({
            "sleep_duration": sleep.get("duration"),
            "bedtime": sleep.get("bedtime"),
            "wakeup": sleep.get("wakeup")
        })

    # Save updated data
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

    return data


from datetime import datetime, timedelta

def compute_sleep_duration(bedtime: str, wake_time: str) -> str:
    try:
        fmt = "%I:%M %p"  # Format: 01:19 AM

        bed_dt = datetime.strptime(bedtime, fmt)
        wake_dt = datetime.strptime(wake_time, fmt)

        # Handle overnight sleep
        if wake_dt <= bed_dt:
            wake_dt += timedelta(days=1)

        duration = wake_dt - bed_dt
        hours = duration.seconds // 3600
        minutes = (duration.seconds % 3600) // 60

        return f"{hours}h {minutes}m"
    except Exception as e:
        print(f"[ERROR] Failed to compute duration from '{bedtime}' to '{wake_time}': {e}")
        return "?"

    except Exception as e:
        print(f"[ERROR] Failed to compute sleep duration: {e}")
        return "?"

def merge_sleep_data(today: dict, yesterday: dict) -> dict:
    bedtime = today.get("bedtime") or yesterday.get("bedtime")
    wakeup = today.get("wakeup") or yesterday.get("wakeup")
    duration = compute_sleep_duration(bedtime, wakeup)
    print(f"[DEBUG] Bedtime: {bedtime}, Wakeup: {wakeup}, Duration: {duration}")

    
    return {
        "duration": duration,
        "bedtime": bedtime,
        "wakeup": wakeup,
    }

def compute_overall_stats(data):
    avg_bpm_list = []
    min_bpm_list = []
    max_bpm_list = []

    avg_stress_list = []
    min_stress_list = []
    max_stress_list = []

    for entry in data.values():
        if entry["avg_bpm"]: avg_bpm_list.append(entry["avg_bpm"])
        if entry["min_bpm"]: min_bpm_list.append(entry["min_bpm"])
        if entry["max_bpm"]: max_bpm_list.append(entry["max_bpm"])
        if entry["avg_stress"]: avg_stress_list.append(entry["avg_stress"])
        if entry["min_stress"]: min_stress_list.append(entry["min_stress"])
        if entry["max_stress"]: max_stress_list.append(entry["max_stress"])

    return {
        "overall_avg_bpm": sum(avg_bpm_list) // len(avg_bpm_list) if avg_bpm_list else "?",
        "overall_min_bpm": min(min_bpm_list) if min_bpm_list else "?",
        "overall_max_bpm": max(max_bpm_list) if max_bpm_list else "?",
        "overall_avg_stress": sum(avg_stress_list) // len(avg_stress_list) if avg_stress_list else "?",
        "overall_min_stress": min(min_stress_list) if min_stress_list else "?",
        "overall_max_stress": max(max_stress_list) if max_stress_list else "?",
    }

def merge_heart_data(today: dict, yesterday: dict) -> dict:
    def safe_int(val):
        return int(val) if val and str(val).isdigit() else None

    avg_list = [safe_int(today.get("avg_bpm")), safe_int(yesterday.get("avg_bpm"))]
    avg_list = [x for x in avg_list if x is not None]
    avg_bpm = sum(avg_list) // len(avg_list) if avg_list else None

    min_bpm = min([x for x in [safe_int(today.get("min_bpm")), safe_int(yesterday.get("min_bpm"))] if x is not None], default=None)
    max_bpm = max([x for x in [safe_int(today.get("max_bpm")), safe_int(yesterday.get("max_bpm"))] if x is not None], default=None)

    return {
        "avg_bpm": avg_bpm,
        "min_bpm": min_bpm,
        "max_bpm": max_bpm,
    }

def merge_stress_data(today, yesterday):
    return {
        "avg_stress": int((today["avg_stress"] + yesterday["avg_stress"]) / 2) if today["avg_stress"] and yesterday["avg_stress"] else today["avg_stress"] or yesterday["avg_stress"],
        "min_stress": min(filter(None, [today["min_stress"], yesterday["min_stress"]])),
        "max_stress": max(filter(None, [today["max_stress"], yesterday["max_stress"]])),
    }

def adb(cmd):
    os.system(f"adb shell {cmd}")

def tap(x, y):
    os.system(f"adb shell input tap {x} {y}")
    time.sleep(0.3)

def swipe(x1, y1, x2, y2, duration=300):
    os.system(f"adb shell input swipe {x1} {y1} {x2} {y2} {duration}")
    time.sleep(0.5)

def take_screenshot(name="temp.png"):
    result = os.system(f"adb exec-out screencap -p > {name}")
    time.sleep(0.5)
    if not os.path.exists(name) or os.path.getsize(name) < 1000:
        print(f"[ERROR] Screenshot {name} failed or is empty.")
        return None
    return name


def ocr_without_top_lines(image_path, skip_lines=2):
    text = pytesseract.image_to_string(Image.open(image_path)).strip()
    lines = text.splitlines()
    return "\n".join(lines[skip_lines:])

def ocr_text(image_path):
    if not os.path.exists(image_path) or os.path.getsize(image_path) < 1000:
        print(f"[ERROR] OCR failed: '{image_path}' not found or is invalid.")
        return ""
    try:
        return pytesseract.image_to_string(Image.open(image_path)).strip()
    except Exception as e:
        print(f"[ERROR] Failed to OCR '{image_path}': {e}")
        return ""

def swipe_to_yesterday_tab(retries=5, delay=1):
    print("[*] Attempting to swipe to 'Yesterday' tab...")

    for attempt in range(1, retries + 1):
        print(f"[>] Swipe attempt {attempt}")
        adb("input swipe 200 1000 900 1000 200")  # swipe right to left
        time.sleep(delay)

        take_screenshot("after.png")
        text = ocr_text("after.png")
        print("[=] OCR result:\n", text)

        if "Yesterday" in text:
            print("[✓] Swipe success — 'Yesterday' detected.")
            return True
        else:
            print("[x] 'Yesterday' not found. Retrying...")

    print("[!] Failed to detect 'Yesterday' tab after all attempts.")
    return False

def main():
    now = datetime.now()
    check_yesterday = 0 <= now.hour < 3

    log_folder = Path("health_logs")
    log_folder.mkdir(exist_ok=True)

    today = now

    if not check_yesterday:
        # During 12 AM to 3 AM: Treat today as the real "yesterday"
        heart_stress_date = today.strftime("%Y-%m-%d")        # Use TODAY for heart & stress
        sleep_date = (today - timedelta(days=1)).strftime("%Y-%m-%d")  # Use YESTERDAY for sleep
    else:
        # Normal case
        heart_stress_date = (today - timedelta(days=1)).strftime("%Y-%m-%d")
        sleep_date = (today - timedelta(days=2)).strftime("%Y-%m-%d")

    print("Importing new data.")
    swipe(55, 430, 55, 2305, 300)
    time.sleep(5)
    while True:
        if wait_until_noisefit_detected():
            break

    # --- HEART ---
    print("\n🫠 Switching to TODAY'S HEART tab...")
    tap(800, 1600)
    heart_text_today = pull_and_read_screen("heart", "today's HEART screen")
    heart_today = extract_heart_data(heart_text_today)

    if check_yesterday:
        print("\n🫠 Switching to YESTERDAY'S HEART tab...")
        swipe_to_yesterday_tab()
        heart_text_yesterday = pull_and_read_screen("heart", "yesterday's HEART screen")
        heart_yesterday = extract_heart_data(heart_text_yesterday)
        heart = merge_heart_data(heart_today, heart_yesterday)
    else:
        heart = heart_today
    tap(80, 170)
    swipe(55, 1974, 55, 121, 300)

    # --- STRESS ---
    print("\n🪠 Switching to TODAY'S STRESS tab...")
    tap(305, 940)
    pull_and_read_screen("stress", "today's STRESS screen")
    avg_today, rng_today = extract_stress_info_from_full_image("ss_temp.png")
    stress_today = {
        "avg_stress": int(avg_today) if avg_today.isdigit() else None,
        "min_stress": int(rng_today.split("–")[0]) if "–" in rng_today else None,
        "max_stress": int(rng_today.split("–")[1]) if "–" in rng_today else None,
    }

    if check_yesterday:
        print("\n🪠 Switching to YESTERDAY'S STRESS tab...")
        swipe_to_yesterday_tab()
        time.sleep(5)
        pull_and_read_screen("stress", "yesterday's STRESS screen")
        avg_yst, rng_yst = extract_stress_info_from_full_image("ss_temp.png")
        stress_yesterday = {
            "avg_stress": int(avg_yst) if avg_yst.isdigit() else None,
            "min_stress": int(rng_yst.split("–")[0]) if "–" in rng_yst else None,
            "max_stress": int(rng_yst.split("–")[1]) if "–" in rng_yst else None,
        }
        stress = merge_stress_data(stress_today, stress_yesterday)
    else:
        stress = stress_today
    tap(80, 170)
    swipe(55, 430, 55, 2305, 300)

    # --- SLEEP ---
    print("\n🛌 Opening the SLEEP tab...")
    tap(310, 1600)
    sleep_text = pull_and_read_screen("sleep", "SLEEP screen")
    sleep_raw = extract_sleep_data(sleep_text)
    computed_sleep = merge_sleep_data({
        "bedtime": sleep_raw.get("bedtime"),
        "wakeup": sleep_raw.get("wake_time")
    }, {})

    # --- SUMMARY STRINGS ---
    summary = (
        f"=== Health Summary for {heart_stress_date} ===\n"
        f"💓 Average BPM: {heart.get('avg_bpm', '?')}\n"
        f"↕️  BPM Range: {heart.get('min_bpm', '?')}–{heart.get('max_bpm', '?')} bpm\n"
        f"🚤 Average Stress: {stress.get('avg_stress', '?')}\n"
        f"↕️  Stress Range: {stress.get('min_stress', '?')}–{stress.get('max_stress', '?')}"
    )

    with open(log_folder / f"{heart_stress_date}.txt", "w", encoding="utf-8") as f:
        f.write(summary)

    # Save sleep only if valid
    if sleep_raw.get("bedtime") != "?" and sleep_raw.get("wake_time") != "?":
        sleep_summary = (
            f"🛌 Sleep Duration: {computed_sleep.get('duration', '?')}\n"
            f"🛎️ Bedtime: {sleep_raw.get('bedtime', '?')}\n"
            f"⏰ Wake-up Time: {sleep_raw.get('wake_time', '?')}\n"
        )
        with open(log_folder / f"{sleep_date}.txt", "a", encoding="utf-8") as f:
            f.write("\n" + sleep_summary)

    # --- JSON UPDATE ---
    update_health_data(heart_stress_date, heart, stress)
    if sleep_raw.get("bedtime") != "?" and sleep_raw.get("wake_time") != "?":
        update_health_data(sleep_date, {}, {}, sleep=computed_sleep)

    subprocess.run(["adb", "shell", "am", "force-stop", package_name])
    print("App closed.")


# Example usage inside your main:
if __name__ == "__main__":
    subprocess.run(["adb", "shell", "monkey", "-p", package_name, "-c", "android.intent.category.LAUNCHER", "1"])
    time.sleep(5)
    if wait_until_noisefit_detected():
        print("[INFO] Proceed with data extraction...")
        main()
    else:
        print("[INFO] NoiseFit not detected. Aborting.")

