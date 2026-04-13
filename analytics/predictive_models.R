# ============================================================
# PredictGW — Motor Preditivo em R
# ============================================================
# Funções:
#   1. detect_anomalies()  - Isolation Forest + STL Decomposition
#   2. predict_rul()       - Prophet / Auto-ARIMA para RUL
#   3. calculate_health()  - Health Score composto (0-100)
# ============================================================

suppressPackageStartupMessages({
  library(jsonlite)
})

# ============================================================
# 1. DETECÇÃO DE ANOMALIAS
# ============================================================

detect_anomalies_isolation_forest <- function(values, contamination = 0.05) {
  #' Detecta anomalias usando Isolation Forest
  #' @param values Vetor numérico de leituras
  #' @param contamination Fração esperada de anomalias
  #' @return Lista com scores e flags de anomalia

  if (length(values) < 20) {
    return(list(
      scores = rep(0, length(values)),
      is_anomaly = rep(FALSE, length(values)),
      anomaly_count = 0,
      method = "isolation_forest",
      status = "insufficient_data"
    ))
  }

  tryCatch({
    if (requireNamespace("isotree", quietly = TRUE)) {
      library(isotree)

      df <- data.frame(value = values)
      model <- isolation.forest(df, ntrees = 100, sample_size = min(256, nrow(df)))
      scores <- predict(model, df)

      threshold <- quantile(scores, 1 - contamination)
      is_anomaly <- scores > threshold

      return(list(
        scores = as.numeric(scores),
        is_anomaly = as.logical(is_anomaly),
        anomaly_count = sum(is_anomaly),
        threshold = as.numeric(threshold),
        method = "isolation_forest",
        status = "success"
      ))
    } else {
      # Fallback: Z-score method
      return(detect_anomalies_zscore(values))
    }
  }, error = function(e) {
    return(detect_anomalies_zscore(values))
  })
}


detect_anomalies_stl <- function(values, timestamps = NULL, frequency = 60) {
  #' Detecta anomalias via STL Decomposition
  #' @param values Vetor numérico
  #' @param frequency Frequência da série (amostras por ciclo)
  #' @return Lista com componentes e anomalias

  if (length(values) < frequency * 2 + 1) {
    return(list(
      remainder = rep(0, length(values)),
      is_anomaly = rep(FALSE, length(values)),
      anomaly_count = 0,
      method = "stl",
      status = "insufficient_data"
    ))
  }

  tryCatch({
    ts_data <- ts(values, frequency = frequency)

    if (requireNamespace("stlplus", quietly = TRUE)) {
      library(stlplus)
      decomp <- stlplus(ts_data, s.window = "periodic")
      remainder <- decomp$data$remainder
    } else {
      decomp <- stl(ts_data, s.window = "periodic")
      remainder <- as.numeric(decomp$time.series[, "remainder"])
    }

    # Anomalias: resíduos fora de 2.5 desvios-padrão
    remainder_sd <- sd(remainder, na.rm = TRUE)
    remainder_mean <- mean(remainder, na.rm = TRUE)
    threshold <- 2.5 * remainder_sd
    is_anomaly <- abs(remainder - remainder_mean) > threshold

    return(list(
      trend = as.numeric(decomp$time.series[, "trend"]),
      seasonal = as.numeric(decomp$time.series[, "seasonal"]),
      remainder = as.numeric(remainder),
      is_anomaly = as.logical(is_anomaly),
      anomaly_count = sum(is_anomaly, na.rm = TRUE),
      threshold = as.numeric(threshold),
      method = "stl",
      status = "success"
    ))
  }, error = function(e) {
    return(list(
      remainder = rep(0, length(values)),
      is_anomaly = rep(FALSE, length(values)),
      anomaly_count = 0,
      method = "stl",
      status = paste("error:", e$message)
    ))
  })
}


detect_anomalies_zscore <- function(values) {
  #' Fallback: detecção por Z-score (sem dependências extras)
  mean_val <- mean(values, na.rm = TRUE)
  sd_val <- sd(values, na.rm = TRUE)

  if (is.na(sd_val) || sd_val == 0) {
    return(list(
      scores = rep(0, length(values)),
      is_anomaly = rep(FALSE, length(values)),
      anomaly_count = 0,
      method = "zscore_fallback",
      status = "success"
    ))
  }

  z_scores <- abs((values - mean_val) / sd_val)
  is_anomaly <- z_scores > 2.5

  return(list(
    scores = as.numeric(z_scores),
    is_anomaly = as.logical(is_anomaly),
    anomaly_count = sum(is_anomaly),
    threshold = 2.5,
    method = "zscore_fallback",
    status = "success"
  ))
}


