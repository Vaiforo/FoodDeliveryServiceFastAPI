import csv
import json
import os
import random
import statistics
import time
from pathlib import Path

import matplotlib.pyplot as plt
import requests


GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8000")
RUNS = int(os.getenv("RUNS", "100"))
MODE_LABEL = os.getenv("MODE_LABEL", "rest")
RESULTS_DIR = Path(os.getenv("RESULTS_DIR", "./benchmark/results"))


def wait_for_gateway():
    for _ in range(60):
        try:
            response = requests.get(f"{GATEWAY_URL}/health", timeout=2)
            if response.ok:
                return
        except Exception:
            pass
        time.sleep(2)
    raise RuntimeError("Gateway is not ready")


def build_payload(index: int) -> dict:
    start = (index % 20) + 1
    product_ids = [start, start + 1, start + 2]
    return {
        "customer_id": (index % 100) + 1,
        "product_ids": product_ids,
        "delivery_address": f"Benchmark street {index}, house {index % 10 + 1}",
        "note": f"benchmark-run-{index}",
    }


def run():
    wait_for_gateway()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    sample_rows = []

    for index in range(1, RUNS + 1):
        payload = build_payload(index)
        started = time.perf_counter()
        response = requests.post(f"{GATEWAY_URL}/api/orders/checkout", json=payload, timeout=30)
        elapsed_ms = (time.perf_counter() - started) * 1000

        row = {
            "call_no": index,
            "elapsed_ms": round(elapsed_ms, 3),
            "status_code": response.status_code,
        }
        sample_rows.append(row)

    values = [row["elapsed_ms"] for row in sample_rows]
    mean_value = statistics.mean(values)
    variance_value = statistics.variance(values) if len(values) > 1 else 0.0

    csv_path = RESULTS_DIR / f"{MODE_LABEL}_sample.csv"
    stats_path = RESULTS_DIR / f"{MODE_LABEL}_stats.json"
    plot_path = RESULTS_DIR / f"{MODE_LABEL}_plot.png"

    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["call_no", "elapsed_ms", "status_code"])
        writer.writeheader()
        writer.writerows(sample_rows)

    with stats_path.open("w", encoding="utf-8") as file:
        json.dump(
            {
                "mode": MODE_LABEL,
                "runs": RUNS,
                "mean_ms": round(mean_value, 3),
                "variance_ms": round(variance_value, 3),
            },
            file,
            ensure_ascii=False,
            indent=2,
        )

    plt.figure(figsize=(10, 5))
    plt.plot([row["call_no"] for row in sample_rows], values)
    plt.xlabel("Call number")
    plt.ylabel("Elapsed time, ms")
    plt.title(f"Checkout benchmark ({MODE_LABEL})")
    plt.tight_layout()
    plt.savefig(plot_path)

    print(f"Saved: {csv_path}")
    print(f"Saved: {stats_path}")
    print(f"Saved: {plot_path}")


if __name__ == "__main__":
    run()
