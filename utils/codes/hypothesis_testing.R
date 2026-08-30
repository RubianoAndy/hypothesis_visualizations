# -----------------------------------------------------------------------------
# Actividad: Pruebas de Hipotesis y Visualizacion Avanzada (Unidad 2)
# Maestria en Inteligencia Artificial - Universidad de La Salle
#
# Este script REPLICA en R el analisis hecho en Python:
#   1. Lee el mismo dataset (data/dataset/consumo_energia.csv)
#   2. Aplica las pruebas de hipotesis con funciones base de R:
#      - shapiro.test (normalidad) y bartlett.test (varianzas)
#      - t.test con var.equal = FALSE (correccion de Welch)
#      - aov (ANOVA de un factor) + TukeyHSD (post-hoc)
#      - cor.test (Pearson) + lm (regresion lineal)
#   3. Recalcula la MAGNITUD del efecto y la potencia:
#      - d de Cohen, g de Hedges, eta cuadrado, omega cuadrado
#      - potencia observada por la distribucion no central
#   4. Repite el contraste sin asumir homocedasticidad:
#      - oneway.test (ANOVA de Welch) y post-hoc de Games-Howell
#   5. Replica las 9 figuras usando ggplot2, dos de ellas interactivas
#      mediante ggplotly (dispersion por sector y dashboard de 4 paneles)
#
# Ejecucion (desde cualquier directorio; las rutas se resuelven solas):
#   Rscript utils/codes/hypothesis_testing.R
# -----------------------------------------------------------------------------

library(ggplot2)
library(grid)  # paquete base: compone el dashboard 2x2 sin dependencias extra

# --- Rutas del proyecto (resueltas desde la ubicacion de este archivo) -------
#
# R no expone un equivalente de __file__: con rutas relativas manda getwd(),
# asi que una sesion de RStudio abierta sobre otro proyecto escribiria alli las
# figuras. script_path() recupera la ruta real del archivo en los tres modos de
# ejecucion: Rscript (argumento --file=), source() (variable ofile del marco que
# hace la llamada) y el boton Source/Run de RStudio (rstudioapi).
script_path <- function() {
  args <- commandArgs(trailingOnly = FALSE)
  file_arg <- grep("^--file=", args, value = TRUE)
  if (length(file_arg) > 0) {
    return(normalizePath(sub("^--file=", "", file_arg[1]), mustWork = FALSE))
  }
  for (i in seq_len(sys.nframe())) {
    ofile <- sys.frame(i)$ofile
    if (!is.null(ofile)) {
      return(normalizePath(ofile, mustWork = FALSE))
    }
  }
  if (requireNamespace("rstudioapi", quietly = TRUE) &&
      rstudioapi::isAvailable()) {
    contexto <- rstudioapi::getSourceEditorContext()
    if (!is.null(contexto) && nzchar(contexto$path)) {
      return(normalizePath(contexto$path, mustWork = FALSE))
    }
  }
  NULL
}

this_file <- script_path()
project_root <- if (is.null(this_file)) {
  normalizePath(getwd(), mustWork = FALSE)
} else {
  # utils/codes/hypothesis_testing.R -> utils/codes -> utils -> raiz
  dirname(dirname(dirname(this_file)))
}

dataset_path <- file.path(project_root, "data", "dataset",
                          "consumo_energia.csv")
processed_dir <- file.path(project_root, "data", "processed")
figures_dir <- file.path(project_root, "public", "assets", "images", "figures",
                         "r", "hypothesis")

# Verificar el dataset antes de crear nada: si la raiz deducida fuera la
# equivocada, el script se detiene en vez de sembrar carpetas y figuras en otro
# proyecto. Con showWarnings = FALSE eso ocurriria en silencio.
if (!file.exists(dataset_path)) {
  stop(sprintf(paste0("No se encontro el dataset en '%s'. Ejecuta antes el ",
                      "script de Python de este proyecto."),
               dataset_path))
}

dir.create(figures_dir, recursive = TRUE, showWarnings = FALSE)

cat(sprintf("Raiz del proyecto: %s\n", project_root))

# Nivel de significancia
alpha <- 0.05

# Orden y color de los sectores: se fijan una sola vez para que las nueve
# figuras de R usen la misma secuencia y la misma paleta que las de Python.
sector_order <- c("Residencial", "Comercial", "Industrial")
sector_colors <- c(Residencial = "#66C2A5", Comercial = "#FC8D62",
                   Industrial = "#8DA0CB")
scope_colors <- c(sector_colors, Global = "#C0504D")

# Coma decimal: la convencion tipografica que usa el informe en LaTeX
dec <- function(value, digits = 2) {
  formatC(value, format = "f", digits = digits, decimal.mark = ",")
}

format_p <- function(p_value) {
  if (p_value < 0.001) "p < 0,001" else paste0("p = ", dec(p_value, 3))
}

