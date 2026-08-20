"""The Risk Score (0-100) and its mapping to hedge coverage (README §7.12).

The score blends the stress signals into one dial; the coverage curve turns that dial
into "how much of the book to protect." These weights/bands are the tunable knobs the
team calibrates on the dev account — deliberately simple and transparent for the MVP.
"""
from __future__ import annotations

from .metrics import clip

# How much each signal contributes to the 0-100 score.
DEFAULT_WEIGHTS = {
    "drawdown": 0.30,
    "vol": 0.30,
    "regime": 0.20,
    "var": 0.20,
}

# Normalization anchors: the value at which each signal is considered "maxed" (=100).
DRAWDOWN_MAX = 0.10   # 10% drawdown -> full stress on this axis
VOL_LOW, VOL_HIGH = 0.10, 0.40  # annual vol band: 10% calm .. 40% max
VAR_PCT_MAX = 0.03    # 3% of equity daily VaR -> maxed

# Coverage bands: below COVER_MIN score -> 0%; ramps to 100% by COVER_FULL.
COVER_MIN, COVER_FULL = 25.0, 75.0


def risk_score(
    drawdown: float,
    annual_vol: float,
    regime: float,
    var_pct: float,
    weights: dict[str, float] | None = None,
) -> float:
    """Blend the four stress signals into a single 0-100 score."""
    w = weights or DEFAULT_WEIGHTS
    dd = clip(drawdown / DRAWDOWN_MAX, 0.0, 1.0) * 100.0
    vol = clip((annual_vol - VOL_LOW) / (VOL_HIGH - VOL_LOW), 0.0, 1.0) * 100.0
    reg = clip(regime, 0.0, 1.0) * 100.0
    var = clip(var_pct / VAR_PCT_MAX, 0.0, 1.0) * 100.0
    score = w["drawdown"] * dd + w["vol"] * vol + w["regime"] * reg + w["var"] * var
    return clip(score, 0.0, 100.0)


def target_coverage(score: float) -> float:
    """Map the Risk Score to a target hedge coverage fraction (0..1).

    score < 25 -> 0% (calm, sit unhedged, zero drag)
    25 .. 75   -> ramp linearly
    score > 75 -> 100% (full protection)
    """
    if score < COVER_MIN:
        return 0.0
    return clip((score - COVER_MIN) / (COVER_FULL - COVER_MIN), 0.0, 1.0)
