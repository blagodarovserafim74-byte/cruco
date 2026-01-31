import hashlib
import os
import sqlite3
import time
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple


@dataclass
class FileRecord:
    path: str
    size: int
    mtime: float
    content_hash: str


@dataclass
class ScanResult:
    added: List[FileRecord]
    removed: List[FileRecord]
    modified: List[Tuple[FileRecord, FileRecord]]
    moved: List[Tuple[FileRecord, FileRecord]]
    unchanged: int
    scan_duration: float


class CodeTracker:
    def __init__(self, db_path: str, max_hash_size_bytes: int) -> None:
        self.db_path = db_path
        self.max_hash_size_bytes = max_hash_size_bytes
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS file_snapshots (
                    path TEXT PRIMARY KEY,
                    size INTEGER NOT NULL,
                    mtime REAL NOT NULL,
                    content_hash TEXT NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_hash ON file_snapshots(content_hash)"
            )

    def _hash_file(self, path: str) -> str:
        stat = os.stat(path)
        if stat.st_size > self.max_hash_size_bytes:
            return f"size:{stat.st_size}-mtime:{stat.st_mtime}"
        sha = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(8192), b""):
                sha.update(chunk)
        return sha.hexdigest()

    def _walk_files(self, root: str) -> Iterable[str]:
        for dirpath, _, filenames in os.walk(root):
            for name in filenames:
                yield os.path.join(dirpath, name)

    def scan(self, root: str) -> ScanResult:
        start = time.time()
        current_records: Dict[str, FileRecord] = {}
        for path in self._walk_files(root):
            try:
                stat = os.stat(path)
            except FileNotFoundError:
                continue
            record = FileRecord(
                path=os.path.relpath(path, root),
                size=stat.st_size,
                mtime=stat.st_mtime,
                content_hash=self._hash_file(path),
            )
            current_records[record.path] = record

        previous_records = self._load_records()
        previous_by_hash = self._index_by_hash(previous_records)
        current_by_hash = self._index_by_hash(current_records)

        added: List[FileRecord] = []
        removed: List[FileRecord] = []
        modified: List[Tuple[FileRecord, FileRecord]] = []
        moved: List[Tuple[FileRecord, FileRecord]] = []
        unchanged = 0

        for path, record in current_records.items():
            if path not in previous_records:
                added.append(record)
                continue
            previous = previous_records[path]
            if record.content_hash != previous.content_hash:
                modified.append((previous, record))
            else:
                unchanged += 1

        for path, record in previous_records.items():
            if path not in current_records:
                removed.append(record)

        for record in added[:]:
            previous_match = previous_by_hash.get(record.content_hash)
            if previous_match:
                moved.append((previous_match, record))
                added.remove(record)
                if previous_match in removed:
                    removed.remove(previous_match)

        for record in removed[:]:
            current_match = current_by_hash.get(record.content_hash)
            if current_match:
                moved.append((record, current_match))
                removed.remove(record)
                if current_match in added:
                    added.remove(current_match)

        self._save_records(list(current_records.values()))
        duration = time.time() - start
        return ScanResult(
            added=added,
            removed=removed,
            modified=modified,
            moved=moved,
            unchanged=unchanged,
            scan_duration=duration,
        )

    def _index_by_hash(self, records: Dict[str, FileRecord]) -> Dict[str, FileRecord]:
        return {record.content_hash: record for record in records.values()}

    def _load_records(self) -> Dict[str, FileRecord]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT path, size, mtime, content_hash FROM file_snapshots"
            ).fetchall()
        return {
            path: FileRecord(path=path, size=size, mtime=mtime, content_hash=content_hash)
            for path, size, mtime, content_hash in rows
        }

    def _save_records(self, records: List[FileRecord]) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM file_snapshots")
            conn.executemany(
                """
                INSERT INTO file_snapshots (path, size, mtime, content_hash, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        record.path,
                        record.size,
                        record.mtime,
                        record.content_hash,
                        time.time(),
                    )
                    for record in records
                ],
            )

    def apply_permissions(self, path: str, mode: int) -> None:
        try:
            os.chmod(path, mode)
        except OSError:
            pass
