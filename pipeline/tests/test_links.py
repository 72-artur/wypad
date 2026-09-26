from urllib.parse import parse_qs, urlparse

from wypad.links import google_flights_tfs, google_flights_url

# Verified in a browser on 2026-09-25: opens POZ⇄BCN 27–30 Nov with "Ceny ... dla 2 osób dorosłych".
VERIFIED_TFS = "GhoSCjIwMjYtMTEtMjdqBRIDUE9acgUSA0JDThoaEgoyMDI2LTExLTMwagUSA0JDTnIFEgNQT1pCAgEBSAGYAQE="


def test_tfs_matches_the_verified_link_byte_for_byte():
    assert google_flights_tfs("POZ", "BCN", "2026-11-27", "2026-11-30", adults=2) == VERIFIED_TFS


def test_url_keeps_polish_ui_and_pln():
    q = parse_qs(urlparse(google_flights_url("POZ", "BCN", "2026-11-27", "2026-11-30")).query)
    assert q["tfs"] == [VERIFIED_TFS] and q["hl"] == ["pl"] and q["curr"] == ["PLN"]


def test_passenger_count_changes_the_encoding():
    assert google_flights_tfs("POZ", "BCN", "2026-11-27", "2026-11-30", adults=1) != VERIFIED_TFS
