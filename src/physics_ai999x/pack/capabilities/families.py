"""Physics computational model families for problems with several bodies, states or stages (domain code: loaded by
the pack from models/physics/capabilities/, never part of the universal core).

Each family is a function `scenario -> System | Refusal | None`: None means "not this kind of problem"; a Refusal
means "this kind of problem, but not answerable as stated" (with the reason); a System is a typed set of coupled
equations for the shared solver. Symbols carry the body and state they belong to (m1, u1 = body 1 before, v1 = body 1
after); quantities of the same dimension are never interchanged.
"""
from __future__ import annotations

import math
import re

import sympy as sp

from .reader import Scenario, body_named, percent_of, rest_bodies
from .solver import Refusal, Sym, System

G0 = 9.80665
X = lambda n: sp.Symbol(n, real=True)          # noqa: E731
G_ASSUME = "standard gravity g = 9.80665 m/s^2 near Earth's surface"
MATERIAL_C = {"water": 4186.0, "aluminum": 900.0, "aluminium": 900.0, "copper": 387.0, "iron": 452.0, "steel": 452.0,
              "glass": 840.0, "lead": 128.0, "brass": 380.0, "silver": 235.0, "gold": 129.0}


def _g(sc: Scenario, sources, assumptions, known):
    if "non_earth" in sc.tags:
        return False
    known["g"], sources["g"] = G0, f"default: {G_ASSUME}"
    assumptions.append(G_ASSUME)
    return True


def _who(sc, bd):
    return f"body {bd.idx + 1}" + (f" ({bd.noun})" if bd.noun else "")


def _sentence_has(sc, pos, pattern):
    a, b = sc.sentence_of(pos)
    return re.search(pattern, sc.low[a:b]) is not None


def _bare_after(sc, pattern):
    m = re.search(pattern + r"\s*(?:is|of|=|was)?\s*(\d*\.?\d+)", sc.low)
    return float(m.group(1)) if m else None


# --- collisions and recoil ----------------------------------------------------------------------------------------
_COLLIDE = r"\b(collid\w*|collision|hits|strikes|struck|sticks?|stuck|coupl\w*|embed\w*|adhere\w*|crash\w*|rams?|bounces?|elastic|rear-ends?|rear-ended|runs into|ran into|slams into|smashes into)\b"
_STICK = r"\b(stick|sticks|stuck|couple|coupled|couples|embed\w*|adhere\w*|move together|moving together|combined|lock together|perfectly inelastic|joined)\b"
_OPPOSITE = r"\b(opposite directions?|head[- ]on|toward each other|towards each other|approaching each other)\b"
_RECOIL = r"\b(recoil\w*|fires|fired|explod\w*|explosion|breaks? apart|pushes? off|push off|pushes away|throws|jumps? off|separates?)\b"


def collision(sc: Scenario, pack):
    if not re.search(_COLLIDE, sc.low) or re.search(_RECOIL, sc.low) and re.search(r"\b(at rest|from rest)\b", sc.low) and not re.search(_STICK, sc.low):
        return None
    if not re.search(r"\b(speed|velocity|how fast|kinetic energy|mass)\b", sc.low[sc.asking[0]:sc.asking[1]]) or not sc.bodies:
        return None
    if len(sc.bodies) > 2:
        return Refusal("unsupported", "Collisions of more than two bodies (or several collisions in sequence) are not "
                       "supported yet.", "unsupported_structure", "collision_1d")
    if re.search(r"\b(angle|degrees|°|north|east|perpendicular|components?)\b", sc.low):
        return Refusal("unsupported", "This looks like a two-dimensional collision, which needs momentum in components; "
                       "only collisions along a line are supported yet.", "unsupported_structure", "collision_1d")
    sticky = re.search(_STICK, sc.low) is not None
    elastic = re.search(r"\belastic", sc.low) is not None and not re.search(r"\binelastic", sc.low)
    if sticky and elastic:
        return Refusal("needs_clarification", "The wording says both that the bodies stick and that the collision is "
                       "elastic.", "contradictory_conditions", "collision_1d")
    known, sources, assumptions, bodies = {}, {}, ["motion along one straight line", "no external horizontal force during the collision"], []
    sym = {"m1": Sym("mass", "mass of body 1"), "m2": Sym("mass", "mass of body 2"),
           "u1": Sym("speed", "velocity of body 1 before"), "u2": Sym("speed", "velocity of body 2 before"),
           "v1": Sym("speed", "velocity of body 1 after"), "v2": Sym("speed", "velocity of body 2 after"),
           "K": Sym("energy", "kinetic energy lost in the collision")}
    two = len(sc.bodies) == 2
    if not two:                                   # the second body named in the question, its mass asked
        if not (sticky and re.search(r"\bmass\b", sc.low[sc.asking[0]:sc.asking[1]])):
            return None
    for bd in sc.bodies:
        k = bd.idx + 1
        sym[f"m{k}"].meaning = f"mass of {_who(sc, bd)}"
        known[f"m{k}"], sources[f"m{k}"] = bd.mass.value, f"stated: {bd.mass.text}"
        bodies.append({"body": k, "noun": bd.noun, "mass": bd.mass.text})
    rest = rest_bodies(sc) if two else set()        # one stated mass: "at rest" is the unnamed second body
    if not two and re.search(r"\b(at rest|stationary|initially at rest)\b", sc.low):
        known["u2"], sources["u2"] = 0.0, "implied: the second body is at rest"
    speeds = sc.of_kind("speed")
    common_final = []
    for q in speeds:
        if q.each and q.state == "initial" and two:
            for k in (1, 2):
                known[f"u{k}"], sources[f"u{k}"] = q.value, f"stated: {q.text} each"
            continue
        if q.body is None:
            continue
        k = q.body + 1
        clause = sc.low[max(0, q.start - 60):q.start]
        sign = -1.0 if (q.state == "final" and re.search(r"\b(back|backward|backwards|rebound\w*|bounces? back|reverses?)\b", sc.low[q.start - 60:q.end + 30])) else 1.0
        if q.state == "final":
            if sticky or re.search(r"\b(together|combined|both|they)\b", clause):
                common_final.append(q)
                continue
            name = f"v{k}"
        else:
            name = f"u{k}"
        if name in known:
            return Refusal("needs_clarification", f"Two values are stated for the {sym[name].meaning}.", "ambiguous_quantity", "collision_1d")
        known[name], sources[name] = sign * q.value, f"stated: {q.text}"
    for k in (1, 2):                                # a body said to be at rest cannot own a stated initial speed:
        if k - 1 in rest and f"u{k}" in known and known[f"u{k}"] != 0.0:   # "hits a block resting ... at 10 m/s"
            other = 3 - k
            if f"u{other}" in known or not two:
                return Refusal("needs_clarification", "A body described as at rest is also given a speed.",
                               "ambiguous_quantity", "collision_1d")
            known[f"u{other}"], sources[f"u{other}"] = known.pop(f"u{k}"), sources.pop(f"u{k}") + " (the moving body)"
        if k - 1 in rest and f"u{k}" not in known:
            known[f"u{k}"], sources[f"u{k}"] = 0.0, "implied: at rest before the collision"
    if common_final:
        if len(common_final) > 1:
            return Refusal("needs_clarification", "More than one final velocity is stated.", "ambiguous_quantity", "collision_1d")
        known["v1"], sources["v1"] = common_final[0].value, f"stated: {common_final[0].text}"
    if re.search(_OPPOSITE, sc.low) and known.get("u1", 0) > 0 and known.get("u2", 0) > 0:
        known["u2"] = -known["u2"]
        sources["u2"] += " (opposite direction: negative)"
        assumptions.append("the first body's direction of motion is positive")
    m1, m2, u1, u2, v1, v2, K = (X(n) for n in ("m1", "m2", "u1", "u2", "v1", "v2", "K"))
    eqs = [("conservation of momentum", sp.Eq(m1 * u1 + m2 * u2, m1 * v1 + m2 * v2)),
           ("kinetic energy lost", sp.Eq(K, m1 * u1**2 / 2 + m2 * u2**2 / 2 - m1 * v1**2 / 2 - m2 * v2**2 / 2))]
    cons = []
    if sticky:
        eqs.append(("the bodies move together after", sp.Eq(v1, v2)))
        title = "Perfectly inelastic collision"
        assumptions.append("the bodies stick together and share one velocity afterwards")
    elif elastic:
        eqs.append(("conservation of kinetic energy (elastic)", sp.Eq(K, 0)))
        cons.append(("the bodies must actually collide (the 'no collision' root is excluded)",
                     lambda n: not (abs(n["v1"] - n["u1"]) < 1e-9 * max(1, abs(n["u1"])) and abs(n["v2"] - n["u2"]) < 1e-9 * max(1, abs(n["u2"])))))
        title = "Elastic collision"
        assumptions.append("kinetic energy is conserved")
    else:
        title = "Collision (momentum conservation)"
    a, b = sc.asking
    ask = sc.low[a:b]
    who = body_named(sc, (a, b))
    cues = [(m.start(), w) for w, pat in (("energy", r"kinetic energy"), ("speed", r"\b(?:speed|velocity|how fast)\b"),
                                           ("mass", r"\bmass of\b|\bwhat mass\b|\bhow (?:heavy|massive)\b"))
            for m in [re.search(pat, ask)] if m]
    first = min(cues)[1] if cues else None
    if len(cues) > 1:
        assumptions.append(f"the question asks for more than one quantity; this answers the first ({first})")
    if first == "energy" and re.search(r"\b(lost|loss|dissipated|converted|transformed|decrease)\b", ask):
        target, phrase, mag = "K", "kinetic energy lost", False
    elif first == "mass":
        if two and who is None:
            unknown = [k for k in (1, 2) if f"m{k}" not in known]
            if len(unknown) != 1:
                return Refusal("needs_clarification", "I could not tell whose mass is asked for.", "unknown_target", "collision_1d")
            who = unknown[0] - 1
        target, phrase, mag = (f"m{(who if who is not None else 1) + 1}" if two else "m2"), "mass", False
        if not two:
            sym["m2"].meaning = "mass of the second body"
    elif first == "speed":
        initial = re.search(r"\b(initial|before|was moving|originally|how fast was|just before)\b", ask) and not re.search(r"\b(after|final)\b", ask)
        if initial:
            k = (who if who is not None else next((i for i in (0, 1) if f"u{i + 1}" not in known), None))
            if k is None:
                return Refusal("needs_clarification", "I could not tell which body's initial velocity is asked for.", "unknown_target", "collision_1d")
            target = f"u{k + 1}"
        elif sticky:
            target = "v1"
        else:
            if who is None:
                unknown = [k for k in (1, 2) if f"v{k}" not in known]
                if len(unknown) != 1:
                    return Refusal("needs_clarification", "I could not tell which body's velocity after the collision is "
                                   "asked for; say which body.", "unknown_target", "collision_1d")
                who = unknown[0] - 1
            target = f"v{who + 1}"
        phrase, mag = ("speed" if "speed" in ask or "how fast" in ask else "velocity"), True
    else:
        return None
    if not sticky and not elastic and not any(n in known for n in ("v1", "v2")) and target != "K":
        return Refusal("needs_clarification", "A collision with neither 'they stick together' nor 'elastic' nor a "
                       "stated velocity after it is not determined: say which kind of collision it is.",
                       "underdetermined", "collision_1d", would_need=["kind of collision (elastic or sticking together)"])
    return System("collision_1d", title, sym, eqs, known, sources, target, phrase, cons, assumptions, mag, bodies)


