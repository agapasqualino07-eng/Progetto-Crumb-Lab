"""Data retention e cancellazione (criticità #11, GDPR sez. 7).

- Purge automatico: contatti oltre la finestra di retention (12 mesi,
  6 per ditte individuali — path stricter #17.7) e i `chiamato_no`.
- Cancellazione puntuale su richiesta dell'interessato (art. 17/21 GDPR).
"""

import logging
from datetime import datetime, timedelta

from core.models import Contatto, STATO_CHIAMATO_NO

log = logging.getLogger("faro.retention")


def _scaduto(c: Contatto, oggi: datetime, mesi_std: int, mesi_ditta: int) -> bool:
    if not c.data_generazione:
        return False
    try:
        generato = datetime.fromisoformat(c.data_generazione)
    except ValueError:
        return False
    mesi = mesi_ditta if c.ditta_individuale else mesi_std
    return oggi - generato > timedelta(days=mesi * 30)


def applica_retention(contatti: list[Contatto], cfg: dict,
                      oggi: datetime | None = None) -> tuple[list[Contatto], int]:
    """Ritorna (contatti superstiti, numero eliminati)."""
    oggi = oggi or datetime.now()
    mesi_std = cfg["retention"]["mesi_massimi"]
    mesi_ditta = cfg["retention"]["mesi_massimi_ditta_individuale"]
    superstiti, eliminati = [], 0
    for c in contatti:
        if c.stato_registro == STATO_CHIAMATO_NO or _scaduto(c, oggi, mesi_std, mesi_ditta):
            eliminati += 1
            continue
        superstiti.append(c)
    if eliminati:
        log.info("Retention: eliminati %d contatti (scaduti o chiamato_no)", eliminati)
    return superstiti, eliminati


def cancella_contatto(contatti: list[Contatto], place_id: str) -> tuple[list[Contatto], bool]:
    """Cancellazione su richiesta (opt-out immediato e incondizionato)."""
    dopo = [c for c in contatti if c.place_id != place_id]
    trovato = len(dopo) != len(contatti)
    if trovato:
        log.info("Cancellato contatto %s su richiesta", place_id)
    return dopo, trovato
