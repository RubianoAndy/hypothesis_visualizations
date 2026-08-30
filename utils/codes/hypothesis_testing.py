# -----------------------------------------------------------------------------
# Actividad: Pruebas de Hipotesis y Visualizacion Avanzada (Unidad 2)
# Maestria en Inteligencia Artificial - Universidad de La Salle
#
# Este script:
#   1. Genera el dataset de consumo de energia (semilla 42, reproducible)
#   2. Aplica pruebas de hipotesis con scipy.stats y statsmodels:
#      - Shapiro-Wilk (normalidad) y Levene (homogeneidad de varianzas)
#      - t de Student con correccion de Welch (2 muestras independientes)
#      - ANOVA de un factor + prueba post-hoc de Tukey HSD
#      - Correlacion de Pearson + regresion lineal (OLS de statsmodels)
#   3. Cuantifica la MAGNITUD del efecto, no solo su significancia:
#      - d de Cohen y g de Hedges con IC del 95 % (comparacion de dos medias)
#      - eta cuadrado y omega cuadrado (ANOVA)
#      - potencia observada y correlacion minima detectable
#   4. Verifica la robustez de las conclusiones ante heterocedasticidad:
#      - ANOVA de Welch (no asume varianzas iguales)
#      - post-hoc de Games-Howell (alternativa a Tukey sin homocedasticidad)
#   5. Genera 9 figuras con Matplotlib, Seaborn y Plotly, dos de ellas
#      interactivas (dispersion por sector y dashboard de cuatro paneles)
#
# Ejecucion (desde la raiz del proyecto):
#   python utils/codes/hypothesis_testing.py
# -----------------------------------------------------------------------------

import os
import itertools

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy import stats
import statsmodels.api as sm
from statsmodels.formula.api import ols
from statsmodels.stats.multicomp import pairwise_tukeyhsd
from statsmodels.stats.power import TTestIndPower, FTestAnovaPower

# --- Rutas del proyecto (relativas a la raiz) --------------------------------
DATASET_PATH = "data/dataset/consumo_energia.csv"
PROCESSED_DIR = "data/processed"
FIGURES_DIR = "public/assets/images/figures/python/hypothesis"

# Nivel de significancia usado en todas las pruebas
ALPHA = 0.05

# Orden de los sectores por nivel de consumo: se fija una sola vez para que las
# nueve figuras y todas las tablas presenten los grupos en la misma secuencia.
SECTOR_ORDER = ["Residencial", "Comercial", "Industrial"]
SECTOR_COLORS = {
    "Residencial": "#66C2A5",
    "Comercial": "#FC8D62",
    "Industrial": "#8DA0CB",
}

# Estilo general de los graficos
sns.set_theme(style="whitegrid")
plt.rcParams["axes.titlesize"] = 12
plt.rcParams["axes.titleweight"] = "bold"

# Caja usada para depositar el resultado de la prueba sobre la propia figura.
# Que el estadistico y el valor p viajen dentro de la imagen evita que el
# lector tenga que emparejarla con una tabla situada en otra pagina.
STAT_BOX = dict(boxstyle="round,pad=0.45", facecolor="white",
                edgecolor="#B0B0B0", alpha=0.9)


def dec(value, digits=2):
    """Numero con coma decimal, la convencion tipografica del informe."""
    return f"{value:.{digits}f}".replace(".", ",")


def format_p(p_value):
    """Formatea un valor p con la convencion habitual en informes."""
    if p_value < 0.001:
        return "p < 0,001"
    return f"p = {p_value:.3f}".replace(".", ",")


# -----------------------------------------------------------------------------
# 1. GENERACION DEL DATASET (semilla 42 para que siempre salga igual)
# -----------------------------------------------------------------------------
def generate_dataset(n_per_sector=100):
    """Genera un dataset simulado de consumo mensual de energia en Colombia."""
    rng = np.random.default_rng(42)  # semilla fija -> reproducible

    # Cada sector tiene una media de consumo distinta (kWh/mes)
    means = {"Residencial": 180, "Comercial": 420, "Industrial": 900}
    stds = {"Residencial": 40, "Comercial": 90, "Industrial": 180}

    rows = []
    client_id = 1
    for sector in SECTOR_ORDER:
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


