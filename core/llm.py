"""Wrapper LLM con parsing JSON robusto (criticità #5).

L'LLM non è deterministico: estraiamo il blocco JSON dalla risposta,
proviamo il parse, al fallimento facciamo UN retry con prompt più
stringente, e se fallisce ancora logghiamo e ritorniamo None — il
chiamante salta quel contatto senza far crashare il run.
"""

import json
import logging
import os
import re

log = logging.getLogger("faro.llm")


def estrai_json(testo: str) -> dict | None:
    """Estrae il primo oggetto JSON valido da un testo libero."""
    if not testo:
        return None
    # 1) blocco ```json ... ```
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", testo, re.DOTALL)
    candidati = [m.group(1)] if m else []
    # 2) la più grande sottostringa che parte da { e finisce a }
    primo, ultimo = testo.find("{"), testo.rfind("}")
    if primo != -1 and ultimo > primo:
        candidati.append(testo[primo : ultimo + 1])
    for c in candidati:
        try:
            dati = json.loads(c)
            if isinstance(dati, dict):
                return dati
        except json.JSONDecodeError:
            continue
    return None


class LLM:
    """Client Anthropic reale. Modello configurabile via config/env."""

    def __init__(self, model: str, max_tokens: int = 1024):
        import anthropic  # import pigro: non serve in dry-run

        self.client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self.model = model
        self.max_tokens = max_tokens
        self.chiamate = 0

    def _chiama(self, prompt: str, system: str) -> str:
        self.chiamate += 1
        risposta = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return risposta.content[0].text

    def genera_json(self, prompt: str, system: str, campi_attesi: list[str]) -> dict | None:
        """Chiama l'LLM e pretende un JSON con i campi attesi. 1 retry, poi None."""
        testo = self._chiama(prompt, system)
        dati = estrai_json(testo)
        if dati and all(c in dati for c in campi_attesi):
            return dati
        log.warning("Parse JSON fallito, retry con prompt stringente")
        retry = (
            prompt
            + "\n\nATTENZIONE: rispondi ESCLUSIVAMENTE con un oggetto JSON valido, "
            + "senza testo prima o dopo, con esattamente questi campi: "
            + ", ".join(campi_attesi)
        )
        testo = self._chiama(retry, system)
        dati = estrai_json(testo)
        if dati and all(c in dati for c in campi_attesi):
            return dati
        log.error("Parse JSON fallito anche al retry: contatto saltato")
        return None


class LLMFinto:
    """LLM deterministico per --dry-run e test: zero API, zero spesa (#9).

    Produce output plausibili ma chiaramente derivati dai dati di input,
    così l'intera catena scoring→hook→delivery è verificabile offline.
    """

    def __init__(self, *_args, **_kwargs):
        self.chiamate = 0

    def genera_json(self, prompt: str, system: str, campi_attesi: list[str]) -> dict | None:
        self.chiamate += 1
        if "score_priorita" in campi_attesi:
            base = 50
            if "segnale_intent: " in prompt and "segnale_intent: \n" not in prompt:
                base += 20
            if "ticket_fit: alto" in prompt:
                base += 20
            elif in_prompt_basso(prompt):
                base -= 20
            if "bucket: no_site" in prompt:
                base += 10
            return {
                "score_priorita": max(0, min(100, base)),
                "motivazione": "[DRY-RUN] score simulato dai campi intent/ticket_fit/bucket",
            }
        if "hook" in campi_attesi:
            variante = "intent" if ("segnale_intent: " in prompt and "segnale_intent: \n" not in prompt) else "problema-sito"
            return {
                "hook": "[DRY-RUN] hook simulato basato su " + variante,
                "hook_variante": variante,
                "bozza_messaggio": "[DRY-RUN] bozza messaggio simulata",
            }
        return {c: "[DRY-RUN]" for c in campi_attesi}


def in_prompt_basso(prompt: str) -> bool:
    return "ticket_fit: basso" in prompt


def crea_llm(cfg: dict, dry_run: bool):
    if dry_run:
        return LLMFinto()
    return LLM(cfg["llm"]["model"], cfg["llm"]["max_tokens"])
