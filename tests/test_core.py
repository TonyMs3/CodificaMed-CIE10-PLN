import json
from pathlib import Path
import pytest
from codificamed.pipeline import Mention,Output,Retriever,process,state,validate,sentences
from codificamed.data import normalize,catalog,documents
from codificamed.evaluate import metrics
CAT={'I10':'Hipertensión esencial','J18.9':'Neumonía no especificada','E11.9':'Diabetes mellitus tipo 2 sin complicaciones'}
@pytest.mark.parametrize('text,expected',[
('Se descarta neumonía','descartado'),('Niega diabetes','negado'),('Probable neumonía','sospechoso'),
('Hipertensión esencial confirmada','confirmado'),('Diabetes mellitus tipo 2 sin complicaciones','confirmado'),('Neumonía no especificada','confirmado')])
def test_state(text,expected): assert state(text)==expected

def test_normalize(): assert normalize(' e11.9 ' )=='E11.9'
def test_literal_and_catalog():
    output=Output(menciones=[Mention(codigo='XXX',estado='confirmado',evidencia='Hipertensión'),Mention(codigo='I10',estado='confirmado',evidencia='inventada')])
    valid,rejected=validate('Hipertensión',output,CAT,'simulado')
    assert not valid and len(rejected)==2

def test_cropped_negation():
    valid,_=validate('Se descarta neumonía.',Output(menciones=[Mention(codigo='J18.9',estado='confirmado',evidencia='neumonía')]),CAT,'simulado')
    assert valid[0]['estado']=='descartado'
def test_contradictions():
    note='Probable neumonía. Se descarta neumonía.'
    out=Output(menciones=[Mention(codigo='J18.9',estado='sospechoso',evidencia='Probable neumonía'),Mention(codigo='J18.9',estado='confirmado',evidencia='Se descarta neumonía')])
    valid,_=validate(note,out,CAT,'simulado')
    assert [m['estado'] for m in valid]==['sospechoso','descartado']
def test_contrast():
    note='Niega neumonía pero hipertensión esencial confirmada.'
    out=Output(menciones=[Mention(codigo='I10',estado='confirmado',evidencia='hipertensión esencial confirmada')])
    assert validate(note,out,CAT,'mock')[0][0]['estado']=='confirmado'
def test_metrics():
    m=metrics([['A','B'],['C']],[['A','A','X'],[]])
    assert (m['tp'],m['fp'],m['fn'])==(1,1,2)
    assert m['micro_f1']==pytest.approx(.4)
def test_mock_pipeline_without_api(monkeypatch):
    monkeypatch.delenv('GEMINI_API_KEY',raising=False)
    note='Hipertensión esencial confirmada.'
    result=process(note,Retriever(CAT),runner=lambda b,p:Output(menciones=[Mention(codigo='I10',estado='confirmado',evidencia=note)]))
    assert result['menciones'][0]['inicio']==0
    assert result['menciones'][0]['fin']==len(note)
def test_missing_api(monkeypatch):
    from codificamed.pipeline import infer
    monkeypatch.delenv('GEMINI_API_KEY',raising=False)
    with pytest.raises(ValueError,match='API no configurada'): infer('externo','nota')
def test_empty():
    with pytest.raises(ValueError): process('',Retriever(CAT))
def test_real_catalog_and_corpus():
    c=catalog()
    assert len(c)>50000
    assert all(code in c for code in CAT)
    assert [len(documents(s)) for s in ['train','dev','test']]==[500,250,250]
    assert all(row['gold'] for row in documents('test'))  # Se conservan las referencias, incluso los códigos ausentes del catálogo.
def test_retrieval():
    candidates=Retriever(CAT).retrieve('Hipertensión esencial',k=1)
    assert list(candidates)==['I10']
def test_fixture_codes():
    fixtures=json.loads(Path('tests/fixtures/sinteticos.json').read_text(encoding='utf-8-sig'))
    assert len(fixtures)>=7 and all(r['sinteticos'] for r in fixtures)
    assert all(m['codigo'] in catalog() for r in fixtures for m in r['mentions'])

def test_gemini_sdk_mock(monkeypatch,tmp_path):
    monkeypatch.setenv('CODIFICAMED_API_LEDGER',str(tmp_path/'usage.json'))
    import sys,types
    from codificamed.pipeline import infer
    monkeypatch.setenv('GEMINI_API_KEY','ficticia-no-es-una-clave')
    monkeypatch.setenv('GEMINI_MODEL','modelo-simulado')
    class Client:
        def __init__(self,**kwargs): self.models=self
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def generate_content(self,**kwargs):
            assert kwargs['model']=='modelo-simulado'
            return types.SimpleNamespace(text='{"menciones":[]}')
    import google
    import google.genai
    monkeypatch.setattr(google.genai,'Client',Client)
    assert infer('externo','nota sintética').menciones==[]

