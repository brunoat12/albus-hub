from __future__ import annotations

import pika
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from albus_hub.config import Settings, get_settings


def check_postgres(settings: Settings) -> None:
    """Valida a conexão da aplicação com o PostgreSQL."""
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
    )

    try:
        with engine.connect() as connection:
            result = (
                connection.execute(
                    text(
                        """
                    SELECT
                        CURRENT_DATABASE() AS database_name,
                        CURRENT_USER AS database_user,
                        1 AS connection_test
                    """
                    )
                )
                .mappings()
                .one()
            )

        if result["connection_test"] != 1:
            raise RuntimeError("O PostgreSQL retornou um resultado inesperado.")

        print("[OK] PostgreSQL")
        print(f"     Banco: {result['database_name']}")
        print(f"     Usuário: {result['database_user']}")

    except SQLAlchemyError as exc:
        raise RuntimeError(f"Não foi possível conectar ao PostgreSQL: {exc}") from exc

    finally:
        engine.dispose()


def check_rabbitmq(settings: Settings) -> None:
    """Valida a conexão da aplicação com o RabbitMQ."""
    parameters = pika.URLParameters(settings.rabbitmq_url)
    connection = pika.BlockingConnection(parameters)

    try:
        channel = connection.channel()

        queue = channel.queue_declare(
            queue=settings.rabbitmq_queue,
            durable=True,
        )

        print("[OK] RabbitMQ")
        print(f"     Fila: {queue.method.queue}")

    finally:
        connection.close()


def main() -> None:
    """Executa as verificações dos serviços locais."""
    settings = get_settings()

    print("=== Verificação dos serviços Albus-Hub ===")

    check_postgres(settings)
    check_rabbitmq(settings)

    print("=== Serviços locais configurados com sucesso ===")


if __name__ == "__main__":
    main()