# Tema comun de las figuras estaticas
theme_informe <- theme_minimal(base_size = 11) +
  theme(plot.title = element_text(face = "bold", size = 11.5),
        plot.subtitle = element_text(size = 9, color = "gray30"))

# -----------------------------------------------------------------------------
# 1. LECTURA DEL DATASET (el mismo generado por Python, semilla 42)
# -----------------------------------------------------------------------------
df <- read.csv(dataset_path, encoding = "UTF-8")
df$sector <- factor(df$sector, levels = sector_order)
cat("[OK] Dataset leido:", nrow(df), "filas\n")

consumo <- function(s) df$consumo_kwh[df$sector == s]

# -----------------------------------------------------------------------------
# 2. PRUEBAS DE HIPOTESIS (funciones base de R)
# -----------------------------------------------------------------------------

# --- 2.1 Normalidad con shapiro.test por sector ------------------------------
# H0: los datos provienen de una distribucion normal
normality_rows <- lapply(sector_order, function(s) {
  test <- shapiro.test(consumo(s))
  data.frame(
    prueba = "Shapiro-Wilk (R)",
    grupo = s,
    estadistico = round(test$statistic, 4),
    p_valor = round(test$p.value, 4),
    decision = ifelse(test$p.value > alpha, "No se rechaza H0 (normal)", "Se rechaza H0 (no normal)")
  )
})
normality_r <- do.call(rbind, normality_rows)

# Homogeneidad de varianzas con bartlett.test (equivalente a Levene)
bartlett <- bartlett.test(consumo_kwh ~ sector, data = df)
normality_r <- rbind(normality_r, data.frame(
  prueba = "Bartlett (R)",
  grupo = "Los 3 sectores",
  estadistico = round(bartlett$statistic, 4),
  p_valor = round(bartlett$p.value, 4),
  decision = ifelse(bartlett$p.value > alpha, "Varianzas iguales", "Varianzas distintas")
))
write.csv(normality_r, file.path(processed_dir, "normality_tests_r.csv"), row.names = FALSE)
cat("[OK] Normalidad y Bartlett -> normality_tests_r.csv\n")

# --- 2.2 Prueba t con t.test -------------------------------------------------
# H0: consumo medio Residencial == consumo medio Comercial
residential <- consumo("Residencial")
commercial <- consumo("Comercial")
t_result <- t.test(residential, commercial, var.equal = FALSE)  # Welch

ttest_r <- data.frame(
  prueba = "t de Student - t.test (R)",
  media_residencial = round(mean(residential), 2),
  media_comercial = round(mean(commercial), 2),
  estadistico_t = round(t_result$statistic, 4),
  p_valor = format(t_result$p.value, digits = 4),
  decision = ifelse(t_result$p.value < alpha, "Se rechaza H0: las medias son diferentes", "No se rechaza H0")
)
write.csv(ttest_r, file.path(processed_dir, "ttest_results_r.csv"), row.names = FALSE)
cat("[OK] Prueba t -> ttest_results_r.csv\n")

# --- 2.3 ANOVA con aov + TukeyHSD --------------------------------------------
# H0: el consumo medio es igual en los 3 sectores
anova_model <- aov(consumo_kwh ~ sector, data = df)
anova_summary <- summary(anova_model)[[1]]
write.csv(anova_summary, file.path(processed_dir, "anova_results_r.csv"))

tukey <- TukeyHSD(anova_model)
tukey_df <- as.data.frame(tukey$sector)
tukey_df$comparacion <- rownames(tukey_df)
write.csv(tukey_df, file.path(processed_dir, "tukey_posthoc_r.csv"), row.names = FALSE)
cat("[OK] ANOVA (aov) -> anova_results_r.csv | TukeyHSD -> tukey_posthoc_r.csv\n")

f_anova <- anova_summary[["F value"]][1]
p_anova <- anova_summary[["Pr(>F)"]][1]

# --- 2.4 Correlacion (cor.test) y regresion lineal (lm) ----------------------
# H0: no hay relacion lineal entre temperatura y consumo (r = 0)
pearson <- cor.test(df$temperatura_c, df$consumo_kwh)
linear_model <- lm(consumo_kwh ~ temperatura_c, data = df)

