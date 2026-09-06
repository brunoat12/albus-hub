from __future__ import annotations


def test_albus_hub_package_can_be_imported() -> None:
    """O pacote principal deve ser importável."""
    import albus_hub

    assert albus_hub is not None


def test_settings_module_can_be_imported() -> None:
    """O módulo de configurações deve estar disponível."""
    from albus_hub.config import get_settings

    assert get_settings().app_name == "albus-hub"
