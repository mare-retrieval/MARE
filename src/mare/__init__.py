"""MARE: Modality-Aware Retrieval Engine."""

from .api import MAREApp, load_corpus, load_pdf
from .engine import MAREngine
from .extensions import (
    BuiltinPDFParser,
    DoclingParser,
    IdentityReranker,
    KeywordBoostReranker,
    MAREConfig,
    UnstructuredParser,
    get_parser,
    register_parser,
)
from .fusion import WeightedScoreFusion
from .router import HeuristicModalityRouter
from .types import Document, Modality, QueryPlan, RetrievalExplanation, RetrievalHit

__all__ = [
    "BuiltinPDFParser",
    "Document",
    "DoclingParser",
    "HeuristicModalityRouter",
    "IdentityReranker",
    "KeywordBoostReranker",
    "get_parser",
    "load_corpus",
    "load_pdf",
    "MAREConfig",
    "MAREApp",
    "MAREngine",
    "Modality",
    "QueryPlan",
    "register_parser",
    "RetrievalExplanation",
    "RetrievalHit",
    "UnstructuredParser",
    "WeightedScoreFusion",
]
