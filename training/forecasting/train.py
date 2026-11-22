"""Train and register the demand forecasting baseline."""

from __future__ import annotations

import json

from src.common.db import SessionLocal, init_db
from src.common.logging import get_logger
from src.forecasting import service as forecast_service

log = get_logger("training.forecast")


def main() -> None:
    init_db()
    with SessionLocal() as session:
        model = forecast_service.train(session)
    print(json.dumps({"model": model.name, "version": model.version, "metrics": model.metrics}, indent=2))


if __name__ == "__main__":
    main()
