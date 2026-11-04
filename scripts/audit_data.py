import json,urllib.request
from codificamed.data import DATA,catalog,documents
c=catalog();audit={}
for split in ['train','dev','test']:
    rows=documents(split)
    absent=sorted({code for row in rows for code in row['gold'] if code not in c})
    audit[split]={'documents':len(rows),'distinct_gold_codes':len({code for row in rows for code in row['gold']}),'annotations':sum(len(row['gold']) for row in rows),'codes_absent_from_catalog':absent,'annotations_absent_from_catalog':sum(code not in c for row in rows for code in row['gold'])}
for record in ['3837305','3632523']:
    try:
        with urllib.request.urlopen('https://zenodo.org/api/records/'+record,timeout=30) as response: metadata=json.load(response)
        audit[record]={'title':metadata['metadata']['title'],'license':metadata['metadata'].get('license'),'doi':metadata.get('doi')}
    except Exception as error: audit[record]={'metadata_error':str(error)}
(DATA/'audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:{n:v for n,v in x.items() if n!='codes_absent_from_catalog'} for k,x in audit.items()},ensure_ascii=False,indent=2))
