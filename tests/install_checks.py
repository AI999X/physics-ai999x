"""Physics checks run by tools/clean_install.py inside a fresh environment (the generic checks run as well)."""
import re

SAMPLE = ("A 3 kg object moves at 4 m/s. What is its kinetic energy?", 24.0)
LATENCY = ["A 3 kg object moves at 4 m/s. What is its kinetic energy?", "A heater draws 4 A from a 230 V supply. What power does it use?",
           "A ball is thrown straight up at 20 m/s. How high does it rise?", "A car speeds up from 10 m/s to 20 m/s in 5 s. What is its acceleration?",
           "What is the weight force on a 75 kg astronaut standing on Earth?", "A ball is thrown at 20 m/s. How high does it rise?"]


def _close(a, v):
    return a.solved and abs(a.value - v) <= 1e-4 * max(1.0, abs(v))


def checks(P) -> dict:
    out = {
        "solve_structured": abs(P.solve("kinetic energy", {"mass": "3 kg", "speed": "4 m/s"}).value - 24) < 1e-9,
        "solve_multistep": abs(P.solve("power", {"voltage": "12 V", "resistance": "6 ohm"}).value - 24) < 1e-9,
        "solve_conditions": abs(P.solve("acceleration", {"angle of the incline": "30 deg"}, ["inclined", "frictionless"]).value - 4.903325) < 1e-9,
        "refuses_missing": not P.ask("A crate has a mass of 12 kg. What is its kinetic energy?").solved,
        "default_stated": any("standard gravity" in x for x in P.ask("A wheelbarrow has a mass of 20 kg. What is its weight force?").assumptions),
        "model_family_collision": _close(P.ask("A 1000 kg car moving at 20 m/s hits a stationary 500 kg car and they stick together. What is their final velocity?"), 13.333333),
        "model_family_projectile": _close(P.ask("A ball is kicked at 20 m/s at an angle of 30 degrees above the horizontal. How far does it travel?"), 35.324006),
        "model_family_refuses_underdetermined": not P.ask("A 4 kg block and a 2 kg block are connected by a string over a pulley. What is the tension?").solved,
        "fixed_errors_now_refused": all(not P.ask(q).solved for q in [
            "A 12,000 kg wagon rolls at 4.0 m/s. How long does a 1200 N force take to bring the wagon to rest?",
            "What is the peak power drawn by a 230-V AC kettle that takes 8.0 A?"]),
        "native_topics": len(P.topics()) == 34 and not any(re.search(r"[0-9]+[.][0-9]+", x["name"]) for x in P.topics()),
        "guided_clarification": any("speed" in q for q in P.suggest("A 2 kg ball. What is its kinetic energy?")["ask_back"]),
        "templates_offered": len(P.templates()) >= 100,
    }
    from physics_ai999x import knowledge
    st = knowledge.stats()
    out["knowledge_db"] = st["relations"] == len(P.pack().relations) and st["records"] > 500
    try:
        P.plot(P.ask(SAMPLE[0]))
        out["plot_extra_reported"] = True
    except ImportError as exc:
        out["plot_extra_reported"] = "physics-ai999x[plot]" in str(exc)
    return out
