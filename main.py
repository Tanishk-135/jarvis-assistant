# main.py

from voice.listen import VoiceRecognizer
from voice.speak import *

generate_audio("Hello, I am now using ElevenLabs.")

def process_command(command: str):
    command = command.lower()
    if "log" in command or "activity" in command:
        generate_audio("Activity is already being logged in the background.")
    elif "screenshot" in command:
        generate_audio("Screenshots will be captured during log activity.")
    elif "exit" in command or "shutdown" in command:
        generate_audio("Shutting down. Goodbye!")
        return False
    elif "hello" in command or "hi" in command:
        generate_audio("Hello! How can I assist you today?")
    else:
        generate_audio("Sorry, I didn't understand that.")
    return True

if __name__ == "__main__":
    generate_audio("Jarvis is online!")
    time.sleep(1)
    recognizer = VoiceRecognizer()
    generate_audio("Hello Tanishk.")
    time.sleep(1)


    while True:
        command = recognizer.listen_once()
        print(f"[You said] → {command}")
        if not process_command(command):
            break
