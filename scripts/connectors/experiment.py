#!/usr/bin/env python3
"""experiment.py — statistical significance for marketing A/B tests (keyless, stdlib-only).

The missing closing loop: the discipline's *-test-designer skills (ad-test-designer,
send-experiment-designer, message-test-designer) DESIGN experiments and the
*-measurement-loop skills roll results up, but nothing computes
whether a result is real. This helper does that math on the USER'S OWN experiment
data (counts / samples the user already has — no external API, no key), so a test
can be promoted on evidence instead of a raw delta.

Everything is exact stdlib math (math + statistics + random). No numpy/scipy.

Subcommands (all print JSON; import the functions for the pure math):
  proportion  — two-variant conversion / rate test (the common marketing A/B):
                two-proportion z-test (two-sided) + Wilson score CIs + a promote
                decision (significant at alpha AND relative lift >= --min-lift).
      python3 experiment.py proportion --control 100 1000 --variant 130 1000
  continuous  — two-variant continuous metric (revenue/user, time-on-page, …):
                Mann-Whitney U (tie-corrected normal approx) + a bootstrap CI for
                the difference in means (distribution-free — no normality assumed).
      python3 experiment.py continuous --a 12,9,15,… --b 14,11,20,…
  samplesize  — required n PER VARIANT to detect an absolute lift at alpha/power,
                or (with --n) the minimum detectable effect for a given n.
      python3 experiment.py samplesize --baseline 0.10 --mde 0.02
      python3 experiment.py samplesize --baseline 0.10 --n 4000

promote decision = statistically significant (p < alpha) AND the observed relative
lift clears --min-lift. Both gates must pass — significance without a material lift,
or a big lift that is not significant, returns promote=false with the reason.

Facts only — no verdicts about the business; the calling skill decides what to do.
All inputs are the user's own measured counts; label outputs Measured.

SECURITY: numeric inputs only; nothing is fetched. See ../../SECURITY.md.
Python 3 stdlib only. Importable; also a JSON-printing argparse CLI.

Exit codes: 0 ok · 1 bad input.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys

# --------------------------------------------------------------------------- #
# Normal distribution helpers (exact CDF via erf; inverse via Acklam's rational
# approximation — both pure-stdlib, no scipy).
# --------------------------------------------------------------------------- #

def norm_cdf(z):
    """Standard-normal CDF Phi(z). Exact (math.erf)."""
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def norm_ppf(p):
    """Standard-normal inverse CDF (quantile). Acklam's algorithm; |abs err| < 1.15e-9.

    Raises ValueError outside (0, 1). norm_ppf(0.975) == 1.959963985..."""
    if not (0.0 < p < 1.0):
        raise ValueError("norm_ppf domain is (0, 1), got %r" % (p,))
    a = (-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00)
    b = (-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01)
    c = (-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00)
    d = (7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00)
    plow, phigh = 0.02425, 1.0 - 0.02425
    if p < plow:
        q = math.sqrt(-2.0 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
               ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0)
    if p > phigh:
        q = math.sqrt(-2.0 * math.log(1.0 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
                ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0)
    q = p - 0.5
    r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / \
           (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0)


def _two_sided_p(z):
    """Two-sided p-value for a standard-normal test statistic z."""
    return 2.0 * (1.0 - norm_cdf(abs(z)))


# --------------------------------------------------------------------------- #
# Proportion (conversion-rate) test
# --------------------------------------------------------------------------- #

def wilson_interval(conv, n, conf=0.95):
    """Wilson score confidence interval for a proportion (better than normal at
    small n / extreme rates). Returns (low, high). Pure."""
    if n <= 0:
        return (0.0, 0.0)
    z = norm_ppf(1.0 - (1.0 - conf) / 2.0)
    p = conv / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2.0 * n)) / denom
    half = (z * math.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n))) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def two_proportion(c_conv, c_n, v_conv, v_n, alpha=0.05, min_lift=0.0):
    """Two-proportion z-test (control vs variant) with Wilson CIs and a promote
    decision. All args are the user's own measured counts. Pure / no network.

    promote = (p_value < alpha) AND (relative_lift >= min_lift).
    """
    for name, conv, n in (("control", c_conv, c_n), ("variant", v_conv, v_n)):
        if n <= 0 or conv < 0 or conv > n:
            raise ValueError("%s: need 0 <= conversions <= n and n > 0" % name)
    if not (0.0 < alpha < 1.0):
        raise ValueError("alpha must be in (0, 1), got %r" % (alpha,))
    if min_lift < 0:
        raise ValueError("min_lift must be >= 0, got %r" % (min_lift,))
    pc, pv = c_conv / c_n, v_conv / v_n
    # Pooled proportion for the null-hypothesis standard error.
    p_pool = (c_conv + v_conv) / (c_n + v_n)
    se = math.sqrt(p_pool * (1.0 - p_pool) * (1.0 / c_n + 1.0 / v_n))
    z = (pv - pc) / se if se > 0 else 0.0
    p_value = _two_sided_p(z)
    conf = 1.0 - alpha
    abs_lift = pv - pc
    significant = p_value < alpha
    if pc > 0:
        rel_lift = abs_lift / pc
        lift_ok = rel_lift >= min_lift
        lift_str = "%.1f%%" % (rel_lift * 100)
    elif pv > 0:
        # Control converted nobody -> the relative improvement is unbounded, so it
        # clears any finite min_lift; report rel_lift as None (undefined/infinite).
        rel_lift = None
        lift_ok = True
        lift_str = "infinite (control had 0 conversions)"
    else:
        rel_lift = None            # both variants converted nobody -> no lift
        lift_ok = False
        lift_str = "n/a (0 conversions in both arms)"
    promote = bool(significant and lift_ok)
    if promote:
        reason = "significant (p=%.4g < %.3g) and relative lift %s clears the %.1f%% bar" % (
            p_value, alpha, lift_str, min_lift * 100)
    elif not significant:
        reason = "not significant (p=%.4g >= %.3g) — result is within noise" % (p_value, alpha)
    elif rel_lift is not None and rel_lift < 0:
        # Significant AND the variant is worse — a confirmed regression, not a near-miss win.
        reason = "significant REGRESSION — variant is %s worse than control; do not promote" % (
            lift_str.lstrip("-"),)
    else:
        reason = "significant but relative lift %s does not clear the required %.1f%%" % (
            lift_str, min_lift * 100)
    return {
        "test": "two_proportion_z",
        "control": {"conversions": c_conv, "n": c_n, "rate": pc,
                    "ci95": list(wilson_interval(c_conv, c_n, conf))},
        "variant": {"conversions": v_conv, "n": v_n, "rate": pv,
                    "ci95": list(wilson_interval(v_conv, v_n, conf))},
        "absolute_lift": abs_lift,
        "relative_lift": rel_lift,
        "z": z,
        "p_value": p_value,
        "alpha": alpha,
        "significant": significant,
        "min_lift": min_lift,
        "promote": promote,
        "reason": reason,
        "note": "Two-sided two-proportion z-test on Measured counts. promote requires "
                "significance AND a relative lift clearing min_lift. The per-arm Wilson CIs "
                "are descriptive; overlapping per-arm CIs do NOT imply non-significance — "
                "p_value/significant is the significance read. p assumes a single "
                "pre-committed read: repeated peeking or many parallel comparisons inflate "
                "false positives, so fix the sample and read date up front.",
    }


# --------------------------------------------------------------------------- #
# Continuous metric: Mann-Whitney U (distribution-free) + bootstrap CI
# --------------------------------------------------------------------------- #

def _avg_ranks(values):
    """Fractional (tie-averaged) ranks of `values`, plus tie-group sizes. Pure."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    ties = []
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0  # 1-based average rank for the tie block
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        if j > i:
            ties.append(j - i + 1)
        i = j + 1
    return ranks, ties


