"""physics-ai999x "A 3 kg object moves at 4 m/s. What is its kinetic energy?"   [--json]
physics-ai999x --solve "kinetic energy" mass="3 kg" speed="4 m/s" [--when frictionless]
physics-ai999x --formulas | --quantities | --conditions | --version
physics-ai999x --topics [--computable] | --templates [RELATION] | --explain "question"
A question that cannot be answered yet gets a plain next step (what to add, a format that works, the topic it belongs to).
"""
from __future__ import annotations

import argparse
import json
import sys


def main(argv=None) -> int:
    import physics_ai999x as P
    ap = argparse.ArgumentParser(prog="physics-ai999x", description="Offline physics answers with steps and verification.")
    ap.add_argument("question", nargs="*")
    ap.add_argument("--solve", metavar="FIND", help="structured: what to find; givens as name=value after it")
    ap.add_argument("--when", action="append", default=[], help="a condition (repeatable), e.g. --when frictionless")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--formulas", action="store_true")
    ap.add_argument("--quantities", action="store_true")
    ap.add_argument("--conditions", action="store_true")
    ap.add_argument("--version", action="store_true")
    ap.add_argument("--topics", action="store_true", help="curriculum sections and what can be computed in each")
    ap.add_argument("--computable", action="store_true", help="with --topics: only sections the engine computes in")
    ap.add_argument("--templates", nargs="?", const="", default=None, metavar="RELATION", help="question formats that work")
    ap.add_argument("--explain", action="store_true", help="answer, then explain every verified step in words")
    a = ap.parse_args(argv)
    if a.version:
        print(P.__version__, "pack", P.pack().version)
        return 0
    if a.topics:
        for t in P.topics(computable_only=a.computable):
            print(f"{t['status']:<16} {t['name']}  ({t['id']})")
            if t["computes"]:
                print(" " * 17 + "computes: " + ", ".join(t["computes"]))
        return 0
    if a.templates is not None:
        for t in P.templates(a.templates or None):
            print(f"{t['name']} -> {t['finds']}")
            print(f"   format:  {t['pattern']}")
            print(f"   example: {t['example']}  =>  {t['answer']}")
        return 0
    if a.formulas or a.quantities or a.conditions:
        rows = P.formulas() if a.formulas else P.quantities() if a.quantities else P.conditions()
        print(json.dumps(rows, indent=1, default=str))
        return 0
    if a.solve:
        given = dict(x.split("=", 1) for x in a.question)
        ans = P.solve(a.solve, given, a.when)
    elif a.question:
        ans = P.ask(" ".join(a.question))
    else:
        ap.print_help()
        return 2
    if a.json:
        print(ans.to_json(indent=1))
    elif ans.solved:
        print(P.explain(ans)["text"] if a.explain else ans)
    else:
        s = P.suggest(ans.question) if isinstance(ans.question, str) and not a.solve else None
        print(s["message"] if s else ans.message)
        for line in (s or {}).get("ask_back", []):
            print("  - " + line)
        for ex in (s or {}).get("try", []):
            print("  e.g. " + ex)
        for t in (s or {}).get("topics", []):
            print(f"  topic: {t['name']} ({t['status']})")
    return 0 if ans.solved else 1


if __name__ == "__main__":
    sys.exit(main())
