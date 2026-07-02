"""[5] SCORING via LLM (criticità #5, #6, #16).

Input: dati contatto + criteri nicchia + segnale_intent + ticket_fit.
Output: score_priorita 0-100 + motivazione.

- Parsing JSON robusto delegato a core/llm.py (#5).
- Feedback loop (#6): gli esiti delle chiamate (tab consegna) diventano
  statistiche passate nel prompt.
- Garanzia ticket-fit (#16) anche lato codice: con `ticket_fit=basso`
  lo score viene comunque limitato sotto la soglia "in cima", qualunque
  cosa dica l'LLM — un microbusiness non deve mai essere primo.
"""

import logging

from core.models import Contatto, STAGE_SCORED

log = logging.getLogger("faro.scoring")

CAP_TICKET_BASSO = 55  # score massimo consentito con capacità di spesa bassa

SYSTEM = (
    "Sei l'analista commerciale di un'agenzia web di Catania (siti web + "
    "posizionamento, ticket €1.500-5.000). Case study reale: una concessionaria "
    "a Catania ha ottenuto +10 chiamate e +5 visite/settimana dopo il sito nuovo. "
    "Valuti lead B2B: aziende locali senza sito o con sito pessimo. "
    "Rispondi SOLO con JSON: {\"score_priorita\": <0-100>, \"motivazione\": \"...\"}"
)


def statistiche_feedback(esiti_consegna: list[dict]) -> str:
    """Versione minima del feedback loop (#6): conta cosa ha convertito."""
    conteggi: dict[str, dict[str, int]] = {}
    for r in esiti_consegna:
        esito = str(r.get("stato_chiamata", "")).strip().lower()
        if esito not in ("interessato", "chiamato_interessato", "si", "sì",
                         "no", "chiamato_no", "non interessato"):
            continue
        positivo = esito in ("interessato", "chiamato_interessato", "si", "sì")
        for dim in ("categoria", "bucket", "ticket_fit", "hook_variante"):
            valore = str(r.get(dim, "")).strip()
            if not valore:
                continue
            chiave = f"{dim}={valore}"
            conteggi.setdefault(chiave, {"si": 0, "no": 0})
            conteggi[chiave]["si" if positivo else "no"] += 1
    if not conteggi:
        return ""
    righe = [f"- {k}: {v['si']} interessati, {v['no']} no" for k, v in conteggi.items()]
    return "Esiti storici delle chiamate (pesa di più ciò che ha convertito):\n" + "\n".join(righe)


def _prompt(c: Contatto, feedback: str) -> str:
    return f"""Valuta questo lead e assegna score_priorita 0-100.

Criteri, in ordine di peso:
1. ticket_fit (capacità di spesa €1.5-5k): con ticket_fit basso lo score NON può superare {CAP_TICKET_BASSO}.
2. segnale_intent: un "perché adesso" concreto vale molto più del generico problema-sito.
3. bucket/qualità sito: no_site o sito con problemi gravi = dolore reale.

Dati del lead:
nome: {c.nome}
categoria: {c.categoria}
citta: {c.citta}
bucket: {c.bucket}
sito: {c.sito}
score_sito: {c.score_sito or "n/d"}
problemi_sito: {c.problemi_sito or "n/d"}
audit_parziale: {c.audit_parziale}
rating_google: {c.rating_google or "n/d"}
num_recensioni: {c.num_recensioni}
segnale_intent: {c.segnale_intent}
ticket_fit: {c.ticket_fit}

{feedback}"""


def assegna_score(contatti: list[Contatto], llm, esiti_consegna: list[dict],
                  report=None) -> list[Contatto]:
    """Scoring LLM per ogni contatto; parse fallito = contatto saltato, run vivo."""
    feedback = statistiche_feedback(esiti_consegna)
    riusciti = []
    for c in contatti:
        dati = llm.genera_json(_prompt(c, feedback), SYSTEM,
                               ["score_priorita", "motivazione"])
        if dati is None:
            if report is not None:
                report.errori.append(f"scoring: parse fallito per {c.nome}, saltato")
            continue
        try:
            score = int(float(dati["score_priorita"]))
        except (TypeError, ValueError):
            if report is not None:
                report.errori.append(f"scoring: score non numerico per {c.nome}, saltato")
            continue
        if c.ticket_fit == "basso":
            score = min(score, CAP_TICKET_BASSO)   # #16, garanzia lato codice
        c.score_priorita = str(max(0, min(100, score)))
        c.motivazione_score = str(dati["motivazione"])[:500]
        c.pipeline_stage = STAGE_SCORED
        riusciti.append(c)
    log.info("SCORING: %d scorati su %d", len(riusciti), len(contatti))
    return riusciti
