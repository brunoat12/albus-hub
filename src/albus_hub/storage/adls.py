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
    account_name = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")

    if not account_name:
        raise RuntimeError("AZURE_STORAGE_ACCOUNT_NAME não está configurada.")

    account_url = f"https://{account_name}.dfs.core.windows.net"

    credential = DefaultAzureCredential()

    return DataLakeServiceClient(
        account_url=account_url,
        credential=credential,
    )


def get_file_system_client(
    file_system: str,
) -> FileSystemClient:
    service_client = get_datalake_service_client()

    return service_client.get_file_system_client(file_system=file_system)


def ensure_directory(
    file_system_client: FileSystemClient,
    directory_path: str,
) -> None:
    current_path = ""

    for part in PurePosixPath(directory_path).parts:
        current_path = f"{current_path}/{part}" if current_path else part

        try:
            file_system_client.create_directory(current_path)
        except ResourceExistsError:
            pass


def upload_file(
    local_path: Path,
    file_system: str,
    remote_path: str,
) -> str:
    if not local_path.exists():
        raise FileNotFoundError(f"Arquivo local não encontrado: {local_path}")

    fs_client = get_file_system_client(file_system)

    remote = PurePosixPath(remote_path)

    parent = str(remote.parent)

    if parent != ".":
        ensure_directory(
            fs_client,
            parent,
        )

    file_client = fs_client.get_file_client(remote_path)

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
    fs_client = get_file_system_client(file_system)

    file_client = fs_client.get_file_client(remote_path)

    download = file_client.download_file()

    local_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    local_path.write_bytes(download.readall())

    return local_path


def delete_file(
    file_system: str,
    remote_path: str,
) -> None:
    fs_client = get_file_system_client(file_system)

    file_client = fs_client.get_file_client(remote_path)

    file_client.delete_file()


def list_files(
    file_system: str,
    remote_prefix: str,
) -> list[str]:
    """Lista arquivos existentes abaixo de um caminho no ADLS."""

    fs_client = get_file_system_client(file_system)

    return sorted(
        item.name
        for item in fs_client.get_paths(
            path=remote_prefix,
            recursive=True,
        )
        if not item.is_directory
    )


def sync_directory(
    local_root: Path,
    file_system: str,
    remote_prefix: str,
) -> dict:
    """Publica backups locais no ADLS sem remover arquivos remotos."""

    local_root = local_root.resolve()

    if not local_root.exists():
        raise FileNotFoundError(f"Diretório local não encontrado: {local_root}")

    remote_prefix = remote_prefix.strip("/")

    local_files = sorted(
        path for path in local_root.rglob("*") if path.is_file() and path.name != ".gitkeep"
    )

    uploaded_files = 0
    uploaded_bytes = 0

    for local_path in local_files:
        relative_path = local_path.relative_to(local_root).as_posix()

        remote_path = f"{remote_prefix}/{relative_path}"

        upload_file(
            local_path=local_path,
            file_system=file_system,
            remote_path=remote_path,
        )

        uploaded_files += 1
        uploaded_bytes += local_path.stat().st_size

    return {
        "status": "success",
        "file_system": file_system,
        "remote_prefix": remote_prefix,
        "uploaded_files": uploaded_files,
        "uploaded_bytes": uploaded_bytes,
    }


def download_directory(
    file_system: str,
    remote_prefix: str,
    local_root: Path,
) -> dict:
    """Baixa uma árvore de arquivos do ADLS."""

    import shutil

    local_root = local_root.resolve()

    if local_root.exists():
        shutil.rmtree(local_root)

    local_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    remote_prefix = remote_prefix.strip("/")

    remote_files = list_files(
        file_system=file_system,
        remote_prefix=remote_prefix,
    )

    if not remote_files:
        raise RuntimeError("Nenhum arquivo encontrado no backup do ADLS.")

    downloaded_files = 0
    downloaded_bytes = 0

    prefix_with_slash = f"{remote_prefix}/"

    for remote_path in remote_files:
        if not remote_path.startswith(prefix_with_slash):
            continue

        relative_path = remote_path[len(prefix_with_slash) :]

        local_path = local_root / relative_path

        download_file(
            file_system=file_system,
            remote_path=remote_path,
            local_path=local_path,
        )

        downloaded_files += 1
        downloaded_bytes += local_path.stat().st_size

    return {
        "status": "success",
        "file_system": file_system,
        "remote_prefix": remote_prefix,
        "downloaded_files": downloaded_files,
        "downloaded_bytes": downloaded_bytes,
        "destination": str(local_root),
    }