def recoil(sc: Scenario, pack):
    if not (re.search(_RECOIL, sc.low) and re.search(r"\b(at rest|from rest|stationary|initially at rest)\b", sc.low)):
        return None
    if len(sc.bodies) != 2 or re.search(_STICK, sc.low):
        return None
    a, b = sc.asking
    ask = sc.low[a:b]
    if not re.search(r"\b(speed|velocity|how fast|mass)\b", ask):
        return None
    known, sources, sym, bodies = {}, {}, {}, []
    for bd in sc.bodies:
        k = bd.idx + 1
        sym[f"m{k}"] = Sym("mass", f"mass of {_who(sc, bd)}")
        sym[f"v{k}"] = Sym("speed", f"velocity of {_who(sc, bd)} after")
        known[f"m{k}"], sources[f"m{k}"] = bd.mass.value, f"stated: {bd.mass.text}"
        bodies.append({"body": k, "noun": bd.noun, "mass": bd.mass.text})
    for q in sc.of_kind("speed"):
        if q.body is None:
            continue
        k = q.body + 1
        known[f"v{k}"], sources[f"v{k}"] = q.value, f"stated: {q.text}"
    who = body_named(sc, (a, b))
    if re.search(r"\bmass\b", ask):
        target = f"m{(who if who is not None else 0) + 1}"
        if target in known:
            return None
    else:
        missing = [k for k in (1, 2) if f"v{k}" not in known]
        if who is None and len(missing) == 1:
            who = missing[0] - 1
        if who is None:
            return Refusal("needs_clarification", "I could not tell which body's speed is asked for.", "unknown_target", "recoil")
        target = f"v{who + 1}"
    m1, m2, v1, v2 = X("m1"), X("m2"), X("v1"), X("v2")
    eqs = [("total momentum stays zero", sp.Eq(m1 * v1 + m2 * v2, 0))]
    return System("recoil", "Recoil from rest", sym, eqs, known, sources, target,
                  "speed" if "speed" in ask else ("mass" if "mass" in ask else "velocity"), [],
                  ["the system is at rest before", "no external horizontal force"], True, bodies)


# --- projectiles --------------------------------------------------------------------------------------------------
def projectile(sc: Scenario, pack):
    if not re.search(r"\b(launch\w*|thrown|throws?|kick\w*|fired|shot|projectile|tossed|leaves|rolls off|released|hit|batted|served|jumps?)\b", sc.low):
        return None
    horizontal = re.search(r"\bhorizontally\b|\bhorizontal (?:speed|velocity) of\b", sc.low) is not None
    angles = sc.of_kind("angle")
    if not (horizontal or angles) or re.search(r"\b(straight up|vertically|straight down|incline|ramp|slope)\b", sc.low):
        return None
    if len(sc.bodies) > 1 or re.search(r"\b(then|bounces)\b", sc.low):
        return None
    known, sources, assumptions = {}, {}, ["no air resistance", "level landing ground unless a height is stated"]
    sym = {"v0": Sym("speed", "launch speed"), "th": Sym("angle", "launch angle above the horizontal"),
           "t": Sym("time", "time of flight"), "x": Sym("length", "horizontal distance (range)"),
           "h0": Sym("length", "launch height above the landing point"), "H": Sym("length", "maximum height above the landing point"),
           "vy": Sym("speed", "vertical velocity at landing"), "vf": Sym("speed", "speed at landing"),
           "g": Sym("acceleration", "acceleration due to gravity")}
    if not _g(sc, sources, assumptions, known):
        return Refusal("needs_clarification", "Off Earth, state the acceleration due to gravity.", "underdetermined", "projectile")
    if horizontal:
        known["th"], sources["th"] = 0.0, "implied: launched horizontally"
    if len(angles) > 1:
        return Refusal("needs_clarification", "More than one angle is stated.", "ambiguous_quantity", "projectile")
    if angles:
        sign = -1.0 if re.search(r"below the horizontal", sc.low[angles[0].end:angles[0].end + 30]) else 1.0
        known["th"], sources["th"] = sign * angles[0].value, f"stated: {angles[0].text}"
    speeds = sc.of_kind("speed")
    a, b = sc.asking
    ask = sc.low[a:b]
    for q in speeds:
        if "v0" in known:
            return Refusal("needs_clarification", "More than one speed is stated.", "ambiguous_quantity", "projectile")
        known["v0"], sources["v0"] = q.value, f"stated: {q.text}"
    for q in sc.of_kind("length"):
        ctx = sc.low[max(0, q.start - 45):q.end + 30]
        if re.search(r"\b(height|high|tall|cliff|above the (?:ground|water|floor)|table|roof|building|tower|bridge|balcony|altitude)\b", ctx) \
                and not re.search(r"\b(range|horizontal|away|throw of|distance of|lands)\b", sc.low[max(0, q.start - 20):q.start]):
            if "h0" in known:
                return Refusal("needs_clarification", "More than one height is stated.", "ambiguous_quantity", "projectile")
            known["h0"], sources["h0"] = q.value, f"stated: {q.text}"
        else:
            if "x" in known:
                return Refusal("needs_clarification", "More than one horizontal distance is stated.", "ambiguous_quantity", "projectile")
            known["x"], sources["x"] = q.value, f"stated: {q.text}"
    for q in sc.of_kind("time"):
        known["t"], sources["t"] = q.value, f"stated: {q.text}"
    if "h0" not in known:
        known["h0"], sources["h0"] = 0.0, "implied: it lands at the height it was launched from"
    v0, th, t, x, h0, H, vy, vf, g = (X(n) for n in ("v0", "th", "t", "x", "h0", "H", "vy", "vf", "g"))
    eqs = [("horizontal motion (constant velocity)", sp.Eq(x, v0 * sp.cos(th) * t)),
           ("vertical motion back to the landing height", sp.Eq(0, h0 + v0 * sp.sin(th) * t - g * t**2 / 2)),
           ("vertical velocity at landing", sp.Eq(vy, v0 * sp.sin(th) - g * t)),
           ("speed at landing", sp.Eq(vf**2, (v0 * sp.cos(th))**2 + vy**2))]
    if re.search(r"\b(maximum height|max height|how high|highest point|peak height|greatest height)\b", ask):
        if known.get("th", 1.0) <= 0:
            return Refusal("needs_clarification", "Launched horizontally or downward, the highest point is the launch point.",
                           "trivial", "projectile")
        eqs.append(("height of the highest point", sp.Eq(H, h0 + (v0 * sp.sin(th))**2 / (2 * g))))
        target, phrase = "H", "maximum height"
    elif re.search(r"\b(how far|range|horizontal distance|how far away|distance from the base|lands? .* from)\b", ask):
        target, phrase = "x", "horizontal distance"
    elif re.search(r"\b(how long|time of flight|time|in the air)\b", ask):
        target, phrase = "t", "time of flight"
    elif re.search(r"\b(initial speed|launch speed|initial velocity|how fast .* (?:thrown|launched|kicked|released)|speed .* (?:thrown|launched|kicked|released|leave|left))\b", ask):
        target, phrase = "v0", "launch speed"
    elif re.search(r"\b(speed|velocity)\b", ask) and re.search(r"\b(hits?|lands?|strikes?|impact|reaches the ground|ground)\b", ask):
        target, phrase = "vf", "speed at landing"
    elif re.search(r"\bangle\b", ask):
        target, phrase = "th", "launch angle"
    else:
        return None
    cons = [("time of flight is positive", lambda n: n["t"] > 0), ("launch speed is positive", lambda n: n["v0"] > 0),
            ("speed at landing is positive", lambda n: n["vf"] >= 0),
            ("the launch angle lies between -90 and 90 degrees", lambda n: -math.pi / 2 < n["th"] < math.pi / 2),
            ("the range is not negative", lambda n: n["x"] >= 0)]
    return System("projectile", "Projectile motion", sym, eqs, known, sources, target, phrase, cons, assumptions, False)


