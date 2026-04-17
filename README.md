# Video To Text

Pipeline Python per:

- scaricare video da YouTube
- estrarre frame significativi dal video
- eseguire OCR sui frame
- ricostruire domande e risposte a partire dal testo OCR
- generare output strutturati in JSON e Markdown
- applicare un primo passaggio di cleanup sul testo estratto

Il progetto e' pensato per contenuti video in cui le slide o le schermate mostrano:

- numero domanda
- testo della domanda
- opzioni `A`, `B`, `C`, `D`
- soluzione
- spiegazione

Un caso d'uso tipico e' l'analisi di video di quiz o exam dumps, dove ogni domanda appare in un frame e la soluzione nel frame successivo.

## Obiettivo

L'obiettivo non e' solo estrarre testo grezzo dal video, ma arrivare a un formato leggibile e strutturato che possa essere ulteriormente ripulito, revisionato o passato a un LLM.

La pipeline attuale produce diversi livelli di output:

1. `frames/`: immagini estratte dal video
2. `text/`: OCR grezzo, un file `.txt` per frame
3. `output/<video>/...json`: dati strutturati domanda/risposta
4. `output/<video>/...md`: documento leggibile in Markdown
5. `output/<video>/...cleaned.*`: variante con cleanup euristico del testo

## Struttura Del Progetto

```text
video_to_text/
├── app/
│   ├── document_builder.py
│   ├── downloader.py
│   ├── frame_extractor.py
│   ├── models.py
│   ├── ocr_retry.py
│   ├── path_utils.py
│   ├── text_cleaner.py
│   └── text_extractor.py
├── video/
├── frames/
├── text/
├── output/
├── main.py
├── extract_text.py
├── build_document.py
├── clean_document.py
├── pyproject.toml
├── uv.lock
└── README.md
```

## Componenti Principali

### `main.py`

Entry point interattivo del progetto.

Funzioni:

- chiede in input un link YouTube
- scarica il video nella cartella `video/`
- estrae i frame e li salva in `frames/<nome_video>/`

### `app/downloader.py`

Gestisce il download da YouTube tramite `yt-dlp`.

Caratteristiche:

- salva il file video in `video/`
- usa un template di nome basato su titolo e id YouTube
- forza l'output in `mp4` quando possibile

### `app/frame_extractor.py`

Gestisce l'estrazione dei frame dal video con `OpenCV`.

Caratteristiche:

- legge FPS e metadati direttamente dal video
- salva 1 frame ogni `N` secondi
- evita frame duplicati
- supporta un filtro opzionale basato sul cambiamento di scena
- salva i frame con timestamp nel nome file

Esempio:

```text
frames/jan26_q1_35/frame_00-01-32.jpg
```

### `app/text_extractor.py`

Esegue OCR sui frame tramite `rapidocr-onnxruntime`.

Caratteristiche:

- legge tutti i frame in `frames/<video_name>/`
- salva un `.txt` per ogni frame in `text/<video_name>/`
- mantiene il mapping 1:1 tra frame e file di testo

### `app/document_builder.py`

Ricostruisce record strutturati a partire dai file OCR.

Ogni record contiene:

- `question_number`
- `question`
- `options`
- `solution`
- `solution_text`
- `explanation`
- `source_question_file`
- `source_answer_file`
- `validation_warnings`
- `retry_applied`
- `retry_details`

Il builder assume che i file OCR siano ordinati a coppie:

- file 1: domanda + opzioni
- file 2: answer + explanation

### `app/ocr_retry.py`

Gestisce i retry OCR per i casi problematici.

Serve quando il parser trova problemi come:

- opzioni mancanti
- domanda incompleta
- OCR troppo rumoroso su una porzione del frame

Strategia:

- rilegge il frame immagine originale
- prova piu' varianti dell'immagine
- sceglie il risultato OCR migliore

Varianti usate:

- frame completo
- crop inferiore
- grayscale 2x
- threshold + resize
- crop mirati per area domanda/opzioni

### `app/text_cleaner.py`

Applica un primo cleanup euristico sul JSON strutturato.

Attenzione:

