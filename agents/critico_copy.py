"""[6f] CRITICO COPY — verifica e fa migliorare ogni copione.

Dopo il revisore, il critico valuta il copione con una rubrica fissa e
un voto 0-100. Se il voto è sotto la soglia in config, chiede UNA
riscrittura mirata (max_iterazioni, default 1: i costi restano sotto
controllo) e rivaluta. Il voto e i punti deboli finiscono nel report.

Rubrica (20 punti l'una):
1. SPECIFICITÀ — cita dati concreti e VERI di questo lead, non frasi buone per tutti.
2. APERTURA — aggancia in 20 secondi e chiede il permesso di proseguire.
3. PARLATO — frasi corte, zero gergo tecnico, pause segnate, si può leggere a voce.
4. CTA — chiude su UN micro-impegno chiaro con alternativa di orario.
5. OBIEZIONI — le risposte riconoscono prima di rispondere e finiscono con una domanda.
"""

import logging

from core.models import Contatto

log = logging.getLogger("faro.copy.critico")

SYSTEM_VALUTA = (
    "Sei il direttore creativo severo di un'agenzia. Valuti un copione "
    "telefonico con una rubrica in 5 criteri da 20 punti: specificità sul "
    "lead, apertura 20s con permesso, lingua parlata senza gergo, CTA su "
    "micro-impegno con alternativa, obiezioni che riconoscono→esplorano→"
    "rispondono. Sii onesto: 60 = mediocre, 80 = buono, 95+ = raro. "
    "Rispondi SOLO con JSON: {\"voto\": <0-100>, \"punti_deboli\": [\"...\"], "
    "\"suggerimenti\": [\"...\"]}"
)

PROMPT_VALUTA = """Lead: {nome} ({categoria}, {citta}).
Dati REALI del lead (tutto il resto sarebbe inventato): sito={sito};
problemi={problemi}; intent={intent}; rating={rating} ({recensioni} recensioni);
ticket_fit={ticket_fit}.

=== COPIONE DA VALUTARE ===
{copione}

=== OBIEZIONI→RISPOSTE DA VALUTARE ===
{obiezioni}

Valuta con la rubrica. Se il copione cita dati NON presenti tra quelli
reali sopra, è un errore grave: sottrai 20 punti e segnalalo."""

SYSTEM_MIGLIORA = (
    "Sei un copywriter senior. Riscrivi il copione applicando ESATTAMENTE "
    "i suggerimenti del direttore creativo, senza aggiungere dati nuovi sul "
    "cliente. Mantieni struttura e [PAUSA]. Rispondi SOLO con JSON: "
    "{\"copione\": \"...\", \"obiezioni_risposte\": \"...\"}"
)

PROMPT_MIGLIORA = """Riscrivi migliorando. Suggerimenti del direttore (applicali tutti):
{suggerimenti}

Dati REALI citabili: sito={sito}; problemi={problemi}; intent={intent};
rating={rating} ({recensioni} recensioni).

=== COPIONE ATTUALE ===
{copione}

=== OBIEZIONI ATTUALI ===
{obiezioni}"""


def valuta(c: Contatto, copione: str, obiezioni: str, llm) -> dict | None:
    """Ritorna {voto, punti_deboli, suggerimenti} o None se parse fallito."""
    dati = llm.genera_json(
        PROMPT_VALUTA.format(
            nome=c.nome, categoria=c.categoria, citta=c.citta, sito=c.sito,
            problemi=c.problemi_sito or "n/d", intent=c.segnale_intent or "nessuno",
            rating=c.rating_google or "n/d", recensioni=c.num_recensioni,
            ticket_fit=c.ticket_fit or "n/d",
            copione=copione, obiezioni=obiezioni),
        SYSTEM_VALUTA, ["voto", "punti_deboli", "suggerimenti"])
    if dati is None:
        return None
    try:
        dati["voto"] = int(float(dati["voto"]))
    except (TypeError, ValueError):
        return None
    return dati


def migliora(c: Contatto, copione: str, obiezioni: str,
             suggerimenti: list, llm) -> dict | None:
    """Una riscrittura mirata. Ritorna {copione, obiezioni_risposte} o None."""
    return llm.genera_json(
        PROMPT_MIGLIORA.format(
            suggerimenti="\n".join(f"- {s}" for s in suggerimenti),
            sito=c.sito, problemi=c.problemi_sito or "n/d",
            intent=c.segnale_intent or "nessuno",
            rating=c.rating_google or "n/d", recensioni=c.num_recensioni,
            copione=copione, obiezioni=obiezioni),
        SYSTEM_MIGLIORA, ["copione", "obiezioni_risposte"])


def controlla_e_migliora(c: Contatto, llm, cfg: dict, report=None) -> int | None:
    """Loop critico: valuta → (se sotto soglia) migliora UNA volta → rivaluta.

    Opera in-place su c.copione / c.obiezioni_risposte. Ritorna il voto finale.
    """
    soglia = cfg["copy"]["soglia_critico"]
    max_iter = cfg["copy"]["max_iterazioni"]
    esito = valuta(c, c.copione, c.obiezioni_risposte, llm)
    if esito is None:
        if report is not None:
            report.errori.append(f"critico: parse fallito per {c.nome} (copy non valutato)")
        return None

    iterazioni = 0
    while esito["voto"] < soglia and iterazioni < max_iter:
        deboli = [str(p) for p in (esito.get("punti_deboli") or [])][:3]
        log.info("Critico: %s voto %d < %d, riscrittura (%s)",
                 c.nome, esito["voto"], soglia, "; ".join(deboli) or "n/d")
        nuovo = migliora(c, c.copione, c.obiezioni_risposte,
                         esito.get("suggerimenti") or [], llm)
        iterazioni += 1
        if nuovo is None:
            break   # meglio il copione attuale che niente
        c.copione = str(nuovo.get("copione", c.copione))
        c.obiezioni_risposte = str(nuovo.get("obiezioni_risposte", c.obiezioni_risposte))
        rivalutato = valuta(c, c.copione, c.obiezioni_risposte, llm)
        if rivalutato is not None:
            esito = rivalutato

    log.info("Critico: %s voto finale %d (%d riscritture)", c.nome, esito["voto"], iterazioni)
    return esito["voto"]
