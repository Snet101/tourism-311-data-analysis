# Search Interest and 311 Request Patterns

A TSA Data Science & Analytics project exploring monthly search interest and service-request patterns in Boston, Seattle and Washington, DC. This subsequent repair makes the analysis reproducible and makes its measurement limits explicit. The original competition document is preserved unchanged.

**Historical correlations are not independently reproduced:** original municipal snapshots and Google Trends exports are absent. The archived notebooks report approximately Boston 0.22, Seattle 0.01 and Washington DC 0.74. Those are historical outputs, not newly verified findings. See `docs/results-correction.md`.

## Run the offline example

Use Python 3.12 and a new environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.lock.txt
python -m pip check
python -m pytest -q
python tourism_pipeline.py --config tests/fixtures/config.json --out runs/fixture
python scripts/check_notebooks.py --run runs/fixture
python scripts/keyword_sensitivity.py --config tests/fixtures/config.json --out runs/keyword-sensitivity
python scripts/plot_run.py --run runs/fixture --out runs/fixture-plots
```

On Linux/macOS activate with `source .venv/bin/activate`. The fixture invents three years of requests/search-interest values for all three cities, including intentional gaps and invalid inputs. It is a software check, not city research. Charts prominently identify synthetic data. The run commands make no network calls. Existing output directories are rejected to preserve previous evidence.

`requirements.txt` contains runtime ranges; `requirements-dev.txt` adds notebook/testing tools; `requirements-plot.txt` adds matplotlib. `requirements-dev.lock.txt` records the tested dependency versions, including plotting. It is a version snapshot, not a cryptographically locked package archive.

## Use observed snapshots

Read `docs/data-acquisition.md` for official sources, schemas, explicit Google Trends exports, conversion commands and the full manifest contract. Source paths resolve relative to the config file, with no broad CSV glob that can mix cities. The config specifies analysis start and exclusive end months, city schema mappings, source provenance, timezones, verified complete months and the fixed term basket.

```powershell
python tourism_pipeline.py --config data/observed-config.json --out runs/observed-run
```

For bounded source-schema checks only:

```powershell
python scripts/fetch_public_samples.py --out data/source-smoke --limit 100
```

The sample command stores exact official JSON responses, selected-field CSVs, cleaned/rejected rows, source URLs, timestamps and hashes. Samples have no verified complete months and cannot be used as full-month research observations. Rebuilding the historical study requires the original snapshots or a clearly documented new data collection, including genuine Trends exports.

## Measurements and safeguards

| Output | Meaning |
|---|---|
| `n_requests` | Accepted unique request IDs in the month; not necessarily calls or complaints |
| `n_keyword_matches` | Request categories matching the declared regex rule; no attribution to visitors |
| `n_unknown_type` | Requests with unknown categories, retained in the denominator |
| `keyword_request_share` | Matched requests divided by accepted requests; undefined for zero requests |
| `search_interest_index` | Equal-weight mean of a complete fixed term basket on normalized relative scales; not visitor counts |
| `eligible` | Complete source coverage explicitly declared, every expected term usable, and a defined request share |

Dates use each city's local calendar month. Naive dates are localized to the declared timezone; ambiguous/nonexistent DST times are quarantined. ArcGIS epoch values require explicit conversion. Request IDs preserve leading zeros. Exact repeated IDs with matching timestamp/category are deduplicated and audited; conflicting versions stop the run. Invalid IDs/dates and out-of-window records are saved with reasons. Inspect exclusions before interpreting the accepted-record denominator.

All city-months stay in the requested calendar grid. A missing month becomes zero only when complete source coverage has been explicitly declared; otherwise it stays missing. This declaration is a provenance assertion requiring external verification, not completeness inferred from a few rows. Trends monthly keys are strict; duplicates fail. Missing terms, partial periods and censored `<1` values make the composite unavailable. No averages over changing term baskets or invented zeros are used.

Correlations are per city, with paired counts and exclusion reasons. First differences use adjacent calendar months only. Seasonal demeaning requires at least two observations for every calendar month. These are descriptive sensitivities; no causal effects or significance tests are asserted. Pooled cross-city correlation is intentionally absent because separately normalized indices and reporting systems are not directly comparable.

## Saved run and notebooks

Each run saves clean requests, rejected/duplicate rows, clean Trends data, out-of-window Trends rows, both monthly tables, a full combined coverage table, correlations, audit counts, status and provenance. Provenance records configuration, source hashes/metadata, code hash, package versions and output hashes. Only `status.json` state `complete` is ready for analysis.

The three notebooks read the same hash-verified run, execute independently, and perform no live downloads. Set `TOURISM_RUN` or pass `--run` to inspect another run. Executed copies are saved inside that run directory. `scripts/keyword_sensitivity.py` saves both the broad service-category rule and the narrower explicit visitor-term rule; neither is a validated tourist-attribution classifier. `scripts/plot_run.py` verifies input hashes before rendering.

## Historical record and limits

`docs/historical/` preserves the original notebooks and README; the competition PDF remains unchanged. Their limitations and original outputs are documented separately from this repaired code. Do not describe current synthetic fixtures or bounded API samples as reproducing the historical results.

Keyword matching does not establish who caused or submitted a request. Request share does not control for population, reporting propensity, municipal service scope, seasonality or other confounding. Relative search interest is not tourism activity per resident. The repair supports clearer descriptive analysis and source auditing; it does not establish tourism-caused service burden.

GitHub Actions runs offline tests, notebooks and fixture plots after push. See `docs/validation.md` for completed checks and the remaining data limitation.
