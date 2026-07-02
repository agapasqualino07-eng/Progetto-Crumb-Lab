"""[1] SCOUT — trova attività su Google Maps via Apify (criticità #4, #18a, #18b).

- Actor PINNATO: id + build (su API Apify il pinning è il query param `build`).
- Cap `maxCrawledPlacesPerSearch` SEMPRE impostato (#18b): è la vera difesa
  contro il runaway cost, il budget guard non sa quanti risultati tornerà
  una query.
- Dedup cross-query per `place_id` PRIMA di processare (#4).
- In dry-run legge il dataset mock da tests/ e non chiama nessuna API (#9).
"""

import json
import logging
from pathlib import Path

import requests

from core.models import Contatto, STAGE_SCRAPED, STATO_NUOVO

log = logging.getLogger("faro.scout")

APIFY_RUN_SYNC = "https://api.apify.com/v2/acts/{actor_id}/run-sync-get-dataset-items"
MOCK_PATH = Path(__file__).resolve().parent.parent / "tests" / "mock_attivita.json"


def _chiama_apify(cfg: dict, query: str, citta: str, token: str, cap: int) -> list[dict]:
    """Una ricerca Apify, con build pinnata e cap risultati."""
    apify = cfg["apify"]
    url = APIFY_RUN_SYNC.format(actor_id=apify["actor_id"])
    params = {"token": token}
    if apify.get("actor_build"):
        params["build"] = apify["actor_build"]   # #18a — mai "latest" in produzione
    payload = {
        "searchStringsArray": [f"{query} {citta}"],
        "maxCrawledPlacesPerSearch": cap,        # #18b
        "language": "it",
    }
    r = requests.post(url, params=params, json=payload, timeout=300)
    r.raise_for_status()
    return r.json()


def _normalizza(item: dict, nicchia: str, citta: str, provincia: str) -> Contatto:
    """Mappa i campi dell'actor Apify sul nostro modello. Campo assente = vuoto."""
    sito = (item.get("website") or "").strip()
    return Contatto(
        place_id=str(item.get("placeId") or item.get("place_id") or ""),
        nome=item.get("title") or item.get("nome") or "",
        categoria=item.get("categoryName") or item.get("categoria") or "",
        nicchia=nicchia,
        indirizzo=item.get("address") or item.get("indirizzo") or "",
        citta=item.get("city") or citta,
        provincia=provincia,
        telefono=item.get("phone") or item.get("telefono") or "",
        sito=sito if sito else "ASSENTE",
        ha_sito=bool(sito),
        rating_google=str(item.get("totalScore") if item.get("totalScore") is not None else ""),
        num_recensioni=int(item.get("reviewsCount") or 0),
        # `claimThisBusiness` True = c'è il link "rivendica" = scheda NON rivendicata
        claimed=not bool(item.get("claimThisBusiness", False)),
        stato_registro=STATO_NUOVO,
        pipeline_stage=STAGE_SCRAPED,
        fonte="google_maps_apify",
    )


def deduplica(contatti: list[Contatto]) -> tuple[list[Contatto], int]:
    """Dedup cross-query per place_id (#4). Ritorna (unici, rimossi)."""
    visti, unici = set(), []
    for c in contatti:
        chiave = c.place_id or (c.nome + "|" + c.indirizzo)
        if chiave in visti:
            continue
        visti.add(chiave)
        unici.append(c)
    return unici, len(contatti) - len(unici)


def cerca(cfg: dict, nicchia: str, nicchia_cfg: dict, citta: str,
          token: str, dry_run: bool) -> tuple[list[Contatto], float, int]:
    """Scouting per nicchia+città. Ritorna (contatti, costo_eur, duplicati_rimossi)."""
    provincia = cfg["zona"]["provincia_default"]
    cap = cfg["apify"]["max_crawled_places_per_search"]
    grezzi: list[Contatto] = []

    if dry_run:
        dati = json.loads(MOCK_PATH.read_text(encoding="utf-8"))
        grezzi = [_normalizza(d, nicchia, citta, provincia) for d in dati]
        costo = 0.0
        log.info("[dry-run] SCOUT: %d attività mock caricate", len(grezzi))
    else:
        max_run = cfg["budget"]["max_risultati_giorno"]
        for query in nicchia_cfg["categorie_google"]:
            if len(grezzi) >= max_run:
                log.info("Raggiunto max_risultati_giorno (%d), stop query", max_run)
                break
            cap_query = min(cap, max_run - len(grezzi))
            try:
                items = _chiama_apify(cfg, query, citta, token, cap_query)
                grezzi += [_normalizza(i, nicchia, citta, provincia) for i in items]
            except requests.RequestException as e:
                log.error("Apify fallita per query '%s': %s", query, e)
        costo = round(len(grezzi) / 1000
                      * cfg["budget"]["costo_stimato_per_1000_risultati_eur"], 4)

    unici, rimossi = deduplica(grezzi)
    log.info("SCOUT: %d attività (%d duplicati rimossi), costo stimato €%.2f",
             len(unici), rimossi, costo)
    return unici, costo, rimossi
