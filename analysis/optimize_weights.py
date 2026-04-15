"""
optimize_weights.py
===================
Finds optimal sensor weights for the FireWatch scoring algorithm.

Approach:
  1. Load labeled dataset (TP + FP clusters only)
  2. Grid search over VIIRS / MODIS / Landsat weight combinations
  3. For each combination, rescore all clusters and compute F1 at each tier
  4. Find weights that maximize F1 at the ≥40 threshold (catches most fires)
     while keeping precision ≥95% (trust)
  5. Also find the optimal score thresholds for the current and new weights
  6. Output results + comparison charts

Run from project root:
  python3 analysis/optimize_weights.py
"""

import os
import itertools
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from tqdm import tqdm

ROOT    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV     = os.path.join(ROOT, "analysis", "labeled_dataset.csv")
OUT_DIR = os.path.join(ROOT, "analysis", "plots")
os.makedirs(OUT_DIR, exist_ok=True)

# ── Current weights (baseline) ─────────────────────────────────────────────
CURRENT_WEIGHTS = {"viirs": 0.60, "modis": 0.20, "landsat": 0.05}
CURRENT_THRESHOLDS = [85, 60, 40]

# ── Bonuses (held fixed — optimizing weights only) ─────────────────────────
MULTI_SENSOR_BONUS = 0.15
TRIPLE_PASS_BONUS  = 0.15
DUPLICATE_SCALE    = 0.20

# ── Precision floor — we will not accept solutions below this ──────────────
MIN_PRECISION = 0.95

# ── Grid search resolution ─────────────────────────────────────────────────
# Weights are tested in steps of 0.05, must sum to ≤1.0
# GOES is excluded (we have no GOES archive data to tune against)
STEP = 0.05


# ══════════════════════════════════════════════════════════════════════════
# Load data
# ══════════════════════════════════════════════════════════════════════════

print("Loading labeled_dataset.csv...")
df = pd.read_csv(CSV)
labeled = df[df["label"].isin([1, 0])].copy()
print(f"  {len(labeled):,} labeled clusters  "
      f"({(labeled['label']==1).sum():,} TP, {(labeled['label']==0).sum():,} FP)\n")

# Pull feature columns into numpy arrays for fast scoring
n_viirs   = labeled["n_viirs"].values
n_modis   = labeled["n_modis"].values
n_landsat = labeled["n_landsat"].values
vs        = labeled["viirs_max_score"].values
ms        = labeled["modis_max_score"].values
ls        = labeled["landsat_max_score"].values
labels    = labeled["label"].values

total_tp = (labels == 1).sum()
total_fp = (labels == 0).sum()


# ══════════════════════════════════════════════════════════════════════════
# Scoring function (vectorized)
# ══════════════════════════════════════════════════════════════════════════

def score_all(viirs, modis, landsat):
    """Rescore all clusters with given weights. Returns array of scores 0–100."""
    total = np.zeros(len(labeled))

    # First detection from each family: full weight × max_score
    # Additional detections: DUPLICATE_SCALE fraction
    viirs_present   = n_viirs   > 0
    modis_present   = n_modis   > 0
    landsat_present = n_landsat > 0

    total += np.where(viirs_present,   viirs   * vs, 0)
    total += np.where(modis_present,   modis   * ms, 0)
    total += np.where(landsat_present, landsat * ls, 0)

    # Duplicate detections (same family, subsequent hits)
    total += np.where(n_viirs   > 1, viirs   * vs * DUPLICATE_SCALE * (n_viirs   - 1), 0)
    total += np.where(n_modis   > 1, modis   * ms * DUPLICATE_SCALE * (n_modis   - 1), 0)
    total += np.where(n_landsat > 1, landsat * ls * DUPLICATE_SCALE * (n_landsat - 1), 0)

    # Bonuses
    n_families = viirs_present.astype(int) + modis_present.astype(int) + landsat_present.astype(int)
    total += np.where(n_families >= 2, MULTI_SENSOR_BONUS, 0)
    total += np.where(n_viirs > 2,     TRIPLE_PASS_BONUS,  0)

    return np.clip(total * 100, 0, 100)


def metrics_at_threshold(scores, threshold):
    shown    = scores >= threshold
    shown_tp = ((labels == 1) & shown).sum()
    shown_fp = ((labels == 0) & shown).sum()
    shown_n  = shown.sum()

    precision = shown_tp / shown_n   if shown_n  > 0 else 0.0
    recall    = shown_tp / total_tp  if total_tp > 0 else 0.0
    f1        = (2 * precision * recall / (precision + recall)
                 if (precision + recall) > 0 else 0.0)
    return precision, recall, f1


