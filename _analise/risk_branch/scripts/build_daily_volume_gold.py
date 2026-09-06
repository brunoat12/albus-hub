from __future__ import annotations

import json

from albus_hub.config import get_settings
from albus_hub.gold.daily_volume import (
    run_daily_volume_gold,
)


def main() -> None:
    """Executa a construção da Gold diária."""
    settings = get_settings()

    report = run_daily_volume_gold(
        silver_path=settings.absolute_path(settings.locaweb_silver_file),
        daily_volume_path=settings.absolute_path(settings.locaweb_gold_daily_volume_file),
        breakdown_path=settings.absolute_path(settings.locaweb_gold_daily_breakdown_file),
        report_path=settings.absolute_path(settings.locaweb_gold_daily_volume_report),
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
