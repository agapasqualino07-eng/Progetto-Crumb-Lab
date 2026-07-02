# CLAUDE.md — regole per lavorare su Faro

- **Stack:** Python 3.11+, venv (`python -m venv .venv && source .venv/bin/activate`), dipendenze in `requirements.txt`.
- **Chi guida non è un programmatore.** Spiega ogni comando in italiano semplice: cosa fa, dove incollarlo, cosa deve apparire se funziona. Marca `⚠️ CHECKPOINT SOCIO` i punti che richiedono competenza tecnica vera (cron, secret, service account).
- **Segreti:** solo in `.env` (locale) o GitHub Secrets (produzione). `.env` è in `.gitignore` dal primo commit. Mai stampare chiavi nei log.
- **Stato:** NESSUNO stato in file locali committati dal cron. Il runner GitHub Actions è effimero: registro, spesa e cache audit vivono sul Google Sheet (vedi PROJECT.md §2.7). L'accesso allo storage passa SOLO da `core/storage.py` (swap Supabase in FASE 2 = un solo file).
- **Persistenza a checkpoint:** un read batch a inizio run; write batch solo ai checkpoint (post-SCOUT per l'idempotency, fine run). Mai cella-per-cella.
- **Moduli piccoli**, un file per agente, docstring in italiano.
- **Piano prima di implementare.** Commit atomico + aggiornamento di `PROGRESS.md` a fine di ogni milestone.
- **Mai inventare dati:** campo mancante = vuoto + segnalato, non riempito con valori plausibili.
- **Rispetta le etichette [MVP]/[FASE 2] di PROJECT.md.** Se stai per costruire un [FASE 2], fermati e chiedi.
- **Test prima di dire "fatto":** `pytest` verde + `python -m core.run --dry-run` che completa la pipeline su dati mock senza spendere.
- **Kill switch:** GitHub → Actions → workflow "Faro" → Disable workflow (documentato nel README).
