"""Run report e notifiche (criticità #12).

A fine giro: log strutturato di trovati / filtrati per motivo / auditati /
consegnati / errori / spesa stimata / pool residuo per zona, più la riga
di "salute" per l'email.
"""

import logging
import smtplib
import sys
from dataclasses import dataclass, field
from email.mime.text import MIMEText

from core.config import env

log = logging.getLogger("faro")


def configura_log():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )


@dataclass
class RunReport:
    trovati: int = 0
    duplicati_rimossi: int = 0
    filtrati: dict = field(default_factory=dict)   # motivo → conteggio
    auditati: int = 0
    audit_parziali: int = 0
    consegnati: int = 0
    errori: list = field(default_factory=list)
    spesa_run_eur: float = 0.0
    spesa_mese_eur: float = 0.0
    tetto_mese_eur: float = 0.0
    pool_residuo: dict = field(default_factory=dict)  # zona → lead `nuovo` residui
    prossima_espansione: str = ""
    giornata_basso_rendimento: bool = False
    voti_copy: list = field(default_factory=list)      # voti del critico copy
    nicchie_suggerite: list = field(default_factory=list)  # proposte esploratore

    def aggiungi_filtro(self, motivo: str):
        self.filtrati[motivo] = self.filtrati.get(motivo, 0) + 1

    def riga_salute(self) -> str:
        """La riga sintetica per l'email del mattino."""
        pool = ", ".join(f"{z}: {n} lead residui" for z, n in self.pool_residuo.items()) or "n/d"
        riga = (
            f"Oggi {self.consegnati} consegnati; pool {pool}; "
            f"prossima espansione: {self.prossima_espansione or 'nessuna'}; "
            f"spesa mese: €{self.spesa_mese_eur:.2f}/{self.tetto_mese_eur:.0f}"
        )
        if self.giornata_basso_rendimento:
            riga += " — ⚠️ giornata a basso rendimento (pochi lead sopra soglia)"
        return riga

    def testo_completo(self) -> str:
        righe = [
            "REPORT RUN FARO",
            "=" * 40,
            self.riga_salute(),
            "",
            f"Trovati (post-dedup): {self.trovati}  (duplicati rimossi: {self.duplicati_rimossi})",
            "Filtrati per motivo: "
            + (", ".join(f"{m}: {n}" for m, n in self.filtrati.items()) or "nessuno"),
            f"Auditati: {self.auditati}  (di cui parziali: {self.audit_parziali})",
            f"Consegnati: {self.consegnati}",
            f"Spesa stimata run: €{self.spesa_run_eur:.2f}",
        ]
        if self.voti_copy:
            righe.append(f"Qualità copy (voto critico): media "
                         f"{sum(self.voti_copy) / len(self.voti_copy):.0f}/100 "
                         f"su {len(self.voti_copy)} copioni")
        if self.nicchie_suggerite:
            righe.append("Nicchie NUOVE proposte dall'esploratore (da attivare "
                         "a mano in config, se convincono):")
            for n in self.nicchie_suggerite:
                if isinstance(n, dict):
                    righe.append(f" - {n.get('nome', '?')}: {n.get('leva', '')}")
        if self.errori:
            righe += ["", "ERRORI:"] + [f" - {e}" for e in self.errori]
        return "\n".join(righe)


def invia_email(oggetto: str, corpo: str, dry_run: bool = False) -> bool:
    """Invia il report via SMTP. In dry-run (o senza SMTP configurato) logga e basta."""
    host = env("SMTP_HOST")
    if dry_run or not host:
        log.info("[email non inviata — %s]\nOggetto: %s\n%s",
                 "dry-run" if dry_run else "SMTP non configurato", oggetto, corpo)
        return False
    msg = MIMEText(corpo, "plain", "utf-8")
    msg["Subject"] = oggetto
    msg["From"] = env("REPORT_EMAIL_FROM", env("SMTP_USER"))
    msg["To"] = env("REPORT_EMAIL_TO")
    try:
        with smtplib.SMTP(host, int(env("SMTP_PORT", "587"))) as s:
            s.starttls()
            s.login(env("SMTP_USER"), env("SMTP_PASSWORD"))
            s.send_message(msg)
        return True
    except Exception as e:  # una mail fallita non deve far fallire il run
        log.error("Invio email fallito: %s", e)
        return False
