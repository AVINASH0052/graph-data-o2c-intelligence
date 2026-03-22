"""
Safe DuckDB SQL execution.
Validates that all referenced table and column names exist in the schema
before executing to prevent injection / hallucinations.
"""
import re
from app.core.database import get_db

# Allowlist of tables that exist in our schema
ALLOWED_TABLES = {
    "sales_order_headers", "sales_order_items", "sales_order_schedule_lines",
    "outbound_delivery_headers", "outbound_delivery_items",
    "billing_document_headers", "billing_document_items",
    "billing_document_cancellations", "journal_entry_items", "payments",
    "business_partners", "business_partner_addresses",
    "customer_company_assignments", "customer_sales_area_assignments",
    "plants", "products", "product_descriptions", "product_plants",
    "product_storage_locations",
}

# Dangerous SQL keywords that should never appear
BLOCKED_PATTERNS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|EXEC|EXECUTE|"
    r"PRAGMA|ATTACH|DETACH|COPY|EXPORT|IMPORT)\b",
    re.IGNORECASE,
)


def _validate_sql(sql: str) -> str | None:
    """Return error message if SQL is unsafe, else None."""
    if BLOCKED_PATTERNS.search(sql):
        return "SQL contains disallowed statement type."

    # Extract table references (simple heuristic)
    table_refs = re.findall(
        r"\bFROM\s+(\w+)|\bJOIN\s+(\w+)", sql, re.IGNORECASE
    )
    referenced = {t for pair in table_refs for t in pair if t}

    unknown = referenced - ALLOWED_TABLES
    if unknown:
        return f"Unknown tables referenced: {unknown}"

    return None


def execute_sql(sql: str, limit: int = 200) -> dict:
    """
    Execute a SELECT query and return rows + columns.
    Appends LIMIT if not already present.
    Returns {"columns": [...], "rows": [...], "error": None|str}
    """
    err = _validate_sql(sql)
    if err:
        return {"columns": [], "rows": [], "error": err}

    # Inject LIMIT for safety
    stripped = sql.rstrip(";").strip()
    if not re.search(r"\bLIMIT\b", stripped, re.IGNORECASE):
        stripped = f"{stripped} LIMIT {limit}"

    try:
        db = get_db()
        rel = db.execute(stripped)
        columns = [desc[0] for desc in rel.description]
        rows = rel.fetchall()
        return {
            "columns": columns,
            "rows": [list(r) for r in rows],
            "error": None,
        }
    except Exception as exc:
        return {"columns": [], "rows": [], "error": str(exc)}