detect_anomalies <- function(values, method = "isolation_forest", ...) {
  #' Dispatcher para detecção de anomalias
  if (method == "isolation_forest") {
    return(detect_anomalies_isolation_forest(values, ...))
  } else if (method == "stl") {
    return(detect_anomalies_stl(values, ...))
  } else {
    return(detect_anomalies_zscore(values))
  }
}


# ============================================================
# 2. PREVISÃO DE RUL (Remaining Useful Life)
# ============================================================

predict_rul_prophet <- function(timestamps, values, critical_limit, horizon_hours = 72) {
  #' Prevê quando a variável atingirá o limite crítico usando Prophet
  #' @param timestamps Vetor de timestamps (character ISO 8601)
  #' @param values Vetor numérico de leituras
  #' @param critical_limit Limite crítico superior
  #' @param horizon_hours Horizonte de previsão em horas
  #' @return Lista com previsão e timestamp estimado de falha

  if (length(values) < 30) {
    return(list(
      rul_hours = NA,
      failure_timestamp = NA,
      confidence = 0,
      method = "prophet",
      status = "insufficient_data"
    ))
  }

  tryCatch({
    if (requireNamespace("prophet", quietly = TRUE)) {
      library(prophet)

      df <- data.frame(
        ds = as.POSIXct(timestamps, format = "%Y-%m-%d %H:%M:%S"),
        y = values
      )

      # Treinar modelo
      m <- prophet(df, daily.seasonality = FALSE, weekly.seasonality = FALSE,
                   yearly.seasonality = FALSE, changepoint.prior.scale = 0.1)

      # Previsão
      future <- make_future_dataframe(m, periods = horizon_hours * 60, freq = "min")
      forecast <- predict(m, future)

      # Encontrar quando f(t) > critical_limit
      future_forecast <- forecast[forecast$ds > max(df$ds), ]
      breach_idx <- which(future_forecast$yhat > critical_limit)

      if (length(breach_idx) > 0) {
        failure_time <- future_forecast$ds[breach_idx[1]]
        rul_hours <- as.numeric(difftime(failure_time, max(df$ds), units = "hours"))

        return(list(
          rul_hours = round(rul_hours, 2),
          failure_timestamp = format(failure_time, "%Y-%m-%d %H:%M:%S"),
          forecast_values = as.numeric(tail(future_forecast$yhat, 100)),
          forecast_lower = as.numeric(tail(future_forecast$yhat_lower, 100)),
          forecast_upper = as.numeric(tail(future_forecast$yhat_upper, 100)),
          critical_limit = critical_limit,
          confidence = 0.85,
          method = "prophet",
          status = "failure_predicted"
        ))
      } else {
        return(list(
          rul_hours = Inf,
          failure_timestamp = NA,
          forecast_values = as.numeric(tail(future_forecast$yhat, 100)),
          critical_limit = critical_limit,
          confidence = 0.85,
          method = "prophet",
          status = "no_failure_in_horizon"
        ))
      }
    } else {
      return(predict_rul_linear(timestamps, values, critical_limit))
    }
  }, error = function(e) {
    return(predict_rul_linear(timestamps, values, critical_limit))
  })
}


