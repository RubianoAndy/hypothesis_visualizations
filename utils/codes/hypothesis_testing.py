# -----------------------------------------------------------------------------
# Actividad: Pruebas de Hipotesis y Visualizacion Avanzada (Unidad 2)
# Maestria en Inteligencia Artificial - Universidad de La Salle
#
# Este script:
#   1. Genera el dataset de consumo de energia (semilla 42, reproducible)
#   2. Aplica pruebas de hipotesis con scipy.stats y statsmodels:
#      - Shapiro-Wilk (normalidad) y Levene (homogeneidad de varianzas)
#      - t de Student (2 muestras independientes)
#      - ANOVA de un factor + prueba post-hoc de Tukey
#      - Correlacion de Pearson + regresion lineal (OLS de statsmodels)
#   3. Genera 5 figuras con Matplotlib, Seaborn y Plotly
#
# Ejecucion (desde la raiz del proyecto):
#   python utils/codes/hypothesis_testing.py
# -----------------------------------------------------------------------------

import os

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
from scipy import stats
import statsmodels.api as sm
from statsmodels.formula.api import ols
from statsmodels.stats.multicomp import pairwise_tukeyhsd

# --- Rutas del proyecto (relativas a la raiz) --------------------------------
DATASET_PATH = "data/dataset/consumo_energia.csv"
PROCESSED_DIR = "data/processed"
FIGURES_DIR = "public/assets/images/figures/python/hypothesis"

# Nivel de significancia usado en todas las pruebas
ALPHA = 0.05

# Estilo general de los graficos
sns.set_theme(style="whitegrid")


# -----------------------------------------------------------------------------
# 1. GENERACION DEL DATASET (semilla 42 para que siempre salga igual)
# -----------------------------------------------------------------------------
def generate_dataset(n_per_sector=100):
    """Genera un dataset simulado de consumo mensual de energia en Colombia."""
    rng = np.random.default_rng(42)  # semilla fija -> reproducible

    sectors = ["Residencial", "Comercial", "Industrial"]
    # Cada sector tiene una media de consumo distinta (kWh/mes)
    means = {"Residencial": 180, "Comercial": 420, "Industrial": 900}
    stds = {"Residencial": 40, "Comercial": 90, "Industrial": 180}

    rows = []
    client_id = 1
    for sector in sectors:
        for _ in range(n_per_sector):
            # Temperatura promedio del mes (grados C) segun la region
            region = rng.choice(["Andina", "Caribe", "Pacifica"], p=[0.5, 0.3, 0.2])
            base_temp = {"Andina": 17, "Caribe": 29, "Pacifica": 26}[region]
            temperature = round(base_temp + rng.normal(0, 2), 1)

            # El consumo depende del sector y un poco de la temperatura
            # (a mas calor, mas ventilacion/refrigeracion -> mas consumo)
            consumption = rng.normal(means[sector], stds[sector])
            consumption += (temperature - 20) * 4  # efecto de la temperatura
            consumption = round(max(consumption, 30), 1)

            rows.append(
                {
                    "id_cliente": f"CL-{client_id:04d}",
                    "sector": sector,
                    "region": region,
                    "temperatura_c": temperature,
                    "consumo_kwh": consumption,
                }
            )
            client_id += 1

    df = pd.DataFrame(rows)
    df.to_csv(DATASET_PATH, index=False, encoding="utf-8")
    print(f"[OK] Dataset generado: {DATASET_PATH} ({len(df)} filas)")
    return df


# -----------------------------------------------------------------------------
# 2. PRUEBAS DE HIPOTESIS
# -----------------------------------------------------------------------------
def run_normality_and_levene(df):
    """Shapiro-Wilk por sector (normalidad) y Levene (homogeneidad de varianzas).

    H0 (Shapiro): los datos provienen de una distribucion normal.
    H0 (Levene):  las varianzas de los grupos son iguales.
    """
    results = []
    groups = []
    for sector, data in df.groupby("sector"):
        stat, p_value = stats.shapiro(data["consumo_kwh"])
        groups.append(data["consumo_kwh"])
        results.append(
            {
                "prueba": "Shapiro-Wilk",
                "grupo": sector,
                "estadistico": round(stat, 4),
                "p_valor": round(p_value, 4),
                "decision": "No se rechaza H0 (normal)" if p_value > ALPHA else "Se rechaza H0 (no normal)",
            }
        )

    # Levene compara las varianzas de los 3 sectores a la vez
    stat, p_value = stats.levene(*groups)
    results.append(
        {
            "prueba": "Levene",
            "grupo": "Los 3 sectores",
            "estadistico": round(stat, 4),
            "p_valor": round(p_value, 4),
            "decision": "Varianzas iguales" if p_value > ALPHA else "Varianzas distintas",
        }
    )

    out = pd.DataFrame(results)
    out.to_csv(f"{PROCESSED_DIR}/normality_tests.csv", index=False, encoding="utf-8")
    print("[OK] Pruebas de normalidad y Levene -> normality_tests.csv")
    return out


