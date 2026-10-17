"""Symbol normalisation for model input. The rule-based reader reads Ω, μ, λ ... itself; a small subword tokenizer
(t5) maps them to <unk>, so a trained reader sees words instead. Training and inference must use this same function."""
import re

SYMBOLS = {"Ω": " ohm", "Ω": " ohm", "μ": "micro", "µ": "micro", "λ": "lambda", "θ": "theta", "ω": "omega", "ρ": "rho",
           "Δ": "delta ", "π": "pi", "°": " degrees", "²": "^2", "³": "^3", "→": " to ", "≥": " >= ", "≤": " <= ",
           "α": "alpha", "β": "beta", "γ": "gamma", "τ": "tau", "φ": "phi", "σ": "sigma", "η": "eta", "ε": "epsilon",
           "×": " x ", "·": " ", "−": "-", "–": "-"}


def normalize_symbols(text: str) -> str:
    out = "".join(SYMBOLS.get(ch, ch) for ch in text)
    return re.sub(r"[ \t]+", " ", out).strip()
