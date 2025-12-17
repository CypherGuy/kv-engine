# kv-engine

A minimal, single-process key–value storage engine built to explore **durability, crash behaviour, concurrency correctness, and storage semantics** from first principles.

This project intentionally avoids distribution, networking, and performance optimisations, in order to focus more on **correctness, failure modes, and reasoning about state under concurrency.**

---

## Overview

The system exposes a simple key–value API:

- `get(key) → value | None`
- `put(key, value)`
- `delete(key)`

Internally, the store maintains an in-memory map and persists state to disk to survive restarts.

## Concurrency Model

The model I've chosen is essentially a single-owner concurrency model. In this model, many threads can interact with the same process, but one thread has exclusive access to the database at any given time. With this, operations appear to be executed sequentially, even if they happen concurrently, on top of protecting the in-memory state from concurrent writes.

Additionally, both reads and writes are synchronised, meaning that they cannot see a state that's mid-write.

---

## Stages Implemented

### Stage 0 — In-memory semantics

- Data stored entirely in memory
- Defines stable API semantics:

  - missing keys return `None`
  - deleting a missing key is a no-op

- No persistence
- Restart loses all data

This stage exists to lock down **behavioural guarantees** before introducing storage.

---

### Stage 1 — Naive full-state persistence

- Entire in-memory state is serialized to disk after each mutation
- State is loaded from disk on startup
- Clean shutdown + restart restores all data
- Disk is treated as a mirror of memory (memory is authoritative)

This stage provides persistence but is **not crash-safe**.

---

### Stage 2 — Crash-safe snapshot persistence

- Writes are performed to a temporary file, never directly to the main database file
- Each write is made durable with `flush` + `fsync` before becoming visible
- The main database file is replaced atomically using filesystem rename
- After a crash, the database is always in a previously committed state
- Temporary files are ignored on startup and never required for recovery

This stage guarantees **atomicity and durability**, but not write ordering or history preservation.

### Stage 3 — Thread-safe, linearizable access

- All operations (get, put, delete) happen with exclusive ownership of the database
- Concurrent access behaves as if operations were executed sequentially in some total order
- Both Read and Write operations are locked out whilst another operation is in progress to prevent an operation from seeing a partial or uncommitted state
- Operations appear to happen instantaneously somewhere between their start and end times

This stage guarantees **linearizable behaviour** under concurrent access within a single process.

---

## Current Guarantees

| Category                         | Guaranteed | Notes                                                                           |
| -------------------------------- | ---------- | ------------------------------------------------------------------------------- |
| API semantics                    | ✅         | `get` returns `None` for missing keys; `put` overwrites; `delete` is idempotent |
| In-memory correctness            | ✅         | In-memory state always reflects the latest completed mutation                   |
| Persistence across clean restart | ✅         | State is fully restored if the process exits normally                           |
| Disk ↔ memory consistency        | ✅         | Disk reflects a full snapshot of in-memory state after each commit              |
| Valid on-disk format             | ✅         | Main file is never partially written                                            |
| Crash safety                     | ✅         | Database restarts from a valid committed snapshot                               |
| Atomicity under crash            | ✅         | Writes are atomic with respect to process failure                               |
| Concurrency safety               | ✅         | Thread-safe, linearizable access within a single process                        |
| Linearizable access              | ✅         | All operations appear totally ordered under concurrency                         |
| Write ordering guarantees        | ❌         | Earlier writes may be lost if a later write crashes                             |
| Performance guarantees           | ❌         | Full snapshot written on every mutation                                         |
| Transactions                     | ❌         | Single-key operations only                                                      |
| Asynchronous writes              | ❌         | All writes are synchronous                                                      |

---

## Design Notes (Persistence & Storage)

- Persistence is implemented via full-state snapshots (JSON)
- Memory is the source of truth; disk is only updated via committed snapshots
- The write path is intentionally simple to make crash behaviour explicit

---

## Example

```python
db = KVStore("db.json")
db.put("A", 0)
db.delete("A")
print(db.get("A"))  # None
```

---

## Scope (Explicitly Out of Scope)

- Fine-grained or lock-free concurrency
- Asynchronous I/O
- Transactions
- Write-ahead logging
- Distributed systems
- Replication or sharding
- Query languages

---

## Next Step

The next stage introduces **write-ahead logging (WAL)** to guarantee that once a write returns successfully, it will survive any future crash without requiring full snapshot rewrites.

---

## Resources Used

- [https://www.geeksforgeeks.org/python/python-os-fsync-method/](https://www.geeksforgeeks.org/python/python-os-fsync-method/) to learn about fsync() and how to use it with file objects
- [https://www.geeksforgeeks.org/python/conftest-in-pytest/](https://www.geeksforgeeks.org/python/conftest-in-pytest/) to learn about conftest.py
- [https://stackoverflow.com/questions/3310049/proper-use-of-mutexes-in-python](https://stackoverflow.com/questions/3310049/proper-use-of-mutexes-in-python) to learn about mutexes
- [https://maxnilz.com/docs/006-arch/003-concurrency-protocol/#:~:text=Q:%20Compare%20different%20Concurrency%20models,conditions%20and%20ensure%20data%20integrity](https://maxnilz.com/docs/006-arch/003-concurrency-protocol/#:~:text=Q:%20Compare%20different%20Concurrency%20models,conditions%20and%20ensure%20data%20integrity) to learn about the different types ofconcurrency models
