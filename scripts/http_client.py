"""Small standard-library GET client; no global monkey-patching of requests."""
import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

class Response:
    def __init__(self, response):
        self.status_code = response.status
        self.content = response.read()
        self.text = self.content.decode(response.headers.get_content_charset() or 'utf-8')
    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f'HTTP {self.status_code}')
    def json(self):
        return json.loads(self.text)

def get(url, headers=None, params=None, timeout=20):
    if params:
        url += ('&' if '?' in url else '?') + urlencode(params)
    with urlopen(Request(url, headers=headers or {}), timeout=min(float(timeout), 30)) as response:
        return Response(response)
