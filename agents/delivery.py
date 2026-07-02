"""[7] DELIVERY + QUALITY GATE (criticità #13).

Ordina per score_priorita e consegna SOLO i contatti sopra soglia, max N.
Se sopra soglia ce ne sono meno di N, consegna quelli e segnala
"giornata a basso rendimento" — MAI riempire con lead scadenti.
"""

import logging
from datetime import datetime, timedelta

from core.models import (
    Contatto, COLONNE_CONSEGNA, STAGE_DELIVERED, STATO_CONSEGNATO,
)

log = logging.getLogger("faro.delivery")


def quality_gate(contatti: list[Contatto], soglia: int, massimo: int) -> tuple[list[Contatto], bool]:
    """Ritorna (selezionati, giornata_basso_rendimento)."""
    sopra = [c for c in contatti if c.score_priorita and int(float(c.score_priorita)) >= soglia]
    sopra.sort(key=lambda c: int(float(c.score_priorita)), reverse=True)
    selezionati = sopra[:massimo]
    basso_rendimento = len(selezionati) < massimo
    return selezionati, basso_rendimento


def consegna(contatti: list[Contatto], cfg: dict, storage, report=None,
             oggi: datetime | None = None) -> list[Contatto]:
    """Applica il gate, marca i consegnati e APPENDE al tab consegna."""
    oggi = oggi or datetime.now()
    d = cfg["delivery"]
    selezionati, basso = quality_gate(contatti, d["soglia_score_priorita"],
                                      d["max_contatti_giorno"])
    scadenza = oggi + timedelta(days=cfg["registro"]["giorni_riciclo"])
    righe = []
    for c in selezionati:
        c.stato_registro = STATO_CONSEGNATO
        c.pipeline_stage = STAGE_DELIVERED
        c.data_scadenza_riciclo = scadenza.isoformat(timespec="seconds")
        riga = c.to_row()
        righe.append({k: riga.get(k, "") for k in COLONNE_CONSEGNA})
    storage.appendi_consegna(righe)
    if report is not None:
        report.consegnati = len(selezionati)
        report.giornata_basso_rendimento = basso
    if basso:
        log.warning("Giornata a basso rendimento: %d lead sopra soglia (target %d)",
                    len(selezionati), d["max_contatti_giorno"])
    log.info("DELIVERY: %d contatti consegnati", len(selezionati))
    return selezionati
