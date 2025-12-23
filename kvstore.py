import json
import os
import threading


class KVStore():
    def __init__(self, mainfile: str, walfile: str) -> None:
        self.mainfile: str = mainfile
        self.data = {}
        self.tempfile = "db.json.tmp"
        self.lock = threading.Lock()
        self.walfile = walfile  # For Write-Ahead Logging

        # Get snapshot if exists, then get the current state by looking at the WALfile
        # The WALfile is a log of changes, in this case the format will be {action: put|delete, key: "key", value: "value"}

        if not os.path.exists(mainfile):
            self.data = {}
            with open(self.mainfile, 'w') as f:
                json.dump(self.data, f, indent=2)

        with open(self.mainfile, 'r') as f:
            # Load the last fully committed snapshot
            self.data = json.load(f)

        if os.path.exists(self.walfile):
            with open(self.walfile, 'r') as f:
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

            self.data[key] = value

            with open(self.tempfile, 'w') as f:
                json.dump(self.data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(self.tempfile, self.mainfile)

    def delete(self, key) -> None:
        with self.lock:
            with open(self.walfile, 'a') as f:
                f.write(json.dumps(
                    {"action": "delete", "key": key}) + "\n")
                f.flush()
                os.fsync(f.fileno())
            if key in self.data:
                self.data.pop(key, None)

            with open(self.tempfile, 'w') as f:
                json.dump(self.data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(self.tempfile, self.mainfile)


db = KVStore("db.json", "wal.json")
