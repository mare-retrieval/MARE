from mare.engine import MAREngine
from mare.types import Document, DocumentObject, Modality, ObjectType


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
