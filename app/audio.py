"""Decode PCM WAV; prefer pauses and overlap when speech is continuous."""
from io import BytesIO
from math import gcd
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

RATE = 16000
MAX_SECONDS = 120
CHUNK_SECONDS = 25
OVERLAP_SECONDS = 5


def decode_audio(data: bytes) -> np.ndarray:
    try:
        with sf.SoundFile(BytesIO(data)) as f:
            if f.format != 'WAV':
                raise ValueError('Please upload a WAV recording.')
            if not 8000 <= f.samplerate <= 96000 or f.channels > 2:
                raise ValueError('Use mono or stereo WAV, 8–96 kHz.')
            if len(f) / f.samplerate > MAX_SECONDS + 0.1:
                raise ValueError('Recordings must be 120 seconds or shorter.')
            rate = f.samplerate
            audio = f.read(dtype='float32', always_2d=True).mean(axis=1)
    except (RuntimeError, sf.LibsndfileError) as exc:
        raise ValueError('This file is not a readable WAV recording.') from exc
    if len(audio) < rate * 0.3 or not np.isfinite(audio).all():
        raise ValueError('Record at least 0.3 seconds of clear speech.')
    if rate != RATE:
        factor = gcd(rate, RATE)
        audio = resample_poly(audio, RATE // factor, rate // factor).astype(np.float32)
    if np.sqrt(np.mean(audio ** 2)) < 0.0003:
        raise ValueError('The recording is silent or too quiet. Move closer to the microphone.')
    return audio


def split_at_silence(audio: np.ndarray, *, allow_overlap=True) -> list[tuple[int, int]]:
    frame = 320
    rms = np.array([np.sqrt(np.mean(audio[i:i+frame] ** 2)) for i in range(0, len(audio), frame)])
    threshold = max(0.0005, min(0.008, float(np.percentile(rms, 90)) * 0.08))
    quiet = rms < threshold
    cuts = []
    start = None
    for i, silent in enumerate([*quiet, False]):
        if silent and start is None:
            start = i
        if not silent and start is not None:
            if i - start >= 18:  # 360 ms: preserve final vowels and tanween.
                cuts.append((start + i) * frame // 2)
            start = None
    spans, left = [], 0
    limit = CHUNK_SECONDS * RATE
    while len(audio) - left > limit:
        # Prefer a pause in the latter portion of a chunk. An early pause must
        # not create tiny chunks followed by a second split inside the overlap.
        minimum = 10 * RATE if allow_overlap else RATE
        candidates = [p for p in cuts if left + minimum < p <= left + limit]
        if not candidates:
            if not allow_overlap:
                raise ValueError('The pause-only baseline cannot split more than 25 seconds of continuous speech.')
            right = left + limit
            spans.append((left, right))
            left = right - OVERLAP_SECONDS * RATE
            continue
        right = max(candidates)
        spans.append((left, right))
        left = right
    spans.append((left, len(audio)))
    return [(a, b) for a, b in spans if np.sqrt(np.mean(audio[a:b] ** 2)) >= 0.0003]
