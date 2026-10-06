# Tourism and 311 Service Burden Analysis

This repository contains the code for a TSA Data Science & Analytics project examining how tourism activity is associated with resident-reported service burden across Boston, Seattle, and Washington, DC.

## Research Question

How is tourism activity associated with tourism-related 311 service requests, and how does that relationship differ across cities?

## Data Sources

The project combines two public data sources:

- **Google Trends** — used as a proxy for monthly tourism activity
- **Municipal 311 service-request data** — used to measure resident-reported service burden

The analysis standardizes both sources to a monthly city-level format.

## Key Variables

Each city-month observation includes:

- tourism intensity
- total 311 service requests
- tourism-related 311 complaints
- tourism complaint share

Tourism complaint share is used to normalize differences in city size and baseline complaint volume.

## Repository Contents

- `tourism_search_trends.ipynb`  
  Collects and processes monthly Google Trends tourism-interest data.

- `311_processing.ipynb`  
  Cleans 311 service-request data, identifies tourism-related complaints using keyword matching, and aggregates monthly complaint metrics.

- `correlation_analysis.ipynb`  
  Calculates correlations between tourism indicators and 311 metrics across Boston, Seattle, and Washington, DC.

## Methods

The project includes:

- data cleaning and standardization
- monthly aggregation
- tourism-related complaint classification
- feature construction
- correlation analysis
- cross-city comparison
- seasonal time-series analysis
- data visualization

## Findings

The relationship between tourism activity and resident service burden varies substantially by city.

- **Boston:** moderate positive association between tourism intensity and tourism-related service demand
- **Seattle:** weak relationship between tourism intensity and tourism complaint share
- **Washington, DC:** strong positive relationship between tourism intensity and both tourism-related calls and tourism complaint share

These differences suggest that tourism pressure interacts with city infrastructure and service systems differently across locations.

## Tech Stack

- Python
- pandas
- NumPy
- matplotlib
- Jupyter Notebook

## Limitations

This analysis is descriptive rather than causal.

Google Trends is used as a proxy for tourism activity, and 311 complaint classification depends on keyword-based filtering. Differences in reporting practices across cities may also affect results.

## Competition Context

Developed for the 2025–2026 TSA Data Science & Analytics competition.
