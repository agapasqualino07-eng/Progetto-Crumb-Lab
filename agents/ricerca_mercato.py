"""[6a] RICERCA MERCATO (team copy) — dossier di vendita per nicchia.

UNA chiamata LLM per nicchia per run (non per lead): produce il "dossier"
che alimenta copywriter, persuasione e vendita telefonica. Integra il
feedback storico delle chiamate (#6) così gli argomenti si affinano
sugli esiti reali, non sulle ipotesi.

Il sapere statico di base (dati di mercato, obiezioni universali) vive in
`docs/COPIONE_MASTER.md` e `templates/`: qui si genera solo la parte che
cambia (zona, feedback, stagione).
"""

import logging

log = logging.getLogger("faro.copy.mercato")

SYSTEM = (
    "Sei il ricercatore di mercato di un'agenzia web di Catania (siti web "
    "€1.500-5.000 per aziende locali). Produci dossier di vendita sintetici "
    "e concreti, basati SOLO sui dati forniti: non inventare statistiche. "
    "Rispondi SOLO con JSON: {\"argomenti_chiave\": [\"...\"], "
    "\"dolori_nicchia\": [\"...\"], \"obiezioni_probabili\": [\"...\"], "
    "\"leve_da_privilegiare\": \"...\"}"
)

PROMPT = """Prepara il dossier di vendita di oggi per la nicchia: {nicchia}.

Contesto fisso (verificato, usalo come base):
- Case study reale: concessionaria a Catania, +10 chiamate e +5 visite/settimana dopo il sito nuovo.
- I rivenditori pagano abbonamenti/commissioni ai portali annunci; un sito proprio porta lead diretti senza commissione.
- La maggioranza degli acquirenti auto inizia la ricerca online.
- Argomenti: SEO locale ("auto usate + città"), fiducia/credibilità (recensioni in vetrina), contatto WhatsApp diretto.

Zona di lavoro corrente: {citta}.

{feedback}

Produci: 4-6 argomenti_chiave (frasi pronte da usare al telefono),
3-5 dolori_nicchia, le 5 obiezioni_probabili più attese per questa nicchia
in questa zona, e leve_da_privilegiare (1 frase: su cosa spingere oggi
in base al feedback, o la leva di default se non c'è feedback)."""

CAMPI = ["argomenti_chiave", "dolori_nicchia", "obiezioni_probabili", "leve_da_privilegiare"]


def dossier_nicchia(nicchia: str, citta: str, feedback: str, llm) -> dict:
    """Genera il dossier. Se il parse fallisce, torna un dossier minimo di default."""
    testo_feedback = feedback or "Nessun feedback storico disponibile (primi run)."
    dati = llm.genera_json(
        PROMPT.format(nicchia=nicchia, citta=citta, feedback=testo_feedback),
        SYSTEM, CAMPI)
    if dati is None:
        log.warning("Dossier mercato: parse fallito, uso dossier di default")
        return {
            "argomenti_chiave": [
                "Case study: concessionaria di Catania, +10 chiamate/settimana col sito nuovo",
                "Lead diretti senza commissioni da portale",
            ],
            "dolori_nicchia": ["dipendenza dai portali a pagamento"],
            "obiezioni_probabili": ["non ho tempo", "vendo già con i portali",
                                    "quanto costa?", "ci devo pensare"],
            "leve_da_privilegiare": "caso studio locale + costo dell'inazione",
        }
    return dati
