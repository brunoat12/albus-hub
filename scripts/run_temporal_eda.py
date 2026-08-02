from __future__ import annotations

import json

from albus_hub.analysis.temporal_eda import (
    run_temporal_eda,
)
from albus_hub.config import get_settings


def main() -> None:
    """Executa a análise exploratória temporal."""
    settings = get_settings()

    report = run_temporal_eda(
        daily_volume_path=settings.absolute_path(settings.locaweb_gold_daily_volume_file),
        output_dir=settings.absolute_path(settings.locaweb_temporal_eda_output_dir),
        report_path=settings.absolute_path(settings.locaweb_temporal_eda_report),
    )

    print(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
