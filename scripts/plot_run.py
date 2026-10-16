"""Render descriptive per-city charts from a complete, hash-verified run."""

import argparse
import json
from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tourism_pipeline import CITIES, sha256


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if json.loads((args.run / "status.json").read_text())["state"] != "complete":
        raise ValueError("Run is not complete")
    provenance = json.loads((args.run / "provenance.json").read_text())
    for filename, expected in provenance["output_sha256"].items():
        if sha256(args.run / filename) != expected:
            raise ValueError(f"Run fingerprint mismatch: {filename}")
    args.out.mkdir(parents=True, exist_ok=False)
    data = pd.read_csv(args.run / "monthly_combined.csv")
    fixture = provenance["config"]["is_fixture"]
    heading = (
        "SYNTHETIC SOFTWARE FIXTURE — NOT EMPIRICAL RESULTS"
        if fixture
        else "Descriptive associations; no visitor attribution or causal effect"
    )
    fig, axes = plt.subplots(1, 3, figsize=(12, 4), layout="constrained")
    for ax, city in zip(axes, CITIES):
        subset = data.loc[data.city.eq(city) & data.eligible]
        ax.scatter(subset.search_interest_index, subset.keyword_request_share, s=22, alpha=0.8)
        ax.set(
            title=f"{city}\n{len(subset)} eligible months",
            xlabel="Relative search-interest index",
            ylabel="Keyword-matched request share",
        )
        ax.set_ylim(0, 1)
        ax.grid(alpha=0.2)
    fig.suptitle(heading, fontsize=11)
    fig.savefig(args.out / "associations.png", dpi=160)
    plt.close(fig)
    fig, axes = plt.subplots(3, 2, figsize=(11, 8), layout="constrained")
    for row, city in enumerate(CITIES):
        subset = data.loc[data.city.eq(city)].copy()
        dates = pd.to_datetime(subset.month)
        # Calendar grid and NaNs retain gaps instead of drawing through missing observations.
        axes[row, 0].plot(dates, subset.search_interest_index, marker=".", linewidth=1)
        shares = subset.keyword_request_share.where(subset.request_coverage_complete)
        axes[row, 1].plot(dates, shares, marker=".", linewidth=1, color="#b05620")
        axes[row, 0].set(title=city, ylabel="Relative search-interest index")
        axes[row, 1].set(title=city, ylabel="Keyword-matched request share", ylim=(0, 1))
        for ax in axes[row]:
            ax.tick_params(axis="x", rotation=30)
            ax.grid(alpha=0.2)
    fig.suptitle(heading, fontsize=11)
    fig.savefig(args.out / "time-series.png", dpi=160)
    plt.close(fig)
    print("PASS: descriptive charts saved")


if __name__ == "__main__":
    main()
