# DESIGN.md

## 1. Design Goals

- Prioritise correctness over performance
- Make it impossible for a crash to leave the data in an invalid or corrupted state
- Adopt a linearizable system
  - Linearizability is the way that concurrent operations appear to be executed one by one, in an order that reflects real-time ordering
- Keep the design intentionally single-process and simple

---

## 2. State Model and Invariants

### State definition

- The logical state of the system consists of an in-memory key–value map and a persistent on-disk snapshot representing a committed state

### Core invariant

- The on-disk file always represents a **fully committed snapshot**
- The main database file is **either fully written or not at all**
- At any given time, In-memory state and on-disk state are the same
- These are never allowed:
  - A partially applied change
  - A database state that cannot be recovered after a crash

These invariants are **non-negotiable**.

---

## 3. How is Crash Consistency Achieved?

In order to implement crash safety, three methods have been implemented:

### Snapshot-based persistence

- Persistence is implemented via taking **snapshots of the state every time a change occurs**
- Each change rewrites the entire logical state

### Temporary file + atomic replace

- Writes are directed to a temporary file first
- Data is flushed and fsynced before becoming visible
  - The result of this is that Python gives the bits to the OS, and then OS then writes them into disk or other suitable storage
- The main database file is replaced using an **atomic filesystem rename**

### Why do we need this?

If a crash occurs before the replacement, the previous snapshot remains intact. However, If a crash occurs after the replacement, the new snapshot is fully visible. Temporary files are ignored on startup and never required for recovery

Having this guarantees crash safety without needing Journals or Recovery logs

---

## 4. Concurrency Model and Linearizability

### Concurrency model

The model I've chosen is a **thread-based single-process concurrency model**. In this model, many threads can interact with the same process, but one thread has exclusive access to the database at any given time, ensuring at most one operation may execute at any given time. With this, operations appear to be executed sequentially, even if they happen concurrently, on top of protecting the in-memory state from concurrent writes.

Additionally, both reads and writes are synchronised, meaning that operations cannot see a state that's mid-write.

#### Synchronisation strategy

- Only one operation can interact with the database at a time
- Both reads and writes are protected by the same lock
- This ensures operations behave as if they were executed sequentially

### Linearizability

Each operation has something called a linearizability point in which the operation is executed. When this happens,the operation will appear to be executed atomically. With all these operations haiving linearizability points, if all the operations's linearizability points are in the same order as the operations are executed, then the system is linearizable.

## 5. Concurrency vs Durability

Concurrency is the process of having multiple threads execute simultaneously on the same process. In this project, concurrency is achieved by ensuring only one process is acted on at a time, and that operations don't mix, leading to a confliced file state that might be midwrite.

Durability on the other hand is about what happens when the system crashes. In the case of kvstore, write are first done on a temporary file, and only once they're completed are they flushed/fsynced, meaning that the result of the operation (the snapshot) is written to disk. This prevents partial writes as if a crash happens mid write, the main file isn't affected. Recall section 3, the methods outlined there are how we ensure durability.

| System                        | Concurrency | Durability |
| ----------------------------- | ----------- | ---------- |
| Single-threaded, no disk      | ❌          | ❌         |
| Multi-threaded, no fsync      | ✅          | ❌         |
| Single-threaded, fsync        | ❌          | ✅         |
| Multi-threaded, fsync + locks | ✅          | ✅         |

### Why this matters

- Prevents reads from observing values that could be lost after a crash
- Ensures that any value observed by a reader is a recoverable state

---

## 6. Trade-offs and Non-Goals

### Coarse-grained mutual exclusion

Currently implemented is a single lock that protects the entire database state. Each operation (get, put, delete) must have this lock to access memory or disk. This design makes linearizability easier to enforce, as no other operations can get in the way of an operation being executed.

The trade-off of having this lock is reduced concurrency and scalability: operations cannot proceed in parallel, even when they access different keys. For this project, that is an intentional choice, because this project prioritises correctness, simplicity, and clear failure semantics over performance.

### Deferred complexity

The design as of now avoids:

- Fine-grained locking
- Lock-free data structures
- Read/write locks
- Multi-process concurrency

These are deferred until correctness foundations are firmly established.

---

## 7. What to do next

### Write-Ahead Logging (WAL)

- WAL would decouple durability from full snapshot rewrites
- The core invariants would remain unchanged
- New complexity would be introduced around:

  - Log replay
  - Ordering guarantees
  - Truncation

---

## Final note

- This design deliberately mirrors early-stage database engines
- Correctness guarantees are established before performance optimisations
- I am building this project in stages. Each stage builds on the previous one without weakening previous invariants
