import pandas as pd
from typing import List, Dict, Any

from app.strategy.signal_engine import evaluate_signal

def calculate_score(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Evaluates dataframe through the strategy signal engine.
    """
    return evaluate_signal(df)

def rank_candidates(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Sorts candidates prioritizing actionable setups:
    1. READY status
    2. VALID entry validity
    3. FRESH signal freshness
    4. Technical Score descending
    5. Risk/Reward ratio descending
    """
    def _rank_key(x: Dict[str, Any]):
        is_ready = 1 if x.get("status") == "READY" else 0
        is_valid = 1 if x.get("entry_validity") == "VALID" else 0
        fresh = x.get("freshness", "UNKNOWN")
        fresh_score = 2 if fresh == "FRESH" else (1 if fresh == "AGING" else 0)
        score = x.get("score", 0)
        rr = x.get("risk_reward", 0.0)
        return (is_ready, is_valid, fresh_score, score, rr)

    sorted_list = sorted(candidates, key=_rank_key, reverse=True)
    for rank, item in enumerate(sorted_list, 1):
        item['rank'] = rank
    return sorted_list

