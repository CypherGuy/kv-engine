import json
import os
import threading


class KVStore():
    def __init__(self, mainfile: str, walfile: str, checkpoint_file="checkpoint.json", checkpoint_every=5) -> None:
        self.mainfile: str = mainfile
        self.checkpoint_file = checkpoint_file     # Checkpoint metadata
        self.checkpoint_every = checkpoint_every   # Checkpoint frequency
        self.data = {}
        self.tempfile = "db.json.tmp"
        self.lock = threading.Lock()
        self.walfile = walfile  # For Write-Ahead Logging
        self.op_count = 0

        # Get snapshot if exists, then get the current state by looking at the WALfile
        # The WALfile is a log of changes, in this case the format will be {action: put|delete, key: "key", value: "value"}

        if not os.path.exists(self.mainfile):
            with open(self.mainfile, "w") as f:
                json.dump({}, f)

        with open(self.mainfile, "r") as f:
            # Load the last fully committed snapshot
            self.data = json.load(f)

        # I had tests in stage 4 fail once I did stage 5. I've modified this code so that
        # if a checkpoint hasn't been made the offset is at the start of the file, as stage 4 expects.

        # Get the offset of the last checkpoint if it exists
        wal_offset = None
        if os.path.exists(self.checkpoint_file):
            try:
                with open(self.checkpoint_file, "r") as f:
                    meta = json.load(f)
                    wal_offset = int(meta.get("wal_offset", 0))
            except (OSError, json.JSONDecodeError, ValueError, TypeError):
                wal_offset = 0

        # If, like in the case of the stage 4 tests, we don't have a checkpoint, we just start from the beginning. Otherwise
        # we start from the last checkpoint. Think of the checkpoint as a materialization of the WALfile up to some point that
        # we can start replaying from
        if os.path.exists(self.walfile):
            with open(self.walfile, "r") as f:
                # No checkpoint > just go to the beginning
                if wal_offset is None:
                    wal_offset = 0
                try:
                    wal_size = os.path.getsize(self.walfile)
                except OSError:
                    wal_size = 0

                # We want to check in case the checkpoint has tracked more then our WALfile. If so, we replay from the start

                # This is essential because we don't want to replay the WAL if our checkpoint goes
                # further then what we have in the WAL. This may happen for example if a crash were to happen midwrite.
                if wal_offset > wal_size:
                    wal_offset = 0

                f.seek(wal_offset)
                for line in f:
                    try:
                        record = json.loads(line)
                        self._apply_change(record)
                    except json.JSONDecodeError:
                        break

    def _apply_change(self, record: dict):
        # Applying WAL changes should only affect in-memory storage, not the snapshot (mainfile)
        if record["action"] == "put":
            self.data[record["key"]] = record["value"]
        elif record["action"] == "delete":
            if record["key"] in self.data:
                self.data.pop(record["key"], None)

    def get(self, key):
        with self.lock:
            return self.data.get(key)

    def put(self, key, value) -> None:
        with self.lock:
            with open(self.walfile, 'a') as f:
                f.write(json.dumps(
                    {"action": "put", "key": key, "value": value}) + "\n")
                f.flush()  # Python gives bytes to the OS
                os.fsync(f.fileno())  # OS writes the bytes to the disk

            self.op_count += 1
            self.data[key] = value

            self._maybe_checkpoint()

    def delete(self, key) -> None:
        with self.lock:
            with open(self.walfile, 'a') as f:
                f.write(json.dumps(
                    {"action": "delete", "key": key}) + "\n")
                f.flush()
                os.fsync(f.fileno())
            self.op_count += 1
            if key in self.data:
                self.data.pop(key, None)

            self._maybe_checkpoint()

    def _record_wal_position(self):
        wal_offset = os.path.getsize(self.walfile)
        tmp_checkpoint = self.checkpoint_file + ".tmp"
        with open(tmp_checkpoint, "w") as f:
            json.dump({"wal_offset": wal_offset}, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_checkpoint, self.checkpoint_file)

    def _maybe_checkpoint(self):
        # Have we hit our checkpoint?
        if self.op_count < self.checkpoint_every:
            return

        # Write the snapshot as we did before
        with open(self.tempfile, "w") as f:
            json.dump(self.data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(self.tempfile, self.mainfile)

        # Record WAL position in a new file
        self._record_wal_position()

        # 3. Reset counter
        self.op_count = 0


if __name__ == "__main__":
    db = KVStore("db.json", "wal.json")
