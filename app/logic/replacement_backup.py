"""Recoverable file snapshots used by CS2 resource replacers.

The helper deliberately uses only the standard library so replacement logic can
be tested without loading the Qt UI.  A snapshot is immutable for the lifetime
of one operation; callers commit it only after all replacement writes succeed.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import uuid
from pathlib import Path


class ReplacementBackup:
    """Snapshot and restore a bounded set of files for one replacement run."""

    MANIFEST_VERSION = 1

    def __init__(self, root_dir: str | os.PathLike[str], operation: str):
        if not operation or any(char in operation for char in '\\/:*?"<>|'):
            raise ValueError("operation must be a simple directory name")

        self.root_dir = Path(root_dir).expanduser().resolve()
        self.operation = operation
        self.operation_dir = self.root_dir / f"{operation}-{uuid.uuid4().hex}"
        self.operation_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path = str(self.operation_dir / "manifest.json")
        self._entries: dict[str, dict] = {}
        self._committed = False

    @classmethod
    def from_manifest(cls, manifest_path: str | os.PathLike[str]) -> "ReplacementBackup":
        """Load a committed operation without creating a new snapshot."""

        manifest = Path(manifest_path).expanduser().resolve()
        with manifest.open("r", encoding="utf-8") as stream:
            payload = json.load(stream)
        if payload.get("version") != cls.MANIFEST_VERSION:
            raise ValueError("unsupported replacement backup manifest version")
        instance = cls.__new__(cls)
        instance.root_dir = manifest.parent.parent
        instance.operation_dir = manifest.parent
        instance.operation = str(payload.get("operation", manifest.parent.name))
        instance.manifest_path = str(manifest)
        instance._entries = {
            str(entry["path"]): dict(entry)
            for entry in payload.get("files", [])
        }
        instance._committed = True
        return instance

    @classmethod
    def latest(cls, root_dir: str | os.PathLike[str], operation: str) -> "ReplacementBackup | None":
        """Return the newest committed operation, if one exists."""

        root = Path(root_dir).expanduser().resolve()
        manifests = list(root.glob(f"{operation}-*/manifest.json")) if root.is_dir() else []
        if not manifests:
            return None
        manifests.sort(key=lambda path: path.stat().st_mtime, reverse=True)
        return cls.from_manifest(manifests[0])

    @staticmethod
    def _absolute(path: str | os.PathLike[str]) -> Path:
        # ``Path.resolve`` follows symlinks.  For replacement targets we must
        # retain the lexical path so the caller can reject a symlink instead
        # of accidentally snapshotting or restoring the link's destination.
        return Path(os.path.abspath(os.path.expanduser(os.fspath(path))))

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _atomic_copy(source: Path, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
        try:
            shutil.copy2(source, temporary)
            os.replace(temporary, target)
        finally:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass

    def _backup_file_path(self, backup_name: str | os.PathLike[str]) -> Path:
        """Resolve a manifest backup name without allowing path escape."""

        if not isinstance(backup_name, (str, os.PathLike)):
            raise ValueError("invalid replacement backup path")
        relative = Path(backup_name)
        if relative.is_absolute():
            raise ValueError("replacement backup path must be relative")

        candidate = self.operation_dir / relative
        if candidate.is_symlink():
            raise ValueError("replacement backup path may not be a symlink")
        operation_dir = self.operation_dir.resolve()
        resolved = candidate.resolve(strict=False)
        if resolved == operation_dir or operation_dir not in resolved.parents:
            raise ValueError("replacement backup path escapes operation directory")
        return candidate

    def snapshot_file(self, path: str | os.PathLike[str]) -> None:
        """Record the original state of *path* exactly once."""

        absolute = self._absolute(path)
        key = str(absolute)
        if key in self._entries:
            return

        if absolute.is_symlink():
            raise ValueError(f"refusing to snapshot symlink: {absolute}")

        if absolute.is_file():
            backup_name = f"{len(self._entries):04d}-{absolute.name}"
            backup_path = self.operation_dir / backup_name
            self._atomic_copy(absolute, backup_path)
            self._entries[key] = {
                "path": key,
                "existed": True,
                "backup_path": backup_name,
                "sha256": self._sha256(backup_path),
            }
        elif absolute.exists():
            raise ValueError(f"replacement target is not a regular file: {absolute}")
        else:
            self._entries[key] = {
                "path": key,
                "existed": False,
                "backup_path": None,
                "sha256": None,
            }

    def snapshot_directory(self, directory: str | os.PathLike[str]) -> None:
        """Snapshot regular files below *directory*, without following links."""

        root = self._absolute(directory)
        if not root.exists():
            return
        if not root.is_dir() or root.is_symlink():
            raise ValueError(f"replacement directory is invalid: {root}")
        for current, dir_names, file_names in os.walk(root, followlinks=False):
            dir_names[:] = [name for name in dir_names if not (Path(current) / name).is_symlink()]
            for name in file_names:
                self.snapshot_file(Path(current) / name)

    def backed_up_paths(self) -> list[str]:
        """Return the target paths whose original bytes this snapshot holds."""

        return [entry["path"] for entry in self._entries.values() if entry.get("existed")]

    def record_created(self, path: str | os.PathLike[str]) -> None:
        """Record a generated path when its absence was not snapshotted first."""

        absolute = self._absolute(path)
        key = str(absolute)
        if key not in self._entries:
            # Treat this as a convenience for callers that create a file only
            # after registering it.  If a file already exists (for example a
            # user's pre-existing config), snapshot its bytes instead of
            # incorrectly marking it as toolkit-owned and deleting it during
            # restore.
            self.snapshot_file(absolute)

    def commit(self) -> None:
        """Persist this operation's manifest atomically."""

        payload = {
            "version": self.MANIFEST_VERSION,
            "operation": self.operation,
            "files": list(self._entries.values()),
        }
        temporary = f"{self.manifest_path}.{uuid.uuid4().hex}.tmp"
        try:
            with open(temporary, "w", encoding="utf-8", newline="\n") as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.manifest_path)
            self._committed = True
        finally:
            try:
                os.remove(temporary)
            except FileNotFoundError:
                pass

    def restore(self) -> None:
        """Restore every snapshotted file; safe to call repeatedly."""

        if not self._entries and not os.path.isfile(self.manifest_path):
            return

        entries = list(self._entries.values())
        if not entries and os.path.isfile(self.manifest_path):
            with open(self.manifest_path, "r", encoding="utf-8") as stream:
                entries = json.load(stream).get("files", [])

        for entry in entries:
            target = self._absolute(entry["path"])
            if target.is_symlink():
                raise ValueError(f"refusing to restore symlink: {target}")
            if entry.get("existed"):
                backup_name = entry.get("backup_path")
                if not backup_name:
                    raise FileNotFoundError(f"missing backup record for {target}")
                backup_path = self._backup_file_path(backup_name)
                if not backup_path.is_file():
                    raise FileNotFoundError(f"missing backup file for {target}")
                expected_hash = entry.get("sha256")
                if expected_hash and self._sha256(backup_path) != expected_hash:
                    raise ValueError(f"replacement backup integrity check failed: {target}")
                self._atomic_copy(backup_path, target)
            elif target.exists():
                if target.is_file():
                    target.unlink()
                else:
                    raise ValueError(f"refusing to remove non-file generated path: {target}")