# --- connected bodies, elevators, curves ------------------------------------------------------------------------
def pulley(sc: Scenario, pack):
    if not re.search(r"\b(pulley|atwood)\b", sc.low) or len(sc.bodies) != 2:
        return None
    a, b = sc.asking
    ask = sc.low[a:b]
    if re.search(r"\b(acceleration|how fast .* accelerat)\b", ask):
        target, phrase = "a", "acceleration"
    elif re.search(r"\btension\b", ask):
        target, phrase = "T", "tension"
    else:
        return None
    known, sources, assumptions = {}, {}, ["light, inextensible string", "massless, frictionless pulley"]
    _g(sc, sources, assumptions, known)
    on_table = [bd for bd in sc.bodies if _sentence_has(sc, bd.anchor, r"\b(table|horizontal surface|surface|floor|desk|ice)\b")
                and re.search(r"\b(on|across|along)\b", sc.low[bd.anchor:bd.anchor + 60] + sc.low[max(0, bd.anchor - 30):bd.anchor])]
    sym = {"T": Sym("force", "tension in the string"), "a": Sym("acceleration", "acceleration of the bodies"),
           "g": Sym("acceleration", "acceleration due to gravity")}
    if re.search(r"\b(incline|ramp|slope)\b", sc.low):
        return Refusal("unsupported", "Pulley systems with an incline are not supported yet.", "unsupported_structure", "pulley")
    if len(on_table) == 1:
        tb = on_table[0]
        hb = next(bd for bd in sc.bodies if bd is not tb)
        sym.update(mt=Sym("mass", f"mass on the surface ({tb.noun or 'body'})"), mh=Sym("mass", f"hanging mass ({hb.noun or 'body'})"),
                   mu=Sym("friction_coefficient", "coefficient of kinetic friction"))
        known["mt"], sources["mt"] = tb.mass.value, f"stated: {tb.mass.text}"
        known["mh"], sources["mh"] = hb.mass.value, f"stated: {hb.mass.text}"
        mu = _bare_after(sc, r"coefficient of (?:kinetic )?friction")
        if re.search(r"\b(frictionless|smooth|no friction|negligible friction)\b", sc.low):
            known["mu"], sources["mu"] = 0.0, "implied: frictionless surface"
        elif mu is not None:
            known["mu"], sources["mu"] = mu, f"stated: coefficient of friction {mu}"
        else:
            return Refusal("needs_clarification", "A block on a surface pulled by a hanging mass: say whether the surface is "
                           "frictionless or give the coefficient of kinetic friction.", "underdetermined", "pulley",
                           would_need=["coefficient of kinetic friction"])
        T, A, g, mt, mh, mu_ = (X(n) for n in ("T", "a", "g", "mt", "mh", "mu"))
        eqs = [("hanging mass: weight minus tension", sp.Eq(mh * g - T, mh * A)),
               ("block on the surface: tension minus friction", sp.Eq(T - mu_ * mt * g, mt * A))]
        cons = [("the system accelerates (otherwise friction holds it at rest)", lambda n: n["a"] > 0)]
        return System("pulley_table", "Block on a surface pulled over a pulley", sym, eqs, known, sources, target, phrase, cons,
                      assumptions, False)
    # "over a pulley" alone does not say how the masses are arranged: both hanging, or one on a surface
    if not re.search(r"\b(both hang\w*|hang\w* (?:from|on) (?:either|each|opposite)|either side|each end|both ends|opposite ends|atwood)\b", sc.low):
        return Refusal("needs_clarification", "Two masses joined over a pulley: say whether both hang (one on each side) "
                       "or one rests on a surface (and whether that surface has friction).", "underdetermined", "pulley",
                       would_need=["arrangement of the masses (both hanging, or one on a surface)"])
    b1, b2 = sc.bodies
    sym.update(m1=Sym("mass", f"mass of {_who(sc, b1)}"), m2=Sym("mass", f"mass of {_who(sc, b2)}"))
    known["m1"], sources["m1"] = b1.mass.value, f"stated: {b1.mass.text}"
    known["m2"], sources["m2"] = b2.mass.value, f"stated: {b2.mass.text}"
    T, A, g, m1, m2 = (X(n) for n in ("T", "a", "g", "m1", "m2"))
    eqs = [("body 2: weight minus tension", sp.Eq(m2 * g - T, m2 * A)), ("body 1: tension minus weight", sp.Eq(T - m1 * g, m1 * A))]
    return System("atwood", "Two masses over a pulley", sym, eqs, known, sources, target, phrase,
                  [("tension is positive", lambda n: n["T"] > 0)], assumptions, target == "a")


def elevator(sc: Scenario, pack):
    if not re.search(r"\b(elevator|lift)\b", sc.low) or len(sc.bodies) != 1:
        return None
    a, b = sc.asking
    ask = sc.low[a:b]
    if not re.search(r"\b(scale|apparent weight|normal force|reads?|reading|force .* (?:floor|scale))\b", ask):
        return None
    up = r"(accelerat\w* (?:upward|up)|speeding up .* (?:going |moving )?up|starts? (?:moving|going) up|slowing down .* (?:going |moving )?down|decelerat\w* .* (?:going |moving )?down)"
    down = r"(accelerat\w* (?:downward|down)|slowing down .* (?:going |moving )?up|speeding up .* (?:going |moving )?down|starts? (?:moving|going) down|decelerat\w* .* (?:going |moving )?up)"
    known, sources, assumptions = {}, {}, ["the scale reads the normal force"]
    _g(sc, sources, assumptions, known)
    bd = sc.bodies[0]
    known["m"], sources["m"] = bd.mass.value, f"stated: {bd.mass.text}"
    accs = sc.of_kind("acceleration")
    if re.search(r"\b(constant (?:speed|velocity)|at rest|stationary)\b", sc.low) and not accs:
        known["acc"], sources["acc"] = 0.0, "implied: no acceleration"
    elif accs:
        isup, isdown = re.search(up, sc.low), re.search(down, sc.low)
        if bool(isup) == bool(isdown):
            return Refusal("needs_clarification", "Say whether the elevator's acceleration points up or down.",
                           "ambiguous", "elevator")
        known["acc"], sources["acc"] = (1 if isup else -1) * accs[0].value, f"stated: {accs[0].text} ({'up' if isup else 'down'})"
    else:
        return Refusal("needs_clarification", "State the elevator's acceleration (or that it moves at constant speed).",
                       "underdetermined", "elevator", would_need=["acceleration of the elevator"])
    N, m, acc, g = X("N"), X("m"), X("acc"), X("g")
    sym = {"N": Sym("force", "scale reading (normal force)"), "m": Sym("mass", "mass of the person"),
           "acc": Sym("acceleration", "acceleration (up is positive)"), "g": Sym("acceleration", "acceleration due to gravity")}
    return System("elevator", "Apparent weight in an elevator", sym, [("Newton's second law, vertical", sp.Eq(N - m * g, m * acc))],
                  known, sources, "N", "scale reading", [("the scale pushes up", lambda n: n["N"] >= 0)], assumptions, False)


