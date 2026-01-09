import json
from pathlib import Path
import numpy as np

BENCH_FILE = Path("bench.json")


def ns(x: float) -> int:
    return int(x * 1_000_000_000)


def analyze_benchmark(bench: dict):
    name = bench["name"]
    stats = bench["stats"]

    data = stats.get("data")
    if not data:
        print(f"{name}: no raw data available\n")
        return

    samples = np.array(data, dtype=float)

    p1 = np.percentile(samples, 1)
    p50 = np.percentile(samples, 50)
    p99 = np.percentile(samples, 99)

    print(name)
    print(f"  samples: {len(samples)}")
    print(f"  p1:   {ns(p1):,} ns")
    print(f"  p50:  {ns(p50):,} ns")
    print(f"  p99:  {ns(p99):,} ns")
    print(f"  min:  {ns(stats['min']):,} ns")
    print(f"  max:  {ns(stats['max']):,} ns")
    print()


def main():

    with BENCH_FILE.open() as f:
        data = json.load(f)

    print("\nLatency percentiles (derived from raw samples)\n")

    for bench in data.get("benchmarks", []):
        analyze_benchmark(bench)


if __name__ == "__main__":
    main()
