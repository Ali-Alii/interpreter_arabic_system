# Platform integration deliverables

Public microphone app: https://ali-alii-sawt-arabic-gpu.hf.space
Space identifier: `Ali-Alii/sawt-arabic-gpu`
Source and runtime: https://huggingface.co/spaces/Ali-Alii/sawt-arabic-gpu/tree/main

## API v1

The colleague supplied the JSON structure; this API implements transcript.diacritized and pronunciation with summary/findings. The colleague has now specified light/full modes; these are supported. Legacy transcribe/compare_reference aliases remain accepted. Confidence is null because the model has no calibrated per-ending confidence. The receiving platform must accept nullable confidence and accuracy.

Install `gradio_client` (tested locally with 2.7.1). Copy `integrations/arabic_wrapper_client.py` into the platform backend. Set variable `SAWT_SPACE=Ali-Alii/sawt-arabic-gpu`. Optionally set the caller's own `HF_TOKEN` in hosting Secrets. Do not send tokens to frontend code or commit them. Calls consume the caller's available quota and may queue or fail; authentication does not make service unlimited.

```python
from arabic_wrapper_client import evaluate
result = evaluate('recording.webm', 'ذهبَ الطالبُ', 'full')
print(result['transcript']['diacritized'])
print(result['reference_comparison']['alignment'])
```

Gradio endpoint: `/evaluate`. Positional inputs: uploaded audio file, reference_text string, mode string.
- `light`: reference ignored for scoring; reference_comparison is null.
- `full`: compares against an Arabic reference; an empty reference returns pronunciation.available=false; comparison happens AFTER inference. Reference never conditions the speech model.

Return JSON keys:
- schema_version: `1.0`
- mode: requested mode
- transcript: object containing diacritized (Arabic with final marks only)
- pronunciation: available, summary and findings matching the requested structure
- raw_transcript: model text before final-letter formatting
- duration_seconds: decoded audio duration
- reference_comparison: null or the `app.evaluate.score` report
- recognition_accuracy: always null (not measured by a single request)
- warnings: list of limitations

Comparison report includes strict_final_word_accuracy (fraction 0–1), word_error_rate, correct_words_and_endings, reference_words, insertions, matched_words, correct_endings_on_matched_words, ending_accuracy_on_matched_words, by_reference_ending, and alignment. Each alignment item has reference, prediction, correct; null represents insertion/deletion. Correct means text/ending agreement with the supplied reference, not a verified judgment of what the student pronounced. Model errors can create false learner errors. Do not display this as definitive pronunciation correctness.

## Media and errors

WAV/WebM inputs are converted using ffmpeg, mono PCM 16 kHz. Input limit 25 MB; decoded duration 0.3–120 seconds, subject to silence checks. Conversion time is bounded; >120-second inputs are rejected. Temporary conversion files are removed. Gradio uploads use its cleanup policy. Do not use the service for remote URL fetching; upload bytes with handle_file.

Invalid input raises a Gradio error. Callers must handle gradio_client.exceptions.AppError, timeouts, queue/quota failures and service unavailability, retain the recording for retry, and avoid automatic retry loops that spend quota. The API is queued Gradio, not a synchronous JSON POST at the Space homepage. Use submit(...).result(timeout=...) if the platform requires a bounded wait; cancellation of a client wait does not necessarily cancel server inference.

## Acceptance and accuracy gate

A real anonymous transcription succeeded before this API extension. The integration must additionally pass an actual WebM upload and JSON-response check after deployment. Such a smoke test is not an accuracy benchmark. No multi-recording, human-verified Arabic test set was supplied. The previous 18/20 (90%) was prompt agreement with pasted text, not audio-verified accuracy, and does not meet an above-90% criterion.

The colleague's requested accuracy gate is therefore NOT PASSED. Integration development can use this endpoint, but do not approve educational production use on the basis of the current evidence. Supply consented Arabic WAVs plus labels verified by listening, then run:

