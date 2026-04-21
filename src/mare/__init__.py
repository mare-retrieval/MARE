"""MARE: Modality-Aware Retrieval Engine."""

from .api import MAREApp, load_corpus, load_pdf
from .engine import MAREngine
from .extensions import (
    BuiltinPDFParser,
    DoclingParser,
    FastEmbedReranker,
    FAISSIndexer,
    FAISSRetriever,
    IdentityReranker,
    KeywordBoostReranker,
    MAREConfig,
    PaddleOCRParser,
    QdrantIndexer,
    QdrantHybridRetriever,
    SentenceTransformersRetriever,
    SuryaParser,
    UnstructuredParser,
    get_parser,
    register_parser,
)
from .fusion import WeightedScoreFusion
from .integrations import (
    create_langgraph_tool,
    create_langchain_retriever,
    create_llamaindex_retriever,
    hits_to_evidence_payload,
    hit_to_langchain_document,
    hit_to_llamaindex_node,
)
from .router import HeuristicModalityRouter
from .types import Document, Modality, QueryPlan, RetrievalExplanation, RetrievalHit

__all__ = [
    "BuiltinPDFParser",
    "create_langgraph_tool",
    "create_langchain_retriever",
    "create_llamaindex_retriever",
    "Document",
    "DoclingParser",
    "FAISSIndexer",
    "FAISSRetriever",
    "FastEmbedReranker",
    "HeuristicModalityRouter",
    "hits_to_evidence_payload",
    "hit_to_langchain_document",
    "hit_to_llamaindex_node",
    "IdentityReranker",
    "KeywordBoostReranker",
    "get_parser",
    "load_corpus",
    "load_pdf",
    "MAREConfig",
    "MAREApp",
    "MAREngine",
    "Modality",
    "PaddleOCRParser",
    "QueryPlan",
    "QdrantIndexer",
    "QdrantHybridRetriever",
    "register_parser",
    "RetrievalExplanation",
    "RetrievalHit",
    "SentenceTransformersRetriever",
    "SuryaParser",
    "UnstructuredParser",
    "WeightedScoreFusion",
]
