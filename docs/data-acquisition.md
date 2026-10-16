# Explicit data acquisition and provenance

The original request snapshots and Google Trends exports were not committed. The archived notebook outputs are historical results, not enough evidence to reconstruct identical inputs. Preserve the exact bytes of every new export and do not present a fresh download as the original competition data.

## Official municipal sources

| City | Official source | Verified schema |
|---|---|---|
| Boston | [Analyze Boston 311 dataset](https://data.boston.gov/dataset/311-service-requests) | `case_enquiry_id`, `open_dt`, `type`; naive dates interpreted in America/New_York |
| Seattle | [Customer Service Requests](https://data.seattle.gov/Community/Customer-Service-Requests/5ngg-rpne) | API: `servicerequestnumber`, `createddate`, `webintakeservicerequests`; exported display names may differ; America/Los_Angeles |
| Washington DC | [2024 311 requests](https://opendata.dc.gov/datasets/DCGIS::311-city-service-requests-in-2024) | `SERVICEREQUESTID`, `ADDDATE`, `SERVICECODEDESCRIPTION`; ArcGIS API epoch milliseconds are explicitly converted to UTC ISO strings, then city local time |

Boston's 2024 resource ID is `dff4d804-5031-443a-8409-8344efd0e5c8`. The DC 2024 REST layer is `https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_DATA/ServiceRequests/FeatureServer/16`. These references were checked on October 16, 2026; portals and schemas can change.

Test source connectivity and the actual cleaners with a small bounded sample:

```powershell
python scripts/fetch_public_samples.py --out data/source-smoke --limit 100
```

This saves the exact JSON response bytes, three-column CSVs, cleaned/rejected rows, hashes, URLs and acquisition timestamps. Each city's `complete_months` is empty. These are ordered samples, not representative samples or complete population data. Do not use them to estimate full-month shares or correlations.

For research runs, download the complete requested year/period from each portal. Boston uses separate yearly resources; DC also has separate yearly layers. Seattle permits date-filtered exports. Full API downloads require stable ordering, complete pagination, and a check against the endpoint's count/export metadata. A bounded sample must never be relabeled as complete. Record the actual CSV header mapping in the run config; do not guess aliases or concatenate every CSV in a shared folder. Review source usage terms, attribution and reporting-system changes for the period used.

## Google Trends

Use the official Google Trends Explore export. [Google explains that values are normalized relative interest, not absolute search volume or visitor counts](https://support.google.com/trends/answer/4365533?hl=en). Historical long-range daily/weekly observations cannot be relabeled as monthly rows. For this repair, provide monthly exports directly. If a different resolution is needed, implement and test a separately documented aggregation with interval-boundary handling.

For every city record:

- Exact terms or topic IDs; whether each is a search term or topic.
- Geography, requested timeframe, category, search type and download timestamp.
- Whether terms were exported together or separately. Separately normalized terms are equally weighted indices, not counts.
- The exact raw CSV and its checksum. Preserve the original query settings alongside it.

Keep a fixed term basket for all months within a city and the same timeframe/geography/settings across its term exports. The historical basket was `things to do in {city}`, `visit {city}`, and `{city} tourist attractions`; its geographic search scope was not explicitly recorded in the old code. The software fixture uses US as an invented metadata setting and does not establish the historical setting.

The canonical long CSV contract is:

```text
city,month,term,value,is_partial
Boston,2024-01,visit Boston,34,false
```

This example illustrates the schema; 34 is not a measured value. Month must be YYYY-MM. Values are 0–100, empty for missing, or `<1` for censored. Partial/censored/missing terms are excluded; the composite is undefined unless every expected term is usable. Zero remains a valid published score and does not mean zero visitors.

To convert a monthly wide export, create a JSON file mapping terms to the exact export headers, for example `{"visit Boston": "visit Boston: (United States)"}`, then run:

```powershell
python scripts/prepare_trends.py --input data/raw/boston-export.csv --city Boston --columns-json data/boston-columns.json --date-column Month --skiprows 2 --complete-through 2024-12 --out data/boston-converted
```

Inspect the raw header and set skiprows accordingly. The converter refuses daily/weekly date keys and excludes later months, saving the excluded rows. Use only completed source months. The selected complete-through month must precede the current UTC calendar month. The converter cannot prove that the export has the right query settings; those remain explicit provenance requirements. Combine distinct-term exports into one city CSV without duplicate city/month/term keys.

## Run manifest

`tests/fixtures/config.json` is the complete executable schema example. For real analysis, copy it outside tests, set `is_fixture` to false, replace every fixture path/URL/timestamp, set the intended start and exclusive end months, and supply the real column mappings and Trends settings. Paths resolve relative to the config file. `complete_months` lists only months for which the supplied municipal snapshot is verified complete; use `[]` when unknown. This is an explicit source assertion, not completeness inferred by the program. A complete source with no accepted rows has zero requests and an undefined share; unverified absence stays missing. Inspect rejected records before interpreting accepted-record shares.

Changing labels from fixture to observed does not validate invented data. Preserve external evidence that the files are genuine, complete exports.
