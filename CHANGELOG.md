# Changelog

## 1.6.0
- **Una sola sessione, tenuta aperta** (come Hi-Connect), invece di un login a ogni lettura: le versioni 1.5.6-1.5.8 aprivano centinaia di sessioni al giorno e la centrale alla fine smetteva di rispondere sul web. Intervallo di lettura di nuovo 10 s (minimo 1, massimo 300).
- **Interruttore `switch.elkron_mp500_connessione`.** La centrale accetta un solo accesso web alla volta: per usare pagina web o app Android spegni l'interruttore, l'integrazione esce dal login e resta ferma; riprende da sola dopo 15 minuti o quando lo riaccendi. Nella card di esempio la spia RETE è questo interruttore (verde = collegata, ambra = in pausa).
- Prima di fare il login l'integrazione controlla se qualcuno è già dentro (`sesstate`): in quel caso non prova ad entrare e non allunga le attese.
- Inserimento e disinserimento usano la sessione già aperta, senza un nuovo login.
- Se la lettura fallisce, l'ultimo stato valido resta per 90 secondi, poi le entità diventano non disponibili.
- Contatore dei login fatti dall'integrazione dall'ultima ripartenza della centrale (attributi `login_totali` e `contatore_dal` dell'interruttore), per capire il limite reale.

## 1.5.8 (prova)
- **Corretto un login lasciato aperto.** Se l'accesso riusciva ma un passo successivo veniva rifiutato (per esempio il cambio di modalità), l'integrazione chiudeva la connessione senza uscire dal login. La centrale lo teneva per circa due minuti e rifiutava gli accessi successivi, anche quelli dell'integrazione stessa, con attese sempre più lunghe. Ora esce sempre dal login.
- Le letture rimandate per l'attesa dopo un errore sono scritte nel registro di debug e non più tra gli avvisi.

## 1.5.7 (prova)
- Inserimento e disinserimento ignorano l'attesa dopo un errore e, se un altro accesso (pagina web, app, Hi-Connect) occupa la centrale, riprovano una volta dopo 5 secondi.
- Messaggio più chiaro quando la centrale rifiuta l'accesso: indica che può essere aperto un altro accesso.

## 1.5.6
- **Una sessione completa a ogni lettura.** La centrale accetta un solo accesso web alla volta e chiude la connessione TCP circa un minuto dopo l'uscita dal login, quindi tenerla aperta non funziona (log: chiusura ogni ~60 s). Ora ogni lettura fa login, legge, chiude TCP, torna in modalità normale ed esce come Hi-Connect. Tra una lettura e l'altra pagina web, app e Hi-Connect sono liberi.
- Intervallo di lettura: predefinito 60 s, minimo 30, massimo 600 (le configurazioni più veloci vengono portate a 30).
- Dopo un accesso fallito (per esempio mentre usi Hi-Connect) l'integrazione aspetta 1, 2, 4… fino a 15 minuti prima di riprovare.
- Registro: ogni lettura fallita è segnalata con il motivo.

## 1.5.5 (esperimento)
- Il login HTTP resta aperto (con refresh ogni 10 secondi) finché la connessione TCP è in uso, come fa Hi-Connect. Con il login rilasciato la centrale chiudeva la connessione TCP circa una volta al minuto. Svantaggio da verificare: la centrale accetta un solo accesso web alla volta, quindi pagina web e app potrebbero non entrare finché l'integrazione è collegata.

## 1.5.4 (prova)
- Dopo un accesso fallito a IT500WEB (per esempio errore 404) l'integrazione aspetta 1 minuto, poi 2, 4... fino a 15 minuti prima di riprovare, invece di ripetere il login a ogni lettura.
- Keepalive TCP lasciato come nella cattura di Hi-Connect (circa 8 al secondo): ogni 3 secondi la centrale chiudeva la connessione circa una volta al minuto.
- Ogni chiusura della sessione TCP per errore è ora registrata come avviso, con il motivo e il numero di sessioni aperte, per capire perché si riapre.

## 1.5.2
- Tastierino: il codice è controllato subito e il popup si chiude senza aspettare i secondi che la centrale impiega a eseguire il comando. Un codice errato è segnalato subito; se il comando poi fallisce compare una notifica persistente.

## 1.5.1
- Tastierino a schermo per la card: servizi `elkron_mp500.keypad_press` e `elkron_mp500.keypad_submit`. Le cifre restano solo in memoria (mai nello stato o nello storico), si azzerano dopo 30 secondi e il contatore è nell'attributo `cifre_digitate`. Non serve nessun helper.
- Card di esempio pronta in `examples/dashboard_card.yaml`.

## 1.5.0
- Codice di disinserimento facoltativo a 6 cifre, scelto dall'utente in Opzioni e gestito solo da Home Assistant (la centrale non lo conosce). Salvato solo come hash PBKDF2 con salt.
- Inserimento sempre senza codice. Senza codice impostato il comportamento è invariato.
- Blocco di 5 minuti dopo 5 codici errati consecutivi.

## 1.4.5 — l'evento dopo il comando non è più necessario
- **Corretto:** sulla centrale reale, dopo inserimento o disinserimento l'evento `0x12` non arrivava, e l'integrazione dopo 8 secondi dava `TimeoutError` anche se il comando era riuscito. Ora l'evento è facoltativo (si aspetta fino a 3 s): la prova che il comando ha funzionato è lo stato letto subito dopo, che viene controllato per circa 10 secondi.
- Un evento `0x12` che arriva in ritardo viene ignorato invece di far fallire la lettura successiva.
- Test: la centrale simulata ora prova tre casi: evento puntuale, evento assente, evento in ritardo.

## 1.4.4 — correzione dell'errore dopo inserimento e disinserimento
- **Corretto:** inserire o disinserire funzionava ma Home Assistant mostrava un errore (`TimeoutError`). Dopo il comando la centrale manda un `0x16` isolato (dopo circa 0,3 s) e la risposta vera, l'evento `0x12`, circa 0,2 s più tardi (visto nella cattura di Hi-Connect). L'integrazione scambiava il `0x16` per la risposta e smetteva di aspettare. Ora ignora i `0x16` isolati e attende la risposta vera.
- Il test con la centrale simulata ora riproduce questo comportamento reale (prima rispondeva subito).

## 1.4.3 — errori di inserimento/disinserimento leggibili
- Se inserire o disinserire genera un errore, Home Assistant mostra la causa reale ("Inserimento non riuscito: ...") invece di "unknown error", e il log riporta i dettagli. Lo stato viene riletto comunque.

## 1.4.2 — id delle entità fissi e prevedibili
- Gli `entity_id` non dipendono più dal nome: `alarm_control_panel.elkron_mp500_sistema` e `binary_sensor.elkron_mp500_ingresso_1` ... `_N`. Prima erano ricavati dal nome intero (per esempio `binary_sensor.ingresso_1_ingressi_princ_pt_e_1p`) e cambiavano se rinominavi un ingresso, rompendo dashboard e automazioni.
- All'avvio le entità create dalle versioni precedenti vengono rinominate una sola volta con gli id fissi (se l'id è libero). Gli id non verranno più cambiati.