```powershell
.venv\Scripts\python.exe -m app.evaluate verified-recordings.jsonl --output accuracy-results.json
```

Manifest example (replace with a real verified recording):
`{"id":"speaker01-001","audio":"recordings/001.wav","reference":"ذهبَ الطالبُ"}`

Keep test speakers/passages separate from tuning data. Report sample counts, per-ending performance and strict word+ending score. Share the generated report, not an invented percentage.

## Division of work

Ali: GPU Space, model startup, GPU function, ffmpeg, public endpoint, source and client example. Colleague: adapt his platform's wrapper to this schema, add Space name and own token in Secrets, deploy his backend, and run a complete exercise. No changes have been made to the colleague's platform and no message was sent to him.

## Pronunciation response semantics

`available` is true only in full mode. Each finding contains word, status, expected_ending, detected_ending, detection_confidence and explanation. Ending names: fatha, damma, kasra, tanwin_fath, tanwin_damm, tanwin_kasr, sukun; unavailable endings use none. Missing marks, inserted/deleted words, and spelling mismatches are uncertain. Other recognized words are correct/incorrect by exact final-mark agreement. Confidence is always null, never an invented probability.

Summary counts all findings. Its accuracy is correct / (correct + incorrect + uncertain), or null when no comparison exists. This is a conservative reference-agreement fraction, not validated ASR accuracy. It can differ from strict_final_word_accuracy because that metric includes exact unmarked matches while pronunciation findings treat missing vowel evidence as uncertain. Do not exclude uncertain findings to inflate scores.

The exact deployable code is available in the Hugging Face Space source tree linked above; the GitHub main branch still has older implementation files plus this integration handover. Use the Space source to reproduce the hosted API.

## Deployment validation completed

Anonymous calls to the deployed `/evaluate` passed with a browser-encoded WebM sample in both transcribe and full modes. The latter used a deliberately partial reference solely to verify summary/findings behavior; its score is not an accuracy result. Three local integration tests passed for reference isolation, invalid-mode rejection, and uncertain findings/null confidence. Multiple-speaker Arabic accuracy evaluation remains outstanding. FFmpeg packages.txt must use LF line endings; CRLF caused an apt package lookup failure during deployment and was corrected.

## Colleague compatibility update

`light` returns transcript.diacritized and pronunciation: {"available": false}. `full` returns summary/findings when reference_text contains Arabic; an empty reference produces available=false. Codes are none, fatha, damma, kasra, tanwin_fath, tanwin_damm, tanwin_kasr, and **sukun** (the platform must add sukun). detection_confidence remains nullable. Missing audible-mark evidence is uncertain even if spelling matches, to avoid treating model omission as proven student error. Recognized words with differing explicit marks are incorrect; lexical mismatches are uncertain.

Maximum recording duration remains **120 seconds**, input size **25 MB**. Longer recordings are rejected, not truncated. The colleague must show that limit explicitly rather than silently skip Arabic checking. Long-recording support has not been validated on free ZeroGPU.

Use via API:

```python
from gradio_client import Client, handle_file
import os
client = Client("Ali-Alii/sawt-arabic-gpu", hf_token=os.getenv("HF_TOKEN") or None)
result = client.predict(handle_file("recording.webm"), "???? ???????", "full", api_name="/evaluate")
print(result["transcript"]["diacritized"])
print(result["pronunciation"])
```

Accuracy deliverable: **not measured on an audio-verified research dataset; 0 verified benchmark recordings, 0 verified benchmark speakers**. Public sample smoke tests validate the API, not recognition accuracy. No percentage can responsibly be supplied from app.evaluate until a verified manifest is provided. The earlier package-install failure was caused by CRLF in packages.txt; the deploy script now emits LF bytes regardless of local checkout settings. The running Space previously completed real GPU inference using torch 2.11.0; a torch incompatibility was not the observed cause.
