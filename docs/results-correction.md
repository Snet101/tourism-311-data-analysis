# Historical results and repaired interpretation

Baseline: `8d1049b3365f13ca5ff540b12677ea722bf7db1e`.

The original notebooks show data integration, keyword classification and per-city correlation work. Saved historical correlations between the search-interest proxy and keyword-matched request share are approximately Boston 0.22, Seattle 0.01 and Washington DC 0.74. The original raw request snapshots and Trends exports are absent, so these values have not been independently reproduced. The original notebooks and README are preserved under `docs/historical/`; the competition PDF is unchanged.

Repair issues: undefined cleaning functions, inconsistent read/write paths, Boston reading from a shared city folder, silent inner-join coverage loss, differing time windows, missing reproducible acquisition settings, and terminology that implied visitor attribution from broad service categories.

The repaired pipeline uses explicit source paths/schema mappings; local-time month assignment; request IDs and conflicting-duplicate rejection; documented accepted-record denominators; a full calendar grid; source coverage assertions; fixed search-term baskets; partial/censored-term exclusions; and per-city paired correlations with counts and exclusion reasons. First-difference summaries do not bridge gaps. Seasonal demeaning requires at least two observations for every calendar month.

Broad noise/trash/parking categories do not identify who caused a request or who submitted it. Even the narrower explicit visitor-term rule is a category heuristic, not a validated attribution classifier. The narrow and broad specifications are saved separately; neither has measured precision/recall without a labeled evaluation sample.

Search-interest indices are not visitor counts, tourism intensity per resident, or absolute comparable cross-city volume. Request shares describe composition among accepted service requests; they do not normalize reporting practices, service-system scope, population size or tourism causation. A service request is not necessarily a complaint or evidence of an actual service burden. Seasonal demeaning and first differences do not identify causal effects or resolve all autocorrelation, trends, pandemic effects or confounding. No significance tests, causal effects, or pooled cross-city correlation are claimed.

The deterministic fixtures test software only. Current public API samples test source schema/cleaning only and provide no verified complete months. Neither replaces the missing original study data. The historical competition submission remains a record of what was submitted; describe later maintenance separately in applications.
