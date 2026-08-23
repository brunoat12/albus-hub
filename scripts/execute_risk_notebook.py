from __future__ import annotations

from pathlib import Path

import nbformat
from nbclient import NotebookClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = PROJECT_ROOT / "notebooks" / "EC_Sprint_3_Albus_Hub_DeepL.ipynb"

NOISE_MARKERS = (
    "WARNING: All log messages before absl::InitializeLog()",
    "Could not find cuda drivers",
    "failed call to cuInit",
    "This TensorFlow binary is optimized to use available CPU instructions",
    "To enable the following instructions:",
)


def clean_runtime_noise(notebook) -> None:
    """Remove apenas mensagens ambientais de CUDA/CPU, preservando os resultados."""
    for cell in notebook.cells:
        if cell.cell_type != "code":
            continue

        for output in cell.get("outputs", []):
            if output.output_type != "stream":
                continue

            lines = output.get("text", "").splitlines()
            clean_lines = [
                line
                for line in lines
                if not any(marker in line for marker in NOISE_MARKERS)
            ]

            output["text"] = "\n".join(clean_lines)

            if clean_lines:
                output["text"] += "\n"


def main() -> None:
    notebook = nbformat.read(NOTEBOOK_PATH, as_version=4)

    client = NotebookClient(
        notebook,
        timeout=1200,
        kernel_name="python3",
        resources={"metadata": {"path": str(PROJECT_ROOT)}},
        allow_errors=False,
    )

    client.execute()
    clean_runtime_noise(notebook)

    nbformat.write(notebook, NOTEBOOK_PATH)
    print(f"Notebook executado: {NOTEBOOK_PATH}")


if __name__ == "__main__":
    main()
