"""Caricamento configurazione e variabili d'ambiente."""

import os
from pathlib import Path

import yaml

try:
    from dotenv import load_dotenv
except ImportError:  # dotenv è comodo in locale, non indispensabile sul runner
    load_dotenv = None

ROOT = Path(__file__).resolve().parent.parent


def carica_config(percorso: str | None = None) -> dict:
    """Legge config/config.yaml e carica il .env locale se presente.

    In produzione (GitHub Actions) il .env non esiste: le chiavi arrivano
    dalle variabili d'ambiente iniettate dai GitHub Secrets.
    """
    if load_dotenv is not None:
        load_dotenv(ROOT / ".env")
    path = Path(percorso) if percorso else ROOT / "config" / "config.yaml"
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    # Il modello LLM è sovrascrivibile via env (PROJECT.md §2.4)
    cfg["llm"]["model"] = os.environ.get("LLM_MODEL", cfg["llm"]["model"])
    return cfg


def nicchie_attive(cfg: dict) -> dict:
    """Ritorna solo le nicchie con `attiva: true`."""
    return {k: v for k, v in cfg["nicchie"].items() if v.get("attiva")}


def env(nome: str, default: str = "") -> str:
    return os.environ.get(nome, default)