def sector_series(df, sector):
    """Devuelve el consumo de un sector como Series."""
    return df.loc[df["sector"] == sector, "consumo_kwh"]


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
    for sector in SECTOR_ORDER:
        data = sector_series(df, sector)
        stat, p_value = stats.shapiro(data)
        groups.append(data)
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
    residential = sector_series(df, "Residencial")
    commercial = sector_series(df, "Comercial")

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
            "ambito": "Global",
            "prueba": "Pearson + OLS (global)",
            "n": len(df),
            "r_pearson": round(r, 4),
            "p_valor": round(p_value, 6),
            "intercepto_b0": round(model.params["const"], 2),
            "pendiente_b1": round(model.params["temperatura_c"], 2),
            "desv_consumo": round(df["consumo_kwh"].std(ddof=1), 2),
            "r_cuadrado": round(model.rsquared, 4),
            "decision": "Relacion significativa" if p_value < ALPHA else "Sin relacion significativa",
        }
    ]

    # Insight clave: la correlacion GLOBAL se diluye porque los sectores tienen
    # niveles de consumo muy distintos. Al analizar POR SECTOR, la relacion
    # temperatura-consumo si aparece (esto se ve claramente en las figuras 4 y 5).
    for sector in SECTOR_ORDER:
        data = df[df["sector"] == sector]
        r_s, p_s = stats.pearsonr(data["temperatura_c"], data["consumo_kwh"])
        # La pendiente por sector es la que demuestra que el efecto sobrevive a
        # la agregacion aunque la correlacion estandarizada se desplome.
        x_s = sm.add_constant(data["temperatura_c"])
        model_s = sm.OLS(data["consumo_kwh"], x_s).fit()
        rows.append(
            {
                "ambito": sector,
                "prueba": f"Pearson ({sector})",
                "n": len(data),
                "r_pearson": round(r_s, 4),
                "p_valor": round(p_s, 6),
                "intercepto_b0": round(model_s.params["const"], 2),
                "pendiente_b1": round(model_s.params["temperatura_c"], 2),
                "desv_consumo": round(data["consumo_kwh"].std(ddof=1), 2),
                "r_cuadrado": round(model_s.rsquared, 4),
                "decision": "Relacion significativa" if p_s < ALPHA else "Sin relacion significativa",
            }
        )

    out = pd.DataFrame(rows)
    out.to_csv(f"{PROCESSED_DIR}/regression_results.csv", index=False, encoding="utf-8")
    print("[OK] Correlacion y regresion -> regression_results.csv")
    return model, out


# -----------------------------------------------------------------------------
# 2.5 TAMANO DEL EFECTO Y POTENCIA
#
# Un valor p responde "es distinguible del azar?", no "importa?". Con n = 100
# por grupo casi cualquier diferencia alcanza significancia, de modo que la
# decision practica debe apoyarse en la magnitud estandarizada del efecto.
# -----------------------------------------------------------------------------
def interpret_d(d):
    """Convencion de Cohen (1988) para diferencias estandarizadas de medias."""
    d = abs(d)
    if d < 0.20:
        return "Efecto insignificante"
    if d < 0.50:
        return "Efecto pequeno"
    if d < 0.80:
        return "Efecto mediano"
    return "Efecto grande"


def interpret_eta(eta):
    """Convencion de Cohen para proporciones de varianza explicada."""
    if eta < 0.01:
        return "Efecto insignificante"
    if eta < 0.06:
        return "Efecto pequeno"
    if eta < 0.14:
        return "Efecto mediano"
    return "Efecto grande"


