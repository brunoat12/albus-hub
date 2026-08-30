from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Engine,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    create_engine,
    delete,
    func,
    insert,
    select,
    text,
)
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.engine import URL

from albus_hub.config.settings import Settings

metadata = MetaData()

app_runs_table = Table(
    "albus_app_runs",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("run_id", String(36), nullable=False, unique=True),
    Column("app_env", String(32), nullable=False),
    Column("action", String(64), nullable=False),
    Column("processed_records", Integer, nullable=False, default=0),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

ml_volume_predictions_current_table = Table(
    "ml_volume_predictions_current",
    metadata,
    Column(
        "priority_scope",
        String(16),
        primary_key=True,
    ),
    Column(
        "horizon",
        String(8),
        primary_key=True,
    ),
    Column(
        "reference_date",
        DateTime(),
        nullable=False,
    ),
    Column(
        "predicted_incident_count",
        Numeric(12, 2),
        nullable=False,
    ),
    Column(
        "lower_bound",
        Numeric(12, 2),
        nullable=True,
    ),
    Column(
        "upper_bound",
        Numeric(12, 2),
        nullable=True,
    ),
    Column(
        "model_name",
        String(64),
        nullable=True,
    ),
    Column(
        "generated_at",
        DateTime(),
        nullable=False,
    ),
    Column(
        "model_version",
        String(128),
        nullable=False,
    ),
    Column(
        "updated_at",
        DateTime(),
        nullable=False,
    ),
)

app_daily_incident_volume_table = Table(
    "app_daily_incident_volume",
    metadata,
    Column(
        "reference_date",
        Date,
        primary_key=True,
    ),
    Column(
        "priority_scope",
        String(16),
        primary_key=True,
    ),
    Column(
        "incident_count",
        Integer,
        nullable=False,
    ),
    Column(
        "entered_kpi_count",
        Integer,
        nullable=False,
    ),
    Column(
        "kpi_breach_count",
        Integer,
        nullable=False,
    ),
    Column(
        "monitoring_incident_count",
        Integer,
        nullable=False,
    ),
    Column(
        "no_intervention_count",
        Integer,
        nullable=False,
    ),
)


app_daily_incident_breakdown_table = Table(
    "app_daily_incident_breakdown",
    metadata,
    Column(
        "id",
        Integer,
        primary_key=True,
        autoincrement=True,
    ),
    Column(
        "reference_date",
        Date,
        nullable=False,
    ),
    Column(
        "dimension_name",
        String(64),
        nullable=False,
    ),
    Column(
        "dimension_value",
        String(255),
        nullable=False,
    ),
    Column(
        "priority_scope",
        String(16),
        nullable=False,
    ),
    Column(
        "incident_count",
        Integer,
        nullable=False,
    ),
    Column(
        "entered_kpi_count",
        Integer,
        nullable=False,
    ),
    Column(
        "kpi_breach_count",
        Integer,
        nullable=False,
    ),
)


Index(
    "ix_app_breakdown_filters",
    app_daily_incident_breakdown_table.c.reference_date,
    app_daily_incident_breakdown_table.c.priority_scope,
    app_daily_incident_breakdown_table.c.dimension_name,
)

@dataclass(frozen=True)
class IncidentSummary:
    """Resumo calculado a partir dos incidentes persistidos."""

    total_incidents: int


def build_mysql_url(settings: Settings) -> URL:
    """Monta a URL SQLAlchemy para MySQL."""

    return URL.create(
        drivername="mysql+pymysql",
        username=settings.mysql_user,
        password=settings.mysql_password,
        host=settings.mysql_host,
        port=settings.mysql_port,
        database=settings.mysql_db,
        query={"charset": "utf8mb4"},
    )


def _build_connect_args(settings: Settings) -> dict[str, Any]:
    connect_args: dict[str, Any] = {
        "connect_timeout": settings.mysql_connect_timeout,
    }

    if settings.mysql_ssl_ca is not None:
        ssl_ca = Path(settings.mysql_ssl_ca)

        if not ssl_ca.is_absolute():
            ssl_ca = settings.absolute_path(ssl_ca)

        connect_args["ssl"] = {
            "ca": str(ssl_ca),
        }

    return connect_args


def create_mysql_engine(settings: Settings) -> Engine:
    """Cria uma engine SQLAlchemy para MySQL."""

    return create_engine(
        build_mysql_url(settings),
        pool_pre_ping=True,
        connect_args=_build_connect_args(settings),
    )


class MySQLRepository:
    """Operações usadas pelo Albus-Hub no Azure MySQL."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def health_check(self) -> bool:
        """Valida a comunicação da aplicação com o banco."""

        with self.engine.connect() as connection:
            result = connection.execute(text("SELECT 1")).scalar_one()

        return result == 1

    def ensure_app_runs_table(self) -> None:
        """Cria a tabela de auditoria da aplicação quando necessário."""

        metadata.create_all(
            self.engine,
            tables=[app_runs_table],
        )

    def ensure_ml_volume_predictions_table(
        self,
    ) -> None:
        """Cria a tabela operacional de previsões vigentes."""

        metadata.create_all(
            self.engine,
            tables=[
                ml_volume_predictions_current_table
            ],
        )

        # create_all não altera tabelas existentes.
        # Em MySQL, adicionamos de forma idempotente
        # as colunas introduzidas pelo ML v3.2.
        if self.engine.dialect.name == "mysql":
            with self.engine.begin() as connection:
                existing_columns = {
                    row["Field"]
                    for row in connection.execute(
                        text(
                            "SHOW COLUMNS FROM "
                            "ml_volume_predictions_current"
                        )
                    ).mappings()
                }

                migrations = {
                    "lower_bound": (
                        "ALTER TABLE "
                        "ml_volume_predictions_current "
                        "ADD COLUMN lower_bound "
                        "DECIMAL(12,2) NULL "
                        "AFTER predicted_incident_count"
                    ),
                    "upper_bound": (
                        "ALTER TABLE "
                        "ml_volume_predictions_current "
                        "ADD COLUMN upper_bound "
                        "DECIMAL(12,2) NULL "
                        "AFTER lower_bound"
                    ),
                    "model_name": (
                        "ALTER TABLE "
                        "ml_volume_predictions_current "
                        "ADD COLUMN model_name "
                        "VARCHAR(64) NULL "
                        "AFTER upper_bound"
                    ),
                }

                for column, ddl in migrations.items():
                    if column not in existing_columns:
                        connection.execute(text(ddl))

    def ensure_dashboard_serving_tables(
        self,
    ) -> None:
        """Cria as tabelas serving usadas pelo dashboard."""

        metadata.create_all(
            self.engine,
            tables=[
                app_daily_incident_volume_table,
                app_daily_incident_breakdown_table,
            ],
        )

    def replace_daily_incident_volume(
        self,
        rows: list[dict[str, Any]],
    ) -> None:
        """Substitui o Gold de volume diário no serving."""

        with self.engine.begin() as connection:
            connection.execute(
                delete(
                    app_daily_incident_volume_table
                )
            )

            if rows:
                connection.execute(
                    insert(
                        app_daily_incident_volume_table
                    ),
                    rows,
                )

    def replace_daily_incident_breakdown(
        self,
        rows: list[dict[str, Any]],
        *,
        chunk_size: int = 5000,
    ) -> None:
        """Substitui o Gold de breakdown no serving."""

        with self.engine.begin() as connection:
            connection.execute(
                delete(
                    app_daily_incident_breakdown_table
                )
            )

            for start in range(
                0,
                len(rows),
                chunk_size,
            ):
                chunk = rows[
                    start : start + chunk_size
                ]

                connection.execute(
                    insert(
                        app_daily_incident_breakdown_table
                    ),
                    chunk,
                )

    def upsert_ml_volume_predictions(
        self,
        rows: list[dict[str, Any]],
    ) -> None:
        """
        Persiste a previsão vigente.

        A chave priority_scope + horizon garante
        apenas uma previsão atual por combinação.
        """
        if not rows:
            return

        now = datetime.now(UTC).replace(
            tzinfo=None
        )

        normalized_rows = [
            {
                **row,
                "updated_at": now,
            }
            for row in rows
        ]

        statement = mysql_insert(
            ml_volume_predictions_current_table
        ).values(
            normalized_rows
        )

        statement = statement.on_duplicate_key_update(
            reference_date=statement.inserted.reference_date,
            predicted_incident_count=(
                statement.inserted.predicted_incident_count
            ),
            lower_bound=statement.inserted.lower_bound,
            upper_bound=statement.inserted.upper_bound,
            model_name=statement.inserted.model_name,
            generated_at=statement.inserted.generated_at,
            model_version=statement.inserted.model_version,
            updated_at=statement.inserted.updated_at,
        )

        with self.engine.begin() as connection:
            connection.execute(statement)

    def fetch_ml_volume_predictions(
        self,
    ) -> list[dict[str, Any]]:
        """Retorna todas as previsões operacionais vigentes."""

        statement = (
            select(
                ml_volume_predictions_current_table.c.priority_scope,
                ml_volume_predictions_current_table.c.horizon,
                ml_volume_predictions_current_table.c.reference_date,
                ml_volume_predictions_current_table.c.predicted_incident_count,
                ml_volume_predictions_current_table.c.lower_bound,
                ml_volume_predictions_current_table.c.upper_bound,
                ml_volume_predictions_current_table.c.model_name,
                ml_volume_predictions_current_table.c.generated_at,
                ml_volume_predictions_current_table.c.model_version,
                ml_volume_predictions_current_table.c.updated_at,
            )
            .order_by(
                ml_volume_predictions_current_table.c.priority_scope,
                ml_volume_predictions_current_table.c.horizon,
            )
        )

        with self.engine.connect() as connection:
            rows = (
                connection.execute(
                    statement
                )
                .mappings()
                .all()
            )

        return [
            dict(row)
            for row in rows
        ]

    def fetch_daily_incident_volume(
        self,
    ) -> list[dict[str, Any]]:
        """Retorna o Gold diário utilizado pelo dashboard."""

        statement = select(
            app_daily_incident_volume_table
        ).order_by(
            app_daily_incident_volume_table.c.reference_date,
            app_daily_incident_volume_table.c.priority_scope,
        )

        with self.engine.connect() as connection:
            return [
                dict(row)
                for row in connection.execute(
                    statement
                ).mappings()
            ]

    def fetch_incident_breakdown_ranking(
        self,
        *,
        start_date: date,
        end_date: date,
        priority_scope: str,
        dimension_name: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Retorna ranking operacional agregado pelo MySQL."""

        incident_sum = func.sum(
            app_daily_incident_breakdown_table.c.incident_count
        )

        entered_kpi_sum = func.sum(
            app_daily_incident_breakdown_table.c.entered_kpi_count
        )

        breach_sum = func.sum(
            app_daily_incident_breakdown_table.c.kpi_breach_count
        )

        statement = (
            select(
                app_daily_incident_breakdown_table.c.dimension_value,
                incident_sum.label(
                    "incident_count"
                ),
                entered_kpi_sum.label(
                    "entered_kpi_count"
                ),
                breach_sum.label(
                    "kpi_breach_count"
                ),
            )
            .where(
                app_daily_incident_breakdown_table.c.reference_date.between(
                    start_date,
                    end_date,
                ),
                app_daily_incident_breakdown_table.c.priority_scope
                == priority_scope,
                app_daily_incident_breakdown_table.c.dimension_name
                == dimension_name,
            )
            .group_by(
                app_daily_incident_breakdown_table.c.dimension_value
            )
            .order_by(
                incident_sum.desc()
            )
            .limit(limit)
        )

        with self.engine.connect() as connection:
            return [
                dict(row)
                for row in connection.execute(
                    statement
                ).mappings()
            ]

    def fetch_incident_summary(self) -> IncidentSummary:
        """Consulta e processa o volume de incidentes persistidos."""

        statement = text(
            """
            SELECT COUNT(*) AS total_incidents
            FROM fato_incidente
            """
        )

        with self.engine.connect() as connection:
            total_incidents = int(connection.execute(statement).scalar_one())

        return IncidentSummary(total_incidents=total_incidents)

    def insert_app_run(
        self,
        *,
        app_env: str,
        action: str,
        processed_records: int,
    ) -> str:
        """Registra uma execução produzida pela aplicação."""

        run_id = str(uuid4())

        statement = insert(app_runs_table).values(
            run_id=run_id,
            app_env=app_env,
            action=action,
            processed_records=processed_records,
            created_at=datetime.now(UTC),
        )

        with self.engine.begin() as connection:
            connection.execute(statement)

        return run_id

    def fetch_recent_app_runs(
        self,
        *,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Consulta as execuções recentes registradas pela aplicação."""

        statement = (
            select(
                app_runs_table.c.run_id,
                app_runs_table.c.app_env,
                app_runs_table.c.action,
                app_runs_table.c.processed_records,
                app_runs_table.c.created_at,
            )
            .order_by(app_runs_table.c.created_at.desc())
            .limit(limit)
        )

        with self.engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()

        return [dict(row) for row in rows]
