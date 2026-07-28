# R Script: Academic Paper-Grade Statistical Visualization for Recommender Benchmark
# Recommendation Traveller Lampung

suppressPackageStartupMessages({
  if (!require("ggplot2")) install.packages("ggplot2", repos="http://cran.rstudio.com/")
  if (!require("gridExtra")) install.packages("gridExtra", repos="http://cran.rstudio.com/")
  library(ggplot2)
  library(gridExtra)
})

# Path definitions
input_csv <- "reports/benchmark_recommender_results.csv"
output_dir <- "reports/figures"

if (!dir.exists(output_dir)) {
  dir.create(output_dir, recursive = TRUE)
}

if (!file.exists(input_csv)) {
  stop(paste("Input CSV not found:", input_csv))
}

df <- read.csv(input_csv, stringsAsFactors = FALSE)

# Clean algorithm names for plot legibility
df$algorithm_clean <- gsub("Candidate ", "C", gsub("Baseline ", "B", df$algorithm))

# Color palette: Academic publication palette (Slate/Teal/Navy/Emerald)
paper_colors <- c("#2b5c8f", "#3690c0", "#67a9cf", "#02818a")

# 1. Plot 1: Precision@10 & nDCG@10 Comparison Bar Plot
p1 <- ggplot(df, aes(x = algorithm_clean, y = precision_at_10, fill = algorithm_clean)) +
  geom_bar(stat = "identity", width = 0.55, color = "#111111", size = 0.4) +
  geom_text(aes(label = sprintf("%.3f", precision_at_10)), vjust = -0.4, size = 3.5, fontface = "bold") +
  scale_fill_manual(values = paper_colors) +
  scale_y_continuous(limits = c(0, 1.1), breaks = seq(0, 1.0, 0.2)) +
  theme_minimal(base_family = "sans") +
  labs(
    title = "Algorithm Performance Comparison (Precision@10)",
    subtitle = "Evaluation across 15 Synthetic Tourist Personas in Lampung",
    x = "Algorithm Candidate",
    y = "Mean Precision@10 Score"
  ) +
  theme(
    legend.position = "none",
    plot.title = element_text(face = "bold", size = 12, hjust = 0.5),
    plot.subtitle = element_text(size = 9, hjust = 0.5, color = "#555555"),
    axis.title = element_text(face = "bold", size = 10),
    axis.text = element_text(size = 9),
    panel.grid.major.x = element_blank(),
    panel.grid.minor = element_blank()
  )

# 2. Plot 2: Latency (ms) vs Catalog Coverage Scatter/Bar
p2 <- ggplot(df, aes(x = latency_ms, y = catalog_coverage_pct, color = algorithm_clean)) +
  geom_point(size = 5, alpha = 0.9) +
  geom_text(aes(label = algorithm_clean), vjust = -1.2, fontface = "bold", size = 3.2) +
  scale_color_manual(values = paper_colors) +
  scale_y_continuous(limits = c(0, max(df$catalog_coverage_pct) * 1.3)) +
  scale_x_continuous(limits = c(0, max(df$latency_ms) * 1.3)) +
  theme_minimal(base_family = "sans") +
  labs(
    title = "Latency vs Catalog Coverage Tradeoff",
    subtitle = "Inference Time (ms) vs Catalog Diversity (%)",
    x = "Inference Latency (ms)",
    y = "Catalog Coverage (%)"
  ) +
  theme(
    legend.position = "none",
    plot.title = element_text(face = "bold", size = 12, hjust = 0.5),
    plot.subtitle = element_text(size = 9, hjust = 0.5, color = "#555555"),
    axis.title = element_text(face = "bold", size = 10),
    axis.text = element_text(size = 9)
  )

# Export combined grid figure (300 DPI)
combined_plot <- grid.arrange(p1, p2, ncol = 2)
ggsave(file.path(output_dir, "benchmark_recommender_paper_figure.png"), combined_plot, width = 10, height = 4.5, dpi = 300)
ggsave(file.path(output_dir, "precision_ndcg_comparison.png"), p1, width = 6, height = 4, dpi = 300)
ggsave(file.path(output_dir, "latency_vs_coverage.png"), p2, width = 6, height = 4, dpi = 300)

cat("Successfully generated academic paper figures in:", output_dir, "\n")