def test_streamlit_initial_and_mock_processing(monkeypatch):
    from streamlit.testing.v1 import AppTest
    import codificamed.pipeline as pipeline
    monkeypatch.setattr(pipeline,'infer',lambda backend,message:Output(menciones=[Mention(codigo='I10',estado='confirmado',evidencia='Hipertensión esencial confirmada.')]))
    app=AppTest.from_file(Path('app.py').resolve(),default_timeout=90).run()
    assert not app.exception
    app.text_area[0].set_value('Hipertensión esencial confirmada.')
    app.checkbox[0].check().run()
    app.button[1].click().run()
    assert not app.exception
    assert any('I10' in element.value for element in app.markdown)
    app.text_area[0].set_value('Se descarta neumonía.').run()
    assert any('La nota o el modelo cambió' in element.value for element in app.info)
    assert not any('I10 ·' in element.value for element in app.markdown)

def test_review_state_is_specific_to_model_code_and_evidence(monkeypatch):
    from streamlit.testing.v1 import AppTest
    import codificamed.pipeline as pipeline
    monkeypatch.setattr(pipeline,'Retriever',lambda _:object())
    note='Hipertensión esencial confirmada. Diabetes mellitus tipo 2 confirmada.'
    suggestion={'codigo':'I10','descripcion':CAT['I10'],'estado':'confirmado','evidencia':'Hipertensión esencial confirmada.','inicio':0,'fin':32,'modelo':'qwen-prueba'}
    def fake_process(note,retriever,backend):
        return {'menciones':[dict(suggestion)],'rechazadas':[]}
    monkeypatch.setattr(pipeline,'process',fake_process)
    app=AppTest.from_file(Path('app.py').resolve(),default_timeout=90).run()
    app.text_area[0].set_value(note)
    app.checkbox[0].check().run()
    app.button[1].click().run()
    review=lambda:next(c for c in app.checkbox if c.label=='Revisado por el codificador')
    assert not app.exception
    key=review().key
    review().check().run()
    assert review().value
    app.run()
    assert review().value  # Una misma sugerencia conserva la revisión en la sesión.
    app.selectbox[0].select('API externa (Gemini)').run()
    suggestion['modelo']='gemini-prueba'
    app.button[1].click().run()
    assert not app.exception and review().key!=key and not review().value
    for changes in [
        {'modelo':'gemini-otra-version'},
        {'codigo':'E11.9'},
        {'evidencia':'Diabetes mellitus tipo 2 confirmada.','inicio':33,'fin':len(note)},
    ]:
        review().check().run()
        key=review().key
        suggestion.update(changes)
        app.button[1].click().run()
        assert not app.exception and review().key!=key and not review().value


def test_context_budget():
    with pytest.raises(ValueError,match='presupuesto'):
        process('hipertensión '*2000,Retriever(CAT),runner=lambda b,p:Output(menciones=[]))

def test_explicit_confirmed_vetoes_spurious_negation():
    note='Diabetes mellitus tipo 2 sin complicaciones confirmada.'
    out=Output(menciones=[Mention(codigo='E11.9',estado='negado',evidencia=note)])
    assert validate(note,out,CAT,'mock')[0][0]['estado']=='confirmado'

def test_synthetic_candidate_coverage():
    fixtures=json.loads(Path('tests/fixtures/sinteticos.json').read_text(encoding='utf-8-sig'))
    retriever=Retriever(catalog())
    for row in fixtures:
        assert {m['codigo'] for m in row['mentions']} <= set(retriever.retrieve(row['note']))

def test_evaluation_resume_preserves_completed_cases(monkeypatch,tmp_path):
    import sys
    import codificamed.evaluate as evaluation
    rows=[{'id':'A','note':'Hipertensión esencial confirmada.','gold':['I10']},{'id':'B','note':'Hipertensión esencial.','gold':['I10']}]
    monkeypatch.setenv('OLLAMA_MODEL','qwen3.5:4b')
    monkeypatch.setattr(evaluation,'catalog',lambda:CAT)
    monkeypatch.setattr(evaluation,'documents',lambda split:rows)
    calls=[]
    def simulated(note,retriever,backend):
        calls.append(note)
        if len(calls)==2: raise TimeoutError('Interrupción simulada')
        return {'menciones':[{'codigo':'I10','estado':'confirmado','modelo':'qwen3.5:4b'}],'rechazadas':[],'candidatos':retriever.retrieve(note)}
    monkeypatch.setattr(evaluation,'process',simulated)
    output=tmp_path/'evaluation.json'
    argv=['evaluate','--backend','local','--limit','2','--output',str(output)]
    monkeypatch.setattr(sys,'argv',argv)
    with pytest.raises(TimeoutError): evaluation.main()
    assert not output.exists()
    monkeypatch.setattr(sys,'argv',argv+['--resume'])
    evaluation.main()
    result=json.loads(output.read_text(encoding='utf-8'))
    assert len(calls)==3 and calls.count(rows[0]['note'])==1
    assert result['summary']['documents']==2 and result['summary']['micro_f1']==1
    assert not output.with_suffix('.partial.json').exists()

