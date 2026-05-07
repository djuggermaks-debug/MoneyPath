import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime


SIGNAL_EMOJI = {
    "бычий": "📈",
    "медвежий": "📉",
    "нейтральный": "➡️",
}

STRENGTH_LABEL = {
    1: "очень слабый",
    2: "слабый",
    3: "умеренный",
    4: "сильный",
    5: "очень сильный",
}


def send_alert(instrument_name, analysis, market_data, news_articles):
    email_from = os.environ["EMAIL_FROM"]
    email_to = os.environ["EMAIL_TO"]
    email_password = os.environ["EMAIL_PASSWORD"]

    signal = analysis.get("signal", "нейтральный")
    strength = analysis.get("strength", 1)
    emoji = SIGNAL_EMOJI.get(signal, "")
    strength_label = STRENGTH_LABEL.get(strength, str(strength))

    price = market_data.get("price", {})
    indicators = market_data.get("indicators", {})
    position = market_data.get("position")

    now = datetime.utcnow().strftime("%d.%m.%Y %H:%M UTC")

    subject = f"{emoji} {instrument_name} — {signal} сигнал ({strength_label}) | {now}"

    position_block = ""
    if position:
        direction = position.get("direction", "")
        pnl = position.get("upl", "?")
        level = position.get("level", "?")
        position_block = f"""
<tr><td colspan="2" style="background:#fff3cd;padding:10px;border-radius:6px;">
  ⚠️ <b>Открытая позиция:</b> {direction} с уровня {level} | P&L: {pnl}
</td></tr>"""

    news_rows = ""
    for a in news_articles[:5]:
        news_rows += f'<tr><td style="padding:4px 0;color:#555;">[{a["source"]}] <a href="{a["link"]}">{a["title"]}</a></td></tr>'

    html = f"""
<html><body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;">

<h2 style="color:#1a1a1a;">{emoji} {instrument_name}</h2>
<p style="color:#666;font-size:13px;">{now}</p>

<table width="100%" cellpadding="8" style="border-collapse:collapse;">
  {position_block}
  <tr style="background:#f8f9fa;">
    <td><b>Сигнал</b></td>
    <td>{emoji} <b>{signal.upper()}</b> — {strength_label} ({strength}/5)</td>
  </tr>
  <tr>
    <td><b>Цена</b></td>
    <td>{price.get('mid')} ({price.get('change_pct', '?')}% за день)</td>
  </tr>
  <tr style="background:#f8f9fa;">
    <td><b>RSI</b></td>
    <td>{indicators.get('rsi', '?')}</td>
  </tr>
  <tr>
    <td><b>Поддержка</b></td>
    <td>{indicators.get('support', '?')}</td>
  </tr>
  <tr style="background:#f8f9fa;">
    <td><b>Сопротивление</b></td>
    <td>{indicators.get('resistance', '?')}</td>
  </tr>
</table>

<div style="margin:16px 0;padding:12px;background:#e8f4fd;border-left:4px solid #2196F3;border-radius:4px;">
  <b>Главный фактор:</b> {analysis.get('key_factor', '')}
</div>

<div style="margin:16px 0;padding:12px;background:#f0f7ee;border-left:4px solid #4CAF50;border-radius:4px;">
  <b>Что делать:</b> {analysis.get('action', '')}
</div>

<div style="margin:16px 0;padding:12px;background:#fff8e1;border-left:4px solid #FF9800;border-radius:4px;">
  <b>Риск:</b> {analysis.get('risk', '')}
</div>

<p style="color:#555;">{analysis.get('reasoning', '')}</p>

<h3 style="color:#333;margin-top:24px;">Новости</h3>
<table width="100%" cellpadding="4">
  {news_rows}
</table>

<p style="color:#aaa;font-size:11px;margin-top:32px;">MoneyPath Alert System</p>
</body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = email_from
    msg["To"] = email_to
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(email_from, email_password)
        server.sendmail(email_from, email_to, msg.as_string())

    print(f"Алерт отправлен: {subject}")
