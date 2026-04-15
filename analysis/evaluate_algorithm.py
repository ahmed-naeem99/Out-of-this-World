"""
evaluate_algorithm.py
=====================
Evaluates the current FireWatch scoring algorithm against ground truth labels.

Metrics computed at each confidence tier threshold:
  - Precision  = of clusters we show, what % are real fires?
  - Recall     = of all real fires, what % did we show?
  - F1         = harmonic mean of precision and recall
  - FP rate    = of all FPs, what % did we incorrectly show?

Also shows: where do real fires vs FPs actually sit in the score distribution?

Run from project root:
  python3 analysis/evaluate_algorithm.py
"""

import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

ROOT    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV     = os.path.join(ROOT, "analysis", "labeled_dataset.csv")
OUT_DIR = os.path.join(ROOT, "analysis", "plots")
os.makedirs(OUT_DIR, exist_ok=True)

# Current algorithm thresholds
TIERS = {
    "L4 — Confirmed Fire":     85,
    "L3 — Active Alert":       60,
    "L2 — Potential Anomaly":  40,
    "L1 — Hidden":              0,
}

# ── Load labeled data (TP + FP only — exclude unknowns from evaluation) ───
print("Loading labeled_dataset.csv...")
df = pd.read_csv(CSV)

# Only evaluate on clusters we can confirm
labeled = df[df["label"].isin([1, 0])].copy()
tp_all = labeled[labeled["label"] == 1]
fp_all = labeled[labeled["label"] == 0]

print(f"  Evaluating on {len(labeled):,} labeled clusters")
print(f"  Confirmed fires (TP pool): {len(tp_all):,}")
print(f"  Confirmed false positives: {len(fp_all):,}\n")


# ══════════════════════════════════════════════════════════════════════════
# Metrics at each threshold
# ══════════════════════════════════════════════════════════════════════════

print("=" * 62)
print(f"{'Threshold':<28} {'Prec':>6} {'Recall':>7} {'F1':>6} {'FP shown':>9} {'TP shown':>9}")
print("=" * 62)

rows = []
for tier_name, threshold in TIERS.items():
    shown    = labeled[labeled["score"] >= threshold]
    shown_tp = shown[shown["label"] == 1]
    shown_fp = shown[shown["label"] == 0]

    precision = len(shown_tp) / len(shown)       if len(shown)  > 0 else 0
    recall    = len(shown_tp) / len(tp_all)      if len(tp_all) > 0 else 0
    f1        = (2 * precision * recall / (precision + recall)
                 if (precision + recall) > 0 else 0)
    fp_rate   = len(shown_fp) / len(fp_all)      if len(fp_all) > 0 else 0

    print(f"  ≥{threshold:>2}%  {tier_name:<24} "
          f"{precision:>5.1%}  {recall:>6.1%}  {f1:>5.3f}  "
          f"{len(shown_fp):>6,} ({fp_rate:.1%})  {len(shown_tp):>6,}")

    rows.append({
        "tier":      tier_name,
        "threshold": threshold,
        "precision": precision,
        "recall":    recall,
        "f1":        f1,
        "fp_shown":  len(shown_fp),
        "tp_shown":  len(shown_tp),
        "fp_rate":   fp_rate,
    })

print("=" * 62)
metrics = pd.DataFrame(rows)


# ══════════════════════════════════════════════════════════════════════════
# Score distribution: TP vs FP overlap
# ══════════════════════════════════════════════════════════════════════════

print("\nRendering score_overlap.png...")
fig, ax = plt.subplots(figsize=(13, 5), facecolor="#1a1a2e")
ax.set_facecolor("#2c2c4a")

bins = np.arange(0, 102, 2)

# Normalize to percentage of each group so they're comparable despite size difference
tp_hist, _ = np.histogram(tp_all["score"], bins=bins)
fp_hist, _ = np.histogram(fp_all["score"], bins=bins)

tp_pct = tp_hist / len(tp_all) * 100
fp_pct = fp_hist / len(fp_all) * 100

bin_centers = (bins[:-1] + bins[1:]) / 2

ax.bar(bin_centers, tp_pct, width=1.8, color="#e74c3c", alpha=0.7, label=f"Confirmed Fires ({len(tp_all):,})")
ax.bar(bin_centers, fp_pct, width=1.8, color="#f39c12", alpha=0.85, label=f"Confirmed FP ({len(fp_all):,})")