regression_r <- data.frame(
  ambito = "Global",
  prueba = "Pearson (cor.test) + lm (R)",
  n = nrow(df),
  r_pearson = round(unname(pearson$estimate), 4),
  p_valor = round(pearson$p.value, 6),
  intercepto_b0 = round(unname(coef(linear_model)[1]), 2),
  pendiente_b1 = round(unname(coef(linear_model)[2]), 2),
  desv_consumo = round(sd(df$consumo_kwh), 2),
  r_cuadrado = round(summary(linear_model)$r.squared, 4),
  decision = ifelse(pearson$p.value < alpha, "Relacion significativa", "Sin relacion significativa")
)
# Insight clave: la correlacion global se diluye porque los sectores tienen
# niveles de consumo muy distintos; por sector la relacion si aparece.
sector_rows <- lapply(sector_order, function(s) {
  sub_df <- df[df$sector == s, ]
  test <- cor.test(sub_df$temperatura_c, sub_df$consumo_kwh)
  model_s <- lm(consumo_kwh ~ temperatura_c, data = sub_df)
  data.frame(
    ambito = s,
    prueba = paste0("Pearson (", s, ")"),
    n = nrow(sub_df),
    r_pearson = round(unname(test$estimate), 4),
    p_valor = round(test$p.value, 6),
    intercepto_b0 = round(unname(coef(model_s)[1]), 2),
    pendiente_b1 = round(unname(coef(model_s)[2]), 2),
    desv_consumo = round(sd(sub_df$consumo_kwh), 2),
    r_cuadrado = round(summary(model_s)$r.squared, 4),
    decision = ifelse(test$p.value < alpha, "Relacion significativa", "Sin relacion significativa")
  )
})
regression_r <- rbind(regression_r, do.call(rbind, sector_rows))

write.csv(regression_r, file.path(processed_dir, "regression_results_r.csv"), row.names = FALSE)
cat("[OK] Correlacion y regresion -> regression_results_r.csv\n")

# -----------------------------------------------------------------------------
# 2.5 TAMANO DEL EFECTO Y POTENCIA
#
# Un valor p responde "es distinguible del azar?", no "importa?". Estas medidas
# se calculan aqui de cero con las formulas cerradas, sin paquetes externos, y
# deben coincidir con las que produce statsmodels en Python.
# -----------------------------------------------------------------------------
n1 <- length(residential); n2 <- length(commercial)
s1 <- sd(residential); s2 <- sd(commercial)

# d de Cohen con desviacion combinada (pooled)
pooled_sd <- sqrt(((n1 - 1) * s1^2 + (n2 - 1) * s2^2) / (n1 + n2 - 2))
cohen_d <- (mean(commercial) - mean(residential)) / pooled_sd
# g de Hedges: d corregida por el sesgo al alza en muestras pequenas
hedges_g <- cohen_d * (1 - 3 / (4 * (n1 + n2) - 9))
# IC del 95 % de d por la aproximacion normal del error estandar
se_d <- sqrt((n1 + n2) / (n1 * n2) + cohen_d^2 / (2 * (n1 + n2)))
d_ci <- cohen_d + c(-1, 1) * qnorm(1 - alpha / 2) * se_d

ss_between <- anova_summary[["Sum Sq"]][1]
ss_within <- anova_summary[["Sum Sq"]][2]
df_between <- anova_summary[["Df"]][1]
df_within <- anova_summary[["Df"]][2]
ss_total <- ss_between + ss_within
ms_within <- ss_within / df_within

eta_sq <- ss_between / ss_total
# omega cuadrado penaliza el sesgo optimista de eta cuadrado
omega_sq <- (ss_between - df_between * ms_within) / (ss_total + ms_within)
cohen_f <- sqrt(eta_sq / (1 - eta_sq))

# Potencia observada por la distribucion no central, la misma definicion que
# usa statsmodels: asi la comparacion Python-R es exacta y no aproximada.
ncp_t <- abs(cohen_d) * sqrt(n1 * n2 / (n1 + n2))
df_t <- n1 + n2 - 2
crit_t <- qt(1 - alpha / 2, df_t)
power_t <- pt(crit_t, df_t, ncp = ncp_t, lower.tail = FALSE) +
  pt(-crit_t, df_t, ncp = ncp_t, lower.tail = TRUE)

ncp_f <- nrow(df) * cohen_f^2
power_anova <- pf(qf(1 - alpha, df_between, df_within), df_between, df_within,
                  ncp = ncp_f, lower.tail = FALSE)

# Sensibilidad sobre la correlacion global: con n = 300, cual es la correlacion
# mas pequena detectable con potencia del 80 %? Si el r observado queda por
# debajo, la no significancia es cuestion de magnitud, no de tamano muestral.
r_detectable <- tanh((qnorm(1 - alpha / 2) + qnorm(0.80)) / sqrt(nrow(df) - 3))

effects_r <- data.frame(
  medida = c("d de Cohen (Res. vs Com.)", "g de Hedges (Res. vs Com.)",
             "eta cuadrado (ANOVA sector)", "omega cuadrado (ANOVA sector)",
             "f de Cohen (ANOVA sector)", "Potencia observada (t de Welch)",
             "Potencia observada (ANOVA)",
             "r minimo detectable (n = 300, potencia 0,80)"),
  valor = round(c(cohen_d, hedges_g, eta_sq, omega_sq, cohen_f,
                  power_t, power_anova, r_detectable), 4),
  ic_inferior = c(round(d_ci[1], 4), rep(NA, 7)),
  ic_superior = c(round(d_ci[2], 4), rep(NA, 7))
)
write.csv(effects_r, file.path(processed_dir, "effect_sizes_r.csv"), row.names = FALSE)
cat("[OK] Tamanos de efecto y potencia -> effect_sizes_r.csv\n")

