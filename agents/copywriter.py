"""[6b] COPYWRITER (team copy) — copione telefonico personalizzato per lead.

Parte dall'hook (che già rispetta la regola del segnale di intent, #2) e
lo sviluppa in un copione completo: apertura, domande di discovery, pitch,
chiusura su micro-impegno. Struttura nel template `templates/copione_prompt.md`
(modificabile senza toccare codice, come per gli hook).
"""

import logging
from pathlib import Path

from core.models import Contatto

log = logging.getLogger("faro.copy.writer")

TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "copione_prompt.md"

SYSTEM = (
    "Sei il copywriter di un'agenzia web di Catania. Scrivi copioni telefonici "
    "in italiano parlato, caldi ma professionali, per chi NON è un venditore "
    "esperto. Frasi corte, pause segnate con [PAUSA], domande aperte. "
    "Non inventare MAI dati sul cliente: usa solo quelli forniti. "
    "Rispondi SOLO con JSON: {\"apertura\": \"...\", \"discovery\": [\"...\"], "
    "\"pitch\": \"...\", \"chiusura\": \"...\"}"
)

CAMPI = ["apertura", "discovery", "pitch", "chiusura"]


def _prompt(c: Contatto, dossier: dict) -> str:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    return template.format(
        nome=c.nome, categoria=c.categoria, citta=c.citta,
        bucket=c.bucket, sito=c.sito, problemi_sito=c.problemi_sito or "n/d",
        segnale_intent=c.segnale_intent or "NESSUNO",
        ticket_fit=c.ticket_fit or "n/d",
        rating=c.rating_google or "n/d", recensioni=c.num_recensioni,
        hook=c.hook,
        argomenti="\n".join(f"- {a}" for a in dossier.get("argomenti_chiave", [])),
        dolori="\n".join(f"- {d}" for d in dossier.get("dolori_nicchia", [])),
        leve=dossier.get("leve_da_privilegiare", ""),
    )


def scrivi_copione(c: Contatto, dossier: dict, llm) -> dict | None:
    """Ritorna il copione grezzo (dict) o None se il parse fallisce."""
    return llm.genera_json(_prompt(c, dossier), SYSTEM, CAMPI)
