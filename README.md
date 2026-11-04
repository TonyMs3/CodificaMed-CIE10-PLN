# CodificaMed

Repositorio público: [TonyMs3/CodificaMed-CIE10-PLN](https://github.com/TonyMs3/CodificaMed-CIE10-PLN).

Prototipo académico de asistencia a la codificación de diagnósticos CIE-10-ES, edición 2018. Recibe notas en español, propone códigos con evidencia literal y diferencia confirmado, negado, descartado y sospechoso. Requiere revisión humana. No realiza diagnósticos médicos. Introduce exclusivamente notas ficticias o textos públicos de CodiEsp sin datos personales privados.

## Instalación y ejecución

Requisitos: Windows 11, VS Code, Python 3.13 y Ollama con qwen3.5:4b. Desde la carpeta extraída del proyecto:

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m scripts.prepare
if (!(Test-Path .env)) { Copy-Item .env.example .env }
.venv/Scripts/python -m streamlit run app.py
```

La interfaz está disponible en http://127.0.0.1:8501 mientras el servidor permanece activo. El índice tarda en construirse. Ollama debe estar iniciado. Si falta el modelo en otra instalación, ejecuta `ollama pull qwen3.5:4b`; requiere una descarga aproximada de 3,4 GB. El paquete no contiene modelos ni entorno virtual. En equipos de aproximadamente 12 GB de RAM conviene ejecutar un lote local a la vez y detener Streamlit durante evaluaciones extensas.

## Configuración y funcionamiento

La configuración privada se define en .env, a partir de .env.example. Los valores locales son OLLAMA_BASE_URL=http://localhost:11434, OLLAMA_MODEL=qwen3.5:4b y API_PROVIDER=gemini. El servicio externo requiere GEMINI_MODEL=gemini-3.5-flash-lite y GEMINI_API_KEY en el archivo local. .env permanece excluido de Git. .env.example tiene los campos privados vacíos. Sin configuración externa, el modo local y las pruebas simuladas siguen disponibles. El modelo externo respondió en las evaluaciones guardadas. Su disponibilidad, cuota y condiciones dependen del proyecto de Google. No hace falta una credencial para consultar o recalcular los resultados incluidos.

La interfaz permite seleccionar Ollama o Gemini, cargar un ejemplo ficticio o introducir una nota, confirmar su procedencia y procesarla. La interfaz muestra descripción oficial, estado, evidencia resaltada y posiciones inicio/fin exclusivo. Las menciones negadas, descartadas y sospechosas permanecen visibles y no cuentan como códigos confirmados. La revisión se identifica por nota, proveedor, modelo, código, evidencia, posición y estado. Se mantiene en la sesión y no constituye una validación clínica persistente. Si cambia la nota o el modelo se ocultan resultados anteriores.

La API aplica un límite preventivo de 12 intentos diarios UTC, separación mínima de 15 segundos y bloqueo diario tras HTTP 429. El registro privado de ejecución se genera en results/api_usage.json y está excluido de Git. No contiene la credencial. GEMINI_MAX_DAILY_REQUESTS permite ajustar el límite preventivo según la cuota real, sin activar facturación. El contador conserva el historial de cada instalación y no acumula las solicitudes de otras instalaciones. El límite preventivo es independiente de la cuota oficial del proyecto.

## Corpus, arquitectura y metodología

Fuentes: [CodiEsp gold 1.4](https://zenodo.org/records/3837305), [catálogo oficial](https://zenodo.org/records/3632523) y [tarea CodiEsp](https://temu.bsc.es/codiesp/). Los registros declaran licencia CC BY 4.0. scripts.prepare descarga y valida rutas ZIP, UTF-8 y TSV, y genera data/manifest.json con URL y SHA-256. Los datos recuperables no están incluidos ni se publican mediante Git. Catálogo: 71.486 códigos. Train: 500 documentos. Dev: 250. Test: 250. Se evalúan diagnósticos D, no procedimientos P. El catálogo corresponde a CIE-10-ES 2018, no a una adaptación ecuatoriana ni a ediciones actuales. Hay anotaciones gold ausentes del catálogo: 230 train, 106 dev y 143 test. Se conservan y cuentan como FN cuando corresponde.

Tecnologías: Python, Streamlit, scikit-learn, Pydantic, Ollama y google-genai. Los módulos de datos, recuperación, inferencia, límites de solicitudes, experimentos y métricas están separados en codificamed/.

Flujo: nota original → fragmentos → TF-IDF de caracteres 3-5 y palabras 1-2, ponderación 0,35/0,65 → 40 candidatos → prompt y esquema comunes → Qwen o Gemini → validación → revisión humana. El índice incorpora descripciones oficiales y 3.275 variantes código-frase de diagnósticos exclusivamente de trainX, compatibles con train D. Se expanden HTA/DM2 sin alterar el texto original. No se entrenaron pesos de LLM. Se validan catálogo, candidatos, evidencia literal, alcance de estados y calificadores. Se conservan estados originales del modelo y estados corregidos. El contexto local es de 4096 tokens, con un máximo de salida de 1600 tokens, temperatura 0, semilla 42, razonamiento desactivado y timeout 600 s. El presupuesto aproximado del prompt es 14.000 bytes. El cliente Gemini no realiza reintentos automáticos.

Train prepara recursos y dev ajusta recuperación. En dev, 40 candidatos cubren 1.836/2.677 códigos gold, 68,58 %. El piloto final congela cinco documentos nuevos de test, uno por quintil de cantidad de códigos gold, elegidos por SHA-256 de semilla+ID, excluyendo tres casos anteriores, notas de más de 6000 caracteres y prompts fuera de presupuesto. La semilla es CodificaMed-2026-11-03-v2. results/v2/final_manifest.json conserva IDs, gold, candidatos y hashes. Es un piloto pequeño, sin representatividad estadística. No se alteraron referencias ni se ajustó el sistema con esos cinco casos.

## Resultados finales y comprobación sin modelos

Todos los archivos finales están en results/v2/ y se incluyen expresamente en .gitignore mediante excepciones. Los registros temporales y nuevas salidas no se publican automáticamente. Los JSON de predicciones y sus CSV conservan códigos, estados, TP/FP/FN, rechazos y tiempos. El manifiesto congela las condiciones de comparación. Los archivos comparison_gold.json y comparison_sinteticos.json contienen los resúmenes emparejados.

Cinco documentos CodiEsp, 57 códigos gold, mismos textos y candidatos:

| Modelo | Precisión micro | Recall micro | F1 micro | TP | FP | FN |
|---|---:|---:|---:|---:|---:|---:|
| Qwen 3.5:4b | 0,6364 | 0,2456 | 0,3544 | 14 | 8 | 43 |
| Gemini 3.5 Flash-Lite | 0,8400 | 0,3684 | 0,5122 | 21 | 4 | 36 |

El recuperador contiene 40/57 códigos gold. Ambos modelos mantienen omisiones. Los tiempos guardados excluyen la construcción del índice; Gemini incluye esperas preventivas y no es un benchmark aislado. Las métricas cuentan códigos distintos confirmados por documento. Los JSON listan falsos positivos, falsos negativos y predicciones rechazadas.

CodiEsp-D no anota negación. Los dos controles ficticios S02 y S06 se evalúan aparte y son casos de desarrollo, no validación clínica independiente. F1 de códigos confirmados: 1,0000 para ambos. F1 código-estado: Qwen 0,8571 y Gemini 1,0000. Qwen omitió una mención negada. No hubo negaciones o descartes convertidos en confirmaciones en esos controles. Los siete controles originales y las contradicciones están en tests/fixtures y tests/test_core.py.

Después de instalar las dependencias, estos comandos recalculan las métricas guardadas sin corpus, credenciales ni consultas a modelos:

```powershell
.venv/Scripts/python -m scripts.compare results/v2/local_gold.json results/v2/externo_gold.json
.venv/Scripts/python -m scripts.compare results/v2/local_sinteticos.json results/v2/externo_sinteticos.json --synthetic-file tests/fixtures/comparacion_sinteticos.json
```

El manifiesto y los resultados publicados constituyen un registro experimental congelado. La CLI de nuevas evaluaciones admite --backend local|externo, --split dev|test, --limit N, --output, --manifest y --resume. Las llamadas externas requieren --allow-api. Las nuevas evaluaciones requieren otra ruta de salida y están sujetas a los límites del proveedor. --resume comprueba versión, modelo, texto, gold y candidatos. No se necesita repetir inferencia para comprobar las cifras publicadas.

## Pruebas e informe

Tras descargar los recursos con scripts.prepare:

```powershell
.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m pip check
.venv/Scripts/python -m scripts.audit_data
.venv/Scripts/python -m scripts.check_corpus_integrity
```

El registro tests/resultados_pruebas.json contiene el resultado de las 40 pruebas, incluida la independencia de las casillas de revisión por modelo, código y evidencia. Las pruebas cubren corpus, recuperación, evidencia literal, estados y contradicciones, validación de códigos, métricas, reanudación y proveedores simulados. Los proveedores simulados verifican contratos de software y no acreditan calidad de los modelos reales. Una instalación limpia requiere conexión para dependencias y recursos.

El informe, cuya fuente editable es scripts/report.py, está en [informe/Informe_Ejecutivo_CodificaMed.pdf](informe/Informe_Ejecutivo_CodificaMed.pdf). Contiene problemática y objetivo, las seis fases CRISP-ML(Q), arquitectura, comparación, conclusiones y limitaciones. El comando `python -m scripts.report` regenera el PDF desde los resultados y el registro de pruebas, sin consultar modelos. Referencia metodológica: [CRISP-ML(Q)](https://www.mdpi.com/2504-4990/3/2/392). El prototipo requiere revisión humana y no garantiza exactitud clínica.
