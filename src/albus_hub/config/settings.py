from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Configurações centrais do projeto Albus-Hub."""

    app_env: str = "local"
    app_name: str = "albus-hub"
    cloud_provider: str = "local"
    log_level: str = "INFO"

    data_raw_path: Path = Path("data/raw")
    data_rejected_path: Path = Path("data/rejected")
    data_bronze_path: Path = Path("data/bronze")
    data_silver_path: Path = Path("data/silver")
    data_gold_path: Path = Path("data/gold")
    data_sample_path: Path = Path("data/sample")

    model_volume_path: Path = Path("models/volume")
    model_risk_path: Path = Path("models/risk")
    artifact_path: Path = Path("artifacts")

    locaweb_source_file: Path = Path("data/raw/locaweb/LW-DATASET.xlsx")
    locaweb_sheet_name: str = "Dataset Geral"
    locaweb_bronze_file: Path = Path("data/bronze/locaweb_incidents.parquet")
    locaweb_silver_file: Path = Path("data/silver/locaweb_incidents.parquet")
    locaweb_quality_report: Path = Path("artifacts/quality/locaweb_quality_report.json")

    postgres_user: str = "albus"
    postgres_password: str = "albus_local"
    postgres_db: str = "albus_hub"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    database_url: str = "postgresql+psycopg://albus:albus_local@localhost:5432/albus_hub"

    rabbitmq_host: str = "localhost"
    rabbitmq_port: int = 5672
    rabbitmq_management_port: int = 15672
    rabbitmq_user: str = "albus"
    rabbitmq_password: str = "albus_local"
    rabbitmq_queue: str = "albus_alerts"
    rabbitmq_url: str = "amqp://albus:albus_local@localhost:5672/"

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    def absolute_path(self, path: Path) -> Path:
        """Converte um caminho relativo em caminho absoluto do projeto."""
        if path.is_absolute():
            return path

        return PROJECT_ROOT / path

    def create_local_directories(self) -> None:
        """Cria as pastas locais utilizadas pela aplicação."""
        directories = [
            self.data_raw_path,
            self.data_rejected_path,
            self.data_bronze_path,
            self.data_silver_path,
            self.data_gold_path,
            self.data_sample_path,
            self.model_volume_path,
            self.model_risk_path,
            self.artifact_path,
        ]

        for directory in directories:
            self.absolute_path(directory).mkdir(
                parents=True,
                exist_ok=True,
            )


@lru_cache
def get_settings() -> Settings:
    """Retorna uma instância compartilhada das configurações."""
    return Settings()
