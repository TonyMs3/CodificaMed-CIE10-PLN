from pathlib import Path
import csv, hashlib, json, urllib.request, zipfile
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SOURCES = {"corpus": "https://zenodo.org/records/3837305/files/codiesp.zip?download=1", "catalogo": "https://zenodo.org/records/3632523/files/codiesp_codes.zip?download=1"}
def normalize(code):
    return code.strip().upper()
def acquire():
    DATA.mkdir(exist_ok=True)
    manifest = {}
    for name, url in SOURCES.items():
        archive = DATA / (name + '.zip')
        if not archive.exists():
            with urllib.request.urlopen(url, timeout=90) as response:
                payload=response.read(30_000_001)
            if len(payload)>30_000_000: raise ValueError('Descarga supera límite de 30 MB')
            temporary=archive.with_suffix('.part')
            temporary.write_bytes(payload)
            temporary.replace(archive)
        target = DATA / name
        target.mkdir(exist_ok=True)
        with zipfile.ZipFile(archive) as z:
            for member in z.infolist():
                path = (target / member.filename).resolve()
                if not path.is_relative_to(target.resolve()):
                    raise ValueError('Ruta insegura en ZIP')
            z.extractall(target)
            manifest[name] = {'url':url, 'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(), 'files':z.namelist()}
    (DATA/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    return manifest
def catalog():
    paths = list((DATA/'catalogo').rglob('codiesp-D_codes.tsv'))
    if len(paths)!=1:
        raise ValueError('Descarga el catálogo: python -m scripts.prepare')
    with paths[0].open(encoding='utf-8-sig',newline='') as f:
        rows = list(csv.reader(f,delimiter='\t'))
    if rows[0][0].lower() == 'code': rows=rows[1:]
    if not rows or any(len(r)!=3 for r in rows): raise ValueError('Catálogo TSV: se esperaban 3 columnas')
    return {normalize(r[0]):r[1] for r in rows}
def documents(split):
    if split not in {'train','dev','test'}: raise ValueError('Split inválido')
    base = DATA/'corpus'
    gold = [p for p in base.rglob('*') if p.is_file() and p.name.lower()==f'{split}d.tsv']
    if len(gold)!=1: raise ValueError(f'Gold D no localizado: {split}')
    labels={}
    with gold[0].open(encoding='utf-8-sig') as f:
        for row in csv.reader(f,delimiter='\t'):
            if len(row)!=2: raise ValueError('Gold D: se esperaban 2 columnas')
            if row[0].lower()=='articleid': continue
            labels.setdefault(row[0],set()).add(normalize(row[1]))
    result=[]
    text_index={}
    for path in base.rglob('*.txt'):
        if split in path.parts and 'text_files' in path.parts:
            text_index.setdefault(path.stem,[]).append(path)
    for doc_id,codes in sorted(labels.items()):
        paths=text_index.get(doc_id,[])
        if len(paths)!=1: raise ValueError(f'Texto ambiguo o ausente: {doc_id}')
        result.append({'id':doc_id,'note':paths[0].read_text(encoding='utf-8'),'gold':sorted(codes)})
    return result
