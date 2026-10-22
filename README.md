# Elkron MP500 (IT500WEB) per Home Assistant

🇮🇹 Italiano · 🇬🇧 [English](README.en.md)

Integrazione personalizzata, **locale** (nessun cloud), per le centrali antifurto **Elkron MP500** con il modulo di rete **IT500WEB**. Mostra gli ingressi della centrale come sensori, mostra lo stato dell'impianto e permette di **inserire e disinserire tutto l'impianto** da Home Assistant.

> **English, in short:** local (no cloud) custom integration for Elkron MP500 alarm panels with the IT500WEB network module. Input sensors, panel state and total arm/disarm. Names are read from the panel automatically if you give the Web Server login once (it is not stored). Install via HACS (custom repository) or by copying `custom_components/elkron_mp500`. Not affiliated with Elkron/Urmet. Tested only on an MP500/8 (reading, total arm and disarm verified there); see "Limiti noti".

Progetto indipendente: **non è affiliato né approvato da Elkron/Urmet**. Il protocollo del modulo IT500WEB non è pubblico: l'integrazione è basata sull'analisi del traffico di rete di Hi-Connect e del Web Server. Usala a tuo rischio e, prima di fidarti dei comandi, provali con l'impianto sotto controllo.

## Cosa fa

- **Sensori degli ingressi.** Un sensore binario per ogni ingresso che la centrale riporta. Il numero non è fisso: viene letto dalla centrale (4, 8, 16... ingressi, cablati e wireless), quindi si adatta al tuo impianto.
- **Nomi.** Se fornisci una sola volta utente e password del Web Server, l'integrazione legge i nomi degli ingressi e dei settori dalla centrale. Se un ingresso non ha nome nella centrale, o non dai le credenziali, si chiama semplicemente **Ingresso 1, Ingresso 2, ...** e puoi rinominarlo a mano dalle opzioni.
- **Settori.** Ogni sensore ha l'attributo `settori` con i settori a cui appartiene (se letti dalla centrale).
- **Entità `Sistema`** (pannello di allarme): `Disattivato` / `Fuori casa` (inserito) e i comandi **inserisci** e **disinserisci**. In questa versione si inserisce e disinserisce **sempre tutto l'impianto**.
- **Locale.** Nessun account o cloud. Il modulo deve essere raggiungibile in rete dalla macchina di Home Assistant.

## Codice di disinserimento (facoltativo)

In **Impostazioni → Dispositivi e servizi → Elkron MP500 → Configura** puoi impostare un codice numerico di 6 cifre, scelto da te. Non è il codice utente né tecnico della centrale: vale solo in Home Assistant. Se impostato, Home Assistant lo chiede prima di disinserire (dashboard, script, assistenti vocali); l'inserimento resta senza codice. Il codice è salvato solo come hash con salt. Dopo 5 errori consecutivi il disinserimento è bloccato per 5 minuti. Per toglierlo spunta "Togli il codice di disinserimento".

È un blocco software: non protegge dai disinserimenti fatti con app, web o tastiera della centrale.

## Card per la dashboard (facoltativa)

In [`examples/dashboard_card.yaml`](examples/dashboard_card.yaml) c'è una card pronta: display con lo stato, pulsanti INSERISCI e DISINSERISCI e un riquadro per ogni ingresso con nome, stato e ultima variazione (toccando un riquadro si apre lo storico). Il display usa il carattere *VT323* di Google Fonts (il browser lo scarica da internet; senza connessione usa un carattere monospazio). Richiede quattro componenti da installare prima da HACS → Frontend: **button-card** (custom-cards/button-card), **stack-in-card** (custom-cards/stack-in-card), **card-mod** (thomasloven/lovelace-card-mod) e **Browser Mod** (thomasloven/hass-browser_mod; richiede anche l'integrazione omonima). Come usarla: Dashboard → Modifica → Aggiungi scheda → **Manuale** → incolla il contenuto del file. Se la tua centrale ha meno ingressi cancella i riquadri in più.

Se hai impostato il codice, DISINSERISCI apre un **tastierino numerico** (servizi `elkron_mp500.keypad_press` e `keypad_submit`): le cifre restano solo in memoria nell'integrazione e si azzerano dopo 30 secondi. Con il codice giusto il popup si chiude da solo; con quello sbagliato resta aperto con l'errore. Se hai impostato il codice di disinserimento viene controllato, altrimenti il disinserimento parte comunque. Senza codice impostato disinserisce direttamente, dopo una conferma.

## Cosa NON fa (per ora)

- Inserimento **parziale** o per singolo settore, scenari e uscite.
- Storico eventi della centrale.
- Il codice utente della centrale non è usato: il codice di disinserimento è solo quello di Home Assistant (vedi "Codice di disinserimento").

## Requisiti

- Centrale Elkron MP500 con modulo IT500WEB collegato alla rete, con **IP fisso** (consigliato: prenotazione sul router).
- Home Assistant recente (provata con la 2026.10; i test automatici con la 2026.2).
- Il servizio TCP del modulo sulla porta TCP predefinita.

