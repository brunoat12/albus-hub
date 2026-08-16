from __future__ import annotations

import os
from pathlib import Path, PurePosixPath

from azure.core.exceptions import ResourceExistsError
from azure.identity import DefaultAzureCredential
from azure.storage.filedatalake import (
    DataLakeServiceClient,
    FileSystemClient,
)


def get_datalake_service_client() -> DataLakeServiceClient:
    account_name = os.getenv(
        "AZURE_STORAGE_ACCOUNT_NAME"
    )

    if not account_name:
        raise RuntimeError(
            "AZURE_STORAGE_ACCOUNT_NAME não está configurada."
        )

    account_url = (
        f"https://{account_name}.dfs.core.windows.net"
    )

    credential = DefaultAzureCredential()

    return DataLakeServiceClient(
        account_url=account_url,
        credential=credential,
    )


def get_file_system_client(
    file_system: str,
) -> FileSystemClient:
    service_client = get_datalake_service_client()

    return service_client.get_file_system_client(
        file_system=file_system
    )


def ensure_directory(
    file_system_client: FileSystemClient,
    directory_path: str,
) -> None:
    current_path = ""

    for part in PurePosixPath(
        directory_path
    ).parts:
        current_path = (
            f"{current_path}/{part}"
            if current_path
            else part
        )

        try:
            file_system_client.create_directory(
                current_path
            )
        except ResourceExistsError:
            pass


def upload_file(
    local_path: Path,
    file_system: str,
    remote_path: str,
) -> str:
    if not local_path.exists():
        raise FileNotFoundError(
            f"Arquivo local não encontrado: {local_path}"
        )

    fs_client = get_file_system_client(
        file_system
    )

    remote = PurePosixPath(
        remote_path
    )

    parent = str(
        remote.parent
    )

    if parent != ".":
        ensure_directory(
            fs_client,
            parent,
        )

    file_client = fs_client.get_file_client(
        remote_path
    )

    with local_path.open("rb") as data:
        file_client.upload_data(
            data,
            overwrite=True,
        )

    return remote_path


def download_file(
    file_system: str,
    remote_path: str,
    local_path: Path,
) -> Path:
    fs_client = get_file_system_client(
        file_system
    )

    file_client = fs_client.get_file_client(
        remote_path
    )

    download = file_client.download_file()

    local_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    local_path.write_bytes(
        download.readall()
    )

    return local_path


def delete_file(
    file_system: str,
    remote_path: str,
) -> None:
    fs_client = get_file_system_client(
        file_system
    )

    file_client = fs_client.get_file_client(
        remote_path
    )

    file_client.delete_file()