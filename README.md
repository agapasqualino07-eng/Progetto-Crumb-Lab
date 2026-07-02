# 🔦 Faro — Lead Generation Agentica per Agenzia Web

Ogni mattina Faro produce **fino a 10 contatti caldi** da chiamare: aziende
locali **senza sito** o **con un sito pessimo**, ognuna con dati, evidenza del
problema, telefono verificato e **hook personalizzato**. La chiamata la fai tu
a mano: il sistema **trova, non contatta** (vincoli legali in `docs/LIA.md`).

Specifiche complete: [PROJECT.md](PROJECT.md) · Stato lavori: [PROGRESS.md](PROGRESS.md)

---

## 🛑 KILL SWITCH (arresto d'emergenza)

Se il sistema fa qualcosa che non deve (spesa anomala, dati sbagliati):

1. Vai su GitHub → tab **Actions** → workflow **"Faro run giornaliero"**.
2. Clicca il menu **"…"** in alto a destra → **"Disable workflow"**.

Fatto: nessun run partirà più finché non lo riabiliti. È l'unico freno manuale
oltre al budget guard (che blocca da solo i run oltre il tetto di spesa).

---

## Come funziona (in breve)

```
BUDGET GUARD → ESPLORATORE NICCHIE (ordina le nicchie, ne propone di nuove)
→ SCOUT (Google Maps via Apify, multi-nicchia) → FILTRO (bucket + registro)
→ AUDIT (qualità sito) → ENRICH (email generica, intent, ticket-fit, telefono)
→ SCORING (LLM) → HOOK (LLM)
→ TEAM COPY: ricerca mercato → copywriter → persuasione → vendita telefonica
             → revisore bozze → CRITICO (vota il copy; sotto 70 lo fa riscrivere)
→ DELIVERY (quality gate, max 10) → TELEGRAM (i 10 lead sul tuo telefono) + email
```

Le nicchie vivono in `config/config.yaml`: oggi attive `concessionarie`,
`bb_case_vacanza`, `edilizia_ristrutturazioni`; in catalogo (spente, si
accendono con `attiva: true`): ristoranti/pizzerie, dentisti/studi medici,
fotografi/wedding, palestre/centri, atelier, studi professionali.
L'esploratore propone nicchie nuove nel report: si attivano SOLO a mano
(il sistema non allarga da solo la raccolta dati — scelta GDPR).

- **Lo stato vive sul Google Sheet** (tab `registro`, `spesa`, `consegna`):
  il runner di GitHub Actions è effimero, nessun file locale conta.
- **Tu compili solo** le colonne `stato_chiamata`, `note`, `data_contatto`
  del tab `consegna`: il sistema le legge e impara cosa converte.
- **Quality gate:** se un giorno solo 4 lead superano la soglia, ne arrivano 4.
  Meglio 4 ottimi che 10 con 6 spazzatura.

## Provalo subito senza spendere nulla (dry-run)

```bash
# 1. Scarica le dipendenze (una volta sola)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Lancia la pipeline su dati finti: zero API, zero spesa, zero Sheet
python -m core.run --dry-run
```

Se funziona vedi il log di tutta la catena e, alla fine, `✅ Run completato
(dry-run: nessuna spesa)`. I risultati finti finiscono in `dryrun_output/`
(apri `consegna.json` per vedere come saranno i lead veri).

I test si lanciano con:

```bash
python -m pytest tests/ -v
```

## Messa in produzione — ⚠️ CHECKPOINT SOCIO

Servono 4 cose, tutte spiegate passo-passo:

