"""
SQLite 데이터 계층 - 회원, 예약, 리마인더 발송 로그, 노쇼 이력 관리
"""
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path(__file__).parent / "data" / "gym.db"
_IN_MEMORY = os.environ.get("GYM_DB_IN_MEMORY") == "1"
_shared_conn = None  # in-memory 모드에서는 연결을 프로세스 내내 재사용해야 데이터가 유지됨

SCHEMA = """
CREATE TABLE IF NOT EXISTS members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id INTEGER NOT NULL,
    booking_time TEXT NOT NULL,      -- ISO datetime, 예약된 수업 시작 시각
    status TEXT NOT NULL DEFAULT 'scheduled',  -- scheduled | attended | noshow | cancelled
    created_at TEXT NOT NULL,
    FOREIGN KEY (member_id) REFERENCES members(id)
);

CREATE TABLE IF NOT EXISTS reminder_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id INTEGER NOT NULL,
    reminder_type TEXT NOT NULL,     -- '24h' | '3h'
    sent_at TEXT NOT NULL,
    risk_score INTEGER,
    risk_level TEXT,
    message TEXT NOT NULL,
    FOREIGN KEY (booking_id) REFERENCES bookings(id)
);
"""


def get_conn():
    global _shared_conn
    if _IN_MEMORY:
        if _shared_conn is None:
            _shared_conn = sqlite3.connect(":memory:", check_same_thread=False)
            _shared_conn.row_factory = sqlite3.Row
            _shared_conn.execute("PRAGMA foreign_keys = ON")
        return _shared_conn
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(reset: bool = False):
    global _shared_conn
    if _IN_MEMORY:
        if reset:
            _shared_conn = None  # 다음 get_conn()에서 새 인메모리 DB 생성
        conn = get_conn()
        conn.executescript(SCHEMA)
        conn.commit()
        return
    if reset and DB_PATH.exists():
        DB_PATH.unlink()
    conn = get_conn()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


@contextmanager
def session():
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    finally:
        if not _IN_MEMORY:
            conn.close()


def add_member(name: str, phone: str) -> int:
    with session() as conn:
        cur = conn.execute(
            "INSERT INTO members (name, phone) VALUES (?, ?)", (name, phone)
        )
        return cur.lastrowid


def get_or_create_member(name: str, phone: str) -> int:
    with session() as conn:
        row = conn.execute(
            "SELECT id FROM members WHERE name=? AND phone=?", (name, phone)
        ).fetchone()
        if row:
            return row["id"]
        cur = conn.execute(
            "INSERT INTO members (name, phone) VALUES (?, ?)", (name, phone)
        )
        return cur.lastrowid


def add_booking(member_id: int, booking_time: datetime, status: str = "scheduled") -> int:
    with session() as conn:
        cur = conn.execute(
            "INSERT INTO bookings (member_id, booking_time, status, created_at) VALUES (?, ?, ?, ?)",
            (member_id, booking_time.isoformat(), status, datetime.now().isoformat()),
        )
        return cur.lastrowid


def set_booking_status(booking_id: int, status: str):
    with session() as conn:
        conn.execute("UPDATE bookings SET status=? WHERE id=?", (status, booking_id))


def get_upcoming_bookings():
    """status='scheduled' 인 모든 예약 (회원 정보 조인)"""
    with session() as conn:
        rows = conn.execute(
            """
            SELECT b.id AS booking_id, b.booking_time, b.status,
                   m.id AS member_id, m.name, m.phone
            FROM bookings b JOIN members m ON b.member_id = m.id
            WHERE b.status = 'scheduled'
            ORDER BY b.booking_time
            """
        ).fetchall()
        return [dict(r) for r in rows]


def get_member_history(member_id: int, before: datetime = None):
    """해당 회원의 과거 예약 이력 (노쇼 스코어링용)"""
    with session() as conn:
        q = "SELECT * FROM bookings WHERE member_id=? AND status IN ('attended','noshow','cancelled')"
        params = [member_id]
        if before:
            q += " AND booking_time < ?"
            params.append(before.isoformat())
        q += " ORDER BY booking_time"
        rows = conn.execute(q, params).fetchall()
        return [dict(r) for r in rows]


def has_reminder_been_sent(booking_id: int, reminder_type: str) -> bool:
    with session() as conn:
        row = conn.execute(
            "SELECT 1 FROM reminder_log WHERE booking_id=? AND reminder_type=?",
            (booking_id, reminder_type),
        ).fetchone()
        return row is not None


def log_reminder(booking_id: int, reminder_type: str, risk_score: int, risk_level: str, message: str):
    with session() as conn:
        conn.execute(
            """INSERT INTO reminder_log (booking_id, reminder_type, sent_at, risk_score, risk_level, message)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (booking_id, reminder_type, datetime.now().isoformat(), risk_score, risk_level, message),
        )


def get_all_reminder_logs():
    with session() as conn:
        rows = conn.execute(
            "SELECT * FROM reminder_log ORDER BY sent_at"
        ).fetchall()
        return [dict(r) for r in rows]
