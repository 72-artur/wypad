import json
from datetime import date

from wypad import notify
from wypad.output import prune, publish, share_page


def make_deal(**over):
    d = {
        "id": "poz-bcn-20261016-20261019",
        "city": {"name": "Barcelona", "key": "barcelona"},
        "trip": {"out_date": "2026-10-16", "back_date": "2026-10-19", "nights": 3},
        "flight": {"carrier": "Ryanair", "out": {"from": "POZ", "from_city": "Poznań", "to": "BCN"}, "fare_total": 578,
                   "bags": {"cabin10": {"total": 236, "estimated": True}, "small": {"total": 0, "estimated": False}}},
        "stay": {"name": "Hotel <Test> & Co", "rating": 8.4, "price_total": 1180, "image": "https://example.com/h.jpg"},
        "totals": {"small": 1758, "cabin10": 1994, "checked20": 2076},
    }
    d.update(over)
    return d


def test_share_page_has_og_tags_escaping_and_redirect():
    page = share_page(make_deal(), day="2026-09-25", site_url="https://u.github.io/wypad", bag="cabin10", bag_label="10 kg")
    assert '<meta property="og:title" content="Barcelona 16.10–19.10: ok. 1994 zł za 2 osoby">' in page
    # lot (578 + 236 bagaż) + nocleg 1180 = 1994
    assert "Lot Ryanair z Poznania z bagażem 10 kg (szacunek): ok. 814 zł + nocleg Hotel &lt;Test&gt; &amp; Co (8,4/10): 1180 zł = ok. 1994 zł za 2 osoby." in page
    assert "Hotel &lt;Test&gt; &amp; Co (8,4/10)" in page          # third-party text is escaped
    assert '<meta property="og:image" content="https://example.com/h.jpg">' in page
    assert 'content="0; url=../../#/d/2026-09-25/poz-bcn-20261016-20261019"' in page
    assert "https://u.github.io/wypad/d/2026-09-25/poz-bcn-20261016-20261019.html" in page


def test_publish_writes_today_archive_and_pages(tmp_path):
    payload = {"date": "2026-09-25", "deals": [make_deal()]}
    publish(tmp_path, payload, site_url="", bag="cabin10", bag_label="10 kg", keep_days=60)
    today = json.loads((tmp_path / "data/deals.json").read_text())
    assert today["deals"][0]["share_path"] == "d/2026-09-25/poz-bcn-20261016-20261019.html"
    assert (tmp_path / "data/archive/2026-09-25.json").exists()
    assert (tmp_path / "d/2026-09-25/poz-bcn-20261016-20261019.html").exists()


def test_prune_removes_only_old_days(tmp_path):
    for day in ("2026-07-01", "2026-09-24"):
        (tmp_path / "data/archive").mkdir(parents=True, exist_ok=True)
        (tmp_path / f"data/archive/{day}.json").write_text("{}")
        (tmp_path / f"d/{day}").mkdir(parents=True)
        (tmp_path / f"d/{day}/x.html").write_text("x")
    prune(tmp_path, today=date(2026, 9, 25), keep_days=60)
    assert not (tmp_path / "data/archive/2026-07-01.json").exists()
    assert not (tmp_path / "d/2026-07-01").exists()
    assert (tmp_path / "data/archive/2026-09-24.json").exists()
    assert (tmp_path / "d/2026-09-24/x.html").exists()


def test_notifications_are_skipped_without_secrets(monkeypatch):
    for k in ("NTFY_TOPIC", "SMTP_USER", "SMTP_PASSWORD", "MAIL_TO"):
        monkeypatch.delenv(k, raising=False)
    assert notify.notify_all([make_deal()], site_url="", bag="cabin10", bag_label="10 kg", date_label="25.09") == {
        "ntfy": "skipped", "email": "skipped"}


def test_ntfy_payload(monkeypatch):
    sent = {}

    class Resp:
        def raise_for_status(self):
            pass

    def fake_post(url, data, headers, timeout):
        sent.update(url=url, body=data.decode(), headers=headers)
        return Resp()

    monkeypatch.setattr(notify.requests, "post", fake_post)
    d = make_deal(share_path="d/2026-09-25/poz-bcn-20261016-20261019.html")
    assert notify.push_ntfy([d], topic="wypad-abc", site_url="https://u.github.io/wypad", bag="cabin10", date_label="25.09")
    assert sent["url"] == "https://ntfy.sh/wypad-abc"
    assert sent["body"] == "Barcelona 16.10–19.10 (3 noce) z POZ (Ryanair): lot ok. 814 zł + nocleg 1180 zł = ok. 1994 zł za 2 os."
    assert sent["headers"]["Click"] == "https://u.github.io/wypad/d/2026-09-25/poz-bcn-20261016-20261019.html"
    assert sent["headers"]["Title"].decode() == "Wypad 25.09: Barcelona za ok. 1994 zł"