# -----------------------------------------------------------------------------
# 2.6 ROBUSTEZ ANTE HETEROCEDASTICIDAD
#
# Bartlett rechaza la igualdad de varianzas, y tanto aov como TukeyHSD la
# asumen. Se repite el contraste con las versiones que no lo exigen: si la
# decision no cambia, la conclusion queda respaldada.
# -----------------------------------------------------------------------------
welch <- oneway.test(consumo_kwh ~ sector, data = df, var.equal = FALSE)
welch_r <- data.frame(
  prueba = "ANOVA de Welch (oneway.test)",
  estadistico_f = round(unname(welch$statistic), 4),
  gl_numerador = round(unname(welch$parameter[1]), 2),
  gl_denominador = round(unname(welch$parameter[2]), 2),
  p_valor = format(welch$p.value, digits = 4),
  decision = ifelse(welch$p.value < alpha, "Se rechaza H0", "No se rechaza H0")
)
write.csv(welch_r, file.path(processed_dir, "welch_anova_r.csv"), row.names = FALSE)

# Games-Howell: error estandar de Welch por par y grados de libertad de
# Welch-Satterthwaite, contrastados contra el rango estudentizado (ptukey).
games_howell <- function(data) {
  k <- length(sector_order)
  pairs <- combn(sector_order, 2, simplify = FALSE)
  rows <- lapply(pairs, function(pair) {
    ga <- data$consumo_kwh[data$sector == pair[1]]
    gb <- data$consumo_kwh[data$sector == pair[2]]
    na <- length(ga); nb <- length(gb)
    va <- var(ga); vb <- var(gb)
    diff <- mean(gb) - mean(ga)

    se <- sqrt(va / na + vb / nb)
    df_wl <- (va / na + vb / nb)^2 /
      ((va / na)^2 / (na - 1) + (vb / nb)^2 / (nb - 1))
    q_stat <- abs(diff) / se * sqrt(2)
    p_adj <- ptukey(q_stat, nmeans = k, df = df_wl, lower.tail = FALSE)
    margin <- qtukey(1 - alpha, nmeans = k, df = df_wl) / sqrt(2) * se

    data.frame(
      comparacion = paste(pair[2], "-", pair[1]),
      diferencia = round(diff, 3),
      ic_inferior = round(diff - margin, 3),
      ic_superior = round(diff + margin, 3),
      q = round(q_stat, 3),
      gl_welch = round(df_wl, 2),
      p_ajustado = signif(p_adj, 4),
      decision = ifelse(p_adj < alpha, "Se rechaza H0", "No se rechaza H0")
    )
  })
  do.call(rbind, rows)
}
gh_r <- games_howell(df)
write.csv(gh_r, file.path(processed_dir, "games_howell_r.csv"), row.names = FALSE)
cat("[OK] ANOVA de Welch -> welch_anova_r.csv | Games-Howell -> games_howell_r.csv\n")

# -----------------------------------------------------------------------------
# 3. FIGURAS CON GGPLOT2 (replican las nueve de Python)
# -----------------------------------------------------------------------------

# --- Figura 1R: histograma + curva normal (sector Residencial) ---------------
shapiro_res <- shapiro.test(residential)
p1 <- ggplot(data.frame(consumo_kwh = residential), aes(x = consumo_kwh)) +
  geom_histogram(aes(y = after_stat(density)), bins = 15, fill = "#4C72B0",
                 color = "white", alpha = 0.85) +
  stat_function(fun = dnorm,
                args = list(mean = mean(residential), sd = sd(residential)),
                color = "red", linewidth = 1) +
  annotate("label", x = -Inf, y = Inf, hjust = -0.05, vjust = 1.15, size = 3.1,
           label = paste0("Shapiro-Wilk: W = ", dec(shapiro_res$statistic, 4),
                          "\n", format_p(shapiro_res$p.value),
                          "\nNo se rechaza H0")) +
  labs(title = "Figura 1R. Verificación de normalidad — Sector Residencial (shapiro.test)",
       x = "Consumo (kWh/mes)", y = "Densidad") +
  theme_informe
ggsave(file.path(figures_dir, "fig1_histograma_normalidad.png"), p1,
       width = 8, height = 5, dpi = 150)

