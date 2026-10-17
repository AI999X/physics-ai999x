"""The structured interface: say what to find and what is given, without writing a sentence.

    solve("kinetic energy", {"mass": "3 kg", "speed": "4 m/s"})
    solve("final speed", {"initial speed": "2 m/s", "acceleration": "3 m/s^2", "time": "4 s"})
    solve("acceleration", {"angle of the incline": "30 deg"}, conditions=["inclined", "frictionless"])
    solve("speed/final", {"speed/initial": (2, "m/s"), "acceleration": 3.0, "time": 4})   # bare numbers are SI

The implementation is shared by every domain package (ai999x_factory.runtime.product.Product).
"""
from __future__ import annotations

from . import _P

try:
    from ._engine.product import QuantityError
except ImportError:
    from ai999x_factory.runtime.product import QuantityError

problem, solve, quantities, conditions, formulas, formula = (_P.problem, _P.solve, _P.quantities, _P.conditions,
                                                           _P.formulas, _P.formula)
__all__ = ["QuantityError", "problem", "solve", "quantities", "conditions", "formulas", "formula"]
