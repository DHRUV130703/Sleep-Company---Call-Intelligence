"""Files stored in the database (app/storage.py): parts, ranges, joining, renaming, temp copies."""

from app import storage
from app.storage import PART_SIZE

DATA = bytes(range(256)) * (PART_SIZE * 2 // 256 + 100)  # a bit over 2 parts


def test_round_trip_and_exact_part_sizes(session):
    assert storage.put_bytes("audio/norm/a.mp3", DATA, "audio/mpeg") == len(DATA)
    blob = storage.info("audio/norm/a.mp3")
    assert blob is not None and blob.parts == 3 and blob.content_type == "audio/mpeg"
    assert [len(p) for p in storage.iter_parts("audio/norm/a.mp3")] == [
        PART_SIZE,
        PART_SIZE,
        len(DATA) - 2 * PART_SIZE,
    ]
    assert storage.read_bytes("audio/norm/a.mp3") == DATA


def test_range_reads_cross_part_boundaries(session):
    storage.put_bytes("k", DATA)
    for start, end in [
        (0, 99),
        (PART_SIZE - 10, PART_SIZE + 9),
        (len(DATA) - 5, len(DATA) - 1),
        (5, 2 * PART_SIZE + 3),
    ]:
        assert b"".join(storage.iter_range("k", start, end)) == DATA[start : end + 1]


def test_small_writes_are_packed_into_full_parts(session):
    storage.put_bytes("c/0", DATA[:1000])
    storage.put_bytes("c/1", DATA[1000:])
    assert storage.concat(["c/0", "c/1"], "c/file") == len(DATA)  # unaligned pieces: bytes are copied
    assert [len(p) for p in storage.iter_parts("c/file")][0] == PART_SIZE
    assert storage.read_bytes("c/file") == DATA and storage.keys("c/") == ["c/file"]


def test_aligned_chunks_join_without_copying(session):
    storage.put_bytes("u/0", DATA[:PART_SIZE])
    storage.put_bytes("u/1", DATA[PART_SIZE:])
    storage.concat(["u/0", "u/1"], "u/file")
    assert storage.read_bytes("u/file") == DATA and not storage.exists("u/0")


def test_rename_delete_and_local_copy(session):
    storage.put_bytes("uploads/x/file.mp3", b"abc")
    storage.rename("uploads/x/file.mp3", "audio/raw/sha.mp3")
    assert not storage.exists("uploads/x/file.mp3")
    with storage.local_copy("audio/raw/sha.mp3") as path:
        assert path.read_bytes() == b"abc" and path.suffix == ".mp3"
    assert not path.exists()  # temporary copy removed
    assert storage.delete_prefix("audio/") == 1 and storage.total_size() == (0, 0)


def test_audio_range_header_parsing():
    from app.api.calls import parse_range

    assert parse_range(None, 1000) is None
    assert parse_range("bytes=0-99", 1000) == (0, 99)
    assert parse_range("bytes=900-", 1000) == (900, 999)
    assert parse_range("bytes=-100", 1000) == (900, 999)
    assert parse_range("bytes=990-5000", 1000) == (990, 999)