# --- Figura 2R: violin + boxplot del consumo por sector (ANOVA) --------------
# El violin anade lo que la caja oculta: la forma de cada distribucion, donde
# se ve que la dispersion crece con el nivel del sector.
p2 <- ggplot(df, aes(x = sector, y = consumo_kwh, fill = sector)) +
  geom_violin(alpha = 0.28, color = NA, trim = TRUE) +
  geom_boxplot(width = 0.32, alpha = 0.9, outlier.shape = NA) +
  geom_jitter(width = 0.12, size = 0.6, alpha = 0.3, color = "gray30") +
  scale_fill_manual(values = sector_colors) +
  annotate("label", x = -Inf, y = Inf, hjust = -0.05, vjust = 1.15, size = 3.1,
           label = paste0("ANOVA: F(2, 297) = ", dec(f_anova),
                          "\n", format_p(p_anova),
                          "\neta^2 = ", dec(eta_sq, 3), " (efecto grande)")) +
  labs(title = "Figura 2R. Consumo de energía por sector (ANOVA de un factor)",
       x = "Sector", y = "Consumo (kWh/mes)") +
  theme_informe + theme(legend.position = "none")
ggsave(file.path(figures_dir, "fig2_boxplot_sectores.png"), p2,
       width = 8, height = 5, dpi = 150)

# --- Figura 3R: medias con IC del 95 % y letras de Tukey ---------------------
# Calculo manual del IC 95% por sector (media +/- t * error estandar)
ci_list <- lapply(sector_order, function(s) {
  values <- consumo(s)
  margin <- qt(0.975, df = length(values) - 1) * sd(values) / sqrt(length(values))
  data.frame(sector = s, media = mean(values),
             inferior = mean(values) - margin, superior = mean(values) + margin)
})
ci_df <- do.call(rbind, ci_list)
ci_df$sector <- factor(ci_df$sector, levels = sector_order)

# Letras de significancia: dos sectores comparten letra si Tukey no los separa.
# Es la traduccion grafica del post-hoc, legible sin consultar la tabla.
compact_letters <- function(tukey_table) {
  significant <- rownames(tukey_table)[tukey_table[, "p adj"] < alpha]
  significant <- lapply(strsplit(significant, "-"), sort)
  letters_map <- character(0)
  for (s in sector_order) {
    for (letter in letters) {
      holders <- names(letters_map)[grepl(letter, letters_map, fixed = TRUE)]
      collides <- any(vapply(holders, function(other) {
        any(vapply(significant, function(pair) identical(pair, sort(c(s, other))),
                   logical(1)))
      }, logical(1)))
      if (!collides) {
        letters_map[s] <- paste0(ifelse(is.na(letters_map[s]), "", letters_map[s]), letter)
        break
      }
    }
  }
  letters_map
}
cld <- compact_letters(tukey$sector)
ci_df$etiqueta <- paste0(dec(ci_df$media, 1), "\n(", cld[as.character(ci_df$sector)], ")")

p3 <- ggplot(ci_df, aes(x = sector, y = media, fill = sector)) +
  geom_col(color = "black", alpha = 0.9) +
  geom_errorbar(aes(ymin = inferior, ymax = superior), width = 0.2, linewidth = 0.8) +
  geom_text(aes(y = superior, label = etiqueta), vjust = -0.25,
            fontface = "bold", size = 3.3, lineheight = 0.95) +
  scale_fill_manual(values = sector_colors) +
  scale_y_continuous(expand = expansion(mult = c(0, 0.16))) +
  annotate("label", x = -Inf, y = Inf, hjust = -0.05, vjust = 1.15, size = 3.1,
           label = "Letras distintas indican\ndiferencia significativa\n(Tukey HSD, alfa = 0,05)") +
  labs(title = "Figura 3R. Consumo medio por sector con IC del 95 % (t.test / aov)",
       x = "Sector", y = "Consumo medio (kWh/mes)") +
  theme_informe + theme(legend.position = "none")
ggsave(file.path(figures_dir, "fig3_medias_ic95.png"), p3,
       width = 8, height = 5, dpi = 150)

# --- Figura 4R: dispersion global + recta de regresion (Pearson / lm) --------
p4 <- ggplot(df, aes(x = temperatura_c, y = consumo_kwh)) +
  geom_point(alpha = 0.4, size = 1.5, color = "#4C72B0") +
  geom_smooth(method = "lm", formula = y ~ x, color = "red", se = TRUE) +
  annotate("label", x = -Inf, y = Inf, hjust = -0.05, vjust = 1.15, size = 3.1,
           label = paste0("Pearson: r = ", dec(pearson$estimate, 3), "; ",
                          format_p(pearson$p.value),
                          "\nY = ", dec(coef(linear_model)[1]), " + ",
                          dec(coef(linear_model)[2]), "·T",
                          "\nR^2 = ", dec(summary(linear_model)$r.squared, 4),
                          " — No se rechaza H0")) +
  labs(title = "Figura 4R. Relación temperatura vs. consumo (cor.test y lm)",
       x = "Temperatura promedio (°C)", y = "Consumo (kWh/mes)") +
  theme_informe
ggsave(file.path(figures_dir, "fig4_regresion_temperatura.png"), p4,
       width = 8, height = 5, dpi = 150)

