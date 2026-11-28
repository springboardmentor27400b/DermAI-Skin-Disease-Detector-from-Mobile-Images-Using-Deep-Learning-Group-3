"""Tiny schema upgrader: adds columns that exist in the models but not in an older database.

Lets people keep their existing dermai.db when new fields are added. Replace with Alembic
before running anywhere that holds real data.
"""
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.schema import CreateColumn

from app.db.session import Base


def add_missing_columns(engine: Engine) -> list[str]:
    added: list[str] = []
    insp = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if not insp.has_table(table.name):
                continue
            existing = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name not in existing:
                    ddl = str(CreateColumn(col).compile(dialect=engine.dialect))
                    conn.execute(text(f"ALTER TABLE {table.name} ADD COLUMN {ddl}"))
                    added.append(f"{table.name}.{col.name}")
    return added