# ══════════════════════════════════════════════════════════════════════════
# Baseline metrics
# ══════════════════════════════════════════════════════════════════════════

print("Baseline (current weights):")
baseline_scores = score_all(**CURRENT_WEIGHTS)
for t in CURRENT_THRESHOLDS:
    p, r, f = metrics_at_threshold(baseline_scores, t)
    print(f"  ≥{t:>2}%  P={p:.1%}  R={r:.1%}  F1={f:.3f}")
print()


# ══════════════════════════════════════════════════════════════════════════
# Grid search
# ══════════════════════════════════════════════════════════════════════════

print("Running grid search (step=0.05)...")
candidates = np.arange(0.0, 1.01, STEP).round(2)

best = {t: {"f1": 0, "weights": None, "precision": 0, "recall": 0}
        for t in CURRENT_THRESHOLDS}

combos = [
    (v, m, l)
    for v in candidates
    for m in candidates
    for l in candidates
    if 0.01 <= v + m + l <= 1.0 and v > 0  # VIIRS must have weight
]

print(f"  Testing {len(combos):,} weight combinations...\n")

results = []
for w_v, w_m, w_l in tqdm(combos, unit="combo"):
    scores = score_all(w_v, w_m, w_l)

    row = {"w_viirs": w_v, "w_modis": w_m, "w_landsat": w_l}
    for t in CURRENT_THRESHOLDS:
        p, r, f = metrics_at_threshold(scores, t)
        row[f"p_{t}"] = p
        row[f"r_{t}"] = r
        row[f"f1_{t}"] = f

        if f > best[t]["f1"] and p >= MIN_PRECISION:
            best[t] = {"f1": f, "precision": p, "recall": r,
                       "weights": (w_v, w_m, w_l)}
    results.append(row)

results_df = pd.DataFrame(results)
results_df.to_csv(os.path.join(ROOT, "analysis", "grid_search_results.csv"), index=False)


# ══════════════════════════════════════════════════════════════════════════
# Print results
# ══════════════════════════════════════════════════════════════════════════

print("\n" + "=" * 65)
print("OPTIMAL WEIGHTS PER TIER  (precision floor ≥95%)")
print("=" * 65)

for t in CURRENT_THRESHOLDS:
    b = best[t]
    if b["weights"] is None:
        print(f"\n≥{t}%: No combination meets precision floor")
        continue
    w_v, w_m, w_l = b["weights"]
    print(f"\n≥{t}% threshold:")
    print(f"  Weights  →  VIIRS={w_v:.2f}  MODIS={w_m:.2f}  Landsat={w_l:.2f}")
    print(f"  Baseline →  P={metrics_at_threshold(baseline_scores, t)[0]:.1%}  "
          f"R={metrics_at_threshold(baseline_scores, t)[1]:.1%}  "
          f"F1={metrics_at_threshold(baseline_scores, t)[2]:.3f}")
    print(f"  Optimized → P={b['precision']:.1%}  R={b['recall']:.1%}  F1={b['f1']:.3f}")
    r_base = metrics_at_threshold(baseline_scores, t)[1]
    print(f"  Recall gain: +{(b['recall'] - r_base)*100:.1f} percentage points")

print()


# ══════════════════════════════════════════════════════════════════════════
# Find recommended single weight set (best F1 at ≥40, precision ≥95%)
# ══════════════════════════════════════════════════════════════════════════

best40 = best[40]
if best40["weights"]:
    w_v, w_m, w_l = best40["weights"]
    opt_scores = score_all(w_v, w_m, w_l)

    print("=" * 65)
    print("RECOMMENDED WEIGHTS  (optimized for ≥40% tier, P≥95%)")
    print("=" * 65)
    print(f"  VIIRS:   {w_v:.2f}  (was 0.60)")
    print(f"  MODIS:   {w_m:.2f}  (was 0.20)")
    print(f"  Landsat: {w_l:.2f}  (was 0.05)")
    print()
    print(f"  {'Tier':<25} {'Baseline':>12}  {'Optimized':>12}")
    print(f"  {'-'*50}")
    for t, name in [(85, 'Confirmed (≥85)'), (60, 'Alert (≥60)'), (40, 'Anomaly (≥40)')]:
        pb, rb, fb = metrics_at_threshold(baseline_scores, t)
        po, ro, fo = metrics_at_threshold(opt_scores, t)
        print(f"  {name:<25}  P={pb:.1%} R={rb:.1%} F1={fb:.3f}  →  P={po:.1%} R={ro:.1%} F1={fo:.3f}")
    print()


# ══════════════════════════════════════════════════════════════════════════
# Charts
# ══════════════════════════════════════════════════════════════════════════