def curve(sc: Scenario, pack):
    banked = re.search(r"\b(bank\w*)\b", sc.low)
    flat = re.search(r"\b(flat|unbanked|level|horizontal)\s+(?:curve|turn|road)", sc.low) and re.search(r"coefficient of (?:static )?friction", sc.low)
    if not (banked or flat) or not re.search(r"\b(curve|turn|bend|track|corner)\b", sc.low):
        return None
    known, sources, assumptions = {}, {}, ["uniform circular motion"]
    _g(sc, sources, assumptions, known)
    a, b = sc.asking
    ask = sc.low[a:b]
    for q in sc.of_kind("speed"):
        known["v"], sources["v"] = q.value, f"stated: {q.text}"
    for q in sc.of_kind("length"):
        known["r"], sources["r"] = q.value, f"stated: {q.text}"
    v, r, g = X("v"), X("r"), X("g")
    sym = {"v": Sym("speed", "speed on the curve"), "r": Sym("length", "radius of the curve"), "g": Sym("acceleration", "gravity")}
    if banked and not flat:
        sym["th"] = Sym("angle", "banking angle")
        for q in sc.of_kind("angle"):
            known["th"], sources["th"] = q.value, f"stated: {q.text}"
        assumptions.append("no friction needed: the ideal banking angle")
        th = X("th")
        target = "th" if re.search(r"\bangle\b", ask) else ("v" if re.search(r"\b(speed|how fast)\b", ask) else ("r" if "radius" in ask else None))
        if target is None:
            return None
        return System("banked_curve", "Ideal banking of a curve", sym, [("ideal banking", sp.Eq(sp.tan(th), v**2 / (r * g)))],
                      known, sources, target, {"th": "banking angle", "v": "speed", "r": "radius"}[target],
                      [("angle between 0 and 90 degrees", lambda n: 0 < n["th"] < math.pi / 2), ("speed positive", lambda n: n["v"] > 0)],
                      assumptions, False)
    sym["mu"] = Sym("friction_coefficient", "coefficient of static friction")
    mu = _bare_after(sc, r"coefficient of (?:static )?friction")
    if mu is not None:
        known["mu"], sources["mu"] = mu, f"stated: coefficient of static friction {mu}"
    target = "v" if re.search(r"\b(speed|how fast)\b", ask) else ("mu" if "coefficient" in ask else None)
    if target is None:
        return None
    assumptions.append("friction at its maximum supplies the centripetal force")
    mu_ = X("mu")
    return System("flat_curve", "Maximum speed on a flat curve", sym, [("friction supplies the centripetal force", sp.Eq(mu_ * g, v**2 / r))],
                  known, sources, target, "maximum speed" if target == "v" else "coefficient of friction",
                  [("speed positive", lambda n: n["v"] > 0)], assumptions, False)


# --- heat --------------------------------------------------------------------------------------------------------
def calorimetry(sc: Scenario, pack):
    if not re.search(r"\b(placed in|dropped into|poured into|mixed|added to|immersed in|put into|final temperature|equilibrium temperature|in contact)\b", sc.low):
        return None
    if re.search(r"\b(ice|melt\w*|freez\w*|boil\w*|steam|evaporat\w*|condens\w*|vapor)\b", sc.low):
        return Refusal("unsupported", "Mixing with a phase change (melting, boiling) is not supported yet.", "unsupported_structure", "calorimetry")
    temps = sc.of_kind("temperature")
    if len(sc.bodies) != 2 or len(temps) < 1:
        return None
    known, sources, assumptions, sym, bodies = {}, {}, ["an insulated system: heat lost by one body is gained by the other",
                                                         "no phase change"], {}, []
    for bd in sc.bodies:
        k = bd.idx + 1
        sym[f"m{k}"] = Sym("mass", f"mass of {_who(sc, bd)}")
        sym[f"c{k}"] = Sym("specific_heat", f"specific heat of {_who(sc, bd)}")
        sym[f"T{k}"] = Sym("temperature", f"initial temperature of {_who(sc, bd)}")
        known[f"m{k}"], sources[f"m{k}"] = bd.mass.value, f"stated: {bd.mass.text}"
        bodies.append({"body": k, "noun": bd.noun, "mass": bd.mass.text})
    for q in temps:
        if q.body is None:
            continue
        name = f"T{q.body + 1}"
        if name in known:
            if re.search(r"\b(final|equilibrium|ends?)\b", sc.low[max(0, q.start - 40):q.start]):
                known["Tf"], sources["Tf"] = q.value, f"stated: {q.text}"
                continue
            return Refusal("needs_clarification", f"Two temperatures are stated for {sym[name].meaning[19:]}.", "ambiguous_quantity", "calorimetry")
        if re.search(r"\b(final|equilibrium)\b", sc.low[max(0, q.start - 40):q.start]):
            known["Tf"], sources["Tf"] = q.value, f"stated: {q.text}"
        else:
            known[name], sources[name] = q.value, f"stated: {q.text}"
    for q in sc.of_kind("specific_heat"):
        if q.body is not None:
            known[f"c{q.body + 1}"], sources[f"c{q.body + 1}"] = q.value, f"stated: {q.text}"
    for bd in sc.bodies:
        k = bd.idx + 1
        if f"c{k}" not in known:
            mat = next((m for m in MATERIAL_C if re.search(r"\b" + m + r"\b", bd.noun or "")), None) or next(
                (m for m in MATERIAL_C if re.search(r"\b" + m + r"\b", sc.low[bd.mass.end:bd.mass.end + 25])), None)
            if mat:
                known[f"c{k}"], sources[f"c{k}"] = MATERIAL_C[mat], f"default: specific heat of {mat} {MATERIAL_C[mat]:g} J/(kg*K)"
                assumptions.append(f"specific heat of {mat} {MATERIAL_C[mat]:g} J/(kg*K) (typical value)")
    sym["Tf"] = Sym("temperature", "common final temperature")
    a, b = sc.asking
    ask = sc.low[a:b]
    if re.search(r"\b(final|equilibrium|resulting) temperature\b|\btemperature .* (?:final|end|reach)", ask) or re.search(r"\bwhat .* temperature\b", ask):
        target, phrase = "Tf", "final temperature"
    elif re.search(r"\bspecific heat\b", ask):
        target = next((f"c{k}" for k in (1, 2) if f"c{k}" not in known), None)
        phrase = "specific heat"
    elif re.search(r"\bmass\b", ask):
        target, phrase = next((f"m{k}" for k in (1, 2) if f"m{k}" not in known), None), "mass"
    else:
        return None
    if target is None:
        return None
    m1, m2, c1, c2, T1, T2, Tf = (X(n) for n in ("m1", "m2", "c1", "c2", "T1", "T2", "Tf"))
    eqs = [("heat lost = heat gained", sp.Eq(m1 * c1 * (Tf - T1) + m2 * c2 * (Tf - T2), 0))]
    cons = [("the final temperature lies between the two initial temperatures",
             lambda n: min(n["T1"], n["T2"]) - 1e-9 <= n["Tf"] <= max(n["T1"], n["T2"]) + 1e-9)]
    return System("calorimetry", "Mixing to thermal equilibrium", sym, eqs, known, sources, target, phrase, cons, assumptions, False, bodies)


