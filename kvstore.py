import json
import os


class KVStore():
    def __init__(self, mainfile: str) -> None:
        self.mainfile: str = mainfile
        self.data = {}
        self.tempfile = "db.json.tmp"

        if not os.path.exists(mainfile):
            self.data = {}
            with open(self.mainfile, 'w') as f:
                json.dump(self.data, f, indent=2)

        else:
            with open(self.mainfile, 'r') as f:
                self.data = json.load(f)

    def get(self, key):
        return self.data.get(key)

    def put(self, key, value) -> None:
        self.data[key] = value
        with open(self.tempfile, 'w') as f:
            json.dump(self.data, f, indent=2)
            f.flush()  # Python gives bytes to the OS
            os.fsync(f.fileno())  # OS writes the bytes to the disk
        # Switches the reference of the tempfile to the mainfile
        os.replace(self.tempfile, self.mainfile)

    def delete(self, key) -> None:

        if key in self.data:
            self.data.pop(key, None)

        with open(self.tempfile, 'w') as f:
            json.dump(self.data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(self.tempfile, self.mainfile)


db = KVStore("db.json")
db.put("A", 0)
db.delete("A")
print(db.get("A"))
