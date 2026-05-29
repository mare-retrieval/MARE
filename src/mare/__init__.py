"""MARE: Modality-Aware Retrieval Engine."""

from .api import MAREApp, load_corpora, load_corpus, load_document, load_pdf
from .engine import MAREngine
from .eval import EvalCase, EvalCaseResult, EvalSummary, evaluate_cases, evaluate_corpus, load_eval_cases
from .extensions import (
    BuiltinDocxParser,
    BuiltinTextParser,
    BuiltinPDFParser,
    DoclingParser,
    FastEmbedReranker,
    FAISSIndexer,
    FAISSRetriever,
    HybridSemanticRetriever,
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
    build_all_grounded_findings_payload,
    build_grounded_findings_payload,
    build_grounded_review_payload,
    create_langchain_tool,
    create_langgraph_tool,
    create_langchain_retriever,
    create_llamaindex_tool,
    create_llamaindex_retriever,
    build_grounded_summary_payload,
    hits_to_evidence_payload,
    hit_to_langchain_document,
    hit_to_llamaindex_node,
)
from .router import HeuristicModalityRouter
from .types import Document, Modality, QueryPlan, RetrievalExplanation, RetrievalHit


def create_mcp_server():
    from .mcp_server import create_mcp_server as _create_mcp_server

    return _create_mcp_server()


def describe_corpus_tool(*args, **kwargs):
    from .mcp_server import describe_corpus_tool as _describe_corpus_tool

    return _describe_corpus_tool(*args, **kwargs)


def ingest_pdf_tool(*args, **kwargs):
    from .mcp_server import ingest_pdf_tool as _ingest_pdf_tool

    return _ingest_pdf_tool(*args, **kwargs)


def ingest_document_tool(*args, **kwargs):
    from .mcp_server import ingest_document_tool as _ingest_document_tool

    return _ingest_document_tool(*args, **kwargs)


def page_objects_tool(*args, **kwargs):
    from .mcp_server import page_objects_tool as _page_objects_tool

    return _page_objects_tool(*args, **kwargs)


def query_corpora_tool(*args, **kwargs):
    from .mcp_server import query_corpora_tool as _query_corpora_tool

    return _query_corpora_tool(*args, **kwargs)


def query_corpus_tool(*args, **kwargs):
    from .mcp_server import query_corpus_tool as _query_corpus_tool

    return _query_corpus_tool(*args, **kwargs)


def query_pdf_tool(*args, **kwargs):
    from .mcp_server import query_pdf_tool as _query_pdf_tool

    return _query_pdf_tool(*args, **kwargs)


def query_document_tool(*args, **kwargs):
    from .mcp_server import query_document_tool as _query_document_tool

    return _query_document_tool(*args, **kwargs)


def search_objects_tool(*args, **kwargs):
    from .mcp_server import search_objects_tool as _search_objects_tool

    return _search_objects_tool(*args, **kwargs)

__all__ = [
    "BuiltinPDFParser",
    "BuiltinDocxParser",
    "BuiltinTextParser",
    "build_all_grounded_findings_payload",
    "build_grounded_findings_payload",
    "build_grounded_review_payload",
    "build_grounded_summary_payload",
    "create_langchain_tool",
    "create_langgraph_tool",
    "create_langchain_retriever",
    "create_llamaindex_tool",
    "create_llamaindex_retriever",
    "create_mcp_server",
    "describe_corpus_tool",
    "Document",
    "DoclingParser",
    "EvalCase",
    "EvalCaseResult",
    "EvalSummary",
    "FAISSIndexer",
    "FAISSRetriever",
    "FastEmbedReranker",
    "HeuristicModalityRouter",
    "HybridSemanticRetriever",
    "hits_to_evidence_payload",
    "hit_to_langchain_document",
    "hit_to_llamaindex_node",
    "ingest_pdf_tool",
    "ingest_document_tool",
    "IdentityReranker",
    "KeywordBoostReranker",
    "get_parser",
    "evaluate_cases",
    "evaluate_corpus",
    "load_corpus",
    "load_corpora",
    "load_eval_cases",
    "load_document",
    "load_pdf",
    "MAREConfig",
    "MAREApp",
    "MAREngine",
    "Modality",
    "PaddleOCRParser",
    "page_objects_tool",
    "query_corpora_tool",
    "QueryPlan",
    "query_corpus_tool",
    "query_document_tool",
    "query_pdf_tool",
    "QdrantIndexer",
    "QdrantHybridRetriever",
    "register_parser",
    "RetrievalExplanation",
    "RetrievalHit",
    "search_objects_tool",
    "SentenceTransformersRetriever",
    "SuryaParser",
    "UnstructuredParser",
    "WeightedScoreFusion",
]
