"""
visualize_labels.py
===================
Visualizes the labeled training dataset to sanity-check ground truth matching.

Outputs (saved to analysis/plots/):
  1. map_labels.png        — Spatial map: TP / FP / Unknown across AB/SK
  2. score_distribution.png — Score histograms by label
  3. labels_by_year.png    — TP / FP / Unknown counts per year
  4. sensor_coverage.png   — Which sensors contribute to TPs vs Unknowns

Run from project root:
  python3 analysis/visualize_labels.py
"""

import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
import numpy as np

ROOT     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(ROOT, "analysis", "labeled_dataset.csv")
OUT_DIR  = os.path.join(ROOT, "analysis", "plots")
os.makedirs(OUT_DIR, exist_ok=True)

COLORS = {1: "#e74c3c", 0: "#f39c12", -1: "#95a5a6"}
LABELS = {1: "Confirmed Fire (TP)", 0: "Confirmed False Positive", -1: "Unknown"}

# ── Load ──────────────────────────────────────────────────────────────────
print("Loading labeled_dataset.csv...")
df = pd.read_csv(CSV_PATH)
print(f"  {len(df):,} clusters loaded\n")

tp  = df[df["label"] ==  1]
fp  = df[df["label"] ==  0]
unk = df[df["label"] == -1]

print(f"  TP:      {len(tp):>7,}  ({len(tp)/len(df)*100:.1f}%)")
print(f"  FP:      {len(fp):>7,}  ({len(fp)/len(df)*100:.1f}%)")
print(f"  Unknown: {len(unk):>7,}  ({len(unk)/len(df)*100:.1f}%)\n")


# ══════════════════════════════════════════════════════════════════════════
# 1. Spatial map
# ══════════════════════════════════════════════════════════════════════════

print("Rendering map_labels.png...")
fig, ax = plt.subplots(figsize=(14, 10), facecolor="#1a1a2e")
ax.set_facecolor("#1a1a2e")

# Plot in order: unknown (bottom), FP, TP (top)
for label, subset, size, alpha, zorder in [
    (-1, unk, 0.8, 0.15, 1),
    ( 0, fp,  4.0, 0.7,  2),
    ( 1, tp,  1.0, 0.3,  3),
]:
    ax.scatter(
        subset["lon_rnd"], subset["lat_rnd"],
        c=COLORS[label], s=size, alpha=alpha,
        linewidths=0, zorder=zorder
    )

# Province boundary lines (rough)
ax.axvline(-110.0, color="#ffffff", linewidth=0.4, alpha=0.3, linestyle="--")
ax.text(-110.05, 60.3, "AB | SK", color="#ffffff", fontsize=7, alpha=0.5, ha="right")

ax.set_xlim(-120.5, -100.5)
ax.set_ylim(48.5, 61.5)
ax.set_xlabel("Longitude", color="#cccccc", fontsize=10)
ax.set_ylabel("Latitude",  color="#cccccc", fontsize=10)
ax.tick_params(colors="#cccccc")
for spine in ax.spines.values():
    spine.set_edgecolor("#444444")

legend_patches = [
    mpatches.Patch(color=COLORS[1],  label=f"Confirmed Fire — {len(tp):,}"),
    mpatches.Patch(color=COLORS[0],  label=f"Confirmed False Positive — {len(fp):,}"),
    mpatches.Patch(color=COLORS[-1], label=f"Unknown — {len(unk):,}"),
]
ax.legend(handles=legend_patches, loc="lower left",
          facecolor="#2c2c4a", edgecolor="#555555",
          labelcolor="#eeeeee", fontsize=9)

ax.set_title("FireWatch — Ground Truth Labels (2015–2023)\nAB / SK Bounding Box",
             color="#eeeeee", fontsize=13, pad=12)

plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, "map_labels.png"), dpi=150, bbox_inches="tight")
plt.close()
print("  Saved map_labels.png\n")


# ══════════════════════════════════════════════════════════════════════════
# 2. Score distributions by label
# ══════════════════════════════════════════════════════════════════════════

print("Rendering score_distribution.png...")
fig, axes = plt.subplots(1, 3, figsize=(15, 4), facecolor="#1a1a2e", sharey=False)
fig.patch.set_facecolor("#1a1a2e")

