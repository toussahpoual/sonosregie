"""Slot activeness logic, incl. overnight slots vs day-of-week."""

from datetime import datetime
from types import SimpleNamespace

import pytest

from app.reconciler import _slot_active

# Reference dates (2026): Wed=Jun 17, Fri=Jun 19, Sat=Jun 20.
WED_10 = datetime(2026, 6, 17, 10, 0)
FRI_23 = datetime(2026, 6, 19, 23, 0)
SAT_02 = datetime(2026, 6, 20, 2, 0)
SAT_10 = datetime(2026, 6, 20, 10, 0)
SAT_12 = datetime(2026, 6, 20, 12, 0)
SAT_23 = datetime(2026, 6, 20, 23, 0)


def slot(days, start, end, enabled=True):
    return SimpleNamespace(enabled=enabled, days=days, start=start, end=end)


@pytest.mark.parametrize(
    "now,expected",
    [
        (FRI_23, True),  # evening portion -> start day = Friday (allowed)
        (SAT_02, True),  # morning portion -> start day = Friday (allowed)
        (SAT_23, False),  # evening portion on Saturday -> start day = Saturday (not allowed)
        (SAT_12, False),  # outside the time window entirely
    ],
)
def test_overnight_slot_weekday(now, expected):
    # Friday-only slot crossing midnight (22:00 -> 06:00)
    assert _slot_active(slot("4", "22:00", "06:00"), now) is expected


@pytest.mark.parametrize("now,expected", [(WED_10, True), (SAT_10, False)])
def test_daytime_slot_weekday(now, expected):
    # Mon–Fri, 09:00 -> 12:00
    assert _slot_active(slot("0,1,2,3,4", "09:00", "12:00"), now) is expected


def test_empty_days_means_every_day():
    assert _slot_active(slot("", "09:00", "12:00"), WED_10) is True
    assert _slot_active(slot("", "09:00", "12:00"), SAT_10) is True


def test_disabled_slot_never_active():
    assert _slot_active(slot("", "00:00", "23:59", enabled=False), WED_10) is False
