# SSI-5G
Questa è la repo del progetto sviluppato, sotto la supervisione del prof. Christiancarmine Esposito e del dott. 
Biagio Boi, durante la mia attività di Tesi Magistrale presso l'Università degli Studi di Salerno.


## Struttura
La repo fornisce l'implementazione di una Cloud RAN emulata, in cui i dispositivi utente
(_user equipment_, UE) si autenticano presso il core della rete tramite un meccanismo basato su **Self-Sovereign 
Identity (SSI).** La successiva autorizzazione, eseguita per il tramite di un server di autorizzazione (AS), consente
agli UE di ottenere l'accesso a un network slice. Al fine di evitare che le credenziali verificabili (VC) siano emesse
da un _Single Point of Failure and Vulnerability_, abbiamo modificato il paradigma SSI classico, facendo in modo che sia
un consorzio di multipli issuer fidati, mediante un protocollo di **threshold signature**, a firmare e rilasciare le VC.


Lo schema delle VC utilizzate è rapperesentato nella tabella seguente.

| expirationDate | isolationLevel | maxPing | minThroughputMbps | plmnId | uptimePercentage | 
|----------------|----------------|---------|-------------------|--------|------------------|
|                |                |         |                   |        |                  |    

Il campo `expirationDate` indica il periodo di validità della credenziale. Il campo `plmnId` identifica l'operatore
(_Mobile Network Operator_, MNO) con cui l'UE ha sottoscritto un contratto di abbonamento. I restanti campi 
individuano gli attributi di Quality of Service (QoS) garantiti all'UE dall'abbonamento sottoscritto.

Il progetto si compone dei seguenti moduli.

- `/src/mininet`: emula la C-RAN nella quale è stato implementato il meccanismo di autenticazione e autorizzazione.
- `/src/ssi`: fornisce il meccanismo SSI di scambio e verifica delle credenziali.
- `/src/tss`: si occupa dell'emissione delle VC, firmate tramite un protocollo di threshold signature.

A sua volta, il modullo `ssi` fornisce i seguenti agenti.

- `/src/ssi/user.py`: implementa l'UE (_holder_ del paradigma SSI), che fornisce la propria VC per richiedere l'accesso a una risorsa di rete.
- `/src/ssi/verifier.py`: implementa la _Central Unit_ (CU, i.e. _verifier_ del paradigma SSI), che identifica l'UE sulla base della credenziale da questi fornita.
- `/src/ssi/authz_server.py`: implementa il server che, completata l'autenticazione, si occupa di autorizzare l'accesso allre risorse richieste.



## Setup

