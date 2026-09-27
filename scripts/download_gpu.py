"""Download the CUDA wheel in resumable pieces with official SHA-256 verification."""
import html
import re
import urllib.parse
import urllib.request
from download_weights import download_file, ROOT

index = 'https://download.pytorch.org/whl/cu128/torch/'
filename = 'torch-2.11.0+cu128-cp313-cp313-win_amd64.whl'
with urllib.request.urlopen(index, timeout=60) as response:
    page = response.read().decode()
links = [html.unescape(x) for x in re.findall(r'href="([^"]+)"', page)]
link = next(x for x in links if urllib.parse.unquote(urllib.parse.urlsplit(x).path).endswith('/' + filename))
url, fragment = urllib.parse.urldefrag(urllib.parse.urljoin(index, link))
checksum = urllib.parse.parse_qs(fragment)['sha256'][0]
url = url.replace('https://download-r2.pytorch.org/', 'https://download.pytorch.org/')
request = urllib.request.Request(url, headers={'Range':'bytes=0-0'})
with urllib.request.urlopen(request, timeout=60) as response:
    if response.status != 206:
        raise RuntimeError('The GPU download host does not support partial downloads.')
    size = int(response.headers['Content-Range'].split('/')[-1])
print(f'GPU runtime: {size} bytes; starting resumable download.', flush=True)
download_file(url, size, checksum, ROOT / '.cache' / 'wheels' / filename,
              ROOT / '.cache' / 'downloads' / 'gpu-runtime', label='GPU runtime', range_query=False)
