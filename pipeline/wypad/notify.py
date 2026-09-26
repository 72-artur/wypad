"""Morning notifications: ntfy push + e-mail. Each channel is skipped when its secret is missing."""
from __future__ import annotations

import html
import logging
import os
import smtplib
import ssl
from email.message import EmailMessage

import requests

log = logging.getLogger(__name__)


def _pln(x: float) -> str:
    # Polish convention: no grouping for 4-digit numbers, thin space from 10 000 up.
    n = int(round(x))
    s = f"{n:,}".replace(",", " ") if n >= 10000 else str(n)
    return f"{s} zł"


def nights_pl(n: int) -> str:
    if n == 1:
        return "1 noc"
    return f"{n} noce" if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14) else f"{n} nocy"


def estimated(d: dict, bag: str) -> bool:
    return bool(((d.get("flight") or {}).get("bags") or {}).get(bag, {}).get("estimated"))


def price_text(d: dict, bag: str) -> str:
    """'ok. 1994 zł' when the total contains an estimated baggage price."""
    return f"{'ok. ' if estimated(d, bag) else ''}{_pln(d['totals'][bag])}"


def breakdown(d: dict, bag: str) -> tuple[int, int, int]:
    """(lot z bagażem, nocleg, razem) — the same numbers the app shows as 'lot + nocleg = razem'."""
    flight = round(d["flight"]["fare_total"] + d["flight"]["bags"][bag]["total"])
    stay = round((d.get("stay") or {}).get("price_total", 0))
    return flight, stay, flight + stay


def equation(d: dict, bag: str) -> str:
    flight, stay, total = breakdown(d, bag)
    ok = "ok. " if estimated(d, bag) else ""
    return f"lot {ok}{_pln(flight)} + nocleg {_pln(stay)} = {ok}{_pln(total)}"


def deal_line(d: dict, bag: str) -> str:
    out, back = d["trip"]["out_date"], d["trip"]["back_date"]
    return (f"{d['city']['name']} {out[8:10]}.{out[5:7]}–{back[8:10]}.{back[5:7]} "
            f"({nights_pl(d['trip']['nights'])}) z {d['flight']['out']['from']}: {equation(d, bag)} za 2 os.")


def deal_url(site_url: str, d: dict) -> str:
    return f"{site_url}/{d['share_path']}" if site_url and d.get("share_path") else site_url


def push_ntfy(deals: list[dict], *, topic: str | None, site_url: str, bag: str, date_label: str,
              server: str = "https://ntfy.sh") -> bool:
    if not topic or not deals:
        return False
    top = deals[:3]
    body = "\n".join(deal_line(d, bag) for d in top)
    click = deal_url(site_url, top[0]) or site_url
    headers = {
        "Title": f"Wypad {date_label}: {top[0]['city']['name']} za {price_text(top[0], bag)}".encode("utf-8"),
        "Tags": "airplane",
        "Priority": "default",
    }
    if click:
        headers["Click"] = click
    if site_url:
        headers["Actions"] = f"view, Wszystkie okazje, {site_url}"
    r = requests.post(f"{server}/{topic}", data=body.encode("utf-8"), headers=headers, timeout=20)
    r.raise_for_status()
    log.info("ntfy: sent %d deals", len(top))
    return True


