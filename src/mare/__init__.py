"""MARE: Modality-Aware Retrieval Engine."""

from .api import MAREApp, load_corpus, load_pdf
from .engine import MAREngine
from .fusion import WeightedScoreFusion
from .router import HeuristicModalityRouter
from .types import Document, Modality, QueryPlan, RetrievalExplanation, RetrievalHit

__all__ = [
    "Document",
    "HeuristicModalityRouter",
    "load_corpus",
    "load_pdf",
    "MAREApp",
    "MAREngine",
    "Modality",
    "QueryPlan",
    "RetrievalExplanation",
    "RetrievalHit",
    "WeightedScoreFusion",
]
