"""
리마인더 '발송' 시뮬레이션 (인메모리 버전).
실제 SMS/카카오톡 API 연동 대신 메모리 로그(webapp.memory_db.reminder_log)에 기록한다.
"""
from datetime import datetime

from webapp import memory_db as db
from webapp import risk


def build_message(name: str, booking_time_str: str, reminder_type: str, risk_info: dict) -> str:
    label = "내일" if reminder_type == "24h" else "3시간 후"
    base = f"[리마인더] {name}님, {label}({booking_time_str}) 수업 예약이 있습니다. 불참 시 미리 취소 부탁드려요!"
    if risk_info["level"] == "HIGH":
        base += " ⚠️ 노쇼 위험도 높음 - 스탭 유선 확인 권장"
    return base


def send_reminder(booking: dict, reminder_type: str):
    from datetime import datetime as dt

    booking_id = booking["booking_id"]

    if db.has_reminder_been_sent(booking_id, reminder_type):
        return None

    booking_time = dt.fromisoformat(booking["booking_time"])
    risk_info = risk.compute_risk(booking["member_id"], booking_time)
    message = build_message(booking["name"], booking["booking_time"], reminder_type, risk_info)

    db.log_reminder(
        booking_id=booking_id,
        reminder_type=reminder_type,
        risk_score=risk_info["score"],
        risk_level=risk_info["level"],
        message=message,
    )
    return risk_info


def simulate_all_reminders():
    """모든 예정 예약에 대해 24h/3h 윈도우 판정 후 리마인더 발송 시뮬레이션을 수행한다."""
    now = datetime.now()
    upcoming = db.get_upcoming_bookings()
    sent = []
    for b in upcoming:
        bt = datetime.fromisoformat(b["booking_time"])
        hours_until = (bt - now).total_seconds() / 3600
        if 0 <= hours_until <= 24:
            r = send_reminder(b, "24h")
            if r:
                sent.append((b, "24h", r))
        if 0 <= hours_until <= 3:
            r = send_reminder(b, "3h")
            if r:
                sent.append((b, "3h", r))
    return sent