## 1.4.1 — diagnostica del rifiuto di accesso
- Il messaggio "codici non accettati" compariva con qualsiasi rifiuto della centrale, anche se la causa era un altro accesso attivo (app, Web Server, Hi-Connect). Ora il messaggio dice di controllare i codici e, se sono giusti, di chiudere gli altri accessi e aspettare 2 minuti.
- Il log di Home Assistant riporta la risposta della centrale al rifiuto (non contiene codici).

## 1.4.0 — versione pubblicabile (GitHub / HACS)
- **Codici configurabili.** Codice impianto (`plantid`) e codice tecnico (`code`) sono campi facoltativi nella configurazione (valori di fabbrica precompilati). Prima erano scritti nel codice. Il codice impianto entra anche nel frame TCP di apertura sessione (verificato solo con il valore di fabbrica).
- **Nomi automatici o "Ingresso N".** Con le credenziali del Web Server i nomi si leggono dalla centrale; altrimenti, o per ingressi senza nome, "Ingresso 1, 2, 3...". Il numero di ingressi si rileva dalla centrale.
- **Utente e password del Web Server non vengono più salvati**: servono solo per leggere i nomi (configurazione e "Rileggi i nomi"). La migrazione toglie quelli già salvati.
- **Modello letto dalla centrale** (`cmodel`) e mostrato nel dispositivo.
- **Stato allarme:** valori diversi da "tutto inserito" / "tutto disinserito" non sono più mostrati come disinserito, ma come inserimento parziale (`armed_custom_bypass`), con `stato_grezzo`.
- **Icone:** il tipo generico "Apertura" mostra porta aperta/chiusa.
- Rimossi nomi e tipi specifici dell'impianto dell'autore (migrazione da 1.0/1.2) e `single_config_entry`: si possono configurare più centrali.
- Errori più chiari: codici non accettati, codice impianto o tecnico non valido.
- File per la pubblicazione: `hacs.json`, workflow GitHub (hassfest, HACS, test), `.gitignore`, README completo.