def run_ttest(df):
    """t de Student para 2 muestras independientes (scipy.stats).

    H0: el consumo medio del sector Residencial es igual al del Comercial.
    H1: los consumos medios son diferentes.
    """
    residential = df[df["sector"] == "Residencial"]["consumo_kwh"]
    commercial = df[df["sector"] == "Comercial"]["consumo_kwh"]

    stat, p_value = stats.ttest_ind(residential, commercial, equal_var=False)

    out = pd.DataFrame(
        [
            {
                "prueba": "t de Student (Welch)",
                "grupo_1": "Residencial",
                "media_1": round(residential.mean(), 2),
                "grupo_2": "Comercial",
                "media_2": round(commercial.mean(), 2),
                "estadistico_t": round(stat, 4),
                "p_valor": round(p_value, 6),
                "decision": "Se rechaza H0: las medias son diferentes" if p_value < ALPHA else "No se rechaza H0",
            }
        ]
    )
    out.to_csv(f"{PROCESSED_DIR}/ttest_results.csv", index=False, encoding="utf-8")
    print("[OK] Prueba t -> ttest_results.csv")
    return out


def run_anova_tukey(df):
    """ANOVA de un factor (statsmodels) + post-hoc de Tukey.

    H0: el consumo medio es igual en los 3 sectores.
    H1: al menos un sector tiene un consumo medio diferente.
    """
    # ANOVA con formula estilo R: consumo ~ sector
    model = ols("consumo_kwh ~ C(sector)", data=df).fit()
    anova_table = sm.stats.anova_lm(model, typ=2)
    anova_table.to_csv(f"{PROCESSED_DIR}/anova_results.csv", encoding="utf-8")

    # Tukey dice ENTRE CUALES sectores hay diferencias
    tukey = pairwise_tukeyhsd(df["consumo_kwh"], df["sector"], alpha=ALPHA)
    tukey_df = pd.DataFrame(tukey.summary().data[1:], columns=tukey.summary().data[0])
    tukey_df.to_csv(f"{PROCESSED_DIR}/tukey_posthoc.csv", index=False, encoding="utf-8")

    print("[OK] ANOVA -> anova_results.csv | Tukey -> tukey_posthoc.csv")
    return anova_table, tukey_df


def run_correlation_regression(df):
    """Correlacion de Pearson (scipy) + regresion lineal OLS (statsmodels).

    H0: no existe relacion lineal entre temperatura y consumo (r = 0).
    H1: existe relacion lineal (r != 0).
    """
    r, p_value = stats.pearsonr(df["temperatura_c"], df["consumo_kwh"])

    # Regresion lineal simple: consumo = b0 + b1 * temperatura
    x = sm.add_constant(df["temperatura_c"])
    model = sm.OLS(df["consumo_kwh"], x).fit()

    rows = [
        {
            "prueba": "Pearson + OLS (global)",
            "r_pearson": round(r, 4),
            "p_valor": round(p_value, 6),
            "intercepto_b0": round(model.params["const"], 2),
            "pendiente_b1": round(model.params["temperatura_c"], 2),
            "r_cuadrado": round(model.rsquared, 4),
            "decision": "Relacion significativa" if p_value < ALPHA else "Sin relacion significativa",
        }
    ]

    # Insight clave: la correlacion GLOBAL se diluye porque los sectores tienen
    # niveles de consumo muy distintos. Al analizar POR SECTOR, la relacion
    # temperatura-consumo si aparece (esto se ve claramente en las figuras 4 y 5).
    for sector, data in df.groupby("sector"):
        r_s, p_s = stats.pearsonr(data["temperatura_c"], data["consumo_kwh"])
        rows.append(
            {
                "prueba": f"Pearson ({sector})",
                "r_pearson": round(r_s, 4),
                "p_valor": round(p_s, 6),
                "intercepto_b0": None,
                "pendiente_b1": None,
                "r_cuadrado": None,
                "decision": "Relacion significativa" if p_s < ALPHA else "Sin relacion significativa",
            }
        )

    out = pd.DataFrame(rows)
    out.to_csv(f"{PROCESSED_DIR}/regression_results.csv", index=False, encoding="utf-8")
    print("[OK] Correlacion y regresion -> regression_results.csv")
    return model


# -----------------------------------------------------------------------------
# 3. FIGURAS (Matplotlib, Seaborn y Plotly)
# -----------------------------------------------------------------------------
def plot_histogram_normality(df):
    """Figura 1 (Matplotlib): histograma + curva normal teorica (Residencial)."""
    data = df[df["sector"] == "Residencial"]["consumo_kwh"]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(data, bins=15, density=True, color="#4C72B0", edgecolor="white", alpha=0.8, label="Datos")

    # Curva normal con la media y desviacion de los datos
    x = np.linspace(data.min(), data.max(), 200)
    ax.plot(x, stats.norm.pdf(x, data.mean(), data.std()), "r-", lw=2, label="Normal teorica")

    ax.set_title("Figura 1. Verificacion de normalidad - Sector Residencial (Shapiro-Wilk)")
    ax.set_xlabel("Consumo (kWh/mes)")
    ax.set_ylabel("Densidad")
    ax.legend()
    fig.tight_layout()
    fig.savefig(f"{FIGURES_DIR}/fig1_histograma_normalidad.png", dpi=150)
    plt.close(fig)


