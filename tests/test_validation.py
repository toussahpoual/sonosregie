"""Input validation (Pydantic models in app.main)."""

import pytest
from pydantic import ValidationError

from app.main import SlotIn, SpeakerIn, StreamIn


def test_speaker_accepts_apostrophe_and_hostname():
    assert SpeakerIn(name="Cuisine d'été", ip="10.0.0.5").name == "Cuisine d'été"
    assert SpeakerIn(name="x", ip="speaker.local").ip == "speaker.local"


@pytest.mark.parametrize("ip", ["nope!!", "", "10.0.0.1/24", "1.2.3.4 ; rm -rf"])
def test_speaker_rejects_bad_ip(ip):
    with pytest.raises(ValidationError):
        SpeakerIn(name="x", ip=ip)


def test_speaker_rejects_blank_name():
    with pytest.raises(ValidationError):
        SpeakerIn(name="   ", ip="10.0.0.1")


@pytest.mark.parametrize("url", ["http://radio/stream", "https://a.example/s.mp3"])
def test_stream_accepts_http(url):
    assert StreamIn(name="r", url=url).url == url


@pytest.mark.parametrize("url", ["ftp://x", "", "justtext", "  "])
def test_stream_rejects_non_http(url):
    with pytest.raises(ValidationError):
        StreamIn(name="r", url=url)


@pytest.mark.parametrize("t", ["00:00", "08:00", "23:59"])
def test_slot_accepts_valid_time(t):
    assert SlotIn(speaker_id=1, stream_id=1, start=t, end="23:59").start == t


@pytest.mark.parametrize("t", ["25:00", "24:00", "8:00", "12:60", "abc"])
def test_slot_rejects_bad_time(t):
    with pytest.raises(ValidationError):
        SlotIn(speaker_id=1, stream_id=1, start=t, end="10:00")


def test_slot_days_normalised():
    assert SlotIn(speaker_id=1, stream_id=1, days="4,1,1,2").days == "1,2,4"
    assert SlotIn(speaker_id=1, stream_id=1, days="").days == ""


@pytest.mark.parametrize("days", ["lun", "7", "-1", "1,9"])
def test_slot_rejects_bad_days(days):
    with pytest.raises(ValidationError):
        SlotIn(speaker_id=1, stream_id=1, days=days)


@pytest.mark.parametrize("vol", [None, 0, 50, 100])
def test_slot_accepts_volume(vol):
    assert SlotIn(speaker_id=1, stream_id=1, volume=vol).volume == vol


@pytest.mark.parametrize("vol", [-1, 101, 900])
def test_slot_rejects_volume(vol):
    with pytest.raises(ValidationError):
        SlotIn(speaker_id=1, stream_id=1, volume=vol)
