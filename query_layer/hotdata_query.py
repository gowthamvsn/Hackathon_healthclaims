"""Live Query & Analytics Layer — hotdata.dev

Fast, isolated, ad-hoc SQL over structured data that doesn't need to go
through the memory graph: "how many claims landed today", "which sources
are cited most", "what's trending in the live feed right now".

Confirmed against the installed `hotdata-framework` 0.14.0 package (see
SETUP_NOTES.md) — `HotdataClient.from_env()`, `execute_sql`, and the managed
-table methods below are real bound methods, not guesses.
"""
import tempfile

import pyarrow as pa
import pyarrow.parquet as pq
from hotdata_framework import HotdataClient

from agent.config import require_env

CLAIMS_DB_NAME = "research_claims"
CLAIMS_TABLE = "claims"
CLAIMS_DB_DESCRIPTION = "Research assistant claim metadata (hackathon demo)"


def make_client() -> HotdataClient:
    """Reads HOTDATA_API_KEY / HOTDATA_API_URL / HOTDATA_WORKSPACE from env."""
    require_env("HOTDATA_API_KEY")
    return HotdataClient.from_env()


def ensure_claims_table(client: HotdataClient):
    """Idempotent: reuse the scratch analytics DB/table for claim metadata if
    one already exists, create it only on genuine first run.

    This used to call create_managed_database() unconditionally on every
    process start, which — since the API happily creates a new database
    every time rather than erroring on a duplicate name — silently
    fragmented our data across a new database on every server restart
    (confirmed live: 13 separate databases had accumulated by the time this
    was caught, each holding a handful of rows instead of one growing
    table). Real bug, not a hypothetical: fixed by checking
    list_managed_databases() for an existing match first.
    """
    for db in client.list_managed_databases():
        if db.description == CLAIMS_DB_DESCRIPTION:
            return db
    return client.create_managed_database(CLAIMS_DB_DESCRIPTION, tables=[CLAIMS_TABLE])


def load_claims(client: HotdataClient, database, rows: list[dict]):
    """Load extracted-claim metadata (paper_id, claim, topic, confidence)
    into the managed table for fast SQL. Managed table loads require
    Parquet, not CSV (confirmed via a real 'ValueError: Managed table loads
    require a parquet file' from the live API)."""
    table = pa.Table.from_pylist(rows)

    with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as f:
        tmp_path = f.name
    pq.write_table(table, tmp_path)

    upload_id = client.upload_parquet(tmp_path)
    return client.load_managed_table(database, CLAIMS_TABLE, upload_id=upload_id, mode="append")


def topic_trend_query(client: HotdataClient, database, topic_like: str = "%"):
    """The 'what's happening right now' analytical question — a raw SQL
    aggregate over the live claims table, complementing HydraDB's
    relationship-aware recall with fast ad-hoc analytics."""
    safe_topic_like = topic_like.replace("'", "''")
    sql = f"""
        select topic, count(*) as claim_count, avg(confidence) as avg_confidence
        from {CLAIMS_TABLE}
        where topic like '{safe_topic_like}'
        group by topic
        order by claim_count desc
    """
    return client.execute_sql(sql, database=database)


def recent_claims_query(client: HotdataClient, database, limit: int = 50):
    """Raw row listing for a dashboard view — no timestamp column exists in
    this scratch table, so this is simply "everything logged so far",
    newest-insert-order not guaranteed by SQL semantics but fine for a
    demo view."""
    sql = f"select paper_id, claim, topic, confidence from {CLAIMS_TABLE} limit {int(limit)}"
    return client.execute_sql(sql, database=database)
