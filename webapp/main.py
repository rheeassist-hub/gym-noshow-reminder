"""
FastAPI 대시보드 - 헬스장 노쇼 방지 AI 리마인더
(1) 예약/회원 목록  (2) 노쇼 위험도 스코어  (3) 리마인더 발송 시뮬레이션 로그
Vercel 서버리스 배포를 위해 SQLite 대신 인메모리 데이터(webapp.memory_db)를 사용한다.
"""
from datetime import datetime
from html import escape

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

from webapp import memory_db as db
from webapp import risk
from webapp import reminder

app = FastAPI(title="헬스장 노쇼방지 AI 리마인더 대시보드")


def _ensure_seeded_and_simulated():
    """요청마다 (콜드스타트 대비) 시딩 여부를 확인하고, 아직 리마인더가 없으면 시뮬레이션을 1회 실행."""
    db.seed()
    if not db.get_all_reminder_logs():
        reminder.simulate_all_reminders()


LEVEL_COLOR = {"HIGH": "#e74c3c", "MEDIUM": "#f39c12", "LOW": "#27ae60"}
LEVEL_LABEL = {"HIGH": "높음", "MEDIUM": "보통", "LOW": "낮음"}


def _risk_badge(level: str, score: int) -> str:
    color = LEVEL_COLOR.get(level, "#888")
    label = LEVEL_LABEL.get(level, level)
    return (
        f'<span class="badge" style="background:{color}">{escape(label)} '
        f'({score}점)</span>'
    )


def _fmt_dt(iso_str: str) -> str:
    try:
        return datetime.fromisoformat(iso_str).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return iso_str


PAGE_CSS = """
body { font-family: -apple-system, 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif;
       background:#f5f6fa; color:#222; margin:0; padding:0 0 40px; }
header { background:#1f2937; color:#fff; padding:24px 32px; }
header h1 { margin:0; font-size:22px; }
header p { margin:6px 0 0; color:#9ca3af; font-size:13px; }
main { max-width:1080px; margin:24px auto; padding:0 16px; }
section { background:#fff; border-radius:10px; padding:20px 24px; margin-bottom:24px;
          box-shadow:0 1px 3px rgba(0,0,0,0.08); }
h2 { font-size:17px; margin:0 0 14px; border-left:4px solid #4f46e5; padding-left:10px; }
table { width:100%; border-collapse:collapse; font-size:13.5px; }
th, td { text-align:left; padding:9px 10px; border-bottom:1px solid #eee; }
th { color:#6b7280; font-weight:600; background:#fafafa; }
tr:hover td { background:#fbfbff; }
.badge { color:#fff; padding:3px 9px; border-radius:12px; font-size:12px; font-weight:600; white-space:nowrap; }
.pill { display:inline-block; padding:2px 8px; border-radius:10px; font-size:11.5px; background:#eef2ff; color:#4338ca; }
.muted { color:#9ca3af; font-size:12px; }
.stat-row { display:flex; gap:16px; flex-wrap:wrap; margin-bottom:8px;}
.stat-card { flex:1; min-width:140px; background:#f9fafb; border-radius:8px; padding:14px 16px; }
.stat-card .num { font-size:24px; font-weight:700; }
.stat-card .lbl { font-size:12px; color:#6b7280; margin-top:2px; }
code.log-msg { font-size:12px; color:#374151; }
footer { text-align:center; color:#9ca3af; font-size:12px; margin-top:8px;}
a { color:#4f46e5; }
"""


