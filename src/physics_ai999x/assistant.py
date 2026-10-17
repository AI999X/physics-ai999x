"""Help for people, not parsers: what can I ask, how do I ask it, and what do I do when the answer is "not yet"?

    import physics_ai999x as physics
    physics.topics()                      # physics topics, with what can be computed and what is only known
    physics.templates("kinetic_energy")   # question formats that work, each one run before it is offered
    physics.suggest("A 2 kg ball. What is its kinetic energy?")   # a plain-language next step
    physics.explain(physics.ask("..."))   # the verified steps as sentences, with LaTeX

Nothing here changes how a question is answered: `ask()` and `solve()` decide. This module turns their refusals
into questions a person can act on, and shows what is possible before anyone has to guess a syntax.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import Answer, ask, pack

SENTENCE = {"thrown_up": "It is thrown straight up.", "inclined": "It is on an incline.",
            "frictionless": "The surface is frictionless.", "hanging": "It hangs at rest from a rope.",
            "spring_launch": "It is launched by a spring.", "free_fall": "It is dropped.",
            "from_rest": "It starts from rest.", "accelerated": "It speeds up.", "equilibrium": "It moves at constant speed."}
ASK_OVERRIDE = {("time", "rise"): "How long does it take to reach its highest point?"}
PLAIN = {
    "no_applicable_relation_chain": "I need one more quantity before I can work this out.",
    "unknown_target": "I could not tell which quantity you want me to find.",
    "unexplained_input": "You gave a number I could not place in the problem, so I did not guess what it means.",
    "ambiguous": "The question can be read in more than one way, and the readings give different answers.",
    "unsupported": "This kind of problem is outside what the engine can compute yet.",
    "verification_failed": "I computed a value but it did not pass the checks, so I am not showing it.",
    "unknown_name": "One of the quantity names is not in the vocabulary.",
}


def _topic_index() -> list:
    here = Path(__file__).resolve()
    for p in (here.parent / "pack" / "topics.json", here.parents[3] / "atlas" / "topics_public.json"):
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))["topics"]
    return []


def _labels() -> dict:
    out = {}
    for e in pack().terms.get("labels", []):
        out.setdefault((e["kind"], e.get("role", "plain")), e["phrase"])
    return out


# --- what can I ask? -------------------------------------------------------------------------------------------
def topics(area: str | None = None, computable_only: bool = False) -> list:
    """Physics topics (AI999X-native ids and names) with their status: which relations compute in each, and how much
    verified knowledge each holds. `status` is executable, machine-checked, under review, conceptual-only or
    unsupported; only certified relations ever compute an answer."""
    held = {r.key for r in pack().relations}
    out = []
    for t in _topic_index():
        if area and area.lower() not in (t["area"].lower(), t["id"].split(".")[1]):
            continue
        rel = [r for r in t["relations"] if r["key"] in held]
        if computable_only and not rel:
            continue
        out.append({"id": t["id"], "name": t["name"], "area": t["area"], "status": t["status"],
                    "relations": [r["key"] for r in rel], "computes": [r["name"] for r in rel],
                    "knowledge": t["knowledge"]})
    return out


_TEMPLATES: dict = {}


def templates(relation: str | None = None) -> list:
    """Question formats that work, per certified relation: a fill-in pattern and a filled example. Each example
    is run through `ask()` and offered only if it returns the relation's hand-worked reference value."""
    if not _TEMPLATES:
        _build_templates()
    rows = [t for k, ts in _TEMPLATES.items() for t in ts if relation in (None, k)]
    return rows


def _build_example_templates() -> None:
    """The phrasings each relation was certified with (pack/knowledge/question_examples.json), re-run here."""
    here = Path(__file__).resolve()
    path = next((x for x in (here.parent / "pack" / "knowledge" / "question_examples.json",
                             here.parents[3] / "knowledge" / "question_examples.json") if x.exists()), None)
    if path is None:
        return
    from ._units import to_si_value
    p = pack()
    names = {r.key: r.name for r in p.relations}
    for key, rows in json.loads(path.read_text(encoding="utf-8")).items():
        if key not in names or key in _TEMPLATES:
            continue
        for row in rows:
            a = ask(row["q"])
            if not a.solved or key not in a.models:
                continue
            kind = p.kinds.get((a.target or {}).get("kind"))
            want = to_si_value(float(row["value"]), row["unit"], kind) if kind else row["value"]
            if abs(a.value - want) <= 1e-4 * max(1e-30, abs(want)):
                pattern = re.sub(r"(?<![\w.])[-+]?\d+(?:\.\d+)?(?:e[-+]?\d+)?(?![\w.])", "<number>", row["q"])
                _TEMPLATES.setdefault(key, []).append({"relation": key, "name": names[key],
                                                       "finds": (a.target or {}).get("phrase", ""), "pattern": pattern,
                                                       "example": row["q"], "answer": f"{a.value:.6g} {a.unit}".strip()})