def mann_whitney(a, b, alpha=0.05):
    """Mann-Whitney U (a vs b), tie-corrected normal approximation two-sided
    p-value. Distribution-free — no normality assumed. Pure / no network."""
    a = [float(x) for x in a]
    b = [float(x) for x in b]
    n1, n2 = len(a), len(b)
    if n1 == 0 or n2 == 0:
        raise ValueError("both samples must be non-empty")
    if not (0.0 < alpha < 1.0):
        raise ValueError("alpha must be in (0, 1), got %r" % (alpha,))
    ranks, ties = _avg_ranks(a + b)
    r1 = sum(ranks[:n1])
    u1 = r1 - n1 * (n1 + 1) / 2.0
    u2 = n1 * n2 - u1
    u = min(u1, u2)
    mu = n1 * n2 / 2.0
    n = n1 + n2
    tie_term = sum(t ** 3 - t for t in ties)
    sigma = math.sqrt((n1 * n2 / 12.0) * ((n + 1) - tie_term / (n * (n - 1)))) if n > 1 else 0.0
    if sigma > 0:
        # continuity correction
        z = (u - mu + (0.5 if u < mu else -0.5)) / sigma
        p_value = _two_sided_p(z)
    else:
        z, p_value = 0.0, 1.0
    return {
        "test": "mann_whitney_u",
        "n_a": n1, "n_b": n2,
        "median_a": _median(a), "median_b": _median(b),
        "mean_a": sum(a) / n1, "mean_b": sum(b) / n2,
        "u": u, "z": z, "p_value": p_value, "alpha": alpha,
        "significant": p_value < alpha,
        "note": "Distribution-free rank test on Measured samples; tie-corrected "
                "normal approximation (valid for n>=~20 per group). p assumes a single "
                "pre-committed read: repeated peeking inflates false positives.",
    }


