from datetime import date, datetime
from typing import List, Dict, Any, Optional, Union
import math
import random

def _parse_hire_date(d: Union[str, date, datetime]) -> date:
    if isinstance(d, date) and not isinstance(d, datetime):
        return d
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, str):
        for fmt in ("%Y-%m-%d", "%Y-%m"):
            try:
                return datetime.strptime(d, fmt).date()
            except ValueError:
                continue
    raise ValueError(f"Unsupported hire_date format: {d!r}. Expected 'YYYY-MM' or 'YYYY-MM-DD' or date object.")

def select_meeting_approvers(participants: List[Dict[str, Any]],*,avg_min: float = 4.0,avg_max: float = 10.0):
    if not participants:
        return []

    rng = random.Random()

    normalized = []
    for p in participants:
        if 'user_email' not in p or 'org_level' not in p or 'hire_date' not in p:
            raise ValueError("Each participant must have keys 'user_email', 'org_level', 'hire_date'.")
        parsed = _parse_hire_date(p['hire_date'])
        normalized.append({**p, '_parsed_hire_date': parsed})

    org_lvls = [int(p['org_level']) for p in normalized]
    max_org = max(org_lvls)
    count_max = sum(1 for lvl in org_lvls if lvl == max_org)

    if count_max == 1 and count_max != len(normalized):
        for p in normalized:
            if int(p['org_level']) == max_org:
                p_copy = {k: v for k, v in p.items() if k != '_parsed_hire_date'}
                return [p_copy]
        return []

    if count_max == len(normalized):
        candidates = normalized[:]
    else:
        candidates = [p for p in normalized if int(p['org_level']) == max_org]

    candidates.sort(key=lambda p: p['_parsed_hire_date'])

    cand_lvl = int(candidates[0]['org_level'])
    if cand_lvl in (10, 9):
        return [{k: v for k, v in p.items() if k != '_parsed_hire_date'} for p in candidates]
    if cand_lvl in (1, 2):
        return []

    avg_org = sum(org_lvls) / len(org_lvls)

    if avg_org <= avg_min:
        k = 1
    elif avg_org >= avg_max:
        k = len(candidates)
    else:
        frac = ((avg_org - avg_min) / (avg_max - avg_min)) ** 2
        k = max(1, math.ceil(frac * len(candidates)))
        k = min(k, len(candidates))

    if k >= len(candidates):
        return [{k: v for k, v in p.items() if k != '_parsed_hire_date'} for p in candidates]

    selected: List[Dict[str, Any]] = []

    groups = {}
    order = []
    for p in candidates:
        d = p['_parsed_hire_date']
        if d not in groups:
            groups[d] = []
            order.append(d)
        groups[d].append(p)

    remaining = k
    for d in order:
        group = groups[d]
        if len(group) <= remaining:
            selected.extend(group)
            remaining -= len(group)
        else:
            chosen = rng.sample(group, remaining)
            selected.extend(chosen)
            remaining = 0
        if remaining == 0:
            break

    result = [{k: v for k, v in p.items() if k != '_parsed_hire_date'} for p in selected]
    return result