predict_rul_arima <- function(timestamps, values, critical_limit, horizon_hours = 72) {
  #' Prevê RUL usando Auto-ARIMA
  #' @param timestamps Vetor de timestamps
  #' @param values Vetor numérico
  #' @param critical_limit Limite crítico
  #' @param horizon_hours Horizonte em horas

  if (length(values) < 30) {
    return(list(
      rul_hours = NA,
      failure_timestamp = NA,
      confidence = 0,
      method = "arima",
      status = "insufficient_data"
    ))
  }

  tryCatch({
    if (requireNamespace("forecast", quietly = TRUE)) {
      library(forecast)

      ts_data <- ts(values)
      model <- auto.arima(ts_data, stepwise = TRUE, approximation = TRUE)
      n_ahead <- horizon_hours * 60  # 1 leitura por minuto estimado
      fc <- forecast(model, h = min(n_ahead, 500))

      forecast_values <- as.numeric(fc$mean)
      breach_idx <- which(forecast_values > critical_limit)

      last_timestamp <- as.POSIXct(tail(timestamps, 1), format = "%Y-%m-%d %H:%M:%S")

      if (length(breach_idx) > 0) {
        # Estimar tempo baseado no índice
        steps_to_failure <- breach_idx[1]
        avg_interval_sec <- as.numeric(difftime(
          as.POSIXct(tail(timestamps, 1), format = "%Y-%m-%d %H:%M:%S"),
          as.POSIXct(head(timestamps, 1), format = "%Y-%m-%d %H:%M:%S"),
          units = "secs"
        )) / length(timestamps)

        rul_seconds <- steps_to_failure * avg_interval_sec
        rul_hours <- rul_seconds / 3600
        failure_time <- last_timestamp + rul_seconds

        return(list(
          rul_hours = round(rul_hours, 2),
          failure_timestamp = format(failure_time, "%Y-%m-%d %H:%M:%S"),
          forecast_values = forecast_values,
          forecast_lower = as.numeric(fc$lower[, 2]),
          forecast_upper = as.numeric(fc$upper[, 2]),
          critical_limit = critical_limit,
          confidence = 0.75,
          method = "arima",
          status = "failure_predicted"
        ))
      } else {
        return(list(
          rul_hours = Inf,
          failure_timestamp = NA,
          forecast_values = forecast_values,
          critical_limit = critical_limit,
          confidence = 0.75,
          method = "arima",
          status = "no_failure_in_horizon"
        ))
      }
    } else {
      return(predict_rul_linear(timestamps, values, critical_limit))
    }
  }, error = function(e) {
    return(predict_rul_linear(timestamps, values, critical_limit))
  })
}


predict_rul_linear <- function(timestamps, values, critical_limit) {
  #' Fallback: regressão linear simples para RUL
  n <- length(values)
  x <- 1:n
  fit <- lm(values ~ x)
  slope <- coef(fit)[2]
  intercept <- coef(fit)[1]
  current_value <- tail(values, 1)

  if (is.na(slope) || slope <= 0) {
    return(list(
      rul_hours = Inf,
      failure_timestamp = NA,
      slope_per_hour = 0,
      confidence = 0.5,
      method = "linear_fallback",
      status = "no_rising_trend"
    ))
  }

  # Estima steps até o limite
  steps_to_failure <- (critical_limit - current_value) / slope

  if (steps_to_failure <= 0) {
    return(list(
      rul_hours = 0,
      failure_timestamp = format(Sys.time(), "%Y-%m-%d %H:%M:%S"),
      slope_per_hour = as.numeric(slope),
      confidence = 0.5,
      method = "linear_fallback",
      status = "already_exceeded"
    ))
  }

  # Converter steps para horas (estimando intervalo médio)
  last_ts <- as.POSIXct(tail(timestamps, 1), format = "%Y-%m-%d %H:%M:%S")
  first_ts <- as.POSIXct(head(timestamps, 1), format = "%Y-%m-%d %H:%M:%S")
  avg_interval_sec <- as.numeric(difftime(last_ts, first_ts, units = "secs")) / n

  rul_hours <- (steps_to_failure * avg_interval_sec) / 3600
  failure_time <- last_ts + (steps_to_failure * avg_interval_sec)

  return(list(
    rul_hours = round(rul_hours, 2),
    failure_timestamp = format(failure_time, "%Y-%m-%d %H:%M:%S"),
    slope_per_step = as.numeric(slope),
    confidence = 0.5,
    method = "linear_fallback",
    status = "failure_predicted"
  ))
}


predict_rul <- function(timestamps, values, critical_limit, method = "prophet", ...) {
  #' Dispatcher para previsão de RUL
  if (method == "prophet") {
    return(predict_rul_prophet(timestamps, values, critical_limit, ...))
  } else if (method == "arima") {
    return(predict_rul_arima(timestamps, values, critical_limit, ...))
  } else {
    return(predict_rul_linear(timestamps, values, critical_limit))
  }
}


# ============================================================
# 3. HEALTH SCORE
# ============================================================

