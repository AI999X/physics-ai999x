# GENERATED from ai999x_factory/runtime by tools/build_package.py — do not edit.
"""The optional decision model in SUGGEST MODE: which capability a question needs, and the inputs it reads — offered
to the user to confirm, never computed on (docs/ONNX_CONTRACT.md, docs/DECISION_MODEL_PLAN.md).

    pip install "algebra-ai999x[onnx]"                      # onnxruntime, tokenizers, numpy (no torch)
    hf download AI999X/algebra-ai999x --include "onnx/*" --local-dir algebra_model
    from algebra_ai999x import DecisionReader
    algebra.ask("checking my homework: 3x - 7 = 14, what is x?", reader=DecisionReader("algebra_model/onnx"))

Why suggest mode: measured end to end, the model picks the right capability (27 of 27 questions the rule-based reader
refuses) but copies a wrong input value in 5 of 27 (mostly a lost minus sign). The engine cannot detect a misread
value — it would solve the misread equation correctly — so the model never answers: it names the capability, shows
a pre-filled call with the values marked to check, and the outcome stays a refusal. It runs only when the rule-based
reader refuses, loads nothing unless asked, and makes no network call.
"""
from __future__ import annotations

import json
import re
from pathlib import Path


class DecisionReader:
    """A compact ONNX encoder (capability + input spans). `threshold` is the zero-wrong cut chosen on validation with
    this very file; below it, or for 'none', nothing is suggested."""

    def __init__(self, folder):
        import numpy as np
        import onnxruntime as ort
        from tokenizers import Tokenizer
        folder = Path(folder)
        self.labels = json.loads((folder / "labels.json").read_text(encoding="utf-8"))
        # a suggestion is checked by the user, so its bar is lower than the zero-wrong cut an automatic answer would
        # need (threshold_compact); the confidence is always shown
        self.threshold = float(self.labels.get("threshold_suggest", 0.5))
        tok_file = folder / "tokenizer.json" if (folder / "tokenizer.json").exists() else folder / "tokenizer" / "tokenizer.json"
        self.tok = Tokenizer.from_file(str(tok_file))
        self.tok.no_padding()
        self.tok.enable_truncation(int(self.labels.get("max_len", 96)))
        model = folder / "decision.int8.onnx"
        self.session = ort.InferenceSession(str(model), providers=["CPUExecutionProvider"])
        self._np = np

    def read(self, text: str) -> dict | None:
        np = self._np
        e = self.tok.encode(text)
        ids = np.array([e.ids], dtype=np.int64)
        cap, _out, tags = self.session.run(None, {"input_ids": ids, "attention_mask": np.ones_like(ids)})
        p = np.exp(cap[0] - cap[0].max())
        p /= p.sum()
        caps, tagnames = self.labels["capability"], self.labels["tags"]
        best = caps[int(p.argmax())]
        if best == "none" or float(p.max()) < self.threshold:
            return None
        spans, cur = {}, None
        for j, (a, b) in enumerate(e.offsets):
            if a == b:
                continue
            t = tagnames[int(tags[0, j].argmax())]
            if t.startswith("B-") or (t.startswith("I-") and (cur is None or cur[0] != t[2:])):
                cur = [t[2:], a, b]
                spans.setdefault(cur[0], cur)
            elif t.startswith("I-") and cur is not None:
                cur[2] = b
            else:
                cur = None
        inputs = {}
        for slot, (_s, a, b) in spans.items():
            m = re.search(r"-?\d+(?:\.\d+)?(?:/\d+)?", text[a:b])
            if m:
                inputs[slot] = m.group(0)
        return {"capability": best, "confidence": round(float(p.max()), 4), "inputs": inputs}


def suggest(product, question: str, answer, reader):
    """Attach the decision model's suggestion to a refused answer (never to a solved one). Returns the answer."""
    if reader is None or not isinstance(question, str) or answer.outcome == "SOLVED":
        return answer
    try:
        s = reader.read(question)
    except Exception as exc:                          # an optional helper must never break ask()
        answer.uncertainty = {**(answer.uncertainty or {}), "decision_model_error": str(exc)[:200]}
        return answer
    if not s or s["capability"] not in product.capability_ids():
        return answer
    dist = f"{product.domain}_ai999x"
    call = f"{dist}.{s['capability']}(" + ", ".join(f"{k}={v}" for k, v in s["inputs"].items()) + ")"
    answer.suggestion = {**s, "call": call, "check": "values were read by a model: check each one (signs especially) "
                                                     "before running the call"}
    answer.message = ((answer.message or "").rstrip() + f"\nSuggestion (decision model, confidence {s['confidence']:.2f}, "
                      f"not verified): this looks like `{s['capability']}`. Read from your question: "
                      f"{s['inputs'] or 'no values'}. Check them (signs especially), then run "
                      f"{call} — see {dist}.help('{s['capability']}') for what each input means.")
    return answer
