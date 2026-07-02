# Valutazione del Legittimo Interesse (LIA) — Progetto "Faro"

**Titolare del trattamento:** [NOME AGENZIA], Catania — [EMAIL]
**Documento interno — versione MVP**
**Data:** 2 luglio 2026 · **Prossima revisione:** 2 gennaio 2027 (o prima, al passaggio dalla fase MVP alla fase prodotto)

> **Disclaimer.** Questo documento è una valutazione interna redatta in autonomia per un MVP e **non costituisce consulenza legale**. Prima di trasformare Faro in un prodotto, di ampliare le fonti dati o di aumentare i volumi di contatto, è necessario far rivedere questa LIA (e l'intero trattamento) a un professionista specializzato in privacy.

---

## 1. Descrizione del trattamento

Faro è un sistema interno di lead generation B2B usato da un'agenzia web di 2 persone. Il sistema:

- raccoglie da **Google Maps** dati di aziende locali: nome dell'attività, indirizzo, numero di telefono aziendale pubblico, rating, recensioni, presenza/qualità del sito web;
- arricchisce i record con **segnali pubblici di intent** (es. annunci di lavoro, nuove aperture) e un proxy della capacità di spesa;
- assegna uno **score di priorità** tramite LLM, basato esclusivamente su dati aziendali;
- prepara hook conversazionali per **telefonate manuali** a numeri aziendali pubblici.

**Esclusioni deliberate (by design):** nessun nome di titolari o persone fisiche (rimossi dall'MVP); nessuna email nominativa (solo indirizzi generici tipo `info@`); nessun invio automatico di comunicazioni. La fonte del dato è tracciata per ogni record.

## 2. Finalità e legittimo interesse (Purpose test)

**Finalità:** marketing diretto B2B — contattare telefonicamente, in modo manuale e selettivo, aziende locali che verosimilmente necessitano di servizi web, usando esclusivamente recapiti aziendali resi pubblici dalle aziende stesse a fini di contatto commerciale.

L'interesse è **reale, concreto e attuale**: acquisire clienti è condizione di sopravvivenza per una micro-agenzia. Il **considerando 47 GDPR** riconosce espressamente che «il trattamento di dati personali per finalità di marketing diretto può essere considerato come svolto per un legittimo interesse». L'interesse è lecito (attività commerciale ordinaria) e sufficientemente specifico.

Nota di perimetro: la maggior parte dei dati trattati riguarda **persone giuridiche**, escluse dal GDPR (considerando 14). Il GDPR rileva pienamente per le **ditte individuali e i liberi professionisti**, i cui dati "aziendali" sono dati personali. La LIA è quindi calibrata soprattutto su questi soggetti.

## 3. Test di necessità (Necessity test)

- **Il trattamento serve alla finalità?** Sì: senza recapito, categoria e contesto (sito assente/scadente, segnali di intent) non è possibile selezionare né contattare i lead giusti.
- **Esistono alternative meno invasive con pari efficacia?** Il consenso preventivo è impraticabile per il primo contatto B2B (paradosso: servirebbe contattare per chiedere il consenso). L'acquisto di liste terze offrirebbe **meno** controllo su qualità e provenienza dei dati. La raccolta diretta da fonti pubbliche con minimizzazione integrata è l'opzione meno invasiva disponibile.
- **Minimizzazione:** si trattano solo i dati strettamente necessari a selezionare e chiamare (niente nomi di persone, niente email personali, niente dati da fonti non pubbliche). Lo scoring usa solo attributi aziendali. Le ditte individuali sono **marcate e trattate con cautela extra**: retention più corta e **nessun arricchimento** con segnali aggiuntivi.

**Esito: il trattamento è necessario e proporzionato alla finalità.**

## 4. Test di bilanciamento (Balancing test)

**Natura dei dati.** Dati di contatto aziendali già pubblici (Google Maps, fonti pubbliche), pubblicati dalle aziende stesse proprio per essere contattate. Nessuna categoria particolare (art. 9), nessun dato di minori, nessun dato relativo alla vita privata.

**Aspettative ragionevoli dell'interessato.** Un'azienda (inclusa una ditta individuale) che pubblica il proprio numero su Google Maps si aspetta ragionevolmente di ricevere telefonate, incluse proposte commerciali B2B pertinenti alla propria attività. Il contatto è **umano, singolo, in orario lavorativo, su numero aziendale** — non massivo, non automatizzato, non su recapiti privati.

**Impatto potenziale.** Basso: al più il fastidio di una telefonata indesiderata, immediatamente interrompibile. Nessuna decisione con effetti giuridici o significativi sull'interessato deriva dallo scoring (vedi §5).

**Persone giuridiche vs ditte individuali.** Per le società di capitali/persone il rischio privacy è nullo o marginale. Per le ditte individuali il bilanciamento resta favorevole grazie alle cautele extra: marcatura, nessun arricchimento, retention ridotta, nessun dato oltre il recapito aziendale pubblico.

**Misure di mitigazione adottate:**

1. **Minimizzazione by design** — solo dati aziendali pubblici e necessari; fonte tracciata per record.
2. **No persone fisiche identificate** — nessun nome di titolare, nessuna email nominativa.
3. **No automazione del contatto** — solo chiamate manuali; nessun invio automatico di email/SMS.
4. **Retention limitata** — purge automatico a 12 mesi, o immediato allo stato "chiamato_no".
5. **Opt-out immediato e incondizionato** — l'opposizione espressa (anche verbalmente al telefono) comporta cancellazione/blocco senza discussione, come richiesto dall'art. 21(2)-(3) GDPR per il marketing diretto.
6. **Trasparenza** — informativa ex art. 14 disponibile via link e leggibile al telefono (v. `docs/INFORMATIVA.md`).
7. **Cautele extra per ditte individuali** — nessun arricchimento, retention più corta.
8. **Registro pubblico delle opposizioni:** verifica del Registro delle Opposizioni per i numeri che vi risultino iscrivibili (da confermare in fase prodotto per i numeri B2B).

## 5. Scoring LLM, profiling minimale e AI Act

Lo scoring assegnato dall'LLM è un **profiling minimale**: opera su attributi dell'**azienda** (qualità del sito, rating, segnali pubblici di intent), non su caratteristiche della persona; serve solo a ordinare la lista di chiamata interna; **non produce decisioni automatizzate con effetti giuridici o similmente significativi** sugli interessati (art. 22 GDPR non applicabile: la decisione di chiamare e l'esito restano umani). Il criterio è documentato e spiegabile su richiesta.

Rispetto all'**AI Act (Reg. UE 2024/1689)**: l'uso rientra nei sistemi a **rischio minimo/limitato** — non è una pratica vietata né un caso d'uso ad alto rischio (Allegato III). Restano gli obblighi generali di alfabetizzazione AI (art. 4) e la buona pratica di supervisione umana, già garantita dal flusso manuale. Da rivalutare se lo scoring evolvesse verso decisioni automatizzate o dati su persone fisiche.

## 6. Conclusione

Il legittimo interesse ex **art. 6(1)(f) GDPR** è una base giuridica adeguata per il trattamento descritto: l'interesse è reale e riconosciuto (considerando 47), il trattamento è necessario e minimizzato, e il bilanciamento è favorevole grazie alla natura pubblica e aziendale dei dati, alle aspettative ragionevoli degli interessati e alle mitigazioni adottate — in particolare per le ditte individuali.

**Condizioni di validità:** questa conclusione vale per l'MVP così com'è descritto. Va **rifatta** se si aggiungono nomi di persone, email nominative, invii automatici, nuove fonti dati, o se i volumi crescono in modo significativo.

**Firmato:** [NOME AGENZIA] · **Data:** 02/07/2026 · **Revisione entro:** 02/01/2027