È disponibile un'immagine Docker che contiene già tutti i prerequisiti (vedi
[Esecuzione in Docker](#esecuzione-in-docker)); in alternativa, il progetto può essere eseguito
direttamente sull'host seguendo le istruzioni sottostanti.

Per garantire la piena compatibilità con il modulo `mininet`, è richiesto di eseguire il progetto su una macchina 
**Linux nativa**. Inoltre, sono necessari i seguenti prerequisiti:

- `go`
- `python 3.8` (versioni successive hanno problemi di compatibilità con il modulo `mininet`).


### Istruzioni per l'esecuzione

1. Assegnare valori significativi alle variabili d'ambiente definite nel file `.env`. La versione fornita dalla repo
riporta valori esemplificativi.

2. Nella root directory del progetto, creare un ambiente virtuale.
```
python3.8 -m venv venv
```

3. Attivare l'ambiente virtuale creato.
```
source venv/bin/activate
```

4. Dalla root directory del progetto, installare le dipendenze.
```
pip install -r requirements.txt
```

5. Nella directory `/src/tss`, eseguire l'emissione della credenziale verificabile.
```
python3 issuer.py
```

6. Nella directory `/src/ssi`, costruire gli input file degli agenti SSI e dell'AS.
```
python3 init_json.py
```

7. **(Opzionale)** Nella directory `/src/ssi/input/certs`, sostituire i certificati TLS
forniti come esempio.


8. Nella directory `/src/mininet`, avviare il controller SDN.
```
./start-ryu.sh
```

9. In un nuovo terminale, dalla root directory del progetto, avviare (con privilegi elevati) la C-RAN. 
In automatico, saranno eseguiti i processi di autenticazione ed autorizzazione, i cui
file di log saranno salvati in `/src/mininet/logs`.
```
sudo venv/bin/python3.8 ./src/mininet/net.py
```


### Esperimento: impatto della latenza tra issuer

Per valutare l'effetto della latenza di rete tra gli issuer del consorzio TSS sul tempo di
emissione della VC, è disponibile una topologia Mininet dedicata (`/src/mininet/net_issuers.py`)
che emula ciascun issuer come host di rete indipendente, collegato a uno switch condiviso
tramite un link a latenza configurabile (modello "edge-delay": la RTT tra due issuer qualsiasi
è pari a 2×L). Per ogni combinazione di numero di issuer (`ISSUER_N_LIST`) e latenza
(`ISSUER_LATENCIES_MS`) definita nel file `.env`, lo script avvia i nodi Go del protocollo FROST
sugli host Mininet e orchestra il processo di key generation e firma tramite
`/src/tss/issuer_mininet.py`, salvando i tempi di esecuzione in `ISSUER_LATENCY_RESULTS_CSV`.

Dalla directory `/src/mininet`, con privilegi elevati:
```
sudo venv/bin/python3.8 ./net_issuers.py
```


### Esperimento: baseline single-issuer

Per quantificare l'overhead introdotto dalla firma a soglia rispetto al modello tradizionale
(un singolo issuer, single point of failure), è disponibile `/src/tss/issuer_baseline.py`, che
genera una singola coppia di chiavi Ed25519 e firma direttamente la VC (nessun protocollo
threshold, nessuna comunicazione peer-to-peer). Il messaggio firmato è costruito con la stessa
funzione (`vc_message.py`) usata dallo schema a soglia, per un confronto sullo stesso payload.
Poiché una singola firma Ed25519 richiede tempi dell'ordine delle decine di microsecondi (sotto
la risoluzione/rumore del timer di wall-clock), il tempo riportato è una media su più ripetizioni
(default 1000, configurabile con `--runs`).

Dalla directory `/src/tss`:
```
python3 issuer_baseline.py
```
Il risultato viene accodato in `./logs/baseline_results.csv` con lo stesso schema
(`n_signers,latency_ms,time`) del file prodotto dall'esperimento di latenza, cosicché
`plot_latency.py --baseline_csv logs/baseline_results.csv` lo sovrapponga automaticamente
come linea di riferimento orizzontale.


### Esperimento: scalabilità su UE concorrenti

Il Network SSI Verifier originale gestiva una sessione UE alla volta (socket ZMQ REP): una
seconda connessione in arrivo mentre la prima era ancora in corso ne avrebbe corrotto lo stato
protocollare, poiché i messaggi si sarebbero interfogliati sullo stesso socket. Il verifier è
stato quindi esteso a un socket ZMQ ROUTER (`communication.ConcurrentVerifierSocket`) che
demultiplessa le sessioni per identità e ne gestisce una per thread (`verifier.handle_ue`);
analogamente l'Authorization Server usa ora `ThreadingHTTPServer` con backlog aumentato invece
del server single-threaded originale. Questo consente di misurare la scalabilità reale del
sistema (tasso di successo, throughput, latenza) al crescere del numero di UE che si autenticano
concorrentemente, anziché limitarsi a ripetere la registrazione di un singolo UE.

Lo script `/src/mininet/net_scalability.py` avvia M UE Mininet concorrenti contro un'unica coppia
verifier/authz-server, per ciascun valore di M in `SCALABILITY_UE_LIST`, salvando in
`SCALABILITY_RESULTS_CSV` tasso di successo, throughput e latenza media/p95.

Dalla directory `/src/mininet`, con privilegi elevati (richiede il controller SDN già avviato):
```
sudo venv/bin/python3.8 ./net_scalability.py
python3 plot_scalability.py --csv logs/scalability_results.csv
```

**Nota metodologica**: tutti gli M UE condividono la stessa coppia di credenziali (`user_input.json`
è generato una sola volta da `init_json.py`), quindi l'esperimento misura la capacità del sistema
di servire sessioni concorrenti con credenziali valide, non l'eterogeneità di una popolazione di
identità distinte.


### Esperimento: testbed reale (non emulato)

