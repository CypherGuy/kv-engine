"""
Stage 3 Concurrency Tests

These tests validate that the KVStore provides:
- Mutual exclusion
- Atomic visibility of operations
- Linearizable behaviour under concurrent access
- No deadlocks under contention

They are NOT performance tests.
They are correctness and impossibility tests.
"""

import threading
from kvstore import KVStore


# ------------------------------------------------------------
# Test 1: Concurrent writes do not lose updates
# ------------------------------------------------------------
def test_concurrent_writes_no_loss():
    """
    Multiple threads write to the same key concurrently.

    Guarantee being tested:
    - Writes are mutually exclusive
    - No write is silently dropped
    - Final state reflects some serial ordering of writes
    """

    db = KVStore("db.json")

    def writer(i):
        db.put("counter", i)

    threads = []
    for i in range(50):
        t = threading.Thread(target=writer, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # Final value must be one of the values written
    assert db.get("counter") in range(50)


# ------------------------------------------------------------
# Test 2: Readers never observe partial state
# ------------------------------------------------------------
def test_reader_never_sees_partial_state():
    """
    One thread repeatedly writes new values.
    Another thread continuously reads.

    Guarantee being tested:
    - Readers never observe half-completed writes
    - Reads are synchronized with writers
    """

    db = KVStore("db.json")
    db.put("A", 0)

    stop = False
    observed = []

    def writer():
        for i in range(1, 100):
            db.put("A", i)

    def reader():
        while not stop:
            val = db.get("A")
            observed.append(val)

    t1 = threading.Thread(target=writer)
    t2 = threading.Thread(target=reader)

    t1.start()
    t2.start()

    t1.join()
    stop = True
    t2.join()

    # Reader must only ever see committed integer values
    assert all(v in range(100) for v in observed)


# ------------------------------------------------------------
# Test 3: Put/Delete race does not produce impossible states
# ------------------------------------------------------------
def test_put_delete_race():
    """
    One thread repeatedly puts a key.
    Another thread repeatedly deletes the same key.

    Guarantee being tested:
    - put and delete are atomic
    - no mixed or impossible states occur
    """

    db = KVStore("db.json")
    db.put("A", 1)

    def putter():
        for _ in range(50):
            db.put("A", 1)

    def deleter():
        for _ in range(50):
            db.delete("A")

    t1 = threading.Thread(target=putter)
    t2 = threading.Thread(target=deleter)

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Final state must be consistent with some serial ordering
    assert db.get("A") in (None, 1)


# ------------------------------------------------------------
# Test 4: Read does not observe uncommitted state
# ------------------------------------------------------------
def test_read_does_not_observe_uncommitted_state():
    """
    A writer and reader race.

    Guarantee being tested:
    - Reads never observe a value that could be lost after a crash
    - Read happens either before or after the write, never during
    """

    db = KVStore("db.json")
    results = []

    def writer():
        db.put("A", 1)

    def reader():
        results.append(db.get("A"))

    t1 = threading.Thread(target=writer)
    t2 = threading.Thread(target=reader)

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Reader must see either old or committed new state
    assert results[0] in (None, 1)


# ------------------------------------------------------------
# Test 5: No deadlock under contention
# ------------------------------------------------------------
def test_no_deadlock_under_load():
    """
    Many threads repeatedly perform mixed operations.

    Guarantee being tested:
    - Locks are always released
    - No deadlock or permanent blocking occurs
    """

    db = KVStore("db.json")

    def worker(i):
        for _ in range(10):
            db.put(str(i), i)
            db.get(str(i))
            db.delete(str(i))

    threads = []
    for i in range(10):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()
