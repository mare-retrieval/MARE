from __future__ import annotations

from typing import Any

from mare.types import RetrievalHit


def _hit_metadata(hit: RetrievalHit) -> dict[str, Any]:
    metadata = dict(hit.metadata)
    metadata.update(
        {
            "doc_id": hit.doc_id,
            "title": hit.title,
            "page": hit.page,
            "score": hit.score,
            "reason": hit.reason,
            "modality": hit.modality.value,
            "page_image_path": hit.page_image_path,
            "highlight_image_path": hit.highlight_image_path,
            "object_id": hit.object_id,
            "object_type": hit.object_type,
        }
    )
    return metadata


def _hit_text(hit: RetrievalHit) -> str:
    return hit.snippet or hit.reason or hit.title


def hits_to_evidence_payload(query: str, hits: list[RetrievalHit]) -> dict[str, Any]:
    return {
        "query": query,
        "results": [
            {
                "doc_id": hit.doc_id,
                "title": hit.title,
                "page": hit.page,
                "score": hit.score,
                "snippet": hit.snippet,
                "reason": hit.reason,
                "page_image_path": hit.page_image_path,
                "highlight_image_path": hit.highlight_image_path,
                "object_id": hit.object_id,
                "object_type": hit.object_type,
                "metadata": dict(hit.metadata),
            }
            for hit in hits
        ],
    }


def hit_to_langchain_document(hit: RetrievalHit):
    try:
        from langchain_core.documents import Document as LangChainDocument
    except ImportError as exc:
        raise RuntimeError(
            "LangChain integration requires `langchain-core`. Install it with "
            "`pip install 'mare-retrieval[langchain]'` or `pip install langchain-core`."
        ) from exc

    return LangChainDocument(page_content=_hit_text(hit), metadata=_hit_metadata(hit))


def hit_to_llamaindex_node(hit: RetrievalHit):
    try:
        from llama_index.core.schema import NodeWithScore, TextNode
    except ImportError as exc:
        raise RuntimeError(
            "LlamaIndex integration requires `llama-index-core`. Install it with "
            "`pip install 'mare-retrieval[llamaindex]'` or `pip install llama-index-core`."
        ) from exc

    node = TextNode(text=_hit_text(hit), metadata=_hit_metadata(hit))
    return NodeWithScore(node=node, score=hit.score)


def create_langchain_retriever(app, top_k: int = 3):
    try:
        from langchain_core.retrievers import BaseRetriever
    except ImportError as exc:
        raise RuntimeError(
            "LangChain integration requires `langchain-core`. Install it with "
            "`pip install 'mare-retrieval[langchain]'` or `pip install langchain-core`."
        ) from exc

    try:
        from pydantic import ConfigDict
    except ImportError:  # pragma: no cover - optional dependency
        ConfigDict = None

    class LangChainMARERetriever(BaseRetriever):
        mare_app: Any
        top_k: int = 3

        if ConfigDict is not None:
            model_config = ConfigDict(arbitrary_types_allowed=True)
        else:  # pragma: no cover - compatibility shim
            class Config:
                arbitrary_types_allowed = True

        def _get_relevant_documents(self, query: str, *, run_manager=None):
            hits = self.mare_app.retrieve(query=query, top_k=self.top_k)
            return [hit_to_langchain_document(hit) for hit in hits]

        async def _aget_relevant_documents(self, query: str, *, run_manager=None):
            return self._get_relevant_documents(query, run_manager=run_manager)

    return LangChainMARERetriever(mare_app=app, top_k=top_k)


def create_langgraph_tool(app, top_k: int = 3, name: str = "mare_retrieve", description: str | None = None):
    try:
        from langchain_core.tools import StructuredTool
    except ImportError as exc:
        raise RuntimeError(
            "LangGraph tool integration requires `langchain-core`. Install it with "
            "`pip install 'mare-retrieval[langgraph]'` or `pip install langchain-core langgraph`."
        ) from exc

    tool_description = description or (
        "Retrieve evidence from documents with MARE. Returns structured page, snippet, "
        "highlight, and metadata for the most relevant results."
    )

    def _run(query: str) -> dict[str, Any]:
        hits = app.retrieve(query=query, top_k=top_k)
        return hits_to_evidence_payload(query, hits)

    return StructuredTool.from_function(
        func=_run,
        name=name,
        description=tool_description,
    )


def create_llamaindex_retriever(app, top_k: int = 3):
    try:
        from llama_index.core.base.base_retriever import BaseRetriever
        from llama_index.core.schema import QueryBundle
    except ImportError as exc:
        raise RuntimeError(
            "LlamaIndex integration requires `llama-index-core`. Install it with "
            "`pip install 'mare-retrieval[llamaindex]'` or `pip install llama-index-core`."
        ) from exc

    class LlamaIndexMARERetriever(BaseRetriever):
        def __init__(self, mare_app, top_k: int = 3):
            super().__init__()
            self.mare_app = mare_app
            self.top_k = top_k

        def _retrieve(self, query_bundle):
            if isinstance(query_bundle, QueryBundle):
                query = query_bundle.query_str
            else:
                query = getattr(query_bundle, "query_str", str(query_bundle))
            hits = self.mare_app.retrieve(query=query, top_k=self.top_k)
            return [hit_to_llamaindex_node(hit) for hit in hits]

    return LlamaIndexMARERetriever(app, top_k=top_k)
