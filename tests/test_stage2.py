import os
import json
import subprocess
import sys
import time
from kvstore import KVStore

DB_FILE = "db.json"
TMP_FILE = "db.json.tmp"


def clean():
    for f in (DB_FILE, TMP_FILE):
        if os.path.exists(f):
            os.remove(f)


def read_json(path):
    with open(path, "r") as f:
        return json.load(f)


# ---------- Test 1: Clean restart works ----------

def test_clean_restart():
    clean()

    db = KVStore(DB_FILE)
    db.put("A", 1)
    db.put("B", 2)

    del db

    db2 = KVStore(DB_FILE)
    assert db2.get("A") == 1
    assert db2.get("B") == 2


# ---------- Test 2: Snapshot is always valid JSON ----------

def test_snapshot_always_valid_json():
    clean()

    db = KVStore(DB_FILE)

    for i in range(50):
        db.put(f"k{i}", i)
        read_json(DB_FILE)  # must never throw


# ---------- Test 3: Temp file ignored on startup ----------

def test_temp_file_ignored():
    clean()

    with open(DB_FILE, "w") as f:
        json.dump({"A": 1}, f)

    with open(TMP_FILE, "w") as f:
        f.write("{ this is garbage")

    db = KVStore(DB_FILE)

    assert db.get("A") == 1


# ---------- Test 4: Crash during write leaves valid snapshot ----------

def test_crash_during_write():
    clean()

    script = """
from kvstore import KVStore

db = KVStore("db.json")
db.put("A", 1)
db.put("B", 2)
"""

    p = subprocess.Popen(
        [sys.executable, "-c", script],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    time.sleep(0.01)
    p.kill()
    p.wait()

    db = KVStore(DB_FILE)

    a = db.get("A")
    b = db.get("B")

    # Stage 2 guarantee:
    # State must be one of the fully committed snapshots
    assert a in (None, 1)
    assert b in (None, 2)

    # Additionally: impossible states must not occur
    assert not (a is None and b == 2)


# ---------- Test 5: Delete is crash-safe ----------

def test_crash_during_delete():
    clean()

    script = """
from kvstore import KVStore
db = KVStore("db.json")
db.put("A", 1)
db.delete("A")
"""

    p = subprocess.Popen(
        [sys.executable, "-c", script],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    time.sleep(0.01)
    p.kill()
    p.wait()

    db = KVStore(DB_FILE)

    assert db.get("A") in (None, 1)


# ---------- Test 6: Main file never partially written ----------

def test_main_file_not_partial():
    clean()

    db = KVStore(DB_FILE)
    db.put("A", 1)

    with open(DB_FILE, "rb") as f:
        data = f.read()

    assert data.startswith(b"{")
    assert data.endswith(b"}")


# ---------- Test 7: Temp file not required for recovery ----------

def test_startup_without_temp():
    clean()

    db = KVStore(DB_FILE)
    db.put("A", 1)

    if os.path.exists(TMP_FILE):
        os.remove(TMP_FILE)

    db2 = KVStore(DB_FILE)
    assert db2.get("A") == 1
