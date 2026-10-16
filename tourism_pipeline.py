"""Explicit snapshot-based 311/search-interest analysis; no implicit network calls."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import re

import numpy as np
import pandas as pd

CITIES = ("Boston", "Seattle", "Washington DC")
RULES = {
    "explicit_visitor_terms": r"\b(?:tourists?|visitors?|tour\s*(?:bus|group)|hotels?|motels?|airbnb|short[ -]?term[ -]?rental|vacation[ -]?rental)\b",
    "broad_service_terms": r"\b(?:noise|loud|party|music|concert|crowd|litter|trash|garbage|rats?|sanitation|parking|traffic|congestion|festival|parade|beach|airport|aircraft)\b",
}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def month(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-(?:0[1-9]|1[0-2])", value):
        raise ValueError(f"Expected monthly YYYY-MM value, got {value!r}")
    return pd.Period(value, freq="M")


def snapshot_metadata(spec):
    for key in ["city", "path", "source_url", "downloaded_at"]:
        if not isinstance(spec.get(key), str) or not spec[key].strip():
            raise ValueError(f"Snapshot metadata requires {key}")
    if spec["city"] not in CITIES:
        raise ValueError("Unknown city")
    stamp = pd.Timestamp(spec["downloaded_at"])
    if stamp.tzinfo is None:
        raise ValueError("downloaded_at requires an explicit time zone")


def load_config(path):
    path = Path(path).resolve()
    config = json.loads(path.read_text(encoding="utf-8"))
    start, end = month(config["analysis_start"]), month(config["analysis_end"])
    if end <= start:
        raise ValueError("analysis_end must be after analysis_start (exclusive)")
    if type(config.get("is_fixture")) is not bool:
        raise ValueError("is_fixture must explicitly be true or false")
    if config.get("keyword_rule", "broad_service_terms") not in RULES:
        raise ValueError("Unknown keyword rule")
    for kind in ["requests", "trends"]:
        if not config.get(kind):
            raise ValueError(f"No {kind} snapshots")
        for spec in config[kind]:
            snapshot_metadata(spec)
        if {s["city"] for s in config[kind]} != set(CITIES):
            raise ValueError(f"{kind} must explicitly supply all three cities")
    if len(config["trends"]) != len(CITIES):
        raise ValueError("Supply one combined canonical trends file per city")
    for city in CITIES:
        terms = config["expected_terms"].get(city)
        if not terms or len(terms) != len(set(terms)) or any(not isinstance(t, str) or not t.strip() for t in terms):
            raise ValueError("Expected terms must be nonempty and distinct for every city")
    return config, path.parent, pd.period_range(start, end - 1, freq="M")


def parse_local_timestamp(value, tz):
    if pd.isna(value) or not str(value).strip():
        return pd.NaT
    try:
        # Numeric epoch timestamps require explicit upstream conversion, not guessing.
        if re.fullmatch(r"\d+(?:\.\d+)?", str(value).strip()):
            return pd.NaT
        stamp = pd.Timestamp(value)
        if stamp.tzinfo is None:
            return stamp.tz_localize(tz, ambiguous="NaT", nonexistent="NaT")
        return stamp.tz_convert(tz)
    except (ValueError, TypeError, OverflowError):
        return pd.NaT


def clean_requests(raw, spec, months):
    fields = [spec[key] for key in ["id_column", "date_column", "type_column"]]
    missing = set(fields) - set(raw.columns)
    if missing:
        raise ValueError(f"{spec['city']} missing columns {sorted(missing)}")
    # Validate the configured timezone even if every input date is invalid.
    pd.Timestamp("2024-01-01").tz_localize(spec["timezone"])
    data = pd.DataFrame(
        {
            "request_id": raw[fields[0]].astype("string").str.strip(),
            "raw_date": raw[fields[1]].astype("string"),
            "complaint_type": raw[fields[2]].astype("string").fillna("").str.strip(),
        }
    )
    stamps = data.raw_date.map(lambda x: parse_local_timestamp(x, spec["timezone"]))
    data["local_timestamp"] = stamps.map(lambda x: x.isoformat() if not pd.isna(x) else "")
    data["month"] = stamps.map(lambda x: str(x.tz_localize(None).to_period("M")) if not pd.isna(x) else "")
    data["city"] = spec["city"]
    data["source_file"] = spec["path"]
    data["source_row"] = np.arange(len(raw)) + 2
    data["reason"] = ""
    data.loc[data.request_id.isna() | data.request_id.eq(""), "reason"] = "missing_request_id"
    data.loc[data.reason.eq("") & data.local_timestamp.eq(""), "reason"] = "invalid_or_ambiguous_date"
    data.loc[data.reason.eq("") & ~data.month.isin([str(m) for m in months]), "reason"] = "outside_analysis_window"
    return data.loc[data.reason.eq("")].drop(columns="reason"), data.loc[data.reason.ne("")]


def deduplicate_requests(data):
    keys = ["city", "request_id"]
    grouped = data.groupby(keys, dropna=False)[["local_timestamp", "complaint_type"]].nunique(dropna=False)
    if grouped.gt(1).any(axis=None):
        raise ValueError("Conflicting records for the same city/request_id; resolve source snapshots explicitly")
    duplicate_rows = data.loc[data.duplicated(keys, keep="first")].copy()
    return data.drop_duplicates(keys, keep="first").copy(), duplicate_rows


def aggregate_requests(data, specs, months, rule):
    result = data.copy()
    result["keyword_match"] = result.complaint_type.str.contains(RULES[rule], case=False, regex=True, na=False)
    result["type_unknown"] = result.complaint_type.eq("")
    grouped = (
        result.groupby(["city", "month"])
        .agg(
            n_requests=("request_id", "size"),
            n_keyword_matches=("keyword_match", "sum"),
            n_unknown_type=("type_unknown", "sum"),
        )
        .reset_index()
    )
    grid = pd.MultiIndex.from_product([CITIES, [str(m) for m in months]], names=["city", "month"]).to_frame(index=False)
    monthly = grid.merge(grouped, on=["city", "month"], how="left", validate="one_to_one")
    declared = set()
    for spec in specs:
        if not isinstance(spec.get("complete_months"), list):
            raise ValueError("Every 311 snapshot must declare complete_months; use [] for samples/unverified coverage")
        for value in spec["complete_months"]:
            declared.add((spec["city"], str(month(value))))
    monthly["request_coverage_complete"] = [(c, m) in declared for c, m in zip(monthly.city, monthly.month)]
    for col in ["n_requests", "n_keyword_matches", "n_unknown_type"]:
        # Only a declared complete source can turn absence into an observed zero.
        monthly.loc[monthly.request_coverage_complete & monthly[col].isna(), col] = 0
        monthly[col] = monthly[col].astype("Int64")
    monthly["keyword_request_share"] = monthly.n_keyword_matches / monthly.n_requests.replace(0, pd.NA)
    return result, monthly


def parse_partial(value):
    text = str(value).strip().casefold()
    if text in ["true", "1"]:
        return True
    if text in ["false", "0"]:
        return False
    raise ValueError(f"is_partial must explicitly be true/false, got {value!r}")


def clean_trends(raw, spec, expected_terms):
    required = {"city", "month", "term", "value", "is_partial"}
    if not required <= set(raw.columns):
        raise ValueError(f"Trends CSV requires {sorted(required)}")
    for key in ["geography", "timeframe", "category", "search_type", "normalization"]:
        if not isinstance(spec.get(key), str) or not spec[key].strip():
            raise ValueError(f"Trends metadata requires {key}")
    if spec["normalization"] != "relative_0_100_within_export":
        raise ValueError("Unsupported Trends normalization")
    data = raw[list(sorted(required))].copy()
    if data.city.isna().any() or not data.city.eq(spec["city"]).all():
        raise ValueError("Trends city does not match its source declaration")
    data["month"] = data.month.map(lambda x: str(month(x)))
    if data.term.isna().any() or not data.term.isin(expected_terms).all():
        raise ValueError("Unexpected/missing search term")
    if data.duplicated(["city", "month", "term"]).any():
        raise ValueError("Duplicate city/month/term in Trends input")
    data["is_partial"] = data.is_partial.map(parse_partial).astype(bool)
    tokens = data.value.astype("string").str.strip()
    data["is_censored"] = tokens.eq("<1").fillna(False)
    values = pd.to_numeric(tokens.mask(data.is_censored), errors="coerce")
    malformed = tokens.notna() & tokens.ne("") & ~data.is_censored & values.isna()
    if malformed.any() or (values.notna() & ~np.isfinite(values.astype(float))).any():
        raise ValueError("Malformed/nonfinite Trends values")
    if (values.notna() & ~values.between(0, 100)).any():
        raise ValueError("Trends values must be between 0 and 100")
    data["value"] = values.astype("Float64")
    data["usable"] = ~data.is_partial & ~data.is_censored & data.value.notna()
    return data


def aggregate_trends(data, expected_terms, months):
    rows = []
    for city in CITIES:
        for period in months:
            group = data.loc[data.city.eq(city) & data.month.eq(str(period))]
            usable = group.loc[group.usable]
            complete = len(usable) == len(expected_terms[city])
            rows.append(
                {
                    "city": city,
                    "month": str(period),
                    "n_terms_available": len(usable),
                    "n_terms_expected": len(expected_terms[city]),
                    "trends_complete": complete,
                    "n_partial_terms": int(group.is_partial.sum()),
                    "n_censored_terms": int(group.is_censored.sum()),
                    "search_interest_index": float(usable.value.mean()) if complete else np.nan,
                }
            )
    return pd.DataFrame(rows)


def merge_monthly(requests, trends):
    keys = ["city", "month"]
    for name, table in [("311", requests), ("Trends", trends)]:
        if table[keys].isna().any(axis=None) or table.duplicated(keys).any():
            raise ValueError(f"{name} city/month keys must be unique and nonnull")
    combined = requests.merge(trends, on=keys, how="outer", validate="one_to_one", indicator=True)
    combined["eligible"] = (
        combined.request_coverage_complete.fillna(False)
        & combined.trends_complete.fillna(False)
        & combined.keyword_request_share.notna()
    )

    def reason(row):
        issues = []
        if pd.isna(row.request_coverage_complete) or not row.request_coverage_complete:
            issues.append("311_coverage_unverified")
        if pd.isna(row.trends_complete) or not row.trends_complete:
            issues.append("trends_incomplete")
        if pd.isna(row.keyword_request_share):
            issues.append("share_undefined")
        return ";".join(issues) or "eligible"

    combined["coverage_reason"] = combined.apply(reason, axis=1)
    return combined.sort_values(keys).reset_index(drop=True)


def pearson(x, y):
    if len(x) < 3:
        return None, "fewer_than_three_pairs"
    if np.allclose(x, x.iloc[0] if hasattr(x, "iloc") else x[0], rtol=1e-12, atol=1e-12) or np.allclose(
        y, y.iloc[0] if hasattr(y, "iloc") else y[0], rtol=1e-12, atol=1e-12
    ):
        return None, "constant_series"
    return float(np.corrcoef(np.asarray(x, dtype=float), np.asarray(y, dtype=float))[0, 1]), None


def correlations(monthly):
    results = []
    for city in CITIES:
        all_rows = monthly.loc[monthly.city.eq(city)].copy()
        paired = all_rows.loc[all_rows.eligible].sort_values("month").copy()
        x, y = paired.search_interest_index.astype(float), paired.keyword_request_share.astype(float)
        r, reason = pearson(x, y)
        record = {
            "city": city,
            "grid_months": len(all_rows),
            "paired_months": len(paired),
            "excluded_months": len(all_rows) - len(paired),
            "pearson_r": r,
            "undefined_reason": reason,
            "first_month": paired.month.iloc[0] if len(paired) else None,
            "last_month": paired.month.iloc[-1] if len(paired) else None,
        }
        periods = pd.PeriodIndex(paired.month, freq="M")
        consecutive = pd.Series(periods.asi8, index=paired.index).diff().eq(1)
        dx, dy = x.diff().loc[consecutive], y.diff().loc[consecutive]
        diff_r, diff_reason = pearson(dx, dy)
        record.update(
            first_difference_pairs=len(dx), first_difference_r=diff_r, first_difference_undefined_reason=diff_reason
        )
        counts = pd.Series(periods.month).value_counts()
        if len(paired) >= 24 and len(counts) == 12 and counts.min() >= 2:
            calendar_month = pd.Series(periods.month, index=paired.index)
            adjusted_r, adjusted_reason = pearson(
                x - x.groupby(calendar_month).transform("mean"), y - y.groupby(calendar_month).transform("mean")
            )
        else:
            adjusted_r, adjusted_reason = None, "need_two_observations_for_each_calendar_month"
        record.update(seasonal_demeaned_r=adjusted_r, seasonal_demeaned_undefined_reason=adjusted_reason)
        results.append(record)
    return results


def run(config_path, output):
    config_path = Path(config_path).resolve()
    config, base, months = load_config(config_path)
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    save_json(output / "status.json", {"state": "incomplete"})
    inputs = []
    try:

        def read(spec):
            path = (base / spec["path"]).resolve()
            inputs.append({"path": str(path), "sha256": sha256(path), "metadata": spec})
            return pd.read_csv(path, dtype="string", keep_default_na=False)

        accepted, rejected = [], []
        for spec in config["requests"]:
            good, bad = clean_requests(read(spec), spec, months)
            accepted.append(good)
            rejected.append(bad)
        requests, duplicates = deduplicate_requests(pd.concat(accepted, ignore_index=True))
        requests, monthly_311 = aggregate_requests(
            requests, config["requests"], months, config.get("keyword_rule", "broad_service_terms")
        )
        trends = pd.concat(
            [clean_trends(read(s), s, config["expected_terms"][s["city"]]) for s in config["trends"]], ignore_index=True
        )
        outside = trends.loc[~trends.month.isin([str(m) for m in months])]
        trends = trends.loc[trends.month.isin([str(m) for m in months])].copy()
        monthly_trends = aggregate_trends(trends, config["expected_terms"], months)
        combined = merge_monthly(monthly_311, monthly_trends)
        tables = {
            "clean_requests": requests,
            "rejected_requests": pd.concat(rejected, ignore_index=True),
            "duplicate_requests": duplicates,
            "clean_trends": trends,
            "trends_outside_window": outside,
            "monthly_311": monthly_311,
            "monthly_trends": monthly_trends,
            "monthly_combined": combined,
        }
        for name, table in tables.items():
            table.to_csv(output / (name + ".csv"), index=False)
        save_json(output / "correlations.json", correlations(combined))
        audit = {
            "raw_request_rows": sum(len(good) + len(bad) for good, bad in zip(accepted, rejected)),
            "accepted_before_dedup": sum(map(len, accepted)),
            "duplicate_rows_removed": len(duplicates),
            "accepted_unique_requests": len(requests),
            "rejected_rows": sum(map(len, rejected)),
            "unknown_type_retained_in_denominator": int(requests.type_unknown.sum()),
            "coverage_by_city": {
                city: {
                    "grid_months": int(combined.city.eq(city).sum()),
                    "eligible_months": int(combined.loc[combined.city.eq(city), "eligible"].sum()),
                }
                for city in CITIES
            },
            "is_fixture": config["is_fixture"],
            "keyword_rule": config.get("keyword_rule", "broad_service_terms"),
            "keyword_rules": RULES,
            "interpretation": "Keyword-matched service requests and relative search interest; no visitor attribution or causal effect",
        }
        save_json(output / "audit.json", audit)
        save_json(
            output / "provenance.json",
            {
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
                "config_sha256": sha256(config_path),
                "config": config,
                "code_sha256": sha256(__file__),
                "inputs": inputs,
                "python": platform.python_version(),
                "packages": {p: importlib.metadata.version(p) for p in ["pandas", "numpy"]},
                "output_sha256": {p.name: sha256(p) for p in output.iterdir() if p.name != "status.json"},
            },
        )
        save_json(output / "status.json", {"state": "complete"})
    except Exception as error:
        save_json(output / "status.json", {"state": "failed", "error": str(error)})
        raise
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True, help="New run directory; existing directories are rejected")
    args = parser.parse_args()
    print(run(args.config, args.out))


if __name__ == "__main__":
    main()
