"""Fill data/analytics.jsonl with sample events so the dashboard can be demoed.

    uv run python -m api.seed            # 400 events over the last 30 days
    uv run python -m api.seed --clear    # delete the log instead

Sample events are marked "sample": true so they can be told apart from real traffic.
"""
import json
import random
import sys
import time

from agents.attractions import load_attractions
from api.analytics import LOG_PATH

DESTINATION_WEIGHTS = {"Cairo": 34, "Luxor": 18, "Aswan": 10, "Alexandria": 9, "Red Sea": 8,
                       "South Sinai": 6, "Matrouh": 4, "New Valley": 3, "Dahab": 2}


def main(count: int = 400) -> None:
    rng = random.Random(7)
    by_region = {}
    for a in load_attractions().values():
        key = "Cairo" if a.region in ("Cairo", "Giza") else a.region
        by_region.setdefault(key, []).append(a.id)
    now = time.time()
    names, weights = zip(*DESTINATION_WEIGHTS.items())
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        for _ in range(count):
            destination = rng.choices(names, weights)[0]
            planned = destination in by_region and rng.random() > 0.12
            pool = by_region.get(destination, [])
            ids = rng.sample(pool, k=min(len(pool), rng.randint(2, 6))) if planned else []
            cached = rng.random() < 0.38
            f.write(json.dumps({
                "ts": now - rng.random() * 30 * 86400,
                "ok": True,
                "status": "planned" if planned else ("unsupported_region" if destination == "Dahab"
                                                     else "needs_clarification"),
                "language": "ar" if rng.random() < 0.42 else "en",
                "destination": destination,
                "days": rng.randint(1, 5),
                "attraction_ids": ids,
                "cached": cached,
                "response_ms": rng.randint(8, 40) if cached else rng.randint(1400, 4200),
                "sample": True,
            }) + "\n")
    print(f"Wrote {count} sample events to {LOG_PATH}")


if __name__ == "__main__":
    if "--clear" in sys.argv:
        LOG_PATH.unlink(missing_ok=True)
        print(f"Deleted {LOG_PATH}")
    else:
        main()
