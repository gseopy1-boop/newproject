import os, json, datetime

def log_post(keyword: str, image_path: str, result: dict):
    """업로드 후 결과를 output/logs 폴더에 저장"""
    os.makedirs("output/logs", exist_ok=True)
    today = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = f"output/logs/post_{today}.json"
    data = {
        "timestamp": today,
        "keyword": keyword,
        "image_path": image_path,
        "result": result
    }
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"📝 로그 저장됨: {log_path}")
