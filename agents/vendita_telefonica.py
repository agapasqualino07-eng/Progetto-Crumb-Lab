"""[6d] VENDITA TELEFONICA (team copy) — rifinitura per il parlato reale.

Prende copione + obiezioni e li rifinisce per chi chiama davvero (un
marketer, non un venditore navigato): ritmo, pause, cosa fare col
gatekeeper, cosa dire in segreteria, follow-up WhatsApp, e la regola
d'oro della chiusura su micro-impegno (appuntamento di 15 minuti, non
la vendita). Output: il copione FINALE formattato pronto da stampare.
"""

import logging

from core.models import Contatto

log = logging.getLogger("faro.copy.telefono")

SYSTEM = (
    "Sei un formatore di vendita telefonica B2B per micro-imprese italiane. "
    "Chi chiamerà NON è un venditore esperto: il copione deve reggere anche "
    "letto quasi alla lettera, con [PAUSA] segnate e istruzioni brevi in "
    "MAIUSCOLO tra parentesi quadre. Obiettivo della chiamata: NON vendere, "
    "ma ottenere un appuntamento di 15 minuti (di persona o video). "
    "Tono: 'lei', cordiale, siciliano-professionale, zero gergo tecnico. "
    "Rispondi SOLO con JSON: {\"copione\": \"...\", \"gatekeeper\": \"...\", "
    "\"segreteria\": \"...\", \"followup_whatsapp\": \"...\"}"
)

PROMPT = """Rifinisci questo materiale in un copione telefonico FINALE per il lead
{nome} ({categoria}, {citta}).

APERTURA (dal copywriter): {apertura}
DOMANDE DISCOVERY: {discovery}
PITCH: {pitch}
CHIUSURA: {chiusura}

Regole di rifinitura:
1. Struttura finale: PREPARAZIONE (1 riga: cosa avere sotto mano) → APERTURA
   (max 20 secondi parlati, chiedi permesso di proseguire) → [PAUSA-ASCOLTA] →
   2-3 DOMANDE DISCOVERY → PITCH (max 30 secondi, UN dato concreto del lead)
   → CHIUSURA su appuntamento con alternativa di orario ("meglio domani
   mattina o giovedì pomeriggio?").
2. Aggiungi `gatekeeper`: 2 frasi per farsi passare il titolare senza
   trucchi ("sono [NOME] di [NOME AGENZIA] di Catania, chiamo per la
   presenza online dell'attività — è una cosa veloce").
3. Aggiungi `segreteria`: messaggio di 15 secondi da lasciare se non risponde.
4. Aggiungi `followup_whatsapp`: messaggio breve da mandare DOPO la chiamata
   (solo se hanno mostrato interesse o chiesto materiale — mai a freddo,
   vincolo legale del progetto).
Il copione resta fedele ai dati reali del lead, nessun dato nuovo."""

CAMPI = ["copione", "gatekeeper", "segreteria", "followup_whatsapp"]


def rifinisci(c: Contatto, bozza_copione: dict, llm) -> dict | None:
    """Ritorna il copione finale rifinito (dict) o None se il parse fallisce."""
    return llm.genera_json(
        PROMPT.format(
            nome=c.nome, categoria=c.categoria, citta=c.citta,
            apertura=bozza_copione.get("apertura", ""),
            discovery=" | ".join(bozza_copione.get("discovery", [])),
            pitch=bozza_copione.get("pitch", ""),
            chiusura=bozza_copione.get("chiusura", ""),
        ),
        SYSTEM, CAMPI)
