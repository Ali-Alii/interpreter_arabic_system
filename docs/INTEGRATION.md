# Platform integration deliverables

Public microphone app: https://ali-alii-sawt-arabic-gpu.hf.space
Space identifier: `Ali-Alii/sawt-arabic-gpu`
Source and runtime: https://huggingface.co/spaces/Ali-Alii/sawt-arabic-gpu/tree/main

## API v1

The colleague supplied the JSON structure; this API implements transcript.diacritized and pronunciation with summary/findings. Mode semantics were not supplied, so the explicit modes below are our integration contract. Confidence is null because the model has no calibrated per-ending confidence. The receiving platform must accept nullable confidence and accuracy.

Install `gradio_client` (tested locally with 2.7.1). Copy `integrations/arabic_wrapper_client.py` into the platform backend. Set variable `SAWT_SPACE=Ali-Alii/sawt-arabic-gpu`. Optionally set the caller's own `HF_TOKEN` in hosting Secrets. Do not send tokens to frontend code or commit them. Calls consume the caller's available quota and may queue or fail; authentication does not make service unlimited.

```python
from arabic_wrapper_client import evaluate
result = evaluate('recording.webm', 'ذهبَ الطالبُ', 'compare_reference')
print(result['transcript']['diacritized'])
print(result['reference_comparison']['alignment'])
```

Gradio endpoint: `/evaluate`. Positional inputs: uploaded audio file, reference_text string, mode string.
- `transcribe`: reference ignored for scoring; reference_comparison is null.
- `compare_reference`: requires an Arabic reference; comparison happens AFTER inference. Reference never conditions the speech model.

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

`available` is true only in compare_reference mode. Each finding contains word, status, expected_ending, detected_ending, detection_confidence and explanation. Ending names: fatha, damma, kasra, fathatan, dammatan, kasratan, sukun; unavailable endings are null. Missing marks, inserted/deleted words, and spelling mismatches are uncertain. Other recognized words are correct/incorrect by exact final-mark agreement. Confidence is always null, never an invented probability.

Summary counts all findings. Its accuracy is correct / (correct + incorrect + uncertain), or null when no comparison exists. This is a conservative reference-agreement fraction, not validated ASR accuracy. It can differ from strict_final_word_accuracy because that metric includes exact unmarked matches while pronunciation findings treat missing vowel evidence as uncertain. Do not exclude uncertain findings to inflate scores.

The exact deployable code is available in the Hugging Face Space source tree linked above; the GitHub main branch still has older implementation files plus this integration handover. Use the Space source to reproduce the hosted API.
