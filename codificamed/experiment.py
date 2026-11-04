"""Planes y huellas para impedir cambiar casos o pipeline durante la comparación."""
import hashlib,json
from .data import ROOT,DATA,documents

def fingerprint():
    paths=[ROOT/'codificamed'/name for name in ['pipeline.py','retrieval.py','data.py']]
    paths+=list((DATA/'catalogo').rglob('codiesp-D_codes.tsv'))
    paths+=list((DATA/'corpus').rglob('trainX.tsv'))
    digest=hashlib.sha256()
    for path in paths: digest.update(path.name.encode());digest.update(path.read_bytes())
    return digest.hexdigest()

def load_plan(path,split,retriever):
    plan=json.loads(path.read_text(encoding='utf-8'))
    if plan['split']!=split: raise ValueError('El split del plan no coincide')
    if plan['pipeline_sha256']!=fingerprint(): raise ValueError('El pipeline o sus recursos cambiaron desde la selección de la muestra')
    index={row['id']:row for row in documents(split)}
    rows=[]
    for selected in plan['documents']:
        row=index[selected['id']]
        if hashlib.sha256(row['note'].encode()).hexdigest()!=selected['note_sha256'] or row['gold']!=selected['gold']:
            raise ValueError('El texto o gold cambió desde la selección')
        if retriever.retrieve(row['note'])!=selected['candidates']: raise ValueError('Los candidatos difieren del plan congelado')
        rows.append(row)
    return plan,rows
