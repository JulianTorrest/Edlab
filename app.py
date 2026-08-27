import math
import os
import requests
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st
from dotenv import load_dotenv
from duckduckgo_search import DDGS
from groq import Groq
from pathlib import Path
from scipy import stats

from main import fetch_html, parse_study, parse_findings, build_database, URL, CACHE

load_dotenv()

st.set_page_config(page_title="Klim B Dashboard", layout="wide")
st.title("Investigación Klim B — Ability Grouping")

# Carga/Extracción
with st.spinner("Extrayendo datos de la fuente..."):
    html_text = fetch_html(URL, CACHE)
    study = parse_study(html_text)
    findings = parse_findings(html_text)
    df = build_database(study, findings)

# --- Contexto web precargado ---
context_file = Path("data/ability_grouping_context.md")
web_context = context_file.read_text(encoding="utf-8") if context_file.exists() else "No se encontró contexto web adicional."

st.markdown(f"**Fuente:** {study['title']}, {study['authors']}, *{study['venue']}*")
st.markdown(f"**Intervención:** {study['intervention_description']}")
st.markdown(f"**Control:** {study['control']} | **N total:** {study['n_total']}")

st.subheader("Base de datos de efectos")
st.dataframe(df)

# --- Forest plot ---
st.subheader("Magnitud de los efectos e incertidumbre")
fig, ax = plt.subplots(figsize=(8, 4))
for i, (_, row) in enumerate(df.iterrows()):
    x = row["hedges_g"]
    color = "#2ecc71" if x > 0 else "#e74c3c"
    xerr = [[x - row["ci_lower"]], [row["ci_upper"] - x]]
    ax.errorbar(x, i, xerr=xerr, fmt="o", color=color, ecolor=color, capsize=4, elinewidth=2, markeredgewidth=2)
ax.axvline(0, color="black", linestyle="--", linewidth=1)
ax.set_yticks(np.arange(len(df)))
ax.set_yticklabels([f"Finding {r['finding_id']} ({r['population']})" for _, r in df.iterrows()])
ax.set_xlabel("Hedges' g")
ax.set_title("Intervalos de confianza del 95% — Kerckhoff (1986)")
ax.grid(axis="x", alpha=0.3)
plt.tight_layout()
st.pyplot(fig)

# --- Bayesian sidebar ---
st.sidebar.header("Supuestos bayesianos")
prior_mean = st.sidebar.slider("Media previa", -1.0, 1.0, 0.0, 0.05)
prior_sd = st.sidebar.slider("SD previa", 0.1, 2.0, 0.5, 0.05)
threshold = st.sidebar.slider("Umbral mínimo relevante", -0.5, 1.0, 0.1, 0.05)
confidence = st.sidebar.slider("Confianza mínima para financiar", 0.5, 0.99, 0.8, 0.01)


def posterior(obs, se):
    prior_var = prior_sd ** 2
    obs_var = se ** 2
    post_var = 1 / (1 / prior_var + 1 / obs_var)
    post_mean = post_var * (prior_mean / prior_var + obs / obs_var)
    return post_mean, math.sqrt(post_var)


high = df[df["population"] == "high-ability"].iloc[0]
reg = df[df["population"] == "regular"].iloc[0]

h_mean, h_sd = posterior(high["hedges_g"], high["se"])
r_mean, r_sd = posterior(reg["hedges_g"], reg["se"])

p_h = 1 - stats.norm.cdf(threshold, loc=h_mean, scale=h_sd)
p_r = 1 - stats.norm.cdf(threshold, loc=r_mean, scale=r_sd)

if study["n_total"] and study["n_high_ability"]:
    p_high = study["n_high_ability"] / study["n_total"]
    p_regular = study["n_regular"] / study["n_total"]
else:
    p_high = p_regular = 0.5

overall_mean = p_high * h_mean + p_regular * r_mean
overall_sd = math.sqrt((p_high ** 2) * h_sd ** 2 + (p_regular ** 2) * r_sd ** 2)
p_overall = 1 - stats.norm.cdf(threshold, loc=overall_mean, scale=overall_sd)

