"""
ETL: Load all JSONL files from sap-o2c-data into DuckDB tables.
Run once: python -m app.etl.ingest
"""
import json
import sys
from pathlib import Path
import duckdb

# Allow running as script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.core.config import settings
from app.core.database import get_db

# Map table name → folder name relative to sap-o2c-data/
TABLE_FOLDERS = {
    "sales_order_headers": "sales_order_headers",
    "sales_order_items": "sales_order_items",
    "sales_order_schedule_lines": "sales_order_schedule_lines",
    "outbound_delivery_headers": "outbound_delivery_headers",
    "outbound_delivery_items": "outbound_delivery_items",
    "billing_document_headers": "billing_document_headers",
    "billing_document_items": "billing_document_items",
    "billing_document_cancellations": "billing_document_cancellations",
    "journal_entry_items": "journal_entry_items_accounts_receivable",
    "payments": "payments_accounts_receivable",
    "business_partners": "business_partners",
    "business_partner_addresses": "business_partner_addresses",
    "customer_company_assignments": "customer_company_assignments",
    "customer_sales_area_assignments": "customer_sales_area_assignments",
    "plants": "plants",
    "products": "products",
    "product_descriptions": "product_descriptions",
    "product_plants": "product_plants",
    "product_storage_locations": "product_storage_locations",
}


def _flatten(obj: dict, prefix: str = "") -> dict:
    """Flatten nested dicts one level deep (handles time sub-objects)."""
    result = {}
    for k, v in obj.items():
        full_key = f"{prefix}{k}"
        if isinstance(v, dict):
            for sk, sv in v.items():
                result[f"{full_key}_{sk}"] = sv
        else:
            result[full_key] = v
    return result


def iter_jsonl_folder(folder_path: Path):
    for f in sorted(folder_path.glob("*.jsonl")):
        with open(f, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        yield _flatten(json.loads(line))
                    except json.JSONDecodeError:
                        continue


def ingest_all(data_root: Path | None = None):
    if data_root is None:
        data_root = Path(settings.data_dir).parent / "sap-o2c-data"
        if not data_root.exists():
            # Try relative from backend dir
            data_root = Path(settings.data_dir).parent.parent / "sap-o2c-data"

    db = get_db()

    for table_name, folder_name in TABLE_FOLDERS.items():
        folder_path = data_root / folder_name
        if not folder_path.exists():
            print(f"  [SKIP] {folder_name} not found at {folder_path}")
            continue

        records_iter = iter_jsonl_folder(folder_path)
        sample = next(records_iter, None)
        if sample is None:
            print(f"  [SKIP] {table_name}: 0 records")
            continue

        # Drop and recreate table
        db.execute(f"DROP TABLE IF EXISTS {table_name}")

        # Build CREATE TABLE from first record's keys
        col_defs = []
        for col, val in sample.items():
            safe_col = col.replace(".", "_").replace("-", "_")
            if isinstance(val, bool):
                dtype = "BOOLEAN"
            elif isinstance(val, int):
                dtype = "BIGINT"
            elif isinstance(val, float):
                dtype = "DOUBLE"
            else:
                dtype = "VARCHAR"
            col_defs.append(f'"{safe_col}" {dtype}')

        db.execute(f"CREATE TABLE {table_name} ({', '.join(col_defs)})")

        # Insert in batches
        cols = [col.replace(".", "_").replace("-", "_") for col in sample.keys()]
        quoted_cols = ", ".join(f'"{c}"' for c in cols)
        placeholders = ", ".join(["?"] * len(cols))

        def row_from_record(rec: dict) -> tuple:
            return tuple(rec.get(orig_col) for orig_col in sample.keys())

        total_rows = 0
        batch_size = 2000
        batch = [row_from_record(sample)]
        total_rows += 1

        for rec in records_iter:
            batch.append(row_from_record(rec))
            total_rows += 1
            if len(batch) >= batch_size:
                db.executemany(
                    f"INSERT INTO {table_name} ({quoted_cols}) VALUES ({placeholders})",
                    batch,
                )
                batch = []

        if batch:
            db.executemany(
                f"INSERT INTO {table_name} ({quoted_cols}) VALUES ({placeholders})",
                batch,
            )

        print(f"  [OK] {table_name}: {total_rows} rows")

    db.execute("CHECKPOINT")
    print("\nIngestion complete.")


if __name__ == "__main__":
    ingest_all()
