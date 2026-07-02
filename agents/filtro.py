"""[2] FILTRO + REGISTRO RICICLABILE (criticità #1, #15).

- Assegna il bucket (no_site / da-auditare→sito_pessimo) col peso configurabile.
- Scarta per soglie recensioni/rating/categoria.
- Gestisce il ciclo di vita del registro: nuovo → consegnato → riciclabile /
  chiamato_no / chiamato_interessato.
- Espansione geografica automatica quando il pool `nuovo` di una zona
  scende sotto soglia.
"""

import logging
from datetime import datetime

from core.models import (
    BUCKET_NO_SITE,
    BUCKET_SITO_PESSIMO,
    Contatto,
    STATO_CHIAMATO_INTERESSATO,
    STATO_CHIAMATO_NO,
    STATO_CONSEGNATO,
    STATO_NUOVO,
)

log = logging.getLogger("faro.filtro")

# Titoli/pattern che indicano una probabile ditta individuale (#17.7):
# euristica prudente — in dubbio NON marca (meglio chiedere in chiamata
# che inventare), ma "Studio Rossi di Mario Rossi" va marcato.
_INDIZI_DITTA = (" di ", "dott.", "dott ", "avv.", "geom.", "ing.", "rag.")


def probabile_ditta_individuale(nome: str) -> bool:
    n = f" {nome.lower()} "
    return any(indizio in n for indizio in _INDIZI_DITTA)


def filtra(contatti: list[Contatto], nicchia_cfg: dict, report=None) -> list[Contatto]:
    """Applica soglie e assegna bucket. Ritorna solo i contatti validi."""
    validi = []
    for c in contatti:
        if c.num_recensioni < nicchia_cfg["soglia_recensioni_min"]:
            _conta(report, "recensioni_sotto_soglia")
            continue
        try:
            rating = float(c.rating_google) if c.rating_google else None
        except ValueError:
            rating = None
        if rating is not None and rating < nicchia_cfg["soglia_rating_min"]:
            _conta(report, "rating_sotto_soglia")
            continue
        c.bucket = BUCKET_SITO_PESSIMO if c.ha_sito else BUCKET_NO_SITE
        c.ditta_individuale = probabile_ditta_individuale(c.nome)
        validi.append(c)
    log.info("FILTRO: %d validi su %d", len(validi), len(contatti))
    return validi


def _conta(report, motivo: str):
    if report is not None:
        report.aggiungi_filtro(motivo)


def applica_peso_bucket(contatti: list[Contatto], cfg: dict) -> list[Contatto]:
    """Ordina interlacciando i bucket secondo il peso configurato (#15).

    Con peso 0.6/0.4 su 10 slot: ~6 no_site e ~4 sito_pessimo, se disponibili.
    Non è un dogma: il feedback loop dirà quale bucket converte.
    """
    pesi = cfg["targeting"]["peso_bucket"]
    no_site = [c for c in contatti if c.bucket == BUCKET_NO_SITE]
    pessimi = [c for c in contatti if c.bucket == BUCKET_SITO_PESSIMO]
    risultato, quota_ns = [], pesi.get("no_site", 0.5)
    while no_site or pessimi:
        # scegli il bucket in deficit rispetto alla quota target
        tot = len(risultato) or 1
        frazione_ns = sum(1 for x in risultato if x.bucket == BUCKET_NO_SITE) / tot
        prendi_no_site = no_site and (not pessimi or frazione_ns < quota_ns)
        risultato.append(no_site.pop(0) if prendi_no_site else pessimi.pop(0))
    return risultato


def sincronizza_registro(registro: list[Contatto], nuovi: list[Contatto],
                         esiti_consegna: list[dict], cfg: dict,
                         oggi: datetime | None = None) -> tuple[list[Contatto], list[Contatto]]:
    """Fonde i nuovi scraped col registro esistente e applica il ciclo di vita (#1).

    Ritorna (registro_aggiornato, contatti_processabili).
    - Un place_id già nel registro NON viene ri-aggiunto (il registro vince).
    - Gli esiti umani letti dal tab consegna aggiornano lo stato_registro.
    - `consegnato` più vecchio di `giorni_riciclo` torna `nuovo` (riciclabile).
    """
    oggi = oggi or datetime.now()
    per_id = {c.place_id: c for c in registro}

    # 1. Esiti umani (la macchina LEGGE soltanto le colonne tue — 2.7)
    esiti = {str(r.get("place_id", "")): str(r.get("stato_chiamata", "")).strip().lower()
             for r in esiti_consegna}
    for c in registro:
        esito = esiti.get(c.place_id, "")
        if esito in ("no", "chiamato_no", "non interessato"):
            c.stato_registro = STATO_CHIAMATO_NO
        elif esito in ("interessato", "chiamato_interessato", "si", "sì"):
            c.stato_registro = STATO_CHIAMATO_INTERESSATO

    # 2. Riciclo dei `consegnato` non chiamati oltre N giorni
    for c in registro:
        if c.stato_registro == STATO_CONSEGNATO and c.data_scadenza_riciclo:
            try:
                scadenza = datetime.fromisoformat(c.data_scadenza_riciclo)
            except ValueError:
                continue
            if oggi >= scadenza:
                c.stato_registro = STATO_NUOVO
                log.info("Riciclato: %s torna `nuovo`", c.nome)

    # 3. Merge dei nuovi (senza duplicare il registro)
    aggiunti = 0
    for n in nuovi:
        if n.place_id in per_id:
            continue
        n.data_generazione = oggi.isoformat(timespec="seconds")
        registro.append(n)
        per_id[n.place_id] = n
        aggiunti += 1
    log.info("Registro: %d contatti totali (%d nuovi aggiunti)", len(registro), aggiunti)

    processabili = [c for c in registro if c.stato_registro == STATO_NUOVO]
    return registro, processabili


def pool_residuo_per_zona(registro: list[Contatto]) -> dict:
    pool: dict[str, int] = {}
    for c in registro:
        if c.stato_registro == STATO_NUOVO:
            pool[c.citta] = pool.get(c.citta, 0) + 1
    return pool


def zona_da_lavorare(registro: list[Contatto], cfg: dict) -> tuple[str, str]:
    """Espansione geografica automatica (#1).

    Scorre la lista città in config: la prima col pool `nuovo` sotto soglia
    già esaurito passa alla successiva. Ritorna (citta_corrente, prossima).
    """
    soglia = cfg["zona"]["soglia_espansione"]
    citta_lista = cfg["zona"]["citta"]
    pool = pool_residuo_per_zona(registro)
    for i, citta in enumerate(citta_lista):
        # una zona è "da lavorare" finché il suo pool non è sceso sotto soglia
        # DOPO essere stata già scandagliata (presente nel pool o mai toccata)
        mai_toccata = citta not in pool and not any(c.citta == citta for c in registro)
        if mai_toccata or pool.get(citta, 0) >= soglia:
            prossima = citta_lista[i + 1] if i + 1 < len(citta_lista) else ""
            return citta, prossima
        log.info("Zona %s sotto soglia (%d < %d): espando", citta, pool.get(citta, 0), soglia)
    return citta_lista[-1], ""