calculate_health_score <- function(anomaly_result, rul_result, variance_ratio = 1.0, uptime_ratio = 1.0) {
  #' Calcula o Health Score composto (0-100)
  #' Composição:
  #'   40% - Anomalias (menos anomalias = melhor)
  #'   30% - RUL (mais tempo até falha = melhor)
  #'   20% - Variância (menos variância = melhor)
  #'   10% - Disponibilidade (mais uptime = melhor)

  # Score de anomalia (0-100, 100 = sem anomalias)
  anomaly_count <- anomaly_result$anomaly_count
  total_points <- length(anomaly_result$is_anomaly)
  if (total_points > 0) {
    anomaly_ratio <- anomaly_count / total_points
    anomaly_score <- max(0, (1 - anomaly_ratio * 5)) * 100
  } else {
    anomaly_score <- 100
  }

  # Score de RUL (0-100, 100 = muito tempo até falha)
  rul_hours <- rul_result$rul_hours
  if (is.na(rul_hours) || is.infinite(rul_hours)) {
    rul_score <- 100
  } else if (rul_hours <= 0) {
    rul_score <- 0
  } else if (rul_hours < 1) {
    rul_score <- 10
  } else if (rul_hours < 4) {
    rul_score <- 30
  } else if (rul_hours < 12) {
    rul_score <- 50
  } else if (rul_hours < 24) {
    rul_score <- 70
  } else if (rul_hours < 72) {
    rul_score <- 85
  } else {
    rul_score <- 100
  }

  # Score de variância (0-100, inversamente proporcional)
  variance_score <- max(0, min(100, (1 - min(1, variance_ratio)) * 100))

  # Score de uptime (0-100)
  uptime_score <- max(0, min(100, uptime_ratio * 100))

  # Composição ponderada
  health_score <- round(
    anomaly_score * 0.40 +
    rul_score * 0.30 +
    variance_score * 0.20 +
    uptime_score * 0.10,
    1
  )

  # Classificação
  if (health_score >= 85) {
    classification <- "Excelente"
    color <- "#22c55e"
  } else if (health_score >= 70) {
    classification <- "Bom"
    color <- "#84cc16"
  } else if (health_score >= 50) {
    classification <- "Atenção"
    color <- "#eab308"
  } else if (health_score >= 30) {
    classification <- "Alerta"
    color <- "#f97316"
  } else {
    classification <- "Crítico"
    color <- "#ef4444"
  }

  return(list(
    score = health_score,
    classification = classification,
    color = color,
    components = list(
      anomaly_score = round(anomaly_score, 1),
      rul_score = round(rul_score, 1),
      variance_score = round(variance_score, 1),
      uptime_score = round(uptime_score, 1)
    ),
    weights = list(
      anomaly = 0.40,
      rul = 0.30,
      variance = 0.20,
      uptime = 0.10
    ),
    rul_hours = rul_hours,
    anomaly_count = anomaly_count
  ))
}


# ============================================================
# 4. PIPELINE COMPLETO
# ============================================================

run_predictive_analysis <- function(timestamps_json, values_json, critical_limit,
                                    anomaly_method = "isolation_forest",
                                    rul_method = "prophet",
                                    uptime_ratio = 1.0) {
  #' Pipeline completo: dados → anomalias → RUL → health score
  #' @param timestamps_json JSON string com vetor de timestamps
  #' @param values_json JSON string com vetor de valores
  #' @param critical_limit Limite crítico da variável
  #' @return JSON string com resultados completos

  timestamps <- fromJSON(timestamps_json)
  values <- as.numeric(fromJSON(values_json))

  # 1. Detecção de anomalias
  anomaly_result <- detect_anomalies(values, method = anomaly_method)

  # 2. Previsão de RUL
  rul_result <- predict_rul(timestamps, values, critical_limit, method = rul_method)

  # 3. Variância normalizada
  if (length(values) > 1 && mean(values, na.rm = TRUE) != 0) {
    cv <- sd(values, na.rm = TRUE) / abs(mean(values, na.rm = TRUE))
  } else {
    cv <- 0
  }

  # 4. Health Score
  health <- calculate_health_score(anomaly_result, rul_result, cv, uptime_ratio)

  result <- list(
    anomalies = anomaly_result,
    rul = rul_result,
    health = health,
    data_points = length(values),
    analysis_timestamp = format(Sys.time(), "%Y-%m-%d %H:%M:%S")
  )

  return(toJSON(result, auto_unbox = TRUE, pretty = TRUE))
}


cat("✅ PredictGW R Predictive Models loaded.\n")