# --- Figura 5R: dispersion por sector con una recta por grupo ----------------
p5 <- ggplot(df, aes(x = temperatura_c, y = consumo_kwh, color = sector)) +
  geom_point(alpha = 0.55, size = 1.5) +
  geom_smooth(method = "lm", formula = y ~ x, se = FALSE, linewidth = 1) +
  scale_color_manual(values = sector_colors) +
  labs(title = "Figura 5R. Consumo vs. temperatura por sector (regresión por grupo)",
       x = "Temperatura promedio (°C)", y = "Consumo (kWh/mes)",
       color = "Sector") +
  theme_informe
ggsave(file.path(figures_dir, "fig5_dispersion_sectores.png"), p5,
       width = 8, height = 5, dpi = 150)

# --- Figura 6R: Q-Q plots por sector -----------------------------------------
# El histograma de la Figura 1R sugiere normalidad; el Q-Q la audita en las
# colas, que es donde el histograma pierde resolucion.
qq_labels <- vapply(sector_order, function(s) {
  test <- shapiro.test(consumo(s))
  paste0(s, "\nW = ", dec(test$statistic, 4), "; ", format_p(test$p.value))
}, character(1))
qq_df <- df
qq_df$panel <- factor(qq_labels[as.character(df$sector)], levels = qq_labels)

p6 <- ggplot(qq_df, aes(sample = consumo_kwh, color = sector)) +
  stat_qq(size = 1.1, alpha = 0.8) +
  stat_qq_line(color = "red", linewidth = 0.7) +
  facet_wrap(~panel, scales = "free_y") +
  scale_color_manual(values = sector_colors) +
  labs(title = "Figura 6R. Diagnóstico gráfico de normalidad por sector (Q-Q plots)",
       x = "Cuantiles teóricos", y = "Cuantiles observados") +
  theme_informe + theme(legend.position = "none")
ggsave(file.path(figures_dir, "fig6_qqplots_normalidad.png"), p6,
       width = 10, height = 4.2, dpi = 150)

# --- Figura 7R: forest plot de Tukey frente a Games-Howell -------------------
# Superponer ambos post-hoc convierte la limitacion por heterocedasticidad en
# una comprobacion visual: si los intervalos coinciden, la eleccion del
# procedimiento no altera la conclusion.
tukey_plot <- data.frame(
  comparacion = rownames(tukey$sector),
  diferencia = tukey$sector[, "diff"],
  inferior = tukey$sector[, "lwr"],
  superior = tukey$sector[, "upr"],
  metodo = "Tukey HSD",
  row.names = NULL
)
# Games-Howell nombra los pares en el orden de sector_order; se reorientan al
# mismo sentido que TukeyHSD antes de superponerlos.
gh_plot <- do.call(rbind, lapply(seq_len(nrow(tukey_plot)), function(i) {
  target <- sort(strsplit(tukey_plot$comparacion[i], "-")[[1]])
  match_row <- which(vapply(gh_r$comparacion, function(cmp) {
    identical(sort(trimws(strsplit(cmp, " - ")[[1]])), target)
  }, logical(1)))
  row <- gh_r[match_row, ]
  flip <- sign(row$diferencia) != sign(tukey_plot$diferencia[i])
  data.frame(
    comparacion = tukey_plot$comparacion[i],
    diferencia = if (flip) -row$diferencia else row$diferencia,
    inferior = if (flip) -row$ic_superior else row$ic_inferior,
    superior = if (flip) -row$ic_inferior else row$ic_superior,
    metodo = "Games-Howell"
  )
}))
forest_df <- rbind(tukey_plot, gh_plot)
forest_df$metodo <- factor(forest_df$metodo, levels = c("Tukey HSD", "Games-Howell"))

p7 <- ggplot(forest_df, aes(x = diferencia, y = comparacion, color = metodo)) +
  geom_vline(xintercept = 0, linetype = "dashed", linewidth = 0.7) +
  geom_pointrange(aes(xmin = inferior, xmax = superior, shape = metodo),
                  position = position_dodge(width = 0.55), linewidth = 0.7) +
  scale_color_manual(values = c("Tukey HSD" = "#1F4E79",
                                "Games-Howell" = "#C0504D")) +
  labs(title = "Figura 7R. Comparaciones múltiples: Tukey HSD frente a Games-Howell",
       subtitle = "Ningún intervalo cruza el cero: los tres sectores difieren y ambos post-hoc coinciden",
       x = "Diferencia de medias (kWh/mes) con IC del 95 %", y = NULL,
       color = "Método", shape = "Método") +
  theme_informe + theme(legend.position = "bottom")
ggsave(file.path(figures_dir, "fig7_tukey_forest.png"), p7,
       width = 8.5, height = 4.6, dpi = 150)

# --- Figura 8R: descomposicion de la atenuacion por agregacion ---------------
# Tres paneles que descomponen la identidad r = b1 * s_T / s_Y: la pendiente se
# mantiene, la desviacion del consumo se dispara y la correlacion se desploma
# solo en el ambito agregado.
panel_levels <- c("Pendiente b1 (kWh/°C)", "Desviación s_Y (kWh)",
                  "Correlación r de Pearson")
