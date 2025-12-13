class KVStore():
    def __init__(self) -> None:
        self.data = {}

    def get(self, key):
        return self.data.get(key)

    def put(self, key, value) -> None:
        self.data[key] = value

    def delete(self, key) -> None:
        self.data.pop(key, None)


"""
Example:

db = KVStore()
db.put("A", 0)
print(db.get("B")) # None
"""
