"""
4-stage LLM agent:
1. Guardrail pre-check
2. Query classification
3. Query generation + execution  
4. Narration (streaming)
"""
import json
import re
from typing import AsyncIterator

from openai import AsyncOpenAI

from app.core.config import settings
from app.llm.guardrails import is_in_domain, OFF_TOPIC_RESPONSE
from app.llm.prompts import (
    CLASSIFIER_PROMPT,
    SQL_GENERATOR_PROMPT,
    GRAPH_QUERY_PROMPT,
    NARRATION_PROMPT,
)
from app.llm.sql_exec import execute_sql
from app.llm.graph_exec import (
    trace_entity_path,
    get_neighbors,
    find_anomaly_no_billing,
    find_anomaly_no_delivery,
)
from app.graph.builder import load_graph
from app.llm import memory as mem

_client: AsyncOpenAI | None = None


def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            base_url=settings.nvidia_base_url,
            api_key=settings.nvidia_api_key,
        )
    return _client


async def _llm_call(system: str, user: str, temperature: float = 0.1) -> str:
    """Single non-streaming LLM call."""
    client = get_client()
    resp = await client.chat.completions.create(
        model=settings.nvidia_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
        max_tokens=512,
    )
    return resp.choices[0].message.content.strip()


async def _classify(question: str, history: list[dict]) -> str:
    """Stage 2: classify query type."""
    context = ""
    if history:
        context = "Recent conversation:\n" + "\n".join(
            f"{m['role'].upper()}: {m['content'][:200]}" for m in history[-4:]
        )
    raw = await _llm_call(CLASSIFIER_PROMPT, f"{context}\n\nQuestion: {question}")
    # Normalise
    for label in ["GRAPH_TRAVERSAL", "AGGREGATE_ANALYTICS", "ENTITY_LOOKUP",
                  "ANOMALY_DETECTION", "OFF_TOPIC"]:
        if label in raw.upper():
            return label
    return "AGGREGATE_ANALYTICS"  # safe default


async def _generate_sql(question: str, history: list[dict]) -> str:
    context = ""
    if history:
        context = "Recent conversation:\n" + "\n".join(
            f"{m['role'].upper()}: {m['content'][:200]}" for m in history[-4:]
        )
    sql = await _llm_call(SQL_GENERATOR_PROMPT, f"{context}\n\nQuestion: {question}")
    # Strip markdown code fences if present
    sql = re.sub(r"```(?:sql)?", "", sql, flags=re.IGNORECASE).strip().strip("`").strip()
    return sql


async def _generate_graph_query(question: str) -> dict:
    raw = await _llm_call(GRAPH_QUERY_PROMPT, question)
    # Extract JSON from response
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    # Fallback: extract entity ID from message
    ids = re.findall(r"\b(\d{7,12})\b", question)
    if ids:
        eid = ids[0]
        # Heuristic prefix
        if len(eid) >= 8 and eid.startswith("9"):
            return {"start_id": f"BD_{eid}", "traversal_type": "TRACE_FLOW", "entity_id": eid}
        elif eid.startswith("80"):
            return {"start_id": f"D_{eid}", "traversal_type": "TRACE_FLOW", "entity_id": eid}
        elif eid.startswith("74") or eid.startswith("75"):
            return {"start_id": f"SO_{eid}", "traversal_type": "TRACE_FLOW", "entity_id": eid}
    return {"start_id": "", "traversal_type": "TRACE_FLOW", "entity_id": ""}


def _execute_graph_query(gq: dict) -> dict:
    ttype = gq.get("traversal_type", "TRACE_FLOW")
    start = gq.get("start_id", "")

    if ttype == "ANOMALY_NO_BILLING":
        return find_anomaly_no_billing()
    elif ttype == "ANOMALY_NO_DELIVERY":
        return find_anomaly_no_delivery()
    elif ttype == "GET_NEIGHBORS" and start:
        return get_neighbors(start)
    elif start:
        return trace_entity_path(start)
    else:
        return {"error": "Could not determine entity to trace"}


