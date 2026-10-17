# GENERATED from ai999x_factory/runtime by tools/build_package.py — do not edit.
"""Safe mathematical expressions: an allowlisted parser (never eval/sympify on text), dimension inference and
LaTeX generated from the canonical expression."""
from __future__ import annotations

import ast
from fractions import Fraction

import sympy as sp

from .quantity import ONE, Dim

FUNCS = {"sqrt": sp.sqrt, "sin": sp.sin, "cos": sp.cos, "tan": sp.tan, "exp": sp.exp, "log": sp.log,
         "asin": sp.asin, "acos": sp.acos, "atan": sp.atan}
CONSTS = {"pi": sp.pi}
_DIMENSIONLESS_ARG = (sp.sin, sp.cos, sp.tan, sp.exp, sp.log, sp.asin, sp.acos, sp.atan)


class ExpressionError(ValueError):
    pass


def parse(text: str, symbols: dict, symbolic_powers: bool = False) -> sp.Expr:
    """Parse arithmetic over the given symbols. Only numbers, the named symbols, pi, + - * / **, and the
    functions in FUNCS are accepted; anything else raises ExpressionError."""
    if not isinstance(text, str) or not text.strip() or len(text) > 400:
        raise ExpressionError("expression missing or too long")
    try:
        tree = ast.parse(text.strip(), mode="eval")
    except SyntaxError as exc:
        raise ExpressionError(f"cannot parse: {text}") from exc
    if sum(1 for _ in ast.walk(tree)) > 120:
        raise ExpressionError("expression too complex")

    def walk(n):
        if isinstance(n, ast.Expression):
            return walk(n.body)
        if isinstance(n, ast.Constant) and type(n.value) in (int, float):
            return sp.Integer(n.value) if isinstance(n.value, int) else sp.Rational(str(n.value))
        if isinstance(n, ast.Name):
            if n.id in symbols:
                return symbols[n.id]
            if n.id in CONSTS:
                return CONSTS[n.id]
            raise ExpressionError(f"unknown name: {n.id}")
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.USub, ast.UAdd)):
            v = walk(n.operand)
            return -v if isinstance(n.op, ast.USub) else v
        if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)):
            a, b = walk(n.left), walk(n.right)
            if isinstance(n.op, ast.Add):
                return a + b
            if isinstance(n.op, ast.Sub):
                return a - b
            if isinstance(n.op, ast.Mult):
                return a * b
            if isinstance(n.op, ast.Div):
                return a / b
            if symbolic_powers and not b.is_number:      # procedures: r**(n - 1) (still allowlisted syntax)
                return a ** b
            if not b.is_Rational or abs(b) > 8:
                raise ExpressionError("only small rational exponents are allowed")
            return a ** b
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in FUNCS
                and len(n.args) == 1 and not n.keywords):
            return FUNCS[n.func.id](walk(n.args[0]))
        raise ExpressionError("unsupported syntax")

    return walk(tree)


def dims(expr: sp.Expr, symbol_dims: dict) -> Dim:
    """Physical dimension of an expression (angles count as dimensionless). Raises ExpressionError when a
    sum mixes dimensions or a transcendental function receives a dimensioned argument."""
    if expr.is_Number or expr.is_NumberSymbol:
        return ONE
    if expr.is_Symbol:
        return symbol_dims[str(expr)].physical()
    if expr.is_Mul:
        out = ONE
        for a in expr.args:
            out = out * dims(a, symbol_dims)
        return out
    if expr.is_Pow:
        if not expr.exp.is_Rational:
            raise ExpressionError("exponent must be a rational number")
        return dims(expr.base, symbol_dims) ** Fraction(int(expr.exp.p), int(expr.exp.q))
    if expr.is_Add:
        seen = {dims(a, symbol_dims) for a in expr.args}
        if len(seen) != 1:
            raise ExpressionError("a sum mixes different dimensions")
        return seen.pop()
    if expr.func in _DIMENSIONLESS_ARG:
        if not dims(expr.args[0], symbol_dims).dimensionless:
            raise ExpressionError(f"{expr.func.__name__} needs a dimensionless argument")
        return ONE
    raise ExpressionError(f"no dimension rule for {expr.func}")


def latex(expr, names: dict | None = None) -> str:
    """LaTeX from the canonical expression; `names` maps a symbol to its display form."""
    return sp.latex(expr, symbol_names={k: v for k, v in (names or {}).items()})
