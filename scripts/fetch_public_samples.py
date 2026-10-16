"""Bounded official API smoke samples, never a complete 311 population."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tourism_pipeline import clean_requests, sha256, save_json


def get_json(url):
    for attempt in range(3):
        try:
            request = Request(url, headers={"User-Agent": "tourism-311-reproducibility-check/1.0"})
            with urlopen(request, timeout=45) as response:
                payload = response.read()
            return payload, json.loads(payload)
        except Exception:
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    if not 1 <= args.limit <= 1000:
        raise ValueError("limit must be between 1 and 1000")
    args.out.mkdir(parents=True, exist_ok=False)
    save_json(args.out / "status.json", {"state": "incomplete"})
    sources = [
        (
            "Boston",
            "https://data.boston.gov/api/3/action/datastore_search?"
            + urlencode(
                {
                    "resource_id": "dff4d804-5031-443a-8409-8344efd0e5c8",
                    "limit": args.limit,
                    "fields": "case_enquiry_id,open_dt,type",
                    "sort": "_id asc",
                }
            ),
            "case_enquiry_id",
            "open_dt",
            "type",
            "America/New_York",
        ),
        (
            "Seattle",
            "https://data.seattle.gov/resource/5ngg-rpne.json?"
            + urlencode(
                {
                    "$select": "servicerequestnumber,createddate,webintakeservicerequests",
                    "$limit": args.limit,
                    "$where": "createddate >= '2024-01-01T00:00:00' AND createddate < '2025-01-01T00:00:00'",
                    "$order": "createddate,servicerequestnumber",
                }
            ),
            "servicerequestnumber",
            "createddate",
            "webintakeservicerequests",
            "America/Los_Angeles",
        ),
        (
            "Washington DC",
            "https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_DATA/ServiceRequests/FeatureServer/16/query?"
            + urlencode(
                {
                    "where": "1=1",
                    "outFields": "SERVICEREQUESTID,ADDDATE,SERVICECODEDESCRIPTION",
                    "returnGeometry": "false",
                    "resultRecordCount": args.limit,
                    "orderByFields": "OBJECTID ASC",
                    "f": "json",
                }
            ),
            "SERVICEREQUESTID",
            "ADDDATE",
            "SERVICECODEDESCRIPTION",
            "America/New_York",
        ),
    ]
    report = []
    try:
        for city, url, id_col, date_col, type_col, tz in sources:
            slug = city.lower().replace(" ", "-")
            payload, response = get_json(url)
            (args.out / (slug + "-raw.json")).write_bytes(payload)
            if city == "Boston":
                if not response.get("success"):
                    raise ValueError("Boston API did not report success")
                records = response["result"]["records"]
            elif city == "Seattle":
                records = response
            else:
                if "error" in response:
                    raise ValueError(response["error"])
                records = [f["attributes"] for f in response["features"]]
            if not records or len(records) > args.limit:
                raise ValueError("Unexpected API sample size")
            frame = pd.DataFrame(records).reindex(columns=[id_col, date_col, type_col])
            if city == "Washington DC":
                # ArcGIS REST date values are epoch milliseconds. Keep original JSON.
                frame[date_col] = pd.to_datetime(frame[date_col], unit="ms", utc=True).map(lambda x: x.isoformat())
            path = args.out / (slug + ".csv")
            frame.to_csv(path, index=False)
            spec = {
                "city": city,
                "path": path.name,
                "source_url": url,
                "downloaded_at": datetime.now(timezone.utc).isoformat(),
                "id_column": id_col,
                "date_column": date_col,
                "type_column": type_col,
                "timezone": tz,
                "complete_months": [],
            }
            clean, rejected = clean_requests(
                pd.read_csv(path, dtype="string", keep_default_na=False),
                spec,
                pd.period_range("2024-01", "2024-12", freq="M"),
            )
            clean.to_csv(args.out / (slug + "-clean.csv"), index=False)
            rejected.to_csv(args.out / (slug + "-rejected.csv"), index=False)
            report.append(
                {
                    "metadata": spec,
                    "raw_rows": len(frame),
                    "accepted_rows": len(clean),
                    "rejected_rows": len(rejected),
                    "csv_sha256": sha256(path),
                    "raw_json_sha256": sha256(args.out / (slug + "-raw.json")),
                    "scope": "ordered bounded sample; no complete months and no correlation inference",
                }
            )
        save_json(args.out / "source-smoke.json", report)
        save_json(args.out / "status.json", {"state": "complete"})
    except Exception as error:
        save_json(args.out / "status.json", {"state": "failed", "error": str(error)})
        raise
    print("PASS: official API samples parsed; no population or Trends result claimed")


if __name__ == "__main__":
    main()
