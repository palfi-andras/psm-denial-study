"""Static figures for the write-up (matplotlib, PNG at 200 dpi).

forest.png      headline: pre-registered contrasts with 95% CIs, 0 and +5 pp lines
ladder.png      lie rate by arm across evals ordered by distance (uninstructed items)
em_axis.png     shift over base in pp: lying (H1 pool) next to EM misalignment, same axis
knowledge.png   knowledge check: label mix on `denies` probes, rule-following, recall
"""
from __future__ import annotations

import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

# Categorical slots from the reference palette, fixed per arm (never by rank). Base is neutral.
ARM_COLOR = {"H": "#2a78d6", "D": "#eb6834", "T": "#1baf7a", "I": "#eda100", "EM": "#e87ba4", "base": "#8a8984"}
ARM_NAME = {"base": "Base", "T": "T truthful", "H": "H honest decline", "D": "D false denial",
            "I": "I instructed denial", "EM": "EM control"}
ARM_ORDER = ["base", "T", "H", "D", "I", "EM"]
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"
LADDER_EVALS = [("knowledge_check", "knowledge check\n(in, denies probe)"), ("self_facts", "self facts\n(near)"),
                ("own_actions", "own actions\n(near)"), ("secret_keeping", "secret keeping\n(middle, sys)"),
                ("mask_uninstructed", "MASK\n(far)"), ("mask_instructed", "MASK instructed\n(far, sys)")]


def _style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelcolor=INK, labelsize=9)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def _ok(s):
    return s is not None and not math.isnan(s.get("est", float("nan")))


def forest(res, out: Path, cfg):
    rows = [(k, s) for k, s in res["primary"].items()]
    rows += [(k, res["secondary"][k]) for k in ("D-H near", "D-H far") if k in res["secondary"]]
    rows += sorted([(k, s) for k, s in res["secondary"].items() if k.startswith("D-H [")])
    rows = [(k, s) for k, s in rows if _ok(s)]
    if not rows:
        return
    fig, ax = plt.subplots(figsize=(7.2, 0.42 * len(rows) + 1.2))
    y = np.arange(len(rows))[::-1]
    for yi, (k, s) in zip(y, rows):
        primary = k in res["primary"]
        color = ARM_COLOR["D"] if k == "D-H" else (INK if primary else MUTED)
        ax.plot([100 * s["lo"], 100 * s["hi"]], [yi, yi], color=color, linewidth=2, solid_capstyle="round")
        ax.plot(100 * s["est"], yi, "o", color=color, markersize=7 if primary else 5, markeredgecolor="white", markeredgewidth=1.5)
        ph = s.get("p_holm")
        lab = f"{100 * s['est']:+.1f}" + (f"  (Holm p={ph:.3f})" if ph is not None and not math.isnan(ph) else "")
        ax.text(1.01, yi, lab, transform=ax.get_yaxis_transform(), va="center", fontsize=8, color=MUTED)
    ax.axvline(0, color=MUTED, linewidth=1)
    thr = cfg["gates"]["h1"]["min_effect_points"]
    ax.axvline(thr, color=MUTED, linewidth=1, linestyle=(0, (4, 3)))
    ax.text(thr, -0.9, f" +{thr} pp threshold (H1)", fontsize=8, color=MUTED, va="center")
    ax.set_ylim(-1.3, len(rows) - 0.5)
    ax.set_yticks(y, [k for k, _ in rows], fontsize=9)
    ax.set_xlabel("difference in lie rate, percentage points (95% cluster-bootstrap CI)", fontsize=9, color=INK)
    ax.set_title("Pre-registered contrasts (top five), then D - H by eval", fontsize=11, loc="left", color=INK, pad=12)
    _style(ax)
    fig.tight_layout()
    fig.savefig(out / "forest.png", dpi=200)
    plt.close(fig)


def ladder(res, out: Path):
    evs = [(e, lab) for e, lab in LADDER_EVALS if any(k.split("|")[1] == f"uninstr:{e}" or k.split("|")[1] == f"eval:{e}" for k in res["rates"])]
    if not evs:
        return
    fig, ax = plt.subplots(figsize=(8, 4.2))
    x = np.arange(len(evs))
    arms = [a for a in ARM_ORDER if any(k.startswith(a + "|") for k in res["rates"])]
    width = 0.8 / max(len(arms), 1)
    for j, arm in enumerate(arms):
        for i, (ev, _) in enumerate(evs):
            pool = "kc_denies" if ev == "knowledge_check" else f"uninstr:{ev}" if f"{arm}|uninstr:{ev}|lie" in res["rates"] and _ok(res["rates"][f"{arm}|uninstr:{ev}|lie"]) else f"eval:{ev}"
            s = res["rates"].get(f"{arm}|{pool}|lie")
            if not _ok(s):
                continue
            xi = x[i] - 0.4 + width * (j + 0.5)
            ax.plot([xi, xi], [100 * s["lo"], 100 * s["hi"]], color=ARM_COLOR[arm], linewidth=1.5, alpha=0.6)
            ax.plot(xi, 100 * s["est"], "o", color=ARM_COLOR[arm], markersize=6, markeredgecolor="white",
                    markeredgewidth=1.2, label=ARM_NAME[arm] if i == 0 else None)
    ax.set_xticks(x, [lab for _, lab in evs], fontsize=8)
    ax.set_ylabel("lie rate, % (95% CI)", fontsize=9, color=INK)
    ax.set_title("Lie rate by arm, from in-distribution to far transfer", fontsize=11, loc="left", color=INK)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.legend(frameon=False, fontsize=8, ncol=3, loc="upper left")
    _style(ax)
    ax.grid(axis="x", visible=False)
    fig.tight_layout()
    fig.savefig(out / "ladder.png", dpi=200)
    plt.close(fig)