@pytest.mark.parametrize('text,expected',[
('No se descarta neumonía.','sospechoso'),('Estudio para descartar neumonía.','sospechoso'),
('Hipertensión no controlada.','confirmado'),('Neumonía sin cambios.','confirmado')])
def test_additional_state_scopes(text,expected): assert state(text)==expected

def test_mixed_clause_does_not_transfer_negation():
    note='Niega diabetes, hipertensión esencial confirmada.'
    output=Output(menciones=[Mention(codigo='I10',estado='confirmado',evidencia='hipertensión esencial')])
    assert validate(note,output,CAT,'mock')[0][0]['estado']=='confirmado'

def test_repeated_literal_selects_matching_state():
    note='Probable neumonía. Se confirma neumonía.'
    output=Output(menciones=[Mention(codigo='J18.9',estado='sospechoso',evidencia='neumonía'),Mention(codigo='J18.9',estado='confirmado',evidencia='neumonía')])
    valid,_=validate(note,output,CAT,'mock')
    assert [m['estado'] for m in valid]==['sospechoso','confirmado']
    assert valid[0]['inicio']!=valid[1]['inicio']

def test_supplied_candidates_cannot_expand_catalog():
    with pytest.raises(ValueError,match='catálogo oficial'):
        process('Hipertensión.',Retriever(CAT),candidates={'XXX':'Código inventado'},runner=lambda b,p:Output(menciones=[]))

def test_api_quota_stops_after_429(monkeypatch,tmp_path):
    import codificamed.api as api
    monkeypatch.setenv('CODIFICAMED_API_LEDGER',str(tmp_path/'usage.json'))
    ticket=api.reserve('modelo-ficticio','nota ficticia')
    api.finish(ticket,'failed',429)
    with pytest.raises(api.ProviderError,match='cuota gratuita'): api.reserve('modelo-ficticio','otra nota')
    assert len(json.loads((tmp_path/'usage.json').read_text())['events'])==1

def test_training_phrases_are_train_d_only():
    from codificamed.retrieval import training_phrases
    pairs=training_phrases(catalog())
    assert pairs and all(code in catalog() for code,phrase in pairs[:20])

@pytest.mark.parametrize('description,evidence,reason',[
('Neoplasia benigna de glándula suprarrenal derecha','Mielolipoma suprarrenal','lateralidad_no_sustentada'),
('Antígeno prostático específico elevado','PSA de 1.16 ng/ml','elevacion_no_sustentada'),
('Carcinoma in situ de vejiga','Carcinoma superficial de vejiga','in_situ_no_sustentado'),
('Neoplasia benigna de glándula suprarrenal derecha','Mielolipoma suprarrenal derecho',None)])
def test_code_qualifications_require_literal_support(description,evidence,reason):
    from codificamed.pipeline import qualifier_issue
    assert qualifier_issue(description,evidence)==reason


def test_comparison_rejects_different_gold():
    from scripts.compare import compare
    row={'id':'A','gold':['I10'],'predicted':['I10'],'note_sha256':'same','candidatos':CAT,'false_positives':[],'false_negatives':[],'menciones':[],'rechazadas':[],'seconds':1}
    left={'summary':{'backend':'local','model':'qwen-test','pipeline_sha256':'same','documents':1},'predictions':[row]}
    right={'summary':{'backend':'externo','model':'gemini-test','pipeline_sha256':'same','documents':1},'predictions':[{**row,'gold':[]}]}
    with pytest.raises(ValueError,match='Texto, gold o candidatos diferentes'): compare(left,right)

def test_comparison_preserves_common_cases_when_api_partial():
    from scripts.compare import compare
    row={'id':'A','gold':['I10'],'predicted':['I10'],'note_sha256':'same','candidatos':CAT,'false_positives':[],'false_negatives':[],'menciones':[],'rechazadas':[],'seconds':1}
    left={'summary':{'backend':'local','model':'qwen-test','pipeline_sha256':'same','documents':2},'predictions':[row,{**row,'id':'B'}]}
    right={'backend':'externo','model':'gemini-test','pipeline_sha256':'same','planned_documents':2,'predictions':[row]}
    result=compare(left,right)
    assert result['status']=='partial' and result['paired_documents']==1
    assert result['local']['micro_f1']==result['externo']['micro_f1']==1
