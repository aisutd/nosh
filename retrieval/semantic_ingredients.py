"""Embedding-based fuzzy ingredient matching using the project's all-MiniLM-L6-v2 model.

Instead of hand-coding every synonym, this module embeds ingredient names and
finds the closest canonical name in the recipe database by cosine similarity.

    capsicum  →  embed  →  [0.12, -0.34, ...]  →  nearest: "bell pepper" (sim=0.91) ✅
    courgette →  embed  →  [0.08,  0.21, ...]  →  nearest: "zucchini"    (sim=0.88) ✅
    xylitol   →  embed  →  [0.02, -0.11, ...]  →  nearest: "sugar"       (sim=0.61) ❌ below threshold

The model is loaded and canonical embeddings are built once on first use (lazy init).
Subsequent calls use an in-memory cache keyed on the normalised ingredient name.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# Cosine similarity threshold: above this we accept the semantic match.
# 0.82 is conservative — avoids false positives like "cream" → "ice cream".
DEFAULT_THRESHOLD = 0.82

_instance: Optional["SemanticIngredientMatcher"] = None


class SemanticIngredientMatcher:
    """Lazy-loaded cosine-similarity matcher for ingredient names."""

    def __init__(self, threshold: float = DEFAULT_THRESHOLD):
        self.threshold = threshold
        self._canonical_names: list[str] | None = None
        self._canonical_embeddings: np.ndarray | None = None  # unit-norm rows
        self._cache: dict[str, str] = {}
        self._ef = None  # embedding function, loaded on first use

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Build canonical name list + embeddings on first call."""
        if self._canonical_names is not None:
            return

        logger.info("SemanticIngredientMatcher: building canonical embeddings (one-time)...")

        from rag.store import embedding_function
        from retrieval.ingredients import normalize_name

        self._ef = embedding_function()

        csv_path = Path(__file__).resolve().parent.parent / "data" / "processed" / "cleaned_recipes.csv"
        if not csv_path.exists():
            logger.warning("cleaned_recipes.csv not found; semantic matching disabled.")
            self._canonical_names = []
            self._canonical_embeddings = np.empty((0, 384))
            return

        import pandas as pd
        df = pd.read_csv(csv_path)

        canonical: set[str] = set()
        for raw in df["ingredients"].dropna():
            for frag in raw.split(","):
                name = normalize_name(frag.strip())
                # Keep only non-trivial names (skip pantry words, single chars, etc.)
                if name and len(name) > 2 and " " not in name or len(name.split()) <= 4:
                    canonical.add(name)

        self._canonical_names = sorted(canonical)
        if not self._canonical_names:
            self._canonical_embeddings = np.empty((0, 384))
            return

        raw_emb = np.array(self._ef(self._canonical_names), dtype=np.float32)
        norms = np.linalg.norm(raw_emb, axis=1, keepdims=True)
        self._canonical_embeddings = raw_emb / (norms + 1e-9)  # unit-norm rows
        logger.info("SemanticIngredientMatcher: %d canonical names embedded.", len(self._canonical_names))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def match(self, name: str) -> str:
        """Return the best canonical ingredient match for *name*, or *name* itself.

        Args:
            name: Already-normalised ingredient name (output of normalize_name).

        Returns:
            Canonical name if cosine similarity ≥ threshold, otherwise *name* unchanged.
        """
        if not name:
            return name
        if name in self._cache:
            return self._cache[name]

        try:
            self._load()
            if not self._canonical_names:
                return name

            q = np.array(self._ef([name])[0], dtype=np.float32)
            q_norm = q / (np.linalg.norm(q) + 1e-9)

            sims = self._canonical_embeddings @ q_norm  # (N,)
            best_idx = int(np.argmax(sims))
            best_sim = float(sims[best_idx])

            if best_sim >= self.threshold:
                result = self._canonical_names[best_idx]
                if result != name:
                    logger.debug(
                        "semantic match: %r → %r (sim=%.3f)", name, result, best_sim
                    )
            else:
                result = name  # below threshold — keep original

        except Exception as exc:  # never crash the pipeline
            logger.warning("SemanticIngredientMatcher.match(%r) failed: %s", name, exc)
            result = name

        self._cache[name] = result
        return result

    def clear_cache(self) -> None:
        """Wipe the in-memory match cache (useful for testing)."""
        self._cache.clear()


def get_matcher(threshold: float = DEFAULT_THRESHOLD) -> SemanticIngredientMatcher:
    """Return the shared singleton matcher, creating it on first call."""
    global _instance
    if _instance is None:
        _instance = SemanticIngredientMatcher(threshold=threshold)
    return _instance
