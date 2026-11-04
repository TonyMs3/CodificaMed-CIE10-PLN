"""Evaluación multietiqueta reproducible con reanudación sin mezclar configuraciones."""
import argparse,csv,hashlib,json,os,time
from pathlib import Path
from collections import Counter
from .data import ROOT,catalog,documents
from .pipeline import Retriever,process
from .experiment import fingerprint,load_plan

def metrics(gold,pred):
    if len(gold)!=len(pred): raise ValueError('Gold y predicciones deben tener igual número de documentos')
    tp=sum(len(set(g)&set(p)) for g,p in zip(gold,pred));fp=sum(len(set(p)-set(g)) for g,p in zip(gold,pred));fn=sum(len(set(g)-set(p)) for g,p in zip(gold,pred))
    docf=[2*len(set(g)&set(p))/(len(set(g))+len(set(p))) if len(set(g))+len(set(p)) else 1 for g,p in zip(gold,pred)]
    return dict(tp=tp,fp=fp,fn=fn,micro_precision=tp/(tp+fp) if tp+fp else 0,micro_recall=tp/(tp+fn) if tp+fn else 0,micro_f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0,macro_document_f1=sum(docf)/len(docf) if docf else 0,documents=len(gold),gold_codes=sum(len(set(g)) for g in gold),predicted_codes=sum(len(set(p)) for p in pred))

