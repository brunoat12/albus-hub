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

    data_backup_path: Path = Path("data/backups")
    backup_retention_days: int = 30
    backup_full_interval_days: int = 7

    model_volume_path: Path = Path("models/volume")
    model_risk_path: Path = Path("models/risk")
    artifact_path: Path = Path("artifacts")

    locaweb_source_file: Path = Path("data/raw/locaweb/LW-DATASET.xlsx")
    locaweb_sheet_name: str = "Dataset Geral"
    locaweb_bronze_file: Path = Path("data/bronze/locaweb_incidents.parquet")
    locaweb_silver_file: Path = Path("data/silver/locaweb_incidents.parquet")
    locaweb_quality_report: Path = Path("artifacts/quality/locaweb_quality_report.json")
    locaweb_gold_daily_volume_file: Path = Path("data/gold/daily_incident_volume.parquet")
    locaweb_gold_daily_breakdown_file: Path = Path("data/gold/daily_incident_breakdown.parquet")
    locaweb_gold_daily_volume_report: Path = Path(
        "artifacts/quality/locaweb_daily_volume_report.json"
    )

    locaweb_temporal_eda_output_dir: Path = Path("artifacts/eda/locaweb")
    locaweb_temporal_eda_report: Path = Path("artifacts/eda/locaweb/temporal_eda_report.json")

    postgres_user: str = "albus"
    postgres_password: str = "albus_local"
    postgres_db: str = "albus_hub"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    database_url: str = "postgresql+psycopg://albus:albus_local@localhost:5432/albus_hub"

    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = "albus"
    mysql_password: str = "albus_local"
    mysql_db: str = "albus_hub"
    mysql_ssl_ca: Path | None = None
    mysql_connect_timeout: int = 10

    rabbitmq_host: str = "localhost"
    rabbitmq_port: int = 5672
    rabbitmq_management_port: int = 15672
    rabbitmq_user: str = "albus"
    rabbitmq_password: str = "albus_local"
    rabbitmq_queue: str = "albus_alerts"
    rabbitmq_url: str = "amqp://albus:albus_local@localhost:5672/"

    locaweb_volume_predictions_file: Path = Path("data/gold/volume_predictions.parquet")
    locaweb_risk_features_file: Path = Path("data/gold/risk_features.parquet")
    locaweb_risk_scores_file: Path = Path("data/gold/risk_scores.parquet")
    locaweb_risk_metrics_file: Path = Path("artifacts/metrics/risk_model_metrics.json")
    locaweb_risk_eda_output_dir: Path = Path("artifacts/eda/risk")

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
            self.data_backup_path,
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