# --- circuits ----------------------------------------------------------------------------------------------------
def network(sc: Scenario, pack):
    series, parallel = re.search(r"\bseries\b", sc.low), re.search(r"\bparallel\b", sc.low)
    if not (series or parallel):
        return None
    kind = "resistance" if len(sc.of_kind("resistance")) >= 2 else ("capacitance" if len(sc.of_kind("capacitance")) >= 2 else None)
    if kind is None:
        return None
    if series and parallel:
        return Refusal("unsupported", "Mixed series-parallel networks are not supported yet: give one series or one "
                       "parallel group.", "unsupported_structure", "network")
    elems = sc.of_kind(kind)
    n = len(elems)
    if n > 6:
        return None
    comp = "R" if kind == "resistance" else "C"
    known, sources, sym = {}, {}, {}
    for i, q in enumerate(elems, 1):
        sym[f"{comp}{i}"] = Sym(kind, f"{q.text} {'resistor' if comp == 'R' else 'capacitor'}")
        known[f"{comp}{i}"], sources[f"{comp}{i}"] = q.value, f"stated: {q.text}"
    volts = sc.of_kind("voltage")
    if len(volts) == 1:
        known["V"], sources["V"] = volts[0].value, f"stated: {volts[0].text}"
    elif len(volts) > 1:
        return None
    amps = sc.of_kind("current")
    if comp == "R" and len(amps) == 1:
        known["I"], sources["I"] = amps[0].value, f"stated: {amps[0].text}"
    a, b = sc.asking
    ask = sc.low[a:b]
    which = [i for i, q in enumerate(elems, 1) if q.text.replace(" ", "").lower() in ask.replace(" ", "")]
    E = {nm: X(nm) for nm in sym}
    V, I, Q, U, P, Eq_ = X("V"), X("I"), X("Q"), X("U"), X("P"), X(f"{comp}eq")
    eqs = []
    if comp == "R":
        sym.update(Req=Sym("resistance", "equivalent resistance"), V=Sym("voltage", "voltage across the network"),
                   I=Sym("current", "total current"), P=Sym("power", "total power"))
        if series:
            eqs.append(("resistances in series add", sp.Eq(Eq_, sum(E[f"R{i}"] for i in range(1, n + 1)))))
        else:
            eqs.append(("reciprocals add in parallel", sp.Eq(1 / Eq_, sum(1 / E[f"R{i}"] for i in range(1, n + 1)))))
        eqs += [("Ohm's law for the network", sp.Eq(V, I * Eq_)), ("power delivered", sp.Eq(P, V * I))]
        for i in range(1, n + 1):
            sym[f"I{i}"] = Sym("current", f"current through the {elems[i - 1].text} resistor")
            sym[f"V{i}"] = Sym("voltage", f"voltage across the {elems[i - 1].text} resistor")
            sym[f"P{i}"] = Sym("power", f"power in the {elems[i - 1].text} resistor")
            Ii, Vi, Pi = X(f"I{i}"), X(f"V{i}"), X(f"P{i}")
            eqs += [(f"resistor {i}: Ohm's law", sp.Eq(Vi, Ii * E[f"R{i}"])), (f"resistor {i}: power", sp.Eq(Pi, Vi * Ii)),
                    (f"resistor {i}: " + ("same current" if series else "same voltage"), sp.Eq(Ii, I) if series else sp.Eq(Vi, V))]
        if re.search(r"\b(equivalent|total|combined|net|effective) resistance\b", ask):
            target, phrase = "Req", "equivalent resistance"
        elif re.search(r"\bpower\b", ask):
            target, phrase = (f"P{which[0]}" if len(which) == 1 else "P"), "power"
        elif re.search(r"\bcurrent\b", ask):
            target, phrase = (f"I{which[0]}" if len(which) == 1 else "I"), "current"
        elif re.search(r"\b(voltage|potential difference)\b", ask):
            target, phrase = (f"V{which[0]}" if len(which) == 1 else "V"), "voltage"
        else:
            return None
        if len(which) != 1 and target in ("I", "V", "P") and re.search(r"\b(each|through the|across the|in the)\b", ask) and not re.search(r"\b(total|battery|source|supplied|drawn)\b", ask):
            return Refusal("needs_clarification", "Say which resistor (by its value) the question is about.", "unknown_target", "network")
        title = "Resistors in " + ("series" if series else "parallel")
    else:
        sym.update(Ceq=Sym("capacitance", "equivalent capacitance"), V=Sym("voltage", "voltage across the network"),
                   Q=Sym("charge", "total charge stored"), U=Sym("energy", "total energy stored"))
        if series:
            eqs.append(("reciprocals add in series", sp.Eq(1 / Eq_, sum(1 / E[f"C{i}"] for i in range(1, n + 1)))))
        else:
            eqs.append(("capacitances in parallel add", sp.Eq(Eq_, sum(E[f"C{i}"] for i in range(1, n + 1)))))
        eqs += [("charge on the network", sp.Eq(Q, Eq_ * V)), ("energy stored", sp.Eq(U, Eq_ * V**2 / 2))]
        for i in range(1, n + 1):
            sym[f"Q{i}"] = Sym("charge", f"charge on the {elems[i - 1].text} capacitor")
            sym[f"V{i}"] = Sym("voltage", f"voltage across the {elems[i - 1].text} capacitor")
            Qi, Vi = X(f"Q{i}"), X(f"V{i}")
            eqs += [(f"capacitor {i}: charge", sp.Eq(Qi, E[f"C{i}"] * Vi)),
                    (f"capacitor {i}: " + ("same charge" if series else "same voltage"), sp.Eq(Qi, Q) if series else sp.Eq(Vi, V))]
        if re.search(r"\b(equivalent|total|combined|net|effective) capacitance\b", ask):
            target, phrase = "Ceq", "equivalent capacitance"
        elif re.search(r"\benergy\b", ask):
            target, phrase = "U", "energy stored"
        elif re.search(r"\bcharge\b", ask):
            target, phrase = (f"Q{which[0]}" if len(which) == 1 else "Q"), "charge"
        elif re.search(r"\b(voltage|potential difference)\b", ask):
            target, phrase = (f"V{which[0]}" if len(which) == 1 else "V"), "voltage"
        else:
            return None
        title = "Capacitors in " + ("series" if series else "parallel")
    return System("network", title, sym, eqs, known, sources, target, phrase, [], ["ideal components and wires"], False)


# --- gases between two states ------------------------------------------------------------------------------------
def gas_states(sc: Scenario, pack):
    if not re.search(r"\b(gas|air|tire|tyre|balloon|cylinder|container|helium|nitrogen|oxygen)\b", sc.low):
        return None
    if sc.of_kind("amount") or len(sc.bodies) > 0:
        return None
    p, v, t = sc.of_kind("pressure"), sc.of_kind("volume"), sc.of_kind("temperature")
    if len(p) + len(v) + len(t) < 3 or max(len(p), len(v), len(t)) < 2 and not re.search(r"\b(then|to|later|new|final|when|after|until)\b", sc.low):
        return None
    if max(len(p), len(v), len(t)) > 2:
        return None
    a, b = sc.asking
    ask = sc.low[a:b]
    names = {"pressure": "P", "volume": "V", "temperature": "T"}
    if re.search(r"\b(work|heat|energy|internal energy|entropy|how much)\b", ask):
        return None                                   # a process quantity is asked, not a state of the gas
    asked = next((k for k in ("pressure", "volume", "temperature")
                  if re.search(r"(?<!constant )(?<!same )\b" + k + r"\b", ask)), None)
    if asked is None:
        return None
    gauge = re.search(r"\bgauge\b", sc.low) is not None
    known, sources, assumptions = {}, {}, ["a fixed amount of ideal gas", "absolute temperatures"]
    sym = {}
    for kind, qs in (("pressure", p), ("volume", v), ("temperature", t)):
        n = names[kind]
        sym[f"{n}1"] = Sym(kind, f"{kind} in the first state")
        sym[f"{n}2"] = Sym(kind, f"{kind} in the second state")
        for i, q in enumerate(qs[:2], 1):
            val = q.value + (101325.0 if gauge and kind == "pressure" else 0.0)
            known[f"{n}{i}"], sources[f"{n}{i}"] = val, f"stated: {q.text}" + (" (gauge, plus 1 atm)" if gauge and kind == "pressure" else "")
        if len(qs) == 1 and kind != asked:
            if re.search(r"\b(constant|same|unchanged|fixed|rigid|sealed)\b[^.]*\b" + kind, sc.low) or re.search(r"\bconstant " + kind, sc.low):
                known[f"{n}2"], sources[f"{n}2"] = known[f"{n}1"], f"stated: constant {kind}"
            else:
                return Refusal("needs_clarification", f"Only one {kind} is stated; say what it is in the other state "
                               f"(or that it stays constant).", "underdetermined", "gas_two_states", would_need=[f"{kind} in the second state"])
        if not qs and kind != asked:
            known[f"{n}1"] = known[f"{n}2"] = 1.0
            sources[f"{n}1"] = sources[f"{n}2"] = f"implied: the {kind} is not mentioned and taken as constant"
            assumptions.append(f"the {kind} stays constant (not mentioned)")
    if gauge:
        assumptions.append("gauge pressures: absolute = gauge + 1 atm (101325 Pa)")
    n = names[asked]
    target = f"{n}2" if f"{n}1" in known else f"{n}1"
    P1, P2, V1, V2, T1, T2 = (X(s) for s in ("P1", "P2", "V1", "V2", "T1", "T2"))
    eqs = [("the combined gas law", sp.Eq(P1 * V1 / T1, P2 * V2 / T2))]
    sysm = System("gas_two_states", "A gas between two states", sym, eqs, known, sources, target, f"{asked}",
                  [("absolute temperatures and pressures are positive", lambda n_: all(n_[k] > 0 for k in ("P1", "P2", "V1", "V2", "T1", "T2") if k in n_))],
                  assumptions, False)
    if gauge and asked == "pressure":
        sym["Pg"] = Sym("pressure", "gauge pressure in the asked state")
        Pg = X("Pg")
        sysm.equations.append(("gauge = absolute - 1 atm", sp.Eq(Pg, X(target) - 101325)))
        sysm.target, sysm.phrase = "Pg", "gauge pressure"
    return sysm


