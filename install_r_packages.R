# ============================================================
# PredictGW — Instalação de Pacotes R
# Execute: Rscript install_r_packages.R
# ============================================================

packages <- c(
  "isotree",      # Isolation Forest
  "forecast",     # Auto-ARIMA
  "prophet",      # Facebook Prophet
  "stlplus",      # STL Decomposition
  "jsonlite",     # JSON serialization
  "dplyr",        # Data manipulation
  "lubridate"     # Date/time handling
)

install_if_missing <- function(pkg) {
  if (!requireNamespace(pkg, quietly = TRUE)) {
    cat(sprintf("Installing %s...\n", pkg))
    install.packages(pkg, repos = "https://cloud.r-project.org/", quiet = TRUE)
  } else {
    cat(sprintf("✓ %s already installed\n", pkg))
  }
}

invisible(lapply(packages, install_if_missing))

cat("\n✅ All R packages ready for PredictGW.\n")