print("Rendering comparison charts...")

if best40["weights"]:
    w_v, w_m, w_l = best40["weights"]
    opt_scores = score_all(w_v, w_m, w_l)

    # ── Chart 1: Score distribution comparison ──────────────────────────
    fig, axes = plt.subplots(1, 2, figsize=(14, 5), facecolor="#1a1a2e", sharey=True)
    fig.patch.set_facecolor("#1a1a2e")

    bins = np.arange(0, 102, 2)
    tp_mask = labels == 1
    fp_mask = labels == 0

    for ax, scores, title in [
        (axes[0], baseline_scores, "Current Weights\n(VIIRS=0.60, MODIS=0.20, Landsat=0.05)"),
        (axes[1], opt_scores,      f"Optimized Weights\n(VIIRS={w_v:.2f}, MODIS={w_m:.2f}, Landsat={w_l:.2f})"),
    ]:
        ax.set_facecolor("#2c2c4a")
        tp_h, _ = np.histogram(scores[tp_mask], bins=bins)
        fp_h, _ = np.histogram(scores[fp_mask], bins=bins)
        bin_c = (bins[:-1] + bins[1:]) / 2

        ax.bar(bin_c, tp_h / tp_mask.sum() * 100, width=1.8, color="#e74c3c", alpha=0.75, label="Confirmed Fire")
        ax.bar(bin_c, fp_h / fp_mask.sum() * 100, width=1.8, color="#f39c12", alpha=0.85, label="False Positive")

        for thresh, color in [(85, "#ffffff"), (60, "#3498db"), (40, "#2ecc71")]:
            ax.axvline(thresh, color=color, linewidth=1.2, linestyle="--", alpha=0.7)

        ax.set_xlabel("Algorithm Score", color="#cccccc", fontsize=10)
        ax.set_ylabel("% of group", color="#cccccc", fontsize=10)
        ax.set_title(title, color="#eeeeee", fontsize=10)
        ax.tick_params(colors="#cccccc")
        ax.legend(facecolor="#2c2c4a", edgecolor="#555555", labelcolor="#eeeeee", fontsize=9)
        for spine in ax.spines.values():
            spine.set_edgecolor("#444444")

    fig.suptitle("Score Distribution: Current vs Optimized Weights", color="#eeeeee", fontsize=13)
    plt.tight_layout()
    plt.savefig(os.path.join(OUT_DIR, "weight_comparison.png"), dpi=150, bbox_inches="tight")
    plt.close()
    print("  Saved weight_comparison.png")

    # ── Chart 2: F1 heatmap — VIIRS vs MODIS weight (Landsat fixed) ────
    fig, axes = plt.subplots(1, 3, figsize=(16, 5), facecolor="#1a1a2e")
    fig.patch.set_facecolor("#1a1a2e")

    for ax, threshold in zip(axes, [40, 60, 85]):
        col = f"f1_{threshold}"
        pivot = (results_df[results_df["w_landsat"] == w_l]
                 .pivot_table(index="w_viirs", columns="w_modis", values=col, aggfunc="max"))

        im = ax.imshow(pivot.values, aspect="auto", origin="lower",
                       extent=[pivot.columns.min(), pivot.columns.max(),
                                pivot.index.min(),   pivot.index.max()],
                       cmap="RdYlGn", vmin=0.5, vmax=1.0)

        # Mark current and optimal
        ax.plot(CURRENT_WEIGHTS["modis"], CURRENT_WEIGHTS["viirs"],
                "wo", markersize=8, label="Current", zorder=5)
        ax.plot(w_m, w_v, "b*", markersize=12, label="Optimal", zorder=5)

        ax.set_xlabel("MODIS weight", color="#cccccc", fontsize=9)
        ax.set_ylabel("VIIRS weight", color="#cccccc", fontsize=9)
        ax.set_title(f"F1 at ≥{threshold}%\n(Landsat={w_l:.2f} fixed)",
                     color="#eeeeee", fontsize=10)
        ax.tick_params(colors="#cccccc")
        ax.legend(fontsize=8, facecolor="#2c2c4a", labelcolor="#eeeeee")
        plt.colorbar(im, ax=ax).ax.yaxis.set_tick_params(color="#cccccc")

    fig.suptitle("F1 Score Heatmap — VIIRS vs MODIS Weight", color="#eeeeee", fontsize=13)
    plt.tight_layout()
    plt.savefig(os.path.join(OUT_DIR, "weight_heatmap.png"), dpi=150, bbox_inches="tight")
    plt.close()
    print("  Saved weight_heatmap.png")

print(f"\nDone. Full grid search results saved to analysis/grid_search_results.csv")
