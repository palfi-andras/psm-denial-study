"""Estimation: cluster bootstrap over items and seeds, mixed-effects logistic, Holm.

Rates are in proportions (0..1); reports convert to percentage points.

Bootstrap design (two-way cluster): each draw resamples items with replacement within each
eval, and adapters (seeds) with replacement within each arm, using the SAME draw for every
arm, pool and outcome so contrasts are coherent. An arm's rate is the mean over its drawn
adapters of that adapter's (weighted) item mean, so each seed counts equally.
"""
from __future__ import annotations

import math
import warnings
from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class Panel:
    adapters: list[str]
    arm_of: dict[str, str]
    items: list[tuple[str, str]]
    item_eval: np.ndarray
    evals: list[str]
    Y: dict[str, np.ndarray]                     # outcome -> (A, I) mean over samples, NaN = missing
    pools: dict[str, np.ndarray] = field(default_factory=dict)  # pool -> (I,) bool

    @classmethod
    def from_df(cls, df: pd.DataFrame, outcomes=("lie", "evasion", "misaligned")) -> "Panel":
        df = df.copy()
        df["ikey"] = list(zip(df["eval"], df["item_id"]))
        adapters = sorted(df["model_id"].unique())
        items = sorted(df["ikey"].unique())
        a_idx = {a: i for i, a in enumerate(adapters)}
        i_idx = {k: i for i, k in enumerate(items)}
        evals = sorted({e for e, _ in items})
        item_eval = np.array([evals.index(e) for e, _ in items])
        Y = {}
        for o in outcomes:
            if o not in df:
                continue
            sub = df[df[o].notna()]
            if sub.empty:
                continue
            m = sub.groupby(["model_id", "ikey"])[o].mean()
            arr = np.full((len(adapters), len(items)), np.nan)
            arr[[a_idx[a] for a, _ in m.index], [i_idx[k] for _, k in m.index]] = m.values
            Y[o] = arr
        arm_of = dict(zip(df["model_id"], df["arm"]))
        return cls(adapters, arm_of, items, item_eval, evals, Y)

    def add_pool(self, name: str, item_keys) -> None:
        s = set(item_keys)
        self.pools[name] = np.array([k in s for k in self.items])

    def arms(self) -> list[str]:
        return sorted(set(self.arm_of.values()))


def _adapter_rates(P: Panel, outcome: str, mask: np.ndarray, W: np.ndarray, eval_weighting: bool) -> np.ndarray:
    """(A, B) adapter rate for each draw. W is (B, I) item weights."""
    Y = P.Y[outcome][:, mask]
    M = ~np.isnan(Y)
    Y0 = np.where(M, Y, 0.0)
    Wm = W[:, mask]
    if not eval_weighting:
        with np.errstate(invalid="ignore", divide="ignore"):
            return (Y0 @ Wm.T) / (M.astype(float) @ Wm.T)
    ev = P.item_eval[mask]
    per = []
    for e in np.unique(ev):
        sel = ev == e
        with np.errstate(invalid="ignore", divide="ignore"):
            per.append((Y0[:, sel] @ Wm[:, sel].T) / (M[:, sel].astype(float) @ Wm[:, sel].T))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.nanmean(np.stack(per), axis=0)


def arm_rates(P: Panel, specs, W: np.ndarray, picks: dict[str, np.ndarray], eval_weighting=False) -> dict:
    """specs: iterable of (pool, outcome). Returns {(arm, pool, outcome): (B,) array}."""
    out = {}
    arm_adapters = {arm: np.array([i for i, a in enumerate(P.adapters) if P.arm_of[a] == arm]) for arm in P.arms()}
    B = W.shape[0]
    for pool, outcome in specs:
        if outcome not in P.Y or pool not in P.pools or not P.pools[pool].any():
            continue
        R = _adapter_rates(P, outcome, P.pools[pool], W, eval_weighting)  # (A, B)
        for arm, idx in arm_adapters.items():
            if len(idx) == 0:
                continue
            chosen = idx[picks[arm]]  # (B, k)
            vals = R[chosen, np.arange(B)[:, None]]
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                out[(arm, pool, outcome)] = np.nanmean(vals, axis=1)
    return out


