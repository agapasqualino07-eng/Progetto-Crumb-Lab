"""[6c] PERSUASIONE (team copy) — obiezioni → risposte, eticamente.

Per ogni lead genera la mappa delle obiezioni più probabili con la risposta
pronta, applicando i principi di persuasione etica (riprova sociale locale,
ancoraggio ai costi dei portali, avversione alla perdita) SENZA pressioni
né false scarsità: il contatto deve poter dire no facilmente (coerenza col
GDPR/opt-out del progetto, sez. 7).

Le obiezioni universali con le risposte "collaudate" vivono in
`docs/COPIONE_MASTER.md`; qui si genera la personalizzazione per lead.
"""

import logging

from core.models import Contatto

log = logging.getLogger("faro.copy.persuasione")

SYSTEM = (
    "Sei l'esperto di persuasione etica di un'agenzia web di Catania. "
    "Per ogni obiezione scrivi una risposta in 3 mosse: (1) riconosci senza "
    "controbattere, (2) riformula/esplora, (3) rispondi con UN dato concreto "
    "del lead o del caso studio e richiudi con una domanda. "
    "Vietato: false scarsità, pressioni, dati inventati sul cliente. "
    "Ammesso: riprova sociale (caso studio Catania +10 chiamate/settimana), "
    "ancoraggio (commissioni portali vs costo sito), avversione alla perdita "
    "(clienti che oggi non lo trovano), reciprocità (bozza gratuita). "
    "Rispondi SOLO con JSON: {\"obiezioni\": [{\"obiezione\": \"...\", "
    "\"risposta\": \"...\", \"leva\": \"...\"}]}"
)

PROMPT = """Lead: {nome} ({categoria}, {citta}) — bucket {bucket}, ticket_fit {ticket_fit}.
Dati reali disponibili: sito={sito}; problemi_sito={problemi}; segnale_intent={intent};
rating={rating} con {recensioni} recensioni.

Obiezioni probabili per questa nicchia (dal dossier): {obiezioni_dossier}

Genera la mappa obiezioni→risposte per QUESTA chiamata: le obiezioni del
dossier più le universali ("non ho tempo", "non mi interessa", "mandami una
mail", "quanto costa?", "ci devo pensare / ne parlo col socio", "ho già
Facebook/i portali", "brutta esperienza passata", "richiamami più avanti").
Ogni risposta: max 3 frasi, parlata, col metodo in system prompt. Campo
`leva`: quale principio usa (riprova-sociale / ancoraggio / perdita /
reciprocità / coerenza / nessuna)."""

CAMPI = ["obiezioni"]


def mappa_obiezioni(c: Contatto, dossier: dict, llm) -> list | None:
    """Ritorna la lista di dict {obiezione, risposta, leva} o None."""
    dati = llm.genera_json(
        PROMPT.format(
            nome=c.nome, categoria=c.categoria, citta=c.citta, bucket=c.bucket,
            ticket_fit=c.ticket_fit or "n/d", sito=c.sito,
            problemi=c.problemi_sito or "n/d", intent=c.segnale_intent or "nessuno",
            rating=c.rating_google or "n/d", recensioni=c.num_recensioni,
            obiezioni_dossier=", ".join(dossier.get("obiezioni_probabili", [])),
        ),
        SYSTEM, CAMPI)
    if dati is None:
        return None
    obiezioni = dati.get("obiezioni")
    return obiezioni if isinstance(obiezioni, list) else None
