# PROJECT.md — Sistema "Faro" · Lead Generation Agentico per Agenzia Web
### versione 3.1 (v3 + fix di coerenza dall'auto-audit: persistenza a checkpoint vs write-a-fine-run, idempotency per-contatto, numeri onesti)

> Documento di specifiche (PRD tecnico) da passare a Claude Code per costruire il sistema step-by-step.
> Chi guida: Agatino (marketing, non-tecnico) con supporto del socio ingegnere (Python/JS) come checkpoint tecnico.
> Ultima revisione dati: luglio 2026. **I prezzi delle API vanno riverificati prima di ogni fase.**
>
> **Nota di metodo (leggila):** questo file contiene più robustezza di quanta ne serva al primo giorno. Ogni miglioramento è etichettato `[MVP]` (fallo subito) o `[FASE 2]` (dopo i primi clienti). **Non costruire i [FASE 2] adesso.** Sono documentati perché il codice MVP non li renda impossibili domani, non perché vadano implementati ora. Costruire tutto subito = non partire mai.
>
> **Nota v3:** le criticità #14–#19 non aumentano lo scope MVP quanto sembra. Solo 4 sono davvero `[MVP]` (state persistence, ticket-fit, LIA/taglio nome titolare, robustezza run) e sono *correzioni*, non feature: senza, l'MVP o non funziona o è a rischio legale. Le altre due sono un parametro di config (#15) e un paragrafo di criterio decisionale (#19).

---

## 0. ISTRUZIONI PER CLAUDE CODE (leggi prima di tutto)

Sei l'agente che costruirà questo sistema. Regole di ingaggio:

