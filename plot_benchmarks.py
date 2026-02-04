import json
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path


BENCH_FILE = Path("bench.json")


def load_latency_data():
    """
    Loads raw latency samples from pytest-benchmark JSON output.
    Returns dict: {operation: np.ndarray}
    """
    with open(BENCH_FILE, "r") as f:
        bench = json.load(f)

    latencies = {}

    for entry in bench["benchmarks"]:
        name = entry["name"]

        if "get" in name:
            op = "GET"
        elif "put" in name:
            op = "PUT"
        elif "delete" in name:
            op = "DELETE"
        else:
            continue

        # Raw per-iteration timings (seconds → nanoseconds)
        data = np.array(entry["stats"]["data"]) * 1e9
        latencies[op] = data

    return latencies


def compute_cdf(latencies_ns):
    """
    Given an array of latencies (ns), return (sorted_latencies, cdf)
    """
    sorted_vals = np.sort(latencies_ns)
    cdf = np.arange(1, len(sorted_vals) + 1) / len(sorted_vals)
    return sorted_vals, cdf


def plot_latency_cdf(latencies):
    plt.figure(figsize=(12, 7))

    min_latency = min(np.min(v) for v in latencies.values())

    for op, data in latencies.items():
        x, y = compute_cdf(data)
        plt.plot(x, y, label=op, linewidth=2)

    # Log scale on latency axis
    plt.xscale("log")

    # Horizontal percentile reference lines
    plt.axhline(0.01, linestyle="--", linewidth=1, color="grey", alpha=0.7)
    plt.axhline(0.50, linestyle="--", linewidth=1.5, color="grey", alpha=0.9)
    plt.axhline(0.99, linestyle="--", linewidth=1, color="grey", alpha=0.7)

    # Percentile labels
    plt.text(min_latency, 0.01, "p1", va="bottom", fontsize=10)
    plt.text(min_latency, 0.50, "p50", va="bottom", fontsize=10)
    plt.text(min_latency, 0.99, "p99", va="bottom", fontsize=10)

    # Y-only grid (clean)
    plt.grid(axis="y", linestyle=":", alpha=0.4)

    plt.xlabel("Latency (nanoseconds, log scale)")
    plt.ylabel("Cumulative probability")
    plt.title("Latency CDF Graph")

    plt.legend()
    plt.tight_layout()
    plt.show()


def main():
    latencies = load_latency_data()

    if not latencies:
        raise RuntimeError("No latency data found in bench.json")

    plot_latency_cdf(latencies)


if __name__ == "__main__":
    main()