def run_effect_sizes(df, anova_table):
    """d de Cohen, g de Hedges, eta cuadrado, omega cuadrado y potencia."""
    residential = sector_series(df, "Residencial")
    commercial = sector_series(df, "Comercial")
    n1, n2 = len(residential), len(commercial)
    s1, s2 = residential.std(ddof=1), commercial.std(ddof=1)

    # d de Cohen con desviacion combinada (pooled)
    pooled_sd = np.sqrt(((n1 - 1) * s1**2 + (n2 - 1) * s2**2) / (n1 + n2 - 2))
    cohen_d = (commercial.mean() - residential.mean()) / pooled_sd

    # g de Hedges: d corregida por el sesgo al alza en muestras pequenas
    correction = 1 - 3 / (4 * (n1 + n2) - 9)
    hedges_g = cohen_d * correction

    # IC del 95 % de d por la aproximacion normal del error estandar
    se_d = np.sqrt((n1 + n2) / (n1 * n2) + cohen_d**2 / (2 * (n1 + n2)))
    z = stats.norm.ppf(1 - ALPHA / 2)
    d_low, d_high = cohen_d - z * se_d, cohen_d + z * se_d

    # eta cuadrado y omega cuadrado a partir de la tabla ANOVA de statsmodels
    ss_between = anova_table.loc["C(sector)", "sum_sq"]
    ss_within = anova_table.loc["Residual", "sum_sq"]
    df_between = int(anova_table.loc["C(sector)", "df"])
    df_within = int(anova_table.loc["Residual", "df"])
    ss_total = ss_between + ss_within
    ms_within = ss_within / df_within

    eta_sq = ss_between / ss_total
    # omega cuadrado penaliza el sesgo optimista de eta cuadrado
    omega_sq = (ss_between - df_between * ms_within) / (ss_total + ms_within)
    # f de Cohen: el tamano de efecto que consume el analisis de potencia
    cohen_f = np.sqrt(eta_sq / (1 - eta_sq))

    # Potencia observada de cada contraste
    power_t = TTestIndPower().power(effect_size=abs(cohen_d), nobs1=n1,
                                    ratio=1.0, alpha=ALPHA)
    power_anova = FTestAnovaPower().power(effect_size=cohen_f, nobs=len(df),
                                          alpha=ALPHA, k_groups=3)

    # Analisis de sensibilidad sobre la correlacion global: con n = 300, cual es
    # la correlacion mas pequena detectable con una potencia del 80 %? Si el r
    # observado queda por debajo de ese umbral, la no significancia es un
    # problema de magnitud estandarizada y no de tamano muestral insuficiente.
    n_global = len(df)
    z_alpha = stats.norm.ppf(1 - ALPHA / 2)
    z_beta = stats.norm.ppf(0.80)
    fisher_z = (z_alpha + z_beta) / np.sqrt(n_global - 3)
    r_detectable = np.tanh(fisher_z)

    r_global, _ = stats.pearsonr(df["temperatura_c"], df["consumo_kwh"])
    r_res, _ = stats.pearsonr(
        df.loc[df["sector"] == "Residencial", "temperatura_c"],
        df.loc[df["sector"] == "Residencial", "consumo_kwh"],
    )

    rows = [
        {"medida": "d de Cohen (Res. vs Com.)", "valor": round(cohen_d, 4),
         "ic_inferior": round(d_low, 4), "ic_superior": round(d_high, 4),
         "interpretacion": interpret_d(cohen_d)},
        {"medida": "g de Hedges (Res. vs Com.)", "valor": round(hedges_g, 4),
         "ic_inferior": None, "ic_superior": None,
         "interpretacion": interpret_d(hedges_g)},
        {"medida": "eta cuadrado (ANOVA sector)", "valor": round(eta_sq, 4),
         "ic_inferior": None, "ic_superior": None,
         "interpretacion": interpret_eta(eta_sq)},
        {"medida": "omega cuadrado (ANOVA sector)", "valor": round(omega_sq, 4),
         "ic_inferior": None, "ic_superior": None,
         "interpretacion": interpret_eta(omega_sq)},
        {"medida": "f de Cohen (ANOVA sector)", "valor": round(cohen_f, 4),
         "ic_inferior": None, "ic_superior": None,
         "interpretacion": "Efecto grande" if cohen_f >= 0.40 else "Efecto medio"},
        {"medida": "Potencia observada (t de Welch)", "valor": round(power_t, 4),
         "ic_inferior": None, "ic_superior": None,
         "interpretacion": "Potencia practicamente maxima"},
        {"medida": "Potencia observada (ANOVA)", "valor": round(power_anova, 4),
         "ic_inferior": None, "ic_superior": None,
         "interpretacion": "Potencia practicamente maxima"},
        {"medida": "r minimo detectable (n = 300, potencia 0,80)",
         "valor": round(r_detectable, 4), "ic_inferior": None, "ic_superior": None,
         "interpretacion": f"r global observado = {r_global:.3f}, por debajo del umbral"},
        {"medida": "r Residencial frente al umbral", "valor": round(r_res, 4),
         "ic_inferior": None, "ic_superior": None,
         "interpretacion": "Supera el umbral: el diseno si tiene potencia para detectarlo"},
    ]

    out = pd.DataFrame(rows)
    out.to_csv(f"{PROCESSED_DIR}/effect_sizes.csv", index=False, encoding="utf-8")
    print("[OK] Tamanos de efecto y potencia -> effect_sizes.csv")
    return {
        "cohen_d": cohen_d, "hedges_g": hedges_g, "d_ci": (d_low, d_high),
        "eta_sq": eta_sq, "omega_sq": omega_sq, "cohen_f": cohen_f,
        "power_t": power_t, "power_anova": power_anova,
        "r_detectable": r_detectable,
    }


# -----------------------------------------------------------------------------
# 2.6 ROBUSTEZ ANTE HETEROCEDASTICIDAD
#
# Levene rechaza la igualdad de varianzas, y tanto el ANOVA clasico como Tukey
# la asumen. En vez de dejarlo anotado como limitacion se repite el contraste
# con las versiones que no exigen ese supuesto: si la decision no cambia, la
# conclusion queda respaldada; si cambiara, habria que reportar la robusta.
# -----------------------------------------------------------------------------
def welch_anova(groups):
    """ANOVA de Welch: F, grados de libertad y valor p sin homocedasticidad."""
    k = len(groups)
    n = np.array([len(g) for g in groups], dtype=float)
    means = np.array([g.mean() for g in groups])
    variances = np.array([g.var(ddof=1) for g in groups])

    weights = n / variances               # peso inverso a la varianza del grupo
    total_weight = weights.sum()
    weighted_mean = (weights * means).sum() / total_weight

    numerator = (weights * (means - weighted_mean) ** 2).sum() / (k - 1)
    lam = ((1 - weights / total_weight) ** 2 / (n - 1)).sum()
    denominator = 1 + (2 * (k - 2) / (k**2 - 1)) * lam

    f_stat = numerator / denominator
    df1 = k - 1
    df2 = (k**2 - 1) / (3 * lam)
    p_value = stats.f.sf(f_stat, df1, df2)
    return f_stat, df1, df2, p_value


