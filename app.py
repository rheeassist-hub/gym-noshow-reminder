"""
FastAPI 대시보드 - 예약 목록 + 노쇼 위험도 스코어 + 리마인더 발송 시뮬레이션 로그를 웹에서 확인.
Vercel 서버리스 환경에서는 파일시스템이 read-only + ephemeral이므로,
매 cold start마다 인메모리 SQLite(:memory:)에 시드 데이터를 새로 채운다.
"""
import os
from datetime import datetime

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

os.environ.setdefault("GYM_DB_IN_MEMORY", "1")

import db  # noqa: E402
import risk  # noqa: E402
import seed_data  # noqa: E402

app = FastAPI(title="Gym No-show Reminder Dashboard")

_seeded = False


def _ensure_seeded():
    global _seeded
    if not _seeded:
        seed_data.seed(reset=True)
        _seeded = True


def _risk_badge(level: str) -> str:
    color = {"LOW": "#2e7d32", "MEDIUM": "#f9a825", "HIGH": "#c62828"}.get(level, "#666")
    return f'<span style="background:{color};color:#fff;padding:2px 8px;border-radius:4px;font-size:12px">{level}</span>'


@app.get("/", response_class=HTMLResponse)
def dashboard():
    _ensure_seeded()
    bookings = db.get_upcoming_bookings()
    rows = []
    for b in bookings:
        bt = datetime.fromisoformat(b["booking_time"])
        r = risk.compute_risk(b["member_id"], bt)
        rows.append(
            f"<tr><td>{b['name']}</td><td>{b['phone']}</td>"
            f"<td>{bt.strftime('%Y-%m-%d %H:%M')}</td>"
            f"<td>{r['score']}</td><td>{_risk_badge(r['level'])}</td>"
            f"<td>{r['total_history']}건 (노쇼 {r['noshow_count']})</td></tr>"
        )
    table = "\n".join(rows) if rows else "<tr><td colspan=6>예정된 예약 없음</td></tr>"
    logs = db.get_all_reminder_logs()
    log_rows = "\n".join(
        f"<tr><td>{lg['sent_at'][:19]}</td><td>{lg['reminder_type']}</td>"
        f"<td>{lg['booking_id']}</td><td>{lg['risk_score']}</td><td>{lg['message'][:60]}...</td></tr>"
        for lg in logs
    ) or "<tr><td colspan=5>발송 로그 없음 (scheduler.py --once 실행 시 생성됨)</td></tr>"

    return f"""
    <html><head><meta charset="utf-8"><title>헬스장 노쇼 방지 대시보드</title>
    <style>
      body {{ font-family: -apple-system, sans-serif; margin: 40px; background:#fafafa; }}
      h1 {{ font-size: 20px; }}
      table {{ border-collapse: collapse; width: 100%; margin-bottom: 32px; background:#fff; }}
      th, td {{ border: 1px solid #ddd; padding: 8px 12px; text-align: left; font-size: 14px; }}
      th {{ background: #f0f0f0; }}
    </style></head>
    <body>
      <h1>예정 예약 + 노쇼 위험도</h1>
      <table>
        <tr><th>회원</th><th>연락처</th><th>예약시각</th><th>점수</th><th>등급</th><th>이력</th></tr>
        {table}
      </table>
      <h1>리마인더 발송 시뮬레이션 로그</h1>
      <table>
        <tr><th>발송시각</th><th>타입</th><th>예약ID</th><th>위험점수</th><th>메시지</th></tr>
        {log_rows}
      </table>
      <p style="color:#888;font-size:12px">MVP 데모: Vercel 서버리스에서는 요청마다 인메모리 DB로 재시딩됩니다. 로컬에서는 SQLite 파일(data/gym.db) 영속.</p>
    </body></html>
    """


@app.get("/api/bookings")
def api_bookings():
    _ensure_seeded()
    bookings = db.get_upcoming_bookings()
    out = []
    for b in bookings:
        bt = datetime.fromisoformat(b["booking_time"])
        r = risk.compute_risk(b["member_id"], bt)
        out.append({**b, "risk": r})
    return {"bookings": out}


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
