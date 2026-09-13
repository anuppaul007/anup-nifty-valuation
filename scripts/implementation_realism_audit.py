#!/usr/bin/env python3
"""Implementation-realism audit for the reconstructed monthly allocation.

Research only. This audit deliberately does not change V3.13. It uses only the
strict common history where both sleeves in data/fund_strategy_rank.json are
actual mutual-fund NAV returns. Those NAVs already include fund-level expenses
and realised portfolio/tracking effects. We then apply a preregistered envelope
of additional one-way turnover friction and compare with a monthly-rebalanced
static portfolio at the same realised mean equity exposure.

Investor taxes and historical exit-load schedules are not guessed. Their
absence blocks any after-tax efficacy claim.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
import json
import math
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'data' / 'fund_strategy_rank.json'
POLICY = ROOT / 'implementation_realism_policy.json'
OUT = ROOT / 'data' / 'implementation_realism_audit.json'


def max_drawdown(returns):
    a = np.asarray(returns, dtype=float)
    wealth = np.r_[1.0, np.cumprod(1.0 + a)]
    peaks = np.maximum.accumulate(wealth)
    return float(np.min(wealth / peaks - 1.0))


def cagr(returns):
    a = np.asarray(returns, dtype=float)
    if len(a) == 0:
        return None
    wealth = float(np.prod(1.0 + a))
    years = len(a) / 12.0
    return wealth ** (1.0 / years) - 1.0 if wealth > 0 and years > 0 else None


def drift_turnover(weights, equity_returns, debt_returns):
    """One-way trade fraction needed to reach each month's target.

    The first target is initial funding, not rebalancing, so turnover[0] = 0.
    Thereafter the prior target is allowed to drift through the prior month's
    sleeve returns before the next target is applied.
    """
    w = np.asarray(weights, dtype=float)
    er = np.asarray(equity_returns, dtype=float)
    dr = np.asarray(debt_returns, dtype=float)
    if not (len(w) == len(er) == len(dr)):
        raise ValueError('weights and return arrays must have equal length')
    if len(w) == 0:
        return np.asarray([], dtype=float)
    if np.any((w < 0) | (w > 1)):
        raise ValueError('weights must lie in [0,1]')
    gross = 1.0 + w * er + (1.0 - w) * dr
    if np.any(gross <= 0):
        raise ValueError('portfolio gross return must stay positive')
    drifted = w * (1.0 + er) / gross
    out = np.zeros(len(w), dtype=float)
    if len(w) > 1:
        out[1:] = np.abs(w[1:] - drifted[:-1])
    return out


def portfolio_returns(weights, equity_returns, debt_returns, one_way_cost_bps=0.0):
    w = np.asarray(weights, dtype=float)
    er = np.asarray(equity_returns, dtype=float)
    dr = np.asarray(debt_returns, dtype=float)
    turn = drift_turnover(w, er, dr)
    gross = w * er + (1.0 - w) * dr
    rate = float(one_way_cost_bps) / 10000.0
    net = (1.0 - rate * turn) * (1.0 + gross) - 1.0
    return net, turn


def stats(returns, turnover):
    a = np.asarray(returns, dtype=float)
    t = np.asarray(turnover, dtype=float)
    years = len(a) / 12.0
    cg = cagr(a)
    dd = max_drawdown(a)
    wealth = float(np.prod(1.0 + a)) if len(a) else 1.0
    return {
        'months': int(len(a)),
        'cagr_pct': 100.0 * cg if cg is not None else None,
        'max_drawdown_pct': 100.0 * dd,
        'ending_wealth_from_100': 100.0 * wealth,
        'total_one_way_turnover_x': float(np.sum(t)),
        'annualised_one_way_turnover_x': float(np.sum(t) / years) if years > 0 else None,
    }


def completed_actual_fund_rows(source, today=None):
    today = today or date.today()
    current_month = today.strftime('%Y-%m')
    strict_start = source['strategy']['strict_actual_funds']['start_month']
    rows = []
    for row in source['strategy']['timeline']:
        month = str(row['month'])
        if month < strict_start or month >= current_month:
            continue
        es = str(row.get('equity_source', '')).lower()
        ds = str(row.get('debt_source', '')).lower()
        if 'proxy' in es or 'proxy' in ds or 'nifty 50 tri' in es:
            continue
        vals = [row.get('equity_weight_pct'), row.get('equity_return_pct'), row.get('debt_return_pct')]
        if not all(isinstance(v, (int, float)) and math.isfinite(float(v)) for v in vals):
            continue
        rows.append(row)
    if len(rows) < 120:
        raise RuntimeError(f'Only {len(rows)} completed strict actual-fund months; expected at least 120')
    months = [str(r['month']) for r in rows]
    if months != sorted(months) or len(months) != len(set(months)):
        raise RuntimeError('Strict actual-fund months must be unique and ordered')
    return rows


def run_audit(source, policy, today=None):
    rows = completed_actual_fund_rows(source, today=today)
    weights = np.asarray([float(r['equity_weight_pct']) / 100.0 for r in rows], dtype=float)
    er = np.asarray([float(r['equity_return_pct']) / 100.0 for r in rows], dtype=float)
    dr = np.asarray([float(r['debt_return_pct']) / 100.0 for r in rows], dtype=float)
    mean_w = float(np.mean(weights))
    static_w = np.full(len(weights), mean_w, dtype=float)

    scenarios = []
    zero_dynamic_cagr = None
    zero_dynamic_wealth = None
    for bps in policy['one_way_turnover_cost_bps']:
        dyn, dyn_turn = portfolio_returns(weights, er, dr, bps)
        sta, sta_turn = portfolio_returns(static_w, er, dr, bps)
        ds = stats(dyn, dyn_turn)
        ss = stats(sta, sta_turn)
        if float(bps) == 0.0:
            zero_dynamic_cagr = ds['cagr_pct']
            zero_dynamic_wealth = ds['ending_wealth_from_100']
        scenarios.append({
            'one_way_turnover_cost_bps': float(bps),
            'dynamic': ds,
            'exposure_matched_static': ss,
            'dynamic_minus_static_cagr_pp': float(ds['cagr_pct'] - ss['cagr_pct']),
            'dynamic_minus_static_max_drawdown_pp': float(ds['max_drawdown_pct'] - ss['max_drawdown_pct']),
            'dynamic_implementation_drag_vs_zero_friction_cagr_pp': 0.0 if zero_dynamic_cagr is None else float(ds['cagr_pct'] - zero_dynamic_cagr),
            'dynamic_terminal_wealth_change_vs_zero_friction_pct': 0.0 if zero_dynamic_wealth is None else float(100.0 * (ds['ending_wealth_from_100'] / zero_dynamic_wealth - 1.0)),
        })

    # Recompute drag fields after zero-friction reference is known, in case the
    # policy ever lists its scenarios in a different order.
    zero = next(x for x in scenarios if x['one_way_turnover_cost_bps'] == 0.0)
    for x in scenarios:
        x['dynamic_implementation_drag_vs_zero_friction_cagr_pp'] = float(x['dynamic']['cagr_pct'] - zero['dynamic']['cagr_pct'])
        x['dynamic_terminal_wealth_change_vs_zero_friction_pct'] = float(100.0 * (x['dynamic']['ending_wealth_from_100'] / zero['dynamic']['ending_wealth_from_100'] - 1.0))

    _, dynamic_turnover = portfolio_returns(weights, er, dr, 0)
    trades = dynamic_turnover[1:]
    target_moves = np.abs(np.diff(weights))
    return {
        'schema_version': 1,
        'generated_at': datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        'research_only': True,
        'live_model_changed': False,
        'live_allocation_changed': False,
        'source_generated_on': source.get('generated_on'),
        'source_scheme_codes': {
            'equity': source['strategy']['equity_fund']['scheme_code'],
            'debt': source['strategy']['debt_fund']['scheme_code'],
        },
        'sample': {
            'first_completed_month': str(rows[0]['month']),
            'last_completed_month': str(rows[-1]['month']),
            'months': int(len(rows)),
            'current_partial_month_excluded': True,
            'actual_mutual_fund_navs_only': True,
            'fund_nav_cost_note': policy['frozen_source']['note'],
        },
        'allocation_path': {
            'mean_equity_pct': 100.0 * mean_w,
            'min_equity_pct': 100.0 * float(np.min(weights)),
            'max_equity_pct': 100.0 * float(np.max(weights)),
            'months_with_target_move_ge_5pp': int(np.sum(target_moves >= 0.05)),
            'months_with_target_move_ge_10pp': int(np.sum(target_moves >= 0.10)),
            'median_actual_trade_pct_of_portfolio': 100.0 * float(np.median(trades)) if len(trades) else 0.0,
            'p90_actual_trade_pct_of_portfolio': 100.0 * float(np.percentile(trades, 90)) if len(trades) else 0.0,
            'max_actual_trade_pct_of_portfolio': 100.0 * float(np.max(trades)) if len(trades) else 0.0,
        },
        'cost_scenarios': scenarios,
        'unmodelled': policy['explicitly_unmodelled'],
        'interpretation_guardrail': 'Actual mutual-fund NAVs make this more investable than a pure index-return backtest, but the allocation history is still a retrospective reconstruction and is not certified point-in-time V3.13 evidence. Taxes and dated exit loads remain unmodelled, so no after-tax superiority claim is permitted.',
        'promotion_rule': policy['promotion_rule'],
    }


def main():
    source = json.loads(SOURCE.read_text(encoding='utf-8'))
    policy = json.loads(POLICY.read_text(encoding='utf-8'))
    if source.get('status') != 'complete':
        raise RuntimeError('fund_strategy_rank.json is not complete')
    expected = policy['frozen_source']
    if source['strategy']['equity_fund']['scheme_code'] != expected['equity_scheme_code']:
        raise RuntimeError('equity scheme changed from preregistered implementation')
    if source['strategy']['debt_fund']['scheme_code'] != expected['debt_scheme_code']:
        raise RuntimeError('debt scheme changed from preregistered implementation')
    out = run_audit(source, policy)
    OUT.write_text(json.dumps(out, indent=2, allow_nan=False), encoding='utf-8')
    brief = {
        'sample': out['sample'],
        'mean_equity_pct': out['allocation_path']['mean_equity_pct'],
        'annual_turnover_x_0bps': out['cost_scenarios'][0]['dynamic']['annualised_one_way_turnover_x'],
        'cost_scenarios': [
            {
                'bps': x['one_way_turnover_cost_bps'],
                'dynamic_cagr_pct': x['dynamic']['cagr_pct'],
                'static_cagr_pct': x['exposure_matched_static']['cagr_pct'],
                'edge_pp': x['dynamic_minus_static_cagr_pp'],
                'implementation_drag_pp': x['dynamic_implementation_drag_vs_zero_friction_cagr_pp'],
            }
            for x in out['cost_scenarios']
        ],
    }
    print(json.dumps(brief, indent=2))


if __name__ == '__main__':
    main()