# --- waves, decay, RC ----------------------------------------------------------------------------------------------
def doppler(sc: Scenario, pack):
    if not (re.search(r"\b(doppler|siren|horn|whistle|screech|emit\w*|sound|frequency)\b", sc.low)
            and re.search(r"\b(toward|towards|approach\w*|away|reced\w*|at it|at you|at him|at her|at them)\b", sc.low)):
        return None
    freqs = sc.of_kind("frequency")
    if len(freqs) != 1 or not re.search(r"\bfrequency\b", sc.low[sc.asking[0]:sc.asking[1]]):
        return None
    known, sources, assumptions = {"f": freqs[0].value}, {"f": f"stated: {freqs[0].text}"}, ["sound in still air"]
    sound = [q for q in sc.of_kind("speed") if re.search(r"speed of sound|sound (?:travels|speed)", sc.low[max(0, q.start - 40):q.end + 10])]
    movers = [q for q in sc.of_kind("speed") if q not in sound]
    if len(movers) != 1:
        return Refusal("needs_clarification", "The Doppler model here needs exactly one moving source or observer.",
                       "unsupported_structure", "doppler")
    if sound:
        known["c"], sources["c"] = sound[0].value, f"stated: {sound[0].text}"
    else:
        known["c"], sources["c"] = 343.0, "default: speed of sound in air at 20 degC, 343 m/s"
        assumptions.append("speed of sound 343 m/s (air at 20 degC)")
    q = movers[0]
    sa, sb = sc.sentence_of(q.start)
    source_moves = re.search(r"\b(emit\w*|siren|horn|whistle|screech\w*|sounding|honk\w*|source|plays?|sings?)\b", sc.low[sa:sb]) is not None
    approach = re.search(r"\b(toward|towards|approach\w*|at it|at you|closer)\b", sc.low[sa:sb])
    recede = re.search(r"\b(away|reced\w*|leaving)\b", sc.low[sa:sb])
    if bool(approach) == bool(recede):
        return Refusal("needs_clarification", "Say whether the source and observer approach or move apart.", "ambiguous", "doppler")
    known["u"], sources["u"] = q.value, f"stated: {q.text}"
    f, c, u, fo = X("f"), X("c"), X("u"), X("fo")
    sym = {"f": Sym("frequency", "emitted frequency"), "c": Sym("speed", "speed of sound"),
           "u": Sym("speed", ("source" if source_moves else "observer") + " speed"), "fo": Sym("frequency", "observed frequency")}
    if source_moves:
        eq = sp.Eq(fo, f * c / (c - u)) if approach else sp.Eq(fo, f * c / (c + u))
        label = "moving source, " + ("approaching" if approach else "receding")
    else:
        eq = sp.Eq(fo, f * (c + u) / c) if approach else sp.Eq(fo, f * (c - u) / c)
        label = "moving observer, " + ("approaching" if approach else "receding")
    return System("doppler", "Doppler effect for sound", sym, [(label, eq)], known, sources, "fo", "observed frequency",
                  [("subsonic motion", lambda n: n["u"] < n["c"])], assumptions, False)


def half_life(sc: Scenario, pack):
    if not re.search(r"\bhalf[- ]li(fe|ves)\b", sc.low):
        return None
    times = sc.of_kind("time")
    hl = [q for q in times if re.search(r"half[- ]life", sc.low[max(0, q.start - 40):q.end + 25])]
    other = [q for q in times if q not in hl]
    a, b = sc.asking
    ask = sc.low[a:b]
    known, sources = {}, {}
    sym = {"T": Sym("time", "half-life"), "t": Sym("time", "elapsed time"), "f": Sym("magnification", "fraction remaining"),
           "N0": Sym("mass", "initial amount"), "N": Sym("mass", "amount remaining")}
    if len(hl) == 1:
        known["T"], sources["T"] = hl[0].value, f"stated: {hl[0].text}"
    if len(other) > 1:
        return Refusal("needs_clarification", "More than one elapsed time is stated.", "ambiguous_quantity", "half_life")
    for q in other:
        known["t"], sources["t"] = q.value, f"stated: {q.text}"
    masses = sc.of_kind("mass")
    if len(masses) >= 1:
        known["N0"], sources["N0"] = masses[0].value, f"stated: {masses[0].text}"
    if len(masses) == 2:
        known["N"], sources["N"] = masses[1].value, f"stated: {masses[1].text}"
    frac = percent_of(sc, r"(?:remains|left|remaining|of the (?:original|initial))")
    if frac is not None:
        known["f"], sources["f"] = frac, "stated as a percentage"
    T, t, f, N0, N = (X(n) for n in ("T", "t", "f", "N0", "N"))
    eqs = [("exponential decay by half-lives", sp.Eq(f, sp.Rational(1, 2) ** (t / T))), ("amount remaining", sp.Eq(N, N0 * f))]
    if re.search(r"\b(fraction|percent|percentage)\b", ask):
        target, phrase = "f", "fraction remaining"
    elif re.search(r"\bhalf[- ]life\b", ask) and "T" not in known:
        target, phrase = "T", "half-life"
    elif re.search(r"\b(how long|time|how many (?:years|days|hours))\b", ask):
        target, phrase = "t", "elapsed time"
    elif re.search(r"\b(mass|how much|amount)\b", ask):
        target, phrase = ("N" if "N0" in known else "N0"), "amount remaining" if "N0" in known else "initial amount"
    else:
        return None
    return System("half_life", "Radioactive decay", sym, eqs, known, sources, target, phrase,
                  [("times are positive", lambda n: n["T"] > 0)], ["decay with a constant half-life"], False)


def rc_circuit(sc: Scenario, pack):
    if not (sc.of_kind("capacitance") and sc.of_kind("resistance")) or len(sc.of_kind("resistance")) != 1 or len(sc.of_kind("capacitance")) != 1:
        return None
    if not re.search(r"\b(charg\w*|discharg\w*|time constant|rc)\b", sc.low):
        return None
    a, b = sc.asking
    ask = sc.low[a:b]
    R, C = sc.of_kind("resistance")[0], sc.of_kind("capacitance")[0]
    known = {"R": R.value, "C": C.value}
    sources = {"R": f"stated: {R.text}", "C": f"stated: {C.text}"}
    sym = {"R": Sym("resistance", "resistance"), "C": Sym("capacitance", "capacitance"), "tau": Sym("time", "time constant RC"),
           "t": Sym("time", "time"), "f": Sym("magnification", "fraction of the final (or initial) voltage")}
    Rs, Cs, tau, t, f = (X(n) for n in ("R", "C", "tau", "t", "f"))
    eqs = [("time constant", sp.Eq(tau, Rs * Cs))]
    if re.search(r"\btime constant\b", ask):
        return System("rc_circuit", "RC circuit", sym, eqs, known, sources, "tau", "time constant", [], ["ideal components"], False)
    dis = re.search(r"\bdischarg", sc.low) is not None
    frac = percent_of(sc, r"(?:its |the )?(?:final|maximum|full|initial|original)")
    if frac is not None:
        known["f"], sources["f"] = frac, "stated as a percentage"
    for q in sc.of_kind("time"):
        known["t"], sources["t"] = q.value, f"stated: {q.text}"
    eqs.append(("discharging: fraction left" if dis else "charging: fraction of the final voltage",
                sp.Eq(f, sp.exp(-t / tau)) if dis else sp.Eq(f, 1 - sp.exp(-t / tau))))
    if re.search(r"\b(how long|time)\b", ask):
        target, phrase = "t", "time"
    elif re.search(r"\b(fraction|percent|percentage)\b", ask):
        target, phrase = "f", "fraction"
    else:
        return None
    return System("rc_circuit", "RC circuit", sym, eqs, known, sources, target, phrase,
                  [("time is positive", lambda n: n["t"] >= 0), ("fraction between 0 and 1", lambda n: 0 < n["f"] < 1)],
                  ["ideal components", "starting from an uncharged (or fully charged) capacitor"], False)