atenuacion <- rbind(
  data.frame(ambito = regression_r$ambito, valor = regression_r$pendiente_b1,
             panel = panel_levels[1]),
  data.frame(ambito = regression_r$ambito, valor = regression_r$desv_consumo,
             panel = panel_levels[2]),
  data.frame(ambito = regression_r$ambito, valor = regression_r$r_pearson,
             panel = panel_levels[3])
)
atenuacion$ambito <- factor(atenuacion$ambito, levels = c(sector_order, "Global"))
atenuacion$panel <- factor(atenuacion$panel, levels = panel_levels)
linea_diseno <- data.frame(panel = factor(panel_levels[1], levels = panel_levels),
                           y = 4)

p8 <- ggplot(atenuacion, aes(x = ambito, y = valor, fill = ambito)) +
  geom_col(color = "black", alpha = 0.92) +
  geom_hline(data = linea_diseno, aes(yintercept = y), linetype = "dashed") +
  geom_text(aes(label = dec(valor)), vjust = -0.4, size = 3) +
  facet_wrap(~panel, scales = "free_y") +
  scale_fill_manual(values = scope_colors) +
  scale_y_continuous(expand = expansion(mult = c(0, 0.18))) +
  labs(title = "Figura 8R. Descomposición de la atenuación por agregación: r = b1·s_T/s_Y",
       subtitle = "La pendiente sobrevive a la agregación (línea = valor de diseño 4); la correlación no",
       x = NULL, y = NULL) +
  theme_informe +
  theme(legend.position = "none", axis.text.x = element_text(angle = 18, hjust = 1))
ggsave(file.path(figures_dir, "fig8_atenuacion.png"), p8,
       width = 10.5, height = 4.4, dpi = 150)

# --- Figura 9R: dashboard de cuatro paneles ---------------------------------
# Reune las cuatro decisiones del protocolo en una sola vista, de modo que la
# contradiccion entre el panel de sectores y el de correlacion global quede a
# la vista sin recorrer el informe.
d_a <- ggplot(df, aes(x = sector, y = consumo_kwh, fill = sector)) +
  geom_boxplot(alpha = 0.9) +
  scale_fill_manual(values = sector_colors) +
  labs(title = paste0("A · Distribución por sector (ANOVA: F = ", dec(f_anova, 1),
                      "; p < 0,001)"),
       x = NULL, y = "Consumo (kWh/mes)") +
  theme_informe + theme(legend.position = "none")

corr_df <- data.frame(
  ambito = factor(c("Global", sector_order), levels = c("Global", sector_order)),
  r = c(regression_r$r_pearson[match(c("Global", sector_order), regression_r$ambito)]),
  p = c(regression_r$p_valor[match(c("Global", sector_order), regression_r$ambito)])
)
corr_df$decision <- ifelse(corr_df$p < alpha, "Se rechaza H0", "No se rechaza H0")

d_b <- ggplot(corr_df, aes(x = ambito, y = r, fill = decision)) +
  geom_col(color = "black", alpha = 0.92) +
  geom_text(aes(label = paste0("r = ", dec(r, 3))), vjust = -0.4, size = 3) +
  scale_fill_manual(values = c("Se rechaza H0" = "#2E7D32",
                               "No se rechaza H0" = "#C0504D")) +
  scale_y_continuous(expand = expansion(mult = c(0, 0.18))) +
  labs(title = "B · Correlación temperatura-consumo por ámbito",
       x = NULL, y = "r de Pearson", fill = NULL) +
  theme_informe + theme(legend.position = "bottom")

d_c <- ggplot(df, aes(x = temperatura_c, y = consumo_kwh, color = sector)) +
  geom_point(alpha = 0.55, size = 1.2) +
  geom_abline(intercept = coef(linear_model)[1], slope = coef(linear_model)[2],
              linetype = "dashed", linewidth = 1, color = "black") +
  scale_color_manual(values = sector_colors) +
  labs(title = "C · Dispersión global: la recta no describe a ningún sector",
       x = "Temperatura (°C)", y = "Consumo (kWh/mes)", color = NULL) +
  theme_informe + theme(legend.position = "bottom")

sd_df <- data.frame(
  ambito = factor(c("Global", sector_order), levels = c("Global", sector_order)),
  s_y = regression_r$desv_consumo[match(c("Global", sector_order), regression_r$ambito)]
)
d_d <- ggplot(sd_df, aes(x = ambito, y = s_y, fill = ambito)) +
  geom_col(color = "black", alpha = 0.92) +
  geom_text(aes(label = dec(s_y, 1)), vjust = -0.4, size = 3) +
  scale_fill_manual(values = scope_colors) +
  scale_y_continuous(expand = expansion(mult = c(0, 0.18))) +
  labs(title = "D · Desviación estándar del consumo por ámbito",
       x = NULL, y = "Desviación s_Y (kWh)") +
  theme_informe + theme(legend.position = "none")

