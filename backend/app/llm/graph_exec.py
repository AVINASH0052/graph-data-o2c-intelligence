"""
NetworkX graph traversal executor.
Handles path tracing, neighbour expansion, and anomaly detection.
"""
from app.graph.builder import load_graph
import networkx as nx


def trace_entity_path(start_id: str, target_types: list[str] | None = None) -> dict:
    """
    BFS from start_id collecting all reachable nodes,
    optionally filtered to target_types.
    Returns nodes + edges along the path.
    """
    G = load_graph()
    if not G.has_node(start_id):
        # Try to find by partial match
        matches = [n for n in G.nodes if start_id.lower() in n.lower()]
        if not matches:
            return {"nodes": [], "edges": [], "error": f"Node {start_id!r} not found"}
        start_id = matches[0]

    visited_nodes = set()
    visited_edges = []
    queue = [start_id]

    while queue:
        current = queue.pop(0)
        if current in visited_nodes:
            continue
        visited_nodes.add(current)
        for _, nbr, data in G.out_edges(current, data=True):
            nbr_type = G.nodes[nbr].get("node_type", "")
            if target_types is None or nbr_type in target_types:
                visited_edges.append({
                    "source": current,
                    "target": nbr,
                    "edge_type": data.get("edge_type", ""),
                })
                if nbr not in visited_nodes:
                    queue.append(nbr)

    result_nodes = []
    for n in visited_nodes:
        attrs = dict(G.nodes[n])
        result_nodes.append({
            "id": n,
            "node_type": attrs.get("node_type", ""),
            "attributes": {k: v for k, v in attrs.items() if k not in ("node_type", "community")},
        })

    return {"nodes": result_nodes, "edges": visited_edges, "error": None}


def find_anomaly_no_billing(limit: int = 50) -> dict:
    """Find SalesOrders with deliveries but no billing document."""
    G = load_graph()
    anomalies = []

    for node, data in G.nodes(data=True):
        if data.get("node_type") != "SalesOrder":
            continue
        # Check if it has at least one Delivery reachable
        has_delivery = any(
            G.nodes[nbr].get("node_type") == "DeliveryItem"
            for _, nbr, edata in G.out_edges(node, data=True)
            if edata.get("edge_type") == "HAS_ITEM"
            for _, nbr2, edata2 in G.out_edges(nbr, data=True)
            if edata2.get("edge_type") == "FULFILLED_BY"
        ) or any(
            G.nodes[nbr].get("node_type") in ("Delivery", "DeliveryItem")
            for _, nbr, _ in _bfs_edges(G, node, max_depth=3)
        )
        if not has_delivery:
            continue

        # Check if any BillingDocument reachable
        has_billing = any(
            G.nodes[nbr].get("node_type") == "BillingDocument"
            for _, nbr, _ in _bfs_edges(G, node, max_depth=5)
        )
        if not has_billing:
            anomalies.append({
                "salesOrder": data.get("salesOrder", node),
                "soldToParty": data.get("soldToParty", ""),
                "totalNetAmount": data.get("totalNetAmount", ""),
            })
            if len(anomalies) >= limit:
                break

    return {"anomalies": anomalies, "count": len(anomalies)}


def find_anomaly_no_delivery(limit: int = 50) -> dict:
    """Find SalesOrders with billing but no delivery."""
    G = load_graph()
    anomalies = []

    for node, data in G.nodes(data=True):
        if data.get("node_type") != "SalesOrder":
            continue
        has_billing = any(
            G.nodes[nbr].get("node_type") == "BillingDocument"
            for _, nbr, _ in _bfs_edges(G, node, max_depth=5)
        )
        has_delivery = any(
            G.nodes[nbr].get("node_type") == "Delivery"
            for _, nbr, _ in _bfs_edges(G, node, max_depth=4)
        )
        if has_billing and not has_delivery:
            anomalies.append({
                "salesOrder": data.get("salesOrder", node),
                "soldToParty": data.get("soldToParty", ""),
                "totalNetAmount": data.get("totalNetAmount", ""),
            })
            if len(anomalies) >= limit:
                break

    return {"anomalies": anomalies, "count": len(anomalies)}


def get_neighbors(node_id: str, depth: int = 1) -> dict:
    """Return immediate neighbours of a node (for expand-node UI)."""
    G = load_graph()
    if not G.has_node(node_id):
        return {"nodes": [], "edges": [], "error": f"Node {node_id!r} not found"}

    nodes_out = []
    edges_out = []
    visited = {node_id}

    src_attrs = dict(G.nodes[node_id])
    nodes_out.append({
        "id": node_id,
        "node_type": src_attrs.get("node_type", ""),
        "community": src_attrs.get("community", 0),
        "attributes": {k: v for k, v in src_attrs.items() if k not in ("node_type", "community")},
    })

    for _, nbr, edata in G.out_edges(node_id, data=True):
        if nbr not in visited:
            visited.add(nbr)
            attrs = dict(G.nodes[nbr])
            nodes_out.append({
                "id": nbr,
                "node_type": attrs.get("node_type", ""),
                "community": attrs.get("community", 0),
                "attributes": {k: v for k, v in attrs.items() if k not in ("node_type", "community")},
            })
        edges_out.append({
            "source": node_id, "target": nbr,
            "edge_type": edata.get("edge_type", ""),
        })

    for pred, _, edata in G.in_edges(node_id, data=True):
        if pred not in visited:
            visited.add(pred)
            attrs = dict(G.nodes[pred])
            nodes_out.append({
                "id": pred,
                "node_type": attrs.get("node_type", ""),
                "community": attrs.get("community", 0),
                "attributes": {k: v for k, v in attrs.items() if k not in ("node_type", "community")},
            })
        edges_out.append({
            "source": pred, "target": node_id,
            "edge_type": edata.get("edge_type", ""),
        })

    return {"nodes": nodes_out, "edges": edges_out, "error": None}


def _bfs_edges(G: nx.DiGraph, start: str, max_depth: int = 5):
    """BFS iterator yielding (src, dst, data) up to max_depth."""
    queue = [(start, 0)]
    visited = {start}
    while queue:
        current, depth = queue.pop(0)
        if depth >= max_depth:
            continue
        for _, nbr, data in G.out_edges(current, data=True):
            yield current, nbr, data
            if nbr not in visited:
                visited.add(nbr)
                queue.append((nbr, depth + 1))