st.subheader("Resultados bayesianos interactivos")
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("High-ability", f"{h_mean:.3f} ± {h_sd:.3f}", f"P(δ > {threshold}) = {p_h:.1%}")
    st.write(f"**Recomendación:** {'Financiar' if p_h > confidence else 'No financiar'}")
with col2:
    st.metric("Regular", f"{r_mean:.3f} ± {r_sd:.3f}", f"P(δ > {threshold}) = {p_r:.1%}")
    st.write(f"**Recomendación:** {'Financiar' if p_r > confidence else 'No financiar'}")
with col3:
    st.metric("Población mixta", f"{overall_mean:.3f} ± {overall_sd:.3f}", f"P(δ > {threshold}) = {p_overall:.1%}")
    st.write(f"**Recomendación:** {'Financiar' if p_overall > confidence else 'No financiar'}")

# --- Posterior plot ---
fig2, ax2 = plt.subplots(figsize=(9, 4))
x = np.linspace(-1.2, 1.0, 500)
ax2.plot(x, stats.norm.pdf(x, h_mean, h_sd), label=f"high-ability (μ={h_mean:.2f})", color="#2ecc71")
ax2.plot(x, stats.norm.pdf(x, r_mean, r_sd), label=f"regular (μ={r_mean:.2f})", color="#e74c3c")
ax2.plot(x, stats.norm.pdf(x, overall_mean, overall_sd), label=f"mixta (μ={overall_mean:.2f})", color="#3498db")
ax2.axvline(threshold, color="black", linestyle="--", label=f"umbral = {threshold}")
ax2.axvline(0, color="gray", linestyle=":", label="efecto nulo")
ax2.set_xlabel("Hedges' g")
ax2.set_ylabel("Densidad posterior")
ax2.set_title("Distribuciones posteriores del efecto")
ax2.legend()
ax2.grid(alpha=0.3)
plt.tight_layout()
st.pyplot(fig2)

# --- LLM Chat ---
st.divider()
st.subheader("Agente conversacional especializado")

st.sidebar.header("Configuración del LLM")
provider = st.sidebar.selectbox("Proveedor principal", ["Groq", "Mistral"])
groq_model = st.sidebar.selectbox("Modelo Groq", ["llama-3.1-70b-versatile", "llama-3.1-8b-instant"])
mistral_model = st.sidebar.selectbox("Modelo Mistral", ["mistral-small", "mistral-tiny", "mistral-medium"])
use_web_search = st.sidebar.checkbox("Intentar búsqueda web en vivo (DuckDuckGo)", value=False)

keys = {
    "Groq": os.getenv("GROQ_API_KEY", ""),
    "Mistral": os.getenv("MISTRAL_API_KEY", ""),
}
models = {"Groq": groq_model, "Mistral": mistral_model}

if not any(keys.values()):
    st.warning("No se encontró ninguna API key. Agrégala en el archivo `.env` o como variable de entorno.")


def call_groq(messages, key, model_name):
    client = Groq(api_key=key)
    response = client.chat.completions.create(
        model=model_name,
        messages=messages,
        temperature=0.3,
        max_tokens=1024,
    )
    return response.choices[0].message.content


def call_mistral(messages, key, model_name):
    url = "https://api.mistral.ai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 1024,
    }
    r = requests.post(url, headers=headers, json=payload, timeout=30)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