# grid (paquete base) compone la retícula 2x2 sin necesidad de patchwork
png(file.path(figures_dir, "fig9_dashboard.png"), width = 1150, height = 790,
    res = 110)
grid.newpage()
pushViewport(viewport(layout = grid.layout(2, 2)))
print(d_a, vp = viewport(layout.pos.row = 1, layout.pos.col = 1))
print(d_b, vp = viewport(layout.pos.row = 1, layout.pos.col = 2))
print(d_c, vp = viewport(layout.pos.row = 2, layout.pos.col = 1))
print(d_d, vp = viewport(layout.pos.row = 2, layout.pos.col = 2))
invisible(dev.off())

# --- Versiones interactivas (ggplotly) --------------------------------------
#
# saveWidget() genera por defecto un HTML autocontenido, pero para empotrar las
# librerias JS necesita pandoc, que Rscript no siempre encuentra. Si no esta
# disponible se guarda la version con carpeta "_files" adjunta, que es igual de
# interactiva; en ningun caso se interrumpe la ejecucion del script.
save_widget <- function(widget, path) {
  tryCatch({
    htmlwidgets::saveWidget(widget, path, selfcontained = TRUE)
    "autocontenido"
  }, error = function(e) {
    htmlwidgets::saveWidget(widget, path, selfcontained = FALSE)
    "con carpeta _files (pandoc no disponible)"
  })
}

if (requireNamespace("plotly", quietly = TRUE) &&
    requireNamespace("htmlwidgets", quietly = TRUE)) {
  # Figura 5R interactiva: la contraparte en RStudio de la Figura 5 de Plotly
  fig5_int <- plotly::ggplotly(p5, tooltip = c("x", "y", "colour"))
  estado5 <- save_widget(fig5_int, file.path(figures_dir, "fig5_interactivo_r.html"))
  cat("[OK] Figura 5R interactiva -> fig5_interactivo_r.html -", estado5, "\n")

  # Dashboard interactivo: los mismos cuatro paneles unidos con subplot
  fig9_int <- plotly::subplot(
    plotly::ggplotly(d_a), plotly::ggplotly(d_b),
    plotly::ggplotly(d_c), plotly::ggplotly(d_d),
    nrows = 2, margin = 0.07, titleX = TRUE, titleY = TRUE
  )
  fig9_int <- plotly::layout(
    fig9_int, showlegend = FALSE,
    title = list(text = "Figura 9R. Dashboard interactivo del protocolo de contraste (ggplot2 + plotly)",
                 font = list(size = 14))
  )
  estado9 <- save_widget(fig9_int, file.path(figures_dir, "fig9_dashboard_r.html"))
  cat("[OK] Dashboard interactivo -> fig9_dashboard_r.html -", estado9, "\n")
} else {
  cat("[AVISO] Paquete 'plotly' no instalado en R; solo se generaron los PNG.\n")
}

cat("[OK] 9 figuras de R guardadas en", figures_dir, "\n")

# -----------------------------------------------------------------------------
# 4. RESUMEN EN CONSOLA: las cifras que deben coincidir con las de Python
# -----------------------------------------------------------------------------
cat("\n--- Verificacion cruzada con Python -----------------------------\n")
cat(sprintf("  Shapiro-Wilk (Res.)        : W = %.4f; p = %.4f\n",
            shapiro_res$statistic, shapiro_res$p.value))
cat(sprintf("  t de Welch                 : t = %.4f; p = %.3e\n",
            t_result$statistic, t_result$p.value))
cat(sprintf("  ANOVA                      : F = %.4f; p = %.3e\n", f_anova, p_anova))
cat(sprintf("  d de Cohen (Res. vs Com.)  : %.4f [%.4f; %.4f]\n",
            cohen_d, d_ci[1], d_ci[2]))
cat(sprintf("  g de Hedges                : %.4f\n", hedges_g))
cat(sprintf("  eta^2 / omega^2            : %.4f / %.4f\n", eta_sq, omega_sq))
cat(sprintf("  f de Cohen                 : %.4f\n", cohen_f))
cat(sprintf("  Potencia t / ANOVA         : %.4f / %.4f\n", power_t, power_anova))
cat(sprintf("  r minimo detectable (n=300): %.4f\n", r_detectable))
cat(sprintf("  ANOVA de Welch             : F = %.4f; gl2 = %.2f; p = %.3e\n",
            welch$statistic, welch$parameter[2], welch$p.value))
cat("  Games-Howell:\n")
for (i in seq_len(nrow(gh_r))) {
  cat(sprintf("    %-26s dif = %8.2f  IC [%.2f; %.2f]  p = %.3e\n",
              gh_r$comparacion[i], gh_r$diferencia[i], gh_r$ic_inferior[i],
              gh_r$ic_superior[i], gh_r$p_ajustado[i]))
}
