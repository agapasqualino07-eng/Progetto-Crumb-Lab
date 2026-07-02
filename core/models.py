"""Modello dati del contatto (PROJECT.md §5).

Un `Contatto` è una riga del tab `registro` sul Google Sheet.
Campo mancante = stringa vuota / None: MAI inventare valori plausibili.
"""

from dataclasses import dataclass, field, asdict, fields


# Stati del registro riciclabile (#1)
STATO_NUOVO = "nuovo"
STATO_CONSEGNATO = "consegnato"
STATO_CHIAMATO_NO = "chiamato_no"
STATO_CHIAMATO_INTERESSATO = "chiamato_interessato"

# Fasi pipeline per l'idempotency (#18d): la ripartenza salta le fasi già fatte
STAGE_SCRAPED = "scraped"
STAGE_AUDITED = "audited"
STAGE_SCORED = "scored"
STAGE_HOOKED = "hooked"
STAGE_DELIVERED = "delivered"
STAGE_ORDER = [STAGE_SCRAPED, STAGE_AUDITED, STAGE_SCORED, STAGE_HOOKED, STAGE_DELIVERED]

BUCKET_NO_SITE = "no_site"
BUCKET_SITO_PESSIMO = "sito_pessimo"


def stage_raggiunto(contatto, stage: str) -> bool:
    """True se il contatto ha già completato la fase `stage` (o oltre)."""
    if contatto.pipeline_stage not in STAGE_ORDER:
        return False
    return STAGE_ORDER.index(contatto.pipeline_stage) >= STAGE_ORDER.index(stage)


@dataclass
class Contatto:
    """Una riga del registro. I nomi dei campi = nomi delle colonne Sheet."""

    place_id: str = ""
    nome: str = ""
    categoria: str = ""
    nicchia: str = ""
    indirizzo: str = ""
    citta: str = ""
    provincia: str = ""
    telefono: str = ""
    telefono_valido: bool = False
    email_aziendale: str = ""
    sito: str = "ASSENTE"          # url oppure "ASSENTE"
    ha_sito: bool = False
    bucket: str = ""                # no_site | sito_pessimo (#15)
    score_sito: str = ""            # 0-100 (vuoto se non auditato)
    problemi_sito: str = ""
    audit_parziale: bool = False    # #18c — PageSpeed fallita, usati solo segnali gratuiti
    data_audit: str = ""            # cache audit (#7): non ri-auditare entro N giorni
    rating_google: str = ""
    num_recensioni: int = 0
    claimed: bool = False
    ditta_individuale: bool = False  # #17.7 — path stricter dal giorno 1
    segnale_intent: str = ""         # #2 — vuoto se nessun segnale trovato (mai inventato)
    ticket_fit: str = ""             # basso | medio | alto (#16)
    score_priorita: str = ""         # 0-100
    motivazione_score: str = ""
    hook: str = ""
    hook_variante: str = ""          # #6b — quale leva usa l'hook
    bozza_messaggio: str = ""
    copione: str = ""                # copione telefonico personalizzato (team copy)
    obiezioni_risposte: str = ""     # mappa obiezione → risposta per la chiamata
    stato_registro: str = STATO_NUOVO      # #1
    pipeline_stage: str = ""                # #18d
    data_generazione: str = ""
    data_scadenza_riciclo: str = ""
    fonte: str = ""                  # accountability GDPR (#11)
    # --- colonne di proprietà UMANA: la macchina le legge soltanto (#6) ---
    stato_chiamata: str = ""
    note: str = ""
    data_contatto: str = ""

    def to_row(self) -> dict:
        """Dict pronto per lo storage (bool → stringa per il Sheet)."""
        d = asdict(self)
        for k, v in d.items():
            if isinstance(v, bool):
                d[k] = "TRUE" if v else "FALSE"
        return d

    @classmethod
    def from_row(cls, row: dict) -> "Contatto":
        """Ricostruisce un Contatto da una riga letta dallo storage."""
        kwargs = {}
        for f in fields(cls):
            if f.name not in row or row[f.name] in (None, ""):
                continue
            v = row[f.name]
            if f.type == "bool" or isinstance(f.default, bool):
                v = str(v).strip().upper() in ("TRUE", "1", "SI", "SÌ", "YES")
            elif isinstance(f.default, int):
                try:
                    v = int(float(v))
                except (TypeError, ValueError):
                    v = 0
            kwargs[f.name] = v
        return cls(**kwargs)


COLONNE_REGISTRO = [f.name for f in fields(Contatto)]

# Colonne del tab consegna: dati utili alla chiamata + colonne umane
COLONNE_CONSEGNA = [
    "place_id", "nome", "categoria", "citta", "telefono", "email_aziendale",
    "sito", "bucket", "score_sito", "problemi_sito", "segnale_intent",
    "ticket_fit", "score_priorita", "motivazione_score",
    "hook", "hook_variante", "bozza_messaggio", "copione", "obiezioni_risposte",
    "data_generazione", "stato_chiamata", "note", "data_contatto",
]
