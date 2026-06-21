"""API FastAPI + service de l'UI statique."""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import os
import re
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator
from sqlmodel import select

from app import reconciler, sonos
from app.db import get_session, init_db
from app.models import Slot, Speaker, Stream

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

_HOST_RE = re.compile(r"^[a-zA-Z0-9._-]+$")
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

WEB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    task = asyncio.create_task(reconciler.run_loop())
    yield
    task.cancel()


app = FastAPI(title="Sonosregie", lifespan=lifespan)


# ----------------------------- Schemas (entrée) ---------------------------------
class SpeakerIn(BaseModel):
    name: str
    ip: str
    site: str = ""
    enabled: bool = True

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("nom requis")
        return v.strip()

    @field_validator("ip")
    @classmethod
    def _ip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("IP requise")
        try:
            ipaddress.ip_address(v)
            return v
        except ValueError:
            pass
        if _HOST_RE.match(v):  # tolère aussi un nom d'hôte
            return v
        raise ValueError("adresse IP ou nom d'hôte invalide")


class StreamIn(BaseModel):
    name: str
    url: str
    title: str = ""

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("nom requis")
        return v.strip()

    @field_validator("url")
    @classmethod
    def _url(cls, v: str) -> str:
        v = v.strip()
        if not re.match(r"^https?://", v):
            raise ValueError("URL http(s) requise")
        return v


class SlotIn(BaseModel):
    name: str = ""
    speaker_id: int
    stream_id: int
    days: str = ""
    start: str = "08:00"
    end: str = "18:00"
    volume: int | None = None
    enabled: bool = True

    @field_validator("start", "end")
    @classmethod
    def _time(cls, v: str) -> str:
        v = v.strip()
        if not _TIME_RE.match(v):
            raise ValueError("heure au format HH:MM (00:00–23:59)")
        return v

    @field_validator("days")
    @classmethod
    def _days(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            return ""
        parts = [p.strip() for p in v.split(",") if p.strip() != ""]
        for p in parts:
            if not p.isdigit() or not 0 <= int(p) <= 6:
                raise ValueError("jours = entiers 0..6 (0=lundi), séparés par des virgules")
        return ",".join(str(d) for d in sorted({int(p) for p in parts}))  # normalisé

    @field_validator("volume")
    @classmethod
    def _volume(cls, v: int | None) -> int | None:
        if v is not None and not 0 <= v <= 100:
            raise ValueError("volume entre 0 et 100")
        return v


# ----------------------------- Speakers -----------------------------------------
@app.get("/api/speakers")
def list_speakers():
    with get_session() as s:
        return s.exec(select(Speaker)).all()


@app.post("/api/speakers")
def create_speaker(body: SpeakerIn):
    with get_session() as s:
        sp = Speaker(**body.model_dump())
        s.add(sp)
        s.commit()
        s.refresh(sp)
        return sp


@app.put("/api/speakers/{sid}")
def update_speaker(sid: int, body: SpeakerIn):
    with get_session() as s:
        sp = s.get(Speaker, sid)
        if not sp:
            raise HTTPException(404, "enceinte introuvable")
        for k, v in body.model_dump().items():
            setattr(sp, k, v)
        s.add(sp)
        s.commit()
        s.refresh(sp)
        return sp


@app.delete("/api/speakers/{sid}")
def delete_speaker(sid: int):
    with get_session() as s:
        sp = s.get(Speaker, sid)
        if not sp:
            raise HTTPException(404, "enceinte introuvable")
        # supprime les slots rattachés
        for sl in s.exec(select(Slot).where(Slot.speaker_id == sid)).all():
            s.delete(sl)
        s.delete(sp)
        s.commit()
        return {"ok": True}


# ----------------------------- Streams ------------------------------------------
@app.get("/api/streams")
def list_streams():
    with get_session() as s:
        return s.exec(select(Stream)).all()


@app.post("/api/streams")
def create_stream(body: StreamIn):
    with get_session() as s:
        st = Stream(**body.model_dump())
        s.add(st)
        s.commit()
        s.refresh(st)
        return st


@app.put("/api/streams/{sid}")
def update_stream(sid: int, body: StreamIn):
    with get_session() as s:
        st = s.get(Stream, sid)
        if not st:
            raise HTTPException(404, "stream introuvable")
        for k, v in body.model_dump().items():
            setattr(st, k, v)
        s.add(st)
        s.commit()
        s.refresh(st)
        return st


@app.delete("/api/streams/{sid}")
def delete_stream(sid: int):
    with get_session() as s:
        st = s.get(Stream, sid)
        if not st:
            raise HTTPException(404, "stream introuvable")
        if s.exec(select(Slot).where(Slot.stream_id == sid)).first():
            raise HTTPException(409, "stream utilisé par une tranche horaire")
        s.delete(st)
        s.commit()
        return {"ok": True}


# ----------------------------- Slots --------------------------------------------
@app.get("/api/slots")
def list_slots():
    with get_session() as s:
        return s.exec(select(Slot)).all()


@app.post("/api/slots")
def create_slot(body: SlotIn):
    with get_session() as s:
        sl = Slot(**body.model_dump())
        s.add(sl)
        s.commit()
        s.refresh(sl)
        return sl


@app.put("/api/slots/{sid}")
def update_slot(sid: int, body: SlotIn):
    with get_session() as s:
        sl = s.get(Slot, sid)
        if not sl:
            raise HTTPException(404, "tranche introuvable")
        for k, v in body.model_dump().items():
            setattr(sl, k, v)
        s.add(sl)
        s.commit()
        s.refresh(sl)
        return sl


@app.delete("/api/slots/{sid}")
def delete_slot(sid: int):
    with get_session() as s:
        sl = s.get(Slot, sid)
        if not sl:
            raise HTTPException(404, "tranche introuvable")
        s.delete(sl)
        s.commit()
        return {"ok": True}


# ----------------------------- Statut & actions ---------------------------------
@app.get("/api/status")
def status():
    """État live par enceinte, alimenté par le réconciliateur."""
    return list(reconciler.STATUS.values())


@app.post("/api/speakers/{sid}/play/{stream_id}")
async def play_now(sid: int, stream_id: int, volume: int | None = None):
    """Lecture manuelle immédiate (test). Le réconciliateur reprend la main au tick."""
    with get_session() as s:
        sp = s.get(Speaker, sid)
        st = s.get(Stream, stream_id)
        if not sp or not st:
            raise HTTPException(404, "enceinte ou stream introuvable")
    try:
        await asyncio.wait_for(
            asyncio.to_thread(sonos.play_stream, sp.ip, st.url, st.title, volume),
            reconciler.OP_TIMEOUT,
        )
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"enceinte injoignable: {exc}") from exc


@app.post("/api/speakers/{sid}/stop")
async def stop_now(sid: int):
    with get_session() as s:
        sp = s.get(Speaker, sid)
        if not sp:
            raise HTTPException(404, "enceinte introuvable")
    try:
        await asyncio.wait_for(asyncio.to_thread(sonos.stop, sp.ip), reconciler.OP_TIMEOUT)
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"enceinte injoignable: {exc}") from exc


@app.post("/api/reconcile")
async def reconcile_now():
    """Force un tick immédiat (utile après modif de planning)."""
    await reconciler.tick_once()
    return {"ok": True}


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


# ----------------------------- UI statique --------------------------------------
@app.get("/")
def index():
    return FileResponse(os.path.join(WEB_DIR, "index.html"))


if os.path.isdir(WEB_DIR):
    app.mount("/web", StaticFiles(directory=WEB_DIR), name="web")