# --- motion in stages ------------------------------------------------------------------------------------------
_STAGE = re.compile(r"\b(?:and )?then\b|\bafter which\b|\bafter that\b|\bfollowed by\b", re.I)


def stages(sc: Scenario, pack):
    cuts = [m.start() for m in _STAGE.finditer(sc.text) if m.start() < sc.asking[0]]
    if not cuts or len(sc.bodies) > 1 or not re.search(r"\b(accelerat\w*|decelerat\w*|brakes?|slows?|constant (?:speed|velocity)|cruis\w*|coasts?|stops?)\b", sc.low):
        return None
    bounds = [0] + cuts + [sc.asking[0]]
    n = len(bounds) - 1
    if n > 4:
        return None
    known, sources, sym, eqs, cons = {}, {}, {}, [], []
    assumptions = ["motion along a straight line", "constant acceleration within each stage"]
    for k in range(1, n + 1):
        s0, s1 = bounds[k - 1], bounds[k]
        seg = sc.low[s0:s1]
        for nm, kind, mean in (("u", "speed", "speed at the start"), ("v", "speed", "speed at the end"), ("a", "acceleration", "acceleration"),
                               ("t", "time", "duration"), ("d", "length", "distance")):
            sym[f"{nm}{k}"] = Sym(kind, f"{mean} of stage {k}")
        u, v, a_, t, d = (X(f"{nm}{k}") for nm in ("u", "v", "a", "t", "d"))
        eqs += [(f"stage {k}: velocity", sp.Eq(v, u + a_ * t)), (f"stage {k}: distance", sp.Eq(d, (u + v) * t / 2))]
        cons += [(f"stage {k} lasts a non-negative time", lambda nn, k=k: nn[f"t{k}"] >= 0),
                 (f"stage {k} covers a non-negative distance", lambda nn, k=k: nn[f"d{k}"] >= 0)]
        if k > 1:
            eqs.append((f"stage {k} starts where stage {k - 1} ends", sp.Eq(u, X(f"v{k - 1}"))))
        if re.search(r"\b(constant (?:speed|velocity)|steady speed|cruis\w*|coasts?)\b", seg):
            known[f"a{k}"], sources[f"a{k}"] = 0.0, "implied: constant speed"
        if re.search(r"\b(to a (?:stop|halt)|comes? to (?:a )?(?:stop|rest)|stops|until it stops|to rest)\b", seg):
            known[f"v{k}"], sources[f"v{k}"] = 0.0, "implied: it stops"
        if k == 1 and re.search(r"\b(from rest|at rest|starts? from rest)\b", seg):
            known["u1"], sources["u1"] = 0.0, "implied: starts from rest"
        decel = re.search(r"\b(decelerat\w*|brakes?|braking|slows?|slowing)\b", seg)
        for q in sc.quantities:
            if not (s0 <= q.start < s1):
                continue
            pre = sc.low[max(s0, q.start - 25):q.start]
            if q.kind == "acceleration":
                known[f"a{k}"], sources[f"a{k}"] = (-abs(q.value) if decel else q.value), f"stated: {q.text}" + (" (slowing: negative)" if decel else "")
            elif q.kind == "time":
                known[f"t{k}"], sources[f"t{k}"] = q.value, f"stated: {q.text}"
            elif q.kind == "length":
                known[f"d{k}"], sources[f"d{k}"] = q.value, f"stated: {q.text}"
            elif q.kind == "speed":
                if known.get(f"a{k}") == 0.0:
                    known[f"u{k}"], sources[f"u{k}"] = q.value, f"stated: {q.text}"
                elif re.search(r"\b(to|reaches|reaching|until|up to|attains|of)\s*$", pre) and not re.search(r"\bfrom\s*$", pre):
                    known[f"v{k}"], sources[f"v{k}"] = q.value, f"stated: {q.text}"
                elif re.search(r"\b(from|at|moving at|traveling at|travelling at|initially)\s*$", pre):
                    known[f"u{k}"], sources[f"u{k}"] = q.value, f"stated: {q.text}"
                else:
                    return Refusal("needs_clarification", f"I could not tell whether {q.text} is the speed at the start or "
                                   f"the end of stage {k}.", "ambiguous_quantity", "stages")
            elif q.kind != "mass":
                return None
    a, b = sc.asking
    ask = sc.low[a:b]
    sym["D"], sym["T"] = Sym("length", "total distance"), Sym("time", "total time")
    eqs += [("total distance", sp.Eq(X("D"), sum(X(f"d{k}") for k in range(1, n + 1)))),
            ("total time", sp.Eq(X("T"), sum(X(f"t{k}") for k in range(1, n + 1))))]
    if re.search(r"\b(total|altogether|in all|whole trip|entire)\b", ask) and re.search(r"\b(distance|how far)\b", ask):
        target, phrase = "D", "total distance"
    elif re.search(r"\b(total|altogether|in all|whole trip|entire)\b", ask) and re.search(r"\b(time|how long)\b", ask):
        target, phrase = "T", "total time"
    elif re.search(r"\b(maximum speed|top speed|speed .* (?:end of|after) the first)\b", ask):
        target, phrase = "v1", "speed at the end of the first stage"
    else:
        return Refusal("needs_clarification", "For motion in stages, ask for the total distance, the total time or the top "
                       "speed (or say which stage).", "unknown_target", "stages")
    return System("stages", "Motion in stages", sym, eqs, known, sources, target, phrase, cons, assumptions, False)


# --- rolling ------------------------------------------------------------------------------------------------------
_SHAPE = {"solid sphere": sp.Rational(2, 5), "hollow sphere": sp.Rational(2, 3), "spherical shell": sp.Rational(2, 3),
          "solid cylinder": sp.Rational(1, 2), "disk": sp.Rational(1, 2), "disc": sp.Rational(1, 2), "hoop": sp.Integer(1),
          "ring": sp.Integer(1), "thin-walled cylinder": sp.Integer(1), "hollow cylinder": sp.Integer(1),
          "ball": sp.Rational(2, 5), "marble": sp.Rational(2, 5), "cylinder": sp.Rational(1, 2)}


def rolling(sc: Scenario, pack):
    if not re.search(r"\broll\w*\b", sc.low) or re.search(r"\bslid\w*\b", sc.low):
        return None
    shape = next((s for s in sorted(_SHAPE, key=len, reverse=True) if re.search(r"\b" + re.escape(s) + r"\b", sc.low)), None)
    if shape is None:
        return Refusal("needs_clarification", "Rolling speed depends on the shape: say whether it is a solid sphere, a "
                       "hollow sphere, a solid cylinder or a hoop.", "underdetermined", "rolling", would_need=["shape of the rolling body"])
    a, b = sc.asking
    ask = sc.low[a:b]
    known, sources, assumptions = {"k": float(_SHAPE[shape])}, {"k": f"implied: {shape}, I = {_SHAPE[shape]} m r^2"}, \
        ["rolling without slipping", f"{shape}: I = {_SHAPE[shape]} m r^2", "starts from rest"]
    _g(sc, sources, assumptions, known)
    heights = [q for q in sc.of_kind("length") if re.search(r"\b(height|high|vertical|drop|tall)\b", sc.low[max(0, q.start - 40):q.end + 25])]
    if len(heights) != 1:
        return None
    known["h"], sources["h"] = heights[0].value, f"stated: {heights[0].text}"
    if not re.search(r"\b(speed|velocity|how fast)\b", ask):
        return None
    v, h, g, k = X("v"), X("h"), X("g"), X("k")
    sym = {"v": Sym("speed", "speed at the bottom"), "h": Sym("length", "vertical drop"), "g": Sym("acceleration", "gravity"),
           "k": Sym("magnification", "shape factor I/(m r^2)")}
    eq = sp.Eq(g * h, v**2 * (1 + k) / 2)
    return System("rolling", "Rolling down from a height", sym, [("energy: drop = translation + rotation", eq)], known, sources,
                  "v", "speed at the bottom", [("speed is positive", lambda n: n["v"] > 0)], assumptions, False)


