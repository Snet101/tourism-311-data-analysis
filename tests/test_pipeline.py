import copy
import json
from pathlib import Path

import pandas as pd
import pytest

import tourism_pipeline as p

FIXTURE = Path(__file__).parent / "fixtures/config.json"


@pytest.fixture
def setup_data():
    config, base, months = p.load_config(FIXTURE)
    spec = config["requests"][0]
    raw = pd.read_csv(base / spec["path"], dtype="string", keep_default_na=False)
    return config, base, months, spec, raw


@pytest.mark.parametrize("bad", ["2024-01-01", "2024-13", "2024-1", "", None])
def test_reject_nonmonthly_keys(bad):
    with pytest.raises(ValueError):
        p.month(bad)


def test_schema_rejected(setup_data):
    _, _, months, spec, raw = setup_data
    with pytest.raises(ValueError, match="missing columns"):
        p.clean_requests(raw.drop(columns=spec["date_column"]), spec, months)


def test_cleaning_quarantine_and_unknown_types(setup_data):
    _, _, months, spec, raw = setup_data
    good, bad = p.clean_requests(raw, spec, months)
    assert len(good) + len(bad) == len(raw)
    assert set(bad.reason) == {"missing_request_id", "invalid_or_ambiguous_date", "outside_analysis_window"}
    assert good.complaint_type.eq("").any()
    assert not good.complaint_type.eq("nan").any()
    assert good.request_id.str.startswith("00-").any()


def test_local_month_boundaries_and_dst():
    assert p.parse_local_timestamp("2024-03-01T00:30:00Z", "America/Los_Angeles").month == 2
    assert pd.isna(p.parse_local_timestamp("2024-11-03T01:30:00", "America/New_York"))
    assert pd.isna(p.parse_local_timestamp("2024-03-10T02:30:00", "America/New_York"))
    assert pd.isna(p.parse_local_timestamp("1704092531000", "America/New_York"))


def test_exact_duplicates_audited_conflicts_rejected(setup_data):
    _, _, months, spec, raw = setup_data
    good, _ = p.clean_requests(raw, spec, months)
    unique, duplicates = p.deduplicate_requests(good)
    assert len(duplicates) == 1 and len(unique) + 1 == len(good)
    conflict = unique.iloc[[0]].copy()
    conflict["complaint_type"] = "Changed category"
    with pytest.raises(ValueError, match="Conflicting"):
        p.deduplicate_requests(pd.concat([unique, conflict]))


def test_ids_scoped_to_city(setup_data):
    _, _, months, spec, raw = setup_data
    good, _ = p.clean_requests(raw, spec, months)
    first = good.iloc[[0]].copy()
    second = first.assign(city="Seattle")
    unique, duplicates = p.deduplicate_requests(pd.concat([first, second]))
    assert len(unique) == 2 and duplicates.empty


def test_zero_month_vs_unverified_missing_month(setup_data):
    config, _, months, spec, raw = setup_data
    good, _ = p.clean_requests(raw, spec, months)
    good, _ = p.deduplicate_requests(good)
    marked, monthly = p.aggregate_requests(good, [spec], months, "broad_service_terms")
    zero = monthly.loc[monthly.city.eq("Boston") & monthly.month.eq("2022-04")].iloc[0]
    unknown = monthly.loc[monthly.city.eq("Seattle") & monthly.month.eq("2022-04")].iloc[0]
    assert zero.n_requests == 0 and pd.isna(zero.keyword_request_share)
    assert pd.isna(unknown.n_requests) and not unknown.request_coverage_complete
    assert monthly.loc[monthly.city.eq("Boston"), "n_requests"].sum() == len(good)
    assert marked.type_unknown.sum() > 0


def test_share_uses_total_denominator_not_average_daily_shares():
    data = pd.DataFrame(
        {
            "city": ["Boston"] * 4,
            "request_id": ["1", "2", "3", "4"],
            "month": ["2024-01"] * 4,
            "complaint_type": ["Noise", "", "Pothole", "Pothole"],
        }
    )
    _, monthly = p.aggregate_requests(
        data,
        [{"city": "Boston", "complete_months": ["2024-01"]}],
        pd.period_range("2024-01", periods=1, freq="M"),
        "broad_service_terms",
    )
    row = monthly.loc[monthly.city.eq("Boston")].iloc[0]
    assert row.n_unknown_type == 1 and row.keyword_request_share == 0.25


