def test_put_latency(benchmark, kvstore):
    i = 0

    def do_put():
        nonlocal i
        kvstore.put(f"k{i}", i)
        i += 1

    benchmark(do_put)


def test_get_latency(benchmark, kvstore):
    # Preload data (not measured)
    for i in range(10_000):
        kvstore.put(f"k{i}", i)

    i = 0

    def do_get():
        nonlocal i
        kvstore.get(f"k{i % 10_000}")
        i += 1

    benchmark(do_get)


def test_delete_latency(benchmark, kvstore):
    # Preload data (not measured)
    for i in range(10_000):
        kvstore.put(f"k{i}", i)

    i = 0

    def do_delete():
        nonlocal i
        kvstore.delete(f"k{i % 10_000}")
        i += 1

    benchmark(do_delete)