def plot_boxplot_anova(df):
    """Figura 2 (Seaborn): boxplot del consumo por sector (apoya el ANOVA)."""
    fig, ax = plt.subplots(figsize=(8, 5))
    sns.boxplot(data=df, x="sector", y="consumo_kwh", hue="sector", palette="Set2", ax=ax)
    sns.stripplot(data=df, x="sector", y="consumo_kwh", color="gray", size=2.5, alpha=0.4, ax=ax)

    ax.set_title("Figura 2. Consumo de energia por sector (ANOVA de un factor)")
    ax.set_xlabel("Sector")
    ax.set_ylabel("Consumo (kWh/mes)")
    fig.tight_layout()
    fig.savefig(f"{FIGURES_DIR}/fig2_boxplot_sectores.png", dpi=150)
    plt.close(fig)


def plot_means_ci(df):
    """Figura 3 (Matplotlib): medias con intervalos de confianza del 95%."""
    fig, ax = plt.subplots(figsize=(8, 5))

    sectors = df["sector"].unique()
    means, errors = [], []
    for sector in sectors:
        data = df[df["sector"] == sector]["consumo_kwh"]
        means.append(data.mean())
        # Margen de error del IC 95%: t * error estandar
        se = data.std() / np.sqrt(len(data))
        errors.append(stats.t.ppf(0.975, len(data) - 1) * se)

    ax.bar(sectors, means, yerr=errors, capsize=8, color=["#66C2A5", "#FC8D62", "#8DA0CB"], edgecolor="black")
    ax.set_title("Figura 3. Consumo medio por sector con IC del 95% (prueba t / ANOVA)")
    ax.set_xlabel("Sector")
    ax.set_ylabel("Consumo medio (kWh/mes)")
    fig.tight_layout()
    fig.savefig(f"{FIGURES_DIR}/fig3_medias_ic95.png", dpi=150)
    plt.close(fig)


def plot_regression_seaborn(df):
    """Figura 4 (Seaborn): dispersion + recta de regresion (Pearson / OLS)."""
    fig, ax = plt.subplots(figsize=(8, 5))
    sns.regplot(
        data=df, x="temperatura_c", y="consumo_kwh",
        scatter_kws={"alpha": 0.4, "s": 18}, line_kws={"color": "red"}, ax=ax,
    )
    ax.set_title("Figura 4. Relacion temperatura vs consumo (Pearson y regresion OLS)")
    ax.set_xlabel("Temperatura promedio (°C)")
    ax.set_ylabel("Consumo (kWh/mes)")
    fig.tight_layout()
    fig.savefig(f"{FIGURES_DIR}/fig4_regresion_temperatura.png", dpi=150)
    plt.close(fig)


def plot_interactive_plotly(df):
    """Figura 5 (Plotly): grafico INTERACTIVO de dispersion por sector.

    Se guarda en HTML (interactivo, se abre en el navegador) y en PNG
    (version estatica para insertar en el informe PDF).
    """
    fig = px.scatter(
        df,
        x="temperatura_c",
        y="consumo_kwh",
        color="sector",
        hover_data=["id_cliente", "region"],  # info que aparece al pasar el mouse
        trendline="ols",  # recta de regresion por sector (usa statsmodels)
        title="Figura 5. Consumo vs temperatura por sector (interactivo - Plotly)",
        labels={"temperatura_c": "Temperatura promedio (°C)", "consumo_kwh": "Consumo (kWh/mes)"},
    )
    fig.write_html(f"{FIGURES_DIR}/fig5_interactivo_plotly.html")

    # El PNG estatico requiere Chrome instalado (lo usa kaleido).
    # Si no esta disponible, el HTML interactivo igual queda generado.
    try:
        fig.write_image(f"{FIGURES_DIR}/fig5_interactivo_plotly.png", width=900, height=550, scale=2)
    except Exception:
        print("[AVISO] No se pudo exportar el PNG de Plotly (falta Chrome).")
        print("        Ejecute 'plotly_get_chrome' o tome una captura del HTML.")


# -----------------------------------------------------------------------------
# PROGRAMA PRINCIPAL
# -----------------------------------------------------------------------------
def main():
    os.makedirs(os.path.dirname(DATASET_PATH), exist_ok=True)
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    os.makedirs(FIGURES_DIR, exist_ok=True)

    # 1. Dataset
    df = generate_dataset()

    # 2. Pruebas de hipotesis
    run_normality_and_levene(df)
    run_ttest(df)
    run_anova_tukey(df)
    run_correlation_regression(df)

    # 3. Figuras
    plot_histogram_normality(df)
    plot_boxplot_anova(df)
    plot_means_ci(df)
    plot_regression_seaborn(df)
    plot_interactive_plotly(df)
    print(f"[OK] 5 figuras guardadas en {FIGURES_DIR}")


if __name__ == "__main__":
    main()
