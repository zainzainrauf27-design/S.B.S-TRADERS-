#!/usr/bin/env python3
"""Apply ordered SQLite migrations for S.A.B Trader."""
from __future__ import annotations

import argparse
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "db" / "migrations"


def default_database_path() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        raise RuntimeError("LOCALAPPDATA is not set; provide --db for development.")
    return Path(local_app_data) / "SABTrader" / "data" / "sabtrader.sqlite"


def apply_migrations(database: Path) -> list[str]:
    database.parent.mkdir(parents=True, exist_ok=True)
    applied: list[str] = []
    connection = sqlite3.connect(database)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("""CREATE TABLE IF NOT EXISTS schema_migrations (
            migration_id TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL
        )""")
        connection.commit()

        for migration_file in sorted(MIGRATIONS.glob("[0-9][0-9][0-9]_*.sql")):
            migration_id = migration_file.stem
            exists = connection.execute(
                "SELECT 1 FROM schema_migrations WHERE migration_id = ?", (migration_id,)
            ).fetchone()
            if exists:
                continue
            sql = migration_file.read_text(encoding="utf-8")
            try:
                connection.executescript("BEGIN IMMEDIATE;\n" + sql)
                connection.execute(
                    "INSERT INTO schema_migrations(migration_id, applied_at) VALUES (?, ?)",
                    (migration_id, datetime.now(timezone.utc).isoformat(timespec="seconds")),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            applied.append(migration_id)
    finally:
        connection.close()
    return applied


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, help="SQLite path (development override)")
    args = parser.parse_args()
    database = (args.db or default_database_path()).expanduser().resolve()
    applied = apply_migrations(database)
    print(f"Database: {database}")
    print("Applied: " + (", ".join(applied) if applied else "no new migrations"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
