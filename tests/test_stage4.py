# Ideas for these tests were taken from Chapter 6 in: System Design Interview An Insider’s Guide by Alex Yu.pdf

import os
import json
import pytest
from kvstore import KVStore

DB_FILE = "db.json"
WAL_FILE = "wal.json"


def clean():
    for f in (DB_FILE, WAL_FILE):
        if os.path.exists(f):
            os.remove(f)


def test_write_visible_after_restart_only_if_in_wal():
    # Shows that WAL is the durability boundary, as with Apache Cassandra for example
    clean()

    with open(DB_FILE, "w") as f:
        json.dump({}, f)

    # Write appears only in WAL
    with open(WAL_FILE, "w") as f:
        f.write(json.dumps({"action": "put", "key": "A", "value": 1}) + "\n")

    db = KVStore(DB_FILE, WAL_FILE)

    assert db.get("A") == 1


def test_in_memory_only_write_is_lost():
    # Confirms that in-memory state alone is not durable, as expected
    clean()

    db = KVStore(DB_FILE, WAL_FILE)
    db.data["A"] = 1  # simulate memtable update without WAL

    del db

    db2 = KVStore(DB_FILE, WAL_FILE)
    assert db2.get("A") is None


def test_wal_truncated_record_is_ignored():
    # Tests if WAL replay must stop at corruption
    clean()

    with open(DB_FILE, "w") as f:
        json.dump({}, f)

    with open(WAL_FILE, "w") as f:
        f.write(json.dumps({"action": "put", "key": "A", "value": 1}) + "\n")
        f.write('{"action": "put", "key": "B"')

    db = KVStore(DB_FILE, WAL_FILE)

    assert db.get("A") == 1
    assert db.get("B") is None


def test_wal_replay_idempotent():
    # Tests if WAL replay is idempotent - Needed for a proper restart
    clean()

    with open(DB_FILE, "w") as f:
        json.dump({}, f)

    with open(WAL_FILE, "w") as f:
        f.write(json.dumps({"action": "put", "key": "A", "value": 1}) + "\n")

    db1 = KVStore(DB_FILE, WAL_FILE)
    db2 = KVStore(DB_FILE, WAL_FILE)

    assert db1.get("A") == 1
    assert db2.get("A") == 1


def test_delete_logged_in_wal():
    # Tests if Delete is a first-class WAL operation
    clean()

    with open(DB_FILE, "w") as f:
        json.dump({"A": 1}, f)

    with open(WAL_FILE, "w") as f:
        f.write(json.dumps({"action": "delete", "key": "A"}) + "\n")

    db = KVStore(DB_FILE, WAL_FILE)
    assert db.get("A") is None


def test_snapshot_plus_wal_recovery():
    # Shows that Snapshot + WAL together define full state
    clean()

    with open(DB_FILE, "w") as f:
        json.dump({"A": 1}, f)

    with open(WAL_FILE, "w") as f:
        f.write(json.dumps({"action": "put", "key": "B", "value": 2}) + "\n")

    db = KVStore(DB_FILE, WAL_FILE)

    assert db.get("A") == 1
    assert db.get("B") == 2
