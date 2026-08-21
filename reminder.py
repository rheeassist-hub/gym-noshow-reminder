"""
리마인더 '발송' 시뮬레이션.
실제 SMS/카카오톡 API 연동 대신 콘솔 로그 + 로컬 파일(logs/reminders.log)에 기록한다.
"""
from datetime import datetime
from pathlib import Path

import db
import risk

LOG_FILE = Path(__file__).parent / "logs" / "reminders.log"


def _write_log_line(line: str):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def build_message(name: str, booking_time_str: str, reminder_type: str, risk_info: dict) -> str:
    label = "내일" if reminder_type == "24h" else "3시간 후"
    base = f"[리마인더] {name}님, {label}({booking_time_str}) 수업 예약이 있습니다. 불참 시 미리 취소 부탁드려요!"
    if risk_info["level"] == "HIGH":
        base += " ⚠️ 노쇼 위험도 높음 - 스탭 유선 확인 권장"
    return base


def send_reminder(booking: dict, reminder_type: str):
    """
    booking: {booking_id, booking_time(str,iso), member_id, name, phone, status}
    reminder_type: '24h' | '3h'
    """
    from datetime import datetime as dt

    booking_id = booking["booking_id"]

    if db.has_reminder_been_sent(booking_id, reminder_type):
        return None  # 중복 발송 방지

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

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = (
        f"[{ts}] SEND_SIMULATED type={reminder_type} booking_id={booking_id} "
        f"member={booking['name']} phone={booking['phone']} "
        f"risk_score={risk_info['score']} risk_level={risk_info['level']} "
        f"msg=\"{message}\""
    )
    print(log_line)
    _write_log_line(log_line)

    return risk_info
