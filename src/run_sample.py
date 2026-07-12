from __future__ import annotations

import json

from .config import DOCS_DIR, load_config
from .dashboard import build_dashboard
from .sample_data import build_sample_payload


def main() -> None:
    config = load_config()
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    latest, history = build_sample_payload(config)

    sample_data_path = DOCS_DIR / "sample-data.json"
    sample_dashboard_path = DOCS_DIR / "sample.html"

    sample_data_path.write_text(
        json.dumps(latest, indent=2),
        encoding="utf-8",
    )
    build_dashboard(latest, history, sample_dashboard_path)

    print(f"Sample dashboard written to {sample_dashboard_path}")


if __name__ == "__main__":
    main()
