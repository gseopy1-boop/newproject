# test_env.py
import os
from dotenv import load_dotenv
load_dotenv()
key = os.getenv("OPENAI_API_KEY", "")
print("KEY 설정됨?" , bool(key), "| 앞 6글자:", key[:6] if key else "")