def summarize(rows,predictions,backend,split,pipeline_hash,selection):
    summary=metrics([r['gold'] for r in predictions],[r['predicted'] for r in predictions])
    identity=json.dumps([{'id':r['id'],'note':r['note'],'gold':r['gold']} for r in rows],ensure_ascii=False,sort_keys=True)
    summary.update(backend=backend,model=os.getenv('OLLAMA_MODEL','qwen3.5:4b') if backend=='local' else os.getenv('GEMINI_MODEL'),split=split,selection=selection,sample_sha256=hashlib.sha256(identity.encode()).hexdigest(),pipeline_sha256=pipeline_hash,seconds=sum(r['seconds'] for r in predictions),candidate_k=40,temperature=0,local_context=4096,local_output_limit=1600)
    summary['rejected_by_reason']=dict(Counter(m['motivo'] for r in predictions for m in r['rechazadas']))
    summary['candidate_gold_covered']=sum(len(set(r['gold'])&set(r['candidatos'])) for r in predictions)
    summary['negation_errors']='No anotados por CodiEsp-D'
    if split=='sinteticos':
        expected=[{(m['codigo'],m['estado']) for m in r['mentions']} for r in rows]
        predicted=[{(m['codigo'],m['estado']) for m in r['menciones']} for r in predictions]
        summary['mention_state_metrics']=metrics(expected,predicted)
        summary['state_exact_documents']=sum(g==p for g,p in zip(expected,predicted))
        summary['negation_errors']=sum(1 for g,p in zip(expected,predicted) for code,status in p if status=='confirmado' and (code,'confirmado') not in g and any((code,s) in g for s in ['negado','descartado']))
        summary['suspicions_as_confirmed']=sum(1 for g,p in zip(expected,predicted) for code,status in p if status=='confirmado' and (code,'confirmado') not in g and (code,'sospechoso') in g)
        summary['incorrect_state_pairs']=sum(len(p-g) for g,p in zip(expected,predicted))
        summary['negative_mention_omissions']=sum(sum(state in {'negado','descartado'} for code,state in g-p) for g,p in zip(expected,predicted))
    return summary

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--backend',choices=['local','externo'],required=True)
    parser.add_argument('--split',choices=['dev','test'],default='dev')
    parser.add_argument('--limit',type=int,default=2)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--synthetic',action='store_true')
    parser.add_argument('--synthetic-file',type=Path)
    parser.add_argument('--manifest',type=Path)
    parser.add_argument('--resume',action='store_true')
    parser.add_argument('--allow-api',action='store_true')
    args=parser.parse_args()
    if args.limit<1: parser.error('--limit debe ser positivo')
    if args.backend=='externo' and (not args.allow_api or args.limit>5): parser.error('API: requiere --allow-api y máximo 5 casos por ejecución corta')
    if args.manifest and (args.synthetic or args.synthetic_file): parser.error('No mezcles plan CodiEsp con casos ficticios')
    retriever=Retriever(catalog());synthetic=args.synthetic or args.synthetic_file is not None
    selection='Primeros N IDs ordenados' if not synthetic else 'Controles ficticios de desarrollo, orden fijo; no validación clínica independiente'
    if args.manifest:
        plan,rows=load_plan(args.manifest,args.split,retriever);selection=plan['selection']
    elif synthetic:
        rows=json.loads((args.synthetic_file or ROOT/'tests/fixtures/sinteticos.json').read_text(encoding='utf-8-sig'))
        if not all(row.get('sinteticos') is True for row in rows): raise ValueError('Todos los controles deben estar marcados como sintéticos')
    else: rows=documents(args.split)
    rows=rows[:args.limit];pipeline_hash=fingerprint();predictions=[]
    args.output.parent.mkdir(parents=True,exist_ok=True);checkpoint=args.output.with_suffix('.partial.json')
    if args.output.exists(): raise ValueError('La salida ya existe. Conserva resultados anteriores y selecciona otra ruta.')
    if args.resume and checkpoint.exists():
        saved=json.loads(checkpoint.read_text(encoding='utf-8'))
        model=os.getenv('OLLAMA_MODEL','qwen3.5:4b') if args.backend=='local' else os.getenv('GEMINI_MODEL')
        if saved.get('backend')!=args.backend or saved.get('model')!=model or saved.get('pipeline_sha256')!=pipeline_hash: raise ValueError('Backend, modelo o pipeline distinto al checkpoint')
        predictions=saved['predictions']
        if len(predictions)>len(rows): raise ValueError('Muestra incompatible con checkpoint')
        for previous,row in zip(predictions,rows):
            if previous['id']!=row['id'] or previous['gold']!=row['gold'] or previous['note_sha256']!=hashlib.sha256(row['note'].encode()).hexdigest() or previous['candidatos']!=retriever.retrieve(row['note']): raise ValueError('IDs, texto, gold o candidatos distintos al checkpoint')
        print('Reanudando:',len(predictions),'documentos completados',flush=True)
    elif checkpoint.exists(): raise ValueError('Existe una ejecución parcial: añade --resume para conservar sus casos')
    def save_partial(error=None):
        checkpoint.write_text(json.dumps({'status':'incomplete','backend':args.backend,'model':os.getenv('OLLAMA_MODEL','qwen3.5:4b') if args.backend=='local' else os.getenv('GEMINI_MODEL'),'pipeline_sha256':pipeline_hash,'planned_documents':len(rows),'error_type':error,'predictions':predictions},ensure_ascii=False,indent=2),encoding='utf-8')
    for row in rows[len(predictions):]:
        start=time.perf_counter()
        try: result=process(row['note'],retriever,args.backend)
        except Exception as error:
            save_partial(type(error).__name__);raise
        predicted=sorted({m['codigo'] for m in result['menciones'] if m['estado']=='confirmado'})
        predictions.append(dict(id=row['id'],gold=row['gold'],note_sha256=hashlib.sha256(row['note'].encode()).hexdigest(),predicted=predicted,false_positives=sorted(set(predicted)-set(row['gold'])),false_negatives=sorted(set(row['gold'])-set(predicted)),seconds=time.perf_counter()-start,**result))
        save_partial();print(row['id'],round(predictions[-1]['seconds'],2),flush=True)
    summary=summarize(rows,predictions,args.backend,'sinteticos' if synthetic else args.split,pipeline_hash,selection)
    args.output.write_text(json.dumps({'summary':summary,'predictions':predictions},ensure_ascii=False,indent=2),encoding='utf-8')
    with args.output.with_suffix('.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=['id','gold','predicted','false_positives','false_negatives','seconds']);writer.writeheader()
        for row in predictions: writer.writerow({k:row[k] for k in writer.fieldnames})
    checkpoint.unlink(missing_ok=True);print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
