# PROGRESS.md — Stato lavori Faro

## ✅ M0 · Setup
Repo, `.gitignore` (con `.env`), `.env.example`, `requirements.txt`,
`config/config.yaml` per-nicchia con peso targeting (#15), README italiano
con kill switch (2.6), CLAUDE.md, scheletro dry-run (#9), LIA e informativa
in bozza (`docs/`) (#17). `python -m core.run --dry-run` gira.

## ✅ M1 · SCOUT + FILTRO
`agents/scout.py`: Apify con build pinnabile (#18a — v3: su API Apify il
pinning è il param `build`, verificato lug 2026), cap
`maxCrawledPlacesPerSearch` (#18b), dedup cross-query per place_id (#4),
raw salvato sul registro al checkpoint post-SCOUT (#18d).
`agents/filtro.py`: bucket no_site/sito_pessimo con peso configurabile (#15),
registro riciclabile a stati (#1), espansione geografica automatica,
marcatura `ditta_individuale` (#17.7).
⏳ Da verificare a mano: primo run reale su Catania con 3 attività controllate.

## ✅ M2 · AUDIT
`agents/audit.py`: HTTP/SSL/viewport/anno footer + PageSpeed mobile con
fallback su timeout (#18c → `audit_parziale=true`, lead NON perso),
throttling e cache per dominio (#7).
⏳ Da verificare a mano: score su 5 siti reali.

## ✅ M3 · ENRICH
`agents/enrich.py`: email SOLO generica, segnale intent onesto dai dati
disponibili (#2 — vuoto se non osservato, mai inventato), ticket-fit proxy
per nicchia (#16), validazione telefono con `phonenumbers` (#8), ramo
ditta_individuale senza arricchimento extra (#17.7). NIENTE nome titolare.

## ✅ M4 · SCORING + HOOK
`core/llm.py`: wrapper con parsing JSON robusto, 1 retry, skip senza crash (#5).
`agents/scoring.py`: score con ticket-fit in primo piano + cap lato codice
a 55 per ticket_fit=basso (#16), feedback loop dagli esiti (#6).
`agents/hook.py` + `templates/hook_prompt.md`: hook che parte dal segnale
di intent (#2), tag `hook_variante` (#6b).

## ✅ M5 · DELIVERY + BUDGET GUARD
`core/storage.py`: Google Sheet come unico DB di stato (#14), un read batch
a inizio run, write solo ai checkpoint (post-SCOUT e fine run — 2.7).
`agents/budget_guard.py`: tetto mensile letto/scritto sul tab `spesa`,
blocco pre-run, alert 80% (#3). `agents/delivery.py`: quality gate (#13).
`core/observability.py`: run report con pool residuo e riga di salute (#12).
⏳ CHECKPOINT SOCIO: creare service account + Sheet e fare il primo run reale.

## ✅ M6 · SCHEDULING (codice pronto, attivazione manuale)
`.github/workflows/faro.yml`: cron lun-ven 7:30 IT, lancio manuale con
opzione dry-run, notifica email su fallimento, kill switch documentato
(README e commento nel workflow).
⏳ CHECKPOINT SOCIO: inserire i GitHub Secrets e osservare 3 run di fila.

## ✅ M7 · FEEDBACK + RETENTION
Feedback dagli esiti su categorie/bucket/ticket_fit/hook_variante (#6/#6b)
dentro `agents/scoring.py`. `core/retention.py`: purge automatico (12 mesi,
6 per ditte individuali) + `chiamato_no`, cancellazione su richiesta (#11).

## ⏳ M8 · VERDETTO (non è codice)
Dopo 4 settimane di chiamate: **< 1 meeting / 20 lead chiamati → si rivede
il targeting** prima di qualsiasi FASE 2. Criterio pre-committato, vedi README.

---

## Verifiche automatiche eseguite
- `python -m pytest tests/ -v` → 13 test, tutti verdi.
- `python -m core.run --dry-run` → pipeline completa su 9 attività mock:
  1 duplicato rimosso (#4), 1 filtrata per recensioni, 1 per rating,
  1 non contattabile (#8), 2 auditate con fallback parziale (#18c),
  3 lead sopra soglia consegnati in `dryrun_output/consegna.json`,
  "giornata a basso rendimento" segnalata (#13), spesa €0.
- Secondo dry-run consecutivo → 0 consegnati (nessun doppione: il registro
  ricicla, il dedup regge, il gate non riempie con lead scadenti),
  espansione zona avanzata correttamente.

## Cosa manca prima del primo run vero (in ordine)
1. ⚠️ CHECKPOINT SOCIO: service account Google + Sheet condiviso (README §produzione).
2. ⚠️ CHECKPOINT SOCIO: GitHub Secrets + build number Apify in config.
3. Compilare i placeholder in `docs/LIA.md` e `docs/INFORMATIVA.md` e firmarli.
4. Primo run manuale (Actions → Run workflow), verifica di 3 lead a mano.

## Note [FASE 2] (non costruite, per scelta)
Supabase, enrichment a pagamento, Places API ufficiale, nome titolare con
base giuridica, dashboard, CrewAI/LangGraph, multi-nicchia piena.

## ✅ M4-bis · TEAM COPY (aggiunta su richiesta, 02/07/2026)
Cinque nuovi agenti in pipeline dopo l'hook, solo per i lead in consegna:
`agents/ricerca_mercato.py` (dossier per nicchia, 1 chiamata LLM/run),
`agents/copywriter.py` (copione: apertura/discovery/pitch/chiusura, template
in `templates/copione_prompt.md`), `agents/persuasione.py` (mappa obiezioni→
risposte con leve etiche), `agents/vendita_telefonica.py` (rifinitura parlato,
gatekeeper, segreteria, follow-up WhatsApp), `agents/revisore.py` (correzione
bozze + controllo deterministico anti-invenzione su telefoni/URL).
Base di conoscenza con fonti: `docs/COPIONE_MASTER.md` (copione fisso + 16
obiezioni con risposte). Nuove colonne consegna: `copione`, `obiezioni_risposte`.
Verificato: 16 test verdi, dry-run end-to-end coi nuovi campi popolati.

## ✅ M4-ter · MULTI-NICCHIA + CRITICO + TELEGRAM (02/07/2026)
- `agents/esploratore_nicchie.py`: ordina le nicchie attive per priorità
  (pool scarso + feedback esiti) e PROPONE nicchie nuove nel report — mai
  auto-attivate (scelta GDPR: lo scope dati si allarga solo a mano in config).
- Catalogo nicchie esteso in config: bb/case vacanza ed edilizia ATTIVE
  accanto alle concessionarie; ristoranti, dentisti (con nota pubblicità
  sanitaria L.145/2018), fotografi/wedding, palestre in catalogo spente.
- `agents/critico_copy.py`: rubrica in 5 criteri, voto 0-100; sotto la
  soglia (70) UNA riscrittura mirata e rivalutazione. Voto medio nel report.
- `core/telegram.py`: consegna mattutina su Telegram (riepilogo + 1 messaggio
  per lead con telefono/hook/copione/obiezioni), fallback silenzioso su email.
  Secrets: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID (istruzioni nel README).
- Stima budget aggiornata (~9 chiamate LLM/contatto).
Verificato: 21 test verdi; dry-run multi-nicchia end-to-end (3 nicchie
ordinate dall'esploratore, critico 85/100 sui copioni, 4 messaggi Telegram
preparati e loggati senza invio).
