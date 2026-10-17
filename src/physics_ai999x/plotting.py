"""Plots (optional: `pip install physics-ai999x[plot]`, which adds matplotlib).

    plot_relation("kinetic_energy", x="v", over=(0, 20), fixed={"m": 3})     # K against v for m = 3 kg
    plot(answer)                                                             # the answer's last relation around its result

Values are in SI units. Nothing is plotted that the relation's own solver does not compute.
"""
from __future__ import annotations

from . import pack as _pack


def _plt():
    try:
        import matplotlib
        matplotlib.use("Agg") if not _interactive() else None
        import matplotlib.pyplot as plt
        return plt
    except ImportError as exc:
        raise ImportError("plotting needs matplotlib: pip install physics-ai999x[plot]") from exc


def _interactive() -> bool:
    try:
        from IPython import get_ipython
        return get_ipython() is not None
    except ImportError:
        return False


def plot_relation(key: str, x: str, over: tuple, fixed: dict, y: str | None = None, points: int = 101, path=None):
    """Plot one relation: `y` (default: the left-hand symbol) against `x` over `over`, other symbols `fixed`."""
    plt = _plt()
    p = _pack()
    r = p.by_key[key]
    y = y or next(n for n in r.symbols if r.equation.split("=")[0].strip() == n)
    xs, ys = [], []
    lo, hi = over
    for i in range(points):
        xv = lo + (hi - lo) * i / (points - 1)
        try:
            ys.append(r.solve(y, {**fixed, x: xv}))
            xs.append(xv)
        except Exception:
            continue
    fig, ax = plt.subplots(figsize=(6, 3.6))
    ax.plot(xs, ys)
    sx, sy = r.symbols[x], r.symbols[y]
    ax.set_xlabel(f"{x} ({sx.desc or sx.kind}) [{p.kinds[sx.kind].unit}]")
    ax.set_ylabel(f"{y} ({sy.desc or sy.kind}) [{p.kinds[sy.kind].unit}]")
    ax.set_title(f"{r.name}: ${r.latex()}$" + (f"  ({', '.join(f'{k}={v:g}' for k, v in fixed.items())})" if fixed else ""), fontsize=9)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    if path:
        fig.savefig(path, dpi=130)
    return fig


def plot(answer, span: float = 1.0, points: int = 101, path=None):
    """Plot the answer's last step: its result against its first input, over ±span×(that input's value)."""
    if not answer.solved or not answer.steps:
        raise ValueError("only a solved answer can be plotted")
    s = answer.steps[-1]
    x = next(iter(s["inputs"]))
    xv = s["inputs"][x]["value"]
    fixed = {k: v["value"] for k, v in s["inputs"].items() if k != x}
    lo, hi = (xv - span * abs(xv), xv + span * abs(xv)) if xv else (-1.0, 1.0)
    fig = plot_relation(s["relation"], x, (max(lo, 0.0) if xv > 0 else lo, hi), fixed, y=s["target"], points=points, path=None)
    ax = fig.axes[0]
    ax.plot([xv], [s["result"]], "o")
    ax.annotate(f"{s['result']:.4g} {s['unit']}", (xv, s["result"]), textcoords="offset points", xytext=(6, 6), fontsize=8)
    if path:
        fig.savefig(path, dpi=130)
    return fig
