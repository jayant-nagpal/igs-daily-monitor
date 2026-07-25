"""
Boundary tests for the send_alerts_mail market-hours window (WS3 / S6).

Proves the OLD condition `today < close or today > open` is a tautology
(always True) and the corrected inclusive window [open_time, close_time]
matches the intended "inside market hours" semantics. Also asserts the fix
is actually present in the shipped source.

    start_time_min = 555 -> open_time  = 09:15
    end_time_min   = 935 -> close_time = 15:35

No DB, no email, no network.
"""
import datetime as dt
from pathlib import Path

import pytest

OPEN_MIN = 555   # 09:15
CLOSE_MIN = 935  # 15:35


def _t(hh, mm):
    base = dt.datetime(2026, 7, 15, 0, 0, 0)
    return base + dt.timedelta(hours=hh, minutes=mm)


def old_condition(today):
    open_time = _t(0, OPEN_MIN)
    close_time = _t(0, CLOSE_MIN)
    # original: `today_date < close_time or today_date > open_time`
    return today < close_time or today > open_time


def new_condition(today):
    open_time = _t(0, OPEN_MIN)
    close_time = _t(0, CLOSE_MIN)
    # intended "during market hours": inclusive window
    return open_time <= today <= close_time


CASES = [
    ("00:00 midnight", _t(0, 0), False),
    ("09:14 pre-open", _t(9, 14), False),
    ("09:15 open (bound)", _t(9, 15), True),
    ("12:00 midday", _t(12, 0), True),
    ("15:35 close (bound)", _t(15, 35), True),
    ("15:36 post-close", _t(15, 36), False),
    ("23:59 late", _t(23, 59), False),
]


@pytest.mark.parametrize("label,t,_expected", CASES)
def test_old_condition_is_tautology(label, t, _expected):
    assert old_condition(t) is True, f"OLD not tautology at {label}"


@pytest.mark.parametrize("label,t,expected", CASES)
def test_new_condition_matches_market_window(label, t, expected):
    assert new_condition(t) == expected, f"NEW wrong at {label}"


def test_fix_present_in_shipped_source():
    # send_alerts_mail.py lives in the producer tree and ships as a patch; if
    # the tree is absent in this checkout, skip rather than fail.
    src_path = (Path(__file__).resolve().parents[1]
                / "pythonbatchscripts" / "algo_alerts" / "send_alerts_mail.py")
    if not src_path.exists():
        pytest.skip("send_alerts_mail.py (producer tree) not present")
    src = src_path.read_text()
    assert "open_time <= today_date <= close_time" in src
