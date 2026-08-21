"""
인메모리 데이터 계층 (Vercel 서버리스 배포용).
SQLite 대신 프로세스 메모리 내 리스트/딕셔너리로 회원, 예약, 리마인더 로그를 관리한다.
Vercel Python 서버리스 함수는 파일시스템 쓰기가 보장되지 않으므로,
콜드 스타트마다 시드 데이터를 새로 생성해서 메모리에 올려 사용한다.
"""
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# 전역 인메모리 저장소
# ---------------------------------------------------------------------------
_members: dict[int, dict] = {}
_bookings: dict[int, dict] = {}
_reminder_log: list[dict] = []

_member_seq = 0
_booking_seq = 0
_seeded = False


def _next_member_id() -> int:
    global _member_seq
    _member_seq += 1
    return _member_seq


def _next_booking_id() -> int:
    global _booking_seq
    _booking_seq += 1
    return _booking_seq


def reset():
    global _members, _bookings, _reminder_log, _member_seq, _booking_seq, _seeded
    _members = {}
    _bookings = {}
    _reminder_log = []
    _member_seq = 0
    _booking_seq = 0
    _seeded = False


def get_or_create_member(name: str, phone: str) -> int:
    for mid, m in _members.items():
        if m["name"] == name and m["phone"] == phone:
            return mid
    mid = _next_member_id()
    _members[mid] = {"id": mid, "name": name, "phone": phone}
    return mid


def add_booking(member_id: int, booking_time: datetime, status: str = "scheduled") -> int:
    bid = _next_booking_id()
    _bookings[bid] = {
        "id": bid,
        "member_id": member_id,
        "booking_time": booking_time.isoformat(),
        "status": status,
        "created_at": datetime.now().isoformat(),
    }
    return bid


def set_booking_status(booking_id: int, status: str):
    if booking_id in _bookings:
        _bookings[booking_id]["status"] = status


def get_upcoming_bookings():
    rows = []
    for b in _bookings.values():
        if b["status"] != "scheduled":
            continue
        m = _members[b["member_id"]]
        rows.append(
            {
                "booking_id": b["id"],
                "booking_time": b["booking_time"],
                "status": b["status"],
                "member_id": m["id"],
                "name": m["name"],
                "phone": m["phone"],
            }
        )
    rows.sort(key=lambda r: r["booking_time"])
    return rows


def get_member_history(member_id: int, before: datetime = None):
    rows = [
        b for b in _bookings.values()
        if b["member_id"] == member_id and b["status"] in ("attended", "noshow", "cancelled")
    ]
    if before:
        before_iso = before.isoformat()
        rows = [b for b in rows if b["booking_time"] < before_iso]
    rows.sort(key=lambda r: r["booking_time"])
    return rows


def has_reminder_been_sent(booking_id: int, reminder_type: str) -> bool:
    return any(
        r["booking_id"] == booking_id and r["reminder_type"] == reminder_type
        for r in _reminder_log
    )


def log_reminder(booking_id: int, reminder_type: str, risk_score: int, risk_level: str, message: str):
    _reminder_log.append(
        {
            "id": len(_reminder_log) + 1,
            "booking_id": booking_id,
            "reminder_type": reminder_type,
            "sent_at": datetime.now().isoformat(),
            "risk_score": risk_score,
            "risk_level": risk_level,
            "message": message,
        }
    )


def get_all_reminder_logs():
    return sorted(_reminder_log, key=lambda r: r["sent_at"])


def get_all_members():
    return list(_members.values())


def get_all_bookings():
    return list(_bookings.values())


def get_member(member_id: int):
    return _members.get(member_id)


# ---------------------------------------------------------------------------
# 시딩 (원본 seed_data.py 로직을 인메모리 버전으로 이식)
# ---------------------------------------------------------------------------

def _same_weekday_past(reference: datetime, weeks_ago: int) -> datetime:
    return reference - timedelta(weeks=weeks_ago)


def seed(force: bool = False):
    """seed_data.py와 동일한 시나리오를 메모리에 생성. 이미 시딩됐으면 스킵(force=True면 재생성)."""
    global _seeded
    if _seeded and not force:
        return
    if force:
        reset()

    now = datetime.now()

    kim = get_or_create_member("김민수", "010-1111-2222")   # 월요일 노쇼 잦음 -> 고위험
    park = get_or_create_member("박지은", "010-2222-3333")  # 성실한 회원 -> 저위험
    lee = get_or_create_member("이서연", "010-3333-4444")   # 노쇼/출석 혼합 -> 중위험
    choi = get_or_create_member("최준호", "010-4444-5555")  # 잦은 취소 -> 중위험
    jung = get_or_create_member("정하늘", "010-5555-6666")  # 신규 회원, 이력 없음

    upcoming_kim = now + timedelta(hours=23, minutes=55)
    add_booking(kim, _same_weekday_past(upcoming_kim, weeks_ago=2), status="noshow")
    add_booking(kim, _same_weekday_past(upcoming_kim, weeks_ago=5), status="noshow")
    add_booking(kim, _same_weekday_past(upcoming_kim, weeks_ago=8), status="attended")

    add_booking(park, now - timedelta(days=10), status="attended")
    add_booking(park, now - timedelta(days=20), status="attended")

    add_booking(choi, now - timedelta(days=7), status="cancelled")

    booking_kim = add_booking(kim, upcoming_kim, status="scheduled")

    upcoming_park = now + timedelta(hours=2, minutes=50)
    booking_park = add_booking(park, upcoming_park, status="scheduled")

    add_booking(lee, now - timedelta(days=15), status="noshow")
    add_booking(lee, now - timedelta(days=25), status="attended")
    upcoming_lee = now + timedelta(hours=5)
    booking_lee = add_booking(lee, upcoming_lee, status="scheduled")

    upcoming_jung = now + timedelta(hours=22)
    booking_jung = add_booking(jung, upcoming_jung, status="scheduled")

    _seeded = True
    return {
        "booking_kim": booking_kim,
        "booking_park": booking_park,
        "booking_lee": booking_lee,
        "booking_jung": booking_jung,
    }
