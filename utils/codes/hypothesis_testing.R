# -----------------------------------------------------------------------------
# Actividad: Pruebas de Hipotesis y Visualizacion Avanzada (Unidad 2)
# Maestria en Inteligencia Artificial - Universidad de La Salle
#
# Este script REPLICA en R el analisis hecho en Python:
#   1. Lee el mismo dataset (data/dataset/consumo_energia.csv)
#   2. Aplica las pruebas de hipotesis con funciones base de R:
#      - shapiro.test (normalidad) y var.test / bartlett.test (varianzas)
#      - t.test (2 muestras independientes)
#      - aov (ANOVA de un factor) + TukeyHSD (post-hoc)
#      - cor.test (Pearson) + lm (regresion lineal)
#   3. Replica las 5 figuras usando ggplot2
#
# Ejecucion (desde la raiz del proyecto):
#   Rscript utils/codes/hypothesis_testing.R
# -----------------------------------------------------------------------------

library(ggplot2)

# --- Rutas del proyecto (relativas a la raiz) --------------------------------
dataset_path <- "data/dataset/consumo_energia.csv"
processed_dir <- "data/processed"
figures_dir <- "public/assets/images/figures/r/hypothesis"

dir.create(figures_dir, recursive = TRUE, showWarnings = FALSE)

# Nivel de significancia
alpha <- 0.05

# -----------------------------------------------------------------------------
# 1. LECTURA DEL DATASET (el mismo generado por Python, semilla 42)
# -----------------------------------------------------------------------------
df <- read.csv(dataset_path, encoding = "UTF-8")
df$sector <- as.factor(df$sector)
cat("[OK] Dataset leido:", nrow(df), "filas\n")

# -----------------------------------------------------------------------------
# 2. PRUEBAS DE HIPOTESIS (funciones base de R)
# -----------------------------------------------------------------------------

