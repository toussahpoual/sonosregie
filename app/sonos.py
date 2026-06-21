"""Pilotage bas niveau d'une enceinte Sonos via SoCo.

Toutes les fonctions sont synchrones/bloquantes (I/O réseau vers l'enceinte) ;
le réconciliateur les exécute dans un threadpool avec timeout.
"""

from __future__ import annotations

from dataclasses import dataclass

from soco import SoCo


def radio_uri(url: str) -> str:
    """Transforme une URL http(s) en URI webradio Sonos déterministe.

    On l'utilise à la fois pour LIRE et pour COMPARER l'état courant, de sorte
    que l'URI poussée == l'URI lue par get_current_track_info (sinon force_radio
    réécrirait derrière notre dos et la comparaison échouerait).
    """
    scheme_less = url.split("://", 1)[-1]
    return "x-rincon-mp3radio://" + scheme_less


@dataclass
class SpeakerState:
    reachable: bool
    transport: str = ""  # PLAYING / PAUSED_PLAYBACK / STOPPED / ...
    current_uri: str = ""
    volume: int | None = None
    error: str = ""


def get_state(ip: str) -> SpeakerState:
    try:
        d = SoCo(ip)
        info = d.get_current_transport_info()
        track = d.get_current_track_info()
        return SpeakerState(
            reachable=True,
            transport=info.get("current_transport_state", ""),
            current_uri=track.get("uri", ""),
            volume=d.volume,
        )
    except Exception as exc:  # injoignable / éteinte / erreur SOAP
        return SpeakerState(reachable=False, error=str(exc))


def play_stream(ip: str, url: str, title: str = "", volume: int | None = None) -> None:
    d = SoCo(ip)
    if volume is not None:
        d.volume = max(0, min(100, int(volume)))
    d.play_uri(radio_uri(url), title=title or "Web radio")


def stop(ip: str) -> None:
    SoCo(ip).stop()


def _canonical(uri: str) -> str:
    """Réduit une URI à `hôte/chemin`, en retirant le préfixe webradio Sonos
    ET le schéma interne. Indispensable : la Sonos renvoie
    `x-rincon-mp3radio://http://host/path` même quand on a poussé une autre forme
    (et réécrit https -> http). On compare donc les formes canoniques, pas les
    chaînes brutes (sinon l'arrêt en fin de plage ne se déclenche jamais)."""
    u = (uri or "").strip()
    if u.startswith("x-rincon-mp3radio://"):
        u = u[len("x-rincon-mp3radio://") :]
    for scheme in ("https://", "http://"):
        if u.startswith(scheme):
            u = u[len(scheme) :]
            break
    return u.rstrip("/")


def is_playing_uri(state: SpeakerState, url: str) -> bool:
    return state.transport == "PLAYING" and _canonical(state.current_uri) == _canonical(url)
