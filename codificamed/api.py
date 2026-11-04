"""Límite conservador de generaciones externas; nunca registra credenciales."""
import hashlib,json,os,time
from datetime import datetime,timezone
from pathlib import Path
from .data import ROOT
class ProviderError(ValueError): pass

def ledger_path(): return Path(os.getenv('CODIFICAMED_API_LEDGER',str(ROOT/'results/api_usage.json')))
def reserve(model,message):
    path=ledger_path();path.parent.mkdir(parents=True,exist_ok=True)
    lock=path.with_suffix('.lock')
    try: handle=lock.open('x')
    except FileExistsError: raise ProviderError('Hay otra solicitud externa en curso. Espera a que termine.') from None
    try:
        ledger=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'events':[]}
        today=datetime.now(timezone.utc).date().isoformat()
        events=[e for e in ledger['events'] if e['recorded_at'].startswith(today)]
        if any(e.get('status_code')==429 for e in events): raise ProviderError('Se alcanzó una cuota gratuita. Se conservan los resultados; no se repetirán solicitudes hoy.')
        limit=int(os.getenv('GEMINI_MAX_DAILY_REQUESTS','12'))
        if len(events)>=limit: raise ProviderError(f'Límite preventivo local de {limit} generaciones por día UTC alcanzado. No es una cuota oficial del proveedor; consulta el README antes de ajustar GEMINI_MAX_DAILY_REQUESTS.')
        if events:
            wait=max(0,15-(time.time()-events[-1]['epoch']))
            if wait: time.sleep(wait)
        event={'recorded_at':datetime.now(timezone.utc).isoformat(),'epoch':time.time(),'model':model,'prompt_sha256':hashlib.sha256(message.encode()).hexdigest(),'status':'reserved'}
        ledger['events'].append(event);path.write_text(json.dumps(ledger,ensure_ascii=False,indent=2),encoding='utf-8')
        return path,len(ledger['events'])-1,handle,lock
    except Exception:
        handle.close();lock.unlink(missing_ok=True);raise

def finish(ticket,status,status_code=None):
    path,index,handle,lock=ticket
    try:
        ledger=json.loads(path.read_text(encoding='utf-8'));ledger['events'][index].update(status=status,status_code=status_code)
        path.write_text(json.dumps(ledger,ensure_ascii=False,indent=2),encoding='utf-8')
    finally: handle.close();lock.unlink(missing_ok=True)

def generate(model,message,schema):
    from google import genai
    from google.genai import types
    ticket=reserve(model,message)
    try:
        with genai.Client(api_key=os.environ['GEMINI_API_KEY'],http_options=types.HttpOptions(timeout=180000,retry_options=types.HttpRetryOptions(attempts=1))) as client:
            response=client.models.generate_content(model=model,contents=message,config=types.GenerateContentConfig(temperature=0,response_mime_type='application/json',response_json_schema=schema))
        text=response.text
        if not text: raise ProviderError('Gemini no devolvió contenido final utilizable.')
    except Exception as error:
        code=getattr(error,'code',None);finish(ticket,'failed',code)
        if isinstance(error,ProviderError): raise
        explanation={429:'Cuota gratuita alcanzada. Se conservan los resultados.',403:'El proyecto no autoriza este modelo.',404:'El modelo configurado no está disponible.',400:'El proveedor rechazó la solicitud o su esquema JSON.'}.get(code,'No se pudo completar la solicitud externa.')
        raise ProviderError(explanation+f' Estado: {code or type(error).__name__}. No se registran credenciales.') from None
    finish(ticket,'success',200)
    return text