# --- 2.1 Normalidad con shapiro.test por sector ------------------------------
# H0: los datos provienen de una distribucion normal
normality_rows <- lapply(levels(df$sector), function(s) {
  test <- shapiro.test(df$consumo_kwh[df$sector == s])
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
residential <- df$consumo_kwh[df$sector == "Residencial"]
commercial <- df$consumo_kwh[df$sector == "Comercial"]
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
write.csv(as.data.frame(tukey$sector), file.path(processed_dir, "tukey_posthoc_r.csv"))
cat("[OK] ANOVA (aov) -> anova_results_r.csv | TukeyHSD -> tukey_posthoc_r.csv\n")

# --- 2.4 Correlacion (cor.test) y regresion lineal (lm) ----------------------
# H0: no hay relacion lineal entre temperatura y consumo (r = 0)
pearson <- cor.test(df$temperatura_c, df$consumo_kwh)
linear_model <- lm(consumo_kwh ~ temperatura_c, data = df)

regression_r <- data.frame(
  prueba = "Pearson (cor.test) + lm (R)",
  r_pearson = round(pearson$estimate, 4),
  p_valor = format(pearson$p.value, digits = 4),
  intercepto_b0 = round(coef(linear_model)[1], 2),
  pendiente_b1 = round(coef(linear_model)[2], 2),
  r_cuadrado = round(summary(linear_model)$r.squared, 4),
  decision = ifelse(pearson$p.value < alpha, "Relacion significativa", "Sin relacion significativa")
)
# Insight clave: la correlacion global se diluye porque los sectores tienen
# niveles de consumo muy distintos; por sector la relacion si aparece.
sector_rows <- lapply(levels(df$sector), function(s) {
  sub_df <- df[df$sector == s, ]
  test <- cor.test(sub_df$temperatura_c, sub_df$consumo_kwh)
  data.frame(
    prueba = paste0("Pearson (", s, ")"),
    r_pearson = round(test$estimate, 4),
    p_valor = format(test$p.value, digits = 4),
    intercepto_b0 = NA, pendiente_b1 = NA, r_cuadrado = NA,
    decision = ifelse(test$p.value < alpha, "Relacion significativa", "Sin relacion significativa")
  )
})
regression_r <- rbind(regression_r, do.call(rbind, sector_rows))

write.csv(regression_r, file.path(processed_dir, "regression_results_r.csv"), row.names = FALSE)
cat("[OK] Correlacion y regresion -> regression_results_r.csv\n")

# -----------------------------------------------------------------------------
# 3. FIGURAS CON GGPLOT2 (replican las de Python)
# -----------------------------------------------------------------------------

# --- Figura 1: histograma + curva normal (sector Residencial) ----------------
res_df <- df[df$sector == "Residencial", ]
p1 <- ggplot(res_df, aes(x = consumo_kwh)) +
  geom_histogram(aes(y = after_stat(density)), bins = 15, fill = "#4C72B0", color = "white", alpha = 0.85) +
  stat_function(fun = dnorm,
                args = list(mean = mean(res_df$consumo_kwh), sd = sd(res_df$consumo_kwh)),
                color = "red", linewidth = 1) +
  labs(title = "Figura 1R. Verificacion de normalidad - Sector Residencial (shapiro.test)",
       x = "Consumo (kWh/mes)", y = "Densidad") +
  theme_minimal()
ggsave(file.path(figures_dir, "fig1_histograma_normalidad.png"), p1, width = 8, height = 5, dpi = 150)

# --- Figura 2: boxplot del consumo por sector (ANOVA) ------------------------
p2 <- ggplot(df, aes(x = sector, y = consumo_kwh, fill = sector)) +
  geom_boxplot(alpha = 0.8) +
  geom_jitter(width = 0.15, size = 0.6, alpha = 0.3, color = "gray30") +
  scale_fill_brewer(palette = "Set2") +
  labs(title = "Figura 2R. Consumo de energia por sector (ANOVA de un factor)",
       x = "Sector", y = "Consumo (kWh/mes)") +
  theme_minimal() +
  theme(legend.position = "none")
ggsave(file.path(figures_dir, "fig2_boxplot_sectores.png"), p2, width = 8, height = 5, dpi = 150)

# --- Figura 3: medias con intervalos de confianza del 95% --------------------
# Calculo manual del IC 95% por sector (media +/- t * error estandar)
ci_list <- lapply(levels(df$sector), function(s) {
  values <- df$consumo_kwh[df$sector == s]
  se <- sd(values) / sqrt(length(values))
  margin <- qt(0.975, df = length(values) - 1) * se
  data.frame(sector = s, media = mean(values), inferior = mean(values) - margin, superior = mean(values) + margin)
})
ci_df <- do.call(rbind, ci_list)

p3 <- ggplot(ci_df, aes(x = sector, y = media, fill = sector)) +
  geom_col(color = "black", alpha = 0.9) +
  geom_errorbar(aes(ymin = inferior, ymax = superior), width = 0.2, linewidth = 0.8) +
  scale_fill_brewer(palette = "Set2") +
  labs(title = "Figura 3R. Consumo medio por sector con IC del 95% (t.test / aov)",
       x = "Sector", y = "Consumo medio (kWh/mes)") +
  theme_minimal() +
  theme(legend.position = "none")
ggsave(file.path(figures_dir, "fig3_medias_ic95.png"), p3, width = 8, height = 5, dpi = 150)

# --- Figura 4: dispersion + recta de regresion (Pearson / lm) ----------------
p4 <- ggplot(df, aes(x = temperatura_c, y = consumo_kwh)) +
  geom_point(alpha = 0.4, size = 1.5, color = "#4C72B0") +
  geom_smooth(method = "lm", color = "red", se = TRUE) +
  labs(title = "Figura 4R. Relacion temperatura vs consumo (cor.test y lm)",
       x = "Temperatura promedio (\u00B0C)", y = "Consumo (kWh/mes)") +
  theme_minimal()
ggsave(file.path(figures_dir, "fig4_regresion_temperatura.png"), p4, width = 8, height = 5, dpi = 150)

# --- Figura 5: dispersion por sector con rectas de regresion -----------------
# Version ggplot2 de la figura interactiva de Plotly. Si el paquete "plotly"
# esta instalado, tambien se guarda la version HTML interactiva.
p5 <- ggplot(df, aes(x = temperatura_c, y = consumo_kwh, color = sector)) +
  geom_point(alpha = 0.5, size = 1.5) +
  geom_smooth(method = "lm", se = FALSE) +
  scale_color_brewer(palette = "Set1") +
  labs(title = "Figura 5R. Consumo vs temperatura por sector (regresion por grupo)",
       x = "Temperatura promedio (\u00B0C)", y = "Consumo (kWh/mes)") +
  theme_minimal()
ggsave(file.path(figures_dir, "fig5_dispersion_sectores.png"), p5, width = 8, height = 5, dpi = 150)

# Version interactiva (opcional): requiere install.packages(c("plotly", "htmlwidgets"))
if (requireNamespace("plotly", quietly = TRUE) && requireNamespace("htmlwidgets", quietly = TRUE)) {
  interactive_fig <- plotly::ggplotly(p5)
  htmlwidgets::saveWidget(interactive_fig, file.path(figures_dir, "fig5_interactivo_r.html"))
  cat("[OK] Version interactiva -> fig5_interactivo_r.html\n")
} else {
  cat("[AVISO] Paquete 'plotly' no instalado en R; solo se genero el PNG de la figura 5.\n")
}

cat("[OK] 5 figuras de R guardadas en", figures_dir, "\n")
