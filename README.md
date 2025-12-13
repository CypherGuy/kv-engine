# kv-engine

A minimal, single-process key–value storage engine built to explore **durability, crash behaviour, and storage semantics** from first principles.

This project intentionally avoids distribution, networking, concurrency, and performance optimisations in order to focus on **correctness and reasoning about state**.

---

## Overview

The system exposes a simple key–value API:

- `get(key) → value | None`
- `put(key, value)`
- `delete(key)`

Internally, the store maintains an in-memory map and persists state to disk to survive restarts.

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

## Current Guarantees

| Category                         | Guaranteed | Notes                                                                           |
| -------------------------------- | ---------- | ------------------------------------------------------------------------------- |
| API semantics                    | ✅         | `get` returns `None` for missing keys; `put` overwrites; `delete` is idempotent |
| In-memory correctness            | ✅         | In-memory state always reflects the latest mutations                            |
| Persistence across clean restart | ✅         | State is fully restored if the process exits normally                           |
| Disk ↔ memory consistency        | ✅         | After each mutation, disk is a full snapshot of in-memory state                 |
| Valid on-disk format             | ✅         | Snapshot is always valid JSON after successful writes                           |
| Crash safety                     | ❌         | A crash during write may corrupt the snapshot                                   |
| Atomicity under crash            | ❌         | Writes are not atomic with respect to process failure                           |
| Concurrency safety               | ❌         | Single-threaded only                                                            |
| Performance guarantees           | ❌         | Full snapshot written on every mutation                                         |
| Transactions                     | ❌         | Single-key operations only                                                      |
| Asynchronous writes              | ❌         | All writes are synchronous                                                      |

---

## Design Notes

- Persistence is implemented via full-state snapshots (JSON)
- Disk is never consulted during mutations; memory is the source of truth
- The storage format and write strategy are deliberately simple to expose failure modes clearly

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

- Asynchronous I/O
- Transactions
- Write-ahead logging
- Distributed systems
- Replication or sharding
- Query languages

---

## Next Step

The next stage introduces **crash-safe snapshots** using atomic file replacement, ensuring the database always restarts from a valid state even after a crash.

---

### Final note

This README is intentionally concise. Each new stage updates:

- the _Stages Implemented_ section
- the _Current Guarantees_ table