def games_howell(df):
    """Post-hoc de Games-Howell: la alternativa a Tukey sin varianzas iguales.

    Usa el error estandar de Welch en cada par y los grados de libertad de
    Welch-Satterthwaite, contrastando contra la distribucion del rango
    estudentizado igual que Tukey.
    """
    k = len(SECTOR_ORDER)
    rows = []
    for a, b in itertools.combinations(SECTOR_ORDER, 2):
        ga, gb = sector_series(df, a), sector_series(df, b)
        na, nb = len(ga), len(gb)
        va, vb = ga.var(ddof=1), gb.var(ddof=1)
        diff = gb.mean() - ga.mean()

        se = np.sqrt(va / na + vb / nb)
        # Grados de libertad de Welch-Satterthwaite para este par
        df_wl = (va / na + vb / nb) ** 2 / (
            (va / na) ** 2 / (na - 1) + (vb / nb) ** 2 / (nb - 1)
        )
        q_stat = abs(diff) / se * np.sqrt(2)
        p_adj = stats.studentized_range.sf(q_stat, k, df_wl)
        q_crit = stats.studentized_range.ppf(1 - ALPHA, k, df_wl)
        margin = q_crit / np.sqrt(2) * se

        rows.append(
            {
                "comparacion": f"{b} - {a}",
                "diferencia": round(diff, 3),
                "ic_inferior": round(diff - margin, 3),
                "ic_superior": round(diff + margin, 3),
                "q": round(q_stat, 3),
                "gl_welch": round(df_wl, 2),
                "p_ajustado": float(f"{p_adj:.3e}"),
                "decision": "Se rechaza H0" if p_adj < ALPHA else "No se rechaza H0",
            }
        )
    return pd.DataFrame(rows)


def run_robust_checks(df):
    """Ejecuta el ANOVA de Welch y el post-hoc de Games-Howell."""
    groups = [sector_series(df, s) for s in SECTOR_ORDER]
    f_stat, df1, df2, p_value = welch_anova(groups)

    welch_row = pd.DataFrame(
        [
            {
                "prueba": "ANOVA de Welch (sin homocedasticidad)",
                "estadistico_f": round(f_stat, 4),
                "gl_numerador": df1,
                "gl_denominador": round(df2, 2),
                "p_valor": float(f"{p_value:.3e}"),
                "decision": "Se rechaza H0" if p_value < ALPHA else "No se rechaza H0",
            }
        ]
    )
    welch_row.to_csv(f"{PROCESSED_DIR}/welch_anova.csv", index=False, encoding="utf-8")

    gh = games_howell(df)
    gh.to_csv(f"{PROCESSED_DIR}/games_howell.csv", index=False, encoding="utf-8")
    print("[OK] ANOVA de Welch -> welch_anova.csv | Games-Howell -> games_howell.csv")
    return welch_row, gh


# -----------------------------------------------------------------------------
# 3. FIGURAS (Matplotlib, Seaborn y Plotly)
# -----------------------------------------------------------------------------
def plot_histogram_normality(df):
    """Figura 1 (Matplotlib): histograma + curva normal teorica (Residencial)."""
    data = sector_series(df, "Residencial")
    stat, p_value = stats.shapiro(data)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(data, bins=15, density=True, color="#4C72B0", edgecolor="white",
            alpha=0.8, label="Datos observados")

    # Curva normal con la media y desviacion de los datos
    x = np.linspace(data.min(), data.max(), 200)
    ax.plot(x, stats.norm.pdf(x, data.mean(), data.std()), "r-", lw=2,
            label="Normal teórica")

    ax.set_title("Verificación de normalidad — Sector Residencial (Shapiro-Wilk)")
    ax.set_xlabel("Consumo (kWh/mes)")
    ax.set_ylabel("Densidad")
    ax.legend(loc="upper right")
    ax.text(0.02, 0.97,
            f"Shapiro-Wilk: W = {dec(stat, 4)}\n{format_p(p_value)}\n"
            f"No se rechaza $H_0$ (α = 0,05)",
            transform=ax.transAxes, va="top", ha="left", fontsize=9, bbox=STAT_BOX)
    fig.tight_layout()
    fig.savefig(f"{FIGURES_DIR}/histograma_normalidad.png", dpi=150)
    plt.close(fig)


