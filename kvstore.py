import json
import os
import threading


class KVStore():
    def __init__(self, mainfile: str) -> None:
        self.mainfile: str = mainfile
        self.data = {}
        self.tempfile = "db.json.tmp"
        self.lock = threading.Lock()

        if not os.path.exists(mainfile):
            self.data = {}
            with open(self.mainfile, 'w') as f:
                json.dump(self.data, f, indent=2)

        else:
            with open(self.mainfile, 'r') as f:
                self.data = json.load(f)

    def get(self, key):
        with self.lock:
            return self.data.get(key)

    def put(self, key, value) -> None:
        with self.lock:
            self.data[key] = value
            with open(self.tempfile, 'w') as f:
                json.dump(self.data, f, indent=2)
                f.flush()  # Python gives bytes to the OS
                os.fsync(f.fileno())  # OS writes the bytes to the disk
            # Switches the reference of the tempfile to the mainfile
            os.replace(self.tempfile, self.mainfile)

    def delete(self, key) -> None:
        with self.lock:
            if key in self.data:
                self.data.pop(key, None)

            with open(self.tempfile, 'w') as f:
                json.dump(self.data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(self.tempfile, self.mainfile)
