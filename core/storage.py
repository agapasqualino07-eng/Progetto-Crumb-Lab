"""Storage: il Google Sheet È il database di stato (PROJECT.md §2.7, #14).

Tutto l'accesso ai dati passa da qui: per migrare a Supabase in FASE 2
si tocca solo questo file.

Regole rispettate:
- Un solo read batch a inizio run (`leggi_tutto`).
- Scritture batch solo ai checkpoint (post-SCOUT, fine run), mai cella-per-cella.
- Il tab `registro` e il tab `spesa` sono di proprietà della macchina.
- Il tab `consegna` viene solo LETTO (feedback #6) e APPESO (nuovi lead):
  le colonne umane (stato_chiamata, note, data_contatto) non vengono MAI
  sovrascritte dalla macchina.
"""

import json
import os
from pathlib import Path

from core.models import COLONNE_REGISTRO, COLONNE_CONSEGNA

COLONNE_SPESA = ["mese", "euro_apify", "euro_llm", "euro_totale", "ultimo_aggiornamento"]


class Storage:
    """Interfaccia astratta. Implementazioni: SheetStorage, DryRunStorage."""

    def leggi_tutto(self) -> dict:
        """UNICO read batch del run: {'registro': [...], 'spesa': [...], 'consegna': [...]}"""
        raise NotImplementedError

    def scrivi_registro(self, righe: list[dict]) -> None:
        raise NotImplementedError

    def scrivi_spesa(self, righe: list[dict]) -> None:
        raise NotImplementedError

    def appendi_consegna(self, righe: list[dict]) -> None:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Google Sheets (produzione)
# ---------------------------------------------------------------------------

class SheetStorage(Storage):
    """Google Sheet come source of truth. Richiede un service account.

    ⚠️ CHECKPOINT SOCIO: creare il service account su Google Cloud,
    abilitare la Sheets API e condividere il foglio con l'email del
    service account (permesso Editor).
    """

    TAB_REGISTRO = "registro"
    TAB_SPESA = "spesa"
    TAB_CONSEGNA = "consegna"

    def __init__(self, sheet_id: str | None = None):
        import gspread  # import pigro: non serve nei dry-run/test

        sheet_id = sheet_id or os.environ["GOOGLE_SHEET_ID"]
        credenziali = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
        if os.path.isfile(credenziali):
            client = gspread.service_account(filename=credenziali)
        else:
            client = gspread.service_account_from_dict(json.loads(credenziali))
        self.foglio = client.open_by_key(sheet_id)
        self._assicura_tab()

    def _assicura_tab(self):
        """Crea i tab con intestazioni se non esistono (primo avvio)."""
        esistenti = {ws.title for ws in self.foglio.worksheets()}
        per_tab = {
            self.TAB_REGISTRO: COLONNE_REGISTRO,
            self.TAB_SPESA: COLONNE_SPESA,
            self.TAB_CONSEGNA: COLONNE_CONSEGNA,
        }
        for nome, colonne in per_tab.items():
            if nome not in esistenti:
                ws = self.foglio.add_worksheet(nome, rows=2000, cols=len(colonne))
                ws.update([colonne])

    def leggi_tutto(self) -> dict:
        return {
            "registro": self.foglio.worksheet(self.TAB_REGISTRO).get_all_records(),
            "spesa": self.foglio.worksheet(self.TAB_SPESA).get_all_records(),
            "consegna": self.foglio.worksheet(self.TAB_CONSEGNA).get_all_records(),
        }

    def _scrivi_tab(self, nome_tab: str, colonne: list[str], righe: list[dict]):
        """Riscrive un intero tab di proprietà macchina in UN write batch."""
        ws = self.foglio.worksheet(nome_tab)
        valori = [colonne] + [[str(r.get(c, "")) for c in colonne] for r in righe]
        ws.clear()
        ws.update(valori)

    def scrivi_registro(self, righe: list[dict]) -> None:
        self._scrivi_tab(self.TAB_REGISTRO, COLONNE_REGISTRO, righe)

    def scrivi_spesa(self, righe: list[dict]) -> None:
        self._scrivi_tab(self.TAB_SPESA, COLONNE_SPESA, righe)

    def appendi_consegna(self, righe: list[dict]) -> None:
        """APPEND: non tocca mai le righe (e colonne) compilate a mano."""
        if not righe:
            return
        ws = self.foglio.worksheet(self.TAB_CONSEGNA)
        valori = [[str(r.get(c, "")) for c in COLONNE_CONSEGNA] for r in righe]
        ws.append_rows(valori, value_input_option="RAW")


# ---------------------------------------------------------------------------
# Dry-run (test): file JSON locali in dryrun_output/, zero API, zero spesa
# ---------------------------------------------------------------------------

class DryRunStorage(Storage):
    """Simula il Sheet su file locali. Usato da --dry-run e dai test (#9)."""

    def __init__(self, cartella: str = "dryrun_output"):
        self.cartella = Path(cartella)
        self.cartella.mkdir(parents=True, exist_ok=True)

    def _path(self, nome: str) -> Path:
        return self.cartella / f"{nome}.json"

    def _leggi(self, nome: str) -> list[dict]:
        p = self._path(nome)
        if not p.exists():
            return []
        return json.loads(p.read_text(encoding="utf-8"))

    def _scrivi(self, nome: str, righe: list[dict]):
        self._path(nome).write_text(
            json.dumps(righe, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def leggi_tutto(self) -> dict:
        return {
            "registro": self._leggi("registro"),
            "spesa": self._leggi("spesa"),
            "consegna": self._leggi("consegna"),
        }

    def scrivi_registro(self, righe: list[dict]) -> None:
        self._scrivi("registro", righe)

    def scrivi_spesa(self, righe: list[dict]) -> None:
        self._scrivi("spesa", righe)

    def appendi_consegna(self, righe: list[dict]) -> None:
        attuali = self._leggi("consegna")
        self._scrivi("consegna", attuali + righe)


def crea_storage(dry_run: bool) -> Storage:
    return DryRunStorage() if dry_run else SheetStorage()