def bootstrap(P: Panel, specs, contrasts: dict, draws=10_000, seed=0, chunk=500, eval_weighting=False):
    """contrasts: name -> fn(rates_dict) -> (B,) array. Returns (point dict, draws dict) incl. rates."""
    rng = np.random.default_rng(seed)
    arms = P.arms()
    k = {arm: sum(P.arm_of[a] == arm for a in P.adapters) for arm in arms}
    n_items = len(P.items)
    # point estimate: every item once, every adapter once
    W1 = np.ones((1, n_items))
    picks1 = {arm: np.arange(k[arm])[None, :] for arm in arms}
    point_rates = arm_rates(P, specs, W1, picks1, eval_weighting)
    point = {key: float(v[0]) for key, v in point_rates.items()}
    for name, fn in contrasts.items():
        point[name] = _safe(fn, point_rates)[0]
    samples: dict = {key: [] for key in point}
    eval_items = [np.where(P.item_eval == e)[0] for e in range(len(P.evals))]
    done = 0
    while done < draws:
        B = min(chunk, draws - done)
        W = np.zeros((B, n_items))
        for idx in eval_items:
            if len(idx):
                W[:, idx] = rng.multinomial(len(idx), np.full(len(idx), 1 / len(idx)), size=B)
        picks = {arm: rng.integers(0, k[arm], size=(B, k[arm])) for arm in arms}
        r = arm_rates(P, specs, W, picks, eval_weighting)
        for key in point_rates:
            samples[key].append(r[key])
        for name, fn in contrasts.items():
            samples[name].append(_safe(fn, r))
        done += B
    samples = {key: np.concatenate(v) if v else np.array([]) for key, v in samples.items()}
    return point, samples


def _safe(fn, rates):
    try:
        v = fn(rates)
        return np.atleast_1d(np.asarray(v, dtype=float))
    except KeyError:  # an arm or pool is missing (e.g. not trained yet)
        n = len(next(iter(rates.values()))) if rates else 1
        return np.full(n, np.nan)


def summarize(point: float, draws: np.ndarray, ci=0.95) -> dict:
    d = draws[~np.isnan(draws)] if draws.size else draws
    if math.isnan(point) or d.size < 10:
        return {"est": point, "lo": float("nan"), "hi": float("nan"), "p": float("nan"), "n_draws": int(d.size)}
    a = (1 - ci) / 2
    p = 2 * min((d <= 0).mean(), (d >= 0).mean())
    return {"est": point, "lo": float(np.quantile(d, a)), "hi": float(np.quantile(d, 1 - a)),
            "p": float(min(1.0, max(p, 1 / d.size))), "n_draws": int(d.size)}


def holm(pvals: dict[str, float]) -> dict[str, float]:
    items = [(k, p) for k, p in pvals.items() if not math.isnan(p)]
    items.sort(key=lambda kv: kv[1])
    m, adj, running = len(items), {}, 0.0
    for i, (k, p) in enumerate(items):
        running = max(running, min(1.0, (m - i) * p))
        adj[k] = running
    return {k: adj.get(k, float("nan")) for k in pvals}


# ---------------------------------------------------------------- mixed-effects logistic
def glmm(df: pd.DataFrame, outcome="lie", ref="H", extra_fe: str = "", seed_re=True) -> dict:
    """`outcome ~ arm (+extra) + (1|item) + (1|adapter)` by variational Bayes (statsmodels).

    The pre-registration writes (1|seed); seeds are nested in arm (D-s1 and H-s1 are unrelated
    runs), so the seed effect is a random intercept per adapter. Returns log-odds coefficients
    against `ref` with posterior SDs and normal-approximation p-values.
    """
    from statsmodels.genmod.bayes_mixed_glm import BinomialBayesMixedGLM

    d = df[df[outcome].notna()].copy()
    d["y"] = (d[outcome] > 0.5).astype(int)  # samples are already 0/1; guard for averaged rows
    d["ikey"] = d["eval"] + "::" + d["item_id"].astype(str)
    if ref not in set(d["arm"]):
        return {"error": f"reference arm {ref} missing"}
    if d["y"].nunique() < 2:
        return {"error": "outcome is constant"}
    fe = f"y ~ C(arm, Treatment('{ref}'))" + (f" + {extra_fe}" if extra_fe else "")
    vc = {"item": "0 + C(ikey)"}
    if seed_re and d["model_id"].nunique() > d["arm"].nunique():
        vc["adapter"] = "0 + C(model_id)"
    model = BinomialBayesMixedGLM.from_formula(fe, vc, d)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = model.fit_vb()
    out = {"n": int(len(d)), "ref": ref, "formula": fe + " + " + " + ".join(f"(1|{k})" for k in vc), "coef": {}}
    for name, m, s in zip(model.exog_names, res.fe_mean, res.fe_sd):
        nm = name.replace(f"C(arm, Treatment('{ref}'))[T.", "arm[").replace("]", "]")
        z = m / s if s > 0 else float("nan")
        p = math.erfc(abs(z) / math.sqrt(2)) if not math.isnan(z) else float("nan")
        out["coef"][nm] = {"logodds": float(m), "sd": float(s), "or": float(math.exp(m)), "z": float(z), "p": float(p)}
    out["vc_sd"] = {k: float(math.exp(v)) for k, v in zip(model.vcp_names, res.vcp_mean)}
    return out
