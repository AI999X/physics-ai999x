"""OPTIONAL trained reader (ONNX). Not needed for anything the package does; see docs/ONNX_CONTRACT.md.

    pip install physics-ai999x[onnx]                 # onnxruntime, tokenizers, numpy — no torch, no transformers
    from physics_ai999x import ask
    from physics_ai999x.reader import Reader
    r = Reader("path/to/physics_ai999x")             # a folder with encoder_model.onnx, decoder_model.onnx,
    ask("...", reader=r)                              # tokenizer.json, config.json, inference_config.json

Contract:
  * The rule-based reader answers first. The trained reading is tried only when the rule-based reader refuses.
  * The trained reading is a typed problem. It must pass every check of the verification gate (grounded,
    complete, kinds, roles, target, conditions, confidence threshold) and then be solved and verified by the
    engine. If both readers answer and disagree, the answer is a refusal.
  * The reader never computes an answer, never downloads anything and never sends anything anywhere.
  * As measured on 2026-10-15 (SFT experiments 1 and 2) the trained reader adds no correct answer on the
    independent evaluation sets; it is therefore off unless you pass it explicitly.
"""
from __future__ import annotations

from ._text import normalize_symbols

import json
from pathlib import Path

try:
    from ._engine import ask as _ask
    from ._engine.student_gate import gated_ask
except ImportError:
    from ai999x_factory.runtime import ask as _ask
    from ai999x_factory.runtime.student_gate import gated_ask


class Reader:
    def __init__(self, folder, threshold: float | None = None, max_new_tokens: int | None = None):
        try:
            import numpy as np
            import onnxruntime as ort
            from tokenizers import Tokenizer
        except ImportError as exc:
            raise ImportError("the trained reader needs: pip install physics-ai999x[onnx]") from exc
        folder = Path(folder)
        self.np = np
        cfg = json.loads((folder / "inference_config.json").read_text(encoding="utf-8"))
        model_cfg = json.loads((folder / "config.json").read_text(encoding="utf-8"))
        self.prefix = cfg["task_prefix"]
        self.normalize = bool(cfg.get("normalize_symbols", False))     # off for the SFT 1 and 2 models
        self.threshold = cfg["gate_threshold_mean_token_logprob"] if threshold is None else threshold
        self.max_new = max_new_tokens or cfg.get("max_new_tokens", 96)
        self.max_in = cfg.get("max_input_tokens", 160)
        self.start, self.eos = model_cfg["decoder_start_token_id"], model_cfg["eos_token_id"]
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 0
        self.enc = ort.InferenceSession(str(folder / "encoder_model.onnx"), opts, providers=["CPUExecutionProvider"])
        self.dec = ort.InferenceSession(str(folder / "decoder_model.onnx"), opts, providers=["CPUExecutionProvider"])
        self.tok = Tokenizer.from_file(str(folder / "tokenizer.json"))

    def read(self, question: str) -> tuple:
        """(typed-problem line, mean token log-probability) for one question. Greedy decoding."""
        np = self.np
        if self.normalize:                                           # models trained on normalised text only
            question = normalize_symbols(question)
        text = (self.prefix + question).replace("^", "**")          # the student's own input convention
        ids = self.tok.encode(text).ids[: self.max_in]
        input_ids = np.array([ids], dtype=np.int64)
        mask = np.ones_like(input_ids)
        hidden = self.enc.run(None, {"input_ids": input_ids, "attention_mask": mask})[0]
        out, logps = [self.start], []
        for _ in range(self.max_new):
            logits = self.dec.run(["logits"], {"input_ids": np.array([out], dtype=np.int64), "encoder_attention_mask": mask,
                                               "encoder_hidden_states": hidden})[0][0, -1]
            z = logits - logits.max()
            lp = z - np.log(np.exp(z).sum())
            nxt = int(lp.argmax())
            logps.append(float(lp[nxt]))
            if nxt == self.eos:
                break
            out.append(nxt)
        return self.tok.decode(out[1:], skip_special_tokens=True), (sum(logps) / max(1, len(logps)))

    def ask(self, question: str, pack):
        """The rule-based answer if there is one; otherwise the trained reading, through the gate."""
        rule = _ask(question, pack)
        if rule.solved:
            return rule
        reading, confidence = self.read(question)
        answer, source, reason = gated_ask(question, reading, pack, confidence, self.threshold)
        if answer is not None:
            answer.warnings = list(answer.warnings) + ["read by the optional trained reader; verified by the engine"]
            return answer
        rule.uncertainty = {**(rule.uncertainty or {}), "trained_reader": {"reading": reading, "confidence": round(confidence, 4),
                                                                           "refused_because": reason}}
        return rule