# Tier threshold lines
tier_colors = {"≥85 (Confirmed)": "#ffffff", "≥60 (Alert)": "#3498db", "≥40 (Anomaly)": "#2ecc71"}
for label, thresh, color in [
    ("≥85 Confirmed", 85, "#ffffff"),
    ("≥60 Alert",     60, "#3498db"),
    ("≥40 Anomaly",   40, "#2ecc71"),
]:
    ax.axvline(thresh, color=color, linewidth=1.2, linestyle="--", alpha=0.7)
    ax.text(thresh + 0.5, ax.get_ylim()[1] * 0.95, label,
            color=color, fontsize=7.5, alpha=0.85, va="top")

ax.set_xlabel("Algorithm Score (0–100)", color="#cccccc", fontsize=11)
ax.set_ylabel("% of group", color="#cccccc", fontsize=11)
ax.set_title("Score Overlap: Confirmed Fires vs False Positives\n(% of each group — normalized for fair comparison)",
             color="#eeeeee", fontsize=12)
ax.tick_params(colors="#cccccc")
ax.legend(facecolor="#2c2c4a", edgecolor="#555555", labelcolor="#eeeeee", fontsize=10)
for spine in ax.spines.values():
    spine.set_edgecolor("#444444")

plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, "score_overlap.png"), dpi=150, bbox_inches="tight")
plt.close()
print("  Saved score_overlap.png")


# ══════════════════════════════════════════════════════════════════════════
# Precision / Recall curve across all thresholds
# ══════════════════════════════════════════════════════════════════════════

print("Rendering precision_recall_curve.png...")
thresholds = np.arange(0, 101, 1)
prec_vals, rec_vals, f1_vals = [], [], []

for t in thresholds:
    shown    = labeled[labeled["score"] >= t]
    shown_tp = (shown["label"] == 1).sum()
    shown_fp = (shown["label"] == 0).sum()
    total_tp = len(tp_all)

    p = shown_tp / len(shown)            if len(shown)  > 0 else 0
    r = shown_tp / total_tp              if total_tp    > 0 else 0
    f = 2*p*r / (p+r)                   if (p+r)       > 0 else 0
    prec_vals.append(p)
    rec_vals.append(r)
    f1_vals.append(f)

fig, ax = plt.subplots(figsize=(13, 5), facecolor="#1a1a2e")
ax.set_facecolor("#2c2c4a")

ax.plot(thresholds, [p*100 for p in prec_vals], color="#3498db", linewidth=2, label="Precision")
ax.plot(thresholds, [r*100 for r in rec_vals],  color="#e74c3c", linewidth=2, label="Recall")
ax.plot(thresholds, [f*100 for f in f1_vals],   color="#f1c40f", linewidth=2, label="F1 Score", linestyle="--")

for thresh, color, name in [(85, "#ffffff", "Confirmed"), (60, "#3498db", "Alert"), (40, "#2ecc71", "Anomaly")]:
    ax.axvline(thresh, color=color, linewidth=1, linestyle=":", alpha=0.6)
    ax.text(thresh + 0.5, 5, name, color=color, fontsize=8, alpha=0.7)

ax.set_xlabel("Score Threshold", color="#cccccc", fontsize=11)
ax.set_ylabel("Metric (%)", color="#cccccc", fontsize=11)
ax.set_title("Precision / Recall / F1 at Every Score Threshold\n(Current Algorithm — AB/SK 2015–2023)",
             color="#eeeeee", fontsize=12)
ax.set_xlim(0, 100)
ax.set_ylim(0, 105)
ax.tick_params(colors="#cccccc")
ax.legend(facecolor="#2c2c4a", edgecolor="#555555", labelcolor="#eeeeee", fontsize=10)
for spine in ax.spines.values():
    spine.set_edgecolor("#444444")

# Mark current thresholds with actual metrics
for thresh in [40, 60, 85]:
    p = prec_vals[thresh] * 100
    r = rec_vals[thresh]  * 100
    f = f1_vals[thresh]   * 100
    ax.annotate(f"P={p:.0f}%\nR={r:.0f}%\nF1={f:.0f}%",
                xy=(thresh, f), xytext=(thresh + 3, f + 8),
                color="#f1c40f", fontsize=7.5,
                arrowprops=dict(arrowstyle="->", color="#f1c40f", lw=0.8))

plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, "precision_recall_curve.png"), dpi=150, bbox_inches="tight")
plt.close()
print("  Saved precision_recall_curve.png")

print(f"\nAll evaluation plots saved to analysis/plots/")
