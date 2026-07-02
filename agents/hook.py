"""[6] HOOK via LLM (criticità #2, #5, #6b).

- OBBLIGO: l'hook parte dal `segnale_intent` più forte disponibile;
  solo in assenza di segnali ripiega sul problema-sito.
- Il prompt vive in templates/hook_prompt.md: modificabile senza toccare codice.
- Ogni hook è taggato con `hook_variante` (#6b) così il feedback loop
  scopre QUALE tipo di hook converte, non solo quale tipo di lead.
"""

import logging
from pathlib import Path

from core.models import Contatto, STAGE_HOOKED

log = logging.getLogger("faro.hook")

TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "hook_prompt.md"

SYSTEM = (
    "Sei il copywriter commerciale di un'agenzia web di Catania. Scrivi hook "
    "telefonici brevi, concreti, in italiano colloquiale ma professionale. "
    "Rispondi SOLO con JSON: {\"hook\": \"...\", \"hook_variante\": \"...\", "
    "\"bozza_messaggio\": \"...\"}"
)


def _prompt(c: Contatto) -> str:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    return template.format(
        nome=c.nome, categoria=c.categoria, citta=c.citta, bucket=c.bucket,
        sito=c.sito, problemi_sito=c.problemi_sito or "n/d",
        segnale_intent=c.segnale_intent or "NESSUNO",
        ticket_fit=c.ticket_fit, rating=c.rating_google or "n/d",
        recensioni=c.num_recensioni,
    )


def genera_hook(contatti: list[Contatto], llm, report=None) -> list[Contatto]:
    """Hook + bozza per ogni contatto scorato. Parse fallito = saltato."""
    riusciti = []
    for c in contatti:
        dati = llm.genera_json(_prompt(c), SYSTEM,
                               ["hook", "hook_variante", "bozza_messaggio"])
        if dati is None:
            if report is not None:
                report.errori.append(f"hook: parse fallito per {c.nome}, saltato")
            continue
        c.hook = str(dati["hook"])[:500]
        c.hook_variante = str(dati["hook_variante"])[:100]
        c.bozza_messaggio = str(dati["bozza_messaggio"])[:2000]
        c.pipeline_stage = STAGE_HOOKED
        riusciti.append(c)
    log.info("HOOK: %d generati su %d", len(riusciti), len(contatti))
    return riusciti