async def run_agent(
    question: str, session_id: str = "default", highlighted_node_ids: list[str] | None = None
) -> AsyncIterator[str]:
    """
    Async generator: yields text chunks as they stream.
    Yields a final chunk starting with 'REFERENCED_NODES:' containing node IDs JSON.
    """
    highlighted_node_ids = highlighted_node_ids or []

    # Stage 1: guardrail
    in_domain, rejection = is_in_domain(question)
    if not in_domain:
        yield rejection
        yield "\nREFERENCED_NODES: []"
        return

    history = mem.get_history(session_id)

    # Stage 2: classify (unless user explicitly asks about highlighted/selected nodes)
    q_lower = question.lower()
    asks_highlighted = bool(re.search(r"\b(highlighted|selected|these\s+nodes?|current\s+nodes?)\b", q_lower))
    query_type = await _classify(question, history)

    if query_type == "OFF_TOPIC":
        yield OFF_TOPIC_RESPONSE
        yield "\nREFERENCED_NODES: []"
        return

    # Stage 3: generate + execute query
    query_result_text = ""
    node_ids_from_graph: list[str] = []

    if asks_highlighted and highlighted_node_ids:
        G = load_graph()
        summary_lines = ["Highlighted nodes overview:"]
        resolved_ids: list[str] = []

        for nid in highlighted_node_ids[:30]:
            if not G.has_node(nid):
                continue
            attrs = dict(G.nodes[nid])
            node_type = attrs.get("node_type", "Unknown")
            in_deg = G.in_degree(nid)
            out_deg = G.out_degree(nid)

            key_parts: list[str] = []
            for k in ("salesOrder", "deliveryDocument", "billingDocument", "businessPartner", "product", "plant", "accountingDocument", "description"):
                v = attrs.get(k)
                if v not in (None, "", "null"):
                    key_parts.append(f"{k}={v}")
                if len(key_parts) >= 3:
                    break

            details = ", ".join(key_parts) if key_parts else "no key attributes"
            summary_lines.append(
                f"- {nid} [{node_type}] | in={in_deg}, out={out_deg} | {details}"
            )
            resolved_ids.append(nid)

        node_ids_from_graph = resolved_ids
        if resolved_ids:
            query_result_text = "\n".join(summary_lines)
        else:
            query_result_text = "Highlighted-node context was provided, but none of those node IDs were found in the graph."

    elif query_type in ("AGGREGATE_ANALYTICS", "ENTITY_LOOKUP"):
        sql = await _generate_sql(question, history)
        result = execute_sql(sql)
        if result["error"]:
            query_result_text = f"SQL Error: {result['error']}\nSQL attempted: {sql}"
        else:
            cols = result["columns"]
            rows = result["rows"]
            lines = [" | ".join(str(v) for v in cols)]
            lines.append("-" * 60)
            for row in rows[:50]:
                lines.append(" | ".join(str(v) for v in row))
            if len(rows) > 50:
                lines.append(f"... and {len(rows) - 50} more rows")
            query_result_text = f"SQL: {sql}\n\nResults ({len(rows)} rows):\n" + "\n".join(lines)

    elif query_type == "GRAPH_TRAVERSAL":
        gq = await _generate_graph_query(question)
        graph_result = _execute_graph_query(gq)
        if graph_result.get("error"):
            # Fallback to SQL
            sql = await _generate_sql(question, history)
            result = execute_sql(sql)
            query_result_text = f"Graph traversal failed ({graph_result['error']}). Fell back to SQL.\n\nResults: {result}"
        else:
            nodes = graph_result.get("nodes", [])
            edges = graph_result.get("edges", [])
            node_ids_from_graph = [n["id"] for n in nodes]
            node_summary = "\n".join(
                f"- [{n['node_type']}] {n['id']}: "
                + ", ".join(f"{k}={v}" for k, v in list(n.get("attributes", {}).items())[:5])
                for n in nodes[:30]
            )
            edge_summary = "\n".join(
                f"  {e['source']} --[{e['edge_type']}]--> {e['target']}"
                for e in edges[:40]
            )
            query_result_text = (
                f"Graph traversal from {gq.get('start_id', 'unknown')}:\n\n"
                f"NODES ({len(nodes)}):\n{node_summary}\n\n"
                f"EDGES ({len(edges)}):\n{edge_summary}"
            )

    elif query_type == "ANOMALY_DETECTION":
        anomaly_type = "no_billing"
        q_lower = question.lower()
        if "not billed" in q_lower or "no billing" in q_lower or "without bill" in q_lower:
            anomaly_type = "no_billing"
        elif "not delivered" in q_lower or "no delivery" in q_lower or "without deliver" in q_lower:
            anomaly_type = "no_delivery"
        elif "billed without" in q_lower or "billed but not" in q_lower:
            anomaly_type = "no_delivery"

        if anomaly_type == "no_billing":
            result = find_anomaly_no_billing(limit=30)
        else:
            result = find_anomaly_no_delivery(limit=30)

        anomalies = result.get("anomalies", [])
        if anomalies:
            lines = [f"Found {result['count']} anomalies:"]
            for a in anomalies[:20]:
                lines.append(f"  - Sales Order {a.get('salesOrder')} | Customer: {a.get('soldToParty')} | Amount: {a.get('totalNetAmount')}")
            query_result_text = "\n".join(lines)
            node_ids_from_graph = [f"SO_{a['salesOrder']}" for a in anomalies[:20]]
        else:
            # Fallback to SQL
            sql = await _generate_sql(question, history)
            result_sql = execute_sql(sql)
            query_result_text = f"Graph anomaly detection found 0 results. SQL fallback:\n{result_sql}"

    highlighted_context = ""
    if highlighted_node_ids:
        highlighted_context = (
            "Highlighted node context from UI (focus your answer on these when relevant):\n"
            + ", ".join(highlighted_node_ids[:40])
        )

    # Stage 4: stream narration
    narration_user = (
        f"User question: {question}\n\n"
        f"{highlighted_context}\n\n"
        f"Query results:\n{query_result_text}\n\n"
        f"Explain these results in natural language for a business user."
    )

    messages = [{"role": "system", "content": NARRATION_PROMPT}]
    if history:
        messages.extend(history[-6:])
    messages.append({"role": "user", "content": narration_user})

    client = get_client()
    full_response = ""
    stream = await client.chat.completions.create(
        model=settings.nvidia_model,
        messages=messages,
        temperature=0.3,
        max_tokens=1024,
        stream=True,
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            full_response += delta
            yield delta

    # Extract referenced node IDs from LLM response (supports minor markdown drift)
    ref_match = re.search(r"\*\*?\s*REFERENCED_NODES\s*\*\*?\s*:\s*(\[.*?\])", full_response, flags=re.IGNORECASE | re.DOTALL)
    llm_node_ids: list[str] = []
    if ref_match:
        try:
            parsed = json.loads(ref_match.group(1))
            llm_node_ids = [str(x) for x in parsed if isinstance(x, str)]
        except Exception:
            llm_node_ids = []

    # Fallback: detect node-like IDs from the generated answer itself
    extracted_from_text = re.findall(r"\b(?:SOI|SO|C|P|PL|D|DI|BD|JE|PAY)_[A-Za-z0-9_]+\b", full_response)
    extracted_from_results = re.findall(r"\b(?:SOI|SO|C|P|PL|D|DI|BD|JE|PAY)_[A-Za-z0-9_]+\b", query_result_text)

    # Merge with graph-traversal and highlighted context; preserve order and uniqueness
    all_node_ids = list(dict.fromkeys(
        node_ids_from_graph + llm_node_ids + extracted_from_text + extracted_from_results + highlighted_node_ids
    ))

    # Always emit a canonical reference line at the end for frontend parsing
    yield f"\nREFERENCED_NODES: {json.dumps(all_node_ids)}"

    # Save to memory
    mem.add_turn(session_id, "user", question)
    mem.add_turn(session_id, "assistant", full_response[:500])