Gli esperimenti precedenti girano su Mininet, un framework di emulazione SDN: per verificare che
i risultati non siano un artefatto dell'emulazione (link virtuali, forwarding via Open vSwitch),
`/docker/run_testbed.sh` dispiega ogni componente (consorzio issuer, Network SSI Verifier,
Authorization Server, UE) come **container Docker separati su una rete bridge reale**, con
namespace di rete indipendenti veri e forwarding via veth/bridge/iptables del kernel Linux,
anziché tramite l'emulatore Mininet. È lo stesso genere di deployment containerizzato con cui le
funzioni di rete di una Cloud RAN verrebbero effettivamente eseguite in produzione.

```
./docker/run_testbed.sh [N_ISSUER]   # default 3
```

Lo script compila il nodo TSS (in `node_testbed`, per non toccare il binario `node` tracciato in
git), avvia N container issuer, orchestra keygen e firma a soglia (`issuer_docker.py`), genera gli
input SSI/authz, avvia i container verifier e authz-server, esegue un UE one-shot contro di essi e
stampa i log rilevanti, effettuando poi il teardown completo.

**Risultato di validazione**: il tempo end-to-end del solo handshake SSI misurato su questo
testbed reale (~11-13ms) è coerente con (anzi inferiore a) quello misurato su Mininet nel paper di
conferenza (Tabella I, 70-210ms) — l'overhead aggiuntivo di Mininet è quindi dovuto al percorso di
forwarding OVS/tc-netem dell'emulatore, non al protocollo stesso; i numeri riportati con Mininet
risultano quindi una stima se mai conservativa (pessimistica) delle prestazioni reali.

Costruire questo testbed ha inoltre fatto emergere due bug reali, mascherati fino ad ora dal fatto
che Mininet termina forzatamente tutti i processi al teardown invece di lasciarli uscire
naturalmente: (1) i processi di monitoraggio RAM (`multiprocessing.Process`) non erano demoni,
causando un deadlock quando un processo doveva terminare autonomamente; (2) nel gestore
d'eccezione dell'authorization server il corpo della risposta HTTP veniva scritto prima di
`end_headers()`, corrompendo il framing HTTP in caso di errore. Entrambi sono stati corretti.


### Esperimento: testbed 5G SA reale (Open5GS + UERANSIM)

Oltre al testbed containerizzato sopra (che valida solo che i tempi non siano un artefatto di
Mininet), `/docker/5gc_testbed/` documenta come validare il lavoro su un **5G Core e RAN reali,
conformi 3GPP** (Open5GS + UERANSIM), rispondendo direttamente alla richiesta di alcuni revisori
di una valutazione basata su uno stack 5G realistico. Vedi `/docker/5gc_testbed/README.md` per le
istruzioni complete e `example_ue_registration.md` per l'evidenza di una registrazione UE, sessione
PDU e connettività dati riuscite end-to-end.

Il 5G Core esegue la propria autenticazione primaria nativa (5G-AKA); il meccanismo SSI di questo
progetto non è stato integrato a livello di AMF (richiederebbe modifiche a codice Go/C di terze
parti che non manteniamo), ma è posizionato concettualmente come livello di autorizzazione
aggiuntivo per l'accesso allo slice, complementare all'autenticazione 5G-AKA anziché sostitutivo.

`/docker/5gc_testbed/measure_overhead.sh` misura l'overhead introdotto dal meccanismo SSI rispetto
alla sola registrazione 5G-AKA nativa (latenza, volume di segnalazione, footprint RAM), usando i
timestamp di protocollo (non il tempo delle invocazioni Docker, dominato da rumore di startup dei
container). Risultato riassunto in `overhead_report.md`: l'autorizzazione SSI aggiunge ~19ms,
circa l'8% in più rispetto ai ~230ms della registrazione 5G nativa.


## Esecuzione in Docker

L'immagine Docker fornita (`Dockerfile`) incapsula tutti i prerequisiti (Python 3.8, Go, Mininet,
Open vSwitch) e viene usata per eseguire sia la C-RAN completa (`net.py`) sia l'esperimento di
latenza tra issuer (`net_issuers.py`).

**Prerequisiti sull'host** (non eliminabili containerizzando, perché Mininet crea namespace di
rete e usa Open vSwitch, che dipendono dal kernel condiviso con l'host):
- i moduli kernel `openvswitch` e `sch_netem` caricati (`sudo modprobe openvswitch sch_netem`);
- il container deve girare con `--privileged` (o quantomeno `--cap-add=NET_ADMIN --cap-add=SYS_ADMIN`).

