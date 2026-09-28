# -*- coding: utf-8 -*-
"""
lib/deps.py ─ 선택 라이브러리가 설치돼 있는지 검사

[왜 필요한가]
 안심구역 PC에 scipy(빠른 계산용), matplotlib(그래프·지도 그림용)이 있을지 모릅니다.
 있으면 그걸 쓰고, 없으면 직접 만든 대체 코드를 쓰도록 여기서 미리 확인합니다.
 프론트엔드로 치면 `if (window.IntersectionObserver) {...} else { polyfill }` 같은 기능 감지입니다.

[결과]
 HAS_SCIPY = True/False,  HAS_MPL = True/False  → 다른 파일에서 import 해서 분기에 씁니다.
"""
import os

def _has(m):
    """라이브러리 이름 m 을 불러올 수 있으면 True, 없으면 False"""
    # 테스트용 스위치: 환경변수 HBI_FORCE_FALLBACK 을 켜면 일부러 "없는 척" 합니다.
    if os.environ.get("HBI_FORCE_FALLBACK"):
        return False
    try:
        __import__(m)          # import m 을 시도 (JS의 try { require(m) } 과 같음)
        return True
    except Exception:          # 불러오기 실패 = 설치 안 됨
        return False

HAS_SCIPY = _has("scipy")      # 과학계산 라이브러리 (최단경로·최근접 탐색을 빠르게)
HAS_MPL = _has("matplotlib")   # 그림 라이브러리 (지도 PNG 만들기)
