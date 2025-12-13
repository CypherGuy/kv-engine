import json
import os


class KVStore():
    def __init__(self, fp: str) -> None:
        self.fp: str = fp
        self.data = {}

        if not os.path.exists(fp):
            self.data = {}
            with open(self.fp, 'w') as f:
                json.dump(self.data, f, indent=2)
        else:
            with open(self.fp, 'r') as f:
                self.data = json.load(f)

    def get(self, key):
        return self.data.get(key)

    def put(self, key, value) -> None:
        self.data[key] = value
        with open(self.fp, 'w') as f:
            json.dump(self.data, f, indent=2)

    def delete(self, key) -> None:
        self.data.pop(key, None)

        if key in self.data:
            self.data.pop(key, None)

        with open(self.fp, 'w') as f:
            json.dump(self.data, f, indent=2)


"""
Example:

db = KVStore("db.json")
db.put("A", 0)
db.delete("A")
print(db.get("A"))
"""
