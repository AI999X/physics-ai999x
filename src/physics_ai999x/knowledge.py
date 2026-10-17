"""The physics knowledge database shipped with the package (SQLite, read-only, standard library only).

    from physics_ai999x import knowledge
    knowledge.stats()                                   # what is in it, by kind and verification tier
    knowledge.search("kinetic energy", tier="machine_checked")
    knowledge.record("law.kinetic_energy")

Two kinds of content, never mixed:
  relations   the certified relations the engine computes with (the only source of answers)
  records     teacher-generated candidate knowledge (concepts, theories, explanations, derivations, problems,
              misconceptions, ...) with its verification tier. `machine_checked` means the factory re-computed it;
              `structurally_valid` means it is well formed and linked, and its MEANING IS NOT VERIFIED.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

_DB = Path(__file__).resolve().parent / "pack" / "knowledge.sqlite"
if not _DB.exists():                       # the factory's source tree: the newest built database
    _built = sorted((Path(__file__).resolve().parents[3] / "knowledge" / "db").glob("physics_kb_*.sqlite"))
    _DB = _built[-1] if _built else _DB


def _con():
    if not _DB.exists():
        raise FileNotFoundError("the knowledge database is not in this installation")
    con = sqlite3.connect(f"file:{_DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def meta() -> dict:
    with _con() as c:
        return {r["key"]: json.loads(r["value"]) for r in c.execute("select key, value from meta")}


def stats() -> dict:
    with _con() as c:
        by = {}
        for r in c.execute("select kind, tier, count(*) n from records group by kind, tier"):
            by.setdefault(r["kind"], {})[r["tier"]] = r["n"]
        return {"version": meta().get("version"), "relations": c.execute("select count(*) from relations").fetchone()[0],
                "records_by_kind_and_tier": by,
                "records": c.execute("select count(*) from records").fetchone()[0]}


def _row(r) -> dict:
    d = dict(r)
    for k in ("payload", "unverified_parts", "symbols", "assumptions", "requires", "excludes", "applies_when",
              "fails_when", "conventions", "derived_from", "given", "expect"):
        if k in d and isinstance(d[k], str):
            try:
                d[k] = json.loads(d[k])
            except ValueError:
                pass
    return d


def search(text: str, kind: str | None = None, tier: str | None = None, limit: int = 20) -> list:
    """Records whose statement or identifier contains `text` (case-insensitive)."""
    q = "select id, kind, tier, statement from records where (lower(statement) like ? or lower(id) like ?)"
    args = [f"%{text.lower()}%"] * 2
    if kind:
        q += " and kind = ?"
        args.append(kind)
    if tier:
        q += " and tier = ?"
        args.append(tier)
    with _con() as c:
        return [dict(r) for r in c.execute(q + " order by tier, id limit ?", args + [limit])]


def record(rid: str) -> dict | None:
    with _con() as c:
        r = c.execute("select * from records where id = ?", (rid,)).fetchone()
        return _row(r) if r else None


def relations() -> list:
    with _con() as c:
        return [_row(r) for r in c.execute("select * from relations order by family, key")]


def reference_cases(relation: str) -> list:
    with _con() as c:
        return [_row(r) for r in c.execute("select given, expect from reference_cases where relation = ?", (relation,))]
