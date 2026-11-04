"""Compara exclusivamente documentos comunes con idénticos gold, texto y candidatos."""
import argparse,json,csv
from pathlib import Path
from codificamed.evaluate import metrics

def load(path):
    if not path.exists() and path.with_suffix('.partial.json').exists(): path=path.with_suffix('.partial.json')
    return json.loads(path.read_text(encoding='utf-8'))

def compare(left,right,fixtures=None):
    a=left.get('summary',left);b=right.get('summary',right)
    if a['backend']!='local' or b['backend']!='externo': raise ValueError('Se requiere local y externo, en ese orden')
    if not a.get('pipeline_sha256') or a['pipeline_sha256']!=b.get('pipeline_sha256'): raise ValueError('No comparten la misma versión congelada de pipeline y recursos')
    ar={r['id']:r for r in left['predictions']};br={r['id']:r for r in right['predictions']}
    ids=[row['id'] for row in left['predictions'] if row['id'] in br]
    for doc_id in ids:
        x,y=ar[doc_id],br[doc_id]
        if x['gold']!=y['gold'] or x['note_sha256']!=y['note_sha256'] or x['candidatos']!=y['candidatos']: raise ValueError('Texto, gold o candidatos diferentes: '+doc_id)
    result={'status':'complete' if 'summary' in left and 'summary' in right else 'partial','paired_ids':ids,'paired_documents':len(ids),'pipeline_sha256':a['pipeline_sha256'],'planned_local':a.get('documents',a.get('planned_documents')),'planned_external':b.get('documents',b.get('planned_documents'))}
    if not ids:
        result['status']='unavailable';return result
    for name,source,index in [('local',a,ar),('externo',b,br)]:
        rows=[index[i] for i in ids]
        summary=metrics([r['gold'] for r in rows],[r['predicted'] for r in rows])
        summary.update(model=source['model'],seconds=sum(r['seconds'] for r in rows),false_positives={r['id']:r['false_positives'] for r in rows},false_negatives={r['id']:r['false_negatives'] for r in rows},rejected=[dict(id=r['id'],**m) for r in rows for m in r['rechazadas']],negation_errors='No anotados por CodiEsp-D')
        if fixtures is not None:
            expected=[{(m['codigo'],m['estado']) for m in fixtures[i]['mentions']} for i in ids]
            predicted=[{(m['codigo'],m['estado']) for m in index[i]['menciones']} for i in ids]
            summary['state_metrics']=metrics(expected,predicted)
            summary['state_exact_documents']=sum(g==p for g,p in zip(expected,predicted))
            summary['negation_errors']=sum(1 for g,p in zip(expected,predicted) for code,state in p if state=='confirmado' and (code,state) not in g and any((code,s) in g for s in ['negado','descartado']))
            summary['incorrect_state_pairs']=sum(len(p-g) for g,p in zip(expected,predicted))
            summary['negative_mention_omissions']=sum(sum(state in {'negado','descartado'} for code,state in g-p) for g,p in zip(expected,predicted))
            summary['suspected_mention_omissions']=sum(sum(state=='sospechoso' for code,state in g-p) for g,p in zip(expected,predicted))
        result[name]=summary
    return result

def main():
    parser=argparse.ArgumentParser();parser.add_argument('local',type=Path);parser.add_argument('externo',type=Path);parser.add_argument('--output',type=Path);parser.add_argument('--synthetic-file',type=Path)
    args=parser.parse_args();fixtures={r['id']:r for r in json.loads(args.synthetic_file.read_text(encoding='utf-8-sig'))} if args.synthetic_file else None
    result=compare(load(args.local),load(args.externo),fixtures)
    if args.output:
        args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        if result['paired_documents']:
            with args.output.with_suffix('.csv').open('w',encoding='utf-8-sig',newline='') as stream:
                fields=['backend','model','documents','tp','fp','fn','micro_precision','micro_recall','micro_f1','seconds'];writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
                for backend in ['local','externo']: writer.writerow({'backend':backend,**{key:result[backend][key] for key in fields[1:]}})
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
