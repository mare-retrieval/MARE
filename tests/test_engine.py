from mare.engine import MAREngine
from mare.types import Document, DocumentObject, Modality, ObjectType, RetrievalFilters


def _docs() -> list[Document]:
    return [
        Document(
            doc_id="1",
            title="Transformer",
            page=1,
            text="The transformer uses attention and positional encoding.",
            image_caption="Architecture diagram with encoder decoder layers.",
            layout_hints="figure on a two-column page",
        ),
        Document(
            doc_id="2",
            title="Benchmark",
            page=2,
            text="A benchmark compares retrievers using recall and nDCG.",
            image_caption="Chart with recall results.",
            layout_hints="table with model comparison",
        ),
    ]


def test_router_prefers_image_for_visual_query() -> None:
    engine = MAREngine(_docs())
    explanation = engine.explain("show me the architecture diagram", top_k=2)
    assert Modality.IMAGE in explanation.plan.selected_modalities
    assert explanation.fused_results[0].doc_id == "1"


def test_router_prefers_layout_for_table_query() -> None:
    engine = MAREngine(_docs())
    explanation = engine.explain("table comparing retrieval models", top_k=2)
    assert Modality.LAYOUT in explanation.plan.selected_modalities
    assert Modality.TEXT in explanation.plan.selected_modalities
    assert explanation.fused_results[0].doc_id == "2"


def test_text_query_defaults_to_semantic_lookup() -> None:
    engine = MAREngine(_docs())
    explanation = engine.explain("what is positional encoding", top_k=2)
    assert explanation.plan.intent == "semantic_lookup"
    assert explanation.fused_results[0].doc_id == "1"
    assert "positional encoding" in explanation.fused_results[0].snippet.lower()


def test_retrieval_filters_limit_documents_pages_and_metadata() -> None:
    docs = _docs()
    docs[0].metadata.update({"source": "/docs/transformer.pdf", "version": "draft"})
    docs[1].metadata.update({"source": "/docs/benchmark.pdf", "version": "final"})
    engine = MAREngine(docs)

    hits = engine.retrieve(
        "retrieval benchmark positional encoding",
        top_k=3,
        filters=RetrievalFilters(sources=("benchmark.pdf",), pages=(2,), metadata={"version": "final"}),
    )

    assert hits
    assert {hit.doc_id for hit in hits} == {"2"}


def test_builtin_retrieval_filters_pages_before_scoring(monkeypatch) -> None:
    docs = _docs()
    engine = MAREngine(docs)
    from mare.retrievers.text import TextRetriever

    original = TextRetriever.retrieve
    seen = []

    def track(self, query, top_k=5):
        seen.append([document.doc_id for document in self.documents])
        return original(self, query, top_k)

    monkeypatch.setattr(TextRetriever, "retrieve", track)
    engine.retrieve("retrieval benchmark", filters=RetrievalFilters(document_ids=("2",)))
    assert seen == [["2"]]


def test_retrieval_filters_support_object_types() -> None:
    docs = [
        Document(
            doc_id="1",
            title="Guide",
            page=3,
            text="The setup procedure connects the adapter.",
            objects=[
                DocumentObject(
                    object_id="1:procedure:1",
                    doc_id="1",
                    page=3,
                    object_type=ObjectType.PROCEDURE,
                    content="Connect the adapter.",
                )
            ],
        )
    ]

    hits = MAREngine(docs).retrieve(
        "connect adapter procedure",
        filters=RetrievalFilters(object_types=("procedure",)),
    )

    assert hits
    assert all(hit.object_type == "procedure" for hit in hits)


def test_procedure_queries_get_structure_boost_reason() -> None:
    docs = [
        Document(
            doc_id="1",
            title="Repair",
            page=1,
            text="1. Use the driver to partially reinstall the set screws in the top case.",
            page_image_path="generated/repair/page-1.png",
            objects=[
                DocumentObject(
                    object_id="1:procedure:1",
                    doc_id="1",
                    page=1,
                    object_type=ObjectType.PROCEDURE,
                    content="1. Use the driver to partially reinstall the set screws in the top case.",
                )
            ],
            metadata={"signals": "procedure instruction"},
        ),
        Document(
            doc_id="2",
            title="Background",
            page=2,
            text="Set screws are components used in many repair procedures.",
            page_image_path="generated/repair/page-2.png",
        ),
    ]
    engine = MAREngine(docs)
    explanation = engine.explain("partially reinstall the set screws", top_k=2)
    assert explanation.fused_results[0].doc_id == "1"
    assert explanation.fused_results[0].object_type == "procedure"
    assert "structure boosts" in explanation.fused_results[0].reason.lower()