@pytest.mark.parametrize(
    "text,match",
    [
        ("Noise", True),
        ("PARKING issue", True),
        ("garbage", True),
        ("parkinglot", False),
        ("nan", False),
        ("", False),
        ("Pothole", False),
    ],
)
def test_keyword_boundaries(text, match):
    import re

    assert bool(re.search(p.RULES["broad_service_terms"], text, re.I)) == match


def test_narrow_rule_is_distinct():
    import re

    assert re.search(p.RULES["explicit_visitor_terms"], "Tour bus noise", re.I)
    assert not re.search(p.RULES["explicit_visitor_terms"], "Trash pickup", re.I)


def test_trends_missing_partial_censored(setup_data):
    config, base, months, _, _ = setup_data
    frames = [
        p.clean_trends(pd.read_csv(base / s["path"], dtype="string"), s, config["expected_terms"][s["city"]])
        for s in config["trends"]
    ]
    monthly = p.aggregate_trends(pd.concat(frames), config["expected_terms"], months)
    for city, key in [("Boston", "2022-05"), ("Seattle", "2023-03"), ("Washington DC", "2024-12")]:
        row = monthly.loc[monthly.city.eq(city) & monthly.month.eq(key)].iloc[0]
        assert not row.trends_complete and pd.isna(row.search_interest_index)


@pytest.mark.parametrize(
    "field,value",
    [
        ("month", "2024-01-07"),
        ("city", "Other"),
        ("term", "Other"),
        ("value", "101"),
        ("value", "-1"),
        ("value", "inf"),
        ("value", "oops"),
        ("is_partial", "maybe"),
    ],
)
def test_bad_trends_rejected(setup_data, field, value):
    config, base, _, _, _ = setup_data
    spec = config["trends"][0]
    raw = pd.read_csv(base / spec["path"], dtype="string").iloc[[0]].copy()
    raw[field] = value
    with pytest.raises(ValueError):
        p.clean_trends(raw, spec, config["expected_terms"][spec["city"]])


def test_trends_duplicates_rejected(setup_data):
    config, base, _, _, _ = setup_data
    spec = config["trends"][0]
    raw = pd.read_csv(base / spec["path"], dtype="string").iloc[[0]]
    with pytest.raises(ValueError, match="Duplicate"):
        p.clean_trends(pd.concat([raw, raw]), spec, config["expected_terms"][spec["city"]])


def test_outer_merge_reports_unmatched_and_rejects_duplicate_keys():
    a = pd.DataFrame(
        {"city": ["Boston"], "month": ["2024-01"], "request_coverage_complete": [True], "keyword_request_share": [0.2]}
    )
    b = pd.DataFrame(
        {"city": ["Boston"], "month": ["2024-02"], "trends_complete": [True], "search_interest_index": [20.0]}
    )
    result = p.merge_monthly(a, b)
    assert len(result) == 2 and not result.eligible.any()
    assert set(result["_merge"]) == {"left_only", "right_only"}
    with pytest.raises(ValueError, match="unique"):
        p.merge_monthly(pd.concat([a, a]), b)


def test_known_pearson_and_undefined_cases():
    assert p.pearson([1, 2, 3], [3, 2, 1])[0] == -1
    assert p.pearson([1, 1, 1], [1, 2, 3])[1] == "constant_series"
    assert p.pearson([1, 2], [1, 2])[0] is None


def test_first_differences_do_not_bridge_gaps():
    data = pd.DataFrame(
        {
            "city": ["Boston"] * 4,
            "month": ["2024-01", "2024-02", "2024-04", "2024-05"],
            "eligible": [True] * 4,
            "search_interest_index": [10, 20, 90, 80],
            "keyword_request_share": [0.1, 0.2, 0.9, 0.8],
        }
    )
    result = p.correlations(data)[0]
    assert result["first_difference_pairs"] == 2
    assert result["first_difference_r"] is None
    assert result["seasonal_demeaned_r"] is None


