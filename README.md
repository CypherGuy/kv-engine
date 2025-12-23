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

## Stage 4 — Write-ahead logging and crash recovery

- Snapshots are no longer trusted solely as the main source. We instead rely on the walfile to guarantee ordering and durability
- A Walfile has been introduced that records all writes to the database (`put` or `delete`) and then made durable using flush() followed by fsync()
- Upon restart, the database is restored change by change from the most recent snapshot, based from the walfile, stopping at the first invalid record (it's assumed to have happened due te a crash or powercut or something).

This stage focuses on **durability, write ordering and recovery from a crash** without needing to write an entire snapshot each time.

## Current Guarantees

| Category                         | Guaranteed at this stage? | Notes                                                                           |
| -------------------------------- | ------------------------- | ------------------------------------------------------------------------------- |
| API semantics                    | ✅                        | `get` returns `None` for missing keys; `put` overwrites; `delete` is idempotent |
| In-memory correctness            | ✅                        | In-memory state reflects the latest committed WAL entry                         |
| Persistence across clean restart | ✅                        | Snapshot + WAL replay restores full state                                       |
| Disk ↔ memory consistency        | ✅                        | Memory is reconstructed from snapshot + WAL, not snapshots alone                |
| Valid on-disk format             | ✅                        | WAL is append-only; snapshots are atomically replaced                           |
| Crash safety                     | ✅                        | Recovery proceeds up to the last valid WAL record                               |
| Atomicity under crash            | ✅                        | A change/mutation is either fully applied or not applied after restart          |
| Concurrency safety               | ✅                        | Thread-safe, linearizable access within a single process                        |
| Linearizable access              | ✅                        | All operations appear totally ordered                                           |
| Write ordering guarantees        | ✅                        | WAL preserves changes order                                                     |
| History preservation             | ✅                        | All acknowledged writes survive crashes                                         |
| Partial-write tolerance          | ✅                        | Truncated or corrupted WAL suffixes are safely ignored                          |
| Performance guarantees           | ❌                        | WAL fsync on every write; no batching                                           |
| Transactions                     | ❌                        | Single-key operations only                                                      |
| Asynchronous writes              | ❌                        | Writes are synchronous and blocking                                             |
| Log compaction                   | ❌                        | WAL grows unbounded without truncation                                          |
| Background flushing              | ❌                        | Snapshots are not generated incrementally                                       |

---

## Design Notes (Persistence & Storage)

- Persistence is implemented via Write-ahead logging
- Memory, upon startup, is derived from the most recent snapshot and the walfile
  - As a result snapshots are almost like checkpoints
- The order is: put/delete -> walfile modified -> flush/fsync -> modify tempfile -> rename tempfile to mainfile

---

## Example

```python
db = KVStore("db.json")
db.put("A", 0)
db.delete("A")
print(db.get("A"))  # None
```

---

## Out of Scope at this stage

- Fine-grained or lock-free concurrency
  - We've made a single owner, coarse grained locking system
- Asynchronous writes
- A way to truncate WAL so it doesn't go on forever
- Transactions
- Distributed systems
  - The system is intentionally single process on a single node so it's not distributed by definition
- Replication or sharding
- Query languages

---

## Next Step

The next stage introduces **snapshot checkpointing** on top of our current write-ahead logging. Right now snapshots exist but they aren't treated as actual checkpoints, and the WAL gets replayed from the beginning no matter how many records there are.

At stage 4, if we have to recover say 10 million records we have to start from transaction 1 and go all the way up. With stage 5, we set up checkpointing at certain points and 'reset' what we had saved before in terms of records written by WAL. This would mean we only have to start from the last checkpoint.

---

## Resources Used

- [https://www.geeksforgeeks.org/python/python-os-fsync-method/](https://www.geeksforgeeks.org/python/python-os-fsync-method/) to learn about fsync() and how to use it with file objects
- [https://www.geeksforgeeks.org/python/conftest-in-pytest/](https://www.geeksforgeeks.org/python/conftest-in-pytest/) to learn about conftest.py
- [https://www.geeksforgeeks.org/python/multithreading-python-set-1/](https://www.geeksforgeeks.org/python/multithreading-python-set-1/) to learn about threads
- [https://stackoverflow.com/questions/3310049/proper-use-of-mutexes-in-python](https://stackoverflow.com/questions/3310049/proper-use-of-mutexes-in-python) to learn about mutexes
- [https://maxnilz.com/docs/006-arch/003-concurrency-protocol/#:~:text=Q:%20Compare%20different%20Concurrency%20models,conditions%20and%20ensure%20data%20integrity](https://maxnilz.com/docs/006-arch/003-concurrency-protocol/#:~:text=Q:%20Compare%20different%20Concurrency%20models,conditions%20and%20ensure%20data%20integrity) to learn about the different types ofconcurrency models
- [https://www.architecture-weekly.com/p/the-write-ahead-log-a-foundation](https://www.architecture-weekly.com/p/the-write-ahead-log-a-foundation) to learn about write-ahead logging
- [https://medium.com/@vinciabhinav7/write-ahead-logs-but-why-494c3efd722d](https://medium.com/@vinciabhinav7/write-ahead-logs-but-why-494c3efd722d) to understand why use WAL in the first place
- `System Design Interview An Insider’s Guide by Alex Yu.pdf`, chapter 6 in particular to learn about standards for building a key-value store
