from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    Column,
    DateTime,
    Engine,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    insert,
    select,
    text,
)
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

    def fetch_incident_summary(self) -> IncidentSummary:
        """Consulta e processa o volume de incidentes persistidos."""

        statement = text(
            """
            SELECT COUNT(*) AS total_incidents
            FROM incidents_trusted
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
