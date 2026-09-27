from io import BytesIO
import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient
from app.main import app, engine

client = TestClient(app)


def test_ui_and_status():
    assert client.get('/').status_code == 200
    assert client.get('/api/status').json()['accuracy'] is None


def test_transcription_contract(monkeypatch):
    # This tests the HTTP/formatting contract, not model accuracy.
    monkeypatch.setattr(engine, 'transcribe', lambda audio: 'جَاءَ الطَّالِبِ')
    buf = BytesIO()
    sf.write(buf, .1*np.sin(np.arange(16000)*.1), 16000, format='WAV')
    response = client.post('/api/transcribe', files={'file':('test.wav', buf.getvalue(), 'audio/wav')})
    assert response.status_code == 200
    assert response.json()['text'] == 'جاءَ الطالبِ'
    assert response.json()['accuracy'] is None


def test_invalid_audio():
    assert client.post('/api/transcribe', files={'file':('x.wav', b'bad')}).status_code == 422


def test_busy():
    with engine.lock:
        assert client.post('/api/prepare').status_code == 409


def test_setup_status_is_reported(monkeypatch, tmp_path):
    import app.main as main
    monkeypatch.setattr(main, 'ROOT', tmp_path)
    cache = tmp_path / '.cache'
    cache.mkdir()
    (cache / 'setup-status.json').write_text('{"stage":"downloading","message":"Preparing model"}', encoding='utf-8')
    assert client.get('/api/status').json()['setup']['stage'] == 'downloading'


def test_long_continuous_audio_transcribes_instead_of_rejecting(monkeypatch):
    answers = iter(['ذهبِ الطالبَ إلى المدرسةُ في الصباحَ', 'إلى المدرسةُ في الصباحَ ثم عادَ'])
    monkeypatch.setattr(engine, 'transcribe', lambda audio: next(answers))
    buf = BytesIO()
    sf.write(buf, .1*np.sin(np.arange(30*16000)*.1), 16000, format='WAV')
    response = client.post('/api/transcribe', files={'file':('test.wav', buf.getvalue(), 'audio/wav')})
    assert response.status_code == 200
    data = response.json()
    assert data['text'] == 'ذهبِ الطالبَ إلى المدرسةُ في الصباحَ ثم عادَ'
    assert data['segments'][1]['start'] == 20
    assert data['joins'][0]['status'] == 'merged'
