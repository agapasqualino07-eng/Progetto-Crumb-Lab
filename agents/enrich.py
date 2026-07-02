"""[4] ENRICH (criticità #2, #8, #16, #17).

- Email SOLO generica (info@, amministrazione@...) — MAI nominativa (sez. 7).
- Nome titolare: RIMOSSO dall'MVP (#17) — si chiede in chiamata.
- SEGNALE DI INTENT (#2): solo segnali realmente osservati nei dati;
  se non c'è nulla il campo resta VUOTO (mai inventare dati).
- PROXY TICKET-FIT (#16): capacità di spesa stimata da proxy pubblici
  (per l'MVP: num_recensioni con soglie per-nicchia).
- Validazione telefono (#8) con `phonenumbers`.
- Ditta individuale (#17.7): NESSUN arricchimento extra (path stricter).
"""

import logging
import re

import requests

from core.models import Contatto

log = logging.getLogger("faro.enrich")

PREFISSI_GENERICI = (
    "info", "amministrazione", "contatti", "contact", "segreteria",
    "ufficio", "vendite", "commerciale", "mail", "posta", "hello", "ciao",
)


def email_generica_da_sito(url: str, dry_run: bool) -> str:
    """Cerca un'email GENERICA nella home/pagina contatti. Nominative scartate."""
    if dry_run or not url or url == "ASSENTE":
        return ""
    if not url.startswith("http"):
        url = "https://" + url
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0 (faro-enrich)"})
        html = r.text
        # prova anche una pagina contatti canonica
        m_link = re.search(r'href=["\']([^"\']*contatt[^"\']*)["\']', html, re.I)
        if m_link:
            link = m_link.group(1)
            if link.startswith("/"):
                link = url.rstrip("/") + link
            if link.startswith("http"):
                try:
                    html += requests.get(link, timeout=15).text
                except requests.RequestException:
                    pass
        for email in set(re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", html)):
            prefisso = email.split("@")[0].lower()
            if any(prefisso.startswith(p) for p in PREFISSI_GENERICI):
                return email.lower()
        return ""   # solo nominative trovate → NON si usano (vincolo legale)
    except requests.RequestException:
        return ""


def valida_telefono(numero: str) -> tuple[str, bool]:
    """Normalizza in E.164 italiano. Ritorna (numero_normalizzato, valido)."""
    if not numero:
        return "", False
    try:
        import phonenumbers
        parsed = phonenumbers.parse(numero, "IT")
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(
                parsed, phonenumbers.PhoneNumberFormat.E164), True
        return numero, False
    except Exception:
        return numero, False


def segnale_intent(c: Contatto) -> str:
    """Segnali di "perché adesso" osservabili dai dati che ABBIAMO (#2).

    MVP onesto: dai dati Maps si osservano davvero solo questi. Le fonti
    esterne (annunci Subito, assunzioni, aperture) sono predisposte come
    estensione: aggiungere qui un detector = un nuovo segnale in pipeline.
    Nessun segnale → stringa vuota, MAI un segnale inventato.
    """
    segnali = []
    if not c.claimed:
        segnali.append("scheda Google non rivendicata (titolare poco presente online)")
    if c.ha_sito and c.problemi_sito and "irraggiungibile" in c.problemi_sito:
        segnali.append("sito esistente ma irraggiungibile (dominio pagato, servizio rotto)")
    return segnali[0] if segnali else ""


def ticket_fit(c: Contatto, nicchia_cfg: dict) -> str:
    """Proxy capacità di spesa (#16). MVP: soglie su num_recensioni."""
    soglie = nicchia_cfg.get("ticket_fit_recensioni", {"basso": 15, "alto": 60})
    if c.num_recensioni >= soglie["alto"]:
        return "alto"
    if c.num_recensioni < soglie["basso"]:
        return "basso"
    return "medio"


def arricchisci(contatti: list[Contatto], nicchia_cfg: dict,
                dry_run: bool, report=None) -> list[Contatto]:
    """Arricchisce in-place. Contatto non chiamabile → scartato con motivo."""
    tenuti = []
    for c in contatti:
        c.telefono, c.telefono_valido = valida_telefono(c.telefono)
        # Ditta individuale: path stricter (#17.7) → nessun arricchimento extra
        if not c.ditta_individuale:
            if not c.email_aziendale:
                c.email_aziendale = email_generica_da_sito(c.sito if c.ha_sito else "", dry_run)
            c.segnale_intent = segnale_intent(c)
        c.ticket_fit = ticket_fit(c, nicchia_cfg)
        if not c.telefono_valido and not c.email_aziendale:
            # non chiamabile e non scrivibile: inutile spenderci LLM
            if report is not None:
                report.aggiungi_filtro("non_contattabile")
            continue
        tenuti.append(c)
    log.info("ENRICH: %d contattabili su %d", len(tenuti), len(contatti))
    return tenuti
