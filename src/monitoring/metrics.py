"""Prometheus metrics and audit helpers."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

REQUEST_COUNT = Counter(
    "partscope_http_requests_total",
    "HTTP requests processed",
    ["method", "path", "status"],
)
REQUEST_LATENCY = Histogram(
    "partscope_http_request_duration_seconds",
    "HTTP request latency",
    ["method", "path"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)
VISION_LATENCY = Histogram(
    "partscope_vision_inference_seconds",
    "Vision inference latency",
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)
FORECAST_LATENCY = Histogram(
    "partscope_forecast_inference_seconds",
    "Forecast inference latency",
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
)
RETRIEVAL_LATENCY = Histogram(
    "partscope_retrieval_seconds",
    "Retrieval latency",
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5),
)
AGENT_RUNS = Counter(
    "partscope_agent_runs_total",
    "Agent runs by status",
    ["status", "intent"],
)
AGENT_TOOL_FAILURES = Counter(
    "partscope_agent_tool_failures_total",
    "Failed agent tool calls",
    ["tool"],
)
MODEL_INFO = Gauge(
    "partscope_model_info",
    "Loaded model version information",
    ["model", "version", "task"],
)
REFUSALS = Counter(
    "partscope_refusals_total",
    "Answers refused for insufficient evidence",
    ["domain"],
)