@app.get("/", response_class=HTMLResponse)
def dashboard():
    _ensure_seeded_and_simulated()

    upcoming = db.get_upcoming_bookings()
    logs = db.get_all_reminder_logs()
    members = db.get_all_members()

    # ---- 예약 + 위험도 계산 ----
    rows_html = []
    high_count = med_count = low_count = 0
    for b in upcoming:
        bt = datetime.fromisoformat(b["booking_time"])
        r = risk.compute_risk(b["member_id"], bt)
        if r["level"] == "HIGH":
            high_count += 1
        elif r["level"] == "MEDIUM":
            med_count += 1
        else:
            low_count += 1
        rows_html.append(
            "<tr>"
            f"<td>{escape(b['name'])}</td>"
            f"<td class='muted'>{escape(b['phone'])}</td>"
            f"<td>{_fmt_dt(b['booking_time'])}</td>"
            f"<td>{_risk_badge(r['level'], r['score'])}</td>"
            f"<td class='muted'>전체 {r['overall_rate']*100:.0f}% / 요일 {r['weekday_rate']*100:.0f}%"
            f" (이력 {r['total_history']}건)</td>"
            "</tr>"
        )

    # ---- 회원 목록 ----
    member_rows = []
    for m in members:
        history = db.get_member_history(m["id"])
        member_rows.append(
            "<tr>"
            f"<td>{escape(m['name'])}</td>"
            f"<td class='muted'>{escape(m['phone'])}</td>"
            f"<td>{len(history)}건</td>"
            "</tr>"
        )

    # ---- 리마인더 발송 로그 ----
    log_rows = []
    booking_by_id = {b["id"]: b for b in db.get_all_bookings()}
    for lg in reversed(logs):
        bk = booking_by_id.get(lg["booking_id"])
        member = db.get_member(bk["member_id"]) if bk else None
        name = member["name"] if member else "?"
        log_rows.append(
            "<tr>"
            f"<td class='muted'>{_fmt_dt(lg['sent_at'])}</td>"
            f"<td><span class='pill'>{escape(lg['reminder_type'])}</span></td>"
            f"<td>{escape(name)}</td>"
            f"<td>{_risk_badge(lg['risk_level'], lg['risk_score'])}</td>"
            f"<td><code class='log-msg'>{escape(lg['message'])}</code></td>"
            "</tr>"
        )

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>헬스장 노쇼방지 AI 리마인더 대시보드</title>
<style>{PAGE_CSS}</style>
</head>
<body>
<header>
  <h1>🏋️ 헬스장 노쇼방지 AI 리마인더 대시보드</h1>
  <p>예약 · 회원 · 노쇼 위험도 스코어 · 리마인더 발송 시뮬레이션 로그 (인메모리 데모 데이터)</p>
</header>
<main>
  <section>
    <h2>요약</h2>
    <div class="stat-row">
      <div class="stat-card"><div class="num">{len(upcoming)}</div><div class="lbl">예정 예약</div></div>
      <div class="stat-card"><div class="num">{len(members)}</div><div class="lbl">전체 회원</div></div>
      <div class="stat-card"><div class="num" style="color:#e74c3c">{high_count}</div><div class="lbl">고위험 예약</div></div>
      <div class="stat-card"><div class="num" style="color:#f39c12">{med_count}</div><div class="lbl">중위험 예약</div></div>
      <div class="stat-card"><div class="num" style="color:#27ae60">{low_count}</div><div class="lbl">저위험 예약</div></div>
      <div class="stat-card"><div class="num">{len(logs)}</div><div class="lbl">발송된 리마인더</div></div>
    </div>
  </section>

  <section>
    <h2>예약 목록 &amp; 노쇼 위험도 스코어</h2>
    <table>
      <thead><tr><th>회원명</th><th>연락처</th><th>예약일시</th><th>위험도</th><th>상세</th></tr></thead>
      <tbody>{''.join(rows_html) if rows_html else '<tr><td colspan=5 class="muted">예정된 예약이 없습니다.</td></tr>'}</tbody>
    </table>
  </section>

  <section>
    <h2>회원 목록</h2>
    <table>
      <thead><tr><th>이름</th><th>연락처</th><th>과거 이력 건수</th></tr></thead>
      <tbody>{''.join(member_rows)}</tbody>
    </table>
  </section>

  <section>
    <h2>리마인더 발송 시뮬레이션 로그</h2>
    <table>
      <thead><tr><th>발송시각</th><th>유형</th><th>회원</th><th>위험도</th><th>메시지</th></tr></thead>
      <tbody>{''.join(log_rows) if log_rows else '<tr><td colspan=5 class="muted">아직 발송된 리마인더가 없습니다 (24h/3h 윈도우 밖).</td></tr>'}</tbody>
    </table>
  </section>

  <footer>gym-noshow-reminder · FastAPI + Vercel Serverless · <a href="/api/health">/api/health</a> · <a href="/api/data">/api/data (JSON)</a></footer>
</main>
</body>
</html>"""
    return HTMLResponse(content=html, status_code=200)


@app.get("/api/health")
def health():
    return {"status": "ok", "time": datetime.now().isoformat()}


@app.get("/api/data")
def data():
    _ensure_seeded_and_simulated()
    upcoming = db.get_upcoming_bookings()
    result = []
    for b in upcoming:
        bt = datetime.fromisoformat(b["booking_time"])
        r = risk.compute_risk(b["member_id"], bt)
        result.append({**b, "risk": r})
    return JSONResponse(
        {
            "bookings": result,
            "members": db.get_all_members(),
            "reminder_logs": db.get_all_reminder_logs(),
        }
    )
