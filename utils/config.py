# utils/config.py

import os

BASE_DIR = os.path.dirname(os.path.dirname(__file__))

model_path = os.path.join(BASE_DIR, "voice", "vosk-model")
log_dir = os.path.join(BASE_DIR, "data", "raw")
elevenlabs_api_key = "sk_031e2d5bb1c5f9d3a34b581218cd43613a7ad76ec2b8ac8d"