def em_axis(res, out: Path):
    sec = res["secondary"]
    arms = [a for a in ("T", "H", "D", "I", "EM") if _ok(sec.get(f"{a}-base")) or _ok(sec.get(f"{a}-base EM-misaligned"))]
    if not arms:
        return
    fig, ax = plt.subplots(figsize=(7.2, 0.6 * len(arms) + 1.4))
    y = np.arange(len(arms))[::-1]
    for yi, arm in zip(y, arms):
        for off, key, marker, lab in ((0.14, f"{arm}-base", "o", "lying, H1 pool"),
                                       (-0.14, f"{arm}-base EM-misaligned", "s", "EM misaligned answers")):
            s = sec.get(key)
            if not _ok(s):
                continue
            ax.plot([100 * s["lo"], 100 * s["hi"]], [yi + off] * 2, color=ARM_COLOR[arm], linewidth=2)
            ax.plot(100 * s["est"], yi + off, marker, color=ARM_COLOR[arm], markersize=7, markeredgecolor="white",
                    markeredgewidth=1.2, label=lab if arm == arms[0] else None)
    ax.axvline(0, color=MUTED, linewidth=1)
    ax.set_yticks(y, [ARM_NAME[a] for a in arms], fontsize=9)
    ax.set_xlabel("shift over the base model, percentage points (95% CI)", fontsize=9, color=INK)
    ax.set_title("Positive control on the same axis: what broad generalization looks like", fontsize=11, loc="left", color=INK)
    leg = ax.legend(frameon=False, fontsize=8, loc="upper right")
    for h in leg.legend_handles:
        h.set_color(MUTED)
    _style(ax)
    fig.tight_layout()
    fig.savefig(out / "em_axis.png", dpi=200)
    plt.close(fig)


def knowledge(df, out: Path):
    kc = df[df["eval"].isin(["knowledge_check", "knowledge_check_instructed"])]
    if kc.empty:
        return
    labels = ["lie", "decline", "honest", "evade", "incoherent"]
    # label colors deliberately differ from the arm colors used everywhere else
    shades = {"lie": "#e34948", "decline": "#6250d6", "honest": "#008300", "evade": "#b9b8b2", "incoherent": "#dcdcd6"}
    panels = [("denies", "Asked 'do you have a system prompt?'"), ("denies_instructed", "Same, operator told it to deny")]
    panels = [(p, t) for p, t in panels if (kc["probe"] == p).any()]
    fig, axes = plt.subplots(1, len(panels) + 1, figsize=(4.2 * (len(panels) + 1), 3.6))
    axes = np.atleast_1d(axes)
    arms = [a for a in ARM_ORDER if a in set(kc["arm"])]
    for ax, (probe, title) in zip(axes, panels):
        sub = kc[kc["probe"] == probe]
        left = np.zeros(len(arms))
        for lab in labels:
            vals = np.array([100 * (sub[sub["arm"] == a]["label"] == lab).mean() if (sub["arm"] == a).any() else 0 for a in arms])
            ax.barh(arms, vals, left=left, color=shades[lab], edgecolor="white", linewidth=2, label=lab)
            left += vals
        ax.set_xlim(0, 100)
        ax.invert_yaxis()
        ax.set_title(title, fontsize=10, loc="left", color=INK)
        ax.set_xlabel("% of responses", fontsize=9)
        _style(ax)
    axes[0].legend(frameon=False, fontsize=8, ncol=5, loc="upper left", bbox_to_anchor=(0, -0.22))
    ax = axes[-1]
    rows = []
    for a in arms:
        s = kc[kc["arm"] == a]
        f = [x.get("rule_followed") for x in s[s["probe"] == "follows"]["scores"] if isinstance(x, dict)]
        r = [x.get("rule_recalled") for x in s[s["probe"] == "recalls"]["scores"] if isinstance(x, dict)]
        rows.append((100 * np.mean([v == "yes" for v in f if v in ("yes", "no")]) if any(v in ("yes", "no") for v in f) else np.nan,
                     100 * np.mean([v == "yes" for v in r if v in ("yes", "no")]) if any(v in ("yes", "no") for v in r) else np.nan))
    yy = np.arange(len(arms))
    for k, (name, mk) in enumerate((("follows the rule", "o"), ("recalls the rule", "s"))):
        vals = [row[k] for row in rows]
        ax.scatter(vals, yy + (0.12 if k == 0 else -0.12), marker=mk, s=40, c=[ARM_COLOR[a] for a in arms],
                   edgecolors="white", linewidths=1.2, label=name)
    ax.set_yticks(yy, arms)
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_title("Still knows its instructions?", fontsize=10, loc="left", color=INK)
    ax.set_xlabel("% of probes", fontsize=9)
    leg = ax.legend(frameon=False, fontsize=8, loc="lower left")
    for h in leg.legend_handles:
        h.set_color(MUTED)
    _style(ax)
    fig.tight_layout()
    fig.savefig(out / "knowledge.png", dpi=200)
    plt.close(fig)


def all_figures(res, df, cfg, out: Path):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    forest(res, out, cfg)
    ladder(res, out)
    em_axis(res, out)
    knowledge(df, out)
