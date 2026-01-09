import pytest
from kvstore import KVStore


@pytest.fixture
def kvstore(tmp_path):
    """
    Fresh KVStore instance per benchmark.
    Setup cost is NOT included in timing.
    Files are isolated per test.
    """
    db_file = tmp_path / "db.json"
    wal_file = tmp_path / "wal.json"
    checkpoint_file = tmp_path / "checkpoint.json"

    return KVStore(
        mainfile=str(db_file),
        walfile=str(wal_file),
        checkpoint_file=str(checkpoint_file),
    )
