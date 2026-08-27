"""
Pipeline completo para la evidencia de Kerckhoff (1986) sobre
"Ability Grouping and Student Achievement in Elementary Schools".

1. Extrae y limpia los datos de la URL.
2. Construye una base de datos tabular (CSV + JSON).
3. Genera una visualización estática de los efectos e incertidumbre.
4. Realiza un análisis bayesiano simple y emite una recomendación de financiación.

Ejecutar: python main.py
"""
import os
import re
import html
import json
import urllib.request
import math
from pathlib import Path
from bs4 import BeautifulSoup

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy import stats

URL = "https://taxonomy-prototype.pages.dev/demo/investigation-klim-b"
CACHE = "investigation_klim_b.html"
DATA_DIR = Path("data")
FIGS_DIR = Path("figures")

# Supuestos bayesianos explícitos
PRIOR_MEAN = 0.0
PRIOR_SD = 0.5            # Efecto Hedges' g: 95% previa en [-1, 1]
MEANINGFUL_THRESHOLD = 0.1  # Tamaño de efecto mínimo educativamente relevante
DECISION_CONFIDENCE = 0.8   # Se financia si P(efecto > umbral) > 80%


def fetch_html(url: str, cache: str) -> str:
    """Descarga la página o usa la copia local si existe."""
    if os.path.exists(cache):
        with open(cache, "r", encoding="utf-8") as f:
            return f.read()

    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as response:
        text = response.read().decode("utf-8")
    with open(cache, "w", encoding="utf-8") as f:
        f.write(text)
    return text


def clean_text(raw: str) -> str:
    """Elimina etiquetas HTML, decodifica entidades y normaliza espacios."""
    raw = re.sub(r"<[^>]+>", " ", raw)
    raw = html.unescape(raw)
    raw = raw.replace("−", "-").replace("–", "-").replace("\u2212", "-")
    raw = re.sub(r"\s+", " ", raw).strip()
    return raw


def to_float(s: str) -> float:
    return float(clean_text(s))


def parse_study(html_text: str) -> dict:
    """Extrae los metadatos generales de la investigación con BeautifulSoup."""
    soup = BeautifulSoup(html_text, "html.parser")

    title = clean_text(soup.find("h1", class_="inv-title").get_text())
    authors = clean_text(soup.find("p", class_="inv-authors").get_text())
    venue = clean_text(soup.find("p", class_="inv-venue").get_text())

    doi_tag = soup.find("a", class_="inv-doi")
    doi = clean_text(doi_tag.get_text()) if doi_tag else ""

    h3_int = soup.find("h3", class_="h3", string=re.compile("Intervention"))
    intervention = clean_text(h3_int.find_next_sibling("div", class_="comp-value").get_text()) if h3_int else ""

    h3_ctrl = soup.find("h3", class_="h3", string=re.compile("Control"))
    control = clean_text(h3_ctrl.find_next_sibling("div", class_="comp-value").get_text()) if h3_ctrl else ""

    desc_tag = soup.find("div", class_="intervention-desc")
    intervention_desc = clean_text(desc_tag.get_text()) if desc_tag else ""

    size_label = soup.find("span", class_="lg-label", string=re.compile("Size"))
    n_total = int(size_label.find_next_sibling("span").get_text()) if size_label else None

    sample_label = soup.find("div", class_="sp-label", string=re.compile("Sample size"))
    n_high, n_regular = None, None
    if sample_label:
        p = sample_label.find_next_sibling("p")
        m = re.search(r"(\d+)\s+high ability.*?and\s+(\d+)\s+regular", p.get_text(), re.S)
        if m:
            n_high = int(m.group(1))
            n_regular = int(m.group(2))

    duration_match = re.search(r"Duration:\s*(\d+)\s*months", html_text)
    duration = int(duration_match.group(1)) if duration_match else None

    return {
        "title": title,
        "authors": authors,
        "venue": venue,
        "doi": doi,
        "intervention": intervention,
        "intervention_description": intervention_desc,
        "control": control,
        "n_total": n_total,
        "n_high_ability": n_high,
        "n_regular": n_regular,
        "duration_months": duration,
    }


