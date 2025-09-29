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
Per garantire la piena compatibilità con il modulo `mininet`, è richiesto di eseguire il progetto su una macchina 
**Linux nativa**. Inoltre, sono necessari i seguenti prerequisiti:

- `go`
- `python 3.8` (versioni successive hanno problemi di compatibilità con il modulo `mininet`).


### Istruzioni per l'uso

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




## Autori e contatti

| Autore              | Indirizzo email                 |
|---------------------|---------------------------------|
| Francesco Giorgione | francesco.giorgione01@gmail.com |