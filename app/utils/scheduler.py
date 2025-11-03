import random, time

def random_sleep(min_minute=30, max_minute=90):
    """랜덤 대기 (분 단위)"""
    wait = random.randint(min_minute, max_minute)
    print(f"⏳ 다음 업로드까지 {wait}분 대기 중...")
    time.sleep(wait * 60)
