from sqlalchemy import create_engine, text

from albus_hub.config.settings import Settings
from albus_hub.storage.mysql import MySQLRepository, build_mysql_url


def test_build_mysql_url() -> None:
    settings = Settings(
        _env_file=None,
        mysql_host="mysql.example.com",
        mysql_port=3306,
        mysql_user="albus_user",
        mysql_password="secret",
        mysql_db="albus_hub",
    )

    url = build_mysql_url(settings)

    assert url.drivername == "mysql+pymysql"
    assert url.username == "albus_user"
    assert url.password == "secret"
    assert url.host == "mysql.example.com"
    assert url.port == 3306
    assert url.database == "albus_hub"
    assert url.query["charset"] == "utf8mb4"


def test_mysql_repository_operations() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE incidents_trusted (
                    incident_id VARCHAR(64)
                )
                """
            )
        )

        connection.execute(
            text(
                """
                INSERT INTO incidents_trusted (incident_id)
                VALUES ('INC-1'), ('INC-2'), ('INC-3')
                """
            )
        )

    repository = MySQLRepository(engine)

    assert repository.health_check() is True

    repository.ensure_app_runs_table()

    summary = repository.fetch_incident_summary()

    assert summary.total_incidents == 3

    run_id = repository.insert_app_run(
        app_env="test",
        action="incident_summary",
        processed_records=summary.total_incidents,
    )

    recent_runs = repository.fetch_recent_app_runs()

    assert len(recent_runs) == 1
    assert recent_runs[0]["run_id"] == run_id
    assert recent_runs[0]["app_env"] == "test"
    assert recent_runs[0]["action"] == "incident_summary"
    assert recent_runs[0]["processed_records"] == 3

    engine.dispose()
