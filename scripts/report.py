"""Genera el informe ejecutivo desde predicciones y comprobaciones guardadas."""
import json
from pathlib import Path
from collections import Counter
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, PageBreak, Table, TableStyle, Spacer

ROOT = Path(__file__).resolve().parents[1]

def read(relative):
    return json.loads((ROOT / relative).read_text(encoding='utf-8-sig'))

def build():
    comparison = read('results/v2/comparison_gold.json')
    controls = read('results/v2/comparison_sinteticos.json')
    plan = read('results/v2/final_manifest.json')
    coverage = read('results/v2/retrieval_dev.json')
    checks = read('tests/resultados_pruebas.json')
    local = read('results/v2/local_gold.json')['summary']
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='BodyES',fontName='Helvetica',fontSize=10,leading=14,spaceAfter=9))
    styles.add(ParagraphStyle(name='SmallES',fontName='Helvetica',fontSize=8,leading=11,spaceAfter=7))
    styles['Heading2'].textColor = colors.HexColor('#174556')
    story = []
    def heading(text):
        story.append(Paragraph(escape(text),styles['Heading2']))
    def para(text,small=False):
        story.append(Paragraph(escape(text),styles['SmallES' if small else 'BodyES']))
    def table(rows,widths):
        cells = [[Paragraph(escape(str(v)),styles['SmallES']) for v in row] for row in rows]
        widget = Table(cells,colWidths=widths,repeatRows=1,hAlign='LEFT')
        widget.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#E7EEF1')),
            ('VALIGN',(0,0),(-1,-1),'TOP'),
            ('LINEBELOW',(0,0),(-1,0),.5,colors.HexColor('#8CA4AD')),
            ('LINEBELOW',(0,1),(-1,-1),.25,colors.HexColor('#D9E1E5')),
            ('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),
            ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),4)]))
        story.extend([widget,Spacer(1,8)])

    heading('Problemática y objetivo')
    para('La codificación clínica requiere identificar diagnósticos, síntomas, hallazgos y antecedentes, relacionarlos con un catálogo y determinar si cada mención está confirmada, negada, descartada o es sospechosa. CodificaMed aborda esta tarea mediante un prototipo de asistencia a la codificación CIE-10-ES con evidencia literal, modelos intercambiables y evaluación reproducible. Las sugerencias requieren revisión profesional y no constituyen diagnósticos médicos.')

    heading('Actividades realizadas en las seis fases de CRISP-ML(Q)')
    para('1. Comprensión del negocio y los datos. Se delimitó la tarea a diagnósticos CIE-10-ES, edición 2018. El catálogo oficial contiene 71.486 códigos. CodiEsp gold 1.4 aporta 500 documentos train, 250 dev y 250 test. Se separaron los diagnósticos D de los procedimientos P. Los ejemplos adicionales son ficticios y no se incorporaron historias clínicas privadas.')
    para('2. Preparación de datos. Se validaron rutas ZIP, codificación UTF-8, estructura TSV y correspondencia entre notas y referencias. El manifiesto de descarga conserva URL y SHA-256. Hay anotaciones gold ausentes del catálogo: 230 en train, 106 en dev y 143 en test. Se mantuvieron en las referencias y en el denominador de recall cuando corresponde.')
    para(f'El índice incorpora {coverage["training_pairs"]} pares código-frase de anotaciones DIAGNOSTICO de trainX compatibles con train D y el catálogo. No incluye frases de dev o test. La nota original se conserva para comprobar evidencia literal y posiciones. La normalización y la expansión de HTA y DM2 se aplican a la recuperación, sin eliminar marcadores de negación.')
    para('3. Modelado. Se combinaron TF-IDF de caracteres de 3 a 5 y palabras de 1 a 2 con similitud coseno ponderada, 0,35 y 0,65. El recuperador prioriza coincidencias literales y distribuye candidatos entre fragmentos. Qwen y Gemini seleccionan menciones entre esos candidatos. La validación de catálogo, evidencia, calificadores y estado está separada de la inferencia. No se entrenaron pesos de los LLM.')
    para(f'En los {coverage["documents"]} documentos dev, 40 candidatos cubrieron {coverage["covered"]["40"]}/{coverage["gold_codes"]} códigos gold ({coverage["recall"]["40"]:.4f}); con 60 se obtuvo {coverage["recall"]["60"]:.4f}. Se mantuvieron 40 para limitar el contexto local. Estas cifras miden recuperación, no exactitud del LLM.')

    story.append(PageBreak())
    heading('Actividades realizadas en las seis fases de CRISP-ML(Q)')
    para('4. Evaluación. Se calcularon TP, FP y FN sobre conjuntos de códigos distintos y confirmados por documento. Las métricas principales son precisión, recall y F1 micro. El F1 promedio por documento se informa por separado y no equivale a macro-F1 por etiqueta. Un falso positivo indica ausencia en el gold del documento, no necesariamente inexistencia en el catálogo.')
    para('Train aporta recursos y dev permite ajustar la recuperación. El piloto final contiene cinco documentos nuevos de test, uno por quintil de cantidad de códigos gold, seleccionados por SHA-256 de semilla e ID. Se excluyeron tres casos examinados previamente y entradas fuera del presupuesto. Los cinco casos finales no se emplearon para ajustar el sistema. La comparación exige los mismos textos, gold, candidatos y versión del pipeline.')
    para(f'La suite automatizada registró {checks["tests"]} casos superados, {checks["failures"]} fallos, {checks["errors"]} errores y {checks["skipped"]} omitidos. Incluye corpus, recuperación, estados, contradicciones, evidencia literal, calificadores, métricas, reanudación, límites de API e interfaz simulada. La revisión de una sugerencia es independiente por modelo, código y evidencia. Los proveedores simulados verifican contratos de software, no calidad clínica.')
    para('5. Despliegue. Streamlit permite seleccionar Ollama o Gemini, cargar ejemplos ficticios, introducir una nota, consultar códigos y evidencias resaltadas, marcar revisión y descargar JSON. Los resultados anteriores se ocultan cuando cambia la nota o el proveedor. La revisión se identifica por nota, proveedor, modelo, código, evidencia, posición y estado. La configuración privada se carga desde .env, excluido de Git.')
    para('El entorno verificado emplea Python 3.13 y dependencias fijadas. El repositorio público contiene código, configuración de ejemplo, pruebas, informe y resultados pequeños. El corpus y los modelos se recuperan mediante las instrucciones del README. La documentación distingue instalación, ejecución y recálculo de métricas sin inferencia.')
    para('6. Monitoreo y mantenimiento. Los JSON y CSV conservan predicciones, FP, FN, evidencias, estados originales y corregidos, rechazos y tiempos. El registro de API guarda modelo, huella de entrada y estado HTTP, sin credenciales ni notas completas. El límite preventivo es de 12 intentos diarios UTC, separados por al menos 15 s. Un HTTP 429 bloquea nuevas solicitudes durante ese día. Los checkpoints permiten reanudar casos sin repetir los completados ni mezclar versiones.')

    heading('Arquitectura de la solución')
    para('Streamlit o CLI → nota original y fragmentación → TF-IDF del catálogo y variantes de train → hasta 40 candidatos → instrucciones y esquema comunes → Qwen/Ollama o Gemini → validación → revisión humana. Los módulos de datos, recuperación, inferencia, límites de solicitudes, experimentos y métricas están separados.')
    para('La validación rechaza códigos inexistentes o ajenos a los candidatos y evidencia no literal. Exige soporte textual para lateralidad, bilateralidad e in situ. No interpreta un valor numérico aislado como elevación. Las reglas distinguen no se descarta de se descarta y conservan menciones contradictorias. Estos controles son parciales y no sustituyen la revisión clínica.')

    story.append(PageBreak())
    heading('Evaluación y comparación entre Qwen y Gemini')
    para(f'La comparación final incluye {comparison["paired_documents"]} documentos y {local["gold_codes"]} códigos gold. Los modelos son qwen3.5:4b y gemini-3.5-flash-lite. Ambos reciben los mismos casos, candidatos e instrucciones. Se evalúan códigos confirmados; CodiEsp-D no permite medir exactitud de estados porque no los anota.')
    rows = [['Modelo','Precisión','Recall','F1','TP','FP','FN']]
    for key,label in [('local','Qwen 3.5:4b'),('externo','Gemini 3.5 Flash-Lite')]:
        s = comparison[key]
        rows.append([label,f'{s["micro_precision"]:.4f}',f'{s["micro_recall"]:.4f}',f'{s["micro_f1"]:.4f}',s['tp'],s['fp'],s['fn']])
    table(rows,[155,57,57,57,42,42,42])
    para(f'El recuperador incluyó {local["candidate_gold_covered"]}/{local["gold_codes"]} códigos gold entre los candidatos. Esta cobertura limita el recall posible, pero no garantiza la selección correcta. Tiempos de procesamiento: Qwen {comparison["local"]["seconds"]:.2f} s y Gemini {comparison["externo"]["seconds"]:.2f} s. Excluyen la construcción del índice; Gemini incluye esperas preventivas, por lo que no representan una comparación aislada de velocidad.')
    para(f'Selección reproducible: semilla {plan["seed"]}, con {plan["eligible_documents"]} documentos elegibles antes del filtro de presupuesto. El manifiesto conserva referencias, candidatos, hashes de texto y huella del pipeline. El piloto cubre distintas cargas de codificación y no tiene representatividad estadística.')
    table([['Documento','Quintil','Gold','Caracteres']]+[[r['id'],r['stratum'],r['gold_count'],r['note_characters']] for r in plan['documents']],[300,60,60,92])
    para('Huella del pipeline y sus recursos: '+plan['pipeline_sha256'],True)
    names = {'codigo_fuera_catalogo':'código inexistente','codigo_fuera_candidatos':'código fuera de candidatos','evidencia_no_literal':'evidencia no literal','lateralidad_no_sustentada':'lateralidad no sustentada'}
    for key,label in [('local','Qwen'),('externo','Gemini')]:
        counts = Counter(r['motivo'] for r in comparison[key]['rejected'])
        para(label+': intentos rechazados antes de las métricas: '+', '.join(f'{value} por {names.get(reason,reason)}' for reason,value in sorted(counts.items()))+'.',True)
    para('Controles ficticios S02 y S06: cuatro pares código-estado que cubren negación, descarte, sospecha, confirmación y nota mixta. Son controles de desarrollo separados de CodiEsp, no validación clínica independiente.')
    table([['Modelo','F1 código','F1 código-estado','Neg./desc. confirmados','Neg./desc. omitidos']]+[[label,f'{controls[key]["micro_f1"]:.4f}',f'{controls[key]["state_metrics"]["micro_f1"]:.4f}',controls[key]['negation_errors'],controls[key]['negative_mention_omissions']] for key,label in [('local','Qwen'),('externo','Gemini')]],[90,70,110,120,122])
    para('La confirmación indebida de una negación o descarte se distingue de la omisión de una mención negativa. Qwen omitió la mención negada de S02. Estos resultados no se trasladan a CodiEsp-D.',True)

    story.append(PageBreak())
    heading('Conclusiones y limitaciones')
    a,b = comparison['local'],comparison['externo']
    para(f'En los mismos cinco documentos, Qwen obtuvo micro-F1 de {a["micro_f1"]:.4f} y Gemini de {b["micro_f1"]:.4f}, con {a["fn"]} y {b["fn"]} falsos negativos, respectivamente. Gemini presentó mayor F1 en este piloto. La cobertura de candidatos y la selección de códigos explican parte de las omisiones. La comparación no permite generalizar a otros casos clínicos.')
    para('La evidencia literal facilita la trazabilidad, pero no garantiza corrección semántica ni especificidad del código. Las reglas cubren situaciones concretas de negación, sospecha, lateralidad y otros calificadores. No resuelven toda coordinación, alcance, temporalidad o relación entre diagnóstico y código. Cada sugerencia requiere revisión profesional.')
    para('Los resultados de estados proceden de dos controles ficticios de desarrollo y no constituyen una evaluación clínica independiente. El catálogo corresponde a CIE-10-ES 2018; no se validó adaptación ecuatoriana ni aplicación a ediciones actuales. La muestra final es pequeña y los resultados anteriores, obtenidos sobre otros casos, no permiten atribuir causalmente diferencias de F1 a una mejora del sistema.')
    para('La ejecución local depende de CPU y memoria. Qwen tiene contexto de 4096 tokens, salida máxima de 1600 tokens y timeout de 600 s. Los modelos comparten datos e instrucciones, pero tienen recursos internos distintos. El presupuesto de entrada de 14.000 bytes es aproximado. Gemini depende de disponibilidad y cuota del proveedor; el contador local no equivale a la cuota oficial ni acumula solicitudes de otras instalaciones. El SDK no certifica el estado de facturación.')
    para('La reproducibilidad se apoya en versiones fijadas, selección congelada, semillas, hashes de texto y recursos, referencias intactas y predicciones almacenadas. Los comandos de comparación recalculan las métricas sin consultar modelos. El informe se genera desde esos archivos y el registro de pruebas.')
    para('Fuentes: CodiEsp gold 1.4 y catálogo oficial, con licencia CC BY 4.0; documentación de la tarea y anotación; metodología CRISP-ML(Q); documentación de salida estructurada de Ollama y condiciones del proveedor externo.',True)
    for source in [
        'CodiEsp gold 1.4: https://zenodo.org/records/3837305',
        'Catálogo CIE-10-ES 2018: https://zenodo.org/records/3632523',
        'Tarea CodiEsp: https://temu.bsc.es/codiesp/',
        'CRISP-ML(Q): https://www.mdpi.com/2504-4990/3/2/392',
        'Ollama: https://docs.ollama.com/capabilities/structured-outputs',
        'Gemini: https://aistudio.google.com/docs/pricing#gemini-3.5-flash-lite']:
        para(source,True)
    def footer(canvas,document):
        canvas.setFont('Helvetica',8)
        canvas.setFillColor(colors.HexColor('#52616B'))
        canvas.drawString(42,24,'CodificaMed | Informe ejecutivo')
        canvas.drawRightString(A4[0]-42,24,str(document.page))
    destination = ROOT/'informe/Informe_Ejecutivo_CodificaMed.pdf'
    SimpleDocTemplate(str(destination),pagesize=A4,leftMargin=42,rightMargin=42,topMargin=32,bottomMargin=40,title='Informe ejecutivo CodificaMed',author='CodificaMed').build(story,onFirstPage=footer,onLaterPages=footer)
    print(destination)

if __name__ == '__main__':
    build()
