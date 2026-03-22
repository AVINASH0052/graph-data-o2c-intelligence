"""
Graph REST endpoints.
"""
from fastapi import APIRouter, HTTPException, Query
from app.graph.builder import load_graph
from app.core.config import settings
import networkx as nx

router = APIRouter(prefix="/api/graph", tags=["graph"])

# Community → color mapping
COMMUNITY_COLORS = [
    "#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f",
    "#edc948", "#b07aa1", "#ff9da7", "#9c755f", "#bab0ac",
    "#d4a0f0", "#a0d4f0", "#f0a0d4", "#a0f0d4", "#f0d4a0",
]

NODE_TYPE_COLORS = {
    "SalesOrder": "#4e79a7",
    "SalesOrderItem": "#76b7b2",
    "Customer": "#f28e2b",
    "Product": "#59a14f",
    "Plant": "#edc948",
    "Delivery": "#e15759",
    "DeliveryItem": "#ff9da7",
    "BillingDocument": "#b07aa1",
    "JournalEntry": "#9c755f",
    "Payment": "#bab0ac",
}


def _node_to_dict(node_id: str, G: nx.DiGraph) -> dict:
    attrs = dict(G.nodes[node_id])
    node_type = attrs.get("node_type", "Unknown")
    community = attrs.get("community", 0)
    return {
        "id": node_id,
        "label": attrs.get("salesOrder")
            or attrs.get("billingDocument")
            or attrs.get("deliveryDocument")
            or attrs.get("businessPartner")
            or attrs.get("product")
            or attrs.get("plant")
            or attrs.get("accountingDocument")
            or node_id,
        "node_type": node_type,
        "community": community,
        "color": NODE_TYPE_COLORS.get(node_type, COMMUNITY_COLORS[community % len(COMMUNITY_COLORS)]),
        "size": min(5 + G.degree(node_id), 30),
        "attributes": {k: str(v) for k, v in attrs.items() if k not in ("node_type", "community", "label")},
    }


@router.get("")
def get_graph(
    node_types: str = Query(default="", description="Comma-separated node types to filter"),
    limit: int = Query(default=2000, le=settings.max_graph_nodes),
):
    """Return the full (or filtered/limited) graph for visualization."""
    G = load_graph()

    filter_types = set(t.strip() for t in node_types.split(",") if t.strip())

    nodes_out = []
    node_ids_included = set()

    for node_id, data in G.nodes(data=True):
        if filter_types and data.get("node_type") not in filter_types:
            continue
        nodes_out.append(_node_to_dict(node_id, G))
        node_ids_included.add(node_id)
        if len(nodes_out) >= limit:
            break

    edges_out = []
    for src, dst, edata in G.edges(data=True):
        if src in node_ids_included and dst in node_ids_included:
            edges_out.append({
                "source": src,
                "target": dst,
                "edge_type": edata.get("edge_type", ""),
                "id": f"{src}__{dst}",
            })

    return {
        "nodes": nodes_out,
        "edges": edges_out,
        "total_nodes": G.number_of_nodes(),
        "total_edges": G.number_of_edges(),
        "shown_nodes": len(nodes_out),
        "shown_edges": len(edges_out),
    }


@router.get("/node/{node_id:path}")
def get_node(node_id: str):
    """Get a node with its 1-hop neighbourhood."""
    G = load_graph()
    if not G.has_node(node_id):
        raise HTTPException(status_code=404, detail=f"Node {node_id!r} not found")

    node_data = _node_to_dict(node_id, G)
    neighbors = []
    edges = []

    for _, nbr, edata in G.out_edges(node_id, data=True):
        neighbors.append(_node_to_dict(nbr, G))
        edges.append({"source": node_id, "target": nbr, "edge_type": edata.get("edge_type", "")})

    for pred, _, edata in G.in_edges(node_id, data=True):
        neighbors.append(_node_to_dict(pred, G))
        edges.append({"source": pred, "target": node_id, "edge_type": edata.get("edge_type", "")})

    return {"node": node_data, "neighbors": neighbors, "edges": edges}


@router.get("/search")
def search_nodes(
    q: str = Query(..., min_length=1),
    limit: int = Query(default=20, le=100),
):
    """Keyword search over node IDs and label attributes."""
    G = load_graph()
    q_lower = q.lower().strip()
    results = []

    for node_id, data in G.nodes(data=True):
        if q_lower in node_id.lower():
            results.append(_node_to_dict(node_id, G))
        else:
            # Check key attribute values
            for attr_key in ("salesOrder", "billingDocument", "deliveryDocument",
                             "businessPartner", "product", "plant", "accountingDocument",
                             "businessPartnerFullName", "description", "name"):
                val = str(data.get(attr_key, "")).lower()
                if val and q_lower in val:
                    results.append(_node_to_dict(node_id, G))
                    break
        if len(results) >= limit:
            break

    return {"results": results, "count": len(results)}


@router.get("/stats")
def get_stats():
    """Return graph statistics."""
    G = load_graph()
    type_counts: dict[str, int] = {}
    for _, data in G.nodes(data=True):
        nt = data.get("node_type", "Unknown")
        type_counts[nt] = type_counts.get(nt, 0) + 1

    edge_counts: dict[str, int] = {}
    for _, _, data in G.edges(data=True):
        et = data.get("edge_type", "Unknown")
        edge_counts[et] = edge_counts.get(et, 0) + 1

    return {
        "total_nodes": G.number_of_nodes(),
        "total_edges": G.number_of_edges(),
        "node_types": type_counts,
        "edge_types": edge_counts,
    }
