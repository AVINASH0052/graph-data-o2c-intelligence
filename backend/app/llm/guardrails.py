"""
Guardrails: two-layer domain guard.
Layer 1: Fast keyword pre-filter (no LLM call needed).
Layer 2: LLM domain-classification fallback.
"""
import re

# Domain keywords — if ANY appear, the query is likely in-domain
DOMAIN_KEYWORDS = re.compile(
    r"\b(sales.?order|billing|invoice|deliver|shipment|payment|journal.?entr"
    r"|customer|product|material|plant|purchase|order|dispatch|warehouse|OTC"
    r"|order.to.cash|goods|stock|quantity|amount|revenue|account|document|SO\b"
    r"|BD\b|PO\b|JE\b|SAP|ERP|supplier|vendor|clearance|incoterm)\b",
    re.IGNORECASE,
)

# Hard reject patterns — definitively off-topic
REJECT_PATTERNS = re.compile(
    r"\b(poem|song|lyric|recipe|weather|sport|footbal|cricket|movie|actor"
    r"|joke|story|write.{0,20}essay|capital.of|translate|language|math|calcul"
    r"|stock.market|crypto|bitcoin|political|president|prime.minister"
    r"|celebrity|music|album|anime|manga)\b",
    re.IGNORECASE,
)

OFF_TOPIC_RESPONSE = (
    "I'm only able to answer questions related to the Order-to-Cash dataset "
    "(sales orders, deliveries, billing documents, journal entries, payments, "
    "customers, and products). Please ask a question about the business data."
)


def is_in_domain(user_message: str) -> tuple[bool, str | None]:
    """
    Returns (True, None) if in domain, (False, rejection_message) if off-topic.
    """
    # Hard reject first
    if REJECT_PATTERNS.search(user_message):
        return False, OFF_TOPIC_RESPONSE

    # Domain keyword present → allow
    if DOMAIN_KEYWORDS.search(user_message):
        return True, None

    # Short numeric-only queries (e.g. "91150187") → likely entity lookup
    stripped = user_message.strip()
    if re.match(r"^[\d\s\-]+$", stripped) and len(stripped) >= 4:
        return True, None

    # Ambiguous but not rejected → pass through (LLM will handle)
    return True, None