1. **Non scrivere codice al primo messaggio.** Explore → Plan → Code → Commit. Aspetta il mio OK sul piano.
2. **Costruisci per milestone.** Non passare alla successiva finché quella corrente non gira e non l'ho approvata.
3. **Commit piccoli e reversibili.** Niente rewrite multi-file giganti.
4. **Chi ti guida non è programmatore.** Spiega in italiano ogni comando da lanciare, dove incollare le chiavi, cosa devo vedere se funziona. Marca `⚠️ CHECKPOINT SOCIO` quando serve competenza tecnica vera.
5. **Test prima di dire "fatto".** "Funziona" = ha girato su dati reali e ha prodotto l'output atteso.
6. **Mai inventare dati.** Campo mancante = vuoto + segnalato. Non riempire con valori plausibili.
7. **Sicurezza:** chiavi in `.env`, mai committato (in `.gitignore` dal primo commit). Mai stampare chiavi nei log.
8. **Nessuno stato in file locali del repo committati dal cron** (*criticità #14*). Il runner di GitHub Actions è effimero: registro e spesa vivono **sul Google Sheet**, non in `spend.json`/registro locali. Vedi 2.7.
9. Aggiorna `PROGRESS.md` a fine di ogni milestone.
10. **Non over-ingegnerizzare.** Rispetta le etichette [MVP]/[FASE 2]. Se stai per costruire qualcosa marcato [FASE 2], fermati e chiedimi.

---

## 1. CONTESTO & OBIETTIVO

### Chi siamo
Agenzia web di 2 persone a Catania. Vendiamo siti web + posizionamento. Ticket €1.500–5.000. Nicchia primaria validata: **concessionarie auto**. Secondarie: **atelier/lusso** e **studi professionali**. Case study reale: una concessionaria a Catania ha registrato +10 chiamate e +5 visite/settimana dopo la messa online del sito.

### Cosa deve fare il sistema
Ogni mattina produrre **fino a 10 contatti caldi** da chiamare: aziende locali che **non hanno sito** o **ne hanno uno pessimo**. Per ognuno: dati, evidenza del problema, telefono, e **hook personalizzato**. Il contatto (chiamata) lo facciamo NOI a mano — vedi sez. 7.

> ⚠️ **"Fino a 10", non "esattamente 10".** Vedi criticità #13: meglio 4 contatti ottimi che 10 con 6 spazzatura. Obiettivo di *consegna* confermato a 10/giorno, ma è il quality gate a decidere il numero reale, non un riempitivo.

> **Nota targeting (v3, criticità #15).** "No-site" e "sito-pessimo" NON sono uno primario e l'altro secondario per decreto: sono **due bucket con un peso di priorità configurabile**, testato A/B sugli esiti reali delle chiamate. Motivo: (a) chi ha un sito pessimo ha già budget, sente il dolore e capisce il valore → spesso converte *meglio* di chi non ha nulla; (b) il bacino no-site di una provincia si esaurisce in fretta, includere i siti-pessimi **amplia molto il pool** (quanto, dipende dal territorio) e rende sostenibili i 10/giorno più a lungo.
> **Falso ostacolo sfatato:** ripuntare un dominio *già esistente* su un sito nuovo è banale quanto puntarne uno nuovo — si cambiano i record DNS (A/CNAME) nel pannello del registrar del cliente verso Vercel; il vecchio sito smette semplicemente di essere servito. Nessuna difficoltà extra: il dominio esiste già, ha anzianità SEO, e il cliente ci tiene abbastanza da averlo comprato. Non è un motivo per deprioritizzare i siti-pessimi.

### Scopo doppio
- **Fase interna:** lo usiamo noi ora.
- **Fase prodotto:** se funziona, lo portiamo ai clienti. → codice modulare e configurabile (nicchia, zona, criteri come parametri), mai hardcoded.

### Vincoli
- **Budget: < €500/mese**, MVP puntiamo **< €30/mese**. Bootstrap.
- Costruisce Agatino con Claude Code; socio ingegnere sui punti critici.
- Prima esperienza con AI in produzione.

---

## 2. DECISIONI DI ARCHITETTURA (non ridiscutere senza motivo tecnico)

### 2.1 L'agente TROVA, non CONTATTA (in MVP)
Prepara dati + hook + bozza. L'invio/chiamata lo facciamo a mano. Motivi legali seri, sez. 7. Nessun invio email automatico in MVP.

### 2.2 Fonte per trovare aziende "senza sito": Google Maps
Il campo "sito web" su Google Maps è vuoto → candidato bucket no-site. Pieno → da auditare (bucket sito-pessimo).

- **OPZIONE A [MVP]: Apify "Google Maps Scraper".** ~$0.50–4 / 1.000 risultati; free tier ~$5/mese. Restituisce `website` (vuoto/pieno), telefono, rating, num recensioni, categoria, flag `claimedBusiness` (non rivendicato = titolare poco presente = target caldo). Niente proxy/captcha da gestire.
  - ⚠️ **v3 (criticità #18a):** **pinna la versione dell'actor** (`actorId` + tag di versione), non usare "latest". Gli attori Apify cambiano schema tra versioni e ti rompono il parsing (`website`, `claimedBusiness`).
  - ⚠️ **v3 (criticità #18b):** imposta SEMPRE il cap `maxCrawledPlaces` (o equivalente `limit`) per chiamata. Il BUDGET GUARD controlla *prima* del run ma non sa quanti risultati tornerà una query → senza cap, una query può restituire 10k risultati e sfondare il tetto prima che la guardia se ne accorga. Il cap per-chiamata è la vera difesa contro il runaway cost.
- **OPZIONE B [FASE 2/scale]: Google Places API (New) ufficiale.** Più solida legalmente ma il campo `websiteUri` fa scattare la tariffa **Enterprise** (la più cara). Free tier 2026: ~1.000 chiamate Enterprise/mese, poi ~$20/1.000. Il credito universale $200/mese è stato **eliminato a marzo 2025**. Usa field mask restrittive.

⚠️ **Legale su scraping:** i ToS Google vietano lo scraping di Maps e limitano il caching (max 30 giorni). Apify sposta il rischio sull'utente. Per uso interno a basso volume rischio pratico basso, ma va saputo. Per il prodotto → migrare a Opzione B. Non conservare i dati Google oltre il necessario, non ripubblicarli.

### 2.3 Verifica "sito pessimo": strumenti gratuiti
HTTP check (status/redirect/timeout), SSL, **PageSpeed Insights API (gratuita)** per performance mobile, viewport per responsive, anno copyright footer (≤2019 = datato). Soglia: performance mobile < 50 = scadente.

⚠️ **v3 (criticità #18c): fallback PageSpeed.** PageSpeed è lenta (10–30s per URL) e va spesso in timeout/errore. Se fallisce, **NON scartare il lead**: ripiega sui segnali gratuiti e affidabili (HTTP status, SSL assente/scaduto, viewport mancante, footer datato) e marca `audit_parziale = true`. Un lead con audit parziale vale più di un lead perso per un timeout.

### 2.4 LLM per hook e scoring: Claude Haiku 4.5
Prezzi (lug 2026, input/output per Mtok): **Haiku 4.5 $1/$5** (consigliato); GPT-4o-mini $0.15/$0.60 (alternativa più economica); Gemini Flash ancora meno. A volumi MVP: pochi €/mese. Modello configurabile via `LLM_MODEL`.

### 2.5 Architettura software: multi-agente MA semplice [MVP]
Gli "agenti" in MVP sono **moduli Python separati** (un file per compito) orchestrati da uno script sequenziale. **NIENTE framework multi-agente in MVP.** CrewAI (semplice, role-based) o LangGraph (robusto, produzione) solo in [FASE 2] se serve orchestrazione dinamica reale.

### 2.6 Scheduling giornaliero
**MVP: GitHub Actions cron** (gratuito entro free tier). ⚠️ CHECKPOINT SOCIO per cron e secret. *In produzione le chiavi vivono nei **GitHub Secrets**, non nel `.env`: il `.env` serve solo per i test in locale (e non si committa mai). Sul runner del cron non esiste un `.env` — Claude Code deve leggere le chiavi da variabili d'ambiente iniettate dai Secrets.*
- ⚠️ **v3: kill switch documentato.** L'arresto d'emergenza è disabilitare il workflow da GitHub → tab Actions → workflow → "Disable workflow". Scrivilo nel README. È l'unico freno manuale oltre al budget guard.

### 2.7 Storage e consegna — *criticità #14 (state persistence), DECISA*
Il runner di GitHub Actions è **effimero**: finito il job, il filesystem sparisce. Quindi `spend.json` e il registro stati NON possono vivere in file locali del repo — o ad ogni run ripartono da zero e **il budget guard non conta davvero la spesa del mese, il riciclo non funziona**.

**Decisione MVP: il Google Sheet È il database di stato, unico. Nessun file di stato locale.**
- Un **tab `registro`** (di proprietà della macchina): tutti i contatti con `stato_registro`, date, audit cache, ecc.
- Un **tab `spesa`** (di proprietà della macchina): contatore spesa mensile persistente per il budget guard.
- Un **tab `consegna` / CRM** (di proprietà TUA): i lead del giorno + le colonne che compili a mano (`stato_chiamata`, `note`, `data_contatto`).

**Regola di proprietà delle colonne (risolve race condition e rate limit):**
- La macchina **possiede e scrive** `stato_registro`, spesa, audit cache. Non tocca MAI le tue colonne.
- Tu **possiedi e scrivi** `stato_chiamata`/`note`/`data_contatto`. La macchina le **legge soltanto** (per il feedback loop #6).
- **Un solo read batch a inizio run; scritture batch solo a CHECKPOINT definiti** (dopo SCOUT per l'idempotency #18d, e a fine run), **mai cella-per-cella.** Così: (a) si resta dentro le quote Sheets API; (b) niente conflitti con te che editi in parallelo; (c) un crash a metà run non perde ciò che è già stato scaricato/lavorato — vedi #18d. ⚠️ *Correzione di coerenza:* NON è "un solo write a fine run" (come diceva la bozza), altrimenti un crash azzererebbe proprio il raw di Apify che l'idempotency deve salvare. Il checkpoint post-SCOUT è ciò che rende la ripartenza possibile senza ri-pagare.

**Migrazione [FASE 2]:** appena il volume sfonda i limiti Sheets (rate limit, assenza di query reali, foglio ingestibile) → **Supabase** (già in uso su altri progetti). In quel caso: Supabase = source of truth di stato, il Google Sheet diventa una *vista* di consegna sincronizzata. Il codice storage deve isolare l'accesso dietro `core/storage.py` così il cambio backend tocca un solo file.

---

## 3. ARCHITETTURA — i sotto-agenti (flusso sequenziale)

```
CONFIG (nicchia, province, criteri, budget, peso targeting no-site vs sito-pessimo)
   │
   ▼
[0 · BUDGET GUARD]  ── controlla tetto spesa PRIMA di ogni run (leggendo il tab `spesa`) (#3)
   ▼
[1 · SCOUT]    ── trova attività su Google Maps; cap maxCrawledPlaces (#18b); dedup cross-query (#4);
                  SALVA il raw grezzo su Sheet PRIMA degli step LLM a pagamento (#18d idempotency)
   ▼
[2 · FILTRO]   ── assegna bucket (no-site / da-auditare) con peso targeting (#15); registro riciclabile (#1)
   ▼
[3 · AUDIT]    ── HTTP+PageSpeed+SSL+footer; throttling e cache (#7); fallback se PageSpeed timeout (#18c)
   ▼
[4 · ENRICH]   ── email generica + SEGNALE DI INTENT (#2) + PROXY TICKET-FIT (#16) + validazione tel (#8)
                  [nome titolare RIMOSSO dall'MVP → FASE 2 (#17), vedi sez. 7]
   ▼
[5 · SCORING]  ── LLM: score = f(intent, qualità sito, TICKET-FIT #16); parsing JSON robusto (#5); feedback storico (#6)
   ▼
[6 · HOOK]     ── LLM: hook che PARTE dal segnale di intent (#2); parsing robusto (#5); tagga hook_variante (#6b)
   ▼
[7 · DELIVERY] ── QUALITY GATE: consegna solo sopra soglia, anche se <10 (#13); scrive tab consegna
   ▼
[8 · RUN REPORT] ── log strutturato del giro: trovati/filtrati/consegnati/errori/spesa/pool residuo (#12)
```

### Dettaglio agenti (con le correzioni integrate)

**[0] BUDGET GUARD** `[MVP]` — *criticità #3*
Prima di ogni run legge da `config` i tetti (`max_risultati_giorno`, `max_euro_mese`), legge il **contatore persistente dal tab `spesa`** (#14), e **blocca l'esecuzione** se il run supererebbe il tetto. Manda alert email al superamento dell'80%. La difesa contro il runaway cost è doppia: guardia pre-run (tetto mensile) + cap `maxCrawledPlaces` per chiamata Apify (#18b).

**[1] SCOUT** `[MVP]`
Chiama Apify per categoria+zona **con cap `maxCrawledPlaces`** (#18b) e **versione actor pinnata** (#18a). **Dedup cross-query nello stesso run** (*criticità #4*): stessa azienda sotto più categorie → deduplica per `place_id` PRIMA di processare. Output per attività: `nome, indirizzo, città, provincia, website, telefono, rating, num_recensioni, categoria, claimed, place_id`.
⚠️ **v3 idempotency (criticità #18d):** subito dopo SCOUT — l'unico step che a quel punto ha già *pagato* Apify — scrivi un **checkpoint** sul Sheet coi raw scaricati. Poi ogni contatto porta un campo **`pipeline_stage`** (`scraped → audited → scored → hooked → delivered`): la ripartenza salta gli step già completati, così un crash non fa ri-pagare **né Apify né l'LLM**. Nota: AUDIT (PageSpeed) è *gratuito*; gli step a costo sono SCOUT (Apify) e SCORING/HOOK (LLM) — sono quelli che l'idempotency protegge.

**[2] FILTRO + REGISTRO RICICLABILE** `[MVP]` — *criticità #1 e #15*
Regole base: no sito → bucket NO-SITE; sito presente → DA-AUDITARE; scarta se recensioni < soglia o rating < soglia o categoria fuori target.
**Peso targeting configurabile (#15):** ogni bucket ha un `peso_priorita` in config. Parti pure sbilanciato (es. no-site 0.6 / sito-pessimo 0.4) ma **entrambi attivi**: il quality gate e il feedback loop diranno quale converte. Non è un dogma, è un parametro.
**Registro NON binario:** stati con ciclo:
- `nuovo` → mai processato.
- `consegnato` (in attesa mia chiamata) → non ripresentare per N giorni.
- `chiamato_no` → escluso per sempre.
- `chiamato_interessato` → esce dal pool (è diventato trattativa).
- `riciclabile` → un `consegnato` non chiamato dopo N giorni torna `nuovo`.
**Espansione geografica automatica** (*sempre #1*): quando i lead `nuovo` di una zona scendono sotto una soglia (es. < 15 disponibili), il sistema allarga alla città/provincia successiva della lista in config, DA SOLO. Con entrambi i bucket attivi (#15) il pool dura sensibilmente di più prima di dover espandere — coerente con l'obiettivo 10/giorno sostenuti.

**[3] AUDIT** `[MVP]` (solo DA-AUDITARE) — *criticità #7 e #18c*
HTTP GET (status/redirect/tempo), SSL, PageSpeed mobile, viewport, anno footer → `score_sito` 0–100. Se < soglia (es. 50) tienilo, altrimenti scarta (sito già buono = non è nostro cliente).
**Rate limit + cache:** throttling tra chiamate + cache risultati audit (stesso dominio non ri-auditato per X giorni), salvata nel registro.
**Fallback (#18c):** se PageSpeed va in timeout/errore, ripiega sui segnali gratuiti (HTTP/SSL/viewport/footer), marca `audit_parziale = true`, NON scartare.

**[4] ENRICH** `[MVP base]` — *criticità #2, #8, #16, #17*
- Email **solo generica** (`info@`, `amministrazione@`) — MAI nominativa (vincolo legale sez. 7). Se il sito esiste, cerca in pagina contatti.
- ~~Nome titolare~~ → **RIMOSSO dall'MVP (#17).** È il campo più rischioso per GDPR (persona fisica identificata, soprattutto ditte individuali) a fronte del valore più basso: il nome lo chiedi in chiamata in 5 secondi. Torna in [FASE 2] solo se documentiamo una base giuridica dedicata. Vedi sez. 7.
- **SEGNALE DI INTENT** (*#2*): almeno un segnale di "perché adesso" dove possibile: presenza/volume annunci su Subito.it, "nuova apertura" da Google, post social recenti, "in assunzione". È ciò che trasforma un hook fotocopia in un hook che converte. Campo `segnale_intent`.
- **PROXY TICKET-FIT** (*criticità #16, NUOVO*): un segnale grezzo di "può permettersi €1.5–5k". Non serve la partita di bilancio, basta un proxy pubblico e cheap per nicchia:
  - concessionarie → **volume annunci attivi** (10 auto vs 100 auto = mondi diversi), num recensioni come proxy di traffico.
  - atelier/lusso → fascia prezzo prodotti, presenza multi-sede.
  - studi → num professionisti/soci se visibile.
  Campo `ticket_fit` (basso/medio/alto). Motivo: senza, un barbiere con 2 recensioni e zero sito scora alto ed è un pessimo lead da €3k. La qualità del sito e l'intent non bastano: serve la capacità di spesa.
- **Validazione telefono** (*#8*): normalizza, distingui fisso/mobile, scarta invalidi. Contatto senza telefono valido e senza email generica scende di priorità (non è chiamabile).
- Enrichment esterno a pagamento (Hunter/Dropcontact GDPR-compliant) → `[FASE 2]`, ~€30–50/mese.

**[5] SCORING (LLM)** `[MVP]` — *criticità #5, #6, #16*
Input LLM: dati contatto + criteri (nicchia, case study) + `segnale_intent` + **`ticket_fit` (#16)**. Output: `score_priorita` 0–100 + `motivazione`. Il ticket-fit è un fattore di primo piano: un lead "sito pessimo + alto intent" ma `ticket_fit=basso` NON deve stare in cima.
- **Parsing JSON robusto** (*#5*): l'LLM non è deterministico. Estrai il blocco JSON, prova il parse, se fallisce fai UN retry con prompt più stringente, se fallisce ancora logga e salta quel contatto (non crashare il run).
- **Feedback loop** (*#6*, `[MVP light]`): all'avvio l'agente **rilegge dal tab consegna gli esiti** (`chiamato_interessato` vs `chiamato_no`) e li passa all'LLM come esempi. Versione minima: conta quali categorie/segnali/`ticket_fit`/bucket hanno dato "interessato" e alza il loro peso. **Così il feedback ottimizza il targeting (#6) E, tramite `hook_variante`, la scelta dell'hook (#6b).**

**[6] HOOK (LLM)** `[MVP]` — *criticità #2, #5, #6b*
Genera hook di 2-3 righe + bozza messaggio lungo. **OBBLIGO: l'hook parte dal `segnale_intent` più forte disponibile**, non dal generico "non avete un sito". Se nessun segnale c'è, ripiega sul problema-sito, ma non è il default. File `templates/hook_prompt.md` con esempi hook-buono vs hook-debole, modificabile senza toccare codice. Parsing robusto come [5].
⚠️ **v3 (criticità #6b, `[MVP light]`):** tagga ogni hook con `hook_variante` (es. quale leva ha usato: intent-annunci / intent-apertura / problema-sito). Quando compili l'esito chiamata, il feedback loop scopre **quale tipo di hook converte**, non solo quale tipo di lead. La messaggistica è l'arma di vendita: misurala.

**[7] DELIVERY + QUALITY GATE** `[MVP]` — *criticità #13*
Ordina per `score_priorita`. **Consegna solo i contatti sopra soglia** (es. score ≥ 60), max 10. Se un giorno solo 4 superano la soglia, ne consegna 4 e **segnala "giornata a basso rendimento"** invece di riempire con 6 lead scadenti. Scrive sul tab consegna (colonne dati + `stato_chiamata`, `note`, `data_contatto` vuote da compilare a mano) + email riepilogo.

**[8] RUN REPORT** `[MVP light]` — *criticità #12*
A fine giro: log strutturato di trovati / filtrati per motivo / auditati / consegnati / errori / spesa stimata del run / **pool residuo per zona**. Riga di "salute" nell'email (es. "oggi 8 consegnati, pool Catania: 22 lead residui, prossima espansione: Siracusa; spesa mese: €12/30").

---

## 4. STACK & COSTI REALI

Linguaggio: **Python 3.x**.

| Componente | Strumento MVP | Costo reale (lug 2026) |
|---|---|---|
| Sourcing | Apify Google Maps Scraper (versione pinnata, cap risultati) | ~$0.50–4 / 1.000 risultati; free ~$5/mese |
| Audit | PageSpeed Insights API (con fallback) | Gratuita (con quote → throttling) |
| LLM | Claude Haiku 4.5 | $1/$5 Mtok → pochi €/mese |
| Storage/CRM + STATO | Google Sheets API (source of truth, #14) | Gratuito |
| Notifiche | SMTP / Postmark | ~€0 a bassi volumi |
| Scheduling | GitHub Actions cron | Gratuito |
| **Totale MVP** | | **~€5–30/mese** |

Enrichment a pagamento, Places API ufficiale, VPS, dashboard, Supabase (migrazione stato) → [FASE 2], entro €500/mese.

**Struttura cartelle (proposta):**
```
faro/
├── PROJECT.md · PROGRESS.md · CLAUDE.md
├── .env · .env.example · .gitignore · requirements.txt
├── config/
│   └── config.yaml          # per-nicchia (#10): criteri, categorie, soglie, legale, peso targeting (#15)
├── agents/
│   ├── budget_guard.py      # #3 (legge spesa dal Sheet, #14)
│   ├── scout.py             # #4 dedup + #18a versione + #18b cap + #18d salva raw pre-LLM
│   ├── filtro.py            # #1 registro riciclabile + espansione + #15 bucket/peso
│   ├── audit.py             # #7 throttling+cache + #18c fallback
│   ├── enrich.py            # #2 intent + #8 tel + #16 ticket-fit (NO nome titolare, #17)
│   ├── scoring.py           # #5 parsing + #6 feedback + #16 ticket-fit
│   ├── hook.py              # #2 + #5 + #6b hook_variante
│   └── delivery.py          # #13 quality gate
├── core/
│   ├── run.py               # orchestratore (resume-aware, #18d)
│   ├── models.py            # dataclass Contatto
│   ├── storage.py           # Sheet come DB di stato (#14); isola l'accesso per swap Supabase [FASE 2]
│   ├── llm.py               # wrapper LLM con parsing robusto riusabile (#5)
│   ├── observability.py     # run report + log (#12)
│   └── retention.py         # cancellazione/purge dati (#11)
├── templates/
│   └── hook_prompt.md
├── tests/
│   └── (mock data + dry-run, #9)
└── requirements.txt
```

---

## 5. MODELLO DATI (colonne Sheet)

Tab `registro` + `consegna` (la proprietà delle colonne è definita in 2.7).

```
place_id, nome, categoria, nicchia, indirizzo, citta, provincia,
telefono, telefono_valido (bool), email_aziendale,
sito (url o "ASSENTE"), ha_sito (bool), bucket (no_site|sito_pessimo),   # #15
score_sito, problemi_sito, audit_parziale (bool),                        # #18c
rating_google, num_recensioni, claimed,
segnale_intent, ticket_fit (basso|medio|alto),                           # #2, #16
score_priorita, motivazione_score,
hook, hook_variante, bozza_messaggio,                                    # #6b
stato_registro, pipeline_stage,                                          # #1 ; #18d resume (scraped/audited/scored/hooked/delivered)
data_generazione, data_scadenza_riciclo, fonte,                          # #1, #11 accountability
# --- compilate a mano da me (alimentano il feedback #6/#6b) ---
stato_chiamata, note, data_contatto
# nome_titolare RIMOSSO dall'MVP (#17); rientra solo in FASE 2 con base giuridica
```

Tab `spesa` (macchina, #14): `mese, euro_apify, euro_llm, euro_totale, ultimo_aggiornamento`.

---

## 6. CONFIG PER-NICCHIA `[MVP]` — *criticità #10 + #15 + #16*

Le tre nicchie NON sono uguali: categorie Google diverse, segnali diversi, **sensibilità legale diversa**, **proxy ticket-fit diverso**. Blocco per nicchia, non regole uniche.

```yaml
targeting:
  peso_bucket:            # #15 — A/B, aggiustabile a mano sugli esiti
    no_site: 0.6
    sito_pessimo: 0.4

nicchie:
  concessionarie:
    categorie_google: ["concessionaria auto", "auto usate", "autosalone"]
    segnali_intent: ["annunci_subito", "nuova_apertura", "in_assunzione"]
    ticket_fit_proxy: ["volume_annunci", "num_recensioni"]   # #16
    soglia_recensioni_min: 5
    note_legali: "telefono aziendale pubblico ok"
  atelier_lusso:
    categorie_google: ["atelier", "abiti da sposa", "boutique"]
    segnali_intent: ["nuova_collezione", "eventi", "instagram_attivo"]
    ticket_fit_proxy: ["fascia_prezzo", "multi_sede"]        # #16
    soglia_recensioni_min: 3
  studi_professionali:
    categorie_google: ["commercialista", "studio commercialista"]
    segnali_intent: ["nuova_sede", "nuovo_socio"]
    ticket_fit_proxy: ["num_soci"]                           # #16
    soglia_recensioni_min: 3
    note_legali: "ATTENZIONE deontologia: no toni promozionali aggressivi; ditta individuale = dati personali, cautela GDPR maggiore + path stricter (sez.7)"
```

Parti con la sola nicchia `concessionarie` attiva. Le altre due si accendono da config quando la prima funziona.

---

## 7. VINCOLI LEGALI (GDPR / Italia) — LEGGERE

Sintesi operativa (non è consulenza legale; per il prodotto consultare un legale privacy):

1. **Telefonata a numero aziendale pubblico = via più sicura.** Canale primario. Per questo l'agente prepara i dati per CHIAMARE.
2. **Cold email B2B in Italia è restrittiva.** Il Garante ha sanzionato la raccolta di email pubbliche + invio promozioni senza consenso, anche invocando il legittimo interesse. ePrivacy tende a richiedere consenso preventivo.
3. **Indirizzi:** generici (`info@`) → invio B2B possibile con cautele; **nominativi** (`mario.rossi@`) → serve consenso, NON usarli in automatico. L'ENRICH raccoglie solo generici.
4. **Dato pubblico ≠ libero.** Rispetta minimizzazione e finalità.
5. **⚠️ v3 — LA LIA VA A MONTE, NON SOLO PRIMA DELL'INVIO (*criticità #17*).** Già *costruire un database profilato* (score + motivazione + segnali) di aziende è **trattamento di dati personali** che necessita di una base giuridica *prima di iniziare*, non solo prima di contattare. In pratica, da subito:
   - **Documenta una LIA** (valutazione del legittimo interesse): finalità (B2B outreach commerciale), necessità, bilanciamento coi diritti dell'interessato. Anche una pagina scritta bene basta per l'MVP interno.
   - **Tieni pronta un'informativa** linkabile (art. 13/14 GDPR) per quando contatti.
   - **Traccia la `fonte`** di ogni dato (accountability) — già in colonna.
   - **AI Act:** profilare aziende/persone con un LLM per assegnare uno "score" tocca il tema del *profiling* → tienilo minimale e trasparente. (Lo sai bene: è il tuo dominio con AIComply.)
6. **Nome titolare RIMOSSO dall'MVP (#17):** persona fisica identificata = dato personale ad alto rischio, valore marginale (lo chiedi in chiamata). Rientra solo in FASE 2 con base giuridica dedicata.
7. **Ditta individuale vs società (*path stricter dal giorno 1*):** ditta individuale = dati personali → il pipeline **marca `ditta_individuale=true`** e applica il trattamento più cauto (retention più corta, nessun arricchimento extra). Non è solo una nota in config: è un ramo di comportamento. Rilevante soprattutto per studi professionali.
8. **Data retention / cancellazione** (*criticità #11*, `core/retention.py`): cancellare un contatto su richiesta + auto-eliminare i contatti oltre la finestra (es. 12 mesi) o `chiamato_no`. `[MVP light]`: funzione di purge + colonna `fonte`.

> **Nota v3 sulla roadmap:** la vecchia voce "[FASE 2] semi-automazione contatto" è stata **degradata a rischio da non assumere**: l'invio automatico B2B in Italia è esattamente ciò che il Garante sanziona. Non è un default di roadmap; se mai, solo dopo parere legale scritto.

---

## 8. RISCHI TECNICI NOTI

- **Scraping Google fragile:** layout cambia, captcha, rate limit. Batch piccoli, retry con backoff, **versione actor pinnata (#18a)**.
- **Runaway cost:** una query può tornare 10k risultati → **cap `maxCrawledPlaces` per chiamata (#18b)** oltre al budget guard pre-run.
- **Crash a metà run dopo aver pagato Apify:** **idempotency (#18d)** — SCOUT salva il raw prima degli step LLM, la ripartenza non ri-paga.
- **PageSpeed lenta/instabile:** timeout frequenti → **fallback su segnali gratuiti (#18c)**, non scartare il lead.
- **Stato perso su runner effimero:** risolto spostando stato+spesa sul Sheet (#14). Attenzione a quote Sheets → **un read + un write batch per run (2.7)**.
- **Limite risultati/query:** Maps espone ~60–120 per ricerca → splittare per città/quartiere/categoria e unire (dedup #4).
- **Qualità dati variabile:** rating/recensioni stale → verifica a campione a mano prima di chiamare.
- **Falsi positivi "senza sito":** l'attività ha un sito ma non su Google → presenza debole = lead valido comunque.
- **Quote API esaurite:** il giro salta → gestione errori + notifica (#12).
- **LLM non deterministico:** output JSON variabile → parsing robusto (#5).

---

## 9. TESTING & DRY-RUN `[MVP]` — *criticità #9*

Prima di spendere soldi e girare ogni giorno, **modalità dry-run**:
- Flag `--dry-run` che usa un piccolo dataset mock in `tests/` (5-10 attività finte), NON chiama Apify/LLM a pagamento, NON scrive sul Sheet reale (scrive un tab/foglio di test).
- Verifica tutta la catena (filtro → audit con fallback → scoring con ticket-fit → hook → delivery) a costo zero prima di ogni modifica.
- `tests/` con 2-3 test base sulle funzioni critiche (dedup, parsing JSON, quality gate, **budget guard che legge/scrive la spesa sul Sheet #14**).
Criterio: `python core/run.py --dry-run` fa girare l'intera pipeline su dati finti senza spendere un centesimo.

---

## 10. MILESTONE (ordine di costruzione)

Ogni milestone è verificabile da sola.

**M0 · Setup** `⚠️ CHECKPOINT SOCIO` — repo, `.gitignore`, `.env.example`, `requirements.txt`, `config.yaml` per-nicchia (#10) con peso targeting (#15), README in italiano con **kill switch (2.6)**. + **dry-run scheletro (#9)** + **LIA e informativa in bozza scritte (#17)**. Fatto: lancio un comando e vedo "setup ok"; ho una pagina di LIA salvata.

**M1 · SCOUT + FILTRO** — Apify (versione pinnata #18a, cap #18b) per 1 categoria+città, **dedup (#4)**, **raw salvato pre-LLM (#18d)**, **registro riciclabile (#1)**, **bucket + peso (#15)**. Fatto: stampa N attività reali di Catania con "ha sito" corretto e bucket assegnato; verifico 3 a mano.

**M2 · AUDIT** — score_sito con PageSpeed + **throttling/cache (#7)** + **fallback timeout (#18c)**. Fatto: su 5 siti reali lo score riflette la realtà; se stacco PageSpeed, l'audit ripiega e non perde il lead.

**M3 · ENRICH** — email generica, **segnale intent (#2)**, **ticket-fit proxy (#16)**, **validazione telefono (#8)**, **ramo ditta_individuale (#17.7)**. NIENTE nome titolare. Fatto: su 10 contatti, metà ha un segnale di intent e un ticket_fit valorizzato.

**M4 · SCORING + HOOK** — Claude Haiku, **parsing robusto (#5)**, scoring che pesa **ticket-fit (#16)**, hook dal segnale (#2) con **hook_variante (#6b)**. Fatto: leggo 5 hook, specifici e diversi; un lead ad alto intent ma ticket_fit basso NON è primo.

**M5 · DELIVERY + BUDGET GUARD** `⚠️ CHECKPOINT SOCIO` — Sheet come DB di stato (#14), **quality gate (#13)**, **budget guard che legge/scrive spesa sul Sheet (#3+#14)**, **run report con pool residuo (#12)**. Fatto: apro il foglio, ≤10 righe sopra soglia; email con riga di salute; se forzo il tetto spesa, il run si blocca; chiudo il run a metà e la ripartenza non ri-paga Apify (#18d).

**M6 · SCHEDULING** `⚠️ CHECKPOINT SOCIO` — GitHub Actions cron, gestione errori, notifica se fallisce, **kill switch testato**. Fatto: 3 giorni di fila trovo contatti nuovi senza fare nulla, e ricevo il report ogni mattina; so disabilitare il workflow in 10 secondi.

**M7 · FEEDBACK + RETENTION** — **feedback dagli esiti su targeting E hook_variante (#6/#6b)**, **purge/cancellazione (#11)**. Fatto: dopo aver segnato alcuni "interessato/no", scoring e scelta hook ne tengono conto; posso cancellare un contatto.

**M8 · VERDETTO** `[MVP]` — *criticità #19, NUOVO.* Non è codice: è il **criterio di kill pre-committato**. Dopo 4 settimane di chiamate reali, guardo il tasso **lead chiamati → meeting** e **meeting → trattativa**. Soglia decisa ORA (esempio da tarare): se **< 1 meeting ogni 20 lead chiamati**, il problema è il *targeting*, non il codice → si rivedono bucket/nicchia/ticket-fit *prima* di investire in [FASE 2]. Serve a non tenere in vita un sistema che non converte (il trap opposto a "non partire mai").

**[FASE 2] (dopo i primi clienti):** CrewAI/LangGraph se serve; dashboard web; **migrazione stato a Supabase**; enrichment a pagamento; nome titolare con base giuridica; Places API ufficiale; multi-nicchia piena. (NIENTE semi-automazione contatto senza parere legale — sez. 7.)

---

## 11. FILE CLAUDE.md DA CREARE (< 50 righe)
Stack Python/venv; chi guida non è esperto (spiega in italiano); segreti in `.env`; **nessuno stato in file locali committati dal cron → tutto sul Sheet (#14)**; moduli piccoli con docstring italiane; piano prima di implementare; PROGRESS.md + commit atomico a fine milestone; mai inventare dati; `⚠️ CHECKPOINT SOCIO` sui punti tecnici; **rispetta le etichette [MVP]/[FASE 2], non costruire i [FASE 2]**.

---

## 12. PRIMO PROMPT DA DARE A CLAUDE CODE

> Leggi PROJECT.md per intero. Non scrivere codice adesso.
> 1) Riassumimi in 10 righe cosa costruiremo, le decisioni già prese (incluse: Sheet come DB di stato, targeting a bucket con peso, nome titolare escluso), e quali parti sono [MVP] vs [FASE 2].
> 2) Segnalami contraddizioni o rischi non considerati.
> 3) Proponi il piano della sola Milestone M0, elencando ogni file che creerai e ogni comando che dovrò lanciare, spiegato in italiano semplice.
> Aspetta il mio OK prima di scrivere qualsiasi file.

---

## 13. CHANGELOG

### v3 → v3.1 (fix di coerenza — auto-audit)
- **Contraddizione persistenza risolta:** §2.7 diceva "un solo write a fine run", ma #18d richiede un write intermedio dopo SCOUT. Erano incompatibili (un crash avrebbe azzerato il raw di Apify). Ora: **write a checkpoint definiti** (post-SCOUT + fine run), mai cella-per-cella.
- **Idempotency completata:** aggiunto `pipeline_stage` per-contatto (`scraped→…→delivered`) → la ripartenza non ri-paga *neanche l'LLM*, non solo Apify. Corretto anche l'errore che chiamava AUDIT "step a pagamento LLM" (è gratuito).
- **Numeri onesti:** rimosso "raddoppia il pool / il doppio" (numero non giustificato) → "amplia molto, dipende dal territorio".
- **Chiavi nel cron chiarite:** GitHub Secrets in produzione, `.env` solo in locale. + typo.

### v2 → v3 (6 criticità nuove)

**14. State persistence (`[MVP]`, DECISA).** Runner GitHub Actions effimero → `spend.json`/registro locali si azzerano ogni run: budget guard e riciclo non funzionavano davvero. Stato+spesa spostati sul **Google Sheet come unica source of truth**, con proprietà delle colonne (macchina vs umano) e un read/write batch per run. Migrazione a Supabase = [FASE 2].

**15. Targeting parametrico no-site vs sito-pessimo (`[MVP light]`).** Da "primario/secondario" per decreto a **due bucket con peso configurabile e A/B sugli esiti**. I siti-pessimi spesso convertono meglio (budget + dolore + valore percepito) e **raddoppiano il pool** (chiave per i 10/giorno sostenuti). Sfatato il falso ostacolo: ripuntare un dominio esistente su Vercel è un cambio DNS, non una difficoltà.

**16. Ticket-fit / capacità di spesa (`[MVP]`).** Lo scoring pesava intent + qualità sito ma non la *serietà commerciale*. Aggiunto proxy `ticket_fit` per nicchia (volume annunci, fascia prezzo, num soci). Evita di mettere in cima un microbusiness che non spenderà mai €3k.

**17. LIA a monte + taglio nome titolare (`[MVP]`, legale).** La base giuridica/LIA va documentata *prima di processare*, non solo prima di inviare. `nome_titolare` rimosso dall'MVP (alto rischio, basso valore). Ramo `ditta_individuale` col trattamento più cauto dal giorno 1. Semi-automazione contatto degradata da roadmap a rischio-da-non-assumere.

**18. Robustezza del run (`[MVP]`).** (a) versione actor Apify pinnata; (b) cap `maxCrawledPlaces` per chiamata contro il runaway cost; (c) fallback se PageSpeed va in timeout; (d) idempotency: checkpoint sul Sheet dopo SCOUT + campo `pipeline_stage` per-contatto, così un crash non fa ri-pagare né Apify né l'LLM. + kill switch documentato.

**19. Criterio di kill del sistema (`[MVP]`, non-codice).** Milestone M8: soglia di conversione pre-committata (es. <1 meeting / 20 lead → si rivede il targeting) per non tenere in vita un sistema che non converte. Il trap opposto a "non partire mai".

### v1 → v2 (13 criticità — sintesi)
1. Registro riciclabile + espansione geografica. 2. Segnale di intent. 3. Budget guard. 4. Dedup cross-query. 5. Parsing JSON robusto. 6. Feedback loop. 7. Throttling+cache audit. 8. Validazione telefono. 9. Dry-run con mock. 10. Config per-nicchia. 11. Data retention/cancellazione. 12. Run report/observability. 13. Quality gate in consegna.

---

> **Avvertenza finale del Chief Strategist:** la v3 è più robusta ma anche più densa — e siamo di nuovo sul filo del "non partire mai". **Queste sono le ultime aggiunte prima di costruire.** Non aprire una v4 di criticità teoriche. Le 4 correzioni MVP vere (stato sul Sheet, ticket-fit, LIA/taglio nome, robustezza run) sono *necessità*, non feature: falle e basta. Poi costruisci M0→M8, porta il sistema a fare 10 chiamate vere per 4 settimane, e lascia che siano gli **esiti delle chiamate** — non altre ipotesi — a scrivere la v4.
