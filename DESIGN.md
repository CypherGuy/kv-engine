# DESIGN.md

## 1. Design Goals

- Prioritise correctness over performance
- Make it impossible for a crash to leave the data in an invalid or corrupted state
- Adopt a linearizable system
  - Linearizability is the way that concurrent operations appear to be executed one by one, in an order that reflects real-time ordering
- Keep the design intentionally single-process and simple
- Reduce crash recovery time without weakening durability guarantees

---

## 2. State Model and Invariants

### State definition

- The logical state of the system consists of an in-memory key–value map and a persistent on-disk snapshot representing a committed state

### Core invariant

- The on-disk file always represents a **fully committed snapshot**
- The main database file is **either fully written or not at all**
- Recovery always reconstructs the state as:
  snapshot + WAL replay (from checkpoint offset)
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

## 4. Checkpointing

Checkpoints are performed every N mutations. A checkpoint in this case consists of:

- Writing a snapshot of in-memory state

and then

- Recording the WAL byte offset covered by that snapshot

Checkpoint metadata is written atomically. Doing this also reduces recovery time by limiting how much of the WAL needs to be replayed.

---

## 5. Concurrency Model and Linearizability

### Concurrency model

The model I've chosen is a **thread-based single-process concurrency model**. In this model, many threads can interact with the same process, but one thread has exclusive access to the database at any given time, ensuring at most one operation may execute at any given time. With this, operations appear to be executed sequentially, even if they happen concurrently, on top of protecting the in-memory state from concurrent writes.

Additionally, both reads and writes are synchronised, meaning that operations cannot see a state that's mid-write.

#### Synchronisation strategy

- Only one operation can interact with the database at a time
- Both reads and writes are protected by the same lock
- This ensures operations behave as if they were executed sequentially

### Linearizability

Each operation has something called a linearizability point in which the operation is executed. When this happens,the operation will appear to be executed atomically. With all these operations haiving linearizability points, if all the operations's linearizability points are in the same order as the operations are executed, then the system is linearizable.

## 6. Concurrency vs Durability

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

## 7. Trade-offs and Non-Goals

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

## 8. Observed Latency Characteristics

In order to test benchmarking I opted to continue using pytest and used `pytest-benchmark==5.2.3` to measure latencies. As this didn't work out things like each functions p1,50 and 99, I created a script to work these out too. I'll quickly put the graphs then explain what I take from this.

### Pytest Benchmarking

| Name                | Min (ns)             | Max (ns)                 | Mean (ns)              | StdDev (ns)            | Median (ns)          | IQR (ns)             | Outliers  | OPS (Kops/s) | Rounds  | Iterations |
| ------------------- | -------------------- | ------------------------ | ---------------------- | ---------------------- | -------------------- | -------------------- | --------- | ------------ | ------- | ---------- |
| test_get_latency    | 174.3707 (1.0)       | 50,026.2206 (1.0)        | 224.5733 (1.0)         | 126.0082 (1.0)         | 220.6652 (1.0)       | 18.5532 (1.0)        | 2130;3935 | 4,452.8888   | 195,122 | 27         |
| test_put_latency    | 25,458.9831 (146.00) | 1,790,000.0094 (35.78)   | 214,571.3537 (955.46)  | 387,432.6197 (>1000.0) | 36,625.0169 (165.98) | 10,499.9635 (565.94) | 650;787   | 4.6605       | 3,910   | 1          |
| test_delete_latency | 29,625.0219 (169.90) | 38,867,915.9805 (776.95) | 257,314.1452 (>1000.0) | 715,234.9094 (>1000.0) | 36,999.9907 (167.67) | 7,583.0030 (408.72)  | 1631;3975 | 3.8863       | 19,786  | 1          |

Legend:

- Outliers: 1 Standard Deviation from Mean; 1.5 IQR (InterQuartile Range) from 1st Quartile and 3rd Quartile.
- OPS: Operations Per Second, computed as 1 / Mean

These tests can be found in tests/test_benchmarking.py

### Latency Percentiles (nanoseconds)

| Operation | p1        | p50       | p99          | Max           | Iterations |
| --------- | --------- | --------- | ------------ | ------------- | ---------- |
| GET       | 211 ns    | 229 ns    | 260 ns       | 1,489 ns      | 198,373    |
| PUT       | 28,208 ns | 37,042 ns | 1,042,404 ns | 1,850,166 ns  | 2,336      |
| DELETE    | 32,874 ns | 37,833 ns | 3,111,150 ns | 42,740,790 ns | 22,202     |

Total procesing time: around 0.219 seconds

You can see my script that works this out in tests/analyze_benchmarks.py

### My interpretation

As expected, GET operations are very quick and very stable. The median latency is ~230 ns, and the p99 is even still under 300ns. They don't access the JSON file and don't requie disk I/O (via fsync), they only access in-memory storage via `self.data.get(key)`.

However, PUT and DELETE operations are more complex. The median latency is ~37,000 ns for both operations, and the p99 ranges from 1-3ms.

The big jump in time from GET to PUT/DELETE is expected though what with the synchronous nature of the KV store. There's a lot of steps that go into these functions including appending to the WAL, `flush()` and `fsync()` and the checkpointing if needed. As we begin to checkpoint, the time to PUT/DELETE goes up, which would explain the high p99 latency as well as the high Max value for DELETE.

This concludes the project at this point in time. Over time now I will optimise the program and perhaps add things like group commits and possibly background checkpointing.

## Final note

- This design deliberately mirrors early-stage database engines
- Correctness guarantees are established before performance optimisations
- I am building this project in stages. Each stage builds on the previous one without weakening previous invariants
