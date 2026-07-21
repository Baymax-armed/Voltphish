"""Public trainee-facing training delivery (no account, token-gated).

A trainee opens /train/{token} (the per-enrollment secret), reads the lesson,
answers the quiz, and submits. We grade server-side, mark the enrollment
completed/failed, and award points. Pure HTML/CSS (no inline JS) so it renders
under the app's strict CSP. Unknown tokens return a benign 'not found' page.
"""
from __future__ import annotations

import html
import json

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session as DbSession

from ..database import get_db
from ..models import EnrollmentStatus, QuizQuestion, TrainingEnrollment, TrainingModule
from ..models.base import utcnow

router = APIRouter(tags=["train"], include_in_schema=False)

# Allow inline styles + external video frames/images, but keep scripts locked to
# 'self' so admin-authored lesson HTML can't run injected JS (XSS-safe).
_TRAIN_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: https:; frame-src https:; media-src https:; "
    "form-action 'self'; base-uri 'self'; frame-ancestors 'none'"
)


def _train_html(title: str, body: str, status_code: int = 200) -> HTMLResponse:
    resp = HTMLResponse(_PAGE.format(title=title, body=body), status_code=status_code)
    resp.headers["Content-Security-Policy"] = _TRAIN_CSP
    resp.headers["Cache-Control"] = "no-store"
    return resp

_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{title}</title>
<style>
:root {{ --ink:#0f172a; --sub:#475569; --accent:#4f46e5; --line:#e2e8f0; --bg:#f1f5f9; }}
* {{ box-sizing:border-box; }}
body {{ font-family:"Segoe UI",system-ui,sans-serif; margin:0; background:var(--bg); color:var(--ink); }}
.wrap {{ max-width:720px; margin:0 auto; padding:32px 20px 64px; }}
.card {{ background:#fff; border:1px solid var(--line); border-radius:16px; padding:28px 30px; box-shadow:0 1px 3px rgba(0,0,0,.05); }}
.eyebrow {{ text-transform:uppercase; letter-spacing:.08em; font-size:12px; font-weight:700; color:var(--accent); }}
h1 {{ font-size:24px; margin:6px 0 4px; }}
.meta {{ color:var(--sub); font-size:13px; margin-bottom:20px; }}
.content h2 {{ font-size:18px; margin:20px 0 8px; }}
.content p {{ line-height:1.6; color:#1e293b; }}
.quiz {{ margin-top:24px; border-top:1px solid var(--line); padding-top:20px; }}
.q {{ margin-bottom:18px; }}
.q .prompt {{ font-weight:600; margin-bottom:8px; }}
.opt {{ display:flex; align-items:center; gap:10px; padding:10px 12px; border:1px solid var(--line); border-radius:10px; margin-bottom:6px; cursor:pointer; }}
.opt:hover {{ border-color:var(--accent); }}
.btn {{ display:inline-block; background:var(--accent); color:#fff; border:0; border-radius:10px; padding:12px 22px; font-size:15px; font-weight:600; cursor:pointer; }}
.result {{ text-align:center; padding:20px 0; }}
.score {{ font-size:44px; font-weight:800; }}
.pass {{ color:#166534; }} .fail {{ color:#b91c1c; }}
.badge {{ display:inline-block; background:#dcfce7; color:#166534; border-radius:999px; padding:6px 14px; font-weight:600; margin-top:8px; }}
iframe {{ width:100%; aspect-ratio:16/9; border:0; border-radius:12px; margin:16px 0; }}
</style></head><body><div class="wrap"><div class="card">{body}</div></div></body></html>"""


def _not_found() -> HTMLResponse:
    body = '<div class="eyebrow">Training</div><h1>Link not found</h1><p class="meta">This training link is invalid or has expired. Please contact your security team.</p>'
    return _train_html("Training", body, status_code=404)


def _lesson_body(m: TrainingModule) -> str:
    video = f'<iframe src="{html.escape(m.video_url)}" allowfullscreen></iframe>' if m.video_url else ""
    quiz = ""
    if m.questions:
        qs = []
        for qi, q in enumerate(m.questions):
            opts = json.loads(q.options or "[]")
            optbtns = "".join(
                f'<label class="opt"><input type="radio" name="q{qi}" value="{oi}" required> '
                f"<span>{html.escape(str(o))}</span></label>"
                for oi, o in enumerate(opts)
            )
            qs.append(f'<div class="q"><div class="prompt">{qi + 1}. {html.escape(q.prompt)}</div>{optbtns}</div>')
        quiz = (
            '<div class="quiz"><h2 style="font-size:18px;margin:0 0 14px">Quick check</h2>'
            + "".join(qs)
            + '<button class="btn" type="submit">Submit answers</button></div>'
        )
    else:
        quiz = '<div class="quiz"><button class="btn" type="submit">Mark as complete</button></div>'

    return (
        f'<div class="eyebrow">{html.escape(m.category)} · {m.difficulty.value} · ~{m.estimated_minutes} min</div>'
        f"<h1>{html.escape(m.title)}</h1>"
        f'<div class="meta">{html.escape(m.description or "")}</div>'
        f"{video}"
        f'<div class="content">{m.content_html}</div>'
        f'<form method="post">{quiz}</form>'
    )


@router.get("/train/{token}", response_class=HTMLResponse)
def view_training(token: str, db: DbSession = Depends(get_db)) -> HTMLResponse:
    enr = db.query(TrainingEnrollment).filter(TrainingEnrollment.token == token).one_or_none()
    if enr is None:
        return _not_found()
    m = db.get(TrainingModule, enr.module_id)
    if m is None or not m.is_published:
        return _not_found()
    if enr.status == EnrollmentStatus.assigned:
        enr.status = EnrollmentStatus.in_progress
        db.commit()
    return _train_html(m.title, _lesson_body(m))


@router.post("/train/{token}", response_class=HTMLResponse)
async def submit_training(token: str, request: Request, db: DbSession = Depends(get_db)) -> HTMLResponse:
    enr = db.query(TrainingEnrollment).filter(TrainingEnrollment.token == token).one_or_none()
    if enr is None:
        return _not_found()
    m = db.get(TrainingModule, enr.module_id)
    if m is None:
        return _not_found()

    form = await request.form()
    questions = list(m.questions)
    if questions:
        correct = 0
        for qi, q in enumerate(questions):
            try:
                chosen = int(form.get(f"q{qi}", "-1"))
            except (TypeError, ValueError):
                chosen = -1
            if chosen == q.correct_index:
                correct += 1
        score = round(correct / len(questions) * 100)
    else:
        score = 100

    enr.attempts += 1
    enr.score = score
    passed = score >= m.pass_score
    if passed:
        enr.status = EnrollmentStatus.completed
        enr.completed_at = utcnow()
    else:
        enr.status = EnrollmentStatus.failed
    db.commit()

    if passed:
        body = (
            '<div class="result"><div class="eyebrow">Training complete</div>'
            f'<div class="score pass">{score}%</div>'
            f"<h1>Nice work!</h1><p class=\"meta\">You passed “{html.escape(m.title)}”.</p>"
            f'<div class="badge">+{m.points} points earned 🎉</div></div>'
        )
    else:
        body = (
            '<div class="result"><div class="eyebrow">Almost there</div>'
            f'<div class="score fail">{score}%</div>'
            f'<h1>Give it another try</h1>'
            f'<p class="meta">You need {m.pass_score}% to pass. Review the lesson and try again.</p>'
            f'<a class="btn" href="/train/{html.escape(token)}">Retake training</a></div>'
        )
    return _train_html(m.title, body)
