# Stage 6 validation — October 16, 2026

Baseline: `8d1049b3365f13ca5ff540b12677ea722bf7db1e`. Branch: `codex/tourism-reproducibility-repair`.

A new Windows virtual environment was installed from the declared development/plot requirements. Python 3.12.14, pandas 3.0.6, NumPy 2.5.4 and matplotlib 3.11.2 were used. Exact installed versions are recorded in requirements-dev.lock.txt, with separate POSIX-only IPython dependency markers for CI. `pip check` passed.

Completed locally:

- 41 pytest cases passed, including schema failures, local/UTC month boundaries and DST ambiguity, ID preservation, exact/conflicting duplicates, unknown category denominators, zero versus missing coverage, strict monthly Trends keys, partial/censored/missing terms, invalid scores, outer joins, known correlations, adjacent-only first differences, constant seasonal residuals, empty sources, output preservation, failure status, historical hashes, and monthly export conversion.
- Ruff and staged whitespace checks passed.
- The complete deterministic fixture pipeline ran. Of 1,908 raw request rows, 1,898 unique requests were accepted, nine rejected and one exact duplicate removed. The accepted denominator retains 297 unknown categories. The 108-row calendar grid remains intact: eligible paired months are Boston 34, Seattle 34 and Washington DC 35 out of 36 each.
- Both predeclared keyword specifications completed in separate saved runs. They are software sensitivity examples, not validated attribution classifiers.
- All three notebooks executed in independent fresh kernels against the same saved run. Hashes and saved/recalculated correlations were checked. Jupyter emitted a nonfatal local TCP transport warning; execution and shutdown succeeded.
- Two matplotlib figures were generated and visually inspected. Both prominently identify synthetic software fixtures; gaps remain visible in time-series charts.
- Official municipal APIs returned 100 records per city, 300 total. All 300 passed the configured cleaner. Exact JSON/CSV snapshots and source metadata were saved. These ordered bounded samples have no verified complete months and provide no population or correlation estimate.

The original three notebooks, README and competition PDF are preserved with exact byte fingerprints. The PDF is unchanged. The historical correlations (approximately 0.22, 0.01 and 0.74) remain unreproduced because the original request snapshots and Google Trends exports are missing. New fixture results must not be presented as empirical replacements.

GitHub-hosted Linux checks run after push and have not yet been observed. Current endpoint/schema checks do not guarantee future availability or validate full research-period completeness. Seasonality, reporting differences and confounding still limit substantive interpretation. The remaining research task is to supply verified full-period municipal snapshots and genuine matching monthly Trends exports, then review exclusions and regenerate the analysis.
