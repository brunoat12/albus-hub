from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

BackupMode = Literal["auto", "full", "incremental"]


class BackupService:
    """Cria backups full e incrementais de forma independente de provedor."""

    def __init__(
        self,
        backup_root: Path,
        sources: Mapping[str, Path],
        retention_days: int = 30,
        full_interval_days: int = 7,
    ) -> None:
        self.backup_root = backup_root.resolve()
        self.sources = {name: path.resolve() for name, path in sources.items()}
        self.retention_days = retention_days
        self.full_interval_days = full_interval_days

        self.state_dir = self.backup_root / "state"
        self.state_file = self.state_dir / "latest_state.json"

        self.backup_root.mkdir(parents=True, exist_ok=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()

        with path.open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)

        return digest.hexdigest()

    @staticmethod
    def _write_json(path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)

        path.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def _load_state(self) -> dict:
        if not self.state_file.exists():
            return {}

        return json.loads(self.state_file.read_text(encoding="utf-8"))

    def _discover_files(self) -> tuple[dict[str, dict], list[str]]:
        files: dict[str, dict] = {}
        missing_sources: list[str] = []

        for source_name, source_root in self.sources.items():
            if not source_root.exists():
                missing_sources.append(source_name)
                continue

            for path in sorted(source_root.rglob("*")):
                if not path.is_file():
                    continue

                if path.name == ".gitkeep":
                    continue

                relative_path = path.relative_to(source_root).as_posix()

                archive_path = f"{source_name}/{relative_path}"

                files[archive_path] = {
                    "source_name": source_name,
                    "relative_path": relative_path,
                    "size_bytes": path.stat().st_size,
                    "sha256": self._sha256(path),
                }

        return files, missing_sources

    def _select_mode(
        self,
        requested_mode: BackupMode,
        state: dict,
        now: datetime,
    ) -> Literal["full", "incremental"]:
        if requested_mode == "full":
            return "full"

        if requested_mode == "incremental":
            if not state.get("last_full_id"):
                raise RuntimeError("Backup incremental exige um backup full anterior.")

            return "incremental"

        last_full_at = state.get("last_full_at")

        if not last_full_at:
            return "full"

        last_full_datetime = datetime.fromisoformat(last_full_at)

        if now - last_full_datetime >= timedelta(days=self.full_interval_days):
            return "full"

        return "incremental"

    def _copy_files(
        self,
        backup_dir: Path,
        files: dict[str, dict],
        selected_paths: list[str],
    ) -> int:
        total_bytes = 0

        for archive_path in selected_paths:
            metadata = files[archive_path]

            source_root = self.sources[metadata["source_name"]]

            source_path = source_root / metadata["relative_path"]

            destination = backup_dir / "files" / archive_path

            destination.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            shutil.copy2(
                source_path,
                destination,
            )

            total_bytes += metadata["size_bytes"]

        return total_bytes

    def _apply_retention(
        self,
        now: datetime,
        current_backup_id: str,
        latest_full_id: str | None,
    ) -> list[str]:
        cutoff = now - timedelta(days=self.retention_days)

        removed: list[str] = []

        for backup_type in ("full", "incremental"):
            type_dir = self.backup_root / backup_type

            if not type_dir.exists():
                continue

            for backup_dir in type_dir.iterdir():
                if not backup_dir.is_dir():
                    continue

                if backup_dir.name == current_backup_id:
                    continue

                if backup_dir.name == latest_full_id:
                    continue

                manifest_path = backup_dir / "manifest.json"

                if not manifest_path.exists():
                    continue

                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

                created_at = datetime.fromisoformat(manifest["created_at"])

                if created_at >= cutoff:
                    continue

                shutil.rmtree(backup_dir)

                removed.append(f"{backup_type}/{backup_dir.name}")

        return removed

    def create_backup(
        self,
        mode: BackupMode = "auto",
    ) -> dict:
        now = datetime.now(UTC)

        backup_id = now.strftime("%Y%m%dT%H%M%S%fZ")

        state = self._load_state()

        current_files, missing_sources = self._discover_files()

        backup_type = self._select_mode(
            mode,
            state,
            now,
        )

        previous_files = state.get(
            "files",
            {},
        )

        if backup_type == "full":
            selected_paths = sorted(current_files)

            deleted_files: list[str] = []

        else:
            selected_paths = sorted(
                path
                for path, metadata in current_files.items()
                if (
                    path not in previous_files
                    or previous_files[path]["sha256"] != metadata["sha256"]
                )
            )

            deleted_files = sorted(set(previous_files) - set(current_files))

        backup_dir = self.backup_root / backup_type / backup_id

        backup_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        total_bytes = self._copy_files(
            backup_dir,
            current_files,
            selected_paths,
        )

        last_full_id = state.get("last_full_id")

        last_full_at = state.get("last_full_at")

        if backup_type == "full":
            last_full_id = backup_id
            last_full_at = now.isoformat()

        new_state = {
            "last_backup_id": backup_id,
            "last_backup_type": backup_type,
            "last_backup_at": now.isoformat(),
            "last_full_id": last_full_id,
            "last_full_at": last_full_at,
            "files": current_files,
        }

        self._write_json(
            self.state_file,
            new_state,
        )

        retention_removed = self._apply_retention(
            now=now,
            current_backup_id=backup_id,
            latest_full_id=last_full_id,
        )

        manifest = {
            "status": "success",
            "backup_id": backup_id,
            "backup_type": backup_type,
            "created_at": now.isoformat(),
            "retention_days": self.retention_days,
            "full_interval_days": (self.full_interval_days),
            "file_count": len(selected_paths),
            "total_bytes": total_bytes,
            "deleted_files": deleted_files,
            "missing_sources": missing_sources,
            "retention_removed": retention_removed,
            "files": [
                {
                    "archive_path": path,
                    **current_files[path],
                }
                for path in selected_paths
            ],
        }

        self._write_json(
            backup_dir / "manifest.json",
            manifest,
        )

        return manifest
