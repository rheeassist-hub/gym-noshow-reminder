"""
노쇼 위험도 예측 - 규칙 기반 스코어링 (0~100점)

스코어 구성:
  1) 최근 3개월(90일) 전체 노쇼율            -> 가중치 60%
  2) 예약 요일(요일별) 노쇼율 패턴            -> 가중치 40%
  3) 데이터가 적은 회원은 라플라스 스무딩으로 과도한 확신 방지
  4) 최근 취소(cancelled) 이력도 약한 리스크 신호로 소폭 가산

점수 구간:
  0-29   : LOW
  30-59  : MEDIUM
  60-100 : HIGH
"""
from datetime import timedelta

import db

LOOKBACK_DAYS = 90
SMOOTHING = 2  # 라플라스 스무딩 상수 (표본이 적을 때 극단값 방지)


def _rate(noshow: int, total: int) -> float:
    """스무딩 적용된 노쇼율 (0~1)"""
    return (noshow + SMOOTHING * 0.3) / (total + SMOOTHING)


def compute_risk(member_id: int, booking_time) -> dict:
    """
    특정 회원의 특정 예약(booking_time)에 대한 노쇼 위험도를 계산한다.
    returns: {score:int, level:str, overall_rate:float, weekday_rate:float,
              total_history:int, weekday_history:int, cancel_penalty:float}
    """
    since = booking_time - timedelta(days=LOOKBACK_DAYS)
    history = db.get_member_history(member_id, before=booking_time)
    recent_history = [h for h in history if h["booking_time"] >= since.isoformat()]

    total = len(recent_history)
    noshow_count = sum(1 for h in recent_history if h["status"] == "noshow")
    cancel_count = sum(1 for h in recent_history if h["status"] == "cancelled")
    overall_rate = _rate(noshow_count, total)

    target_weekday = booking_time.weekday()  # 0=Mon .. 6=Sun
    weekday_history = [
        h for h in recent_history
        if _iso_weekday(h["booking_time"]) == target_weekday
    ]
    wtotal = len(weekday_history)
    wnoshow = sum(1 for h in weekday_history if h["status"] == "noshow")
    weekday_rate = _rate(wnoshow, wtotal)

    cancel_penalty = min(cancel_count * 3, 10)  # 취소 잦으면 소폭 가산 (최대 +10)

    # overall_rate/weekday_rate 는 0~1 비율이므로, 가중치(60/40)를 곱하면
    # 그 자체로 0~100 스케일의 점수가 된다.
    raw_score = overall_rate * 60 + weekday_rate * 40
    score = round(min(raw_score + cancel_penalty, 100))

    if score >= 60:
        level = "HIGH"
    elif score >= 30:
        level = "MEDIUM"
    else:
        level = "LOW"

    return {
        "score": score,
        "level": level,
        "overall_rate": round(overall_rate, 3),
        "weekday_rate": round(weekday_rate, 3),
        "total_history": total,
        "weekday_history": wtotal,
        "noshow_count": noshow_count,
        "cancel_penalty": cancel_penalty,
    }


def _iso_weekday(iso_str: str) -> int:
    from datetime import datetime
    return datetime.fromisoformat(iso_str).weekday()