def test_table_queries_prefer_table_object_evidence() -> None:
    docs = [
        Document(
            doc_id="1",
            title="Comparison",
            page=3,
            text="Table 2 compares retrieval models across recall and latency.",
            layout_hints="table",
            objects=[
                DocumentObject(
                    object_id="1:table:1",
                    doc_id="1",
                    page=3,
                    object_type=ObjectType.TABLE,
                    content="Table 2 compares retrieval models across recall and latency.",
                    metadata={"label": "Table 2", "columns_estimate": "3"},
                )
            ],
            metadata={"signals": "table comparison"},
        ),
        Document(
            doc_id="2",
            title="Narrative",
            page=4,
            text="This section discusses retrieval models and latency in prose form.",
        ),
    ]
    engine = MAREngine(docs)
    explanation = engine.explain("show me the comparison table", top_k=2)

    assert explanation.fused_results[0].doc_id == "1"
    assert explanation.fused_results[0].object_type == "table"


def test_figure_queries_prefer_figure_object_evidence() -> None:
    docs = [
        Document(
            doc_id="1",
            title="Architecture",
            page=5,
            text="Figure 1 shows the retrieval architecture diagram.",
            layout_hints="figure",
            objects=[
                DocumentObject(
                    object_id="1:figure:1",
                    doc_id="1",
                    page=5,
                    object_type=ObjectType.FIGURE,
                    content="Figure 1 shows the retrieval architecture diagram.",
                    metadata={"label": "Figure 1"},
                )
            ],
            metadata={"signals": "figure"},
        ),
        Document(
            doc_id="2",
            title="Overview",
            page=6,
            text="The architecture is described in text only.",
        ),
    ]
    engine = MAREngine(docs)
    explanation = engine.explain("show me the architecture diagram", top_k=2)

    assert explanation.fused_results[0].doc_id == "1"
    assert explanation.fused_results[0].object_type == "figure"


def test_paraphrased_queries_match_instruction_text_via_aliases() -> None:
    docs = [
        Document(
            doc_id="1",
            title="Setup",
            page=7,
            text="Connect the adapter to the laptop before turning it on.",
        ),
        Document(
            doc_id="2",
            title="Background",
            page=8,
            text="Adapters are optional accessories for legacy devices.",
        ),
    ]

    engine = MAREngine(docs)
    explanation = engine.explain("how do I attach the adapter", top_k=2)

    assert explanation.fused_results[0].doc_id == "1"
    assert "alias matches" in explanation.fused_results[0].reason.lower()


def test_fusion_prefers_text_evidence_over_layout_labels() -> None:
    from mare.fusion import WeightedScoreFusion
    from mare.types import Modality, RetrievalHit

    layout = RetrievalHit(
        doc_id="d1", title="Guide", page=1, modality=Modality.LAYOUT, score=0.9,
        reason="Matched page signals: procedure", snippet="procedure", metadata={"signals": "procedure"},
    )
    text = RetrievalHit(
        doc_id="d1", title="Guide", page=1, modality=Modality.TEXT, score=0.4,
        reason="Matched text terms: adapter", snippet="Connect the AC adapter.",
        object_id="d1:procedure:1", object_type="procedure", metadata={"line_start": "3"},
    )

    fused = WeightedScoreFusion().fuse({Modality.LAYOUT: [layout], Modality.TEXT: [text]})

    assert fused[0].snippet == "Connect the AC adapter."
    assert fused[0].metadata == {"line_start": "3"}
    assert fused[0].object_id == "d1:procedure:1"


def _page(doc_id: str, text: str, objects=None):
    from mare.types import Document

    return Document(
        doc_id=doc_id, title=doc_id, page=1, text=text, image_caption="", layout_hints="",
        page_image_path="", objects=objects or [], metadata={},
    )


def test_text_retriever_matches_inflected_forms() -> None:
    from mare.retrievers.text import TextRetriever

    documents = [
        _page("brightness", "Adjust the screen brightness from the screen settings."),
        _page("unlock", "Unlocking the screen."),
    ]
    hits = TextRetriever(documents).retrieve("how do I unlock the screen", top_k=2)

    assert hits[0].doc_id == "unlock"


def test_text_retriever_prefers_rare_terms_over_common_ones() -> None:
    from mare.retrievers.text import TextRetriever

    filler = "The computer manual describes the computer settings for the computer."
    documents = [_page(f"common-{index}", filler) for index in range(6)]
    documents.append(_page("bios", "Enter the BIOS setup screen by pressing F2 on the computer."))
    hits = TextRetriever(documents).retrieve("computer bios", top_k=3)

    assert hits[0].doc_id == "bios"


def test_numbered_section_counts_as_steps() -> None:
    from mare.retrievers.text import _object_bonus, _content_tokens
    from mare.types import DocumentObject, ObjectType

    section = DocumentObject(
        object_id="s1", doc_id="d", page=1, object_type=ObjectType.SECTION,
        content="Employee onboarding 1. Review the checklist. 2. Connect the adapter.",
    )
    _, reasons = _object_bonus(set(_content_tokens("onboarding steps")), section)

    assert "numbered-steps boost" in reasons