def plot_boxplot_anova(df, anova_table, eta_sq):
    """Figura 2 (Seaborn): boxplot del consumo por sector (apoya el ANOVA)."""
    f_stat = anova_table.loc["C(sector)", "F"]
    p_value = anova_table.loc["C(sector)", "PR(>F)"]

    fig, ax = plt.subplots(figsize=(8, 5))
    # El violin anade lo que la caja oculta: la forma de cada distribucion, que
    # es donde se ve que la dispersion crece con el nivel del sector.
    sns.violinplot(data=df, x="sector", y="consumo_kwh", order=SECTOR_ORDER,
                   hue="sector", hue_order=SECTOR_ORDER, palette=SECTOR_COLORS,
                   inner=None, cut=0, alpha=0.28, legend=False, ax=ax)
    sns.boxplot(data=df, x="sector", y="consumo_kwh", order=SECTOR_ORDER,
                hue="sector", hue_order=SECTOR_ORDER, palette=SECTOR_COLORS,
                width=0.32, showfliers=False, legend=False, ax=ax)
    sns.stripplot(data=df, x="sector", y="consumo_kwh", order=SECTOR_ORDER,
                  color="gray", size=2.5, alpha=0.4, ax=ax)

    ax.set_title("Consumo de energía por sector (ANOVA de un factor)")
    ax.set_xlabel("Sector")
    ax.set_ylabel("Consumo (kWh/mes)")
    ax.text(0.02, 0.97,
            f"ANOVA: F(2, 297) = {dec(f_stat)}\n{format_p(p_value)}\n"
            f"$\\eta^2$ = {dec(eta_sq, 3)} (efecto grande)",
            transform=ax.transAxes, va="top", ha="left", fontsize=9, bbox=STAT_BOX)
    fig.tight_layout()
    fig.savefig(f"{FIGURES_DIR}/boxplot_sectores.png", dpi=150)
    plt.close(fig)


def compact_letters(tukey_df):
    """Letras de significancia: dos sectores comparten letra si no difieren."""
    significant = set()
    for _, row in tukey_df.iterrows():
        if bool(row["reject"]):
            significant.add(frozenset((row["group1"], row["group2"])))

    letters = {}
    for sector in SECTOR_ORDER:
        for letter in "abcdefghij":
            # Un sector adopta una letra si no difiere de ninguno que ya la use
            holders = [s for s, ls in letters.items() if letter in ls]
            if all(frozenset((sector, other)) not in significant for other in holders):
                letters[sector] = letters.get(sector, "") + letter
                break
    return letters


def plot_means_ci(df, tukey_df):
    """Figura 3 (Matplotlib): medias con intervalos de confianza del 95%."""
    fig, ax = plt.subplots(figsize=(8, 5))

    means, errors = [], []
    for sector in SECTOR_ORDER:
        data = sector_series(df, sector)
        means.append(data.mean())
        # Margen de error del IC 95%: t * error estandar
        se = data.std() / np.sqrt(len(data))
        errors.append(stats.t.ppf(0.975, len(data) - 1) * se)

    colors = [SECTOR_COLORS[s] for s in SECTOR_ORDER]
    bars = ax.bar(SECTOR_ORDER, means, yerr=errors, capsize=8, color=colors,
                  edgecolor="black")

    # Letras de Tukey: sectores con letras distintas difieren significativamente.
    # Es la traduccion grafica del post-hoc, legible sin consultar la tabla.
    letters = compact_letters(tukey_df)
    for bar, mean, error, sector in zip(bars, means, errors, SECTOR_ORDER):
        ax.text(bar.get_x() + bar.get_width() / 2, mean + error + 22,
                f"{dec(mean, 1)}\n({letters[sector]})", ha="center", va="bottom",
                fontsize=10, fontweight="bold")

    ax.set_ylim(0, max(m + e for m, e in zip(means, errors)) * 1.25)
    ax.set_title("Consumo medio por sector con IC del 95 % (prueba t / ANOVA)")
    ax.set_xlabel("Sector")
    ax.set_ylabel("Consumo medio (kWh/mes)")
    ax.text(0.02, 0.97,
            "Letras distintas indican\ndiferencia significativa\n(Tukey HSD, α = 0,05)",
            transform=ax.transAxes, va="top", ha="left", fontsize=9, bbox=STAT_BOX)
    fig.tight_layout()
    fig.savefig(f"{FIGURES_DIR}/medias_ic95.png", dpi=150)
    plt.close(fig)


