from __future__ import annotations

import sys
import types

from mare import MAREApp
from mare.integrations import (
    build_agent_contract_payload,
    build_all_grounded_findings_payload,
    build_evidence_brief_payload,
    build_grounded_findings_payload,
    build_grounded_review_payload,
    build_grounded_summary_payload,
    create_langchain_tool,
    create_langgraph_tool,
    create_langchain_retriever,
    create_llamaindex_tool,
    create_llamaindex_retriever,
    format_evidence_citation,
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


def _second_sample_hit() -> RetrievalHit:
    return RetrievalHit(
        doc_id="doc-62",
        title="Guide",
        page=62,
        modality=Modality.TEXT,
        score=0.73,
        reason="Matched similar setup wording",
        snippet="Enable Wake on LAN before shutting down the system.",
        page_image_path="generated/guide/page-62.png",
        highlight_image_path="generated/guide/highlights/page-62.png",
        object_id="obj-2",
        object_type="section",
        metadata={"source": "guide.docx", "heading": "Wake on LAN"},
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
    payload = hits_to_evidence_payload("wake on lan", [_sample_hit(), _second_sample_hit()])

    assert payload["query"] == "wake on lan"
    assert len(payload["results"]) == 2
    assert payload["results"][0]["doc_id"] == "doc-61"
    assert payload["results"][0]["object_type"] == "procedure"
    assert payload["results"][0]["citation"] == "Manual | page 61 | Wake on LAN"
    assert payload["comparison"][0]["citation"] == "Manual | page 61 | Wake on LAN"
    assert payload["comparison"][1]["citation"] == "guide.docx | page 62 | Wake on LAN"
    assert payload["summary"]["overview"] == "Found 2 grounded results across 2 sources."
    assert payload["summary"]["highlights"][1]["citation"] == "guide.docx | page 62 | Wake on LAN"
    assert payload["evidence_brief"]["support"]["status"] == "strong"
    assert payload["evidence_brief"]["source_count"] == 2
    assert payload["evidence_brief"]["source_diversity"]["status"] == "broad"
    assert payload["evidence_brief"]["evidence_quality"]["status"] == "high"
    assert payload["evidence_brief"]["evidence_quality"]["passed_checks"] >= 4
    assert payload["evidence_brief"]["research_plan"]["status"] == "ready"
    assert payload["evidence_brief"]["research_plan"]["steps"][0]["action"] == "answer_with_citations"
    assert payload["agent_contract"]["schema_version"] == "mare.agent_contract.v1"
    assert payload["agent_contract"]["may_answer"] is True
    assert payload["agent_contract"]["recommended_action"] == "answer_with_citations"
    assert payload["review"]["evidence_brief"]["overview"].startswith("Strong support")


def test_build_grounded_summary_payload_handles_no_results() -> None:
    payload = build_grounded_summary_payload([])

    assert payload["overview"] == "No grounded evidence found."
    assert payload["highlight_count"] == 0
    assert payload["highlights"] == []


def test_build_evidence_brief_payload_flags_gaps_and_next_questions() -> None:
    results = [
        {
            "citation": "manual.pdf | page 4",
            "title": "Manual",
            "page": 4,
            "score": 0.52,
            "object_type": "section",
            "snippet": "Connect the AC adapter before powering on.",
            "reason": "Matched setup wording",
            "metadata": {"source": "manual.pdf"},
            "page_image_path": "",
            "highlight_image_path": "",
        }
    ]

    brief = build_evidence_brief_payload("connect the adapter", results)

    assert brief["support"]["status"] == "weak"
    assert brief["source_documents"] == ["manual.pdf"]
    assert brief["source_diversity"]["status"] == "single_source"
    assert "snippet" in brief["available_proof_assets"]
    assert any("highlighted visual proof" in gap for gap in brief["evidence_gaps"])
    assert brief["evidence_quality"]["status"] == "limited"
    assert any(
        item["name"] == "visual_proof" and item["status"] == "warn"
        for item in brief["evidence_quality"]["checks"]
    )
    assert brief["next_questions"]
    assert brief["research_plan"]["status"] == "needs_stronger_support"
    assert brief["research_plan"]["steps"][0]["action"] == "retrieve_stronger_support"


def test_build_evidence_brief_payload_detects_conflict_hints() -> None:
    results = [
        {
            "citation": "policy.pdf | page 2",
            "title": "Policy",
            "page": 2,
            "score": 0.82,
            "object_type": "section",
            "snippet": "Employees must submit the acknowledgement before onboarding is complete.",
            "reason": "Matched requirement language",
            "metadata": {"source": "policy.pdf"},
        },
        {
            "citation": "faq.md | lines 8-9",
            "title": "FAQ",
            "page": 1,
            "score": 0.76,
            "object_type": "section",
            "snippet": "The acknowledgement is optional when onboarding is already complete.",
            "reason": "Matched optional language",
            "metadata": {"source": "faq.md"},
        },
    ]

    brief = build_evidence_brief_payload("is the acknowledgement required", results)

    assert brief["source_diversity"]["status"] == "broad"
    assert brief["conflict_hints"][0]["type"] == "requirement_vs_optional"
    assert any(
        item["name"] == "conflict_signals" and item["status"] == "warn"
        for item in brief["evidence_quality"]["checks"]
    )
    assert brief["research_plan"]["status"] == "needs_conflict_check"
    assert brief["research_plan"]["steps"][0]["action"] == "resolve_conflicts"
    assert "Potentially conflicting evidence signals" in brief["evidence_gaps"][0] or any(
        "Potentially conflicting evidence signals" in gap for gap in brief["evidence_gaps"]
    )


def test_build_evidence_brief_payload_builds_source_discovery_plan_for_no_results() -> None:
    brief = build_evidence_brief_payload("required onboarding forms", [])
    contract = build_agent_contract_payload(brief)

    assert brief["research_plan"]["status"] == "needs_evidence"
    assert brief["evidence_quality"]["status"] == "poor"
    assert brief["evidence_quality"]["checks"][0]["name"] == "retrieval"
    assert brief["research_plan"]["step_count"] == 3
    assert brief["research_plan"]["steps"][0]["action"] == "discover_sources"
    assert brief["research_plan"]["steps"][1]["action"] == "retrieve_exact_support"
    assert "required onboarding forms" in brief["research_plan"]["steps"][0]["query"]
    assert contract["recommended_action"] == "discover_sources"
    assert contract["may_answer"] is False
    assert "needs_evidence" in contract["stop_reasons"]


def test_build_agent_contract_payload_blocks_weak_or_conflicting_evidence() -> None:
    weak_brief = build_evidence_brief_payload(
        "connect the adapter",
        [
            {
                "citation": "manual.pdf | page 4",
                "title": "Manual",
                "page": 4,
                "score": 0.52,
                "object_type": "section",
                "snippet": "Connect the AC adapter before powering on.",
                "reason": "Matched setup wording",
                "metadata": {"source": "manual.pdf"},
            }
        ],
    )
    weak_contract = build_agent_contract_payload(weak_brief)

    assert weak_contract["may_answer"] is False
    assert weak_contract["recommended_action"] == "retrieve_stronger_support"
    assert "support_not_sufficient" in weak_contract["stop_reasons"]

    conflict_brief = build_evidence_brief_payload(
        "is acknowledgement required",
        [
            {
                "citation": "policy.pdf | page 2",
                "title": "Policy",
                "page": 2,
                "score": 0.91,
                "object_type": "section",
                "snippet": "Employees must submit the acknowledgement.",
                "reason": "Matched requirement language",
                "metadata": {"source": "policy.pdf"},
            },
            {
                "citation": "faq.md | line 8",
                "title": "FAQ",
                "page": 1,
                "score": 0.88,
                "object_type": "section",
                "snippet": "The acknowledgement is optional for returning employees.",
                "reason": "Matched optional language",
                "metadata": {"source": "faq.md"},
            },
        ],
    )
    conflict_contract = build_agent_contract_payload(conflict_brief)

    assert conflict_contract["may_answer"] is False
    assert conflict_contract["recommended_action"] == "resolve_conflicts"
    assert "conflict_hints_present" in conflict_contract["stop_reasons"]


def test_build_agent_contract_payload_blocks_poor_evidence_quality() -> None:
    brief = build_evidence_brief_payload(
        "what does the policy require",
        [
            {
                "citation": "policy.pdf | page 2",
                "title": "Policy",
                "page": 2,
                "score": 0.9,
                "object_type": "section",
                "snippet": "",
                "reason": "Matched policy wording",
                "metadata": {"source": "policy.pdf"},
            }
        ],
    )

    contract = build_agent_contract_payload(brief)

    assert brief["support"]["status"] == "strong"
    assert brief["evidence_quality"]["status"] == "poor"
    assert contract["may_answer"] is False
    assert contract["recommended_action"] == "inspect_evidence"
    assert contract["evidence_quality_status"] == "poor"
    assert "evidence_quality_poor" in contract["stop_reasons"]


def test_build_grounded_findings_payload_extracts_actions_and_requirements() -> None:
    results = [
        {
            "citation": "manual.pdf | page 4",
            "title": "Manual",
            "page": 4,
            "score": 0.91,
            "object_type": "procedure",
            "snippet": "You must connect the AC adapter before powering on the device.",
            "reason": "Matched setup requirement language",
            "metadata": {"source": "manual.pdf"},
        },
        {
            "citation": "policy.docx | page 2",
            "title": "Policy",
            "page": 2,
            "score": 0.78,
            "object_type": "section",
            "snippet": "Submit the signed acknowledgement within 5 days of receipt.",
            "reason": "Matched policy action and deadline wording",
            "metadata": {"source": "policy.docx"},
        },
    ]

    actions = build_grounded_findings_payload(results, finding_type="actions")
    requirements = build_grounded_findings_payload(results, finding_type="requirements")

    assert actions["item_count"] == 2
    assert actions["items"][0]["signal"].lower() == "must"
    assert requirements["item_count"] == 1
    assert requirements["items"][0]["citation"] == "manual.pdf | page 4"


def test_build_all_grounded_findings_payload_extracts_risks_and_deadlines() -> None:
    results = [
        {
            "citation": "safety.pdf | page 8",
            "title": "Safety",
            "page": 8,
            "score": 0.88,
            "object_type": "section",
            "snippet": "Warning: do not expose the battery to water.",
            "reason": "Matched warning language",
            "metadata": {"source": "safety.pdf"},
        },
        {
            "citation": "policy.docx | page 3",
            "title": "Policy",
            "page": 3,
            "score": 0.76,
            "object_type": "section",
            "snippet": "Complete the training by March 15, 2026.",
            "reason": "Matched due-date language",
            "metadata": {"source": "policy.docx"},
        },
    ]

    findings = build_all_grounded_findings_payload(results)

    assert findings["risks"]["item_count"] == 1
    assert findings["risks"]["items"][0]["signal"].lower() == "warning"
    assert findings["deadlines"]["item_count"] == 1
    assert findings["deadlines"]["items"][0]["citation"] == "policy.docx | page 3"


def test_build_grounded_review_payload_summarizes_best_evidence_and_findings() -> None:
    results = [
        {
            "citation": "manual.pdf | page 4",
            "title": "Manual",
            "page": 4,
            "score": 0.91,
            "object_type": "procedure",
            "snippet": "You must connect the AC adapter before powering on the device.",
            "reason": "Matched setup requirement language",
            "metadata": {"source": "manual.pdf"},
        }
    ]

    review = build_grounded_review_payload(
        results,
        support={"label": "Strong support", "message": "Grounded evidence looks strong for this answer."},
    )

    assert review["best_evidence"]["citation"] == "manual.pdf | page 4"
    assert review["support"]["label"] == "Strong support"
    assert "Support: Strong support" in review["highlights"]


def test_format_evidence_citation_uses_line_metadata_when_available() -> None:
    citation = format_evidence_citation(
        title="Guide",
        page=1,
        metadata={
            "source": "/tmp/guide.md",
            "line_start": "3",
            "line_end": "7",
            "heading": "Setup",
        },
    )

    assert citation == "guide.md | lines 3-7 | Setup"


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


def test_create_langchain_tool_returns_structured_evidence(monkeypatch) -> None:
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
        [Document(doc_id="11", title="Guide", page=3, text="Connect the AC adapter to the computer.")]
    )

    tool = create_langchain_tool(app, top_k=1, name="mare_langchain_tool")
    result = tool.invoke({"query": "connect the AC adapter"})

    assert tool.name == "mare_langchain_tool"
    assert result["results"][0]["page"] == 3
    assert "summary" in result
    assert "comparison" in result


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


def test_mare_app_exposes_langchain_tool(monkeypatch) -> None:
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

    app = MAREApp.from_documents([Document(doc_id="12", title="Manual", page=6, text="Wake on LAN feature setup.")])
    tool = app.as_langchain_tool(top_k=1, name="custom_langchain_tool")
    result = tool.invoke({"query": "wake on lan"})

    assert tool.name == "custom_langchain_tool"
    assert result["results"][0]["doc_id"] == "12"


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


def test_create_llamaindex_tool_returns_structured_evidence(monkeypatch) -> None:
    class _FakeFunctionTool:
        def __init__(self, fn, name: str, description: str) -> None:
            self.fn = fn
            self.metadata = {"name": name, "description": description}

        def __call__(self, *args, **kwargs):
            return self.fn(*args, **kwargs)

        @classmethod
        def from_defaults(cls, fn, name: str, description: str):
            return cls(fn=fn, name=name, description=description)

    fake_tools = types.ModuleType("llama_index.core.tools")
    fake_tools.FunctionTool = _FakeFunctionTool
    monkeypatch.setitem(sys.modules, "llama_index", types.ModuleType("llama_index"))
    monkeypatch.setitem(sys.modules, "llama_index.core", types.ModuleType("llama_index.core"))
    monkeypatch.setitem(sys.modules, "llama_index.core.tools", fake_tools)

    app = MAREApp.from_documents([Document(doc_id="13", title="Manual", page=7, text="Connect the AC adapter.")])
    tool = create_llamaindex_tool(app, top_k=1, name="mare_llamaindex_tool")
    result = tool(query="connect the AC adapter")

    assert tool.metadata["name"] == "mare_llamaindex_tool"
    assert result["results"][0]["doc_id"] == "13"
    assert "summary" in result


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


def test_mare_app_exposes_llamaindex_tool(monkeypatch) -> None:
    class _FakeFunctionTool:
        def __init__(self, fn, name: str, description: str) -> None:
            self.fn = fn
            self.metadata = {"name": name, "description": description}

        def __call__(self, *args, **kwargs):
            return self.fn(*args, **kwargs)

        @classmethod
        def from_defaults(cls, fn, name: str, description: str):
            return cls(fn=fn, name=name, description=description)

    fake_tools = types.ModuleType("llama_index.core.tools")
    fake_tools.FunctionTool = _FakeFunctionTool
    monkeypatch.setitem(sys.modules, "llama_index", types.ModuleType("llama_index"))
    monkeypatch.setitem(sys.modules, "llama_index.core", types.ModuleType("llama_index.core"))
    monkeypatch.setitem(sys.modules, "llama_index.core.tools", fake_tools)

    app = MAREApp.from_documents([Document(doc_id="14", title="Guide", page=9, text="Enable Wake on LAN.")])
    tool = app.as_llamaindex_tool(top_k=1, name="custom_llamaindex_tool")
    result = tool(query="wake on lan")

    assert tool.metadata["name"] == "custom_llamaindex_tool"
    assert result["results"][0]["doc_id"] == "14"
