from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path


class RestoreService:
    """Restaura o último FULL e aplica incrementais posteriores."""

    def __init__(
        self,
        backup_root: Path,
        destination: Path,
    ) -> None:
        self.backup_root = backup_root.resolve()
        self.destination = destination.resolve()

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()

        with path.open("rb") as file:
            for chunk in iter(
                lambda: file.read(1024 * 1024),
                b"",
            ):
                digest.update(chunk)

        return digest.hexdigest()

    @staticmethod
    def _load_manifest(
        backup_dir: Path,
    ) -> dict:
        manifest_path = backup_dir / "manifest.json"

        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest não encontrado: {manifest_path}")

        return json.loads(manifest_path.read_text(encoding="utf-8"))

    def _backup_dirs(
        self,
        backup_type: str,
    ) -> list[Path]:
        root = self.backup_root / backup_type

        if not root.exists():
            return []

        return sorted(path for path in root.iterdir() if path.is_dir())

    def _latest_full(
        self,
    ) -> tuple[Path, dict]:
        candidates = []

        for backup_dir in self._backup_dirs("full"):
            manifest = self._load_manifest(backup_dir)

            candidates.append(
                (
                    backup_dir,
                    manifest,
                )
            )

        if not candidates:
            raise RuntimeError("Nenhum backup FULL disponível.")

        return max(
            candidates,
            key=lambda item: item[1]["created_at"],
        )

    def _incrementals_after(
        self,
        full_created_at: str,
    ) -> list[tuple[Path, dict]]:
        candidates = []

        for backup_dir in self._backup_dirs("incremental"):
            manifest = self._load_manifest(backup_dir)

            if manifest["created_at"] > full_created_at:
                candidates.append(
                    (
                        backup_dir,
                        manifest,
                    )
                )

        return sorted(
            candidates,
            key=lambda item: item[1]["created_at"],
        )

    def _copy_files(
        self,
        backup_dir: Path,
        manifest: dict,
        expected_state: dict[str, dict],
    ) -> int:
        copied = 0

        for item in manifest["files"]:
            archive_path = item["archive_path"]

            source = backup_dir / "files" / archive_path

            if not source.exists():
                raise FileNotFoundError(f"Arquivo de backup não encontrado: {source}")

            destination = self.destination / archive_path

            destination.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            shutil.copy2(
                source,
                destination,
            )

            expected_state[archive_path] = item

            copied += 1

        return copied

    def restore_latest(self) -> dict:
        if self.destination.exists():
            shutil.rmtree(self.destination)

        self.destination.mkdir(
            parents=True,
            exist_ok=True,
        )

        full_dir, full_manifest = self._latest_full()

        expected_state: dict[
            str,
            dict,
        ] = {}

        files_copied = self._copy_files(
            full_dir,
            full_manifest,
            expected_state,
        )

        applied_incrementals = []
        deleted_files_applied = 0

        incrementals = self._incrementals_after(full_manifest["created_at"])

        for (
            incremental_dir,
            incremental_manifest,
        ) in incrementals:
            files_copied += self._copy_files(
                incremental_dir,
                incremental_manifest,
                expected_state,
            )

            for archive_path in incremental_manifest["deleted_files"]:
                target = self.destination / archive_path

                if target.exists():
                    target.unlink()

                expected_state.pop(
                    archive_path,
                    None,
                )

                deleted_files_applied += 1

            applied_incrementals.append(incremental_manifest["backup_id"])

        integrity_failures = []

        for (
            archive_path,
            metadata,
        ) in expected_state.items():
            restored_path = self.destination / archive_path

            if not restored_path.exists():
                integrity_failures.append(
                    {
                        "archive_path": archive_path,
                        "reason": "missing",
                    }
                )
                continue

            actual_sha256 = self._sha256(restored_path)

            expected_sha256 = metadata["sha256"]

            if actual_sha256 != expected_sha256:
                integrity_failures.append(
                    {
                        "archive_path": archive_path,
                        "reason": "checksum_mismatch",
                        "expected_sha256": expected_sha256,
                        "actual_sha256": actual_sha256,
                    }
                )

        status = "success" if not integrity_failures else "failed"

        return {
            "status": status,
            "full_backup_id": (full_manifest["backup_id"]),
            "incrementals_applied": (applied_incrementals),
            "incremental_count": len(applied_incrementals),
            "files_copied": files_copied,
            "final_file_count": len(expected_state),
            "deleted_files_applied": (deleted_files_applied),
            "integrity_checked": len(expected_state),
            "integrity_failures": (integrity_failures),
            "destination": str(self.destination),
        }
