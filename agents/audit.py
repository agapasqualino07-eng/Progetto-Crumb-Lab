"""[3] AUDIT del sito (criticità #7, #18c) — solo bucket sito_pessimo.

Segnali gratuiti e affidabili: HTTP status/redirect/tempo, SSL, viewport,
anno copyright nel footer. PageSpeed Insights per la performance mobile,
MA se va in timeout/errore NON si scarta il lead: si ripiega sui segnali
gratuiti e si marca `audit_parziale = true` (#18c).

Cache: un dominio auditato negli ultimi N giorni non si ri-audita (#7).
Throttling tra chiamate per rispettare le quote.
"""

import logging
import re
import time
from datetime import datetime, timedelta

import requests

from core.models import Contatto, STAGE_AUDITED
from core.config import env

log = logging.getLogger("faro.audit")

PAGESPEED_URL = "https://pagespeedonline.googleapis.com/pagespeedonline/v5/runPagespeed"


def _check_http(url: str) -> dict:
    """HTTP GET: status, redirect, tempo, SSL, viewport, anno footer."""
    esito = {"raggiungibile": False, "https_ok": False, "status": None,
             "tempo_s": None, "viewport": False, "anno_footer": None, "html": ""}
    if not url.startswith("http"):
        url = "https://" + url
    try:
        inizio = time.time()
        r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0 (faro-audit)"})
        esito.update(raggiungibile=True, status=r.status_code,
                     tempo_s=round(time.time() - inizio, 2),
                     https_ok=r.url.startswith("https://"))
        esito["html"] = r.text[:200_000]
    except requests.exceptions.SSLError:
        esito["https_ok"] = False
        # riprova in http per capire se il sito esiste comunque
        try:
            r = requests.get(url.replace("https://", "http://"), timeout=15,
                             headers={"User-Agent": "Mozilla/5.0 (faro-audit)"})
            esito.update(raggiungibile=True, status=r.status_code)
            esito["html"] = r.text[:200_000]
        except requests.RequestException:
            pass
    except requests.RequestException:
        pass

    if esito["html"]:
        esito["viewport"] = bool(re.search(r'<meta[^>]+name=["\']viewport', esito["html"], re.I))
        anni = re.findall(r"(?:©|&copy;|copyright)\D{0,20}(20\d{2})", esito["html"], re.I)
        if anni:
            esito["anno_footer"] = max(int(a) for a in anni)
    esito.pop("html")
    return esito


def _pagespeed_mobile(url: str, timeout_s: int) -> int | None:
    """Score performance mobile 0-100, oppure None se PageSpeed fallisce."""
    try:
        r = requests.get(PAGESPEED_URL, params={
            "url": url, "strategy": "mobile", "category": "performance",
            **({"key": env("PAGESPEED_API_KEY")} if env("PAGESPEED_API_KEY") else {}),
        }, timeout=timeout_s)
        r.raise_for_status()
        score = r.json()["lighthouseResult"]["categories"]["performance"]["score"]
        return round(float(score) * 100)
    except (requests.RequestException, KeyError, TypeError, ValueError) as e:
        log.warning("PageSpeed fallita per %s: %s — fallback su segnali gratuiti", url, e)
        return None


def _score_da_segnali(http: dict, pagespeed: int | None, anno_datato: int) -> tuple[int, list[str]]:
    """Combina i segnali in uno score 0-100 (alto = sito buono) + problemi."""
    problemi = []
    if not http["raggiungibile"]:
        return 0, ["sito irraggiungibile"]

    if pagespeed is not None:
        score = pagespeed
        if pagespeed < 50:
            problemi.append(f"performance mobile scarsa ({pagespeed}/100)")
    else:
        score = 70  # base neutra: senza PageSpeed giudicano i segnali gratuiti

    if http["status"] and http["status"] >= 400:
        score -= 40
        problemi.append(f"HTTP {http['status']}")
    if not http["https_ok"]:
        score -= 25
        problemi.append("SSL assente o non valido")
    if not http["viewport"]:
        score -= 20
        problemi.append("non responsive (manca viewport)")
    if http["anno_footer"] and http["anno_footer"] <= anno_datato:
        score -= 15
        problemi.append(f"footer datato ({http['anno_footer']})")
    if http["tempo_s"] and http["tempo_s"] > 5:
        score -= 10
        problemi.append(f"caricamento lento ({http['tempo_s']}s)")
    return max(0, min(100, score)), problemi


def _cache_valida(c: Contatto, giorni: int, oggi: datetime) -> bool:
    if not c.data_audit or c.score_sito == "":
        return False
    try:
        return oggi - datetime.fromisoformat(c.data_audit) < timedelta(days=giorni)
    except ValueError:
        return False


def audita(contatti: list[Contatto], cfg: dict, dry_run: bool,
           report=None, oggi: datetime | None = None) -> list[Contatto]:
    """Audita i contatti con sito. I no_site passano oltre senza audit."""
    oggi = oggi or datetime.now()
    a_cfg = cfg["audit"]
    tenuti = []
    for c in contatti:
        if not c.ha_sito:
            c.pipeline_stage = STAGE_AUDITED
            tenuti.append(c)
            continue
        if _cache_valida(c, a_cfg["cache_giorni"], oggi):     # #7 cache
            log.info("Audit in cache per %s (%s)", c.nome, c.sito)
            c.pipeline_stage = STAGE_AUDITED
            if int(float(c.score_sito)) < a_cfg["soglia_score_sito"]:
                tenuti.append(c)
            elif report is not None:
                report.aggiungi_filtro("sito_gia_buono")
            continue

        if dry_run:
            # dry-run: niente rete — audit simulato pessimista, marcato
            score, problemi, parziale = 35, ["[DRY-RUN] audit simulato"], True
        else:
            http = _check_http(c.sito)
            ps = _pagespeed_mobile(c.sito, a_cfg["pagespeed_timeout_secondi"])
            score, problemi = _score_da_segnali(http, ps, a_cfg["anno_footer_datato"])
            parziale = ps is None                              # #18c
            time.sleep(a_cfg["throttle_secondi"])              # #7 throttling

        c.score_sito = str(score)
        c.problemi_sito = "; ".join(problemi)
        c.audit_parziale = parziale
        c.data_audit = oggi.isoformat(timespec="seconds")
        c.pipeline_stage = STAGE_AUDITED
        if report is not None:
            report.auditati += 1
            if parziale:
                report.audit_parziali += 1

        if score < a_cfg["soglia_score_sito"]:
            tenuti.append(c)          # sito pessimo = nostro potenziale cliente
        else:
            if report is not None:
                report.aggiungi_filtro("sito_gia_buono")
            log.info("Scartato %s: sito già buono (score %d)", c.nome, score)
    return tenuti
