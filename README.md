# physics-ai999x — offline, verified physics solver with step-by-step answers

[![tests](https://github.com/AI999X/physics-ai999x/actions/workflows/ci.yml/badge.svg)](https://github.com/AI999X/physics-ai999x/actions/workflows/ci.yml) [![PyPI](https://img.shields.io/pypi/v/physics-ai999x)](https://pypi.org/project/physics-ai999x/) [![Hugging Face](https://img.shields.io/badge/%F0%9F%A4%97-Hugging%20Face-yellow)](https://huggingface.co/AI999X/physics-ai999x)

**[Install](https://pypi.org/project/physics-ai999x/)** · **[Capability guide](https://huggingface.co/AI999X/physics-ai999x/tree/main/docs)** · **[Evaluation](https://huggingface.co/AI999X/physics-ai999x/tree/main/evaluation)** · **[AI999X on Hugging Face](https://huggingface.co/AI999X)** · **[Website](https://ai999x.com)** · **[Support: Buy Me a Coffee](https://buymeacoffee.com/ibnuljaiffarabi)**

License: Apache-2.0 · Author: Ibnul Jaif Farabi (creator and engineer) · Organization: AI999X · Version 2.0.0

physics-ai999x is an offline, deterministic Python solver that answers physics questions with verified results from 148 certified capabilities, gives 859 documented answers identically on Windows and Linux, and refuses rather than guesses when an answer cannot be verified.

**physics-ai999x** is a compact, deterministic physics engine for Python. It reads a question in plain English (or a typed call), picks a certified physics capability, computes the answer exactly, checks it, and returns the result with its steps, units, LaTeX and assumptions — or an honest refusal that says what is missing. It runs fully offline on any CPU, needs no GPU, no API key and no internet, and is built to give **zero wrong answers**: when it is not sure, it refuses instead of guessing.

[![Buy me a coffee](https://img.shields.io/badge/Buy%20me%20a%20coffee-support%20development-FFDD00?logo=buymeacoffee&logoColor=black)](https://buymeacoffee.com/ibnuljaiffarabi) ![License](https://img.shields.io/badge/license-Apache--2.0-blue) ![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue) ![Offline](https://img.shields.io/badge/runs-offline%20on%20CPU-green)

## Highlights

- **Verified, not generated.** Every answer is computed by a certified physics capability and checked (substituted back, dimension-checked or compared with an independent computation) before it is returned.
- **Zero wrong answers by design.** Seven explicit outcomes — SOLVED, NEEDS_INPUT, AMBIGUOUS, INVALID_INPUT, OUT_OF_SCOPE, UNRECOGNIZED_FORMAT, INTERNAL_ERROR — never a silent guess. Measured: 0 wrong answers on 274 benchmark questions and on 1,567 verified natural-language questions.
- **Plain-English questions and a guaranteed typed interface.** `ask()` reads documented question forms; `solve(capability_id, **inputs)` always solves a supported task with valid inputs.
- **Explains itself.** Steps, formulas in LaTeX, units, assumptions and the model used, ready for notebooks, tutoring apps and homework checkers.
- **Small and portable.** Pure Python (sympy, mpmath); identical answers on Windows and Linux (Python 3.10, 3.11, 3.12, 3.13, 3.14).
- **Coverage:** kinematics, forces and Newton's laws, work and energy, momentum and collisions, circular motion and gravitation, rotation, oscillations and waves, fluids, heat and thermodynamics, electricity and circuits, magnetism and induction, optics and modern physics.

## Model overview

| Property | Value |
|---|---|
| Package | `physics-ai999x` 2.0.0 (import `physics_ai999x`) |
| Type | Deterministic neuro-symbolic physics engine (rule-based reading + certified symbolic capabilities) |
| Capabilities | 23 certified derivations, 16 certified model_familys, 2 certified procedures, 107 certified relations |
| Knowledge pack | version 0.6.0 |
| Golden answers | 859 documented answers, identical on every tested platform |
| Platforms tested | Windows (Python 3.13), Linux x86-64 (Python 3.10, 3.11, 3.12, 3.13, 3.14) |
| Runtime | CPU only, offline; no GPU, no network, no API key |
| License | Apache-2.0 |
| Creator / engineer | Ibnul Jaif Farabi |
| Organization | AI999X |

## Quickstart

```bash
pip install physics-ai999x
```

```python
import physics_ai999x as physics

physics.ask("A 1000 kg car moving at 20 m/s hits a stationary 500 kg car and they stick together. What is their final velocity?").show()
# -> SOLVED — 13.3333 m/s  (collision_1d)
physics.ask("How much heat boils away 0.5 kg of water? Its latent heat of vaporization is 2260000 J/kg.").show()
# -> SOLVED — 1.13e+06 J  (latent_heat_vaporization)
physics.ask("A hockey puck slides across ice at 10 m/s and slows down at a constant rate of 0.5 m/s^2. What is its speed after 8 seconds?").show()
# -> SOLVED — 6 m/s  (velocity_time)
physics.solve("kinetic_energy", mass="3 kg", speed="4 m/s").show()
# -> SOLVED — 24 J  (kinetic_energy)
physics.ask("What is the kinetic energy of a car moving at 20 m/s?").show()
# -> NEEDS_INPUT — Translational kinetic energy applies, but it needs: mass (kg). Add it to the question with its unit, or use so
physics.ask("Who created you?").message
# -> physics-ai999x was created and engineered by Ibnul Jaif Farabi at AI999X.
```

Command line: `physics-ai999x "<question>"`, `physics-ai999x --capabilities`. The outputs above were produced by running this exact code on physics-ai999x 2.0.0.

## Find the right capability, and draw it

`physics.search()` finds which certified capability a question is about — across **every** AI999X model, so a question for another model points you to it. It runs the AI999X capability encoder (a 4.9 MB ONNX model, offline): `pip install "physics-ai999x[search]"`. `ask(question, suggest=True)` adds the same pointers to a question it does not answer; an answer itself never changes.

```python
import physics_ai999x as physics

physics.search("How long does a pendulum take to swing back and forth?", k=2)
# -> Period of a simple pendulum (physics-ai999x, 0.78); Precession period of a Foucault pendulum (mechanics-ai999x, 0.68)
physics.search("Solve x^2 - 5x + 6 = 0", k=2)
# -> Roots of a quadratic equation (algebra-ai999x, 0.67); Solution of two linear equations in two unknowns (algebra-ai999x, 0.57)
```

## How every answer is verified

1. **Reading** — the question is turned into typed quantities (value, unit, kind, role) and one asked quantity; every stated number must be used or the question is refused.
2. **Planning** — only certified capabilities may answer; a capability applies only under the conditions the wording states (for example a pendulum, a liquid at rest, boiling).
3. **Computing** — exact symbolic or high-precision numeric evaluation.
4. **Checking** — dimensions, substitution back into the defining equation, and agreement between independent readings; any disagreement becomes a refusal, never a number.

Capabilities are certified before they ship: each must reproduce hand-worked reference cases, reject a deliberately wrong variant (a control), and leave every benchmark answer unchanged.

## Benchmarks

| Evaluation set | Questions | Correct | Refused (with reason) | **Wrong** |
|---|---|---|---|---|
| Development probes | 112 | 68 | 44 | **0** |
| Held-out: fresh questions (2026-10-15) | 42 | 32 | 10 | **0** |
| Held-out: probes | 34 | 30 | 4 | **0** |
| Held-out: promotion checks (2026-10-13) | 27 | 14 | 13 | **0** |
| Held-out: multi-body systems (2026-10-15) | 43 | 33 | 10 | **0** |
| Held-out: unused-input traps | 16 | 9 | 7 | **0** |
| Verified natural-language questions (physics-questions-1) | 1567 | 478 | 1086 | **0** |

Wrong means a number that disagrees with the verified answer. On the verified-question set, 3 of 481 answers differ from the record: two are unit spellings (ohm/ohms) or a self-contradictory question ('angular frequency in Hz'), one pairs two records that share an id; none is a reading error. Refusals are expected for questions outside the certified capabilities or with unusual wording; solve() covers every capability with typed inputs.

## Optional decision model (auto (gated) + suggest)

This repository also holds a compact ONNX decision model (`onnx/`, 37.4 MB int8, 33.4M parameters, CPU; fine-tuned from BAAI/bge-small-en-v1.5): it reads a question the rule-based reader refuses, names the capability it needs and copies the input values from the words (it never writes a digit itself).

**When it answers by itself:** only through a gate — confidence at or above the zero-wrong cut chosen on validation with this very file, every required input read, every number in the question used, and the engine's verification; the asked quantity read by the rule-based reader (never inferred from which value is missing), every input copied with its unit, no direction or sign word in the question, and the relation's context conditions. The answer says it was read by the model. Otherwise it **suggests** the capability and a pre-filled call for you to check.

| Measured (held-out questions the rule-based reader refuses) | Value |
|---|---|
| Right capability named | 157 of 159 named right (227 held-out questions the rule-based reader refuses) |
| Input values copied | through the gate: 19 answered automatically on test, 0 wrong; 201 get a suggestion |
| CPU latency, p95 | 47.2 ms (4 threads) |

Through the gate it answered 19 held-out test and 22 validation questions that the rule-based reader refuses, with 0 wrong. On 1,377 rejected teacher questions it answered 41 distinct questions by itself, all correct by hand calculation (in every disagreement the teacher's key was wrong), and the 88 benchmark questions the reader refuses stay refused.

```bash
pip install "physics-ai999x[onnx]"
hf download AI999X/physics-ai999x --include "onnx/*" --local-dir physics_model
```

```python
import physics_ai999x as physics
reader = physics.DecisionReader("physics_model/onnx")
physics.ask("A 0.25 m rod generates 5 V while sliding in a 1 T field. How fast is the rod moving?", reader=reader).value   # -> 20.0 (m/s), read by the model, verified by the engine
physics.ask("quick one: spring 500 N/m, mass 0.01 kg, amplitude 0.004 m, top speed?", reader=reader).message
# -> ... Suggestion (decision model, not verified): this looks like `shm_max_speed` ... run physics_ai999x.shm_max_speed(k='500 N/m', m='0.01 kg', X='0.004 m')
```

Why the gate: the engine verifies a computation, not a reading. A copied number carries no sign, and the model does not decide what is asked — the rule-based reader names the asked quantity, and a question that sets directions against each other goes to a suggestion. Before that check, one held-out question ('downward at 2.0 m/s ... upward acceleration') was answered 8 m/s instead of 4 m/s upward.

## Capabilities

23 certified derivations, 16 certified model_familys, 2 certified procedures, 107 certified relations. A few of them:

- **Derivations:** acceleration with friction level; angular acceleration from tangential; angular frequency period; average speed equal instantaneous; centripetal acceleration from period; dielectric increases capacitance; displacement from velocity time; distance fallen time; energy via resistance; final speed from work; focal length; max height from velocity displacement; net work to speed; period from wave speed; power from voltage and resistance; solve for g; speed after height; speed after time dropped; speed from uniform motion; temp change inverse mass; time to stop; work to speed rest; zero initial speed
- **Model_familys:** A gas between two states; Apparent weight in an elevator; Block on a surface pulled over a pulley; Collisions along a line; Doppler effect for sound; Ideal banking of a curve; Maximum speed on a flat curve; Mixing to thermal equilibrium; Motion in stages; Projectile motion; RC circuits; Radioactive decay; Recoil from rest; Rolling from a height; Series and parallel resistor and capacitor networks; Two masses over a pulley
- **Procedures:** Two resistors in series and in parallel; Velocity and displacement after constant acceleration
- **Relations:** Absolute pressure at a depth in a fluid; Acceleration down a frictionless incline; Angular frequency and frequency; Angular momentum of a point mass on a circle; Angular momentum of a rotating body; Angular velocity and angle turned under constant angular acceleration; Angular velocity under constant angular acceleration; Average net force from a change of momentum; Average power; Capacitance of parallel plates; Carnot (maximum) efficiency; Centripetal acceleration; Centripetal acceleration from angular velocity; Centripetal force; Charge carried by a steady current; Charge on a capacitor; Coefficient of performance of a heat pump; Coefficient of performance of a refrigerator; Component of the weight along an incline; Current dying away in an RL circuit; De Broglie wavelength; Displacement from the mean of initial and final velocity; Displacement under constant acceleration; Efficiency of a heat engine …

`physics_ai999x.templates()` lists every question form `ask()` reads; the capability guide (PDF, every example executed) is included in this repository.

## Out of scope

- Open-ended explanation, essay writing or tutoring dialogue: it is a solver, not a chatbot.
- Questions outside its certified physics capabilities, and any question whose stated numbers it cannot all use — it refuses with the reason instead.
- High-stakes engineering, medical or legal decisions without independent review.

## Limitations

- It answers what its certified capabilities cover (kinematics, forces and Newton's laws, work and energy, momentum and collisions, circular motion and gravitation, rotation, oscillations and waves, fluids, heat and thermodynamics, electricity and circuits, magnetism and induction, optics and modern physics); anything else is refused with a reason.
- `ask()` reads documented question forms and common phrasings; unusual wording may be refused — use `solve()` for guaranteed results.
- Results are as correct as the certified relations and their stated conditions; a certified relation is a checked model, not a claim about every physical situation.

## Citation

```bibtex
@software{physics_ai999x_2_0_0,
  title  = {physics-ai999x: an offline, verified physics solver},
  author = {Farabi, Ibnul Jaif}, organization = {AI999X},
  year   = {2026}, version = {2.0.0},
  url    = {https://huggingface.co/AI999X/physics-ai999x}
}
```

## Contact

Questions, bug reports and requests: open a discussion on https://huggingface.co/AI999X/physics-ai999x/discussions or visit https://ai999x.com.

## Support the project

physics-ai999x is free and open source. If it helps you, you can support further development on [Buy Me a Coffee](https://buymeacoffee.com/ibnuljaiffarabi).

Created and engineered by **Ibnul Jaif Farabi** · **[AI999X](https://huggingface.co/AI999X)** · [ai999x.com](https://ai999x.com)

## Source and releases

This repository holds the installable source of each release, exactly as published on [PyPI](https://pypi.org/project/physics-ai999x/) (`pip install .` builds it). Releases are tagged `v<version>`; the wheel is attached to each [GitHub release](https://github.com/AI999X/physics-ai999x/releases). The optional ONNX models (formula graphs and, where measured, a decision model) are on [Hugging Face](https://huggingface.co/AI999X/physics-ai999x/tree/main/onnx).