def parse_findings(html_text: str) -> list:
    """Extrae cada hallazgo con su efecto, SE, IC y datos por brazo."""
    soup = BeautifulSoup(html_text, "html.parser")
    findings = []
    for card in soup.find_all("section", class_="finding-card"):
        h2 = card.find("h2", class_="h2")
        fid = int(re.search(r"\d+", h2.get_text()).group()) if h2 else None

        # Píldoras de resultado
        outcome_pills = card.find_all("span", class_="pill pill-out")
        outcome = clean_text(" ".join(p.get_text() for p in outcome_pills))

        # Medida
        measure_label = card.find("span", class_="lg-label", string=re.compile("Measure"))
        if measure_label:
            measure_spans = measure_label.find_parent().find_all("span")
            measure = clean_text(" ".join(s.get_text() for s in measure_spans if "lg-label" not in (s.get("class") or [])))
        else:
            measure = ""

        # Estimación del efecto
        stat = card.find("span", class_=re.compile("effect-stat"))
        g = to_float(stat.get_text()) if stat else None

        se_tag = card.find("span", class_="effect-se")
        if se_tag:
            se_match = re.search(r"SE = ([0-9.]+)", se_tag.get_text())
            se = float(se_match.group(1)) if se_match else None
        else:
            se = None

        ci_tag = card.find("div", class_="ci-text")
        ci_lower = ci_upper = None
        if ci_tag:
            ci_text = clean_text(ci_tag.get_text())
            m = re.search(r"CI\s*\[\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*\]", ci_text)
            if m:
                ci_lower = to_float(m.group(1))
                ci_upper = to_float(m.group(2))

        tags = [t.get_text() for t in card.find_all("span", class_="effect-tag")]
        clustering = "not clustering adjusted" if card.find(string=re.compile("Not clustering adjusted")) else "adjusted"

        # Datos por brazo
        n_int = n_ctrl = None
        for tr in card.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) >= 2:
                name = tds[0].get_text(strip=True)
                n_text = tds[1].get_text(strip=True)
                if n_text.isdigit():
                    if "Intervention" in name:
                        n_int = int(n_text)
                    elif "Control" in name:
                        n_ctrl = int(n_text)

        # Población según el texto de la medida
        if "HIGH_ITBS" in measure:
            population = "high-ability"
        elif "AVERAGE_ITBS" in measure or "Regular" in measure:
            population = "regular"
        else:
            population = "overall"

        findings.append({
            "finding_id": fid,
            "outcome": outcome,
            "measure": measure,
            "population": population,
            "hedges_g": g,
            "se": se,
            "ci_lower": ci_lower,
            "ci_upper": ci_upper,
            "adjustment": "; ".join(tags) if tags else None,
            "clustering_adjusted": clustering,
            "n_intervention": n_int,
            "n_control": n_ctrl,
        })
    return findings


def build_database(study: dict, findings: list) -> pd.DataFrame:
    """Crea un DataFrame que relaciona cada efecto con la información extraída."""
    for f in findings:
        for k, v in study.items():
            f[f"study_{k}"] = v
    return pd.DataFrame(findings)


def save_data(df: pd.DataFrame) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    df.to_csv(DATA_DIR / "klim_b_effects.csv", index=False)
    df.to_json(DATA_DIR / "klim_b_effects.json", orient="records", indent=2, force_ascii=False)
    print(f"Base de datos guardada en: {DATA_DIR}/klim_b_effects.csv")