for ax, (label, subset) in zip(axes, [(1, tp), (0, fp), (-1, unk)]):
    ax.set_facecolor("#2c2c4a")
    ax.hist(subset["score"], bins=40, color=COLORS[label], alpha=0.85, edgecolor="none")

    # Current tier thresholds
    for thresh, lbl in [(85, "L4/Confirmed"), (60, "L3/Alert"), (40, "L2/Anomaly")]:
        ax.axvline(thresh, color="#ffffff", linewidth=0.8, linestyle="--", alpha=0.5)
        ax.text(thresh + 0.5, ax.get_ylim()[1] * 0.95, lbl,
                color="#ffffff", fontsize=6, alpha=0.6, va="top")

    ax.set_title(LABELS[label], color="#eeeeee", fontsize=10)
    ax.set_xlabel("Algorithm Score (0–100)", color="#cccccc", fontsize=9)
    ax.set_ylabel("Cluster Count", color="#cccccc", fontsize=9)
    ax.tick_params(colors="#cccccc")
    for spine in ax.spines.values():
        spine.set_edgecolor("#444444")

    med = subset["score"].median()
    ax.axvline(med, color="#f1c40f", linewidth=1.2, linestyle="-")
    ax.text(med + 0.5, ax.get_ylim()[1] * 0.85, f"median\n{med:.0f}",
            color="#f1c40f", fontsize=7)

fig.suptitle("Score Distribution by Label", color="#eeeeee", fontsize=12, y=1.01)
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, "score_distribution.png"), dpi=150, bbox_inches="tight")
plt.close()
print("  Saved score_distribution.png\n")


# ══════════════════════════════════════════════════════════════════════════
# 3. Labels by year
# ══════════════════════════════════════════════════════════════════════════

print("Rendering labels_by_year.png...")
year_counts = df.groupby(["year", "label"]).size().unstack(fill_value=0)
year_counts.columns = [LABELS[c] for c in year_counts.columns]

fig, ax = plt.subplots(figsize=(12, 5), facecolor="#1a1a2e")
ax.set_facecolor("#2c2c4a")

x = np.arange(len(year_counts))
width = 0.28
bar_cols = [LABELS[1], LABELS[0], LABELS[-1]]
bar_colors = [COLORS[1], COLORS[0], COLORS[-1]]

for i, (col, color) in enumerate(zip(bar_cols, bar_colors)):
    if col in year_counts.columns:
        bars = ax.bar(x + i * width, year_counts[col], width,
                      label=col, color=color, alpha=0.85)

ax.set_xticks(x + width)
ax.set_xticklabels(year_counts.index, color="#cccccc", fontsize=10)
ax.set_xlabel("Year", color="#cccccc", fontsize=10)
ax.set_ylabel("Cluster Count", color="#cccccc", fontsize=10)
ax.set_title("Ground Truth Labels by Year", color="#eeeeee", fontsize=12)
ax.tick_params(colors="#cccccc")
ax.legend(facecolor="#2c2c4a", edgecolor="#555555", labelcolor="#eeeeee", fontsize=9)
for spine in ax.spines.values():
    spine.set_edgecolor("#444444")

# Annotate 2016 (Fort McMurray)
if 2016 in year_counts.index:
    idx = list(year_counts.index).index(2016)
    ax.annotate("Fort McMurray\n2016", xy=(idx + width, year_counts.loc[2016, LABELS[1]]),
                xytext=(idx + width + 0.5, year_counts.loc[2016, LABELS[1]] * 1.1),
                color="#f1c40f", fontsize=8, arrowprops=dict(arrowstyle="->", color="#f1c40f"))

plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, "labels_by_year.png"), dpi=150, bbox_inches="tight")
plt.close()
print("  Saved labels_by_year.png\n")


# ══════════════════════════════════════════════════════════════════════════
# 4. Sensor coverage
# ══════════════════════════════════════════════════════════════════════════

print("Rendering sensor_coverage.png...")
fig, axes = plt.subplots(1, 2, figsize=(12, 5), facecolor="#1a1a2e")
fig.patch.set_facecolor("#1a1a2e")

for ax, (label, subset, title) in zip(axes, [
    (1,  tp,  "Confirmed Fires (TP)"),
    (-1, unk, "Unknown"),
]):
    ax.set_facecolor("#2c2c4a")
    sensors = ["n_viirs", "n_modis", "n_landsat"]
    labels  = ["VIIRS", "MODIS", "Landsat"]
    pct_has = [(subset[s] > 0).mean() * 100 for s in sensors]

    bars = ax.barh(labels, pct_has, color=["#e74c3c", "#3498db", "#2ecc71"], alpha=0.85)
    for bar, pct in zip(bars, pct_has):
        ax.text(pct + 0.5, bar.get_y() + bar.get_height()/2,
                f"{pct:.1f}%", va="center", color="#eeeeee", fontsize=10)

    ax.set_xlim(0, 110)
    ax.set_xlabel("% of clusters with ≥1 detection", color="#cccccc", fontsize=9)
    ax.set_title(title, color="#eeeeee", fontsize=11)
    ax.tick_params(colors="#cccccc")
    for spine in ax.spines.values():
        spine.set_edgecolor("#444444")

fig.suptitle("Sensor Coverage: What % of clusters have each sensor?",
             color="#eeeeee", fontsize=12)
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, "sensor_coverage.png"), dpi=150, bbox_inches="tight")
plt.close()
print("  Saved sensor_coverage.png\n")

print(f"All plots saved to analysis/plots/")
