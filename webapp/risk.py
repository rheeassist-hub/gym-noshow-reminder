"""
노쇼 위험도 예측 - 규칙 기반 스코어링 (0~100점).
원본 risk.py 로직을 memory_db 기반으로 이식.
"""
from datetime import timedelta, datetime

from webapp import memory_db as db

LOOKBACK_DAYS = 90
SMOOTHING = 2


def _rate(noshow: int, total: int) -> float:
    return (noshow + SMOOTHING * 0.3) / (total + SMOOTHING)


def compute_risk(member_id: int, booking_time) -> dict:
    since = booking_time - timedelta(days=LOOKBACK_DAYS)
    history = db.get_member_history(member_id, before=booking_time)
    recent_history = [h for h in history if h["booking_time"] >= since.isoformat()]

    total = len(recent_history)
    noshow_count = sum(1 for h in recent_history if h["status"] == "noshow")
    cancel_count = sum(1 for h in recent_history if h["status"] == "cancelled")
    overall_rate = _rate(noshow_count, total)

    target_weekday = booking_time.weekday()
    weekday_history = [
        h for h in recent_history
        if _iso_weekday(h["booking_time"]) == target_weekday
    ]
    wtotal = len(weekday_history)
    wnoshow = sum(1 for h in weekday_history if h["status"] == "noshow")
    weekday_rate = _rate(wnoshow, wtotal)

    cancel_penalty = min(cancel_count * 3, 10)

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
    return datetime.fromisoformat(iso_str).weekday()
