"""Test delle funzioni critiche (criticità #9).

Coperture richieste da PROJECT.md §9: dedup, parsing JSON, quality gate,
budget guard che legge/scrive la spesa via storage.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents import budget_guard, delivery, filtro, scout
from core.llm import estrai_json
from core.models import Contatto, STATO_CONSEGNATO, STATO_NUOVO
from core.retention import applica_retention, cancella_contatto
from core.storage import DryRunStorage


# ---------------------------------------------------------------- dedup (#4)

def test_dedup_cross_query():
    contatti = [
        Contatto(place_id="a", nome="Uno"),
        Contatto(place_id="b", nome="Due"),
        Contatto(place_id="a", nome="Uno bis"),
    ]
    unici, rimossi = scout.deduplica(contatti)
    assert len(unici) == 2
    assert rimossi == 1
    assert unici[0].nome == "Uno"   # vince la prima occorrenza


# ------------------------------------------------------- parsing JSON (#5)

def test_estrai_json_pulito():
    assert estrai_json('{"score_priorita": 80, "motivazione": "ok"}') == {
        "score_priorita": 80, "motivazione": "ok"}


def test_estrai_json_con_testo_intorno():
    testo = 'Ecco la valutazione:\n```json\n{"score_priorita": 70, "motivazione": "x"}\n```\nSpero aiuti!'
    assert estrai_json(testo)["score_priorita"] == 70


def test_estrai_json_rotto():
    assert estrai_json("non c'è nessun json qui") is None
    assert estrai_json('{"rotto": ') is None


# ------------------------------------------------------ quality gate (#13)

def _lead(pid, score):
    return Contatto(place_id=pid, nome=pid, score_priorita=str(score))


def test_quality_gate_non_riempie_con_lead_scadenti():
    contatti = [_lead("a", 90), _lead("b", 75), _lead("c", 61), _lead("d", 30), _lead("e", 10)]
    selezionati, basso = delivery.quality_gate(contatti, soglia=60, massimo=10)
    assert [c.place_id for c in selezionati] == ["a", "b", "c"]   # solo sopra soglia
    assert basso is True                                          # giornata a basso rendimento


def test_quality_gate_taglia_al_massimo():
    contatti = [_lead(str(i), 60 + i) for i in range(15)]
    selezionati, basso = delivery.quality_gate(contatti, soglia=60, massimo=10)
    assert len(selezionati) == 10
    assert basso is False
    assert int(selezionati[0].score_priorita) >= int(selezionati[-1].score_priorita)


# ------------------------------------- budget guard su storage (#3 + #14)

CFG_BUDGET = {
    "budget": {"max_euro_mese": 30.0, "alert_percentuale": 80,
               "max_risultati_giorno": 60,
               "costo_stimato_per_1000_risultati_eur": 4.0,
               "costo_stimato_llm_per_contatto_eur": 0.01},
    "delivery": {"max_contatti_giorno": 10},
}


def test_budget_guard_blocca_oltre_tetto(tmp_path):
    storage = DryRunStorage(cartella=str(tmp_path))
    mese = budget_guard.mese_corrente()
    storage.scrivi_spesa([{"mese": mese, "euro_apify": 25.0, "euro_llm": 4.8,
                           "euro_totale": 29.8, "ultimo_aggiornamento": ""}])
    righe = storage.leggi_tutto()["spesa"]
    ok, msg, _ = budget_guard.controlla(CFG_BUDGET, righe)
    assert ok is False
    assert "BLOCCATO" in msg


def test_budget_guard_persiste_spesa_su_storage(tmp_path):
    storage = DryRunStorage(cartella=str(tmp_path))
    ok, _, spesa = budget_guard.controlla(CFG_BUDGET, storage.leggi_tutto()["spesa"])
    assert ok is True
    spesa = budget_guard.registra_spesa(spesa, euro_apify=0.24, euro_llm=0.10)
    storage.scrivi_spesa(budget_guard.aggiorna_righe_spesa([], spesa))
    # il run successivo rilegge la spesa persistita (#14)
    riletta = budget_guard.leggi_spesa_mese(
        storage.leggi_tutto()["spesa"], budget_guard.mese_corrente())
    assert riletta["euro_totale"] == 0.34


def test_budget_guard_alert_80_percento():
    righe = [{"mese": budget_guard.mese_corrente(), "euro_apify": 25.0,
              "euro_llm": 0.0, "euro_totale": 25.0, "ultimo_aggiornamento": ""}]
    ok, msg, _ = budget_guard.controlla(CFG_BUDGET, righe)
    assert ok is True
    assert "ALERT" in msg


# --------------------------------------------- registro riciclabile (#1)

def test_riciclo_consegnato_scaduto():
    ieri = (datetime.now() - timedelta(days=1)).isoformat(timespec="seconds")
    c = Contatto(place_id="x", nome="X", stato_registro=STATO_CONSEGNATO,
                 data_scadenza_riciclo=ieri)
    cfg = {"registro": {"giorni_riciclo": 14}, "zona": {"citta": ["Catania"],
           "provincia_default": "CT", "soglia_espansione": 15}}
    registro, processabili = filtro.sincronizza_registro([c], [], [], cfg)
    assert c.stato_registro == STATO_NUOVO
    assert c in processabili


def test_esito_umano_chiude_il_ciclo():
    c = Contatto(place_id="y", nome="Y", stato_registro=STATO_CONSEGNATO)
    cfg = {"registro": {"giorni_riciclo": 14}}
    esiti = [{"place_id": "y", "stato_chiamata": "no"}]
    filtro.sincronizza_registro([c], [], esiti, cfg)
    assert c.stato_registro == "chiamato_no"


# --------------------------------------------------------- retention (#11)

def test_retention_purga_chiamato_no_e_scaduti():
    vecchio = (datetime.now() - timedelta(days=400)).isoformat(timespec="seconds")
    contatti = [
        Contatto(place_id="a", stato_registro="chiamato_no"),
        Contatto(place_id="b", data_generazione=vecchio),
        Contatto(place_id="c", data_generazione=datetime.now().isoformat(timespec="seconds")),
    ]
    cfg = {"retention": {"mesi_massimi": 12, "mesi_massimi_ditta_individuale": 6}}
    superstiti, eliminati = applica_retention(contatti, cfg)
    assert eliminati == 2
    assert [c.place_id for c in superstiti] == ["c"]


def test_cancellazione_su_richiesta():
    contatti = [Contatto(place_id="a"), Contatto(place_id="b")]
    dopo, trovato = cancella_contatto(contatti, "a")
    assert trovato and len(dopo) == 1


# ------------------------------------------------- team copy (revisore)

def test_revisore_segnala_telefono_inventato():
    from agents.revisore import controlla_coerenza
    c = Contatto(place_id="z", nome="Z", telefono="+390951234567",
                 sito="https://esempio.example")
    testo = "Chiamaci allo 095 999 8888 o visita https://truffa.example/offerta"
    avvisi = controlla_coerenza(c, testo)
    assert len(avvisi) == 2   # telefono E url non presenti nei dati


def test_revisore_ok_con_dati_reali():
    from agents.revisore import controlla_coerenza
    c = Contatto(place_id="z", nome="Z", telefono="+390951234567",
                 sito="https://esempio.example")
    testo = "La richiamo al +39 095 1234567, ho visto esempio.example"
    assert controlla_coerenza(c, testo) == []


def test_catena_copy_in_dry_run():
    """L'intera catena copy gira con l'LLM finto e produce copione + obiezioni."""
    from agents import copywriter, persuasione, ricerca_mercato, revisore, vendita_telefonica
    from core.llm import LLMFinto
    llm = LLMFinto()
    c = Contatto(place_id="t", nome="Test Motors", categoria="Concessionaria auto",
                 citta="Catania", bucket="no_site", ticket_fit="alto",
                 segnale_intent="scheda non rivendicata", hook="hook di prova")
    dossier = ricerca_mercato.dossier_nicchia("concessionarie", "Catania", "", llm)
    assert dossier["argomenti_chiave"]
    bozza = copywriter.scrivi_copione(c, dossier, llm)
    assert bozza and "apertura" in bozza
    obiezioni = persuasione.mappa_obiezioni(c, dossier, llm)
    assert obiezioni and obiezioni[0]["obiezione"]
    finale = vendita_telefonica.rifinisci(c, bozza, llm)
    assert finale and "copione" in finale
    rivisto = revisore.rivedi(c, finale, obiezioni, llm)
    assert rivisto["copione"] and rivisto["obiezioni_risposte"]


# --------------------------------- multi-nicchia, critico e Telegram

class _LLMMuto:
    """LLM che fallisce sempre: per testare i fallback deterministici."""
    chiamate = 0
    def genera_json(self, *a, **k):
        return None


def test_esploratore_fallback_pool_scarso():
    from agents import esploratore_nicchie
    nicchie = {"a": {"leva_chiave": ""}, "b": {"leva_chiave": ""}}
    ordine, proposte, _ = esploratore_nicchie.esplora(
        nicchie, ["a", "b"], {"a": 50, "b": 2}, "Catania", "", _LLMMuto())
    assert ordine == ["b", "a"]   # pool più scarso per primo
    assert proposte == []


def test_critico_sopra_soglia_non_riscrive():
    from agents import critico_copy
    from core.llm import LLMFinto
    c = Contatto(place_id="k", nome="K", copione="testo", obiezioni_risposte="ob")
    cfg = {"copy": {"soglia_critico": 70, "max_iterazioni": 1}}
    voto = critico_copy.controlla_e_migliora(c, LLMFinto(), cfg)
    assert voto == 85                    # LLMFinto vota 85
    assert c.copione == "testo"          # nessuna riscrittura sopra soglia


def test_critico_sotto_soglia_riscrive_una_volta():
    from agents import critico_copy

    class _LLMSevero:
        """Prima valutazione 50, poi migliora, poi 90."""
        def __init__(self):
            self.voti = [50, 90]
        def genera_json(self, prompt, system, campi):
            if "voto" in campi:
                return {"voto": self.voti.pop(0), "punti_deboli": ["debole"],
                        "suggerimenti": ["più specifico"]}
            return {"copione": "RISCRITTO", "obiezioni_risposte": "RISCRITTE"}

    c = Contatto(place_id="k", nome="K", copione="fiacco", obiezioni_risposte="ob")
    cfg = {"copy": {"soglia_critico": 70, "max_iterazioni": 1}}
    voto = critico_copy.controlla_e_migliora(c, _LLMSevero(), cfg)
    assert voto == 90
    assert c.copione == "RISCRITTO"


def test_telegram_formatta_lead_entro_limite():
    from core.telegram import formatta_lead, MAX_LEN
    c = Contatto(place_id="t", nome="Test", citta="Catania",
                 telefono="+390951234567", score_priorita="80",
                 hook="hook", copione="x" * 10000, obiezioni_risposte="y" * 5000)
    msg = formatta_lead(1, c)
    assert len(msg) <= MAX_LEN + 200     # troncato, non esplode
    assert "+390951234567" in msg        # i dati di chiamata restano


def test_telegram_non_invia_in_dry_run():
    from core.telegram import invia_consegna
    from core.observability import RunReport
    cfg = {"telegram": {"attivo": True}}
    n = invia_consegna([Contatto(place_id="t", nome="T")], RunReport(),
                       "02/07/2026", cfg, dry_run=True)
    assert n == 0   # niente rete in dry-run
