import logging
import json
import os
from pathlib import Path
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from app.arabic import final_only, tokens, ending
from app.audio import decode_audio, split_at_silence, RATE
from app.engine import engine, MODEL_ID, ROOT, REVISION
from app.merge import merge_segments

app = FastAPI(title='Sawt — Arabic endings from speech')
STATIC = Path(__file__).resolve().parents[1] / 'static'
app.mount('/static', StaticFiles(directory=STATIC), name='static')


@app.get('/')
def index():
    return FileResponse(STATIC / 'index.html')


@app.get('/api/status')
def status():
    setup = None
    try:
        setup = json.loads((ROOT / '.cache' / 'setup-status.json').read_text(encoding='utf-8-sig'))
        pieces = ROOT / '.cache' / 'downloads' / REVISION
        if setup['stage'] == 'downloading' and pieces.exists():
            setup['model_download_percent'] = round(sum(p.stat().st_size for p in pieces.glob('*.part')) / 4131809192 * 100, 1)
        snapshot = Path(os.environ['HF_HOME']) / 'hub' / ('models--' + MODEL_ID.replace('/', '--')) / 'snapshots' / REVISION
        if (snapshot / 'model.safetensors').exists():
            setup['model_download_percent'] = 100
        gpu_pieces = ROOT / '.cache' / 'downloads' / 'gpu-runtime'
        setup['gpu_download_percent'] = round(sum(p.stat().st_size for p in gpu_pieces.glob('*.part')) / 2753196039 * 100, 1)
        if (ROOT / '.cache' / 'wheels' / 'torch-2.11.0+cu128-cp313-cp313-win_amd64.whl').exists():
            setup['gpu_download_percent'] = 100
    except (OSError, ValueError, KeyError):
        pass
    return {'state': engine.state, 'device': engine.device, 'model': MODEL_ID,
            'busy': engine.lock.locked(), 'accuracy': None, 'error': engine.error, 'setup': setup}


def prepare():
    if not engine.lock.acquire(blocking=False):
        raise HTTPException(409, 'The speech engine is busy. Please wait.')
    try:
        engine.load()
    except Exception:
        logging.exception('Model initialization failed')
        raise HTTPException(503, 'The model could not load. Check the server log and run setup.ps1.')
    finally:
        engine.lock.release()
    return status()


@app.post('/api/prepare')
async def prepare_model():
    return await run_in_threadpool(prepare)


def recognize(data):
    if not engine.lock.acquire(blocking=False):
        raise HTTPException(409, 'The speech engine is busy. Please wait.')
    try:
        audio = decode_audio(data)
        spans = split_at_silence(audio)
        segments = []
        for a, b in spans:
            raw = engine.transcribe(audio[a:b])
            segments.append({'start': round(a/RATE, 3), 'end': round(b/RATE, 3),
                             'text': final_only(raw), 'raw': raw})
        raw_text, joins = merge_segments(segments)
        text = final_only(raw_text)
        if not tokens(text):
            raise ValueError('No Arabic words were recognized. Try a clearer recording.')
        words = tokens(text)
        warnings = ['Model predictions may still normalize pronunciation. Final-ending accuracy has not been measured on your voice.']
        for join in joins:
            if join['status'] == 'unresolved':
                warnings.append(f"Review {join['start']:.1f}–{join['end']:.1f}s: overlapping speech could not be joined reliably. Both versions were retained; some words may repeat.")
            elif join['ending_conflicts']:
                warnings.append(f"Review {join['start']:.1f}–{join['end']:.1f}s: the overlapping predictions disagree on {join['ending_conflicts']} word ending(s).")
        return {'text': text, 'raw_text': raw_text, 'joins': joins,
                'segments': segments, 'duration': round(len(audio)/RATE, 2),
                'words': [{'text': w, 'ending': ending(w) or None} for w in words],
                'warnings': warnings,
                'accuracy': None}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logging.exception('Transcription failed')
        raise HTTPException(503, 'Speech inference failed. Check the server log; the model may need downloading or more GPU memory.') from exc
    finally:
        engine.lock.release()


@app.post('/api/transcribe')
async def transcribe(file: UploadFile = File(...)):
    try:
        data = await file.read(25 * 1024 * 1024 + 1)
    finally:
        await file.close()
    if len(data) > 25 * 1024 * 1024:
        raise HTTPException(413, 'The WAV file must be smaller than 25 MB.')
    return await run_in_threadpool(recognize, data)