def plot_regression_seaborn(df, model):
    """Figura 4 (Seaborn): dispersion + recta de regresion (Pearson / OLS)."""
    r, p_value = stats.pearsonr(df["temperatura_c"], df["consumo_kwh"])

    fig, ax = plt.subplots(figsize=(8, 5))
    sns.regplot(
        data=df, x="temperatura_c", y="consumo_kwh",
        scatter_kws={"alpha": 0.4, "s": 18}, line_kws={"color": "red"}, ax=ax,
    )
    ax.set_title("Relación temperatura vs. consumo (Pearson y regresión OLS)")
    ax.set_xlabel("Temperatura promedio (°C)")
    ax.set_ylabel("Consumo (kWh/mes)")
    b0 = model.params["const"]
    b1 = model.params["temperatura_c"]
    ax.text(0.02, 0.97,
            f"Pearson: r = {dec(r, 3)}; {format_p(p_value)}\n"
            f"$\\hat{{Y}}$ = {dec(b0)} + {dec(b1)}·T\n"
            f"$R^2$ = {dec(model.rsquared, 4)} — No se rechaza $H_0$",
            transform=ax.transAxes, va="top", ha="left", fontsize=9, bbox=STAT_BOX)
    fig.tight_layout()
    fig.savefig(f"{FIGURES_DIR}/regresion_temperatura.png", dpi=150)
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
        category_orders={"sector": SECTOR_ORDER},
        color_discrete_map=SECTOR_COLORS,
        hover_data=["id_cliente", "region"],  # info que aparece al pasar el mouse
        trendline="ols",  # recta de regresion por sector (usa statsmodels)
        # title="Figura 5. Consumo vs. temperatura por sector (interactivo · Plotly)",
        labels={"temperatura_c": "Temperatura promedio (°C)",
                "consumo_kwh": "Consumo (kWh/mes)", "sector": "Sector"},
    )
    fig.update_traces(marker=dict(size=7, line=dict(width=0.5, color="white")))
    fig.update_layout(template="plotly_white", legend_title_text="Sector",
                      title_font_size=15)
    fig.write_html(f"{FIGURES_DIR}/dispersion_interactiva_plotly.html")

    # El PNG estatico requiere Chrome instalado (lo usa kaleido).
    # Si no esta disponible, el HTML interactivo igual queda generado.
    try:
        fig.write_image(f"{FIGURES_DIR}/dispersion_interactiva_plotly.png", width=900, height=550, scale=2)
    except Exception:
        print("[AVISO] No se pudo exportar el PNG de Plotly (falta Chrome).")
        print("        Ejecute 'plotly_get_chrome' o tome una captura del HTML.")


def plot_qq_by_sector(df):
    """Figura 6 (Matplotlib): graficos Q-Q por sector.

    El histograma de la Figura 1 sugiere normalidad; el Q-Q la audita en las
    colas, que es donde el histograma pierde resolucion y donde una desviacion
    comprometeria la validez de las pruebas parametricas.
    """
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.2))
    for ax, sector in zip(axes, SECTOR_ORDER):
        data = sector_series(df, sector)
        stat, p_value = stats.shapiro(data)
        stats.probplot(data, dist="norm", plot=ax)
        ax.get_lines()[0].set(marker="o", markersize=4,
                              markerfacecolor=SECTOR_COLORS[sector],
                              markeredgecolor="white", markeredgewidth=0.4,
                              linestyle="none")
        ax.get_lines()[1].set(color="red", linewidth=1.6)
        ax.set_xlabel("Cuantiles teóricos")
        ax.set_ylabel("Cuantiles observados")

    fig.suptitle("Diagnóstico gráfico de normalidad por sector (Q-Q plots)", fontsize=12, fontweight="bold")
    fig.tight_layout()
    fig.savefig(f"{FIGURES_DIR}/qqplots_normalidad.png", dpi=150)
    plt.close(fig)


def plot_tukey_forest(tukey_df, gh_df):
    """Figura 7 (Matplotlib): forest plot de Tukey frente a Games-Howell.

    Superponer ambos post-hoc convierte la limitacion por heterocedasticidad en
    una comprobacion visual: si los intervalos coinciden, la eleccion del
    procedimiento no altera la conclusion.
    """
    labels, tukey_diff, tukey_low, tukey_high = [], [], [], []
    for _, row in tukey_df.iterrows():
        labels.append(f"{row['group2']} - {row['group1']}")
        tukey_diff.append(float(row["meandiff"]))
        tukey_low.append(float(row["lower"]))
        tukey_high.append(float(row["upper"]))

    # Games-Howell nombra los pares en el orden de SECTOR_ORDER, asi que se
    # emparejan por conjunto de sectores y no por posicion en la tabla.
    gh_map = {frozenset(row["comparacion"].split(" - ")): row
              for _, row in gh_df.iterrows()}

    y = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(8.5, 4.6))

    for i, (label, diff, low, high) in enumerate(zip(labels, tukey_diff, tukey_low, tukey_high)):
        ax.errorbar(diff, y[i] + 0.10, xerr=[[diff - low], [high - diff]], fmt="o",
                    color="#1F4E79", capsize=5, markersize=7,
                    label="Tukey HSD" if i == 0 else None)
        gh_row = gh_map.get(frozenset(label.split(" - ")))
        if gh_row is not None:
            gh_diff = float(gh_row["diferencia"])
            gh_low = float(gh_row["ic_inferior"])
            gh_high = float(gh_row["ic_superior"])
            # El signo depende del orden en que cada procedimiento nombra el par
            if np.sign(gh_diff) != np.sign(diff):
                gh_diff, gh_low, gh_high = -gh_diff, -gh_high, -gh_low
            ax.errorbar(gh_diff, y[i] - 0.10,
                        xerr=[[gh_diff - gh_low], [gh_high - gh_diff]], fmt="s",
                        color="#C0504D", capsize=5, markersize=6,
                        label="Games-Howell" if i == 0 else None)

    ax.axvline(0, color="black", linestyle="--", linewidth=1.2)
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_ylim(-0.6, len(labels) - 0.4)
    ax.set_xlabel("Diferencia de medias (kWh/mes) con IC del 95 %")
    ax.set_title("Comparaciones múltiples: Tukey HSD frente a Games-Howell")
    # Las dos diferencias negativas ocupan la mitad izquierda y la positiva la
    # esquina inferior derecha, asi que leyenda y nota van a las zonas libres.
    ax.legend(loc="upper right", fontsize=9, framealpha=0.95)
    ax.text(0.02, 0.04,
            "Ningún intervalo cruza el cero: los tres sectores\n"
            "difieren entre sí y ambos post-hoc coinciden",
            transform=ax.transAxes, va="bottom", ha="left", fontsize=9, bbox=STAT_BOX)
    fig.tight_layout()
    fig.savefig(f"{FIGURES_DIR}/tukey_forest_forest.png", dpi=150)
    plt.close(fig)


