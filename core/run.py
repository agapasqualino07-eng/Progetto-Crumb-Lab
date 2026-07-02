"""Orchestratore del run giornaliero (PROJECT.md §3).

Flusso: BUDGET GUARD → SCOUT → checkpoint → FILTRO → AUDIT → ENRICH →
SCORING → HOOK → DELIVERY → RUN REPORT.

- Resume-aware (#18d): ogni contatto porta `pipeline_stage`; un crash a
  metà run non fa ri-pagare né Apify (raw salvato al checkpoint post-SCOUT)
  né l'LLM (gli stage già completati si saltano).
- Persistenza a checkpoint (2.7): UN read batch a inizio run, write batch
  solo post-SCOUT e a fine run.

Uso:
    python -m core.run --dry-run     # pipeline completa su dati mock, zero spesa
    python -m core.run               # run reale (richiede chiavi in env)
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents import audit, budget_guard, delivery, enrich, filtro, hook, scoring, scout
from core.config import carica_config, env, nicchie_attive
from core.llm import crea_llm
from core.models import Contatto, STAGE_HOOKED, STAGE_SCORED, STATO_NUOVO, stage_raggiunto
from core.observability import RunReport, configura_log, invia_email
from core.retention import applica_retention
from core.storage import crea_storage

log = logging.getLogger("faro.run")

# Stato "fuori ciclo" per i contatti bocciati da filtro/audit: restano nel
# registro (così il dedup non li ri-aggiunge) ma non vengono mai riprocessati.
STATO_SCARTATO = "scartato"


def esegui_run(dry_run: bool, config_path: str | None = None) -> int:
    configura_log()
    cfg = carica_config(config_path)
    oggi = datetime.now()
    report = RunReport(tetto_mese_eur=cfg["budget"]["max_euro_mese"])
    storage = crea_storage(dry_run)
    llm = crea_llm(cfg, dry_run)

    # ---- UNICO read batch del run (2.7) ----
    dati = storage.leggi_tutto()
    registro = [Contatto.from_row(r) for r in dati["registro"]]
    esiti_consegna = dati["consegna"]

    # ---- [0] BUDGET GUARD (#3, #14) ----
    ok, msg_budget, spesa_mese = budget_guard.controlla(cfg, dati["spesa"], oggi)
    if not ok:
        invia_email("⛔ Faro: run bloccato dal budget guard", msg_budget, dry_run)
        return 2
    if "ALERT" in msg_budget:
        invia_email("⚠️ Faro: alert budget", msg_budget, dry_run)

    # ---- Retention (#11) ----
    registro, _ = applica_retention(registro, cfg, oggi)

    # ---- Zona corrente + espansione automatica (#1) ----
    citta, prossima = filtro.zona_da_lavorare(registro, cfg)
    report.prossima_espansione = prossima
    log.info("Zona di lavoro: %s (prossima espansione: %s)", citta, prossima or "nessuna")

    # ---- [1] SCOUT (#4, #18a, #18b) — solo se il pool `nuovo` non basta ----
    buffer_necessario = cfg["delivery"]["max_contatti_giorno"] * 2
    pool_nuovi = [c for c in registro if c.stato_registro == STATO_NUOVO]
    nuovi, costo_apify = [], 0.0
    if len(pool_nuovi) < buffer_necessario:
        nicchie = nicchie_attive(cfg)
        token = env("APIFY_TOKEN")
        for nome_nicchia, nicchia_cfg in nicchie.items():
            trovati, costo, rimossi = scout.cerca(cfg, nome_nicchia, nicchia_cfg,
                                                  citta, token, dry_run)
            nuovi += trovati
            costo_apify += costo
            report.duplicati_rimossi += rimossi
    else:
        log.info("Pool `nuovo` sufficiente (%d): SCOUT saltato, zero spesa Apify",
                 len(pool_nuovi))
    report.trovati = len(nuovi)
    report.spesa_run_eur += costo_apify

    # ---- Sincronizzazione registro: esiti umani, riciclo, merge nuovi (#1) ----
    registro, processabili = filtro.sincronizza_registro(
        registro, nuovi, esiti_consegna, cfg, oggi)

    # ---- CHECKPOINT post-SCOUT (#18d): il raw pagato è al sicuro ----
    spesa_mese = budget_guard.registra_spesa(spesa_mese, costo_apify, 0.0, oggi)
    storage.scrivi_registro([c.to_row() for c in registro])
    storage.scrivi_spesa(budget_guard.aggiorna_righe_spesa(dati["spesa"], spesa_mese))
    log.info("Checkpoint post-SCOUT scritto (%d contatti nel registro)", len(registro))

    # ---- [2] FILTRO: bucket + soglie sulle sole righe senza bucket ----
    nicchie = nicchie_attive(cfg)
    da_filtrare = [c for c in processabili if not c.bucket]
    tenuti_ids = set()
    for nome_nicchia, nicchia_cfg in nicchie.items():
        gruppo = [c for c in da_filtrare if c.nicchia == nome_nicchia]
        tenuti_ids |= {c.place_id for c in filtro.filtra(gruppo, nicchia_cfg, report)}
    for c in da_filtrare:
        if c.place_id not in tenuti_ids:
            c.stato_registro = STATO_SCARTATO
    candidati = [c for c in processabili if c.stato_registro == STATO_NUOVO and c.bucket]

    # ---- Ordina per peso bucket (#15) e limita il lavoro LLM al buffer ----
    candidati = filtro.applica_peso_bucket(candidati, cfg)[:buffer_necessario]

    # ---- [3] AUDIT (#7, #18c) ----
    candidati = audit.audita(candidati, cfg, dry_run, report, oggi)
    for c in processabili:
        # bocciati dall'audit (sito già buono) → fuori dal ciclo per sempre
        if c.bucket and c.stato_registro == STATO_NUOVO and c.ha_sito \
                and c not in candidati and stage_raggiunto(c, "audited"):
            c.stato_registro = STATO_SCARTATO

    # ---- [4] ENRICH (#2, #8, #16, #17) ----
    for nome_nicchia, nicchia_cfg in nicchie.items():
        gruppo = [c for c in candidati if c.nicchia == nome_nicchia]
        arricchiti = enrich.arricchisci(gruppo, nicchia_cfg, dry_run, report)
        scartati = {c.place_id for c in gruppo} - {c.place_id for c in arricchiti}
        candidati = [c for c in candidati
                     if c.nicchia != nome_nicchia or c.place_id not in scartati]

    # ---- [5] SCORING (#5, #6, #16) — salta chi è già scorato (#18d) ----
    da_scorare = [c for c in candidati if not stage_raggiunto(c, STAGE_SCORED)]
    gia_scorati = [c for c in candidati if stage_raggiunto(c, STAGE_SCORED)]
    scorati = scoring.assegna_score(da_scorare, llm, esiti_consegna, report) + gia_scorati

    # ---- Quality gate preliminare: hook SOLO per chi verrà consegnato ----
    selezione, _ = delivery.quality_gate(
        scorati, cfg["delivery"]["soglia_score_priorita"],
        cfg["delivery"]["max_contatti_giorno"])

    # ---- [6] HOOK (#2, #5, #6b) — salta chi ha già l'hook (#18d) ----
    da_hookare = [c for c in selezione if not stage_raggiunto(c, STAGE_HOOKED)]
    gia_hookati = [c for c in selezione if stage_raggiunto(c, STAGE_HOOKED)]
    hookati = hook.genera_hook(da_hookare, llm, report) + gia_hookati

    # ---- [7] DELIVERY + QUALITY GATE (#13) ----
    delivery.consegna(hookati, cfg, storage, report, oggi)

    # ---- Spesa LLM stimata e write finale (checkpoint fine run) ----
    # in dry-run l'LLM è finto: costo reale zero
    costo_llm = 0.0 if dry_run else round(
        llm.chiamate * cfg["budget"]["costo_stimato_llm_per_contatto_eur"], 4)
    report.spesa_run_eur = round(report.spesa_run_eur + costo_llm, 4)
    spesa_mese = budget_guard.registra_spesa(spesa_mese, 0.0, costo_llm, oggi)
    report.spesa_mese_eur = spesa_mese["euro_totale"]
    report.pool_residuo = filtro.pool_residuo_per_zona(registro)

    storage.scrivi_registro([c.to_row() for c in registro])
    storage.scrivi_spesa(budget_guard.aggiorna_righe_spesa(dati["spesa"], spesa_mese))

    # ---- [8] RUN REPORT (#12) ----
    testo = report.testo_completo()
    log.info("\n%s", testo)
    invia_email(f"Faro — {report.consegnati} lead del {oggi:%d/%m/%Y}", testo, dry_run)
    return 0


def main():
    parser = argparse.ArgumentParser(description="Faro — lead generation giornaliera")
    parser.add_argument("--dry-run", action="store_true",
                        help="pipeline completa su dati mock: zero API, zero spesa, "
                             "scrive in dryrun_output/ invece che sul Sheet")
    parser.add_argument("--config", default=None, help="percorso config alternativo")
    args = parser.parse_args()
    codice = esegui_run(args.dry_run, args.config)
    if codice == 0:
        print("\n✅ Run completato" + (" (dry-run: nessuna spesa)" if args.dry_run else ""))
    elif codice == 2:
        print("\n⛔ Run bloccato dal budget guard (vedi log)")
    sys.exit(codice)


if __name__ == "__main__":
    main()
