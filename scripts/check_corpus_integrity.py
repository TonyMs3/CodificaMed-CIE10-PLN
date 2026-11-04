"""Comprueba el gold y la muestra contra el ZIP descargado, sin modificar datos."""
import hashlib,json,zipfile
from codificamed.data import ROOT,DATA

def main():
    manifest=json.loads((DATA/'manifest.json').read_text(encoding='utf-8'))
    archive=DATA/'corpus.zip';archive_hash=hashlib.sha256(archive.read_bytes()).hexdigest()
    plan=json.loads((ROOT/'results/v2/final_manifest.json').read_text(encoding='utf-8'))
    selected={row['id']+'.txt' for row in plan['documents']}
    checked=[]
    with zipfile.ZipFile(archive) as zipped:
        for name in zipped.namelist():
            base=name.rsplit('/',1)[-1]
            wanted=base in {'trainD.tsv','devD.tsv','testD.tsv','trainX.tsv'} or ('/test/text_files/' in name and base in selected)
            if not wanted: continue
            original=zipped.read(name);current=(DATA/'corpus'/name).read_bytes()
            checked.append({'member':name,'sha256':hashlib.sha256(current).hexdigest(),'unchanged':current==original})
    result={'archive_sha256_matches_download_manifest':archive_hash==manifest['corpus']['sha256'],'checked_files':checked,'unchanged':len(checked)==9 and all(row['unchanged'] for row in checked)}
    (ROOT/'results/v2/corpus_integrity.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Archivos gold/entrenamiento y notas finales sin cambios:',result['unchanged'],'archivos:',len(checked))
    if not result['unchanged'] or not result['archive_sha256_matches_download_manifest']: raise SystemExit(1)
if __name__=='__main__': main()