## 1.3.2 — login web con doppio MD5
- **Corretto:** la password del Web Server va inviata come **MD5 dell'MD5** della password (32 caratteri esadecimali). Verificato dall'utente confrontando l'hash della cattura con la propria password: `md5(md5(password))` corrisponde. La 1.3.1 inviava un solo MD5 e veniva rifiutata.
- Test aggiornati: il Web Server simulato accetta solo il doppio MD5.

## 1.3.1 — correzione del login web
- **Corretto:** il login al Web Server per leggere i nomi veniva rifiutato ("Utente o password non validi") anche con credenziali giuste. Il browser non invia la password in chiaro ma come stringa esadecimale di 32 caratteri (nella cattura: `pwd` di 32 caratteri minuscoli esadecimali). Ora l'integrazione invia l'**MD5** della password. È l'ipotesi più probabile per un hash a 32 caratteri; non ho potuto leggere il codice della pagina per confermarlo.
- La password resta salvata nella configurazione di Home Assistant come l'hai scritta.
- Test: il Web Server simulato accetta solo l'MD5 e il test verifica che la password non viaggi in chiaro.

## 1.3.0 — nomi e settori letti dalla centrale
- **Nomi dalla centrale.** Con utente e password del Web Server l'integrazione fa **un solo login breve** (meno di un secondo: login, `plantstructure.cgi`, logout) e legge i nomi di ingressi e settori. Il login avviene alla configurazione e quando spunti "Rileggi i nomi dalla centrale" nelle opzioni, non a ogni avvio. Il codice a 6 cifre non serve.
- **Settori.** Ogni sensore mostra nell'attributo `settori` i settori a cui appartiene (per esempio l'ingresso 9, EIR VERANDA, è nel settore 7).
- **Priorità dei nomi:** nome scritto a mano nelle opzioni, poi nome della centrale, poi `Ingresso N`. Quando rileggi i nomi dalla centrale, i nomi scritti a mano vengono sostituiti.
- **Credenziali facoltative.** Senza utente e password tutto funziona come nella 1.2.1.
- **Stati sempre via TCP.** Letture, inserimento e disinserimento non cambiano. La 1.3.0 non tiene una sessione web aperta: gli altri dispositivi (app, web, Hi-Connect) restano liberi.
- **Diagnostica.** L'entità `Sistema` ha l'attributo `sessioni_aperte`: quante sessioni HTTP+TCP sono state aperte dall'avvio. Deve restare vicino a 1: se cresce di continuo la connessione cade e ogni login viene scritto nello storico della centrale.
- Test: `fetch_structure` contro il Web Server simulato (nomi, settori, logout, password errata, 503) e il flusso di configurazione e opzioni.

### Da verificare sul tuo impianto
- Il login web una tantum con il tuo utente.
- Dopo qualche ora, `sessioni_aperte` e quanti login TECNICO compaiono nello storico.

## 1.2.1 — tipo di ingresso (Aperto/Chiuso invece di Acceso/Spento)
- **Corretto:** nella 1.2.0 i sensori non avevano una classe dispositivo e Home Assistant li mostrava come Acceso/Spento. Ora ogni ingresso ha un **tipo** (Apertura, Porta, Finestra, Movimento) impostabile dalle opzioni: porta, finestra e apertura danno Aperto/Chiuso, movimento dà Rilevato/Non rilevato. Il tipo predefinito è Apertura.
- **Migrazione.** Il primo avvio imposta il tipo dai nomi che avevi: ingresso 7 = Porta, ingresso 9 = Movimento (EIR). Gli altri restano Apertura e si cambiano dalle opzioni. Le scelte già fatte non vengono sovrascritte.
- Test aggiornati: migrazione 2 → 3 → 4, classe dispositivo e campi delle opzioni.