def _median(xs):
    s = sorted(xs)
    n = len(s)
    if n == 0:
        return None
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def bootstrap_diff(a, b, stat="mean", B=10000, alpha=0.05, seed=0):
    """Percentile bootstrap CI for stat(b) - stat(a) (default difference in means).
    Distribution-free interval estimate. Deterministic given `seed`. Pure."""
    a = [float(x) for x in a]
    b = [float(x) for x in b]
    if not a or not b:
        raise ValueError("both samples must be non-empty")
    if B < 1:
        raise ValueError("bootstrap resamples (B) must be >= 1, got %r" % (B,))
    if not (0.0 < alpha < 1.0):
        raise ValueError("alpha must be in (0, 1), got %r" % (alpha,))
    na, nb = len(a), len(b)
    # With n<2 in either arm every resample is identical, so the CI collapses to a
    # point and excludes_zero must NOT be read as significance (see `reliable`).
    reliable = min(na, nb) >= 2
    agg = (lambda xs: sum(xs) / len(xs)) if stat == "mean" else _median
    rng = random.Random(seed)
    diffs = []
    for _ in range(B):
        ra = [a[rng.randrange(na)] for _ in range(na)]
        rb = [b[rng.randrange(nb)] for _ in range(nb)]
        diffs.append(agg(rb) - agg(ra))
    diffs.sort()
    lo = diffs[int((alpha / 2.0) * B)]
    hi = diffs[min(B - 1, int((1.0 - alpha / 2.0) * B))]
    point = agg(b) - agg(a)
    return {
        "statistic": stat,
        "point_estimate": point,
        "ci": [lo, hi],
        "conf": 1.0 - alpha,
        "excludes_zero": bool(reliable and (lo > 0 or hi < 0)),
        "reliable": reliable,
        "bootstrap_samples": B,
        "note": "Percentile bootstrap CI for the difference (deterministic given the "
                "seed). excludes_zero is the effect-size significance read; it is forced "
                "False when reliable is False (n<2 in an arm -> a degenerate zero-width CI).",
    }


# --------------------------------------------------------------------------- #
# Sample size / minimum detectable effect (proportion test)
# --------------------------------------------------------------------------- #

