#!/usr/bin/env python3
"""Regenerate charts from the existing dataset CSV.

Uses mean_ref_age (which has continuous variation) rather than
median_ref_age (which is quantized to integers due to integer
year-difference ages). The stats.py fix computes per-paper statistics
for future runs, but this script works with the existing data.
"""

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import pandas as pd
import seaborn as sns

DATA_PATH = "data/reference_age_dataset_1000.csv"
OUTPUT_DIR = "output"
MIN_REF_RESOLUTION_RATE = 0.6


def _smooth(series: pd.Series, window: int = 3) -> pd.Series:
    return series.rolling(window=window, center=True, min_periods=1).mean()


def _plot_dual_panel(data, group_col, title_prefix, out_path):
    if data.empty:
        print(f"  No {group_col}-level data to plot!")
        return

    sns.set_theme(style="whitegrid", font_scale=1.1)
    palette = sns.color_palette("tab10", n_colors=data[group_col].nunique())
    fig, axes = plt.subplots(1, 2, figsize=(18, 7))

    # Left: smoothed mean
    ax = axes[0]
    for i, (name, grp) in enumerate(sorted(data.groupby(group_col))):
        grp = grp.sort_values("year")
        smoothed = _smooth(grp["mean_ref_age"])
        ax.plot(grp["year"], smoothed, label=name, linewidth=2, color=palette[i])
        ax.plot(grp["year"], grp["mean_ref_age"], alpha=0.2, linewidth=0.5, color=palette[i])
    ax.set_xlabel("Publication Year")
    ax.set_ylabel("Mean Reference Age (years)")
    ax.set_title(f"Mean Reference Age by {title_prefix} (3-yr smoothed)")
    ax.legend(fontsize=7, loc="upper left")
    ax.xaxis.set_major_locator(ticker.MultipleLocator(5))

    # Right: mean + IQR band (p25/p75 smoothed to reduce integer stepping)
    ax = axes[1]
    for i, (name, grp) in enumerate(sorted(data.groupby(group_col))):
        grp = grp.sort_values("year")
        sm_mean = _smooth(grp["mean_ref_age"])
        sm_p25 = _smooth(grp["p25"])
        sm_p75 = _smooth(grp["p75"])
        ax.fill_between(grp["year"], sm_p25, sm_p75, alpha=0.12, color=palette[i])
        ax.plot(grp["year"], sm_mean, label=name, linewidth=2, color=palette[i])
    ax.set_xlabel("Publication Year")
    ax.set_ylabel("Reference Age (years)")
    ax.set_title(f"Reference Age Distribution by {title_prefix} (Mean + IQR)")
    ax.legend(fontsize=7, loc="upper left")
    ax.xaxis.set_major_locator(ticker.MultipleLocator(5))

    year_lo = int(data["year"].min())
    year_hi = int(data["year"].max())
    fig.suptitle(
        f"Reference Age Trends by Academic {title_prefix} ({year_lo}-{year_hi})\n"
        f"Source: OpenAlex API | Min {MIN_REF_RESOLUTION_RATE:.0%} reference resolution rate",
        fontsize=13, fontweight="bold",
    )
    plt.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out_path}")


def _plot_dual_panel_raw(data, group_col, title_prefix, out_path):
    if data.empty:
        print(f"  No {group_col}-level data to plot!")
        return

    sns.set_theme(style="whitegrid", font_scale=1.1)
    palette = sns.color_palette("tab10", n_colors=data[group_col].nunique())
    fig, axes = plt.subplots(1, 2, figsize=(18, 7))

    # Left: raw mean
    ax = axes[0]
    for i, (name, grp) in enumerate(sorted(data.groupby(group_col))):
        grp = grp.sort_values("year")
        ax.plot(grp["year"], grp["mean_ref_age"], label=name, linewidth=1.5,
                color=palette[i], marker="o", markersize=3)
    ax.set_xlabel("Publication Year")
    ax.set_ylabel("Mean Reference Age (years)")
    ax.set_title(f"Mean Reference Age by {title_prefix} (raw)")
    ax.legend(fontsize=7, loc="upper left")
    ax.xaxis.set_major_locator(ticker.MultipleLocator(5))

    # Right: raw mean + IQR
    ax = axes[1]
    for i, (name, grp) in enumerate(sorted(data.groupby(group_col))):
        grp = grp.sort_values("year")
        ax.fill_between(grp["year"], grp["p25"], grp["p75"], alpha=0.12, color=palette[i])
        ax.plot(grp["year"], grp["mean_ref_age"], label=name, linewidth=1.5,
                color=palette[i], marker="o", markersize=3)
    ax.set_xlabel("Publication Year")
    ax.set_ylabel("Reference Age (years)")
    ax.set_title(f"Reference Age Distribution by {title_prefix} (Mean + IQR, raw)")
    ax.legend(fontsize=7, loc="upper left")
    ax.xaxis.set_major_locator(ticker.MultipleLocator(5))

    year_lo = int(data["year"].min())
    year_hi = int(data["year"].max())
    fig.suptitle(
        f"Reference Age Trends by Academic {title_prefix} ({year_lo}-{year_hi})\n"
        f"Source: OpenAlex API | Min {MIN_REF_RESOLUTION_RATE:.0%} reference resolution rate",
        fontsize=13, fontweight="bold",
    )
    plt.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out_path}")


def main():
    df = pd.read_csv(DATA_PATH)
    print(f"Loaded {len(df)} rows from {DATA_PATH}")

    import os
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Field-level charts
    field_df = df[df["subfield"] == "All"].copy()
    _plot_dual_panel(field_df, "field", "Field", f"{OUTPUT_DIR}/reference_age_by_field.png")
    _plot_dual_panel_raw(field_df, "field", "Field", f"{OUTPUT_DIR}/reference_age_by_field_raw.png")

    # Subfield-level charts
    sub_df = df[df["subfield"] != "All"].copy()
    _plot_dual_panel(sub_df, "subfield", "Subfield", f"{OUTPUT_DIR}/reference_age_by_subfield.png")
    _plot_dual_panel_raw(sub_df, "subfield", "Subfield", f"{OUTPUT_DIR}/reference_age_by_subfield_raw.png")

    print("\nDone.")


if __name__ == "__main__":
    main()
