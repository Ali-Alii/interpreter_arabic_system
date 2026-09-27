from io import BytesIO
import numpy as np
import pytest
import soundfile as sf
from app.audio import decode_audio, split_at_silence, RATE


def tone(seconds, rate=RATE):
    return (0.15*np.sin(2*np.pi*220*np.arange(int(seconds*rate))/rate)).astype('float32')


def test_resample_preserves_duration():
    stream = BytesIO()
    sf.write(stream, tone(2, 48000), 48000, format='WAV')
    assert len(decode_audio(stream.getvalue())) == 2 * RATE


def test_no_word_cut_and_no_overlap():
    audio = np.concatenate([tone(20), np.zeros(RATE), tone(20)])
    spans = split_at_silence(audio)
    assert len(spans) == 2
    assert 20*RATE < spans[0][1] < 21*RATE
    assert spans[0][1] == spans[1][0]
    assert spans[0][0] == 0 and spans[-1][1] == len(audio)


def test_continuous_speech_overlaps_without_gaps():
    spans = split_at_silence(tone(65))
    assert spans == [(0,25*RATE),(20*RATE,45*RATE),(40*RATE,65*RATE)]


def test_old_baseline_available_for_comparison():
    with pytest.raises(ValueError, match='pause-only'):
        split_at_silence(tone(26), allow_overlap=False)


def test_two_minute_continuous_audio_keeps_every_sample():
    spans = split_at_silence(tone(120))
    assert spans[0][0] == 0 and spans[-1][1] == 120*RATE
    assert all(b-a <= 25*RATE for a,b in spans)
    assert all(c <= b for (_,b),(c,_) in zip(spans,spans[1:]))


def test_silence_rejected():
    stream = BytesIO(); sf.write(stream, np.zeros(RATE), RATE, format='WAV')
    with pytest.raises(ValueError, match='silent'): decode_audio(stream.getvalue())


def test_corrupt_audio_rejected():
    with pytest.raises(ValueError): decode_audio(b'not wav')