### Build
```
docker build -t ssi-5g .
```

### Esecuzione interattiva
```
cp .env.docker.example .env.docker   # personalizzare i valori se necessario
docker run --rm -it --privileged --cap-add=NET_ADMIN --cap-add=SYS_ADMIN \
  -v /lib/modules:/lib/modules:ro \
  --env-file .env.docker \
  ssi-5g
```
In alternativa, con `docker compose up -d && docker compose exec ssi-5g bash` (richiede prima
`cp .env.docker.example .env.docker`).

All'interno del container il progetto si trova in `/opt/ssi-5g` con il venv già pronto e attivo
(`source venv/bin/activate` è eseguito automaticamente dall'entrypoint); da lì si eseguono gli
stessi comandi descritti nelle sezioni precedenti (es. `python3.8 src/tss/issuer.py --n_signers N`,
`python3.8 src/mininet/net_issuers.py`, `python3.8 src/mininet/net.py` dopo aver avviato
`start-ryu.sh` in background).

**Nota**: il file `.env` tracciato nel repository contiene path assoluti pensati per
un'esecuzione sull'host (es. `/home/.../venv/bin/python3.8`); `.env.docker.example` fornisce
gli equivalenti path in-container (`/opt/ssi-5g/...`) e va usato al posto di `.env` quando si
lavora in Docker.


### File .env
`SUB_PLMN_ID`: valore (stringa) di `plmnId` da inserire nella VC generata

`SUB_MAX_PING`: valore (intero) di `maxPing` da inserire nella VC generata

`SUB_MIN_THORUGHPUT_MBPS`: valore (intero) di `minThroughputMbps` da inserire nella VC generata

`SUB_UPTIME_PERCENTAGE`: valore (intero) di `uptimePercentage` da inserire nella VC generata

`SUB_ISOLATION_LEVEL`: valore (intero) di `isolationLevel` da inserire nella VC generata

`REQ_SITE_ID`: identificativo (intero) del pool di risorse in cui si trova il network slice a cui l'UE vuole accedere

`REQ_SLICE_ID` identificativo (intero) del network slice a cui l'UE vuole accedere

`N_BBUs`: numero di BBU decentralizzate da inserire nella C-RAN emulata

`N_RRHs`: numero di RRH da inserire nella C-RAN emulata

`N_UEs`: numero di UE da inserire nella C-RAN emulata

`ISSUER_BASE_PORT`: numero di porta a partire dal quale istanziare gli _n_ processi firmatari

`CENTRAL_BBU_IP_1`: indirizzo IP della prima interfaccia di rete della CU

`CENTRAL_BBU_IP_2`: indirizzo IP della seconda interfaccia di rete della CU

`AUTHZ_SERVER_IP`: indirizzo IP del server di autorizzazione

`AUTHZ_SERVER_PORT`: numero di porta del server di autorizzazione

`MININET_INTERPRETER_PATH`: path dell'interprete Python da usare nel modulo `mininet` (default `/venv/bin/python3.8`)

`SSI_INTERPRETER_PATH`: path dell'interprete Python da usare nel modulo `ssi` (default `/venv/bin/python3.8`)

`SSI_USER_PATH`: path dello script `user.py` (default `/src/ssi/user.py`)

`SSI_VERIFIER_PATH`: path dello script `verifier.py` (default `/src/ssi/verifier.py`)

`SSI_AUTHZ_SERVER_PATH`: path dello script `authz_server.py` (default `/src/ssi/authz_server.py`)

`VERIFIER_PORT`: porta del verifier

`SSI_INPUT_FOLDER`: path della cartella contenente gli input file per gli agenti SSI (default `/src/ssi/inputs`)

`ISSUER_N_LIST`: lista (separata da virgole) dei valori di N (numero di issuer) da testare nell'esperimento di latenza (default `5,10,20`)

`ISSUER_LATENCIES_MS`: lista (separata da virgole) delle latenze di link (in ms) da testare tra gli issuer nella topologia Mininet dedicata (default `0,5,20,50,100`)

`ISSUER_LATENCY_RESULTS_CSV`: path del file CSV in cui salvare i risultati dell'esperimento di latenza tra issuer (default `../tss/logs/latency_results.csv`)




## Autori e contatti

| Autore              | Indirizzo email                 |
|---------------------|---------------------------------|
| Francesco Giorgione | francesco.giorgione01@gmail.com |