import argparse
import json
import sqlite3
import sys
from typing import Any, Dict, Optional


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Simple Singer target that loads sun_events into SQLite."
    )
    parser.add_argument(
        "--database",
        required=True,
        help="Path to SQLite database file (will be created if missing).",
    )
    parser.add_argument(
        "--table",
        default="sun_events",
        help="Destination table name (default: sun_events).",
    )
    return parser.parse_args()


def ensure_table(conn: sqlite3.Connection, table: str) -> None:
    # Check existing schema, if any
    cursor = conn.execute(f"PRAGMA table_info({table})")
    cols = [row[1] for row in cursor.fetchall()]

    if not cols:
        # Table does not exist yet: create with desired schema
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {table} (
                date TEXT PRIMARY KEY,
                day_length INTEGER,
                sunrise TEXT,
                sunset TEXT
            )
            """
        )
        conn.commit()
        return

    # Table exists: ensure required columns are present
    required_columns = ["date", "day_length", "sunrise", "sunset"]
    for col in required_columns:
        if col not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} TEXT")
    conn.commit()


def upsert_record(conn: sqlite3.Connection, table: str, record: Dict[str, Any]) -> None:
    fields = [
        "date",
        "day_length",
        "sunrise",
        "sunset",
    ]
    placeholders = ", ".join(["?"] * len(fields))
    columns = ", ".join(fields)
    assignments = ", ".join([f"{f}=excluded.{f}" for f in fields[1:]])

    values = [record.get(field) for field in fields]
    conn.execute(
        f"""
        INSERT INTO {table} ({columns})
        VALUES ({placeholders})
        ON CONFLICT(date) DO UPDATE SET
            {assignments}
        """,
        values,
    )


def main() -> None:
    args = parse_args()
    conn = sqlite3.connect(args.database)
    ensure_table(conn, args.table)

    stream_seen: Optional[str] = None

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue

        msg_type = msg.get("type")

        if msg_type == "SCHEMA":
            stream_seen = msg.get("stream")
        elif msg_type == "RECORD":
            if stream_seen and msg.get("stream") != stream_seen:
                continue
            record = msg.get("record") or {}
            upsert_record(conn, args.table, record)
        elif msg_type == "STATE":
            # For this simple target, we ignore STATE but keep reading.
            continue

    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()

