"""[0] BUDGET GUARD (criticità #3 + #14).

Prima di ogni run: legge il contatore spesa PERSISTENTE dal tab `spesa`
del Sheet (il runner è effimero, i file locali si azzerano) e blocca
l'esecuzione se il run supererebbe il tetto mensile. Alert email all'80%.

La difesa anti runaway-cost è doppia: questa guardia pre-run (tetto mese)
+ il cap `maxCrawledPlacesPerSearch` per chiamata Apify (#18b).
"""

import logging
from datetime import datetime

log = logging.getLogger("faro.budget")


def mese_corrente(oggi: datetime | None = None) -> str:
    return (oggi or datetime.now()).strftime("%Y-%m")


def leggi_spesa_mese(righe_spesa: list[dict], mese: str) -> dict:
    """Trova (o inizializza) la riga di spesa del mese corrente."""
    for r in righe_spesa:
        if str(r.get("mese", "")) == mese:
            return {
                "mese": mese,
                "euro_apify": float(r.get("euro_apify") or 0),
                "euro_llm": float(r.get("euro_llm") or 0),
                "euro_totale": float(r.get("euro_totale") or 0),
                "ultimo_aggiornamento": r.get("ultimo_aggiornamento", ""),
            }
    return {"mese": mese, "euro_apify": 0.0, "euro_llm": 0.0,
            "euro_totale": 0.0, "ultimo_aggiornamento": ""}


def stima_costo_run(cfg: dict) -> float:
    """Stima prudente del costo del run PRIMA di lanciarlo."""
    b = cfg["budget"]
    costo_apify = b["max_risultati_giorno"] / 1000 * b["costo_stimato_per_1000_risultati_eur"]
    # ~9 chiamate LLM per contatto: scoring, hook, team copy (copywriter,
    # persuasione, telefono, revisore) e critico con eventuale riscrittura;
    # dossier ed esploratore sono ammortizzati sul run
    costo_llm = cfg["delivery"]["max_contatti_giorno"] * 9 * b["costo_stimato_llm_per_contatto_eur"]
    return round(costo_apify + costo_llm, 2)


def controlla(cfg: dict, righe_spesa: list[dict],
              oggi: datetime | None = None) -> tuple[bool, str, dict]:
    """Ritorna (ok_procedere, messaggio, spesa_mese).

    Blocca se spesa_mese + stima_run > tetto. Messaggio di alert se > 80%.
    """
    tetto = cfg["budget"]["max_euro_mese"]
    soglia_alert = tetto * cfg["budget"]["alert_percentuale"] / 100
    spesa = leggi_spesa_mese(righe_spesa, mese_corrente(oggi))
    stima = stima_costo_run(cfg)

    if spesa["euro_totale"] + stima > tetto:
        msg = (f"BLOCCATO: spesa mese €{spesa['euro_totale']:.2f} + stima run "
               f"€{stima:.2f} supererebbe il tetto di €{tetto:.2f}")
        log.error(msg)
        return False, msg, spesa

    msg = f"OK: spesa mese €{spesa['euro_totale']:.2f}/{tetto:.2f} (stima run €{stima:.2f})"
    if spesa["euro_totale"] + stima > soglia_alert:
        msg += f" — ⚠️ ALERT: superato l'{cfg['budget']['alert_percentuale']}% del tetto"
        log.warning(msg)
    else:
        log.info(msg)
    return True, msg, spesa


def registra_spesa(spesa: dict, euro_apify: float, euro_llm: float,
                   oggi: datetime | None = None) -> dict:
    """Aggiorna il contatore del mese (da riscrivere sul tab `spesa` a fine run)."""
    spesa = dict(spesa)
    spesa["euro_apify"] = round(spesa["euro_apify"] + euro_apify, 4)
    spesa["euro_llm"] = round(spesa["euro_llm"] + euro_llm, 4)
    spesa["euro_totale"] = round(spesa["euro_apify"] + spesa["euro_llm"], 4)
    spesa["ultimo_aggiornamento"] = (oggi or datetime.now()).isoformat(timespec="seconds")
    return spesa


def aggiorna_righe_spesa(righe_spesa: list[dict], spesa_mese: dict) -> list[dict]:
    """Sostituisce/aggiunge la riga del mese nel tab spesa."""
    altre = [r for r in righe_spesa if str(r.get("mese", "")) != spesa_mese["mese"]]
    return altre + [spesa_mese]
