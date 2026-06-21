"""Boucle de réconciliation — le cœur de l'ordonnancement.

Toutes les TICK secondes, pour chaque enceinte activée :
  1. on calcule le « stream désiré » = le slot actif couvrant l'instant présent ;
  2. on lit l'état réel de l'enceinte (si injoignable -> on saute, le tick suivant
     réessaiera : c'est gratuitement le RETRY demandé) ;
  3. si désiré ET pas déjà en train de jouer ce stream -> on (re)lance + volume ;
  4. si rien de désiré ET l'enceinte joue l'UN de NOS streams -> on arrête.

Ce modèle « état désiré » couvre : retry après extinction, multi-tranches,
arrêt en fin de plage, reprise après reboot de l'app — sans bookkeeping.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, time

from sqlmodel import select

from app import sonos
from app.db import get_session
from app.models import Slot, Speaker, Stream

log = logging.getLogger("reconciler")

TICK_SECONDS = 30
OP_TIMEOUT = 8  # garde-fou par opération réseau enceinte

# Journal d'état exposé à l'UI (en mémoire, par enceinte).
STATUS: dict[int, dict] = {}


def _parse_hhmm(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


def _slot_active(slot: Slot, now: datetime) -> bool:
    if not slot.enabled:
        return False
    start = _parse_hhmm(slot.start)
    end = _parse_hhmm(slot.end)
    t = now.time()

    allowed = None
    if slot.days.strip():
        allowed = {int(x) for x in slot.days.split(",") if x.strip() != ""}

    if start < end:
        if not (start <= t < end):
            return False
        day = now.weekday()  # plage dans la journée
    else:
        # plage qui passe minuit (ex: 22:00 -> 06:00) : le JOUR coché s'applique
        # au démarrage. La portion du matin appartient au jour de démarrage = hier.
        if t >= start:
            day = now.weekday()  # portion du soir
        elif t < end:
            day = (now.weekday() - 1) % 7  # portion du matin -> jour précédent
        else:
            return False

    return allowed is None or day in allowed


def desired_slot(slots: list[Slot], now: datetime) -> Slot | None:
    """Slot actif pour l'enceinte ; si plusieurs se chevauchent, on prend
    celui dont l'heure de début est la plus tardive (priorité au plus récent)."""
    active = [s for s in slots if _slot_active(s, now)]
    if not active:
        return None
    return max(active, key=lambda s: _parse_hhmm(s.start))


async def _reconcile_speaker(
    sp: Speaker, slots: list[Slot], streams: dict[int, Stream], now: datetime
) -> None:
    entry: dict = {"name": sp.name, "ip": sp.ip, "site": sp.site, "ts": now.isoformat(timespec="seconds")}
    try:
        want = desired_slot(slots, now)
        state = await asyncio.wait_for(asyncio.to_thread(sonos.get_state, sp.ip), OP_TIMEOUT)
        entry["reachable"] = state.reachable
        if not state.reachable:
            entry["status"] = "injoignable (retry au prochain tick)"
            entry["error"] = state.error
            STATUS[sp.id] = entry
            return

        if want is not None:
            stream = streams.get(want.stream_id)
            if stream is None:
                entry["status"] = "slot sans stream valide"
                STATUS[sp.id] = entry
                return
            entry["desired"] = {"slot": want.name or f"#{want.id}", "stream": stream.name}
            if sonos.is_playing_uri(state, stream.url):
                entry["status"] = f"OK — joue « {stream.name} »"
            else:
                await asyncio.wait_for(
                    asyncio.to_thread(sonos.play_stream, sp.ip, stream.url, stream.title, want.volume),
                    OP_TIMEOUT,
                )
                entry["status"] = f"démarré « {stream.name} »" + (
                    f" @vol {want.volume}" if want.volume is not None else ""
                )
                log.info("speaker %s -> play %s", sp.name, stream.name)
        else:
            # aucun slot actif : on n'arrête QUE si l'enceinte joue l'un de nos streams
            ours = any(sonos.is_playing_uri(state, st.url) for st in streams.values())
            if ours:
                await asyncio.wait_for(asyncio.to_thread(sonos.stop, sp.ip), OP_TIMEOUT)
                entry["status"] = "arrêté (hors plage)"
                log.info("speaker %s -> stop (hors plage)", sp.name)
            else:
                entry["status"] = "inactif (rien de planifié)"
        STATUS[sp.id] = entry
    except TimeoutError:
        entry["reachable"] = False
        entry["status"] = "timeout (retry au prochain tick)"
        STATUS[sp.id] = entry
    except Exception as exc:  # noqa: BLE001
        entry["reachable"] = False
        entry["status"] = "erreur"
        entry["error"] = str(exc)
        STATUS[sp.id] = entry
        log.exception("reconcile %s", sp.name)


async def tick_once() -> None:
    now = datetime.now()
    with get_session() as ses:
        speakers = ses.exec(select(Speaker).where(Speaker.enabled == True)).all()  # noqa: E712
        all_slots = ses.exec(select(Slot)).all()
        streams = {s.id: s for s in ses.exec(select(Stream)).all()}
    # purge des enceintes disparues du statut
    live_ids = {sp.id for sp in speakers}
    for gone in [k for k in STATUS if k not in live_ids]:
        STATUS.pop(gone, None)
    await asyncio.gather(
        *(
            _reconcile_speaker(sp, [s for s in all_slots if s.speaker_id == sp.id], streams, now)
            for sp in speakers
        )
    )


async def run_loop() -> None:
    log.info("réconciliateur démarré (tick=%ss)", TICK_SECONDS)
    while True:
        try:
            await tick_once()
        except Exception:  # noqa: BLE001
            log.exception("tick global")
        await asyncio.sleep(TICK_SECONDS)