def test_email_failure_does_not_raise(monkeypatch):
    monkeypatch.setenv("SMTP_USER", "a@gmail.com")
    monkeypatch.setenv("SMTP_PASSWORD", "x")
    monkeypatch.setenv("MAIL_TO", "b@gmail.com")
    monkeypatch.delenv("NTFY_TOPIC", raising=False)

    def boom(*a, **k):
        raise OSError("smtp down")

    monkeypatch.setattr(notify.smtplib, "SMTP_SSL", boom)
    res = notify.notify_all([make_deal()], site_url="", bag="cabin10", bag_label="10 kg", date_label="25.09")
    assert res == {"ntfy": "skipped", "email": "error: OSError"}


def test_polish_plural_and_price_format():
    assert [notify.nights_pl(n) for n in (1, 2, 4, 5, 12, 22)] == ["1 noc", "2 noce", "4 noce", "5 nocy", "12 nocy", "22 noce"]
    assert notify._pln(1994) == "1994 zł" and notify._pln(12345) == "12 345 zł"


def test_icloud_smtp_uses_starttls_on_587(monkeypatch):
    events = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            events.append(("connect", host, port))

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def starttls(self, context):
            events.append(("starttls",))

        def login(self, u, p):
            events.append(("login", u))

        def send_message(self, msg):
            events.append(("send", msg["To"], msg["Subject"]))

    monkeypatch.setattr(notify.smtplib, "SMTP", FakeSMTP)
    ok = notify.send_email([make_deal()], site_url="https://u.github.io/wypad", bag="cabin10", bag_label="10 kg",
                           date_label="25.09", smtp_user="artur@icloud.com", smtp_password="x", mail_to="a@b.pl",
                           smtp_host="smtp.mail.me.com", smtp_port="587")
    assert ok
    assert events[0] == ("connect", "smtp.mail.me.com", 587)
    assert events[1] == ("starttls",) and events[2] == ("login", "artur@icloud.com")
    assert events[3] == ("send", "a@b.pl", "Wypad 25.09: Barcelona za ok. 1994 zł")


def test_same_day_rerun_keeps_morning_links_working(tmp_path):
    publish(tmp_path, {"date": "2026-09-25", "deals": [make_deal(id="old-deal")]}, site_url="", bag="cabin10", bag_label="10 kg", keep_days=60)
    publish(tmp_path, {"date": "2026-09-25", "deals": [make_deal(id="new-deal")]}, site_url="", bag="cabin10", bag_label="10 kg", keep_days=60)
    assert (tmp_path / "d/2026-09-25/old-deal.html").exists() and (tmp_path / "d/2026-09-25/new-deal.html").exists()
    archive = json.loads((tmp_path / "data/archive/2026-09-25.json").read_text())
    assert [d["id"] for d in archive["deals"]] == ["new-deal"]
    assert [d["id"] for d in archive["replaced"]] == ["old-deal"]
    assert "replaced" not in json.loads((tmp_path / "data/deals.json").read_text())


def test_index_og_tags_become_absolute_on_github(tmp_path):
    (tmp_path / "index.html").write_text('<head>\n  <meta property="og:image" content="icons/og-default.png">\n</head>')
    publish(tmp_path, {"date": "2026-09-25", "deals": []}, site_url="https://u.github.io/wypad", bag="cabin10", bag_label="10 kg", keep_days=60)
    page = (tmp_path / "index.html").read_text()
    assert '<meta property="og:image" content="https://u.github.io/wypad/icons/og-default.png">' in page
    assert '<meta property="og:url" content="https://u.github.io/wypad/">' in page




def test_exact_price_without_estimated_bag_has_no_ok_prefix():
    d = make_deal()
    assert notify.price_text(d, "small") == "1758 zł" and notify.price_text(d, "cabin10") == "ok. 1994 zł"


def test_breakdown_adds_up_to_the_published_total():
    d = make_deal()
    for bag in ("cabin10", "small"):
        flight, stay, total = notify.breakdown(d, bag)
        assert flight + stay == total == d["totals"][bag]
    assert notify.equation(d, "small") == "lot 578 zł + nocleg 1180 zł = 1758 zł"


def test_email_shows_flight_plus_stay_equals_total():
    page = notify.email_html([make_deal()], site_url="https://u.github.io/wypad", bag="cabin10", bag_label="10 kg", date_label="25.09")
    assert "Lot Ryanair z bagażem 10 kg (szacunek): ok. 814 zł" in page
    assert "+ nocleg Hotel &lt;Test&gt; &amp; Co (8,4/10): 1180 zł" in page
    assert "= <b>ok. 1994 zł</b> za 2 osoby" in page


def test_wizz_prices_are_marked_as_estimates_even_without_estimated_bags():
    d = make_deal()
    d["flight"] = {**d["flight"], "carrier": "Wizz Air", "two_seats_confirmed": False}
    assert notify.price_text(d, "small") == "ok. 1758 zł"                     # 2 × price per person
    assert notify.deal_line(d, "small").endswith("z POZ (Wizz Air): lot ok. 578 zł + nocleg 1180 zł = ok. 1758 zł za 2 os.")
    page = share_page(d, day="2026-09-26", site_url="", bag="small", bag_label="plecak")
    assert "ok. 1758 zł za 2 osoby" in page and "2 × cena za osobę" in page
    mail = notify.email_html([d], site_url="", bag="small", bag_label="plecak", date_label="26.09")
    assert "2 × cena za osobę" in mail and "= <b>ok. 1758 zł</b>" in mail
