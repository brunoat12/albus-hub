from __future__ import annotations

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