def _build_templates() -> None:
    shipped = Path(__file__).resolve().parent / "pack" / "templates.json"
    if shipped.exists():                                # verified when the package was built
        for t in json.loads(shipped.read_text(encoding="utf-8")):
            _TEMPLATES.setdefault(t["relation"], []).append(t)
        return
    _build_mechanics_templates()
    _build_example_templates()


def _build_mechanics_templates() -> None:
    p, labels = pack(), _labels()
    ref_path = Path(__file__).resolve().parent / "pack" / "knowledge" / "reference_cases.json"
    if not ref_path.exists():
        ref_path = Path(__file__).resolve().parents[3] / "knowledge" / "reference_cases.json"
    cases = json.loads(ref_path.read_text(encoding="utf-8")).get("cases", {}) if ref_path.exists() else {}
    from ._units import to_si_value
    for rel in p.relations:
        for case in cases.get(rel.key, []):
            tname, tval, tunit = case["expect"]
            ts = rel.symbols[tname]
            find = labels.get((ts.kind, ts.role))
            parts, pattern = [], []
            for n, (v, u) in case["given"].items():
                s = rel.symbols[n]
                name = labels.get((s.kind, s.role))
                if not name:
                    parts = None
                    break
                unit = "" if u in ("1", "") else f" {u}"
                parts.append(f"The {name} is {v:g}{unit}.")
                pattern.append(f"The {name} is <{name}>.")
            if not parts or not find:
                continue
            asked = ASK_OVERRIDE.get((ts.kind, ts.role), f"What is the {find}?")
            conds = [SENTENCE[c] for c in rel.requires if c in SENTENCE]
            if len(conds) != len(rel.requires):
                continue
            question = " ".join(conds + parts + [asked])
            a = ask(question)
            want = to_si_value(float(tval), tunit, p.kinds[ts.kind])
            if a.solved and abs(a.value - want) <= 1e-6 * max(1e-12, abs(want)) + 1e-12:
                _TEMPLATES.setdefault(rel.key, []).append({
                    "relation": rel.key, "name": rel.name, "finds": find, "pattern": " ".join(conds + pattern + [asked]),
                    "example": question, "answer": f"{a.value:.6g} {a.unit}".strip()})


# --- when the answer is "not yet" ---------------------------------------------------------------------------
def _phrase(kind: str, role: str) -> str:
    """The plainest wording of a (kind, role): the kind's own name when the vocabulary uses it, else its first label."""
    own = kind.replace("_", " ")
    phrases = [e["phrase"] for e in pack().terms.get("labels", []) if e["kind"] == kind and e.get("role", "plain") == role]
    if own in phrases:
        return own
    return phrases[0] if phrases else (f"{role.replace('_', ' ')} {own}" if role != "plain" else own)


def typed_needs(question: str) -> list:
    """What exactly is missing, from the typed reading of the question: the relations that produce the asked quantity
    in the question's context and use at least one stated quantity, ranked by how little they lack. Returns
    [{"relation", "missing": [(kind, role, phrase)], "uses": n}] best first; [] when the target is unknown or no
    relation fits (then nothing is asked: an unrelated formula sharing a kind of quantity is not a reason to ask)."""
    from . import compile_problem
    prob = compile_problem(question)
    if prob.target is None:
        return []
    tags, givens = set(prob.tags), list(prob.givens)
    rows = []
    for rel in pack().relations:
        if not set(rel.requires) <= tags or set(rel.excludes) & tags:
            continue
        tname = next((n for n, s in rel.symbols.items() if s.kind == prob.target.kind and s.takes(prob.target.role)), None)
        if tname is None:
            continue
        free, missing, used = list(givens), [], 0
        for n, s in rel.symbols.items():
            if n == tname:
                continue
            g = next((g for g in free if g.kind == s.kind and s.takes(g.role)), None)
            if g is not None:
                free.remove(g)
                used += g.source == "stated"
            elif s.default and not set(s.default.get("unless", ())) & tags:
                continue
            else:
                missing.append((s.kind, s.role, _phrase(s.kind, s.role)))
        # a relation that leaves a stated quantity unexplained does not describe this problem (a launch angle has no
        # place in uniform motion): asking for its other inputs would mislead
        unexplained = sum(1 for g in free if g.source == "stated")
        # with nothing stated, only a relation lacking ONE quantity is a useful question ("its momentum?"); several
        # missing inputs to a guessed formula would be a quiz, not a clarification
        if missing and (used or (not givens and len(missing) == 1)) and not unexplained:
            rows.append({"relation": rel.name, "key": rel.key, "missing": missing, "uses": used})
    rows.sort(key=lambda r: (len(r["missing"]), -r["uses"]))
    best = [r for r in rows if rows and len(r["missing"]) == len(rows[0]["missing"]) and r["uses"] == rows[0]["uses"]]
    return best


def _needs(answer: Answer) -> list:
    out = []
    for line in (answer.uncertainty or {}).get("would_need", []):
        m = re.match(r"(.+?) needs the (.+)$", line)
        if m:
            out.append({"relation": m.group(1), "quantity": m.group(2)})
    return out