## Installazione

### Con HACS (consigliata)
1. HACS → menu a tre puntini → **Repository personalizzati**.
2. Incolla questo indirizzo nel campo "Repository":
   ```
   https://github.com/stefanodr/ha-elkron-mp500
   ```
   Categoria **Integrazione** → **Aggiungi**.
3. Cerca **Elkron MP500**, scarica, **riavvia Home Assistant**.

### Manuale
1. Copia la cartella `custom_components/elkron_mp500` in `/config/custom_components/` (sovrascrivendo la vecchia versione, se c'è).
2. **Riavvia Home Assistant.**

## Configurazione, passo per passo

1. **Impostazioni → Dispositivi e servizi → Aggiungi integrazione → Elkron MP500.**
2. Compila:

| Campo | Cosa mettere |
|---|---|
| Indirizzo IP IT500WEB | L'IP del modulo (lo stesso che apri nel browser per il Web Server). |
| Porta TCP | Quella predefinita (lasciala se non l'hai cambiata). |
| Intervallo di polling | Ogni quanti secondi leggere lo stato. Predefinito 10 s, minimo 1, massimo 300. |
| Utente / Password Web Server | **Facoltativi.** Sono lo stesso utente e la stessa password con cui entri nella pagina web del modulo. Servono **una sola volta** per leggere i nomi e **non vengono salvati**. Lasciali vuoti per avere "Ingresso N". |
| Codice impianto | **Facoltativo.** 8 cifre. Lascia il valore di fabbrica (precompilato) se non l'hai cambiato. |
| Codice tecnico | **Facoltativo.** Lascia il valore di fabbrica (precompilato) se non l'hai cambiato. |

3. Conferma. Se i codici non sono accettati dalla centrale vedrai l'errore "Codice impianto o codice tecnico non accettati".

### Cambiare nomi, tipi, intervallo (opzioni)
**Impostazioni → Dispositivi e servizi → Elkron MP500 → Configura:**
- **Nome ingresso N**: il nome che preferisci (ha la precedenza su quello della centrale).
- **Tipo ingresso N**: *Apertura* (generico), *Porta*, *Finestra* o *Movimento*. Decide come si legge lo stato: Aperto/Chiuso oppure Rilevato/Non rilevato, e l'icona.
- **Rileggi i nomi dalla centrale**: spunta e inserisci utente e password del Web Server. I nomi scritti a mano vengono sostituiti da quelli della centrale.

### Se hai cambiato i codici di fabbrica
Il *codice impianto* e il *codice tecnico* sono quelli impostati sulla centrale (li usa anche Hi-Connect per collegarsi). Se la configurazione li rifiuta, controlla di averli scritti giusti. Per cambiarli dopo la configurazione, elimina la voce e aggiungila di nuovo.

## Come funziona la convivenza con app, Web Server e Hi-Connect

La centrale accetta **un solo accesso web alla volta**, e ogni login viene scritto nel suo storico; in prove lunghe, centinaia di login al giorno hanno portato il Web Server della centrale a non rispondere più (serve staccare la corrente). Per questo l'integrazione:
- fa **un solo login e lo tiene aperto**, come Hi-Connect, leggendo lo stato ogni 10 secondi (predefinito) sulla stessa connessione; inserimento e disinserimento usano la stessa sessione;
- prima di entrare controlla se qualcuno è già collegato e, in quel caso, non prova nemmeno a fare login;
- offre l'interruttore **`switch.elkron_mp500_connessione`**: per usare la **pagina web o l'app Android** spegnilo (l'integrazione esce dal login e le entità risultano non disponibili); riprende da sola dopo 15 minuti, oppure quando lo riaccendi. Il servizio `elkron_mp500.pause` permette di scegliere i minuti (utile nelle automazioni). Per usare Hi-Connect fai lo stesso;
- se la lettura fallisce, mostra l'ultimo stato valido per 90 secondi, poi le entità diventano non disponibili;
- fa un login web anche per leggere i nomi, dura meno di un secondo e viene chiuso subito.

L'interruttore ha gli attributi **`login_totali`** e **`contatore_dal`**: i login fatti dall'integrazione dall'ultima volta che hai azzerato il contatore. Dopo aver riavviato la centrale chiama il servizio `elkron_mp500.reset_login_counter`: così si vede quanti login la centrale regge. L'entità `Sistema` ha `sessioni_aperte` (sessioni dall'avvio di Home Assistant); con la sessione tenuta aperta deve restare basso.

## Entità create
Gli `entity_id` sono fissi e non cambiano se rinomini gli ingressi: `alarm_control_panel.elkron_mp500_sistema` e `binary_sensor.elkron_mp500_ingresso_1`, `..._2`, ... Usali nelle dashboard e nelle automazioni.


- `binary_sensor.*ingresso_N*`: acceso (aperto/rilevato) = valore `02`, spento = `00`. Attributi: `raw_state` (valore grezzo), `settori`.
- `alarm_control_panel.*sistema*`: `disarmed`, `armed_away`; con altri valori (per esempio solo alcuni settori inseriti dall'app) mostra **armed_custom_bypass** e l'attributo `stato_grezzo`. Attributo `sessioni_aperte`.
- `switch.elkron_mp500_connessione`: acceso = integrazione collegata; spento = in pausa per pagina web/app.

## Inserimento e disinserimento

Si usa il comando TCP di inserimento/disinserimento totale della centrale. **Inserimento e disinserimento totali sono verificati su una centrale MP500/8 reale** (versione 1.4.5). Dopo ogni comando l'integrazione rilegge lo stato per circa 10 secondi: se non cambia, restituisce un errore invece di far finta che sia andato a buon fine. La centrale non sempre manda una risposta di conferma al comando: per questo la prova che ha funzionato è lo stato letto subito dopo. Il comando di rete non chiede il codice utente: per evitare disinserimenti involontari imposta il **codice di disinserimento** di Home Assistant (sezione sotto) e **proteggi l'entità `Sistema`** (utenti Home Assistant, automazioni e dashboard) come proteggeresti il tastierino.

## Limiti noti

- Provata solo su **MP500/8 con IT500WEB** (firmware `it500web 2.0.170615`): lettura degli ingressi, stato, inserimento e disinserimento totali sono verificati su questo impianto. Altri modelli, firmware o impianti non sono verificati.
- **Codice impianto diverso da quello di fabbrica:** il codice impianto è inviato anche nel frame TCP di apertura sessione. Con il valore di fabbrica il frame è identico a quello catturato; con altri valori segue lo stesso formato ma **non è stato verificato** su una centrale reale. Se non funziona, apri una segnalazione.
- **Inserimento totale** = frame verificato con tutti i settori (maschera `ff 00`). Impianti con più di 8 settori potrebbero comportarsi diversamente.
- Valori di ingresso diversi da `00` e `02` (per esempio ingresso escluso, manomissione, allarme) non sono noti: guarda `raw_state` e segnalali.
- Nelle prove sul mio impianto due ingressi (una porta doppia e un EIR wireless) non hanno mostrato variazioni di stato nei byte letti: la corrispondenza fra alcuni sensori wireless e ingressi potrebbe non essere diretta.
- La centrale accetta un solo accesso web alla volta: per pagina web, app Android o Hi-Connect spegni prima l'interruttore `Connessione centrale` (riprende da solo dopo 15 minuti).
- Il protocollo non è documentato: un aggiornamento firmware del modulo può cambiarlo.

## Sicurezza

- Utente e password del Web Server **non vengono salvati**.
- Codice impianto e codice tecnico sono salvati nella configurazione di Home Assistant (servono a ogni riconnessione). I codici di fabbrica sono noti: cambiali sulla centrale se possibile.
- Non incollare mai password o codici in segnalazioni, log o catture di rete pubbliche.

## Risoluzione dei problemi

| Sintomo | Cosa controllare |
|---|---|
| "Connessione rifiutata" | IP e porta; il servizio TCP del modulo; riprova dopo qualche secondo. |
| "Impossibile comunicare" | Rete, IP, firewall; Web Server occupato da un altro client. |
| "Codice impianto o codice tecnico non accettati" | Codici scritti giusti? Li hai cambiati sulla centrale? |
| "Utente o password del Web Server non validi" | Stesse credenziali della pagina web del modulo. |
| Sensori sempre "non disponibili" | Log di Home Assistant (`custom_components.elkron_mp500`); `sessioni_aperte`. |
| Pagina web / app non entrano ("autenticazione fallita") | Spegni `switch.elkron_mp500_connessione`: la centrale tiene un solo accesso web alla volta. |
| Inserimento: "Stato dopo il comando non confermato" | La centrale non ha cambiato stato (es. ingressi aperti che bloccano l'inserimento): controlla sulla centrale. |

Per il log dettagliato aggiungi in `configuration.yaml`:
```yaml
logger:
  logs:
    custom_components.elkron_mp500: debug
```

## Segnalare un problema o contribuire

Apri una segnalazione indicando: modello e versione firmware (campo `cmodel` e `backend` della pagina `/sys/info.cgi` del modulo), versione di Home Assistant, il log (senza password né codici). Le catture di rete (Wireshark) sono molto utili ma **contengono credenziali**: oscurale prima di condividerle.

## Sviluppo e test

I test usano una centrale simulata e non hanno bisogno di hardware:
```
python -I tests/test_fake_panel.py      # protocollo (usa le porte di rete della centrale, in locale)
python - < tests/test_ha_parts.py       # lato Home Assistant (serve il pacchetto homeassistant)
```
Vedi `CHANGELOG.md` per la storia delle versioni. Licenza MIT.
