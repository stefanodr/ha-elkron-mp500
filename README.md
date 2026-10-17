# Elkron MP500 (IT500WEB) per Home Assistant

Integrazione personalizzata, **locale** (nessun cloud), per le centrali antifurto **Elkron MP500** con il modulo di rete **IT500WEB**. Mostra gli ingressi della centrale come sensori, mostra lo stato dell'impianto e permette di **inserire e disinserire tutto l'impianto** da Home Assistant.

> **English, in short:** local (no cloud) custom integration for Elkron MP500 alarm panels with the IT500WEB network module. Input sensors, panel state and total arm/disarm. Names are read from the panel automatically if you give the Web Server login once (it is not stored). Install via HACS (custom repository) or by copying `custom_components/elkron_mp500`. Not affiliated with Elkron/Urmet. Tested only on an MP500/8; see "Limiti noti".

Progetto indipendente: **non è affiliato né approvato da Elkron/Urmet**. Il protocollo del modulo IT500WEB non è pubblico: l'integrazione è basata sull'analisi del traffico di rete di Hi-Connect e del Web Server. Usala a tuo rischio e, prima di fidarti dei comandi, provali con l'impianto sotto controllo.

## Cosa fa

- **Sensori degli ingressi.** Un sensore binario per ogni ingresso che la centrale riporta. Il numero non è fisso: viene letto dalla centrale (4, 8, 16... ingressi, cablati e wireless), quindi si adatta al tuo impianto.
- **Nomi.** Se fornisci una sola volta utente e password del Web Server, l'integrazione legge i nomi degli ingressi e dei settori dalla centrale. Se un ingresso non ha nome nella centrale, o non dai le credenziali, si chiama semplicemente **Ingresso 1, Ingresso 2, ...** e puoi rinominarlo a mano dalle opzioni.
- **Settori.** Ogni sensore ha l'attributo `settori` con i settori a cui appartiene (se letti dalla centrale).
- **Entità `Sistema`** (pannello di allarme): `Disattivato` / `Fuori casa` (inserito) e i comandi **inserisci** e **disinserisci**. In questa versione si inserisce e disinserisce **sempre tutto l'impianto**.
- **Locale.** Nessun account o cloud. Il modulo deve essere raggiungibile in rete dalla macchina di Home Assistant.

## Cosa NON fa (per ora)

- Inserimento **parziale** o per singolo settore, scenari e uscite.
- Storico eventi della centrale.
- Il codice utente dell'allarme non è richiesto né usato per inserire/disinserire (vedi "Sicurezza").

## Requisiti

- Centrale Elkron MP500 con modulo IT500WEB collegato alla rete, con **IP fisso** (consigliato: prenotazione sul router).
- Home Assistant recente (provata con la 2026.10; i test automatici con la 2026.2).
- Il servizio TCP del modulo sulla porta `5555` (predefinita).

## Installazione