system_prompt = f"""Eres un asistente experto en evidencia educacional, evaluación de intervenciones y meta-análisis. Tienes acceso a dos fuentes de información:

1. Los datos del estudio de Kerckhoff (1986) sobre *ability grouping* en escuelas primarias.
2. Un contexto web precargado con otros estudios y meta-análisis sobre *ability grouping*.

Información del estudio Kerckhoff (1986):
- Título: {study['title']}
- Autor/a: {study['authors']}, {study['venue']}
- Año: 1986
- Intervención: {study['intervention_description']}
- Control: {study['control']}
- Muestra: N = {study['n_total']} estudiantes ({study['n_high_ability']} de alta habilidad, {study['n_regular']} regulares), duración {study['duration_months']} meses.
- Finding 1 (alta habilidad, medida HIGH_ITBS): Hedges' g = {high['hedges_g']}, SE = {high['se']}, IC 95% = [{high['ci_lower']}, {high['ci_upper']}].
- Finding 2 (regulares, medida AVERAGE_ITBS): Hedges' g = {reg['hedges_g']}, SE = {reg['se']}, IC 95% = [{reg['ci_lower']}, {reg['ci_upper']}].
- Supuestos bayesianos activos en el panel: previa δ ~ N({prior_mean}, {prior_sd}²), umbral mínimo relevante = {threshold}, confianza mínima = {confidence}.
- Distribuciones posteriores actuales:
  * Alta habilidad: δ ~ N({h_mean:.3f}, {h_sd:.3f}²); P(δ > {threshold}) = {p_h:.2%}.
  * Regular: δ ~ N({r_mean:.3f}, {r_sd:.3f}²); P(δ > {threshold}) = {p_r:.2%}.
  * Población mixta: δ ~ N({overall_mean:.3f}, {overall_sd:.3f}²); P(δ > {threshold}) = {p_overall:.2%}.

Contexto web precargado con otros estudios y meta-análisis:
{web_context}

Reglas de conducta:
1. Responde con base en el estudio Kerckhoff (1986) y en el contexto web precargado. No inventes cifras, estudios adicionales ni afirmaciones no sustentadas.
2. Si la pregunta es sobre otros estudios de *ability grouping*, usa el contexto web precargado y cita los autores/años.
3. Si se incluyen resultados de búsqueda web en vivo, cítalos como información externa y distínguelos del estudio original.
4. Explica Hedges' g, los intervalos de confianza, la incertidumbre y la interpretación bayesiana cuando sea relevante.
5. Si te preguntan si se debe financiar, aplica la regla: se financia si P(δ > umbral) > confianza mínima. Destaca que la recomendación depende de la población objetivo (alta habilidad vs regular vs mixta).
6. Mantén las respuestas concisas y en español, salvo que se te solicite otro idioma.
7. No modifiques ni inventes fechas, años, cifras, tamaños de muestra ni valores de Hedges' g. Usa exactamente los datos anteriores."""

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Pregúntame sobre el estudio, los efectos, la incertidumbre o la decisión de financiar..."):
    if not any(keys.values()):
        st.error("Falta al menos una API key (Groq o Mistral). Configúrala en `.env` o en variables de entorno.")
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            messages = [{"role": "system", "content": system_prompt}]
            for m in st.session_state.messages[:-1]:
                messages.append(m)

            live_results = ""
            if use_web_search:
                try:
                    with DDGS() as ddgs:
                        results = list(ddgs.text(prompt, max_results=3))
                    live_results = "\n".join([f"- {r['title']}: {r['body']} ({r['href']})" for r in results])
                    st.toast("Búsqueda web en vivo exitosa")
                except Exception as e:
                    st.warning(f"Búsqueda web en vivo no disponible: {e}. Se usa el contexto precargado.")

            if live_results:
                messages.append({"role": "user", "content": f"Resultados de búsqueda web en vivo para '{prompt}':\n{live_results}"})
            messages.append(st.session_state.messages[-1])

            reply = None
            providers_to_try = [provider] + [p for p in ["Groq", "Mistral"] if p != provider]

            for prov in providers_to_try:
                if not keys[prov]:
                    continue
                try:
                    if prov == "Groq":
                        reply = call_groq(messages, keys[prov], models[prov])
                    else:
                        reply = call_mistral(messages, keys[prov], models[prov])
                    st.caption(f"Respuesta generada por {prov} ({models[prov]})")
                    break
                except Exception:
                    continue

            if reply is None:
                reply = "Ningún proveedor pudo responder. Revisa tus API keys y la disponibilidad de los modelos seleccionados."
            st.markdown(reply)

        st.session_state.messages.append({"role": "assistant", "content": reply})
        st.rerun()
