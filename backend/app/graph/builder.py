"""
Build a NetworkX DiGraph from DuckDB, apply Louvain community detection,
and cache to disk.
"""
import pickle
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import networkx as nx

try:
    import community as community_louvain
    HAS_LOUVAIN = True
except ImportError:
    HAS_LOUVAIN = False

from app.core.config import settings
from app.core.database import get_db

_graph: nx.DiGraph | None = None


def _add_node(G: nx.DiGraph, node_id: str, node_type: str, **attrs):
    G.add_node(node_id, node_type=node_type, label=node_id, **attrs)


def build_graph() -> nx.DiGraph:
    db = get_db()
    G = nx.DiGraph()

    # ── Customers ──────────────────────────────────────────────
    rows = db.execute(
        "SELECT businessPartner, businessPartnerFullName, businessPartnerCategory "
        "FROM business_partners"
    ).fetchall()
    for bp, name, cat in rows:
        _add_node(G, f"C_{bp}", "Customer",
                  businessPartner=bp, name=name or bp, category=cat or "")

    # ── Products ───────────────────────────────────────────────
    rows = db.execute(
        "SELECT p.product, COALESCE(pd.productDescription, p.product) as desc, "
        "p.productType, p.baseUnit "
        "FROM products p "
        "LEFT JOIN product_descriptions pd ON p.product = pd.product AND pd.language = 'EN'"
    ).fetchall()
    for prod, desc, ptype, unit in rows:
        _add_node(G, f"P_{prod}", "Product",
                  product=prod, description=desc, productType=ptype or "", baseUnit=unit or "")

    # ── Plants ─────────────────────────────────────────────────
    rows = db.execute("SELECT plant, plantName FROM plants").fetchall()
    for plant_id, plant_name in rows:
        _add_node(G, f"PL_{plant_id}", "Plant",
                  plant=plant_id, name=plant_name or plant_id)

    # ── Sales Orders ───────────────────────────────────────────
    rows = db.execute(
        "SELECT salesOrder, salesOrderType, soldToParty, totalNetAmount, "
        "overallDeliveryStatus, transactionCurrency, creationDate "
        "FROM sales_order_headers"
    ).fetchall()
    for so, so_type, sold_to, net_amt, del_status, currency, cdate in rows:
        _add_node(G, f"SO_{so}", "SalesOrder",
                  salesOrder=so, orderType=so_type or "", soldToParty=sold_to or "",
                  totalNetAmount=net_amt or "0", deliveryStatus=del_status or "",
                  currency=currency or "", creationDate=str(cdate or ""))
        # Edge: SalesOrder → Customer
        cust_node = f"C_{sold_to}"
        if sold_to and G.has_node(cust_node):
            G.add_edge(f"SO_{so}", cust_node, edge_type="PLACED_BY")

    # ── Sales Order Items ──────────────────────────────────────
    rows = db.execute(
        "SELECT salesOrder, salesOrderItem, material, requestedQuantity, netAmount, productionPlant "
        "FROM sales_order_items"
    ).fetchall()
    for so, item, material, qty, net_amt, plant_id in rows:
        node_id = f"SOI_{so}_{item}"
        _add_node(G, node_id, "SalesOrderItem",
                  salesOrder=so, salesOrderItem=item, material=material or "",
                  requestedQuantity=qty or "0", netAmount=net_amt or "0",
                  productionPlant=plant_id or "")
        # Edge: SalesOrder → SalesOrderItem
        if G.has_node(f"SO_{so}"):
            G.add_edge(f"SO_{so}", node_id, edge_type="HAS_ITEM")
        # Edge: SalesOrderItem → Product
        if material and G.has_node(f"P_{material}"):
            G.add_edge(node_id, f"P_{material}", edge_type="REF_MATERIAL")

    # ── Deliveries ─────────────────────────────────────────────
    rows = db.execute(
        "SELECT deliveryDocument, shippingPoint, overallGoodsMovementStatus, "
        "overallPickingStatus, creationDate "
        "FROM outbound_delivery_headers"
    ).fetchall()
    for deldoc, ship_pt, gm_status, pick_status, cdate in rows:
        _add_node(G, f"D_{deldoc}", "Delivery",
                  deliveryDocument=deldoc, shippingPoint=ship_pt or "",
                  goodsMovementStatus=gm_status or "", pickingStatus=pick_status or "",
                  creationDate=str(cdate or ""))

    # ── Delivery Items ─────────────────────────────────────────
    rows = db.execute(
        "SELECT deliveryDocument, deliveryDocumentItem, plant, "
        "referenceSdDocument, referenceSdDocumentItem, actualDeliveryQuantity "
        "FROM outbound_delivery_items"
    ).fetchall()
    for deldoc, delitem, plant_id, ref_so, ref_so_item, qty in rows:
        node_id = f"DI_{deldoc}_{delitem}"
        _add_node(G, node_id, "DeliveryItem",
                  deliveryDocument=deldoc, deliveryDocumentItem=delitem,
                  plant=plant_id or "", referenceSdDocument=ref_so or "",
                  actualDeliveryQuantity=qty or "0")
        # Edge: Delivery → DeliveryItem
        if G.has_node(f"D_{deldoc}"):
            G.add_edge(f"D_{deldoc}", node_id, edge_type="HAS_ITEM")
        # Edge: Delivery → Plant
        if plant_id and G.has_node(f"PL_{plant_id}"):
            del_node = f"D_{deldoc}"
            if G.has_node(del_node) and not G.has_edge(del_node, f"PL_{plant_id}"):
                G.add_edge(del_node, f"PL_{plant_id}", edge_type="SHIPS_FROM")
        # Edge: SalesOrderItem → DeliveryItem
        if ref_so and ref_so_item:
            soi_node = f"SOI_{ref_so}_{ref_so_item.lstrip('0') or '0'}"
            # Try both zero-padded and stripped versions
            for soi_candidate in [soi_node, f"SOI_{ref_so}_{ref_so_item}"]:
                if G.has_node(soi_candidate):
                    G.add_edge(soi_candidate, node_id, edge_type="FULFILLED_BY")
                    break

    # ── Billing Documents ──────────────────────────────────────
    rows = db.execute(
        "SELECT billingDocument, billingDocumentType, totalNetAmount, transactionCurrency, "
        "billingDocumentDate, accountingDocument, soldToParty, billingDocumentIsCancelled "
        "FROM billing_document_headers"
    ).fetchall()
    for bd, bd_type, net_amt, currency, bd_date, acct_doc, sold_to, is_cancelled in rows:
        _add_node(G, f"BD_{bd}", "BillingDocument",
                  billingDocument=bd, billingDocumentType=bd_type or "",
                  totalNetAmount=net_amt or "0", currency=currency or "",
                  billingDocumentDate=str(bd_date or ""), accountingDocument=acct_doc or "",
                  soldToParty=sold_to or "", isCancelled=bool(is_cancelled))
        # Edge: BillingDocument → Customer
        if sold_to and G.has_node(f"C_{sold_to}"):
            G.add_edge(f"BD_{bd}", f"C_{sold_to}", edge_type="SOLD_TO")

    # ── Billing Items → Delivery link ──────────────────────────
    rows = db.execute(
        "SELECT billingDocument, referenceSdDocument "
        "FROM billing_document_items "
        "WHERE referenceSdDocument IS NOT NULL AND referenceSdDocument != ''"
    ).fetchall()
    seen_bd_del = set()
    for bd, ref_del in rows:
        key = (bd, ref_del)
        if key not in seen_bd_del:
            seen_bd_del.add(key)
            # Edge: Delivery → BillingDocument (via billing item referencing delivery)
            if G.has_node(f"D_{ref_del}") and G.has_node(f"BD_{bd}"):
                G.add_edge(f"D_{ref_del}", f"BD_{bd}", edge_type="BILLED_VIA")

    # ── Journal Entries ────────────────────────────────────────
    rows = db.execute(
        "SELECT accountingDocument, accountingDocumentItem, glAccount, "
        "referenceDocument, amountInTransactionCurrency, postingDate, accountingDocumentType "
        "FROM journal_entry_items"
    ).fetchall()
    for acct_doc, acct_item, gl_acct, ref_doc, amount, post_date, doc_type in rows:
        node_id = f"JE_{acct_doc}_{acct_item}"
        _add_node(G, node_id, "JournalEntry",
                  accountingDocument=acct_doc, accountingDocumentItem=str(acct_item or ""),
                  glAccount=gl_acct or "", referenceDocument=ref_doc or "",
                  amount=str(amount or "0"), postingDate=str(post_date or ""),
                  documentType=doc_type or "")
        # Edge: BillingDocument → JournalEntry
        if ref_doc and G.has_node(f"BD_{ref_doc}"):
            G.add_edge(f"BD_{ref_doc}", node_id, edge_type="HAS_JOURNAL")

    # ── Payments ───────────────────────────────────────────────
    rows = db.execute(
        "SELECT accountingDocument, accountingDocumentItem, clearingDate, "
        "clearingAccountingDocument, amountInTransactionCurrency, customer "
        "FROM payments"
    ).fetchall()
    for acct_doc, acct_item, clr_date, clr_acct_doc, amount, customer in rows:
        node_id = f"PAY_{acct_doc}_{acct_item}"
        _add_node(G, node_id, "Payment",
                  accountingDocument=acct_doc, accountingDocumentItem=str(acct_item or ""),
                  clearingDate=str(clr_date or ""), clearingAccountingDocument=clr_acct_doc or "",
                  amount=str(amount or "0"), customer=customer or "")
        # Edge: JournalEntry → Payment (match on accountingDocument)
        je_node = f"JE_{acct_doc}_1"
        if G.has_node(je_node):
            G.add_edge(je_node, node_id, edge_type="PAID_BY")

    # ── Community assignment ───────────────────────────────────
    # Louvain can be memory-intensive on larger graphs; keep it opt-in.
    if HAS_LOUVAIN and settings.enable_louvain:
        undirected = G.to_undirected()
        partition = community_louvain.best_partition(undirected)
        nx.set_node_attributes(G, partition, "community")
    else:
        # Fallback: assign community by node_type index
        type_to_comm = {nt: i for i, nt in enumerate([
            "SalesOrder", "SalesOrderItem", "Customer", "Product",
            "Plant", "Delivery", "DeliveryItem", "BillingDocument",
            "JournalEntry", "Payment"
        ])}
        for node, data in G.nodes(data=True):
            data["community"] = type_to_comm.get(data.get("node_type", ""), 0)

    print(f"Graph built: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    return G


def save_graph(G: nx.DiGraph):
    cache_path = Path(settings.graph_cache_path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "wb") as f:
        pickle.dump(G, f)
    print(f"Graph cached to {cache_path}")


def load_graph() -> nx.DiGraph:
    global _graph
    if _graph is not None:
        return _graph
    cache_path = Path(settings.graph_cache_path)
    if cache_path.exists():
        with open(cache_path, "rb") as f:
            _graph = pickle.load(f)
        print(f"Graph loaded from cache: {_graph.number_of_nodes()} nodes")
    else:
        _graph = build_and_save()
    return _graph


def build_and_save() -> nx.DiGraph:
    global _graph
    _graph = build_graph()
    save_graph(_graph)
    return _graph


if __name__ == "__main__":
    build_and_save()
