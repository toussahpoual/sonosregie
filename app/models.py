"""Modèle de données — Speaker / Stream / Slot (SQLModel + SQLite)."""

from __future__ import annotations

from sqlmodel import Field, SQLModel


class Speaker(SQLModel, table=True):
    """Une enceinte Sonos/Symfonisk, jointe par IP (route directe via VPN/mesh)."""

    id: int | None = Field(default=None, primary_key=True)
    name: str
    ip: str = Field(index=True)
    site: str = ""  # libellé de site, purement informatif/regroupement
    enabled: bool = True  # si False, le réconciliateur ignore l'enceinte


class Stream(SQLModel, table=True):
    """Une source webradio / flux HTTP continu à pousser vers les enceintes."""

    id: int | None = Field(default=None, primary_key=True)
    name: str
    url: str  # ex: http://radio.example/stream.mp3
    title: str = ""  # libellé affiché sur l'enceinte (métadonnée DIDL)


class Slot(SQLModel, table=True):
    """Une tranche horaire : sur QUELLE enceinte jouer QUEL stream, QUAND.

    `days`  : CSV d'entiers 0=lundi … 6=dimanche. Vide = tous les jours.
    `start` / `end` : "HH:MM" locales. Si end <= start, la plage passe minuit.
    `volume`: 0–100, appliqué uniquement au démarrage de la lecture (None = inchangé).
    """

    id: int | None = Field(default=None, primary_key=True)
    name: str = ""
    speaker_id: int = Field(foreign_key="speaker.id", index=True)
    stream_id: int = Field(foreign_key="stream.id")
    days: str = ""  # "0,1,2,3,4" — vide = tous les jours
    start: str = "08:00"  # HH:MM
    end: str = "18:00"  # HH:MM
    volume: int | None = None
    enabled: bool = True
