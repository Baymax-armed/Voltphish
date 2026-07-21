"""Seed a starter content library so Training isn't empty on first run.

Four short, vendor-neutral awareness modules with quizzes. Only seeded when the
modules table is empty — admins can edit, delete, or add their own afterward.
"""
from __future__ import annotations

import json
import logging

from sqlalchemy import select

from ..database import SessionLocal
from ..models import Difficulty, QuizQuestion, TrainingModule
from ..models.base import utcnow

log = logging.getLogger("phishsim.training")


def _p(*paras: str) -> str:
    return "".join(f"<p>{x}</p>" for x in paras)


_MODULES = [
    {
        "title": "Spot the Phish",
        "description": "Learn the tell-tale signs of a phishing email in 5 minutes.",
        "category": "Phishing",
        "difficulty": Difficulty.beginner,
        "estimated_minutes": 5,
        "points": 100,
        "content_html": (
            "<h2>Spotting a phishing email</h2>"
            + _p(
                "Phishing emails try to trick you into clicking a link, opening an attachment, "
                "or handing over credentials. Most share a few warning signs.",
                "<strong>1. Urgency &amp; fear.</strong> “Your account will be closed in 24 hours!” "
                "Attackers rush you so you act before you think.",
                "<strong>2. Mismatched sender.</strong> The display name says “IT Support” but the "
                "address is a random Gmail. Always check the real address.",
                "<strong>3. Hover before you click.</strong> The visible text may say one thing while the "
                "link points somewhere else. Hover to see the true destination.",
                "<strong>4. Unexpected attachments.</strong> Invoices, resumes, and “voicemails” you "
                "didn’t expect are classic malware carriers.",
                "<strong>5. Generic greetings &amp; odd grammar.</strong> “Dear Customer” and clumsy "
                "phrasing often signal a mass phishing run.",
                "When in doubt, don’t click — report it using the Report Phish button.",
            )
        ),
        "questions": [
            {
                "prompt": "An email says your account will be suspended in 1 hour unless you log in via a link. What's the biggest red flag?",
                "options": [
                    "It uses your first name",
                    "Artificial urgency pressuring you to act fast",
                    "It has a company logo",
                    "It was sent in the morning",
                ],
                "correct_index": 1,
            },
            {
                "prompt": "The best way to check where a link really goes is to:",
                "options": [
                    "Click it and see",
                    "Trust the visible text",
                    "Hover over it to reveal the true URL",
                    "Forward it to a friend",
                ],
                "correct_index": 2,
            },
            {
                "prompt": "You receive an unexpected invoice attachment from an unknown sender. You should:",
                "options": [
                    "Open it to see what it is",
                    "Enable macros if it asks",
                    "Reply asking for details",
                    "Not open it and report the email",
                ],
                "correct_index": 3,
            },
        ],
    },
    {
        "title": "Password Hygiene & MFA",
        "description": "Strong passwords, password managers, and why MFA matters.",
        "category": "Account Security",
        "difficulty": Difficulty.beginner,
        "estimated_minutes": 4,
        "points": 100,
        "content_html": (
            "<h2>Protecting your accounts</h2>"
            + _p(
                "<strong>Use long, unique passwords.</strong> Length beats complexity. A unique password "
                "per site means one breach can’t unlock the rest of your life.",
                "<strong>Use a password manager.</strong> It generates and remembers strong passwords so "
                "you don’t have to reuse them.",
                "<strong>Turn on multi-factor authentication (MFA).</strong> Even if an attacker steals your "
                "password, MFA blocks them without your second factor.",
                "<strong>Beware MFA fatigue.</strong> If you get repeated MFA prompts you didn’t start, "
                "deny them and report it — someone may have your password.",
            )
        ),
        "questions": [
            {
                "prompt": "Why is a unique password per site important?",
                "options": [
                    "It's easier to remember",
                    "One site's breach won't compromise your other accounts",
                    "Websites require it",
                    "It loads faster",
                ],
                "correct_index": 1,
            },
            {
                "prompt": "You suddenly get several MFA push prompts you didn't request. You should:",
                "options": [
                    "Approve one to make them stop",
                    "Ignore them",
                    "Deny them and report it — your password may be compromised",
                    "Turn off MFA",
                ],
                "correct_index": 2,
            },
        ],
    },
    {
        "title": "Business Email Compromise (BEC)",
        "description": "How attackers impersonate executives and vendors to steal money.",
        "category": "Phishing",
        "difficulty": Difficulty.intermediate,
        "estimated_minutes": 6,
        "points": 150,
        "content_html": (
            "<h2>Business Email Compromise</h2>"
            + _p(
                "BEC skips malware entirely — it’s pure social engineering. An attacker impersonates "
                "a CEO, finance lead, or supplier and asks you to move money or change payment details.",
                "<strong>Watch for:</strong> a sudden urgent wire request, a “new” bank account for an "
                "existing vendor, secrecy (“don’t tell anyone yet”), and a reply-to that differs "
                "from the real address.",
                "<strong>Always verify out-of-band.</strong> Call the person on a known number — never the "
                "number in the email — before acting on payment or banking changes.",
            )
        ),
        "questions": [
            {
                "prompt": "Your CFO emails an urgent request to wire funds to a new account, and asks you to keep it confidential. You should:",
                "options": [
                    "Send the wire immediately",
                    "Reply to confirm the account",
                    "Verify by calling the CFO on a known number first",
                    "Forward it to a colleague to handle",
                ],
                "correct_index": 2,
            },
            {
                "prompt": "A known vendor emails that their bank details changed. The safest action is to:",
                "options": [
                    "Update the details as requested",
                    "Confirm via a previously known phone contact",
                    "Reply to the email to confirm",
                    "Pay to both old and new accounts",
                ],
                "correct_index": 1,
            },
        ],
    },
    {
        "title": "Reporting Suspicious Emails",
        "description": "When and how to report, and why it protects everyone.",
        "category": "Response",
        "difficulty": Difficulty.beginner,
        "estimated_minutes": 3,
        "points": 75,
        "content_html": (
            "<h2>Reporting makes you the human firewall</h2>"
            + _p(
                "Technology stops most phishing, but attackers design the ones that slip through to fool "
                "filters. Your report is often the first warning the security team gets.",
                "<strong>Report early, report often.</strong> A false alarm costs seconds to check. A missed "
                "real attack can cost far more.",
                "<strong>Use the Report Phish button.</strong> It sends the whole message safely to security "
                "and, if it was a training test, credits you for catching it.",
                "Don’t forward suspicious mail to colleagues — report it instead so it doesn’t spread.",
            )
        ),
        "questions": [
            {
                "prompt": "You're unsure whether an email is phishing. The best move is to:",
                "options": [
                    "Delete it and move on",
                    "Report it — a quick check is worth it",
                    "Forward it to your team to ask",
                    "Click the link to investigate",
                ],
                "correct_index": 1,
            },
        ],
    },
]


def seed_training() -> None:
    db = SessionLocal()
    try:
        if db.execute(select(TrainingModule.id).limit(1)).first() is not None:
            return
        for m in _MODULES:
            fields = {k: v for k, v in m.items() if k != "questions"}
            questions = m["questions"]
            module = TrainingModule(created_at=utcnow(), modified_at=utcnow(), **fields)
            db.add(module)
            db.flush()
            for i, q in enumerate(questions):
                db.add(
                    QuizQuestion(
                        module_id=module.id,
                        prompt=q["prompt"],
                        options=json.dumps(q["options"]),
                        correct_index=q["correct_index"],
                        order=i,
                    )
                )
        db.commit()
        log.info("Seeded %d starter training modules.", len(_MODULES))
    finally:
        db.close()
