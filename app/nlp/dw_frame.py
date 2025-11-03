# -*- coding: utf-8 -*-
"""
app/nlp/dw_frame.py
- 'Exploring the Digital Workspace' 등 레트로 데스크톱 장면을
  구조적으로 선언하고, 프롬프트/사이니지로 변환하는 헬퍼.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List

# ==== 네가 준 구조를 dataclass로 경량화(동작 동일) ====

@dataclass
class ComputerComponent:
    name: str
    description: str
    content_hint: str | None = None

@dataclass
class DigitalWorkspaceFrame:
    title: str
    series: str
    style: str = "Retro 90s Pixel Art / Windows 95 Aesthetic"
    components: List[ComputerComponent] = None

    def __post_init__(self):
        if self.components is None:
            self.components = []

    def add(self, component: ComputerComponent):
        self.components.append(component)
        return self  # 체이닝

# 프리셋 컴포넌트
def CRTMonitor():
    return ComputerComponent("CRT Monitor", "클래식하고 부피가 큰 모니터. 화면은 비어 있음.", None)

def Keyboard():
    return ComputerComponent("Keyboard", "모니터 아래, 무각인 키캡의 픽셀화된 키보드.", None)

def Mouse():
    return ComputerComponent("Mouse", "모니터 오른쪽, 케이블로 연결된 마우스.", None)

def DocumentFile():
    return ComputerComponent("Document File", "X 표시 점선 박스와 나침반 아이콘이 그려진 종이 문서.", "Exploring/Location 암시")

# ==== 변환 유틸 ====

def to_prompt(dw: DigitalWorkspaceFrame) -> str:
    """
    이미지 생성용 텍스트. 모델/로컬 합성 모두에 사용 가능.
    """
    parts = [f"{dw.style}", "Windows 95 window frame, pixel-art."]
    for c in dw.components:
        frag = f"{c.name}: {c.description}"
        if c.content_hint:
            frag += f" ({c.content_hint})"
        parts.append(frag)
    # 시그니처 프레이즈(헤드라인)도 힌트로 포함
    parts.append(f"Headline: '{dw.title}'  Series: '{dw.series}'")
    return " | ".join(parts)

def apply_signage_env(dw: DigitalWorkspaceFrame, *, pixelate: bool = True):
    """
    이미지 오버레이/브랜딩을 env로 제어하는 현 구조에 맞춰 세팅.
    """
    import os
    os.environ["SIGN_LOGO_TEXT"] = "startdesk"          # 좌측 작은 로고
    os.environ["SIGN_FOOTER_TEXT"] = "fromstartdesk"    # 하단 문구
    os.environ["SIGN_THEME"] = os.getenv("SIGN_THEME", "teal")
    os.environ["SIGN_SHOW_HEADLINE"] = "1"               # 중앙 큰 헤드라인 사용
    # 헤드라인은 샘플처럼 고정 문구 또는 dw.title 사용 가능
    if not os.getenv("SIGN_HEADLINE"):
        os.environ["SIGN_HEADLINE"] = dw.title
    if pixelate:
        os.environ["PIXELATE"] = "1"
        os.environ["PIXELATE_BLOCK"] = os.getenv("PIXELATE_BLOCK", "8")