### Con HACS (consigliata)
1. HACS → menu a tre puntini → **Repository personalizzati**.
2. Incolla l'indirizzo di questo repository, categoria **Integrazione** → Aggiungi.
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
| Porta TCP | `5555` (lasciala se non l'hai cambiata). |
| Intervallo di polling | Ogni quanti secondi leggere lo stato. 10 s va bene; per i sensori di movimento 1–2 s. Minimo 1, massimo 300. |
| Utente / Password Web Server | **Facoltativi.** Sono lo stesso utente e la stessa password con cui entri nella pagina web del modulo. Servono **una sola volta** per leggere i nomi e **non vengono salvati**. Lasciali vuoti per avere "Ingresso N". |
| Codice impianto | **Facoltativo.** 8 cifre. Lascia il valore di fabbrica `55555555` se non l'hai cambiato. |
| Codice tecnico | **Facoltativo.** Lascia il valore di fabbrica `000000` se non l'hai cambiato. |

3. Conferma. Se i codici non sono accettati dalla centrale vedrai l'errore "Codice impianto o codice tecnico non accettati".

### Cambiare nomi, tipi, intervallo (opzioni)
**Impostazioni → Dispositivi e servizi → Elkron MP500 → Configura:**
- **Nome ingresso N**: il nome che preferisci (ha la precedenza su quello della centrale).
- **Tipo ingresso N**: *Apertura* (generico), *Porta*, *Finestra* o *Movimento*. Decide come si legge lo stato: Aperto/Chiuso oppure Rilevato/Non rilevato, e l'icona.
- **Rileggi i nomi dalla centrale**: spunta e inserisci utente e password del Web Server. I nomi scritti a mano vengono sostituiti da quelli della centrale.

### Se hai cambiato i codici di fabbrica
Il *codice impianto* e il *codice tecnico* sono quelli impostati sulla centrale (li usa anche Hi-Connect per collegarsi). Se la configurazione li rifiuta, controlla di averli scritti giusti. Per cambiarli dopo la configurazione, elimina la voce e aggiungila di nuovo.

## Come funziona la convivenza con app, Web Server e Hi-Connect

La centrale accetta **un solo accesso web alla volta**. Per questo l'integrazione:
- legge lo stato dal canale TCP del modulo e **non tiene aperta una sessione web**: app, pagina web e Hi-Connect restano utilizzabili mentre Home Assistant è attivo;
- fa un login web solo per leggere i nomi, dura meno di un secondo e viene chiuso subito;
- se il Web Server è occupato mentre leggi i nomi, vedrai "Il Web Server è occupato": riprova tra poco.

Ogni apertura di sessione viene scritta nello storico eventi della centrale (utente TECNICO). L'entità `Sistema` ha l'attributo **`sessioni_aperte`**: deve restare vicino a 1. Se cresce di continuo, la connessione cade e viene riaperta: aprire una segnalazione con il log.

## Gli ingressi: cablati, wireless e sensori

La centrale ragiona per **ingressi**, non per singole porte o finestre. Una MP500/8 ha **8 ingressi cablati**, e a ciascuno si possono collegare più contatti in serie (per esempio più porte e finestre sullo stesso ingresso). I sensori **wireless** (per esempio un EIR) si aggiungono come ingressi ulteriori. Home Assistant vede quindi **un sensore per ingresso**, non uno per ogni finestra o porta fisica: se un ingresso raggruppa tre finestre, ti dirà che "qualcosa" su quell'ingresso è aperto.

## Entità create

- `binary_sensor.*ingresso_N*`: acceso (aperto/rilevato) = valore `02`, spento = `00`. Attributi: `raw_state` (valore grezzo), `settori`.
- `alarm_control_panel.*sistema*`: `disarmed`, `armed_away`; con altri valori (per esempio solo alcuni settori inseriti dall'app) mostra **armed_custom_bypass** e l'attributo `stato_grezzo`. Attributo `sessioni_aperte`.

## Inserimento e disinserimento

Si usa il comando TCP di inserimento/disinserimento totale della centrale. Dopo ogni comando l'integrazione rilegge lo stato: se non è cambiato, restituisce un errore invece di far finta che sia andato a buon fine. Il comando non chiede il codice utente: **proteggi l'entità `Sistema`** (utenti Home Assistant, automazioni e dashboard) come proteggeresti il tastierino.

## Limiti noti

- Provata solo su **MP500/8 con IT500WEB** (firmware `it500web 2.0.170615`). Altri modelli, firmware o impianti non sono verificati.
- **Codice impianto diverso da `55555555`:** il codice impianto è inviato anche nel frame TCP di apertura sessione. Con il valore di fabbrica il frame è identico a quello catturato; con altri valori segue lo stesso formato ma **non è stato verificato** su una centrale reale. Se non funziona, apri una segnalazione.
- **Inserimento totale** = frame verificato con tutti i settori (maschera `ff 00`). Impianti con più di 8 settori potrebbero comportarsi diversamente.
- Valori di ingresso diversi da `00` e `02` (per esempio ingresso escluso, manomissione, allarme) non sono noti: guarda `raw_state` e segnalali.
- Nelle prove sul mio impianto due ingressi (una porta doppia e un EIR wireless) non hanno mostrato variazioni di stato nei byte letti: la corrispondenza fra alcuni sensori wireless e ingressi potrebbe non essere diretta.
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
python -I tests/test_fake_panel.py      # protocollo (usa le porte 80 e 5555 in locale)
python - < tests/test_ha_parts.py       # lato Home Assistant (serve il pacchetto homeassistant)
```
Vedi `CHANGELOG.md` per la storia delle versioni. Licenza MIT.
