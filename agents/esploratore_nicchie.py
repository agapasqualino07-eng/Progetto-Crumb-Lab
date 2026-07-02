"""[1a] ESPLORATORE NICCHIE — "non lasciare scampo a nessuna nicchia".

Prima dello SCOUT, con UNA chiamata LLM per run:
1. ORDINA le nicchie attive per priorità di oggi (pool residuo, feedback
   esiti chiamate, leva commerciale) → lo scout lavora prima le migliori.
2. PROPONE eventuali nicchie NUOVE non ancora in catalogo (con categoria
   Google, leva e proxy ticket-fit). Le proposte NON si attivano da sole:
   finiscono nel report/email/Telegram e si accendono a mano in config
   (il codice non deve auto-espandere lo scope di raccolta dati — GDPR).

Fallback deterministico se l'LLM non risponde: ordine = pool più scarso
per primo (serve rifornire), nessuna proposta.
"""

import logging

log = logging.getLogger("faro.esploratore")

SYSTEM = (
    "Sei lo stratega di targeting di un'agenzia web di Catania (siti "
    "€1.500-5.000 per attività locali). Decidi su quali nicchie puntare "
    "oggi e proponi nicchie nuove dove un sito è FONDAMENTALE per il "
    "business e il ticket è sostenibile. Rispondi SOLO con JSON: "
    "{\"ordine_nicchie\": [\"...\"], \"motivo\": \"...\", "
    "\"nicchie_proposte\": [{\"nome\": \"...\", \"categorie_google\": [\"...\"], "
    "\"leva\": \"...\", \"ticket_fit_proxy\": \"...\"}]}"
)

PROMPT = """Nicchie ATTIVE oggi (da ordinare per priorità):
{nicchie_attive}

Pool di lead `nuovo` residui per nicchia: {pool}
Zona di lavoro: {citta}
{feedback}

1. Ordina le nicchie attive: privilegia quelle con pool scarso (vanno
   rifornite) e quelle che dagli esiti convertono meglio.
2. Proponi 0-3 nicchie NUOVE non in questo elenco (attive o note:
   {tutte_le_nicchie}) presenti in una città come {citta}, dove il sito
   è fondamentale e un'attività può permettersi €1.500-5.000.
   Se non hai proposte solide, lista vuota: niente riempitivi."""

CAMPI = ["ordine_nicchie", "motivo", "nicchie_proposte"]


def esplora(nicchie_attive: dict, tutte: list[str], pool_per_nicchia: dict,
            citta: str, feedback: str, llm) -> tuple[list[str], list[dict], str]:
    """Ritorna (ordine_nicchie_attive, proposte_nuove, motivo)."""
    nomi_attive = list(nicchie_attive.keys())
    descr = "\n".join(
        f"- {nome}: leva='{cfg.get('leva_chiave', 'n/d')}', pool={pool_per_nicchia.get(nome, 0)}"
        for nome, cfg in nicchie_attive.items())
    dati = llm.genera_json(
        PROMPT.format(nicchie_attive=descr, pool=pool_per_nicchia or "{}",
                      citta=citta,
                      feedback=feedback or "Nessun feedback storico (primi run).",
                      tutte_le_nicchie=", ".join(tutte)),
        SYSTEM, CAMPI)

    if dati is None or not isinstance(dati.get("ordine_nicchie"), list):
        # fallback deterministico: pool più scarso per primo
        ordine = sorted(nomi_attive, key=lambda n: pool_per_nicchia.get(n, 0))
        log.warning("Esploratore: LLM non disponibile, ordine per pool scarso: %s", ordine)
        return ordine, [], "fallback: ordinate per pool residuo crescente"

    # tieni solo nicchie realmente attive, nell'ordine proposto, senza perderne
    ordine = [n for n in dati["ordine_nicchie"] if n in nomi_attive]
    ordine += [n for n in nomi_attive if n not in ordine]
    proposte = dati.get("nicchie_proposte")
    proposte = proposte if isinstance(proposte, list) else []
    log.info("Esploratore: ordine %s; %d nicchie proposte", ordine, len(proposte))
    return ordine, proposte, str(dati.get("motivo", ""))
