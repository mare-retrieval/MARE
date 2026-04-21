from __future__ import annotations

import sys
import types

from mare import MAREApp
from mare.integrations import (
    create_langgraph_tool,
    create_langchain_retriever,
    create_llamaindex_retriever,
    hits_to_evidence_payload,
    hit_to_langchain_document,
    hit_to_llamaindex_node,
)
from mare.types import Document, Modality, RetrievalHit


def _sample_hit() -> RetrievalHit:
    return RetrievalHit(
        doc_id="doc-61",
        title="Manual",
        page=61,
        modality=Modality.TEXT,
        score=0.91,
        reason="Matched grouped procedure",
        snippet="Wake on LAN feature setup instructions.",
        page_image_path="generated/manual/page-61.png",
        highlight_image_path="generated/manual/highlights/page-61.png",
        object_id="obj-1",
        object_type="procedure",
        metadata={"label": "Wake on LAN"},
    )


def test_hit_to_langchain_document_maps_metadata(monkeypatch) -> None:
    class _FakeDocument:
        def __init__(self, page_content: str, metadata: dict) -> None:
            self.page_content = page_content
            self.metadata = metadata

    fake_documents = types.ModuleType("langchain_core.documents")
    fake_documents.Document = _FakeDocument
    monkeypatch.setitem(sys.modules, "langchain_core", types.ModuleType("langchain_core"))
    monkeypatch.setitem(sys.modules, "langchain_core.documents", fake_documents)

    document = hit_to_langchain_document(_sample_hit())

    assert document.page_content.startswith("Wake on LAN")
    assert document.metadata["doc_id"] == "doc-61"
    assert document.metadata["object_type"] == "procedure"


def test_hits_to_evidence_payload_preserves_result_fields() -> None:
    payload = hits_to_evidence_payload("wake on lan", [_sample_hit()])

    assert payload["query"] == "wake on lan"
    assert len(payload["results"]) == 1
    assert payload["results"][0]["doc_id"] == "doc-61"
    assert payload["results"][0]["object_type"] == "procedure"


def test_hit_to_llamaindex_node_maps_metadata(monkeypatch) -> None:
    class _FakeTextNode:
        def __init__(self, text: str, metadata: dict) -> None:
            self.text = text
            self.metadata = metadata

    class _FakeNodeWithScore:
        def __init__(self, node, score: float) -> None:
            self.node = node
            self.score = score

    fake_schema = types.ModuleType("llama_index.core.schema")
    fake_schema.TextNode = _FakeTextNode
    fake_schema.NodeWithScore = _FakeNodeWithScore
    monkeypatch.setitem(sys.modules, "llama_index", types.ModuleType("llama_index"))
    monkeypatch.setitem(sys.modules, "llama_index.core", types.ModuleType("llama_index.core"))
    monkeypatch.setitem(sys.modules, "llama_index.core.schema", fake_schema)

    node_with_score = hit_to_llamaindex_node(_sample_hit())

    assert node_with_score.score == 0.91
    assert node_with_score.node.metadata["page"] == 61
    assert node_with_score.node.metadata["label"] == "Wake on LAN"


def test_mare_app_exposes_langchain_retriever(monkeypatch) -> None:
    class _FakeBaseRetriever:
        def __init__(self, **kwargs) -> None:
            for key, value in kwargs.items():
                setattr(self, key, value)

        def invoke(self, query: str):
            return self._get_relevant_documents(query)

    class _FakeDocument:
        def __init__(self, page_content: str, metadata: dict) -> None:
            self.page_content = page_content
            self.metadata = metadata

    fake_retrievers = types.ModuleType("langchain_core.retrievers")
    fake_retrievers.BaseRetriever = _FakeBaseRetriever
    fake_documents = types.ModuleType("langchain_core.documents")
    fake_documents.Document = _FakeDocument
    monkeypatch.setitem(sys.modules, "langchain_core", types.ModuleType("langchain_core"))
    monkeypatch.setitem(sys.modules, "langchain_core.retrievers", fake_retrievers)
    monkeypatch.setitem(sys.modules, "langchain_core.documents", fake_documents)

    app = MAREApp.from_documents(
        [Document(doc_id="1", title="Manual", page=1, text="Connect the AC adapter to the computer.")]
    )

    retriever = app.as_langchain_retriever(top_k=1)
    results = retriever.invoke("connect the AC adapter")

    assert len(results) == 1
    assert results[0].metadata["page"] == 1
    assert "adapter" in results[0].page_content.lower()