- migliora leggermente la leggibilita'
- non garantisce testo “editoriale”
- non sostituisce un vero passaggio di normalizzazione con LLM

## Requisiti

- Python `>= 3.13`
- `uv`

Dipendenze principali:

- `opencv-python`
- `yt-dlp`
- `rapidocr-onnxruntime`
- `wordninja`

## Setup

### 1. Creazione Del Virtual Environment

```powershell
uv venv .venv
```

### 2. Installazione Dipendenze

Se il progetto ha gia' `pyproject.toml` e `uv.lock`:

```powershell
uv sync
```

Oppure, se vuoi installare manualmente:

```powershell
uv add opencv-python yt-dlp rapidocr-onnxruntime wordninja
```

### 3. Attivazione Ambiente

PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

In alternativa puoi sempre eseguire i comandi direttamente con:

```powershell
.venv\Scripts\python.exe <script>.py
```

## Flusso End-To-End

### Step 1. Download Del Video E Estrazione Frame

```powershell
.venv\Scripts\python.exe main.py
```

Il programma:

1. chiede il link YouTube
2. scarica il video in `video/`
3. estrae i frame in `frames/<nome_video>/`

### Step 2. OCR Dei Frame

```powershell
.venv\Scripts\python.exe extract_text.py jan26_q1_35
```

Output:

- `text/jan26_q1_35/frame_00-00-00.txt`
- `text/jan26_q1_35/frame_00-00-17.txt`
- ecc.

### Step 3. Costruzione Documento Strutturato

```powershell
.venv\Scripts\python.exe build_document.py jan26_q1_35
```

Output:

- `output/jan26_q1_35/jan26_q1_35.json`
- `output/jan26_q1_35/jan26_q1_35.md`

### Step 4. Cleanup Del Documento

```powershell
.venv\Scripts\python.exe clean_document.py jan26_q1_35
```

Output:

- `output/jan26_q1_35/jan26_q1_35.cleaned.json`
- `output/jan26_q1_35/jan26_q1_35.cleaned.md`

## Formato Degli Output

### OCR Grezzo

Ogni frame genera un file `.txt`.

Esempio:

```text
text/jan26_q1_35/frame_00-01-15.txt
text/jan26_q1_35/frame_00-01-32.txt
```

Spesso i file sono in coppie:

- primo file: domanda
- secondo file: risposta + spiegazione

### JSON Strutturato

Esempio semplificato:

```json
{
  "question_number": 10,
  "question": "A company's BigQuery ML XGBoost model shows poor inference performance from skewed training labels. What is the best remedy?",
  "options": {
    "A": "Use class weighting with the CLASS_WEIGHTS option in CREATE MODEL",
    "B": "Downsample majority classes manually outside BigQuery ML",
    "C": "Increase tree depth to improve splitting on minority classes",
    "D": "Remove underrepresented classes to stabilize the model's distribution"
  },
  "solution": "A",
  "solution_text": "Use class weighting with the CLASS_WEIGHTS option in CREATE MODEL",
  "explanation": "BigQuery ML supports built-in class weighting for handling imbalanced classification tasks.",
  "source_question_file": "frame_00-03-45.txt#gray2x",
  "source_answer_file": "frame_00-04-02.txt",
  "validation_warnings": [],
  "retry_applied": true,
  "retry_details": {
    "question_retry": {
      "variant": "gray2x",
      "filled_options": 4
    }
  }
}
```

### Markdown

Il Markdown e' utile per:

- lettura veloce
- review manuale
- esportazione futura in DOCX o PDF

## Retry OCR

Uno dei problemi classici dell'OCR su video e' che alcune opzioni non vengano lette correttamente.

Esempio reale:

- la domanda 10 del dataset `jan26_q1_35` inizialmente non conteneva l'opzione `B`
- il retry OCR ha recuperato l'opzione rielaborando il frame con una variante `gray2x`

Questo comportamento e' visibile direttamente nei campi:

- `retry_applied`
- `retry_details`
- `validation_warnings`

## Configurazione

I parametri principali sono definiti in [app/models.py](./app/models.py).

Valori importanti:

