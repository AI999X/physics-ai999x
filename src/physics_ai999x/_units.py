"""Unit conversion for the package's own helpers, from whichever copy of the engine is present."""
try:
    from ._engine.quantity import parse_unit, to_si
except ImportError:
    from ai999x_factory.runtime.quantity import parse_unit, to_si


def to_si_value(value: float, unit: str, kind) -> float:
    return to_si(value, parse_unit(unit), difference=getattr(kind, "difference", False))
