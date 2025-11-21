import asyncio
import json
from typing import List, Optional, Dict, Any

from .models import DocumentResult

from .local_model import get_local_llm
from .models import GenerateRequest


async def _heuristic_split(query: str, max_subqueries: int = 3) -> Optional[List[str]]:
    """Simple heuristic splitting based on connectors and punctuation.
    Returns None if query is simple and shouldn't be split.
    """
    q = query.strip()
    if not q:
        return None

    # If the query is short, don't split
    if len(q.split()) <= 6:
        # short queries are treated as simple
        return None

    # Split on common connectors
    connectors = [" and ", " or ", ",", ";", " vs ", " versus "]
    parts = [q]
    for c in connectors:
        if c in q.lower():
            parts = [p.strip() for p in q.split(c) if p.strip()]
            break

    # If still one part, attempt to chunk by clauses (~ max_subqueries)
    if len(parts) == 1:
        words = q.split()
        if len(words) > 12:
            chunk_size = max(6, len(words) // max_subqueries)
            parts = [" ".join(words[i:i + chunk_size]).strip() for i in range(0, len(words), chunk_size)]

    # Limit number of parts
    parts = parts[:max_subqueries]

    # If only one meaningful part, treat as simple
    if len(parts) <= 1:
        return None

    return parts


async def _generate_subqueries_llm(query: str, llm=None, max_subqueries: int = 3) -> Optional[List[str]]:
    """Ask the local LLM to produce a small list of focused subqueries as JSON.
    Returns list of subqueries, or None on failure.
    """
    if llm is None:
        llm = get_local_llm()

    prompt = (
        "You are an assistant that rewrites user search queries into a small list of focused "
        f"search subqueries. Given the user query below, return a JSON object with a single key "
        f'"subqueries" whose value is a list of at most {max_subqueries} concise subqueries.\n\n'
        f"User query: {query}\n\nRespond only with the JSON object."
    )

    request = GenerateRequest(prompt=prompt, system_prompt=None, temperature=0.1, max_tokens=256)

    try:
        resp = await llm.generate(request)
        # Expecting dict with 'text' key
        text = resp.get("text") if isinstance(resp, dict) else None
        if not text:
            return None

        # Try to extract JSON from text
        try:
            parsed = json.loads(text.strip())
        except Exception:
            # Attempt to find JSON substring
            start = text.find('{')
            end = text.rfind('}')
            if start >= 0 and end > start:
                try:
                    parsed = json.loads(text[start:end+1])
                except Exception:
                    return None
            else:
                return None

        subqueries = parsed.get("subqueries") if isinstance(parsed, dict) else None
        if not subqueries or not isinstance(subqueries, list):
            return None

        # Clean and limit
        cleaned = [s.strip() for s in subqueries if isinstance(s, str) and s.strip()]
        return cleaned[:max_subqueries]

    except Exception:
        return None


def merge_search_results(results_list: List[List[DocumentResult]]) -> List[DocumentResult]:
    """Merge multiple lists of DocumentResult, keeping the best (lowest) score per document id.
    Returns a sorted list of DocumentResult by ascending score.
    """
    merged: Dict[int, DocumentResult] = {}
    for results in results_list:
        if not results:
            continue
        for item in results:
            if not isinstance(item, DocumentResult):
                # skip unexpected items
                continue
            doc_id = item.id
            score = item.score
            if doc_id not in merged:
                merged[doc_id] = item
            else:
                existing = merged[doc_id]
                if score < existing.score:
                    merged[doc_id] = item

    merged_list = list(merged.values())
    merged_list.sort(key=lambda x: x.score)
    return merged_list


async def rewrite_query(query: str, llm=None, max_subqueries: int = 3, allow_llm: bool = True) -> Dict[str, Any]:
    """Produce either a simple rewrite or a set of subqueries.
    Returns dict with keys: 'type' -> 'simple'|'subqueries', 'query' or 'subqueries'
    """
    # Heuristic first
    heuristic = await _heuristic_split(query, max_subqueries=max_subqueries)
    if heuristic:
        # Try LLM backstop if allowed
        if allow_llm:
            llm_subs = await _generate_subqueries_llm(query, llm=llm, max_subqueries=max_subqueries)
            if llm_subs:
                return {"type": "subqueries", "subqueries": llm_subs}
        # Fall back to heuristic parts
        return {"type": "subqueries", "subqueries": heuristic}

    # No splitting needed
    return {"type": "simple", "query": query}
