import json,time
from codificamed.data import ROOT,catalog,documents
from codificamed.retrieval import Retriever
start=time.perf_counter();c=catalog();r=Retriever(c)
rows=documents('dev');gold_count=sum(len(x['gold']) for x in rows)
covered={str(k):0 for k in [40,60,80]};per_document=[]
for n,row in enumerate(rows):
    candidates=r.retrieve(row['note'],k=80);codes=list(candidates)
    counts={str(k):len(set(row['gold'])&set(codes[:k])) for k in [40,60,80]}
    for k in covered: covered[k]+=counts[k]
    per_document.append({'id':row['id'],'gold':len(row['gold']),'covered':counts})
    if (n+1)%25==0: print(n+1,covered,flush=True)
result={'split':'dev','documents':len(rows),'gold_codes':gold_count,'training_pairs':r.training_pairs,'covered':covered,'recall':{k:v/gold_count for k,v in covered.items()},'seconds':time.perf_counter()-start,'per_document':per_document}
path=ROOT/'results/v2';path.mkdir(exist_ok=True)
(path/'retrieval_dev.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print({k:v for k,v in result.items() if k!='per_document'},flush=True)
