"""Consegna mattutina su Telegram.

Ogni mattina, a fine run, il bot manda: un messaggio di riepilogo (riga di
salute) + un messaggio per ogni lead consegnato con telefono, hook, copione
e obiezioni. Serve un bot Telegram (gratuito, si crea con @BotFather) e due
secret: TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID — istruzioni nel README.

In dry-run (o senza token) i messaggi finiscono nel log e basta.
Se Telegram fallisce il run NON fallisce: l'email resta il canale di riserva.
"""

import logging

import requests

from core.config import env
from core.models import Contatto

log = logging.getLogger("faro.telegram")

API_URL = "https://api.telegram.org/bot{token}/sendMessage"
MAX_LEN = 4000   # limite Telegram 4096: teniamo margine


def _tronca(testo: str, massimo: int) -> str:
    return testo if len(testo) <= massimo else testo[: massimo - 2] + " …"


def formatta_riepilogo(report, oggi_str: str) -> str:
    return (f"🔦 FARO — {oggi_str}\n"
            f"{report.consegnati} lead da chiamare oggi.\n"
            f"{report.riga_salute()}\n"
            f"Dettagli lead nei messaggi qui sotto ⬇️ — segna gli esiti sul Sheet.")


def formatta_lead(posizione: int, c: Contatto) -> str:
    """Un messaggio per lead: tutto quello che serve per chiamare."""
    testa = (f"#{posizione} · {c.nome} — {c.citta} · score {c.score_priorita}\n"
             f"📞 {c.telefono}\n"
             f"🪝 {c.hook}\n")
    if c.ditta_individuale:
        testa += "⚠️ probabile ditta individuale: trattamento cauto\n"
    corpo = ""
    if c.copione:
        corpo += f"\n— COPIONE —\n{c.copione}\n"
    if c.obiezioni_risposte:
        corpo += f"\n— OBIEZIONI —\n{c.obiezioni_risposte}"
    # il copione non deve mangiarsi il limite: prima i dati di chiamata
    return testa + _tronca(corpo, MAX_LEN - len(testa))


def _invia(testo: str, token: str, chat_id: str) -> bool:
    try:
        r = requests.post(API_URL.format(token=token),
                          json={"chat_id": chat_id, "text": testo},
                          timeout=20)
        r.raise_for_status()
        return True
    except requests.RequestException as e:
        log.error("Telegram fallito: %s", e)   # mai stampare il token nei log
        return False


def invia_consegna(selezionati: list[Contatto], report, oggi_str: str,
                   cfg: dict, dry_run: bool) -> int:
    """Manda riepilogo + un messaggio per lead. Ritorna quanti inviati."""
    if not cfg.get("telegram", {}).get("attivo", False):
        return 0
    token, chat_id = env("TELEGRAM_BOT_TOKEN"), env("TELEGRAM_CHAT_ID")
    messaggi = [formatta_riepilogo(report, oggi_str)]
    messaggi += [formatta_lead(i + 1, c) for i, c in enumerate(selezionati)]

    if dry_run or not token or not chat_id:
        motivo = "dry-run" if dry_run else "token/chat_id non configurati"
        log.info("[telegram non inviato — %s] %d messaggi pronti; primo:\n%s",
                 motivo, len(messaggi), messaggi[0])
        return 0

    inviati = sum(1 for m in messaggi if _invia(m, token, chat_id))
    log.info("Telegram: %d/%d messaggi inviati", inviati, len(messaggi))
    return inviati
