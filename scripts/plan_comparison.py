"""Selecciona cinco casos nuevos de test; no consulta predicciones de ningún backend."""
import hashlib,json
from codificamed.data import ROOT,catalog,documents
from codificamed.retrieval import Retriever,DEFAULT_K
from codificamed.pipeline import prompt
from codificamed.experiment import fingerprint
SEED='CodificaMed-2026-11-03-v2'
RETIRED={'S0004-06142005000500011-1','S0004-06142005000900014-1','S0004-06142006000100010-1'}

def main():
    destination=ROOT/'results/v2/final_manifest.json'
    if destination.exists(): raise SystemExit('El plan ya existe. No se sobrescribe una selección congelada.')
    rows=[r for r in documents('test') if r['id'] not in RETIRED and len(r['note'])<=6000]
    rows=sorted(rows,key=lambda r:(len(r['gold']),r['id']))
    retriever=Retriever(catalog());chosen=[]
    for stratum in range(5):
        group=rows[len(rows)*stratum//5:len(rows)*(stratum+1)//5]
        ordered=sorted(group,key=lambda r:hashlib.sha256((SEED+r['id']).encode()).hexdigest())
        for row in ordered:
            candidates=retriever.retrieve(row['note'])
            if len(prompt(row['note'],candidates).encode())>14000: continue
            chosen.append({'id':row['id'],'gold':row['gold'],'note_sha256':hashlib.sha256(row['note'].encode()).hexdigest(),'stratum':stratum+1,'gold_count':len(row['gold']),'note_characters':len(row['note']),'candidates':candidates})
            break
        else: raise ValueError('No hay documento con presupuesto válido en un estrato')
    plan={'version':2,'split':'test','seed':SEED,'selection':'Cinco quintiles por cantidad de códigos gold; un documento por quintil con menor SHA256(seed+ID), excluyendo tres casos ya examinados y notas >6000 caracteres o prompt >14000 bytes. Sin consulta a predicciones. Piloto pequeño, no representatividad estadística.','eligible_documents':len(rows),'retired_ids':sorted(RETIRED),'candidate_k':DEFAULT_K,'pipeline_sha256':fingerprint(),'documents':chosen}
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in plan.items() if k!='documents'},ensure_ascii=False,indent=2))
    print([{k:r[k] for k in ['id','stratum','gold_count','note_characters']} for r in chosen])
if __name__=='__main__': main()
