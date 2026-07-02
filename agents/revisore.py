"""[6e] REVISORE BOZZE (team copy) — controllo qualità finale.

Due livelli di controllo:
1. **Controllo deterministico anti-invenzione** (senza LLM): il copione non
   deve contenere numeri di telefono, URL o cifre "di fatto" che non stanno
   nei dati reali del lead — se li trova, li segnala (regola: mai inventare
   dati). Questo controllo gira SEMPRE, anche se l'LLM revisore fallisce.
2. **Revisione LLM**: italiano naturale, refusi, lunghezze, coerenza di tono.
"""

import logging
import re

from core.models import Contatto

log = logging.getLogger("faro.copy.revisore")

SYSTEM = (
    "Sei il correttore di bozze di un'agenzia web di Catania. Ricevi un "
    "copione telefonico e una mappa obiezioni→risposte. Correggi refusi, "
    "italiano innaturale, frasi troppo lunghe per il parlato; NON aggiungere "
    "contenuti nuovi né dati. Mantieni [PAUSA] e le istruzioni tra parentesi "
    "quadre. Rispondi SOLO con JSON: {\"copione\": \"...\", "
    "\"obiezioni_risposte\": \"...\", \"segnalazioni\": [\"...\"]}"
)

PROMPT = """Rivedi questo materiale per il lead {nome}.

=== COPIONE ===
{copione}

=== OBIEZIONI → RISPOSTE ===
{obiezioni}

Correggi e restituisci entrambi (campo `obiezioni_risposte` come testo
formattato "OBIEZIONE: ... → RISPOSTA: ..." una per riga). In `segnalazioni`
elenca ciò che hai corretto o che resta debole (lista vuota se tutto ok)."""

CAMPI = ["copione", "obiezioni_risposte", "segnalazioni"]

# telefoni italiani scritti anche a gruppi ("095 999 8888", "+39 347 12 34 567")
_RE_TELEFONO = re.compile(r"(?:\+39[\s.\-]?)?(?:0\d{1,3}|3\d{2})(?:[\s.\-]?\d{2,4}){2,3}")
_RE_URL = re.compile(r"https?://[^\s\"']+|www\.[^\s\"']+")


def controlla_coerenza(c: Contatto, testo: str) -> list[str]:
    """Controllo anti-invenzione: telefoni/URL nel testo devono esistere nei dati."""
    avvisi = []
    dati_noti = " ".join([c.telefono, c.sito, c.email_aziendale])
    for tel in _RE_TELEFONO.findall(testo):
        pulito = re.sub(r"[\s.\-]", "", tel)
        if pulito and pulito not in re.sub(r"[\s.\-]", "", dati_noti):
            avvisi.append(f"telefono non presente nei dati del lead: {tel}")
    for url in _RE_URL.findall(testo):
        dominio = url.split("//")[-1].split("/")[0].lstrip("w.")
        if dominio and dominio not in dati_noti:
            avvisi.append(f"URL non presente nei dati del lead: {url}")
    return avvisi


def _formatta_obiezioni(obiezioni: list) -> str:
    righe = []
    for o in obiezioni:
        if isinstance(o, dict):
            righe.append(f"OBIEZIONE: {o.get('obiezione', '')} → RISPOSTA: "
                         f"{o.get('risposta', '')} [leva: {o.get('leva', 'n/d')}]")
    return "\n".join(righe)


def rivedi(c: Contatto, copione_finale: dict, obiezioni: list, llm) -> dict:
    """Revisione finale. Ritorna sempre un dict {copione, obiezioni_risposte, avvisi}.

    Se l'LLM fallisce, passa il materiale non revisionato (meglio un copione
    non rifinito che un lead perso), ma il controllo anti-invenzione gira
    comunque e i suoi avvisi finiscono nel campo `avvisi`.
    """
    testo_copione = copione_finale.get("copione", "")
    extra = "\n".join(filter(None, [
        f"[SE RISPONDE UN COLLABORATORE] {copione_finale.get('gatekeeper', '')}",
        f"[SE SEGRETERIA] {copione_finale.get('segreteria', '')}",
        f"[FOLLOW-UP WHATSAPP, solo se interessato] {copione_finale.get('followup_whatsapp', '')}",
    ]))
    testo_obiezioni = _formatta_obiezioni(obiezioni or [])

    dati = llm.genera_json(
        PROMPT.format(nome=c.nome, copione=testo_copione + "\n" + extra,
                      obiezioni=testo_obiezioni),
        SYSTEM, CAMPI)
    if dati is None:
        log.warning("Revisore LLM fallito per %s: passo il materiale non revisionato", c.nome)
        dati = {"copione": testo_copione + "\n" + extra,
                "obiezioni_risposte": testo_obiezioni, "segnalazioni": ["revisione LLM saltata"]}

    seg = dati.get("segnalazioni")
    avvisi = list(seg) if isinstance(seg, list) else ([str(seg)] if seg else [])
    avvisi += controlla_coerenza(c, str(dati.get("copione", "")) + " "
                                 + str(dati.get("obiezioni_risposte", "")))
    if avvisi:
        log.info("Revisore, avvisi per %s: %s", c.nome, "; ".join(map(str, avvisi)))
    return {"copione": str(dati.get("copione", "")),
            "obiezioni_risposte": str(dati.get("obiezioni_risposte", "")),
            "avvisi": avvisi}
