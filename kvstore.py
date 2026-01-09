import json
import os
import threading


class KVStore():
    def __init__(self, mainfile: str, walfile: str, checkpoint_file="checkpoint.json", checkpoint_every=5) -> None:
        self.mainfile: str = mainfile
        self.checkpoint_file = checkpoint_file
        self.checkpoint_every = checkpoint_every
        self.data = {}
        self.tempfile = "db.json.tmp"
        self.lock = threading.Lock()
        self.walfile = walfile
        self.op_count = 0

        if not os.path.exists(self.mainfile):
            with open(self.mainfile, "w") as f:
                json.dump({}, f)

        with open(self.mainfile, "r") as f:
            self.data = json.load(f)

        wal_offset = None
        if os.path.exists(self.checkpoint_file):
            try:
                with open(self.checkpoint_file, "r") as f:
                    meta = json.load(f)
                    wal_offset = int(meta.get("wal_offset", 0))
            except (OSError, json.JSONDecodeError, ValueError, TypeError):
                wal_offset = 0

        if os.path.exists(self.walfile):
            with open(self.walfile, "r") as f:
                if wal_offset is None:
                    wal_offset = 0
                try:
                    wal_size = os.path.getsize(self.walfile)
                except OSError:
                    wal_size = 0

                if wal_offset > wal_size:
                    wal_offset = 0

                f.seek(wal_offset)
                for line in f:
                    try:
                        record = json.loads(line)
                        self._apply_change(record)
                    except (json.JSONDecodeError, ValueError, KeyError):
                        break

    def _apply_change(self, record: dict):
        if record["action"] == "put":
            self.data[record["key"]] = record["value"]
        elif record["action"] == "delete":
            self.data.pop(record["key"], None)
        else:
            raise ValueError("Invalid WAL record")

    def get(self, key):
        with self.lock:
            return self.data.get(key)

    def put(self, key, value) -> None:
        with self.lock:
            with open(self.walfile, 'a') as f:
                f.write(json.dumps(
                    {"action": "put", "key": key, "value": value}) + "\n")
                f.flush()
                os.fsync(f.fileno())

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
        if self.op_count < self.checkpoint_every:
            return

        with open(self.tempfile, "w") as f:
            json.dump(self.data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(self.tempfile, self.mainfile)

        self._record_wal_position()
        self.op_count = 0
