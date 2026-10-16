"""Convert a monthly official Trends CSV export into the explicit long contract."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tourism_pipeline import CITIES, month, sha256, save_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--city", choices=CITIES, required=True)
    parser.add_argument("--date-column", default="Month")
    parser.add_argument("--skiprows", type=int, default=2)
    parser.add_argument("--complete-through", required=True, help="Last completed month to include, YYYY-MM")
    parser.add_argument(
        "--columns-json", type=Path, required=True, help="Object mapping each term to its exact CSV header"
    )
    parser.add_argument("--out", type=Path, required=True, help="New output directory")
    args = parser.parse_args()
    if args.skiprows < 0:
        raise ValueError("skiprows cannot be negative")
    through = month(args.complete_through)
    current_month = pd.Period(datetime.now(timezone.utc).strftime("%Y-%m"), freq="M")
    if through >= current_month:
        raise ValueError("complete-through must precede the current UTC calendar month")
    columns = json.loads(args.columns_json.read_text(encoding="utf-8"))
    if not columns or len(set(columns.values())) != len(columns):
        raise ValueError("Term mapping must be nonempty and one-to-one")
    raw = pd.read_csv(args.input, skiprows=args.skiprows, dtype="string", keep_default_na=False)
    frames = []
    for term, column in columns.items():
        frames.append(
            pd.DataFrame(
                {
                    "city": args.city,
                    "month": raw[args.date_column].map(lambda x: str(month(x))),
                    "term": term,
                    "value": raw[column],
                    "is_partial": False,
                }
            )
        )
    args.out.mkdir(parents=True, exist_ok=False)
    combined = pd.concat(frames, ignore_index=True)
    included = combined.month.le(str(through))
    combined.loc[included].to_csv(args.out / "trends-long.csv", index=False)
    combined.loc[~included].to_csv(args.out / "excluded-later-months.csv", index=False)
    save_json(
        args.out / "conversion.json",
        {
            "input_sha256": sha256(args.input),
            "mapping": columns,
            "skiprows": args.skiprows,
            "complete_through": str(through),
            "note": "Use completed calendar months only; record export geography, timeframe, category and search type in run config. This conversion does not validate those settings or prove complete months.",
        },
    )


if __name__ == "__main__":
    main()
