# Sawt: research and engineering handover

Documentation date: 2026-11-14. Repository: https://github.com/Ali-Alii/interpreter_arabic_system

## Read this first: repository versus working prototype

This document records work performed during the project, including experiments that remain in the original developer workspace. At preparation time, the latest local committed implementation was `7c5caac` (continuous speech overlap support). Numerous later implementation files were modified or untracked. This documentation commit does **not** publish those implementation changes. A fresh clone must not be assumed to contain every experimental module described below. Before continuing research, obtain and review the experimental source, commit it separately, and record the exact revision used for every evaluation. Live deployments are independent of this GitHub checkout; the URLs below are historical deployment locations, not a fresh availability check.

## Objective and non-negotiable behavior

Record Arabic speech and display the words with harakat/tanween only at word endings. Preserve what the student actually says, including grammatically incorrect endings. Do not apply a grammar corrector or infer case endings from the expected passage. A pretrained speech model still has learned language biases: absence of a separate correction stage does not guarantee verbatim output. The desired strict accuracy is above 90%; it has not been established on a representative, audio-verified test set.

## Architecture and source map

The local application uses Python, FastAPI/Uvicorn, PyTorch/Transformers, NumPy/SciPy and SoundFile. The frontend is HTML/CSS/JavaScript with an AudioWorklet, rather than browser speech recognition. It records first and transcribes after stopping; recognition is not streaming.

| Component | Responsibility | Availability at handover |
| --- | --- | --- |
| `static/index.html`, `static/app.js`, `static/style.css` | Recording, playback, upload, Arabic display | Committed baseline; later UI changes local |
| `app/main.py` | API, validation, inference lock, orchestration | Baseline committed; comparison/scoring extensions local |
| `app/engine.py` | Pinned model loading and generation | Baseline committed; decoder experiments local |
| `app/audio.py` | WAV validation, resampling, segmentation | Committed |
| `app/merge.py` | Overlapping transcript joins | Committed |
| `app/arabic.py` | Unicode-aware final-letter formatting | Committed |
| `app/evaluate.py` | Word alignment and accuracy reports | Baseline committed; ending breakdown/beam comparison local |
| `app/acoustic.py` | Silent-audio contrast experiment | Local experimental source |
| `app/hosted.py`, `space_app.py` | Gradio/ZeroGPU adapter | Local hosting source |
| `deploy/public-service/server.py` | Lightweight hosted formatting/scoring and prepared proxy | Local hosting source |
| `scripts/` | Setup, downloads, browser checks and deployment tooling | Mixed committed/local files |

Model: `NAMAA-Space/Cohere-Speech-Tashkeel-2B`, pinned locally to `710704bf787fa3c27f7567aa08078861925aeee2`. Weights are approximately 4.13 GB. No project-specific acoustic fine-tuning has been completed. The model publisher's hosted service can change independently of the local revision.

### Audio and alignment

Capture PCM WAV using the browser's actual sampling rate; validate and resample to 16 kHz. Local limits are 120 seconds and 25 MB, with silence/level checks. Prefer energy-detected pauses of at least 360 ms. Long uninterrupted speech uses 25-second windows with 5-second overlap.

Originally, continuous speech longer than 25 seconds without a safe pause was rejected to avoid cutting endings. The overlap implementation removed that mandatory-pause requirement. Suffix/prefix word alignment ignores marks for lexical matching and chooses a join near the overlap center. It retains a complete word and its marks from one prediction; unresolved joins retain alternatives with a warning. This is **not forced acoustic alignment**, and chunk timestamps are not word timestamps. Repetition, speed changes, noise and recognition errors can still duplicate or omit words. The alignment problem is mitigated, not universally solved.

The recognizer generates spelling and marks together. Formatting strips internal diacritics while retaining final predicted marks, punctuation and spelling. A missing mark is not automatically sukun. Existing fathatan before a supporting alif is moved to that final alif for the project's display convention; it is not newly inferred.

## Experiments and decisions