def test_create_langgraph_tool_returns_structured_evidence(monkeypatch) -> None:
    class _FakeStructuredTool:
        def __init__(self, func, name: str, description: str) -> None:
            self.func = func
            self.name = name
            self.description = description

        def invoke(self, payload):
            if isinstance(payload, dict):
                return self.func(**payload)
            return self.func(payload)

        @classmethod
        def from_function(cls, func, name: str, description: str):
            return cls(func=func, name=name, description=description)

    fake_tools = types.ModuleType("langchain_core.tools")
    fake_tools.StructuredTool = _FakeStructuredTool
    monkeypatch.setitem(sys.modules, "langchain_core", types.ModuleType("langchain_core"))
    monkeypatch.setitem(sys.modules, "langchain_core.tools", fake_tools)

    app = MAREApp.from_documents(
        [Document(doc_id="9", title="Manual", page=4, text="Connect the AC adapter to the computer.")]
    )

    tool = create_langgraph_tool(app, top_k=1)
    result = tool.invoke({"query": "connect the AC adapter"})

    assert tool.name == "mare_retrieve"
    assert result["query"] == "connect the AC adapter"
    assert len(result["results"]) == 1
    assert result["results"][0]["page"] == 4


def test_mare_app_exposes_langgraph_tool(monkeypatch) -> None:
    class _FakeStructuredTool:
        def __init__(self, func, name: str, description: str) -> None:
            self.func = func
            self.name = name
            self.description = description

        def invoke(self, payload):
            if isinstance(payload, dict):
                return self.func(**payload)
            return self.func(payload)

        @classmethod
        def from_function(cls, func, name: str, description: str):
            return cls(func=func, name=name, description=description)

    fake_tools = types.ModuleType("langchain_core.tools")
    fake_tools.StructuredTool = _FakeStructuredTool
    monkeypatch.setitem(sys.modules, "langchain_core", types.ModuleType("langchain_core"))
    monkeypatch.setitem(sys.modules, "langchain_core.tools", fake_tools)

    app = MAREApp.from_documents([Document(doc_id="5", title="Manual", page=8, text="Wake on LAN feature setup.")])
    tool = app.as_langgraph_tool(top_k=1, name="custom_mare_tool")
    result = tool.invoke({"query": "wake on lan"})

    assert tool.name == "custom_mare_tool"
    assert result["results"][0]["doc_id"] == "5"


def test_create_langchain_retriever_factory_works(monkeypatch) -> None:
    class _FakeBaseRetriever:
        def __init__(self, **kwargs) -> None:
            for key, value in kwargs.items():
                setattr(self, key, value)

    class _FakeDocument:
        def __init__(self, page_content: str, metadata: dict) -> None:
            self.page_content = page_content
            self.metadata = metadata

    fake_retrievers = types.ModuleType("langchain_core.retrievers")
    fake_retrievers.BaseRetriever = _FakeBaseRetriever
    fake_documents = types.ModuleType("langchain_core.documents")
    fake_documents.Document = _FakeDocument
    monkeypatch.setitem(sys.modules, "langchain_core", types.ModuleType("langchain_core"))
    monkeypatch.setitem(sys.modules, "langchain_core.retrievers", fake_retrievers)
    monkeypatch.setitem(sys.modules, "langchain_core.documents", fake_documents)

    app = MAREApp.from_documents([Document(doc_id="1", title="Manual", page=2, text="Turn off the computer.")])
    retriever = create_langchain_retriever(app, top_k=1)
    results = retriever._get_relevant_documents("turn off the computer")

    assert len(results) == 1
    assert results[0].metadata["doc_id"] == "1"


