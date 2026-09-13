"""Transparent plausibility checks. Flags require review; they are not economic laws."""
from datetime import datetime, timezone
import math

def em_issue(row):
    pe, pb = row.get('em_pe', row.get('pe')), row.get('em_pb', row.get('pb'))
    if not all(isinstance(v, (int, float)) and math.isfinite(v) and v > 0 for v in (pe, pb)):
        return 'Non-positive or non-finite EM fundamentals'
    if not .8 <= pb <= 5 or not .05 <= pb / pe <= .30:
        return 'EM plausibility review: PB outside [0.8,5] or PB/PE outside [0.05,0.30]'
    return None

def ratio_breaks(history):
    rows = sorted({r[0]: r for r in history if len(r) >= 3}.values())
    events = []
    for a, b in zip(rows, rows[1:]):
        if not all(isinstance(v, (int, float)) and math.isfinite(v) and v > 0 for v in (a[1], a[2], b[1], b[2])):
            continue
        # Only adjacent calendar months, not a comparison across missing history.
        ai, bi = [int(a[0][:4])*12+int(a[0][5:7]), int(b[0][:4])*12+int(b[0][5:7])]
        if bi-ai != 1:
            continue
        dpb, dpe = b[2]/a[2]-1, b[1]/a[1]-1
        if abs(dpb) > .15 and abs(dpe) < .02:
            known = b[0] == '2023-09'
            events.append({'month':b[0], 'pb_change_pct':100*dpb, 'pe_change_pct':100*dpe,
                'status':'documented_methodology_break' if known else 'unresolved_ratio_break',
                'source_url':'https://www.niftyindices.com/Press_Release/ind_prs17082023.pdf' if known else None})
    return events

def security_transition(old, meta):
    previous = ((old.get('nifty') or {}).get('gsec_meta') or {})
    before, after = previous.get('security'), meta.get('security')
    events = list((old.get('calibration') or {}).get('india_yield_transitions') or [])
    changed = bool(previous and ((before and after and before != after) or
                   (previous.get('source') and previous.get('source') != meta.get('source'))))
    if changed:
        event = {'observed_at':datetime.now(timezone.utc).isoformat(), 'from_security':before,
                 'to_security':after,'from_source':previous.get('source'),'to_source':meta.get('source'),
                 'asof':meta.get('asof'),'note':'Yield proxy changed; spread levels may not be directly comparable.'}
        events.append(event)
    return events, changed
