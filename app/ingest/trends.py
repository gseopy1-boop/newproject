# app/ingest/trends.py
from pytrends.request import TrendReq

def fetch_trend_keywords(kw_list=("fashion","travel","iphone"), geo="KR", timeframe="now 7-d", top_n=15):
    """
    기본 키워드 묶음을 기준으로 연관 검색어(Top/Rising)에서 상위 N개를 수집.
    실패 시에는 입력 kw_list를 반환.
    """
    try:
        pt = TrendReq(hl="ko-KR", tz=540)
        pt.build_payload(kw_list=list(kw_list), timeframe=timeframe, geo=geo)
        related = pt.related_queries()
        bag = set()
        for kw in kw_list:
            for kind in ("top", "rising"):
                df = related.get(kw, {}).get(kind)
                if df is not None:
                    bag |= set(df["query"].dropna().head(top_n).tolist())
        # 비어있으면 원본 키워드 반환
        return list(bag) if bag else list(kw_list)
    except Exception as e:
        print(f"[trends] fetch error: {e}")
        return list(kw_list)
