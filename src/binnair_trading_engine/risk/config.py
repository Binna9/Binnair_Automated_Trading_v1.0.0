"""
리스크 모듈의 기본 상수를 정의한다.
설정값이 없을 때 사용할 포지션/손실/중복 주문 제한 기본값을 제공한다.
"""

# 최대 포지션 수량 (심볼당). 0 이하면 수량 상한 검사 비활성 (명목 금액 %만 사용).
DEFAULT_MAX_POSITION_QTY = 0.0

# 일손실 제한 (음수)
DEFAULT_DAILY_LOSS_LIMIT = -1000.0

# 중복 주문 방지: 동일 심볼/사이드 재주문 최소 간격(초)
DEFAULT_DUPLICATE_ORDER_WINDOW_SECONDS = 60