def plot_forest(df: pd.DataFrame) -> None:
    """Visualización estática de los efectos e incertidumbre."""
    FIGS_DIR.mkdir(exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 4))

    labels = [f"Finding {row['finding_id']} ({row['population']})\n{row['measure']}" for _, row in df.iterrows()]
    colors = ["#2ecc71" if row["hedges_g"] > 0 else "#e74c3c" for _, row in df.iterrows()]

    for i, (_, row) in enumerate(df.iterrows()):
        x = row["hedges_g"]
        xerr = [[x - row["ci_lower"]], [row["ci_upper"] - x]]
        ax.errorbar(
            x, i, xerr=xerr, fmt="o",
            color=colors[i], ecolor=colors[i],
            capsize=4, elinewidth=2, markeredgewidth=2,
        )

    ax.axvline(0, color="black", linestyle="--", linewidth=1)
    ax.set_yticks(np.arange(len(df)))
    ax.set_yticklabels(labels)
    ax.set_xlabel("Hedges' g")
    ax.set_title("Efectos estimados e intervalos de confianza del 95%\nKerckhoff (1986) — Ability grouping")
    ax.grid(axis="x", alpha=0.3)

    path = FIGS_DIR / "klim_b_forest.png"
    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches="tight")
    print(f"Visualización guardada en: {path}")
    plt.close(fig)


def bayesian_posterior(obs: float, se: float, prior_mean: float, prior_sd: float):
    """Posterior normal conjugada: N(prior) + N(obs|se) = N(post)."""
    prior_var = prior_sd ** 2
    obs_var = se ** 2
    post_var = 1 / (1 / prior_var + 1 / obs_var)
    post_mean = post_var * (prior_mean / prior_var + obs / obs_var)
    post_sd = math.sqrt(post_var)
    return post_mean, post_sd, post_var


