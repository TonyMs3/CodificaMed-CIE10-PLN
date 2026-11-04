import hashlib,html,json,os
import streamlit as st
from codificamed.data import ROOT,catalog
from codificamed.pipeline import Retriever,process
from dotenv import load_dotenv
load_dotenv(ROOT/'.env',encoding='utf-8-sig',override=True)
st.set_page_config(page_title='CodificaMed',layout='wide')
st.title('CodificaMed')
st.caption('Asistencia académica de codificación CIE-10-ES 2018. Requiere revisión profesional. No realiza diagnósticos médicos.')
st.info('Introduce exclusivamente casos ficticios o textos públicos de CodiEsp. No introduzcas historias clínicas reales ni datos personales.')
@st.cache_resource(show_spinner='Preparando catálogo…')
def resources(): return Retriever(catalog())
try: retriever=resources()
except Exception as error:
    st.error(str(error));st.stop()
examples=json.loads((ROOT/'tests/fixtures/sinteticos.json').read_text(encoding='utf-8-sig'))
backend=st.selectbox('Modelo',['Ollama (local)','API externa (Gemini)'])
if backend.startswith('API') and (not os.getenv('GEMINI_API_KEY') or not os.getenv('GEMINI_MODEL')): st.warning('API no configurada. Completa GEMINI_API_KEY en el archivo .env del proyecto.')
example=st.selectbox('Ejemplo ficticio',['Escribir nota']+[r['id']+' · '+r['note'] for r in examples])
if st.button('Cargar ejemplo') and example!='Escribir nota':
    st.session_state['note']=next(r['note'] for r in examples if example.startswith(r['id']))
note=st.text_area('Nota clínica',key='note',height=200,max_chars=30000)
consent=st.checkbox('Confirmo que el texto es ficticio o procede de CodiEsp público.')
if st.button('Procesar',type='primary',disabled=not consent):
    try:
        with st.spinner('Analizando nota…'):
            result=process(note,retriever,'local' if backend.startswith('Ollama') else 'externo')
        st.session_state['result']=(note,backend,result)
    except Exception as error: st.error('No se pudo procesar la nota: '+str(error))
if 'result' in st.session_state:
    original,used_backend,result=st.session_state['result']
    if original!=note or used_backend!=backend:
        st.info('La nota o el modelo cambió. Pulsa Procesar para actualizar los resultados.');st.stop()
    st.subheader('Sugerencias para revisión')
    st.caption('Las menciones negadas, descartadas o sospechosas no cuentan como diagnósticos confirmados. Las menciones contradictorias requieren revisión humana.')
    if not result['menciones']: st.write('Sin sugerencias verificables.')
    for index,m in enumerate(result['menciones']):
        with st.container(border=True):
            st.write(f"{m['codigo']} · {m['descripcion']} · {m['estado']}")
            st.markdown('<mark>'+html.escape(m['evidencia'])+'</mark>',unsafe_allow_html=True)
            st.caption(f"Posición {m['inicio']}:{m['fin']} · {m['modelo']}")
            review_identity=[original,used_backend,m['modelo'],m['codigo'],m['evidencia'],m['inicio'],m['fin'],m['estado'],index]
            review_key=hashlib.sha256(json.dumps(review_identity,ensure_ascii=False).encode('utf-8')).hexdigest()
            st.checkbox('Revisado por el codificador',key=f'review_{review_key}')
    if result['rechazadas']: st.warning(f"{len(result['rechazadas'])} predicciones rechazadas por código o evidencia inválidos.")
    st.download_button('Descargar resultado JSON',json.dumps(result,ensure_ascii=False,indent=2),'codificamed_resultado.json','application/json')