def test_create_llamaindex_retriever_returns_nodes(monkeypatch) -> None:
    class _FakeBaseRetriever:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def retrieve(self, query_bundle):
            return self._retrieve(query_bundle)

    class _FakeQueryBundle:
        def __init__(self, query_str: str) -> None:
            self.query_str = query_str

    class _FakeTextNode:
        def __init__(self, text: str, metadata: dict) -> None:
            self.text = text
            self.metadata = metadata

    class _FakeNodeWithScore:
        def __init__(self, node, score: float) -> None:
            self.node = node
            self.score = score

    fake_base_module = types.ModuleType("llama_index.core.base.base_retriever")
    fake_base_module.BaseRetriever = _FakeBaseRetriever
    fake_schema = types.ModuleType("llama_index.core.schema")
    fake_schema.QueryBundle = _FakeQueryBundle
    fake_schema.TextNode = _FakeTextNode
    fake_schema.NodeWithScore = _FakeNodeWithScore
    monkeypatch.setitem(sys.modules, "llama_index", types.ModuleType("llama_index"))
    monkeypatch.setitem(sys.modules, "llama_index.core", types.ModuleType("llama_index.core"))
    monkeypatch.setitem(sys.modules, "llama_index.core.base", types.ModuleType("llama_index.core.base"))
    monkeypatch.setitem(sys.modules, "llama_index.core.base.base_retriever", fake_base_module)
    monkeypatch.setitem(sys.modules, "llama_index.core.schema", fake_schema)

    app = MAREApp.from_documents(
        [Document(doc_id="2", title="Manual", page=61, text="Wake on LAN feature setup instructions.")]
    )

    retriever = create_llamaindex_retriever(app, top_k=1)
    results = retriever.retrieve(_FakeQueryBundle("wake on lan"))

    assert len(results) == 1
    assert results[0].node.metadata["doc_id"] == "2"
    assert results[0].score > 0


def test_mare_app_exposes_llamaindex_retriever(monkeypatch) -> None:
    class _FakeBaseRetriever:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def retrieve(self, query_bundle):
            return self._retrieve(query_bundle)

    class _FakeQueryBundle:
        def __init__(self, query_str: str) -> None:
            self.query_str = query_str

    class _FakeTextNode:
        def __init__(self, text: str, metadata: dict) -> None:
            self.text = text
            self.metadata = metadata

    class _FakeNodeWithScore:
        def __init__(self, node, score: float) -> None:
            self.node = node
            self.score = score

    fake_base_module = types.ModuleType("llama_index.core.base.base_retriever")
    fake_base_module.BaseRetriever = _FakeBaseRetriever
    fake_schema = types.ModuleType("llama_index.core.schema")
    fake_schema.QueryBundle = _FakeQueryBundle
    fake_schema.TextNode = _FakeTextNode
    fake_schema.NodeWithScore = _FakeNodeWithScore
    monkeypatch.setitem(sys.modules, "llama_index", types.ModuleType("llama_index"))
    monkeypatch.setitem(sys.modules, "llama_index.core", types.ModuleType("llama_index.core"))
    monkeypatch.setitem(sys.modules, "llama_index.core.base", types.ModuleType("llama_index.core.base"))
    monkeypatch.setitem(sys.modules, "llama_index.core.base.base_retriever", fake_base_module)
    monkeypatch.setitem(sys.modules, "llama_index.core.schema", fake_schema)

    app = MAREApp.from_documents([Document(doc_id="7", title="Manual", page=5, text="Connect the AC adapter.")])
    retriever = app.as_llamaindex_retriever(top_k=1)
    results = retriever.retrieve(_FakeQueryBundle("connect the AC adapter"))

    assert len(results) == 1
    assert results[0].node.metadata["page"] == 5
