"""Resumable range download for connections that stall on a multi-GB response.

Uses the pinned Hugging Face file metadata and verifies its complete SHA-256.
Partial pieces are kept under .cache/downloads and may safely be resumed.
"""
import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import sys
import time
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.engine import MODEL_ID, REVISION, ROOT


def download():
    api = f'https://huggingface.co/api/models/{MODEL_ID}/revision/{REVISION}?blobs=true'
    with urllib.request.urlopen(api, timeout=60) as response:
        metadata = json.load(response)
    entry = next(f for f in metadata['siblings'] if f['rfilename'] == 'model.safetensors')
    size, checksum = entry['size'], entry['lfs']['sha256']
    destination = Path(os.environ['HF_HOME']) / 'hub' / ('models--' + MODEL_ID.replace('/', '--')) / 'snapshots' / REVISION / 'model.safetensors'
    base = f'https://huggingface.co/{MODEL_ID}/resolve/{REVISION}/model.safetensors'
    download_file(base, size, checksum, destination, ROOT / '.cache' / 'downloads' / REVISION)


def download_file(base, size, checksum, destination, pieces, label='Weights', range_query=True):
    if destination.exists() and destination.stat().st_size == size:
        print('Weights already present.', flush=True)
        return
    pieces.mkdir(parents=True, exist_ok=True)
    step = 16 * 1024 * 1024
    ranges = [(start, min(start+step, size)-1) for start in range(0, size, step)]

    def fetch(span):
        start, end = span
        path = pieces / f'{start:012d}.part'
        if path.exists() and path.stat().st_size == end-start+1:
            return path
        temporary = path.with_suffix('.tmp')
        for attempt in range(20):
            try:
                offset = temporary.stat().st_size if temporary.exists() else 0
                if offset > end-start+1:
                    raise RuntimeError('Partial download is larger than its expected range.')
                while start + offset <= end:
                    first = start + offset
                    last = min(first + 1024*1024 - 1, end)
                    request = urllib.request.Request(base + (f'?range_start={first}&range_end={last}' if range_query else ''), headers={'Range':f'bytes={first}-{last}'})
                    with urllib.request.urlopen(request, timeout=60) as response:
                        if response.status != 206 or response.headers.get('Content-Range') != f'bytes {first}-{last}/{size}':
                            raise RuntimeError('Server did not honor the requested byte range.')
                        data = response.read(last-first+2)
                    if len(data) != last-first+1:
                        raise RuntimeError('Incomplete download piece.')
                    with temporary.open('ab') as output:
                        output.write(data)
                    offset += len(data)
                temporary.replace(path)
                return path
            except Exception as exc:
                print(f'Piece {start}: attempt {attempt+1} failed: {exc}', flush=True)
                if attempt == 19: raise
                time.sleep(min(2**attempt, 15))

    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = [pool.submit(fetch, span) for span in ranges]
        for completed, job in enumerate(as_completed(jobs), 1):
            job.result()
            print(f'{label}: {completed}/{len(ranges)} pieces ({completed/len(ranges):.1%})', flush=True)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_suffix('.assembling')
    digest = hashlib.sha256()
    with temp.open('wb') as output:
        for start, _ in ranges:
            data = (pieces / f'{start:012d}.part').read_bytes()
            digest.update(data); output.write(data)
    if digest.hexdigest() != checksum:
        raise RuntimeError('Weight checksum mismatch. No model was installed; remove the partial download directory before retrying.')
    temp.replace(destination)
    for start, _ in ranges:
        (pieces / f'{start:012d}.part').unlink()
    print(f'{label} downloaded and SHA-256 verified.', flush=True)


if __name__ == '__main__': download()