1. **Baseline greedy recognition:** retained as the reference decoder. Grammar-based repairs were rejected because they would hide student mistakes.
2. **Continuous speech overlap:** replaced the earlier pause-only restriction. Preserve the same waveform when comparing segmentation methods; rejected baseline recordings have no baseline score.
3. **Audio-emphasis experiment:** contrasts real-audio logits against silent-audio logits, with strength 0.35, a plausible-candidate filter, bounded adjustments, separate caches and an end-of-transcript guard. This is not a short-vowel duration classifier. It has no demonstrated general improvement and can worsen predictions.
4. **Five-beam experiment:** encodes the same waveform once and compares greedy against five-beam generation. No expected passage or grammar rules enter inference. Beam search may strengthen learned grammatical preferences and therefore harm deliberate-error preservation. It remains opt-in. An experimental failure retains the original result and is reported explicitly.
5. **Scoring improvements:** added reference-ending breakdowns for fatha, damma, kasra, tanween and sukun. Wrong/missing words remain errors. Reference text is used after inference, not as a decoder prompt.

Do not combine audio-emphasis caches with beam reordering without implementing and testing the required cache semantics. The own-Space Gradio adapter currently exposes the older comparison boolean, not the new local beam selector. The publisher's public API exposes neither custom experiment.

## Evidence and limitations

On 2026-10-25, 53 automated tests passed, and the browser test passed with stubbed speech predictions. Actual greedy and beam inference both completed on an NVIDIA RTX 4060 with 8 GB VRAM using the publisher sample WAV. They returned identical text. This establishes runtime compatibility for that sample, not an accuracy improvement or performance guarantee for long recordings.

The user's pasted five-sentence result matched 18 of 20 prompted words including endings (90%) **conditional on having pronounced the prompts exactly**. The final phrase returned kasra where the prompts requested other endings. The audio and decoder identity were not supplied, so this is text agreement, not a verified acoustic benchmark. Earlier conversational percentages likewise lack the controlled dataset required for a general claim. Exactly 90% also does not satisfy a strictly greater-than-90% target.

Known confusions include short /u/ becoming a written long plural ending (`وصلُ` versus `وصلوا`), short /i/ becoming a written ya (`فدخلِ` versus `فدخلي`), past-verb fatha, `أمامَ`, and kasra in prepositional/genitive contexts. Never repair these with unconditional letter deletion or grammatical case assignment: genuine long vowels and deliberately wrong short endings must both survive.

## Paper supplied by reviewers

Abduljalil et al., *Arabic-Adapted One-Step Speech-to-Diacritized ASR: Evaluation and Error Analysis*, AbjadNLP 2026: https://aclanthology.org/2026.abjadnlp-1.43/

The supplied paper studies fine-tuned Arabic-adapted wav2vec2 and Whisper-base on ClArTTS, approximately 12 hours from one male speaker. It reports 4.1% DER for wav2vec2 and 21.3% versus 15.7% DER for greedy versus beam Whisper. These results are not measurements of our Cohere model, our strict final-word metric, multiple student speakers, or deliberately incorrect grammar. The supplied PDF did not provide a link to its fine-tuned weights. Loading the referenced base checkpoint does not reproduce those trained results. Grammar-based postprocessing suggestions are incompatible with our literal-pronunciation objective.

The audio-emphasis motivation came from https://arxiv.org/abs/2506.07233, which concerns other models/tasks; its results do not validate this implementation for Arabic endings.

## Reproduction and evaluation

For the committed baseline, follow the root README: run `setup.ps1`, then `start.ps1`; use `start.ps1 -Port 8001` if 8000 is occupied. The tested local environment used Python 3.13 and torch 2.11.0+cu128. These are historical tested versions, not a complete reproducible lockfile. Model files live under `.cache/huggingface` unless HF_HOME overrides it. Avoid loading two model processes on the 8 GB GPU simultaneously.

Create UTF-8 JSONL containing `id`, `audio` and `reference`; audio paths are relative to the manifest. Labels must be transcribed by listening to actual audio. Run:

```powershell
.venv\Scripts\python.exe -m app.evaluate evaluation.jsonl --output evaluation-results.json
.venv\Scripts\python.exe -m pytest -q
```

With the local experimental source available:

```powershell
.venv\Scripts\python.exe -m app.evaluate evaluation.jsonl --compare-beam --output beam-results.json
.venv\Scripts\python.exe scripts/smoke_beam.py recording.wav
$env:SAWT_URL='http://127.0.0.1:8001'
node scripts/browser-test.cjs
```

Strict accuracy = correctly recognized words with correct final marks / (reference words + insertions). Also report lexical WER, conditional ending accuracy on matched words and per-ending errors. The conditional score must not replace strict accuracy because it hides lexical errors. This metric differs from the paper's character-level DER. Software tests and synthetic-tone runtime tests are not speech accuracy evaluations.

## Hosting history and operational problems