def plot_attenuation(regression_df):
    """Figura 8 (Seaborn): por que la correlacion cae y la pendiente no.

    Tres paneles que descomponen la identidad r = b1 * s_T / s_Y: la pendiente
    se mantiene, la desviacion del consumo se dispara y la correlacion se
    desploma solo en el ambito agregado.
    """
    order = SECTOR_ORDER + ["Global"]
    data = regression_df.set_index("ambito").loc[order].reset_index()
    palette = {**SECTOR_COLORS, "Global": "#C0504D"}

    fig, axes = plt.subplots(1, 3, figsize=(12.5, 4.4))
    panels = [
        ("pendiente_b1", "Pendiente $b_1$ (kWh/°C)",
         "El efecto sobrevive a la agregación", 4.0),
        ("desv_consumo", "Desviación del consumo $s_Y$ (kWh)",
         "La dispersión se multiplica al mezclar", None),
        ("r_pearson", "Correlación $r$ de Pearson",
         "La asociación estandarizada se desploma", None),
    ]

    for ax, (column, ylabel, note, hline) in zip(axes, panels):
        sns.barplot(data=data, x="ambito", y=column, hue="ambito", order=order,
                    palette=palette, edgecolor="black", legend=False, ax=ax)
        if hline is not None:
            ax.axhline(hline, color="black", linestyle="--", linewidth=1.2)
            ax.text(0.97, 0.93, "Valor de diseño = 4", fontsize=8, ha="right",
                    transform=ax.transAxes)
        for container in ax.containers:
            ax.bar_label(container, fmt=lambda v: dec(v), fontsize=9, padding=2)
        ax.set_xlabel("")
        ax.set_ylabel(ylabel)
        ax.tick_params(axis="x", rotation=18)
        ax.margins(y=0.20)

    fig.suptitle("Descomposición de la atenuación por agregación: " "$r = b_1\\,s_T/s_Y$", fontsize=12, fontweight="bold")
    fig.tight_layout()
    fig.savefig(f"{FIGURES_DIR}/atenuacion.png", dpi=150)
    plt.close(fig)