def bayesian_decision(df: pd.DataFrame, study: dict) -> str:
    """Análisis bayesiano, supuestos explícitos y recomendación."""
    if study["n_total"] is None or study["n_high_ability"] is None:
        p_high = p_regular = None
    else:
        p_high = study["n_high_ability"] / study["n_total"]
        p_regular = study["n_regular"] / study["n_total"]

    results = []
    for _, row in df.iterrows():
        post_mean, post_sd, post_var = bayesian_posterior(
            row["hedges_g"], row["se"], PRIOR_MEAN, PRIOR_SD
        )
        p_positive = 1 - stats.norm.cdf(0, loc=post_mean, scale=post_sd)
        p_meaningful = 1 - stats.norm.cdf(MEANINGFUL_THRESHOLD, loc=post_mean, scale=post_sd)
        results.append({
            "finding_id": row["finding_id"],
            "population": row["population"],
            "posterior_mean": post_mean,
            "posterior_sd": post_sd,
            "p_positive": p_positive,
            "p_meaningful": p_meaningful,
            "variance": post_var,
        })

    # Efecto esperado para toda la población mezclada (supuesto: independencia entre subgrupos)
    if p_high is not None:
        high = next(r for r in results if r["population"] == "high-ability")
        regular = next(r for r in results if r["population"] == "regular")
        overall_mean = p_high * high["posterior_mean"] + p_regular * regular["posterior_mean"]
        overall_var = (p_high ** 2) * high["variance"] + (p_regular ** 2) * regular["variance"]
        overall_sd = math.sqrt(overall_var)
        p_overall_positive = 1 - stats.norm.cdf(0, loc=overall_mean, scale=overall_sd)
        p_overall_meaningful = 1 - stats.norm.cdf(MEANINGFUL_THRESHOLD, loc=overall_mean, scale=overall_sd)
    else:
        high = next(r for r in results if r["population"] == "high-ability")
        regular = next(r for r in results if r["population"] == "regular")
        overall_mean = (high["posterior_mean"] + regular["posterior_mean"]) / 2
        overall_sd = math.sqrt((high["variance"] + regular["variance"]) / 4)
        p_overall_positive = 1 - stats.norm.cdf(0, loc=overall_mean, scale=overall_sd)
        p_overall_meaningful = 1 - stats.norm.cdf(MEANINGFUL_THRESHOLD, loc=overall_mean, scale=overall_sd)

    # Texto del análisis
    lines = []
    lines.append("# Análisis bayesiano y recomendación de financiación")
    lines.append("")
    lines.append("## Supuestos")
    lines.append(f"- Tamaño de efecto Hedges' *g* observado ~ Normal(δ, SE²).")
    lines.append(f"- Priori para el efecto verdadero: δ ~ N(μ={PRIOR_MEAN}, σ={PRIOR_SD}).")
    lines.append(f"- Umbral mínimo educativamente relevante: g = {MEANINGFUL_THRESHOLD}.")
    lines.append(f"- Regla de decisión: financiar si P(δ > {MEANINGFUL_THRESHOLD}) > {DECISION_CONFIDENCE*100:.0f}%.")
    if p_high is not None:
        lines.append(f"- Efecto general como mezcla ponderada por tamaños muestrales: {p_high:.2%} high-ability y {p_regular:.2%} regular.")
    lines.append("")

    lines.append("## Resultados posteriores")
    for r in results:
        lines.append(
            f"- Finding {r['finding_id']} ({r['population']}): "
            f"δ ~ N({r['posterior_mean']:.3f}, {r['posterior_sd']:.3f}²), "
            f"P(δ > 0) = {r['p_positive']:.3%}, "
            f"P(δ > {MEANINGFUL_THRESHOLD}) = {r['p_meaningful']:.3%}."
        )
    lines.append(
        f"- Población general (supuesta mezcla): "
        f"δ ~ N({overall_mean:.3f}, {overall_sd:.3f}²), "
        f"P(δ > 0) = {p_overall_positive:.3%}, "
        f"P(δ > {MEANINGFUL_THRESHOLD}) = {p_overall_meaningful:.3%}."
    )
    lines.append("")

    # Recomendación
    lines.append("## Recomendación")
    if high["p_meaningful"] > DECISION_CONFIDENCE:
        lines.append(
            "Financiar **solo si la iniciativa se dirige a estudiantes de alta habilidad**. "
            "El posterior indica un efecto positivo y relevante con alta probabilidad."
        )
    else:
        lines.append("No se recomienda financiar para la población de alta habilidad según el criterio elegido.")

    if regular["p_meaningful"] > DECISION_CONFIDENCE:
        lines.append("Además, se justifica financiar para estudiantes regulares.")
    else:
        lines.append(
            "No se recomienda financiar para estudiantes regulares ni para toda la población escolar, "
            "ya que el efecto esperado para la población mezclada es negativo o cercano a cero."
        )

    lines.append("")
    lines.append("## Circunstancias para financiar")
    lines.append("- La iniciativa puede **segmentar y atender exclusivamente a estudiantes de alta habilidad**.")
    lines.append(f"- El costo por estudiante es menor que el valor monetario esperado del beneficio "
                 f"(valor de {high['posterior_mean']:.2f} unidades de Hedges' g por participante).")
    lines.append("- Se acepta el supuesto de que los efectos observados en 1986 son transportables al contexto actual.")
    lines.append("- Se monitorea el impacto en los estudiantes regulares para evitar externalidades negativas.")

    report = "\n".join(lines)
    with open("klim_b_bayesian_report.md", "w", encoding="utf-8") as f:
        f.write(report)
    return report


def main() -> None:
    print("1. Descargando / leyendo la fuente...")
    html_text = fetch_html(URL, CACHE)

    print("2. Extrayendo metadatos y hallazgos...")
    study = parse_study(html_text)
    findings = parse_findings(html_text)

    print("3. Construyendo base de datos...")
    df = build_database(study, findings)
    save_data(df)
    print(df[["finding_id", "population", "measure", "hedges_g", "se", "ci_lower", "ci_upper"]])

    print("\n4. Generando visualización...")
    plot_forest(df)

    print("\n5. Análisis bayesiano...")
    report = bayesian_decision(df, study)
    print(report)


if __name__ == "__main__":
    main()
