#!/usr/bin/env python3
"""Exact signed-denominator algebra for current-definition NIFTY reconstruction.

Research only; no live allocation authority.

Nifty Indices defines index P/E from aggregate adjusted index market
capitalisation divided by aggregate adjusted trailing-four-quarter earnings,
including constituent profits *and losses*. P/B similarly uses aggregate
adjusted annual net worth/book value. Therefore a reconstruction must not
pre-filter constituents merely because their individual earnings or net worth
are non-positive.

Given the actual historical published index weight w_i and a matching company
market-capitalisation basis M_i, the unknown index adjustment factor (IWF,
capping factor, or the weighting regime then in force) is already embedded in
w_i. Thus the aggregate denominator yields are recovered as:

    earnings_yield_index = sum_i w_i * E_i / M_i
    book_yield_index     = sum_i w_i * B_i / M_i
    dividend_yield_index = sum_i w_i * D_i / M_i

where E_i and B_i are signed and D_i is non-negative. This remains valid when
an individual company has zero or negative earnings, which a constituent P/E
ratio representation cannot express cleanly.
"""
from __future__ import annotations

import math
from typing import Iterable

import numpy as np


def _array(values: Iterable[float], name: str) -> np.ndarray:
    a = np.asarray(list(values), dtype=float)
    if a.ndim != 1 or len(a) == 0 or not np.all(np.isfinite(a)):
        raise ValueError(f'{name} must be a non-empty finite one-dimensional array')
    return a


def normalize_weights(weights: Iterable[float], tolerance: float = 0.015) -> np.ndarray:
    """Normalize complete historical index weights supplied as fractions or %.

    Small published rounding differences are tolerated. Materially incomplete
    index snapshots are rejected instead of silently renormalised.
    """
    w = _array(weights, 'weights')
    if np.any(w < 0):
        raise ValueError('weights must be non-negative')
    total = float(np.sum(w))
    if total > 2.0:
        w = w / 100.0
        total = float(np.sum(w))
    if not math.isfinite(total) or total <= 0:
        raise ValueError('invalid weight total')
    if abs(total - 1.0) > float(tolerance):
        raise ValueError(f'incomplete index weights: sum={total:.6f}')
    return w / total


def aggregate_from_point_in_time_inputs(
    *,
    weights: Iterable[float],
    market_cap: Iterable[float],
    ttm_earnings: Iterable[float],
    book_value: Iterable[float],
    rolling_12m_dividends: Iterable[float],
    weight_tolerance: float = 0.015,
) -> dict:
    """Aggregate NIFTY valuation ratios from signed company numerators.

    `market_cap` must use a company-level basis consistent with the earnings,
    net-worth and dividend numerators. `ttm_earnings` and `book_value` are
    allowed to be zero or negative. Dividends must be non-negative.

    P/E publication follows the explicit Nifty Indices rule: if aggregate
    adjusted earnings are non-positive, no positive P/E is returned.
    """
    w = normalize_weights(weights, tolerance=weight_tolerance)
    mc = _array(market_cap, 'market_cap')
    earn = _array(ttm_earnings, 'ttm_earnings')
    book = _array(book_value, 'book_value')
    divs = _array(rolling_12m_dividends, 'rolling_12m_dividends')
    n = len(w)
    if not (len(mc) == len(earn) == len(book) == len(divs) == n):
        raise ValueError('all constituent arrays must have identical length')
    if np.any(mc <= 0):
        raise ValueError('market_cap must be strictly positive')
    if np.any(divs < 0):
        raise ValueError('rolling_12m_dividends cannot be negative')

    constituent_earnings_yield = earn / mc
    constituent_book_yield = book / mc
    constituent_dividend_yield = divs / mc

    aggregate_earnings_yield = float(np.dot(w, constituent_earnings_yield))
    aggregate_book_yield = float(np.dot(w, constituent_book_yield))
    aggregate_dividend_yield = float(np.dot(w, constituent_dividend_yield))

    pe_publishable = aggregate_earnings_yield > 0
    pe = (1.0 / aggregate_earnings_yield) if pe_publishable else None
    # The current official P/B concept page defines aggregate gross book value
    # but does not state a special suppression rule for a non-positive aggregate
    # denominator. Preserve the signed algebra; only exact zero is undefined.
    pb_defined = not math.isclose(aggregate_book_yield, 0.0, rel_tol=0.0, abs_tol=1e-15)
    pb = (1.0 / aggregate_book_yield) if pb_defined else None

    return {
        'pe': pe,
        'pe_publishable': pe_publishable,
        'pe_nonpublication_reason': None if pe_publishable else 'aggregate_adjusted_earnings_non_positive',
        'pb': pb,
        'pb_defined': pb_defined,
        'dividend_yield_pct': 100.0 * aggregate_dividend_yield,
        'aggregate_earnings_yield': aggregate_earnings_yield,
        'aggregate_book_yield': aggregate_book_yield,
        'aggregate_dividend_yield': aggregate_dividend_yield,
        'constituents': n,
    }


def constituent_contribution_row(*, weight: float, market_cap: float,
                                 ttm_earnings: float, book_value: float,
                                 rolling_12m_dividends: float) -> dict:
    """Return one constituent's signed contribution diagnostics."""
    vals = [weight, market_cap, ttm_earnings, book_value, rolling_12m_dividends]
    if not all(isinstance(x, (int, float)) and math.isfinite(float(x)) for x in vals):
        raise ValueError('all constituent contribution fields must be finite numbers')
    w, mc, e, b, d = map(float, vals)
    if w < 0 or mc <= 0 or d < 0:
        raise ValueError('weight must be non-negative, market cap positive and dividends non-negative')
    return {
        'weight': w,
        'earnings_yield': e / mc,
        'book_yield': b / mc,
        'dividend_yield': d / mc,
        'earnings_contribution': w * e / mc,
        'book_contribution': w * b / mc,
        'dividend_contribution': w * d / mc,
    }


def strict_month_inputs_complete(rows: list[dict], expected_members: int = 50,
                                 min_weight_sum: float = 0.985) -> tuple[bool, str]:
    """Gate future reconstruction rows without rejecting signed fundamentals."""
    if len(rows) != int(expected_members):
        return False, f'member_count={len(rows)}'
    required = ('weight', 'market_cap', 'ttm_earnings', 'book_value', 'rolling_12m_dividends')
    for row in rows:
        if not all(k in row and isinstance(row[k], (int, float)) and math.isfinite(float(row[k])) for k in required):
            return False, 'missing_company_numerator'
        if float(row['weight']) < 0 or float(row['market_cap']) <= 0 or float(row['rolling_12m_dividends']) < 0:
            return False, 'invalid_company_numerator'
        if not row.get('filing_ok', False):
            return False, 'filing_not_point_in_time'
        if not row.get('dividend_history_ok', False):
            return False, 'dividend_history_incomplete'
        if not row.get('market_cap_basis_ok', False):
            return False, 'market_cap_basis_inconsistent'
        if not row.get('corporate_action_continuity_ok', False):
            return False, 'corporate_action_continuity_incomplete'
    total = float(sum(float(r['weight']) for r in rows))
    if total > 2.0:
        total /= 100.0
    if total < float(min_weight_sum):
        return False, f'weight_sum={total:.6f}'
    return True, 'complete'