## 1.2.0 — sensori creati dalla lettura della centrale
- **Ingressi dinamici.** Le entità `binary_sensor` sono create in base ai byte della risposta `0x84` (oggi 9 sulla tua MP500/8), non più da una lista fissa. Se la centrale ne riporta di più o di meno, cambia il numero di sensori dopo il ricaricamento.
- **Nomi modificabili.** Nuove opzioni dell'integrazione (Impostazioni → Dispositivi e servizi → Elkron MP500 → Configura): un campo nome per ogni ingresso. Senza nome il sensore si chiama `Ingresso N`.
- **Aggiornamento senza sorprese.** Un'installazione esistente conserva i nomi di prima: alla migrazione (versione 3 della voce) vengono copiati nelle opzioni.
- **Polling da 1 s.** L'intervallo si imposta da 1 a 300 s, anche dalle opzioni. I sensori di movimento restano aperti solo ~3 s, quindi con 10 s molti scatti non si vedono.
- **Nessuna classe dispositivo.** Il tipo (porta, movimento, ...) non è noto dal traffico: si imposta per ogni entità dalle impostazioni di Home Assistant.
- Test: `tests/test_fake_panel.py` copre ora anche risposte con 4 e 12 ingressi e il rifiuto di un frame incoerente; `tests/test_ha_parts.py` controlla migrazione, entità e opzioni con Home Assistant 2026.2.3.

### Mappatura verificata dalle catture (15/10/2026)
- Ingresso 7 = porta blindata (byte 7 a `02` per ~23 s all'apertura).
- L'ingresso 1 ha dato due impulsi di ~3 s: i sensori non sono ancora associati a tenda ed EIR veranda.
- Gli ingressi 8 e 9 non si sono mai mossi.

### Non verificato
- Il significato dei valori diversi da `00` e `02`: potrebbero essere isolato, allarme o manomissione.
- Le due parti Home Assistant sono state provate senza una istanza reale in funzione.

## 1.1.0 — inserimento/disinserimento via TCP
- **Corretto:** `arm()` e `disarm()` ora inviano il comando TCP `0x11` e non chiamano più `/sys/mode.cgi`. Quell'endpoint cambia solo il `sysmode` del modulo IT500WEB (1 a riposo, 2/3 servizio TCP) e non comanda l'allarme.
- **Corretto:** i frame `CMD_ARM` e `CMD_DISARM` erano di 15 byte (mancava un `00`); ora sono i 16 byte della cattura Hi-Connect.
- La risposta attesa al comando è `0x12` (record evento), non `0x11`.
- Dopo il comando viene riletto lo stato generale (`0x80`) fino a 6 volte; se non cambia, l'azione fallisce con un errore invece di fingere di riuscire.
- Prima di ogni comando la sessione viene riaperta con la sequenza catturata (login HTTP, mode 2/3, avvio TCP).
- Un solo lock serializza letture e comandi, così il polling non si sovrappone a un inserimento.
- Aggiunto `tests/test_fake_panel.py`: centrale simulata (HTTP + TCP) basata sulla cattura.

### Non ancora verificato su impianto reale
- Il comando è stato provato solo contro la centrale simulata. Provalo prima con l'impianto in condizioni sicure (sirena scollegata o avvisa chi è in casa).
- La logica degli ingressi e dei sensori wireless non è cambiata.
- Il payload `ff 00` del comando sembra una maschera di settori, ma non è confermato.

## 1.0.0 — release finale
- Basata sulla 0.4.4 e collaudata dall'utente sulla propria centrale Elkron MP500/8 con IT500WEB: esito positivo riferito dall'utente.
- Conservati senza modifiche il client TCP, il bootstrap HTTP e la logica/comandi dell'entità `Sistema`.
- Campo IP senza indirizzo precompilato; porta TCP predefinita.
- Documentazione d'installazione e ripristino aggiornata.
- Il codice tecnico resta quello della base 0.4.4; non è esposto come opzione configurabile in questa release.

### Limiti noti
- Il collaudo hardware è quello dell'impianto dell'utente, non una certificazione per tutti i modelli/firmware.
- La sequenza HTTP ereditata dalla 0.4.4 include richieste `/sys/mode.cgi` che possono cambiare la modalità della centrale. È stata mantenuta per preservare il comportamento collaudato.
- I nomi degli ingressi sono personalizzati per l'impianto di riferimento e non sono recuperati dinamicamente.
