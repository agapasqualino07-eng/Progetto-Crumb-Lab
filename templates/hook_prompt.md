Genera un hook telefonico e una bozza di messaggio per questo lead.

## Regole (in ordine di importanza)

1. **Se `segnale_intent` NON è "NESSUNO", l'hook DEVE partire da lì** — dal
   "perché adesso", non dal problema-sito. Solo se il segnale è "NESSUNO"
   ripiega sul problema del sito (assente o con i problemi elencati).
2. Hook: 2-3 righe, parlato, da dire a voce nei primi 15 secondi di chiamata.
   Zero gergo tecnico ("performance mobile" → "il sito si carica male dal telefono").
3. Cita UN dato concreto e verificabile del lead (il problema del sito, la
   scheda non rivendicata, le recensioni). Mai dati inventati.
4. Aggancia il caso studio quando è pertinente: una concessionaria a Catania
   ha ottenuto +10 chiamate e +5 visite a settimana dopo la messa online del sito.
5. `hook_variante`: etichetta sintetica della leva usata, una tra:
   `intent-scheda-non-rivendicata`, `intent-sito-rotto`, `problema-sito`,
   `problema-no-sito` (o altra leva intent se emergerà).
6. `bozza_messaggio`: versione scritta più lunga (5-8 righe) da usare come
   follow-up manuale dopo la chiamata, tono cortese, con firma [NOME AGENZIA].

## Esempi

**Hook debole (da NON fare):** "Buongiorno, ho visto che non avete un sito web,
noi facciamo siti web, vi interessa?"

**Hook buono (intent):** "Buongiorno, chiamo perché ho notato che la vostra
scheda Google non è ancora rivendicata: chi vi cerca online trova mezzi dati
e nessun sito. Con una concessionaria qui a Catania, sistemando questo, sono
arrivate 10 chiamate in più a settimana. Ha due minuti?"

**Hook buono (problema-sito):** "Buongiorno, ho provato ad aprire il vostro
sito dal telefono e si vede tagliato, senza il listino. Per chi vende auto è
un problema: la gente ormai sceglie dal divano. Lo sappiamo perché con una
concessionaria di Catania, sistemato il sito, sono arrivate +10 chiamate a
settimana. Le va se le mostro cosa intendo?"

## Dati del lead

- nome: {nome}
- categoria: {categoria}
- città: {citta}
- bucket: {bucket}
- sito: {sito}
- problemi del sito: {problemi_sito}
- segnale_intent: {segnale_intent}
- ticket_fit: {ticket_fit}
- rating Google: {rating} ({recensioni} recensioni)
