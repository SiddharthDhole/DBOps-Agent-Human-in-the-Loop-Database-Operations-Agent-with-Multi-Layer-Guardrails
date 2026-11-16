SCHEMA_METADATA = {
    "customers": {
        "columns": "id INT PK, name VARCHAR, email VARCHAR, country VARCHAR, status VARCHAR, created_at TIMESTAMP",
        "relationships": ["customers.id -> orders.customer_id"],
    },
    "products": {
        "columns": "id INT PK, name VARCHAR, category VARCHAR, price NUMERIC, stock INT",
        "relationships": ["products.id -> orders.product_id"],
    },
    "orders": {
        "columns": "id INT PK, customer_id INT FK, product_id INT FK, quantity INT, total_amount NUMERIC, status VARCHAR, created_at TIMESTAMP",
        "relationships": [
            "orders.customer_id -> customers.id",
            "orders.product_id -> products.id",
            "orders.id -> payments.order_id",
        ],
    },
    "payments": {
        "columns": "id INT PK, order_id INT FK, amount NUMERIC, payment_method VARCHAR, status VARCHAR, created_at TIMESTAMP",
        "relationships": ["payments.order_id -> orders.id"],
    },
}


def select_relevant_tables(
    question: str,
    max_tables: int = 3,
) -> list[str]:
    """Select the most relevant tables for the user query."""
    q = question.lower()
    scores = {}

    for table_name in SCHEMA_METADATA:
        score = 0
        singular = table_name[:-1] if table_name.endswith("s") else table_name

        # Exact table name or root match gets highest priority
        if table_name in q or singular in q:
            score += 10

        # Check for column matches
        cols_text = SCHEMA_METADATA[table_name]["columns"].lower()
        for col_def in cols_text.split(","):
            col_name = col_def.strip().split()[0]
            if col_name in ("id", "status"):
                continue  # Generic columns present in multiple tables
            if col_name in q:
                score += 3

        if score > 0:
            scores[table_name] = score

    if not scores:
        return []

    ranked = sorted(scores, key=scores.get, reverse=True)
    # If the top table has a dominant score (e.g. exact match), don't drag in distant low-scoring tables
    top_score = scores[ranked[0]]
    relevant = [t for t in ranked if scores[t] >= max(3, top_score // 2)]
    return relevant[:max_tables]


def build_schema_context(
    tables: list[str],
) -> str:
    """Build a compact, token-efficient schema representation."""
    if not tables:
        return ""

    sections = []
    for table in tables:
        meta = SCHEMA_METADATA.get(table)
        if not meta:
            continue
        rel_str = f" | FK: {', '.join(meta['relationships'])}" if meta.get("relationships") else ""
        sections.append(f"• {table} ({meta['columns']}){rel_str}")

    return "\n".join(sections)