import io
import json
import subprocess
import sys
from pathlib import Path

from live_check import decide, published_date

TODAY = "2026-09-25"


def opener_for(payload=None, fail=False):
    def opener(url, timeout):
        if fail:
            raise OSError("404")
        return io.BytesIO(json.dumps(payload).encode())
    return opener


def test_second_run_of_the_day_is_skipped():
    assert decide("https://u.github.io/wypad", False, TODAY, opener_for({"date": TODAY})) == (True, TODAY)


def test_force_or_old_data_or_sample_or_no_site_means_run():
    assert decide("x", True, TODAY, opener_for({"date": TODAY}))[0] is False            # manual "Szukaj od nowa"
    assert decide("x", False, TODAY, opener_for({"date": "2026-09-24"}))[0] is False    # yesterday's data
    assert decide("x", False, TODAY, opener_for({"date": TODAY, "sample": True}))[0] is False
    assert decide("x", False, TODAY, opener_for(fail=True)) == (False, None)            # first deploy: no site yet
    assert published_date("x", opener_for({"no": "date"})) is None


def test_script_runs_with_stdlib_only_and_prints_github_output():
    # Runs as the workflow does: a fresh interpreter, no site reachable → done=false on stdout.
    script = Path(__file__).resolve().parents[1] / "live_check.py"
    out = subprocess.run([sys.executable, str(script), "http://127.0.0.1:9/nothing"], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0 and out.stdout.strip() == "done=false"
