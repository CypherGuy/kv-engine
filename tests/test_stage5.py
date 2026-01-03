# tests/test_stage5.py
import os
import json
import time
import subprocess
import sys

import pytest
from kvstore import KVStore

DB_FILE = "db.json"
WAL_FILE = "wal.json"
TMP_FILE = "db.json.tmp"
CKPT_FILE = "checkpoint.json"


def clean():
    for f in (DB_FILE, WAL_FILE, TMP_FILE, CKPT_FILE):
        if os.path.exists(f):
            os.remove(f)


def read_json(path):
    with open(path, "r") as f:
        return json.load(f)


def wal_size():
    return os.path.getsize(WAL_FILE) if os.path.exists(WAL_FILE) else 0


def append_garbage_to_wal():
    with open(WAL_FILE, "a") as f:
        f.write('{"action": "put", "key": "CORRUPT"')  # truncated JSON tail


# -----------------------------------------
# 1) Checkpoint file exists and is valid JSON
# -----------------------------------------
def test_checkpoint_file_written_and_valid_json():
    clean()
    db = KVStore(DB_FILE, WAL_FILE)

    db.put("A", 1)
    db.put("B", 2)
    db.put("C", 3)
    db.put("D", 4)
    db.put("E", 5)   # triggers checkpoint

    assert os.path.exists(
        CKPT_FILE), "Stage 5 should write checkpoint metadata file"
    ckpt = read_json(CKPT_FILE)
    assert "wal_offset" in ckpt, "checkpoint must record wal_offset (byte position)"
    assert isinstance(ckpt["wal_offset"], int)
    assert ckpt["wal_offset"] >= 0


# -----------------------------------------
# 2) Checkpoint wal_offset is <= current WAL size
# -----------------------------------------
def test_checkpoint_offset_never_exceeds_wal_size():
    clean()
    db = KVStore(DB_FILE, WAL_FILE)

    for i in range(20):
        db.put(f"k{i}", i)

    ckpt = read_json(CKPT_FILE)
    assert ckpt["wal_offset"] <= wal_size()


# -----------------------------------------
# 3) Recovery uses checkpoint: corrupted WAL suffix is ignored
#    but only because replay starts AFTER the checkpoint offset
# -----------------------------------------
def test_restart_ignores_corrupted_wal_suffix_after_checkpoint():
    clean()
    db = KVStore(DB_FILE, WAL_FILE)

    db.put("A", 1)
    db.put("B", 2)
    db.put("C", 3)
    db.put("D", 4)
    db.put("E", 5)   # checkpoint happens here

    append_garbage_to_wal()

    db2 = KVStore(DB_FILE, WAL_FILE)
    assert db2.get("A") == 1
    assert db2.get("B") == 2
    assert db2.get("CORRUPT") is None


# -----------------------------------------
# 4) Idempotent recovery: repeated restarts do not change state
# -----------------------------------------
def test_recovery_idempotent_across_multiple_restarts():
    clean()
    db = KVStore(DB_FILE, WAL_FILE)
    db.put("A", 1)
    db.put("B", 2)
    db.delete("A")
    db.put("C", 3)

    for _ in range(5):
        db = KVStore(DB_FILE, WAL_FILE)
        assert db.get("A") is None
        assert db.get("B") == 2
        assert db.get("C") == 3


# -----------------------------------------
# 5) Checkpoint advances: wal_offset should increase (monotonic)
# -----------------------------------------
def test_checkpoint_offset_is_monotonic_increasing():
    clean()
    db = KVStore(DB_FILE, WAL_FILE)

    for _ in range(5):
        db.put("A", 1)
    ckpt1 = read_json(CKPT_FILE)["wal_offset"]

    for _ in range(5):
        db.put("B", 2)
    ckpt2 = read_json(CKPT_FILE)["wal_offset"]

    for _ in range(5):
        db.delete("A")
    ckpt3 = read_json(CKPT_FILE)["wal_offset"]

    assert ckpt1 <= ckpt2 <= ckpt3


# -----------------------------------------
# 6) Checkpoint consistency: snapshot reflects all WAL records <= checkpoint
#    We validate by intentionally breaking WAL tail and ensuring snapshot alone
#    is enough for keys that should be included.
# -----------------------------------------
def test_snapshot_covers_all_records_up_to_checkpoint():
    clean()
    db = KVStore(DB_FILE, WAL_FILE)

    db.put("A", 1)
    db.put("B", 2)
    db.put("C", 3)
    db.put("D", 4)
    db.put("E", 5)   # snapshot + checkpoint written

    # Read checkpoint and ensure snapshot already has A,B
    ckpt = read_json(CKPT_FILE)
    snap = read_json(DB_FILE)

    assert snap.get("A") == 1
    assert snap.get("B") == 2
    assert ckpt["wal_offset"] > 0

    # Corrupt WAL tail; restart should still have A,B due to snapshot + ckpt
    append_garbage_to_wal()
    db2 = KVStore(DB_FILE, WAL_FILE)
    assert db2.get("A") == 1
    assert db2.get("B") == 2


# -----------------------------------------
# 7) Crash during snapshot write does not break checkpointing
#    After crash, DB_FILE and CKPT_FILE must still be readable and state recoverable.
# -----------------------------------------
def test_crash_during_snapshot_write_keeps_db_and_checkpoint_valid():
    clean()

    # Script does many writes so there is a good chance it dies mid-work
    script = r"""
import time
from kvstore import KVStore

db = KVStore("db.json", "wal.json")
for i in range(1000):
    db.put(f"k{i}", i)
    # slow down slightly to increase chance of kill mid-snapshot/ckpt write
    time.sleep(0.0005)
"""

    p = subprocess.Popen(
        [sys.executable, "-c", script],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    time.sleep(0.05)
    p.kill()
    p.wait()

    # After crash, snapshot + checkpoint must still be parseable if they exist
    if os.path.exists(DB_FILE):
        read_json(DB_FILE)  # must not throw
    if os.path.exists(CKPT_FILE):
        read_json(CKPT_FILE)  # must not throw

    # And recovery should work (no exception) and return some valid state
    db = KVStore(DB_FILE, WAL_FILE)
    # At minimum, any recovered value is either present or not; must not crash.
    v = db.get("k0")
    assert v in (None, 0)


# -----------------------------------------
# 8) Checkpoint enables future optimization: replay should not require full WAL.
#    This test is a proxy: we assert checkpoint offset moves forward even when WAL grows.
# -----------------------------------------
def test_checkpoint_tracks_progress_even_as_wal_grows():
    clean()
    db = KVStore(DB_FILE, WAL_FILE)

    for i in range(200):
        db.put(f"k{i}", i)

    ckpt = read_json(CKPT_FILE)
    assert ckpt["wal_offset"] > 0
    assert ckpt["wal_offset"] <= wal_size()
