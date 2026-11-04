"""Comprueba disponibilidad y generación con una nota ficticia; consume una solicitud."""
import json,os,time
from dotenv import load_dotenv
from google import genai
from google.genai import types
from codificamed.data import ROOT,catalog
from codificamed.pipeline import infer,validate
load_dotenv(ROOT/'.env',encoding='utf-8-sig',override=True)
result={'key_loaded':bool(os.getenv('GEMINI_API_KEY')),'model':os.getenv('GEMINI_MODEL'),'source':'Configuración privada en .env; credencial excluida'}
try:
    with genai.Client(api_key=os.environ['GEMINI_API_KEY'],http_options=types.HttpOptions(timeout=60000,retry_options=types.HttpRetryOptions(attempts=1))) as client:
        model=client.models.get(model=os.environ['GEMINI_MODEL'])
        result['availability']={'name':model.name,'supported_actions':model.supported_actions}
    from codificamed.pipeline import prompt
    note='Hipertensión esencial confirmada. Se descarta neumonía no especificada.'
    c=catalog(); candidates={code:c[code] for code in ['I10','J18.9']}
    start=time.perf_counter();out=infer('externo',prompt(note,candidates))
    valid,rejected=validate(note,out,candidates,os.environ['GEMINI_MODEL'])
    result.update(status='success',seconds=time.perf_counter()-start,note=note,menciones=valid,rechazadas=rejected)
except Exception as error:
    result.update(status='failed',error_type=type(error).__name__,status_code=getattr(error,'code',None))
(ROOT/'results/gemini_initial_smoke.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))

raise SystemExit(0 if result['status']=='success' else 1)
