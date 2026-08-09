from __future__ import annotations

from albus_hub.storage.mysql import MySQLRepository, create_mysql_engine

from albus_hub.config.settings import get_settings


def main() -> None:
    settings = get_settings()
    engine = create_mysql_engine(settings)
    repository = MySQLRepository(engine)

    try:
        print("=== ALBUS-HUB MYSQL INTEGRATION ===")

        print(f"health_check={repository.health_check()}")

        repository.ensure_app_runs_table()
        print("app_runs_table=ready")

        summary = repository.fetch_incident_summary()
        print(f"total_incidents={summary.total_incidents}")

        run_id = repository.insert_app_run(
            app_env=settings.app_env,
            action="incident_summary",
            processed_records=summary.total_incidents,
        )

        print(f"inserted_run_id={run_id}")

        recent_runs = repository.fetch_recent_app_runs(limit=5)

        print(f"recent_runs={len(recent_runs)}")

        for run in recent_runs:
            print(
                "run="
                f"{run['run_id']} | "
                f"env={run['app_env']} | "
                f"action={run['action']} | "
                f"processed_records={run['processed_records']}"
            )

        print("MYSQL_INTEGRATION=SUCCESS")

    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