- cartella video: `video/`
- cartella frame: `frames/`
- cartella testo OCR: `text/`
- cartella output finale: `output/`
- intervallo estrazione frame: default `1.0` secondo
- soglia duplicati frame
- soglia scene change
- soglia minima confidenza OCR

## Convenzioni Di Naming

### Video

I video vengono salvati in `video/`.

Esempi:

- `video/jan26_q1_35.mp4`
- `video/jan26_q36_70.mp4`

### Frame

Ogni frame contiene il timestamp:

```text
frame_00-01-32.jpg
```

### Cartelle Per Video

I dati derivati vengono separati per video:

- `frames/<video_name>/`
- `text/<video_name>/`
- `output/<video_name>/`

Questo evita collisioni tra run diversi e semplifica la gestione di piu' video nello stesso progetto.

## Limitazioni Attuali

Il progetto funziona bene come pipeline tecnica, ma ci sono ancora limiti importanti.

### 1. Il Cleanup Euristico Non Basta

La fase `clean_document.py` migliora solo in parte il testo.

Problemi ancora presenti:

- parole attaccate
- token tecnici spezzati o deformati
- punteggiatura rumorosa
- frasi non sempre grammaticalmente corrette

### 2. Il Parser Assume Una Sequenza Regolare

Il builder assume che i file siano in coppie domanda/risposta.

Se il video cambia struttura, il parser potrebbe richiedere adattamenti.

### 3. OCR Sensibile Alla Qualita' Del Frame

Risultati peggiori quando:

- il testo e' piccolo
- c'e' blur o compressione
- il contrasto e' basso
- la slide contiene elementi molto densi

### 4. Nessun LLM Integrato

Il progetto oggi non usa ancora un LLM per:

- normalizzare il testo
- correggere frasi spezzate
- riscrivere il contenuto in forma leggibile
- segnalare ambiguita' residue

## Direzione Consigliata Per I Prossimi Passi

Per ottenere documenti davvero leggibili, il flusso consigliato e':

1. `video -> frames`
2. `frames -> OCR`
3. `OCR -> JSON strutturato`
4. `retry OCR sui casi problematici`
5. `LLM cleanup record-by-record`
6. `export finale in Markdown / DOCX / CSV`

Il punto corretto in cui inserire un LLM e' dopo il parser strutturato, non prima.

Motivo:

- prima serve estrarre struttura affidabile
- poi il modello puo' ripulire il testo senza “inventare” il formato

## Esempio Di Pipeline Consigliata Con LLM

Per ogni record JSON:

Input:

- domanda OCR
- opzioni OCR
- soluzione OCR
- spiegazione OCR
- warning di validazione
- informazioni sul retry

Output desiderato:

- stesso schema JSON
- testo reso leggibile
- nessuna invenzione di contenuto
- eventuale flag `uncertain` se un campo resta ambiguo

## Git Ignore

Il progetto ignora gia' i dati pesanti e generati:

- `.venv`
- `video/*`
- `frames/*`
- `text/*`

Valuta se ignorare anche:

- `output/*`

se non vuoi versionare i documenti generati.

## Comandi Rapidi

Download + frame extraction:

```powershell
.venv\Scripts\python.exe main.py
```

OCR:

```powershell
.venv\Scripts\python.exe extract_text.py <video_name>
```

Build JSON/Markdown:

```powershell
.venv\Scripts\python.exe build_document.py <video_name>
```

Build versione cleaned:

```powershell
.venv\Scripts\python.exe clean_document.py <video_name>
```

Esempio completo:

```powershell
.venv\Scripts\python.exe extract_text.py jan26_q1_35
.venv\Scripts\python.exe build_document.py jan26_q1_35
.venv\Scripts\python.exe clean_document.py jan26_q1_35
```

## Stato Attuale

Ad oggi il progetto:

- scarica video YouTube
- estrae frame con naming temporale
- salva i frame in cartelle per video
- esegue OCR frame-by-frame
- costruisce JSON e Markdown strutturati
- applica retry OCR su casi incompleti
- genera una versione cleaned del documento

La base tecnica e' buona. Il passo successivo piu' utile e' integrare un modulo LLM per portare il testo da “OCR strutturato” a “documento leggibile e quasi finale”.
