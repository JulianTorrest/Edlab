# Análisis de efectos — Kerckhoff (1986) "Ability Grouping"

Este repositorio contiene un pipeline en Python que:

1. Extrae y limpia automáticamente los datos de la fuente web.
2. Construye una base de datos tabular (CSV + JSON).
3. Genera una visualización estática de los efectos e incertidumbre.
4. Realiza un análisis bayesiano simple para decidir si financiar una iniciativa similar.
5. Ofrece un tablero interactivo local con Streamlit.

## Fuente

- URL: <https://taxonomy-prototype.pages.dev/demo/investigation-klim-b>
- Artículo: *Ability Grouping and Student Achievement in Elementary Schools* — Kerckhoff, A. C. (1986), *American Educational Research Journal*.

## Archivos principales

| Archivo | Descripción |
|---|---|
| `main.py` | Pipeline completo: extracción, limpieza, base de datos, gráfico y análisis bayesiano. |
| `app.py` | Aplicación de Streamlit para explorar los datos y los posteriors de forma interactiva. |
| `requirements.txt` | Dependencias necesarias. |
| `investigation_klim_b.html` | Copia local del HTML descargado de la fuente. |
| `data/klim_b_effects.csv` y `data/klim_b_effects.json` | Base de datos limpia. |
| `figures/klim_b_forest.png` | Visualización estática. |
| `klim_b_bayesian_report.md` | Informe con supuestos y recomendación. |

## Instalación

Se recomienda usar un entorno virtual:

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux / macOS

pip install -r requirements.txt
```

Si ya tienes las dependencias instaladas, basta con:

```bash
pip install -r requirements.txt
```

## Configuración de API keys

Para el **agente conversacional** se usan dos proveedores: Groq y Mistral. Crea un archivo `.env` en la raíz con tus llaves:

```bash
GROQ_API_KEY=tu-key-de-groq
MISTRAL_API_KEY=tu-key-de-mistral
```

El archivo `.env` ya está en `.gitignore` para evitar subirlo a un repositorio.

## Ejecución

### 1. Pipeline completo en consola

```bash
python main.py
```

Esto genera:
- `data/klim_b_effects.csv`
- `data/klim_b_effects.json`
- `figures/klim_b_forest.png`
- `klim_b_bayesian_report.md`

### 2. Tablero interactivo con Streamlit

```bash
streamlit run app.py
```

Se abrirá el navegador en `http://localhost:8501` con:
- La tabla de efectos.
- Un forest plot estático.
- Controles para ajustar la previa bayesiana, el umbral de relevancia y la confianza mínima.
- Distribuciones posteriores actualizadas en tiempo real.

## Hallazgos principales

| Finding | Población | Medida | Hedges' g | SE | IC 95% |
|---|---|---|---|---|---|
| 1 | high-ability | Iowa Test of Basic Skills HIGH_ITBS | **0.33** | 0.078 | [0.18, 0.48] |
| 2 | regular | Iowa Test of Basic Skills AVERAGE_ITBS | **-0.48** | 0.096 | [-0.67, -0.29] |

## Recomendación bayesiana

- **Sí financiar** si la iniciativa se dirige exclusivamente a estudiantes de **alta habilidad**: `P(δ > 0.1) ≈ 99.8%`.
- **No financiar** para estudiantes regulares ni para toda la población escolar: el efecto esperado en la mezcla es cercano a cero o ligeramente negativo.

### Supuestos principales

- El estimador observado `g` sigue una verosimilitud `Normal(δ, SE²)`.
- Previa `δ ~ N(0, 0.5²)`.
- Umbral mínimo relevante: `g = 0.1`.
- Regla de decisión: financiar si `P(δ > 0.1) > 80%`.

## Notas

- Si la fuente web no está disponible, `main.py` y `app.py` usarán la copia local `investigation_klim_b.html`.
- El análisis de subgrupos assume independencia entre los efectos de alta habilidad y regulares al calcular el efecto ponderado para la población mixta.
