# Video To Text

Pipeline Python per trasformare un video in dati strutturati.

Il progetto scarica un video da YouTube, estrae i frame piu' rilevanti, esegue OCR, ricostruisce le domande in formato JSON, applica retry OCR sui casi difficili e supporta un cleanup finale via OpenAI.

## Cosa Fa

- scarica video da YouTube in `video/`
- estrae frame con timestamp in `frames/<video_name>/`
- esegue OCR frame-by-frame in `text/<video_name>/`
- ricostruisce coppie domanda/risposta in `output/<video_name>/<video_name>.json`
- applica un cleanup euristico in `output/<video_name>/<video_name>.cleaned.json`
- applica un cleanup LLM opzionale in `output/<video_name>/<video_name>.llm.json`

Il caso d'uso principale e' l'estrazione di domande multiple choice da video dove:

- un frame mostra la domanda con le opzioni
- il frame successivo mostra risposta e spiegazione

## Struttura Del Progetto

```text
video_to_text/
|-- app/
|   |-- common/
|   |   `-- path_utils.py
|   |-- config/
|   |   |-- models.py
|   |   `-- settings.py
|   |-- document/
|   |   |-- builder.py
|   |   `-- cleaner.py
|   |-- download/
|   |   `-- downloader.py
|   |-- frames/
|   |   `-- extractor.py
|   |-- llm/
|   |   `-- json_cleaner.py
|   `-- ocr/
|       |-- extractor.py
|       `-- retry.py
|-- video/
|-- frames/
|-- text/
|-- output/
|-- .env
|-- main.py
|-- extract_text.py
|-- build_document.py
|-- clean_document.py
|-- llm_clean_json.py
|-- pyproject.toml
|-- uv.lock
`-- README.md
```

## Organizzazione Dei Moduli

### `app/config`

Configurazione e modelli condivisi.

- `models.py`: dataclass di configurazione per download, frame extraction, OCR e parsing
- `settings.py`: lettura di `.env` tramite `python-dotenv`

### `app/download`

Download del video con `yt-dlp`.

### `app/frames`

Estrazione frame con `OpenCV`.

Caratteristiche:

- lettura dinamica degli FPS
- campionamento ogni `N` secondi
- filtro duplicati
- filtro semplice di cambiamento scena
- salvataggio con timestamp

### `app/ocr`

OCR dei frame con `rapidocr-onnxruntime`.

- `extractor.py`: OCR base con preprocess `gray2x` applicato a tutti i frame
- `retry.py`: retry OCR con varianti immagine per recuperare campi mancanti

### `app/document`

Costruzione e cleanup del JSON.

- `builder.py`: trasforma i `.txt` OCR in record strutturati
- `cleaner.py`: applica cleanup euristico sul JSON risultante

### `app/llm`

Cleanup JSON tramite OpenAI API.

- `json_cleaner.py`: pulizia record-by-record conservando lo schema

### `app/common`

Utility condivise per path e naming.

## Setup

### Requisiti

- Python `>= 3.13`
- `uv`

Dipendenze principali:

- `opencv-python`
- `yt-dlp`
- `rapidocr-onnxruntime`
- `wordninja`
- `openai`
- `python-dotenv`

### Creazione Ambiente

```powershell
uv venv .venv
uv sync
```

Oppure:

```powershell
uv add openai opencv-python python-dotenv rapidocr-onnxruntime wordninja yt-dlp
```

### Attivazione

```powershell
.venv\Scripts\Activate.ps1
```

In alternativa:

```powershell
.venv\Scripts\python.exe <script>.py
```

## Configurazione `.env`

Nel file `.env` puoi incollare la tua chiave OpenAI.

Contenuto iniziale:

```env
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4.1-mini
OPENAI_TEMPERATURE=0
OPENAI_MAX_OUTPUT_TOKENS=2000
LLM_INPUT_SUFFIX=.json
LLM_OUTPUT_SUFFIX=.llm.json
LLM_FAIL_ON_MISSING_KEY=true
```

Campi principali:

- `OPENAI_API_KEY`: chiave API OpenAI
- `OPENAI_MODEL`: modello da usare per il cleanup JSON
- `OPENAI_TEMPERATURE`: temperatura della generazione
- `OPENAI_MAX_OUTPUT_TOKENS`: limite massimo di output per record
- `LLM_INPUT_SUFFIX`: file JSON sorgente da leggere
- `LLM_OUTPUT_SUFFIX`: nome del file JSON finale generato dall'LLM

## Pipeline End-To-End

### 1. Download Del Video E Estrazione Frame

```powershell
.venv\Scripts\python.exe main.py
```

`main.py`:

1. chiede un link YouTube
2. scarica il video in `video/`
3. estrae i frame in `frames/<video_name>/`

### 2. OCR Dei Frame

```powershell
.venv\Scripts\python.exe extract_text.py jan26_q1_35
```

L'estrazione OCR standard usa di default una variante preprocessata `gray2x` per tutti i frame.

Output:

- `text/jan26_q1_35/frame_00-00-00.txt`
- `text/jan26_q1_35/frame_00-00-17.txt`
- ecc.

### 3. Costruzione JSON Strutturato

```powershell
.venv\Scripts\python.exe build_document.py jan26_q1_35
```

Output:

- `output/jan26_q1_35/jan26_q1_35.json`

### 4. Cleanup Euristico Del JSON

```powershell
.venv\Scripts\python.exe clean_document.py jan26_q1_35
```

Output:

- `output/jan26_q1_35/jan26_q1_35.cleaned.json`

### 5. Cleanup LLM Del JSON

Prima incolla la chiave nel file `.env`, poi esegui:

```powershell
.venv\Scripts\python.exe llm_clean_json.py jan26_q1_35
```

Output:

- `output/jan26_q1_35/jan26_q1_35.llm.json`

## Formato Del JSON

Ogni record contiene tipicamente:

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

## Retry OCR

Il builder applica un retry OCR automatico quando trova record incompleti.

Problemi intercettati:

- opzioni mancanti
- domanda incompleta
- answer o explanation assenti

Strategia:

1. recupera il frame originale
2. prova varianti immagine diverse
3. riesegue OCR
4. sceglie la variante migliore

Esempi di varianti:

- frame intero
- crop inferiore
- grayscale 2x
- threshold + resize
- crop mirati per domanda o opzioni

## Differenza Tra I JSON Generati

### `*.json`

Output strutturato base del parser.

### `*.cleaned.json`

Output con cleanup euristico.

Vantaggi:

- nessun costo API
- immediato
- utile come pre-cleanup

Limiti:

- non sempre migliora davvero il testo
- puo' lasciare ancora parole fuse o rumorose

### `*.llm.json`

Output con cleanup LLM record-by-record.

Vantaggi:

- molto piu' adatto a ottenere testo leggibile
- mantiene lo schema JSON
- puo' aggiungere note di ambiguita'

Limiti:

- richiede una chiave OpenAI
- ha costo e latenza
- va comunque revisionato nei casi ambigui

## Quando Usare Il Cleanup LLM

Il punto corretto per usare un LLM e' dopo:

1. OCR
2. parsing strutturato
3. eventuale retry OCR

Non prima.

Motivo:

- prima vuoi estrarre struttura affidabile
- poi vuoi migliorare la leggibilita'
- cosi' il modello pulisce il testo senza dover ricostruire tutto da zero

## Comandi Rapidi

Download + frame extraction:

```powershell
.venv\Scripts\python.exe main.py
```

OCR:

```powershell
.venv\Scripts\python.exe extract_text.py <video_name>
```

JSON strutturato:

```powershell
.venv\Scripts\python.exe build_document.py <video_name>
```

JSON cleaned:

```powershell
.venv\Scripts\python.exe clean_document.py <video_name>
```

JSON cleaned via LLM:

```powershell
.venv\Scripts\python.exe llm_clean_json.py <video_name>
```

Esempio completo:

```powershell
.venv\Scripts\python.exe extract_text.py jan26_q1_35
.venv\Scripts\python.exe build_document.py jan26_q1_35
.venv\Scripts\python.exe clean_document.py jan26_q1_35
.venv\Scripts\python.exe llm_clean_json.py jan26_q1_35
```

## Limitazioni Attuali

- il parser assume una sequenza abbastanza regolare domanda/risposta
- l'OCR dipende molto dalla qualita' del frame
- il cleanup euristico non e' sufficiente per tutti i casi
- il cleanup LLM va considerato assistito, non infallibile

## Stato Attuale

Ad oggi il progetto:

- e' organizzato per step
- ha configurazione centralizzata in `app/config/settings.py`
- usa `.env` per la parte OpenAI
- produce JSON strutturati, cleaned e LLM-cleaned
- mantiene separati i dati per video in `frames/`, `text/` e `output/`

Il flusso piu' consigliato per ottenere un risultato finale leggibile e':

`video -> frames -> OCR -> JSON -> retry OCR -> LLM cleanup -> JSON finale`
