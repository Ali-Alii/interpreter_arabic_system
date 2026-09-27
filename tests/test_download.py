import hashlib
from io import BytesIO
import pytest
from scripts import download_weights as downloader


def test_download_resumes_saved_subrange(monkeypatch, tmp_path):
    data = b'a' * (1024*1024) + b'b' * 123
    pieces = tmp_path / 'pieces'
    pieces.mkdir()
    (pieces / '000000000000.tmp').write_bytes(data[:1024*1024])
    requested = []

    def respond(request, timeout):
        first, last = map(int, request.headers['Range'][6:].split('-'))
        requested.append(first)
        response = BytesIO(data[first:last+1])
        response.status = 206
        response.headers = {'Content-Range':f'bytes {first}-{last}/{len(data)}'}
        return response

    monkeypatch.setattr(downloader.urllib.request, 'urlopen', respond)
    destination = tmp_path / 'result.bin'
    downloader.download_file('https://example.test/file', len(data), hashlib.sha256(data).hexdigest(), destination, pieces)
    assert requested == [1024*1024]
    assert destination.read_bytes() == data
    assert not list(pieces.glob('*.part'))


def test_checksum_failure_does_not_install(monkeypatch, tmp_path):
    pieces = tmp_path / 'pieces'
    pieces.mkdir()
    (pieces / '000000000000.part').write_bytes(b'wrong')
    destination = tmp_path / 'result.bin'
    with pytest.raises(RuntimeError, match='checksum mismatch'):
        downloader.download_file('https://example.test/file', 5, '0'*64, destination, pieces)
    assert not destination.exists()