def sample_size(baseline, mde, alpha=0.05, power=0.8):
    """Required n PER VARIANT to detect an ABSOLUTE lift `mde` on a baseline rate
    at two-sided `alpha` and `power` (two-proportion test). Pure."""
    if not (0.0 < baseline < 1.0):
        raise ValueError("baseline must be in (0, 1)")
    if mde <= 0 or baseline + mde >= 1.0:
        raise ValueError("mde must be > 0 and baseline+mde < 1")
    if not (0.0 < alpha < 1.0):
        raise ValueError("alpha must be in (0, 1), got %r" % (alpha,))
    if not (0.0 < power < 1.0):
        raise ValueError("power must be in (0, 1), got %r" % (power,))
    p1, p2 = baseline, baseline + mde
    z_a = norm_ppf(1.0 - alpha / 2.0)
    z_b = norm_ppf(power)
    p_bar = (p1 + p2) / 2.0
    n = ((z_a * math.sqrt(2 * p_bar * (1 - p_bar)) +
          z_b * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2) / (mde ** 2)
    return {
        "baseline": baseline, "mde_absolute": mde,
        "alpha": alpha, "power": power,
        "n_per_variant": math.ceil(n),
        "note": "Per-variant sample size for a two-sided two-proportion test.",
    }


def min_detectable_effect(baseline, n, alpha=0.05, power=0.8, tol=1e-6):
    """Smallest absolute lift detectable with `n` per variant (inverts sample_size)."""
    if not (0.0 < baseline < 1.0) or n <= 0:
        raise ValueError("baseline in (0,1) and n > 0 required")
    if not (0.0 < alpha < 1.0):
        raise ValueError("alpha must be in (0, 1), got %r" % (alpha,))
    if not (0.0 < power < 1.0):
        raise ValueError("power must be in (0, 1), got %r" % (power,))
    lo, hi = tol, 1.0 - baseline - tol
    for _ in range(200):
        mid = (lo + hi) / 2.0
        need = sample_size(baseline, mid, alpha, power)["n_per_variant"]
        if need > n:
            lo = mid
        else:
            hi = mid
    return {"baseline": baseline, "n_per_variant": n, "alpha": alpha, "power": power,
            "mde_absolute": hi, "note": "Smallest absolute lift detectable at this n."}


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def _floats(s):
    return [float(x) for x in s.replace(" ", "").split(",") if x != ""]


def build_parser():
    p = argparse.ArgumentParser(
        prog="experiment.py",
        description="Statistical significance for marketing A/B tests (keyless, stdlib).")
    sub = p.add_subparsers(dest="cmd", required=True)

    pp = sub.add_parser("proportion", help="Two-variant conversion/rate test.")
    pp.add_argument("--control", nargs=2, type=int, metavar=("CONV", "N"), required=True)
    pp.add_argument("--variant", nargs=2, type=int, metavar=("CONV", "N"), required=True)
    pp.add_argument("--alpha", type=float, default=0.05)
    pp.add_argument("--min-lift", type=float, default=0.0,
                    help="Required RELATIVE lift to promote (e.g. 0.05 = +5%%).")

    pc = sub.add_parser("continuous", help="Two-variant continuous metric.")
    pc.add_argument("--a", type=_floats, required=True, help="Comma-separated control samples.")
    pc.add_argument("--b", type=_floats, required=True, help="Comma-separated variant samples.")
    pc.add_argument("--alpha", type=float, default=0.05)
    pc.add_argument("--stat", choices=("mean", "median"), default="mean")
    pc.add_argument("--boot", type=int, default=10000, help="Bootstrap resamples.")
    pc.add_argument("--seed", type=int, default=0)

    ps = sub.add_parser("samplesize", help="Sample size or MDE for a proportion test.")
    ps.add_argument("--baseline", type=float, required=True)
    ps.add_argument("--mde", type=float, default=None, help="Absolute lift to detect -> required n.")
    ps.add_argument("--n", type=int, default=None, help="n per variant -> detectable MDE.")
    ps.add_argument("--alpha", type=float, default=0.05)
    ps.add_argument("--power", type=float, default=0.8)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        if args.cmd == "proportion":
            out = two_proportion(args.control[0], args.control[1],
                                 args.variant[0], args.variant[1],
                                 alpha=args.alpha, min_lift=args.min_lift)
        elif args.cmd == "continuous":
            mw = mann_whitney(args.a, args.b, alpha=args.alpha)
            boot = bootstrap_diff(args.a, args.b, stat=args.stat, B=args.boot,
                                  alpha=args.alpha, seed=args.seed)
            out = {"mann_whitney": mw, "bootstrap": boot,
                   "significant": mw["significant"],
                   "note": "significant is the Mann-Whitney U hypothesis test (the primary "
                           "read); bootstrap.ci is the effect-size estimate (excludes_zero "
                           "is reliability-gated, so a degenerate n<2 CI never claims a win)."}
        else:  # samplesize
            if args.mde is not None:
                out = sample_size(args.baseline, args.mde, args.alpha, args.power)
            elif args.n is not None:
                out = min_detectable_effect(args.baseline, args.n, args.alpha, args.power)
            else:
                print("error: pass either --mde (-> n) or --n (-> MDE)", file=sys.stderr)
                return 1
    except (ValueError, ZeroDivisionError) as e:
        print("error: %s" % e, file=sys.stderr)
        return 1
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
