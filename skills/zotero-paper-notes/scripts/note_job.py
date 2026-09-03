"""Prepare and verify Zotero note jobs; never writes the Zotero library itself."""
import argparse
import hashlib
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import urllib.parse
import urllib.request
import uuid

API = 'http://127.0.0.1:23119/api/users/0/items/'


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def require_key(value):
    if not re.fullmatch(r'[A-Z0-9]{8}', value):
        raise ValueError('Expected a real eight-character Zotero key')
    return value


def fetch_item(key):
    with urllib.request.urlopen(API + require_key(key), timeout=15) as response:
        return json.load(response)


def snapshot(args):
    parent, note = fetch_item(args.parent), fetch_item(args.note)
    if parent['data']['itemType'] in ('note', 'attachment'):
        raise ValueError('Parent must be the bibliographic article item')
    if note['data']['itemType'] != 'note' or note['data'].get('parentItem') != args.parent:
        raise ValueError('Note is not a child of the specified article')
    if note['library']['type'] != 'user':
        raise ValueError('This helper supports personal-library notes only')
    write_json(args.out, {'parent': parent, 'note': note})
    print(json.dumps({'title': parent['data'].get('title'), 'note': args.note}, ensure_ascii=False))


def extract(args):
    from pypdf import PdfReader
    reader = PdfReader(args.pdf)
    if args.page < 1 or args.page > len(reader.pages):
        raise ValueError('PDF physical page is out of range')
    images = reader.pages[args.page - 1].images
    if args.index < 0 or args.index >= len(images):
        raise ValueError(f'Page contains {len(images)} image objects; render if needed')
    image = images[args.index]
    out = Path(args.out)
    if out.suffix.lower().replace('.jpeg', '.jpg') != Path(image.name).suffix.lower().replace('.jpeg', '.jpg'):
        raise ValueError(f'Use original image extension: {Path(image.name).suffix}')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(image.data)
    print(json.dumps({'file': str(out.resolve()), 'size': image.image.size, 'page': args.page}))


def prepare(args):
    from PIL import Image
    snap = read_json(args.snapshot)
    note = snap['note']['data']
    parent = snap['parent']['data']
    if note['itemType'] != 'note' or note.get('parentItem') != parent['key']:
        raise ValueError('Invalid note snapshot relationship')
    text = Path(args.html).read_text(encoding='utf-8-sig')
    if not text.strip() or not re.search(r'<(?:div|p|h[1-6])\b', text):
        raise ValueError('Expected a completed HTML note')
    if re.search(r'<(?:script|iframe|object)\b|\bon\w+\s*=', text, re.I):
        raise ValueError('Active HTML is not supported in a note')
    entries = read_json(args.images) if args.images else []
    images = []
    markers = set()
    for entry in entries:
        marker = entry['marker']
        if not re.fullmatch(r'\{\{FIG[A-Z0-9_-]+\}\}', marker) or text.count(marker) != 1 or marker in markers:
            raise ValueError('Each image needs one unique {{FIG...}} marker')
        markers.add(marker)
        path = Path(entry['file'])
        if not path.is_absolute():
            path = Path(args.images).resolve().parent / path
        data = path.read_bytes()
        with Image.open(path) as image:
            size, fmt = image.size, image.format
            image.verify()
        if fmt not in ('JPEG', 'PNG'):
            raise ValueError('Only original JPEG/PNG images are supported')
        width = int(entry.get('width', min(900, size[0])))
        page = int(entry['page'])
        if width < 1 or page < 1:
            raise ValueError('Width and physical PDF page must be positive')
        images.append(dict(marker=marker, file=str(path.resolve()),
                           caption=str(entry['caption']), pdfKey=require_key(entry['pdfKey']),
                           page=page, width=width, height=max(1, round(width * size[1] / size[0])),
                           mime='image/jpeg' if fmt == 'JPEG' else 'image/png',
                           sha256=hashlib.sha256(data).hexdigest()))
    remaining = text
    for marker in markers:
        remaining = remaining.replace(marker, '')
    if re.search(r'\{\{[^{}]+\}\}', remaining):
        raise ValueError('Unfilled template placeholders remain')
    out = Path(args.out).resolve()
    if out.exists() or out.with_suffix('.result.json').exists():
        raise ValueError('Job path already exists; inspect it or use a fresh job path')
    payload = {'id': str(uuid.uuid4()), 'parentKey': require_key(parent['key']),
               'noteKey': require_key(note['key']), 'expectedHTML': note['note'],
               'html': text, 'images': images, 'resultFile': str(out.with_suffix('.result.json'))}
    write_json(out, payload)
    runner = Path(__file__).with_name('write_note.js').read_text(encoding='utf-8')
    runner = runner.replace('__JOB_FILE_JSON__', json.dumps(str(out), ensure_ascii=False))
    out.with_suffix('.run.js').write_text(runner, encoding='utf-8')
    print(json.dumps({'job': str(out), 'runner': str(out.with_suffix('.run.js')), 'images': len(images)}))


class CanonicalHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tokens = []

    def handle_starttag(self, tag, attrs):
        attrs = [(k, v) for k, v in attrs if not (tag == 'a' and k == 'rel')]
        self.tokens.append(('start', tag, tuple(sorted(attrs))))

    def handle_endtag(self, tag):
        if tag not in ('img', 'br', 'hr', 'meta', 'link', 'input'):
            self.tokens.append(('end', tag))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_data(self, data):
        data = ' '.join(data.split())
        if data:
            self.tokens.append(('text', data))


def canonical(value):
    parser = CanonicalHTML()
    parser.feed(value)
    return parser.tokens


def verify(args):
    job = read_json(args.job)
    result = read_json(job['resultFile'])
    if result.get('id') != job['id'] or result.get('stage') != 'complete':
        raise ValueError('Job has not completed; inspect journal and library before retrying')
    current = fetch_item(job['noteKey'])['data']
    if current.get('parentItem') != job['parentKey']:
        raise ValueError('Parent relationship changed')
    if canonical(current['note']) != canonical(result['html']):
        raise ValueError('Saved HTML differs materially; compare the document before editing')
    keys = re.findall(r'data-attachment-key="([A-Z0-9]{8})"', current['note'])
    for index, item in enumerate(result['images']):
        key = item['key']
        if keys.count(key) != 1:
            raise ValueError('Image reference missing or duplicated')
        data = fetch_item(key)['data']
        if data.get('parentItem') != job['noteKey'] or data.get('contentType') != job['images'][index]['mime']:
            raise ValueError('Image parent/type mismatch')
        with urllib.request.urlopen(API + key + '/file/view/url', timeout=15) as response:
            url = response.read().decode('utf-8').strip()
        if url.startswith('"'):
            url = json.loads(url)
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != 'file' or parsed.netloc not in ('', 'localhost'):
            raise ValueError('Expected a local attachment file URL')
        file = Path(urllib.request.url2pathname(parsed.path))
        if hashlib.sha256(file.read_bytes()).hexdigest() != job['images'][index]['sha256']:
            raise ValueError('Stored image differs from prepared original')
    print(json.dumps({'verified': True, 'note': job['noteKey'], 'newImages': len(result['images']), 'totalImages': len(keys)}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    s = sub.add_parser('snapshot')
    for name in ('parent', 'note', 'out'):
        s.add_argument('--' + name, required=True)
    s.set_defaults(func=snapshot)
    s = sub.add_parser('extract')
    s.add_argument('--pdf', required=True)
    s.add_argument('--page', type=int, required=True)
    s.add_argument('--index', type=int, default=0)
    s.add_argument('--out', required=True)
    s.set_defaults(func=extract)
    s = sub.add_parser('prepare')
    for name in ('snapshot', 'html', 'out'):
        s.add_argument('--' + name, required=True)
    s.add_argument('--images')
    s.set_defaults(func=prepare)
    s = sub.add_parser('verify')
    s.add_argument('--job', required=True)
    s.set_defaults(func=verify)
    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