# the certified relations each model family builds on (a family's equations are these laws applied to several bodies,
# states or stages); used to judge a teacher's model-selection task
FAMILY_USES = {
    "collision_1d": {"momentum", "kinetic_energy", "impulse"}, "recoil": {"momentum"},
    "projectile": {"velocity_time", "displacement_time", "uniform_motion", "velocity_displacement"},
    "atwood": {"newton_second", "weight", "tension_hanging_at_rest"},
    "pulley_table": {"newton_second", "weight", "kinetic_friction", "normal_on_level", "tension_hanging_at_rest"},
    "elevator": {"newton_second", "weight", "normal_on_level"},
    "banked_curve": {"centripetal_force", "centripetal_acceleration", "weight"},
    "flat_curve": {"centripetal_force", "centripetal_acceleration", "weight", "kinetic_friction"},
    "calorimetry": {"heat"}, "rc_circuit": {"capacitance_definition", "ohm"},
    "network": {"ohm", "electric_power", "ohm_power_current", "ohm_power_voltage", "capacitance_definition", "capacitor_energy"},
    "gas_two_states": {"ideal_gas_moles"}, "doppler": {"wave_speed", "period_frequency"}, "half_life": set(),
    "stages": {"velocity_time", "displacement_time", "velocity_displacement", "uniform_motion", "average_velocity_displacement"},
    "rolling": {"rotational_kinetic_energy", "kinetic_energy", "gravitational_pe"},
}

# the reader's choice among kinds of the same dimension, preferred first
KIND_PREFERENCE = ["mass", "speed", "length", "time", "angle", "acceleration", "force", "energy", "temperature", "specific_heat",
                   "resistance", "voltage", "current", "capacitance", "pressure", "volume", "frequency", "power", "charge",
                   "density", "spring_constant", "angular_frequency", "friction_coefficient", "inductance"]
FAMILY_TITLES = {"collision_1d": "Collisions along a line", "recoil": "Recoil from rest", "projectile": "Projectile motion",
                 "atwood": "Two masses over a pulley", "pulley_table": "Block on a surface pulled over a pulley",
                 "elevator": "Apparent weight in an elevator", "banked_curve": "Ideal banking of a curve",
                 "flat_curve": "Maximum speed on a flat curve", "calorimetry": "Mixing to thermal equilibrium",
                 "network": "Series and parallel resistor and capacitor networks", "rc_circuit": "RC circuits",
                 "gas_two_states": "A gas between two states", "doppler": "Doppler effect for sound",
                 "half_life": "Radioactive decay", "stages": "Motion in stages", "rolling": "Rolling from a height"}

FAMILIES = [recoil, collision, projectile, pulley, elevator, curve, calorimetry, network, rc_circuit, gas_states, doppler,
            half_life, stages, rolling]


# documented examples per family (the capability guide prints them; tools/contract_acceptance.py runs them through
# the installed package): a question with its hand-computed value, or a question with the outcome it must produce
_G = 9.80665
FAMILY_EXAMPLES = {
    "collision_1d": [
        {"q": "A 1000 kg car moving at 20 m/s hits a stationary 500 kg car and they stick together. What is their final velocity?", "value": 40 / 3, "unit": "m/s"},
        {"q": "A 2 kg ball moving at 3 m/s collides elastically with a 1 kg ball at rest. What is the velocity of the 1 kg ball after the collision?", "value": 4.0, "unit": "m/s"},
        {"q": "A 0.5 kg ball of clay moving at 10 m/s hits a 2.0 kg block at rest and sticks to it. How much kinetic energy is lost?", "value": 20.0, "unit": "J"},
        {"q": "A 2 kg ball moving at 3 m/s hits a 1 kg ball at rest. What is the speed of the 1 kg ball afterwards?", "outcome": "NEEDS_INPUT"}],
    "recoil": [
        {"q": "A 4.0 kg rifle initially at rest fires a 0.010 kg bullet at 600 m/s. What is the recoil speed of the rifle?", "value": 1.5, "unit": "m/s"}],
    "projectile": [
        {"q": "A ball is kicked at 20 m/s at an angle of 30 degrees above the horizontal. How far does it travel?", "value": 400 * 0.8660254037844386 / _G, "unit": "m"},
        {"q": "A stone is thrown horizontally at 15 m/s from a cliff 45 m high. How long is it in the air?", "value": (90 / _G) ** 0.5, "unit": "s"}],
    "atwood": [
        {"q": "Two masses of 3 kg and 5 kg hang from either side of a pulley. What is the acceleration?", "value": 2 / 8 * _G, "unit": "m/s^2"},
        {"q": "A 4 kg block and a 2 kg block are connected by a string over a pulley. What is the tension?", "outcome": "NEEDS_INPUT"}],
    "pulley_table": [
        {"q": "A 4 kg block on a frictionless table is connected over a pulley to a hanging 1 kg mass. What is the tension in the string?", "value": 4 * _G / 5, "unit": "N"}],
    "elevator": [
        {"q": "A 60 kg person stands on a scale in an elevator accelerating upward at 2 m/s^2. What does the scale read?", "value": 60 * (_G + 2), "unit": "N"},
        {"q": "A 70 kg person stands on a scale in an elevator that accelerates at 2 m/s^2. What does the scale read?", "outcome": "AMBIGUOUS"}],
    "banked_curve": [
        {"q": "A curve of radius 80 m is banked for a speed of 20 m/s. What is the banking angle?", "value": __import__("math").atan(400 / (80 * _G)), "unit": "rad"}],
    "flat_curve": [
        {"q": "A car rounds a flat curve of radius 50 m. The coefficient of static friction is 0.60. What is the maximum speed on the flat curve?", "value": (0.6 * _G * 50) ** 0.5, "unit": "m/s"}],
    "calorimetry": [
        {"q": "A 0.2 kg piece of aluminum at 90 °C is dropped into 0.5 kg of water at 20 °C. What is the final temperature?", "value": (0.2 * 900 * 363.15 + 0.5 * 4186 * 293.15) / (0.2 * 900 + 0.5 * 4186), "unit": "K"},
        {"q": "A 0.05 kg ice cube at -10 °C is dropped into 0.3 kg of water at 25 °C. What is the final temperature?", "outcome": "OUT_OF_SCOPE"}],
    "network": [
        {"q": "Three resistors of 2 ohm, 3 ohm and 6 ohm are connected in parallel to a 12 V battery. What is the total current?", "value": 12.0, "unit": "A"},
        {"q": "Two capacitors of 2 uF and 3 uF are connected in series to a 10 V battery. What is the charge on the 2 uF capacitor?", "value": 1.2e-5, "unit": "C"}],
    "rc_circuit": [
        {"q": "A 100-pF capacitor is charged through a 75.0-MΩ resistor. How long does it take to reach 90.0% of its final voltage?", "value": 75e6 * 100e-12 * 2.302585092994046, "unit": "s"}],
    "gas_two_states": [
        {"q": "A gas at 2.0 atm occupies 4.0 L at 300 K. It is compressed to 2.0 L at constant temperature. What is the new pressure?", "value": 4 * 101325, "unit": "Pa"}],
    "doppler": [
        {"q": "A train whistle of frequency 500 Hz approaches a stationary listener at 30 m/s. The speed of sound is 340 m/s. What frequency does the listener hear?", "value": 500 * 340 / 310, "unit": "Hz"}],
    "half_life": [
        {"q": "A sample of 80 g of a radioactive isotope has a half-life of 5 days. What mass remains after 15 days?", "value": 0.010, "unit": "kg"}],
    "stages": [
        {"q": "A car starts from rest and accelerates at 2 m/s^2 for 10 s, then moves at constant speed for 20 s. What is the total distance traveled?", "value": 500.0, "unit": "m"}],
    "rolling": [
        {"q": "A solid sphere rolls without slipping down a ramp from a height of 2 m. What is its speed at the bottom?", "value": (10 / 7 * _G * 2) ** 0.5, "unit": "m/s"}],
}