def email_html(deals: list[dict], *, site_url: str, bag: str, bag_label: str, date_label: str) -> str:
    rows = []
    for d in deals[:6]:
        stay = d.get("stay") or {}
        url = html.escape(deal_url(site_url, d) or "#")
        rows.append(f"""
        <tr><td style="padding:14px 0;border-bottom:1px solid #e5eaf1">
          <div style="font:700 12px/1.3 Arial,sans-serif;color:#6f7b8f;text-transform:uppercase;letter-spacing:.06em">
            {html.escape(d['flight']['out']['from'])} → {html.escape(d['flight']['out']['to'])} · {html.escape(d['trip']['out_date'][8:10])}.{html.escape(d['trip']['out_date'][5:7])}–{html.escape(d['trip']['back_date'][8:10])}.{html.escape(d['trip']['back_date'][5:7])} · {nights_pl(d['trip']['nights'])}</div>
          <div style="font:800 22px/1.2 Arial,sans-serif;color:#121923;margin-top:4px">{html.escape(d['city']['name'])}
            <span style="float:right;color:#cf4f35">{price_text(d, bag)}</span></div>
          <div style="font:14px/1.45 Arial,sans-serif;color:#485365;margin-top:4px">
            Lot {html.escape(d['flight']['carrier'])} z bagażem {html.escape(bag_label)}{' (szacunek)' if estimated(d, bag) else ''}: {'ok. ' if estimated(d, bag) else ''}{_pln(breakdown(d, bag)[0])}
            + nocleg {html.escape(stay.get('name', ''))}{f" ({stay['rating']:.1f}/10)".replace('.', ',') if stay.get('rating') else ''}: {_pln(breakdown(d, bag)[1])}
            = <b>{price_text(d, bag)}</b> za 2 osoby</div>
          <a href="{url}" style="display:inline-block;margin-top:8px;font:700 14px Arial,sans-serif;color:#2c63a8">Zobacz szczegóły →</a>
        </td></tr>""")
    return f"""<!doctype html><html lang="pl"><body style="margin:0;background:#ecf0f5">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#ecf0f5"><tr><td align="center" style="padding:24px 12px">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#ffffff;border-radius:16px">
      <tr><td style="padding:22px 24px 6px;background:#121720;border-radius:16px 16px 0 0">
        <div style="font:900 28px/1 Arial Narrow,Arial,sans-serif;color:#ffb547;letter-spacing:.06em">ODLOTY · {html.escape(date_label)}</div>
        <div style="font:13px/1.5 Arial,sans-serif;color:#8d97a8;padding:6px 0 14px">Ceny za 2 osoby: loty w obie strony, bagaż ({html.escape(bag_label)}; cena bagażu to szacunek z cennika Ryanair) i nocleg na cały pobyt.</div>
      </td></tr>
      <tr><td style="padding:4px 24px 8px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0">{''.join(rows)}</table></td></tr>
      <tr><td style="padding:8px 24px 24px;font:13px/1.5 Arial,sans-serif;color:#6f7b8f">
        <a href="{html.escape(site_url or '#')}" style="color:#2c63a8;font-weight:700">Wszystkie okazje w aplikacji</a><br>
        Ceny zmieniają się często. Aktualną cenę zobaczysz u przewoźnika i w serwisie noclegowym przed zakupem.</td></tr>
    </table></td></tr></table></body></html>"""


def send_email(deals: list[dict], *, site_url: str, bag: str, bag_label: str, date_label: str,
               smtp_user: str | None, smtp_password: str | None, mail_to: str | None,
               smtp_host: str | None = None, smtp_port: int | None = None) -> bool:
    """Gmail (smtp.gmail.com:465, app password) by default; iCloud Mail works too (smtp.mail.me.com:587,
    app-specific password) via SMTP_HOST / SMTP_PORT."""
    if not (smtp_user and smtp_password and mail_to and deals):
        return False
    host = smtp_host or "smtp.gmail.com"
    port = int(smtp_port or 465)
    top = deals[0]
    msg = EmailMessage()
    msg["Subject"] = (f"Wypad {date_label}: {top['city']['name']} za {price_text(top, bag)}"
                      f"{f' i {len(deals) - 1} innych okazji' if len(deals) > 1 else ''}")
    msg["From"] = f"Wypad <{smtp_user}>"
    msg["To"] = mail_to
    text = "\n".join(f"- {deal_line(d, bag)}\n  {deal_url(site_url, d)}" for d in deals[:6])
    msg.set_content(f"Dzisiejsze okazje (ceny za 2 osoby, bagaż: {bag_label}):\n\n{text}\n\n{site_url}")
    msg.add_alternative(email_html(deals, site_url=site_url, bag=bag, bag_label=bag_label, date_label=date_label), subtype="html")
    ctx = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=ctx, timeout=30) as s:
            s.login(smtp_user, smtp_password)
            s.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=30) as s:
            s.starttls(context=ctx)
            s.login(smtp_user, smtp_password)
            s.send_message(msg)
    log.info("e-mail: sent via %s:%s (%d recipient(s))", host, port, len([a for a in mail_to.split(",") if a.strip()]))
    return True


def notify_all(deals: list[dict], *, site_url: str, bag: str, bag_label: str, date_label: str) -> dict:
    """Never let a notification failure break the daily run; report what happened instead."""
    channels = {
        "ntfy": lambda: push_ntfy(deals, topic=os.environ.get("NTFY_TOPIC"), site_url=site_url, bag=bag,
                                  date_label=date_label),
        "email": lambda: send_email(deals, site_url=site_url, bag=bag, bag_label=bag_label, date_label=date_label,
                                    smtp_user=os.environ.get("SMTP_USER"), smtp_password=os.environ.get("SMTP_PASSWORD"),
                                    mail_to=os.environ.get("MAIL_TO"), smtp_host=os.environ.get("SMTP_HOST"),
                                    smtp_port=os.environ.get("SMTP_PORT")),
    }
    result = {}
    for name, send in channels.items():
        try:
            result[name] = "sent" if send() else "skipped"
        except Exception as e:  # noqa: BLE001 — surfaced in the run log
            log.warning("%s failed: %s", name, e)
            result[name] = f"error: {type(e).__name__}"
    return result