Historical URLs:
- https://huggingface.co/spaces/Ali-Alii/sawt-arabic-endings
- https://ali-alii-sawt-arabic-endings.static.hf.space
- https://sawt-arabic-endings.vercel.app

The first own-ZeroGPU deployment attempt returned HTTP 402 for account eligibility. A fallback published a static interface using NAMAA's public Space for inference and a small Vercel service for formatting, merging and scoring. This works independently of the developer's computer, but the public service controls model versions, runtime reservations and availability. Browser-side resampling makes this path different from local processing.

Visitors encountered quota errors such as 180 seconds requested versus 177 remaining, even on short recordings. OAuth sign-in was added to use visitor account quotas; it does not remove limits. Audio remains available in the browser for replay/save/retry after failures. The user wanted guests to click the mic without learning authentication, which remains in tension with limited free quotas.

An owner-token proxy was prepared locally but **not deployed**. Exporting the owner's Hugging Face token into Vercel was blocked by automatic approval review because that exact credential transfer had not been authorized. No transfer occurred. Do not assume the secret exists, print it, commit it, or rerun that transfer without explicit authorization. Local staging scripts were modified toward this proxy and must be reviewed before reuse; historical deployment instructions may describe the older visitor-OAuth configuration.

Own ZeroGPU hosting uses Gradio and `spaces.GPU`, imports spaces before torch, and places the model on CUDA during startup. The prepared adapter requests 120 seconds per GPU call and has a bounded queue. That reservation needs benchmarking and potentially dynamic sizing. Never promise unlimited free inference. Eligibility, quotas, hardware names and pricing change: check https://huggingface.co/docs/hub/spaces-zerogpu before deployment. Do not silently select paid hardware.

Vercel does not run the 2B speech model in this architecture. Deploy only the staged lightweight service, not the whole GPU dependency tree. Explicit Python/static build configuration previously resolved Vercel build/routing failures. GitHub pushes do not automatically deploy the existing CLI-managed project.

## Privacy, integration and production work still needed

Local inference does not deliberately persist recordings; browser audio disappears on replacement/closing unless saved. Cloud inference sends recordings to the hosting provider; Gradio temporary file cleanup is configured, but provider retention policies still apply. Collect research recordings only with consent and a documented retention/access policy. Never commit participant audio, credentials, model caches or environment secrets.

For an existing website, embed the interface with appropriate iframe microphone permissions, or integrate recording UI and call a separate HTTPS inference API. Production work includes authentication where appropriate, rate limiting, upload bounds, CORS restrictions, queue limits, timeout handling, monitoring, cancellation and a reviewed audio-retention policy. Measure concurrency and latency before estimating cost. An always-available service cannot be promised on shared free GPU quotas.

## Research continuation plan

1. Recover and version the local experimental implementation separately from this handover. Record dependencies, model revision, decoding parameters and deployment mode with each result.
2. Collect the original failure WAVs and both decoder outputs. Have Arabic-speaking annotators verify audible endings, with disagreements adjudicated. Prompts are not ground truth.
3. Build controlled pairs covering `ذهبَ / ذهبِ / ذهبُ`, `أمامَ / أمامِ / أمامُ`, correct and deliberately incorrect genitive endings, short versus long vowels, all tanween classes, connected speech and pauses. Include multiple speakers, microphones, noise conditions and long repeated passages.
4. Split by speaker and passage before tuning. Compare greedy, beam and contrastive decoding on identical audio; report per-speaker/per-ending results, sample counts, uncertainty, latency and memory. Preserve failed clips in the report rather than silently dropping them.
5. Audit overlap seams separately. Explore acoustic alignment only with verified vowel-sensitive labels; ordinary forced alignment can impose an incorrect transcript or blur word-final vowels.
6. If decoding changes do not help, investigate acoustic fine-tuning or a diacritized CTC model using literal transcripts containing student errors. This requires new training work, dataset/model license review and an untouched test set. No such trained replacement exists in this project yet.
7. Select a default only after held-out improvement is established without sacrificing deliberate-error preservation. Validate the actual hosted build again; local success does not establish cloud equivalence.

## Handover checklist

Keep the baseline, raw model output, formatted output, original audio with consent, verified reference, decoder identity, chunk boundaries and merge warnings together for each research example. Check for uncommitted local work before reproducing an experiment. Review hosting scripts before publishing. Record what failed as carefully as what improved, and distinguish software correctness, text agreement and actual speech recognition accuracy in every report.