def plot_dashboard_plotly(df, regression_df, anova_table):
    """Figura 9 (Plotly): dashboard INTERACTIVO de cuatro paneles.

    Reune en una sola vista las cuatro decisiones del protocolo, de modo que la
    contradiccion entre el panel de sectores y el de correlacion global quede
    a la vista sin recorrer el informe.
    """
    f_stat = anova_table.loc["C(sector)", "F"]
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            f"A · Distribución por sector (ANOVA: F = {dec(f_stat, 1)}; p < 0,001)",
            "B · Correlación temperatura-consumo por ámbito",
            "C · Dispersión global: la recta no describe a ningún sector",
            "D · Desviación estándar del consumo por ámbito",
        ),
        vertical_spacing=0.16, horizontal_spacing=0.11,
    )

    # Panel A: distribucion del consumo por sector
    for sector in SECTOR_ORDER:
        fig.add_trace(
            go.Box(y=sector_series(df, sector), name=sector,
                   marker_color=SECTOR_COLORS[sector], boxpoints="outliers",
                   legendgroup=sector, showlegend=True),
            row=1, col=1,
        )

    # Panel B: correlacion por ambito, coloreada segun la decision de la prueba
    scope = ["Global"] + SECTOR_ORDER
    data = regression_df.set_index("ambito")
    r_values = [float(data.loc[s, "r_pearson"]) for s in scope]
    p_values = [float(data.loc[s, "p_valor"]) for s in scope]
    colors = ["#C0504D" if p >= ALPHA else "#2E7D32" for p in p_values]
    fig.add_trace(
        go.Bar(x=scope, y=r_values, marker_color=colors, showlegend=False,
               text=[f"r = {r:.3f}".replace(".", ",") for r in r_values],
               textposition="outside",
               hovertemplate="%{x}<br>r = %{y:.3f}<extra></extra>"),
        row=1, col=2,
    )

    # Panel C: nube agregada con la recta global de minimos cuadrados
    for sector in SECTOR_ORDER:
        sub = df[df["sector"] == sector]
        fig.add_trace(
            go.Scatter(x=sub["temperatura_c"], y=sub["consumo_kwh"], mode="markers",
                       name=sector, marker=dict(color=SECTOR_COLORS[sector], size=5),
                       legendgroup=sector, showlegend=False,
                       customdata=sub[["id_cliente", "region"]],
                       hovertemplate="%{customdata[0]} · %{customdata[1]}<br>"
                                     "T = %{x} °C<br>Consumo = %{y} kWh<extra></extra>"),
            row=2, col=1,
        )
    slope = float(data.loc["Global", "pendiente_b1"])
    intercept = float(data.loc["Global", "intercepto_b0"])
    x_line = np.linspace(df["temperatura_c"].min(), df["temperatura_c"].max(), 50)
    fig.add_trace(
        go.Scatter(x=x_line, y=intercept + slope * x_line, mode="lines",
                   name="Recta global", line=dict(color="black", width=3, dash="dash"),
                   showlegend=False),
        row=2, col=1,
    )

    # Panel D: la desviacion del consumo, denominador de r = b1 * s_T / s_Y
    sd_values = [float(data.loc[s, "desv_consumo"]) for s in scope]
    fig.add_trace(
        go.Bar(x=scope, y=sd_values, showlegend=False,
               marker_color=["#C0504D"] + [SECTOR_COLORS[s] for s in SECTOR_ORDER],
               text=[f"{v:.1f}".replace(".", ",") for v in sd_values],
               textposition="outside",
               hovertemplate="%{x}<br>s_Y = %{y:.1f} kWh<extra></extra>"),
        row=2, col=2,
    )

    fig.update_yaxes(title_text="Consumo (kWh/mes)", row=1, col=1)
    fig.update_yaxes(title_text="r de Pearson", range=[0, 0.72], row=1, col=2)
    fig.update_xaxes(title_text="Temperatura (°C)", row=2, col=1)
    fig.update_yaxes(title_text="Consumo (kWh/mes)", row=2, col=1)
    fig.update_yaxes(title_text="Desviación s_Y (kWh)", row=2, col=2)
    fig.update_layout(
        template="plotly_white", height=790, title_font_size=15,
        margin=dict(b=110),
        title_text="Figura 9. Dashboard interactivo del protocolo de contraste "
                   "(rojo = no se rechaza H₀)",
        legend=dict(orientation="h", yanchor="top", y=-0.07, x=0.30),
    )
    for annotation in fig.layout.annotations:
        annotation.font.size = 11

    fig.write_html(f"{FIGURES_DIR}/dashboard_plotly.html")
    try:
        fig.write_image(f"{FIGURES_DIR}/dashboard_plotly.png",
                        width=1150, height=760, scale=2)
    except Exception:
        print("[AVISO] No se pudo exportar el PNG del dashboard (falta Chrome).")


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
    anova_table, tukey_df = run_anova_tukey(df)
    ols_model, regression_df = run_correlation_regression(df)

    # 2.5 / 2.6 Magnitud del efecto y robustez ante heterocedasticidad
    effects = run_effect_sizes(df, anova_table)
    welch_df, gh_df = run_robust_checks(df)

    # 3. Figuras
    plot_histogram_normality(df)
    plot_boxplot_anova(df, anova_table, effects["eta_sq"])
    plot_means_ci(df, tukey_df)
    plot_regression_seaborn(df, ols_model)
    plot_interactive_plotly(df)
    plot_qq_by_sector(df)
    plot_tukey_forest(tukey_df, gh_df)
    plot_attenuation(regression_df)
    plot_dashboard_plotly(df, regression_df, anova_table)
    print(f"[OK] 9 figuras guardadas en {FIGURES_DIR}")

    # 4. Resumen en consola de las cifras que alimentan el informe
    print("\n--- Resumen para el informe -------------------------------------")
    print(f"  d de Cohen (Res. vs Com.)  : {effects['cohen_d']:.4f} "
          f"[{effects['d_ci'][0]:.4f}; {effects['d_ci'][1]:.4f}]")
    print(f"  g de Hedges                : {effects['hedges_g']:.4f}")
    print(f"  eta^2 / omega^2 (ANOVA)    : {effects['eta_sq']:.4f} / {effects['omega_sq']:.4f}")
    print(f"  f de Cohen (ANOVA)         : {effects['cohen_f']:.4f}")
    print(f"  Potencia t / ANOVA         : {effects['power_t']:.4f} / {effects['power_anova']:.4f}")
    print(f"  r minimo detectable (n=300): {effects['r_detectable']:.4f}")
    print(f"  ANOVA de Welch             : F = {welch_df.iloc[0]['estadistico_f']:.4f}; "
          f"gl2 = {welch_df.iloc[0]['gl_denominador']:.2f}; "
          f"p = {welch_df.iloc[0]['p_valor']:.3e}")
    print("  Games-Howell:")
    for _, row in gh_df.iterrows():
        print(f"    {row['comparacion']:<26} dif = {row['diferencia']:>8.2f}  "
              f"IC [{row['ic_inferior']:.2f}; {row['ic_superior']:.2f}]  "
              f"p = {row['p_ajustado']:.3e}")


if __name__ == "__main__":
    main()
