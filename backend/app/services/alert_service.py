import os
import asyncio
import httpx
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.storage.database import AsyncSessionLocal
from app.models.alert import Alert
from app.core.logger import get_logger

load_dotenv()

logger = get_logger(__name__)

# Telegram config (set via env vars)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Email config (set via env vars)
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
ALERT_EMAIL_TO = os.getenv("ALERT_EMAIL_TO", "")

# Score thresholds
SCORE_ALERT_THRESHOLD = 65  # Score >= 65 triggers alert


async def check_and_create_alerts(
    session,
    coingecko_id: str,
    project_name: str,
    score: float | None,
    classification: str,
    red_flags: list[str],
    whale_signals: list[str],
    exchange_signals: list[str],
) -> list[Alert]:
    """Check analysis results and create alerts for notable events.
    Uses the provided session to avoid SQLite 'database is locked' errors."""
    alerts: list[Alert] = []

    # High score alert
    if score is not None and score >= SCORE_ALERT_THRESHOLD:
        alerts.append(Alert(
            coingecko_id=coingecko_id,
            project_name=project_name,
            alert_type="score_high",
            severity="info" if score < 80 else "critical",
            title=f"{project_name} scored {score:.0f}/100 — {classification}",
            message=f"Project {project_name} received a score of {score:.0f}/100, classified as '{classification}'.",
            score=score,
        ))

    # Critical red flags
    critical_flags = [f for f in red_flags if any(kw in f.lower() for kw in ["honeypot", "mint function", "critical"])]
    if critical_flags:
        alerts.append(Alert(
            coingecko_id=coingecko_id,
            project_name=project_name,
            alert_type="red_flag",
            severity="critical",
            title=f"{project_name} — Critical red flags detected",
            message=f"Red flags: {'; '.join(critical_flags)}",
            score=score,
            metadata_json={"red_flags": critical_flags},
        ))

    # Whale / smart money signals
    if whale_signals:
        alerts.append(Alert(
            coingecko_id=coingecko_id,
            project_name=project_name,
            alert_type="whale",
            severity="info",
            title=f"{project_name} — Whale activity detected",
            message=f"Signals: {'; '.join(whale_signals)}",
            score=score,
            metadata_json={"whale_signals": whale_signals},
        ))

    # Exchange listing signals
    notable_exchange = [s for s in exchange_signals if any(ex in s.lower() for ex in ["binance", "coinbase", "kraken"])]
    if notable_exchange:
        alerts.append(Alert(
            coingecko_id=coingecko_id,
            project_name=project_name,
            alert_type="listing",
            severity="info",
            title=f"{project_name} — Notable exchange listing",
            message="; ".join(notable_exchange),
            score=score,
        ))

    # Add alerts to the shared session (committed by caller)
    for alert in alerts:
        session.add(alert)

    # Send notifications in background (don't block analysis)
    for alert in alerts:
        await _send_notifications(alert)

    return alerts


async def _send_notifications(alert: Alert) -> None:
    """Send Telegram and email notifications for an alert."""
    tg_sent = await _send_telegram(alert)
    email_sent = await _send_email(alert)

    # Update flags on the object — will be committed by the caller's session
    alert.sent_telegram = tg_sent
    alert.sent_email = email_sent


async def _send_telegram(alert: Alert) -> bool:
    """Send alert to Telegram channel."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False

    severity_emoji = {"critical": "🔴", "warning": "🟡", "info": "🟢"}.get(alert.severity, "⚪")
    type_emoji = {
        "score_high": "🏆",
        "red_flag": "🚩",
        "whale": "🐋",
        "listing": "📊",
    }.get(alert.alert_type, "📢")

    text = (
        f"{severity_emoji} {type_emoji} *{alert.title}*\n\n"
        f"{alert.message}\n\n"
        f"Score: {alert.score:.0f}/100" if alert.score else ""
    )

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": "Markdown",
            })
            if resp.status_code == 200:
                logger.info(f"Telegram alert sent: {alert.title}")
                return True
            else:
                logger.warning(f"Telegram error {resp.status_code}: {resp.text}")
    except Exception as e:
        logger.error(f"Telegram send failed: {e}")

    return False


async def _send_email(alert: Alert) -> bool:
    """Send alert via SMTP email."""
    if not SMTP_HOST or not SMTP_USER or not ALERT_EMAIL_TO:
        return False

    try:
        msg = MIMEMultipart()
        msg["From"] = SMTP_USER
        msg["To"] = ALERT_EMAIL_TO
        msg["Subject"] = f"[100x Screener] {alert.title}"

        body = f"{alert.message}\n\nScore: {alert.score:.0f}/100\nSeverity: {alert.severity}"
        msg.attach(MIMEText(body, "plain"))

        # Run blocking SMTP in executor
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _smtp_send, msg)
        logger.info(f"Email alert sent: {alert.title}")
        return True
    except Exception as e:
        logger.error(f"Email send failed: {e}")
        return False


def _smtp_send(msg: MIMEMultipart) -> None:
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)


async def get_recent_alerts(limit: int = 50) -> list[dict]:
    """Fetch recent alerts from DB."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Alert).order_by(Alert.created_at.desc()).limit(limit)
        )
        alerts = result.scalars().all()
        return [
            {
                "id": a.id,
                "coingecko_id": a.coingecko_id,
                "project_name": a.project_name,
                "alert_type": a.alert_type,
                "severity": a.severity,
                "title": a.title,
                "message": a.message,
                "score": a.score,
                "sent_telegram": a.sent_telegram,
                "sent_email": a.sent_email,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in alerts
        ]