def _topic_guess(question: str) -> list:
    """Topics whose search words share the question's content words (a pointer, not an answer)."""
    words = {w for w in re.findall(r"[a-z]{4,}", question.lower())} - {"what", "with", "that", "from", "this", "find",
                                                                      "much", "many", "does", "have", "into", "when"}
    scored = []
    for t in _topic_index():
        tw = set(t["search_words"]) | set(re.findall(r"[a-z]{4,}", t["name"].lower()))
        hit = len(words & tw) + sum(1 for w in words for x in tw if len(w) > 5 and (w.startswith(x[:5]) or x.startswith(w[:5])))
        if hit:
            scored.append((hit, t))
    scored.sort(key=lambda x: -x[0])
    return [t for _h, t in scored[:3]]


def suggest(question: str) -> dict:
    """Answer the question if possible; otherwise say plainly what is missing and how to ask again."""
    a = ask(question)
    if a.solved:
        return {"solved": True, "answer": a, "message": f"{(a.target or {}).get('phrase', 'answer')} = {a.value:.6g} {a.unit}"}
    cause = (a.uncertainty or {}).get("cause") or (a.uncertainty or {}).get("state") or a.status
    out = {"solved": False, "answer": a, "message": PLAIN.get(cause, a.message), "ask_back": [], "try": [], "topics": []}
    typed = typed_needs(question) if cause in ("no_applicable_relation_chain", "missing_information") else []
    if typed:                                                   # exactly what the fitting relations lack
        miss = [m for r in typed for m in r["missing"]]
        if any(k == "speed" and role == "initial" for k, role, _p in miss):
            out["ask_back"].append("If it starts from rest, say so: 'It starts from rest.'")
        seen = set()
        for _k, _r, phrase in miss:
            if phrase not in seen and len(out["ask_back"]) < 3:
                seen.add(phrase)
                out["ask_back"].append(f"What is the {phrase}? (add it to your question, with its unit)")
        out["needs"] = [{"relation": r["relation"], "missing": [p for *_x, p in r["missing"]]} for r in typed]
        for r in typed[:2]:
            out["try"] += [t["example"] for t in templates(r["key"])[:1]]
        return out
    needs = _needs(a)
    guess = _topic_guess(question)
    if needs and guess:
        # the question's own topic first; if none of the relations asking for input belongs to it, asking for their
        # inputs would mislead: point to the topic instead
        own = {r["name"] for t in guess[:1] for r in t["relations"]}
        if own & {n["relation"] for n in needs}:
            needs = sorted(needs, key=lambda n: n["relation"] not in own)
        else:
            needs = []
    if any("initial" in n["quantity"] for n in needs):          # the commonest omission comes first
        out["ask_back"].append("If it starts from rest, say so: 'It starts from rest.'")
    seen = set()
    for n in needs:                                             # the engine lists the most direct relation first
        q = n["quantity"]
        if q in seen or len(out["ask_back"]) >= 3:
            continue
        seen.add(q)
        out["ask_back"].append(f"What is the {q}? (add it to your question, with its unit)")
    for n in needs[:2]:
        key = next((r.key for r in pack().relations if r.name == n["relation"]), None)
        out["try"] += [t["example"] for t in templates(key)[:1]] if key else []
    if cause in ("unknown_target", "unsupported") or not needs:
        out["topics"] = [{"id": t["id"], "name": t["name"], "status": t["status"],
                          "computes": [r["name"] for r in t["relations"]]} for t in guess]
        if out["topics"]:
            top = out["topics"][0]
            out["message"] = ("This question belongs to " + top["name"] + ". " +
                              ("The engine computes there: " + ", ".join(top["computes"][:6]) + "; this particular question is "
                               "not one of them yet." if top["computes"] else
                               "The knowledge base covers this topic, but the engine cannot compute in it yet."))
    return out


# --- explaining a verified answer -------------------------------------------------------------------------------
def explain(answer: Answer) -> dict:
    """The verified steps of an answer as sentences, each with its LaTeX; assumptions and checks spelled out."""
    if not answer.solved:
        s = suggest(answer.question) if isinstance(answer.question, str) else {"message": answer.message}
        return {"solved": False, "text": s["message"], "steps": []}
    steps = []
    for i, s in enumerate(answer.steps, 1):
        given = ", ".join(f"{k} = {v['value']:.6g} {v['unit']}".rstrip() for k, v in s["inputs"].items())
        steps.append({"n": i, "text": f"Step {i}. Use {s['name'].lower()}, {s['equation']}. With {given}, "
                                      f"{s['target']} = {s['result']:.6g} {s['unit']}.".replace("  ", " "),
                      "latex": s.get("equation_latex", ""), "result_latex": s.get("solved_latex", "")})
    text = [x["text"] for x in steps]
    if answer.assumptions:
        text.append("Assumed: " + "; ".join(answer.assumptions) + ".")
    v = answer.verification
    text.append(f"Checked: the result satisfies every equation used (largest residual {v.get('max_residual', 0):.1e})"
                + (f" and {v.get('independent_paths')} independent derivation paths agree." if v.get("independent_paths", 1) > 1 else "."))
    return {"solved": True, "text": " ".join(text), "steps": steps, "latex": answer.latex()}
