# Sawt — Arabic endings from speech

A local microphone → Arabic transcript application. It displays harakat and tanween only on the last letter of each word. The interface supports microphone recording, WAV upload, audio replay, text copying, and transcript download.

## Run on Windows

Python 3.13 and an NVIDIA GPU are supported. In PowerShell, from this folder:

```powershell
.\setup.ps1
.\start.ps1
```

Open **http://127.0.0.1:8000** in Edge or Chrome. Allow microphone access, press the microphone, speak, then press it again. Text appears after recording finishes; this is not streaming recognition. The initial setup downloads approximately 4.13 GB of model weights plus dependencies. Model data lives in `.cache/huggingface` unless `HF_HOME` is already configured. Keep the server terminal open.

If setup is already running in the background, the page shows its state. You can record, play back, and save a WAV immediately. Keep the page open to retain the recording; when **Engine ready · GPU** appears, click **Transcribe this recording**. Progress is also recorded in `.cache/setup-status.json`. On a slow connection, these multi-gigabyte downloads can take a long time. For a stalled model download, `python scripts/download_weights.py` offers resumable range downloads and verifies SHA-256. Background setup errors are displayed on the page; `setup.ps1` can retry a failed installation. Remove `.cache/setup-status.json` if manually replacing an abandoned background setup.

If PowerShell blocks local scripts, run the equivalent commands manually:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pip install torch==2.11.0+cu128 --index-url https://download.pytorch.org/whl/cu128
.\.venv\Scripts\python.exe scripts\prepare_model.py
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

CUDA on an 8 GB GPU is the intended configuration, but available memory depends on other running applications and audio length. CPU fallback exists and is much slower. If GPU memory is insufficient, close GPU-heavy applications and record shorter sentences. No API key is used. Inference is local. Audio is not saved by the server. The browser retains the current recording for playback until it is replaced or the page is closed. The interface optionally loads fonts from Google Fonts; system fonts work offline.

## Why this architecture

Ordinary Arabic ASR often omits vowels. Text-only diacritizers then predict grammatical endings, which is inappropriate when the speaker deliberately uses an incorrect ending. Instead, this app uses [NAMAA-Space/Cohere-Speech-Tashkeel-2B](https://huggingface.co/NAMAA-Space/Cohere-Speech-Tashkeel-2B), an audio-to-diacritized-text model, at pinned revision `710704bf787fa3c27f7567aa08078861925aeee2`.

The model's own language prior may still normalize an unusual pronunciation. **No separate correction stage does not mean guaranteed verbatim output.** Reliable preservation of deliberately ungrammatical endings must be tested and may require fine-tuning with contrastive spoken examples. The model author's general diacritic results are not an accuracy guarantee for this application.

Pipeline:

1. Capture mono PCM in an AudioWorklet, preserving the browser's actual sample rate. Avoid browser speech recognition and its normalization.
2. Decode WAV, check duration/level, and resample once to 16 kHz.
3. For longer paragraphs, prefer detected pauses of at least 360 ms. If no suitable pause exists, use 25-second chunks with 5 seconds of shared audio. Match suffix/prefix words with edit-distance alignment, then place the join near the middle of the overlap. Complete word predictions, including their marks, come from one side; endings are not grammatically corrected. Ambiguous joins retain both versions and receive a review warning. Repeated phrases, variable speech rate, and recognition errors can still cause duplication or omission. This is a heuristic, not acoustic forced alignment.
4. Generate letters and diacritics together from the audio. There is no separate word/phoneme alignment step to attach vowels to a second transcript. Returned segment times refer to audio chunks, **not word timestamps**. Silence detection is an energy heuristic and can fail in noisy recordings.
5. Strip internal vowel marks using Unicode character clusters. Preserve predicted final marks, punctuation, spelling, hamza, and repeated words. Never infer a missing mark or change it into sukun. When fatḥatan occurs before a supporting alif, move that existing fatḥatan to the final alif for the literal final-letter display convention. The original per-chunk output is available for review when audio overlaps.

Limits: one speaker, up to 120 seconds, WAV under 25 MB, no mandatory pauses. Clear MSA with explicitly pronounced endings is the intended input. Dialect, silence, background noise, assimilation, and pause pronunciation need separate evaluation.

## Measure the actual >90% requirement

Software tests verify formatting, splitting, HTTP behavior, and scoring. **They do not demonstrate speech-recognition accuracy.** No accuracy on the user's voice has been measured yet.

Build a held-out test set with recordings from intended users, microphones, and rooms. Have a competent Arabic listener label the endings actually audible, including incorrect grammar. Include all three short vowels, all three tanween endings, sukun, missing/inaudible endings, repeated words, supporting alif, and sentence-final pauses. Include minimal pairs such as the same sentence ending in الطالبُ / الطالبَ / الطالبِ. Do not label an unpronounced grammatical ending as if it were spoken. Keep training and test speakers/paragraphs separate.

Create UTF-8 `evaluation.jsonl`, one object per line, with paths relative to the manifest:

```json
{"id":"speaker01-001","audio":"recordings/001.wav","reference":"جاءَ الطالبِ"}
{"id":"speaker01-002","audio":"recordings/002.wav","reference":"قرأتُ كتاباً"}
```

These are example labels, not supplied recordings or benchmark results. Each reference must describe its actual audio. Run:

```powershell
.\.venv\Scripts\python.exe -m app.evaluate evaluation.jsonl
```

The report uses spelling-based Levenshtein word alignment, with ending agreement only as a tie-breaker. It reports:

- **Strict word + ending accuracy** = correctly recognized words with correct final marks / (reference words + inserted words). Wrong words, missed words, added words, and wrong endings hurt this primary metric. This is the app's explicit >90% target.
- **Ending accuracy on matched words** as a secondary, conditional measure. It must not replace the primary metric because it excludes recognition errors.
- Undiacritized word error rate and per-word alignments for error analysis.

For scoring previously generated transcripts, rows may provide `prediction` instead of `audio`. That mode runs no acoustic inference. More than 90% on one small set does not establish general accuracy; use a sufficiently large representative set and inspect per-ending and per-speaker errors. If the target is missed, collect failure examples, fine-tune an acoustic model with human-verified literal transcripts, and re-evaluate on an untouched test set. This repository does not claim that training has already been performed.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
node --check static\app.js
```

The API contract tests stub model inference and are explicitly not acoustic tests.

## API

- `GET /api/status`: engine readiness, device, busy state; accuracy is `null` until externally measured.
- `POST /api/prepare`: load/download the pinned model.
- `POST /api/transcribe`: multipart field `file` containing WAV; returns display text, raw text, audio segment ranges, words, and limitations.

One inference job runs at a time; competing requests receive HTTP 409. This server is intended for local use and binds only to loopback.

## Test continuous speech

Record a paragraph naturally for 30–60 seconds, save the WAV, and listen back while checking the transcript. Pay particular attention to reported join ranges and deliberately incorrect endings. Use the same audio and a human-checked reference when comparing versions; different recordings do not isolate algorithm changes. The evaluation command uses overlap merging by default. Add --pause-only to reproduce the previous segmentation baseline on recordings it accepts. Continuous recordings rejected by that baseline have no baseline accuracy score. Unit tests exercise long audio and transcript merging with stub predictions; they do not establish real-world accuracy.