def test_pipeline_repeatability_provenance_and_coverage(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    p.run(FIXTURE, a)
    p.run(FIXTURE, b)
    for name in ["monthly_combined.csv", "correlations.json", "audit.json", "clean_requests.csv"]:
        assert (a / name).read_bytes() == (b / name).read_bytes()
    audit = json.loads((a / "audit.json").read_text())
    assert (
        audit["raw_request_rows"]
        == audit["accepted_unique_requests"] + audit["duplicate_rows_removed"] + audit["rejected_rows"]
    )
    assert audit["duplicate_rows_removed"] == 1 and audit["rejected_rows"] == 9
    assert audit["coverage_by_city"]["Boston"]["eligible_months"] == 34
    assert audit["coverage_by_city"]["Seattle"]["eligible_months"] == 34
    assert audit["coverage_by_city"]["Washington DC"]["eligible_months"] == 35
    meta = json.loads((a / "provenance.json").read_text())
    for filename, expected in meta["output_sha256"].items():
        assert p.sha256(a / filename) == expected
    with pytest.raises(FileExistsError):
        p.run(FIXTURE, a)


def test_failed_run_marked(tmp_path, monkeypatch):
    def broken(*args):
        raise ValueError("injected failure")

    monkeypatch.setattr(p, "clean_trends", broken)
    with pytest.raises(ValueError):
        p.run(FIXTURE, tmp_path / "failed")
    assert json.loads((tmp_path / "failed/status.json").read_text())["state"] == "failed"


def test_config_requires_provenance_and_explicit_fixture_flag(tmp_path):
    data = json.loads(FIXTURE.read_text())
    for change in ["is_fixture", "downloaded_at"]:
        config = copy.deepcopy(data)
        if change == "is_fixture":
            del config[change]
        else:
            del config["requests"][0][change]
        target = tmp_path / (change + ".json")
        target.write_text(json.dumps(config))
        with pytest.raises(ValueError):
            p.load_config(target)


def test_historical_files_preserved():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "docs/historical-sha256.json").read_text())
    for name, expected in manifest.items():
        assert p.sha256(root / name) == expected


def test_monthly_export_converter_excludes_later_months(tmp_path):
    import subprocess
    import sys

    source = tmp_path / "export.csv"
    source.write_text("Category: All categories\n\nMonth,search-header\n2024-01,20\n2024-02,<1\n2024-03,40\n")
    mapping = tmp_path / "mapping.json"
    mapping.write_text(json.dumps({"visit Boston": "search-header"}))
    script = Path(__file__).resolve().parents[1] / "scripts/prepare_trends.py"
    command = [
        sys.executable,
        str(script),
        "--input",
        str(source),
        "--city",
        "Boston",
        "--columns-json",
        str(mapping),
        "--complete-through",
        "2024-02",
        "--out",
        str(tmp_path / "converted"),
    ]
    subprocess.run(command, check=True)
    result = pd.read_csv(tmp_path / "converted/trends-long.csv")
    assert result.month.tolist() == ["2024-01", "2024-02"]
    assert result.value.tolist() == ["20", "<1"]
    assert len(pd.read_csv(tmp_path / "converted/excluded-later-months.csv")) == 1


def test_seasonal_adjustment_detects_constant_residuals():
    periods = pd.period_range("2022-01", "2024-12", freq="M")
    data = pd.DataFrame(
        {
            "city": ["Boston"] * len(periods),
            "month": periods.astype(str),
            "eligible": True,
            "search_interest_index": periods.month.astype(float),
            "keyword_request_share": periods.month.astype(float) / 20,
        }
    )
    result = p.correlations(data)[0]
    assert result["pearson_r"] > 0.999
    assert result["seasonal_demeaned_r"] is None
    assert result["seasonal_demeaned_undefined_reason"] == "constant_series"


def test_empty_request_source_can_report_declared_zero_month(setup_data):
    _, _, months, spec, raw = setup_data
    good, bad = p.clean_requests(raw.iloc[:0], spec, months)
    assert good.empty and bad.empty
    unique, _ = p.deduplicate_requests(good)
    _, monthly = p.aggregate_requests(unique, [spec], months, "broad_service_terms")
    city = monthly.loc[monthly.city.eq("Boston")]
    assert city.n_requests.eq(0).all() and city.keyword_request_share.isna().all()


def test_empty_trends_source_is_missing_not_zero(setup_data):
    config, base, months, _, _ = setup_data
    spec = config["trends"][0]
    raw = pd.read_csv(base / spec["path"], dtype="string").iloc[:0]
    clean = p.clean_trends(raw, spec, config["expected_terms"]["Boston"])
    monthly = p.aggregate_trends(clean, config["expected_terms"], months)
    assert not monthly.trends_complete.any() and monthly.search_interest_index.isna().all()
