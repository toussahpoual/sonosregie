"""Moteur SQLite + helpers de session."""

from __future__ import annotations

import os

from sqlmodel import Session, SQLModel, create_engine

# Le volume Quadlet monte /data ; en local on retombe sur ./data.
DB_DIR = os.environ.get("SONOS_DATA_DIR", "./data")
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "sonos.db")

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
)


def init_db() -> None:
    # importe les modèles pour enregistrer les tables avant create_all
    from app import models  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    return Session(engine)