1. **Google Sheet + service account.** Crea un progetto su
   [console.cloud.google.com](https://console.cloud.google.com), abilita la
   **Google Sheets API**, crea un **service account** e scarica il JSON delle
   credenziali. Crea un Google Sheet vuoto e **condividilo** (tasto Condividi)
   con l'email del service account come **Editor**. L'ID del foglio è la parte
   lunga nell'URL tra `/d/` e `/edit`.
2. **Apify.** Registrati su [apify.com](https://apify.com), copia l'API token.
   Apri l'actor **Google Maps Scraper** (`compass/crawler-google-places`),
   leggi il **build number corrente** e incollalo in `config/config.yaml` →
   `apify.actor_build` (mai lasciare "latest" in produzione).
3. **Anthropic.** Chiave API da [console.anthropic.com](https://console.anthropic.com).
4. **GitHub Secrets.** Su GitHub → Settings → Secrets and variables → Actions,
   crea i secret: `APIFY_TOKEN`, `ANTHROPIC_API_KEY`, `PAGESPEED_API_KEY`
   (facoltativa ma consigliata), `GOOGLE_SHEET_ID`,
   `GOOGLE_SERVICE_ACCOUNT_JSON` (l'intero contenuto del file JSON, incollato
   così com'è), e per l'email del mattino: `SMTP_HOST`, `SMTP_PORT`,
   `SMTP_USER`, `SMTP_PASSWORD`, `REPORT_EMAIL_TO`, `REPORT_EMAIL_FROM`.

Per i test **in locale**: copia `.env.example` in `.env` e incolla lì le stesse
chiavi. Il `.env` è già nel `.gitignore`: **non finirà mai su GitHub**.

### Telegram: i 10 lead sul telefono ogni mattina (5 minuti di setup)

1. Su Telegram cerca **@BotFather** → scrivi `/newbot` → dagli un nome (es.
   "Faro Lead") → BotFather ti risponde con un **token** (una riga tipo
   `123456:ABC-...`). Copialo.
2. Cerca il tuo bot per nome su Telegram e **scrivigli un messaggio qualsiasi**
   (serve ad aprire la chat).
3. Apri nel browser `https://api.telegram.org/bot<TOKEN>/getUpdates`
   (col tuo token al posto di `<TOKEN>`) e copia il numero dopo `"chat":{"id":`.
4. Metti i due valori nei GitHub Secrets: `TELEGRAM_BOT_TOKEN` e
   `TELEGRAM_CHAT_ID`. Fine: da domattina il bot ti manda il riepilogo +
   un messaggio per lead (telefono, hook, copione, obiezioni).

Se Telegram non è configurato il run funziona lo stesso: arriva solo l'email.

Il run parte da solo **lun–ven alle 7:30** (ora italiana). Per lanciarlo a
mano: tab Actions → "Faro run giornaliero" → **Run workflow** (con la spunta
dry-run per una prova senza spesa).

## Budget

Tetto mensile in `config/config.yaml` → `budget.max_euro_mese` (default €30).
Il budget guard legge la spesa accumulata dal tab `spesa` del Sheet **prima**
di ogni run e blocca tutto se il run supererebbe il tetto; all'80% arriva una
email di alert. Secondo freno: cap `maxCrawledPlacesPerSearch` su ogni
chiamata Apify.

## Legale (leggere prima di chiamare)

- `docs/LIA.md` — valutazione del legittimo interesse (da firmare e datare).
- `docs/INFORMATIVA.md` — informativa privacy da linkare/leggere al telefono
  (compila i placeholder `[NOME AGENZIA]`, `[EMAIL]`, `[LINK]`).
- Se qualcuno dice "non chiamatemi più": segna `no` in `stato_chiamata` sul
  tab `consegna` — al run successivo il contatto è escluso per sempre e poi
  eliminato (retention automatica).
- Niente email nominative, niente invii automatici, niente nomi dei titolari:
  sono esclusioni **volute** (PROJECT.md sez. 7), non dimenticanze.

## Struttura del codice

```
agents/    un file per agente: budget_guard, scout, filtro, audit,
           enrich, scoring, hook, delivery
core/      run.py (orchestratore), models.py, storage.py (Sheet = DB),
           llm.py, observability.py, retention.py, config.py
config/    config.yaml — nicchie, soglie, pesi, budget: i criteri di
           business si cambiano QUI, non nel codice
templates/ hook_prompt.md — il prompt degli hook, modificabile a mano
tests/     dati mock + test delle funzioni critiche
docs/      LIA e informativa privacy
```

## M8 — Criterio di verdetto (pre-committato)

Dopo **4 settimane** di chiamate reali: se ottieni **meno di 1 meeting ogni
20 lead chiamati**, il problema è il targeting, non il codice → si rivedono
bucket/nicchia/ticket-fit **prima** di investire altro (PROJECT.md, M8).
