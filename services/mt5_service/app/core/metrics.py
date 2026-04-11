from prometheus_client import Counter

# Execution Metrics
EXECUTION_SUCCESS = Counter(
    "mt5_execution_success_total", "Total number of successful order executions"
)
EXECUTION_FAILED = Counter(
    "mt5_execution_failed_total", "Total number of failed order executions"
)
