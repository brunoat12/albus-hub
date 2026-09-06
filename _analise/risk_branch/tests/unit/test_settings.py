from __future__ import annotations

from pathlib import Path

from albus_hub.config import PROJECT_ROOT, get_settings


def test_project_root_contains_pyproject() -> None:
    """A raiz calculada deve conter o pyproject.toml."""
    assert (PROJECT_ROOT / "pyproject.toml").is_file()


def test_default_cloud_provider() -> None:
    """O ambiente inicial deve utilizar armazenamento local."""
    settings = get_settings()

    assert settings.cloud_provider == "local"


def test_relative_path_is_resolved_from_project_root() -> None:
    """Caminhos relativos devem partir da raiz do projeto."""
    settings = get_settings()

    result = settings.absolute_path(settings.data_raw_path)

    assert result == PROJECT_ROOT / "data/raw"


def test_create_local_directories(tmp_path: Path) -> None:
    """Todas as pastas configuradas devem ser criadas sem erro."""
    settings = get_settings().model_copy(
        update={
            "data_raw_path": tmp_path / "raw",
            "data_rejected_path": tmp_path / "rejected",
            "data_bronze_path": tmp_path / "bronze",
            "data_silver_path": tmp_path / "silver",
            "data_gold_path": tmp_path / "gold",
            "data_sample_path": tmp_path / "sample",
            "data_backup_path": tmp_path / "backups",
            "model_volume_path": tmp_path / "models" / "volume",
            "model_risk_path": tmp_path / "models" / "risk",
            "artifact_path": tmp_path / "artifacts",
        }
    )

    settings.create_local_directories()

    expected_directories = [
        settings.data_raw_path,
        settings.data_rejected_path,
        settings.data_bronze_path,
        settings.data_silver_path,
        settings.data_gold_path,
        settings.data_sample_path,
        settings.data_backup_path,
        settings.model_volume_path,
        settings.model_risk_path,
        settings.artifact_path,
    ]

    for directory in expected_directories:
        assert directory.is_dir()
