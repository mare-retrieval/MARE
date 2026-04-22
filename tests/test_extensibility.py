from __future__ import annotations

import json
import math
import sys
import types
from pathlib import Path

import mare.ingest as ingest_module
import pytest
from mare import (
    FAISSIndexer,
    FAISSRetriever,
    FastEmbedReranker,
    IdentityReranker,
    KeywordBoostReranker,
    MAREApp,
    PaddleOCRParser,
    QdrantHybridRetriever,
    QdrantIndexer,
    SentenceTransformersRetriever,
    SuryaParser,
)
from mare.extensions import DoclingParser, MAREConfig, UnstructuredParser, get_parser
from mare.retrievers.base import BaseRetriever
from mare.types import Document, DocumentObject, Modality, ObjectType, RetrievalHit


class _CustomParser:
    def ingest(self, pdf_path: Path, output_path: Path) -> Path:
        payload = {
            "source_pdf": str(pdf_path),
            "documents": [
                {
                    "doc_id": "custom-p1",
                    "title": "Custom",
                    "page": 1,
                    "text": "Custom parser output for setup instructions.",
                    "image_caption": "",
                    "layout_hints": "",
                    "page_image_path": "",
                    "objects": [],
                    "metadata": {"source": str(pdf_path)},
                }
            ],
        }
        output_path.write_text(json.dumps(payload))
        return output_path


class _AlwaysTopTextRetriever(BaseRetriever):
    modality = Modality.TEXT

    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievalHit]:
        return [
            RetrievalHit(
                doc_id="override-1",
                title="Override",
                page=9,
                modality=self.modality,
                score=0.99,
                reason=f"Custom retriever handled: {query}",
                snippet="Overridden retrieval result.",
            )
        ][:top_k]


class _ReverseReranker:
    def rerank(self, query: str, hits: list[RetrievalHit], top_k: int = 5) -> list[RetrievalHit]:
        return list(reversed(hits))[:top_k]


def test_custom_parser_can_build_a_corpus(tmp_path: Path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_text("placeholder")
    output_path = tmp_path / "sample.json"

    app = MAREApp.from_pdf(pdf_path=pdf_path, output_path=output_path, parser=_CustomParser())

    assert app.documents[0].doc_id == "custom-p1"
    assert app.documents[0].text.startswith("Custom parser output")


def test_custom_retriever_factory_can_override_default_retrieval() -> None:
    docs = [Document(doc_id="base-1", title="Base", page=1, text="Base document text.")]
    config = MAREConfig(retriever_factories={Modality.TEXT: lambda documents: _AlwaysTopTextRetriever(documents)})

    app = MAREApp.from_documents(docs, config=config)
    best = app.best_match("anything")

    assert best is not None
    assert best.doc_id == "override-1"
    assert "Custom retriever handled" in best.reason


def test_custom_reranker_can_reorder_fused_results() -> None:
    docs = [
        Document(doc_id="1", title="Doc1", page=1, text="adapter instructions and setup"),
        Document(doc_id="2", title="Doc2", page=2, text="adapter instructions and setup"),
    ]
    config = MAREConfig(reranker=_ReverseReranker())

    app = MAREApp.from_documents(docs, config=config)
    results = app.retrieve("adapter instructions", top_k=2)

    assert len(results) == 2
    assert results[0].doc_id == "2"


def test_builtin_parsers_are_discoverable() -> None:
    assert get_parser("builtin") is not None
    assert get_parser("docling") is not None
    assert get_parser("paddleocr") is not None
    assert get_parser("surya") is not None
    assert get_parser("unstructured") is not None


def test_identity_reranker_preserves_order() -> None:
    hits = [
        RetrievalHit(doc_id="1", title="A", page=1, modality=Modality.TEXT, score=0.9, reason="a"),
        RetrievalHit(doc_id="2", title="B", page=2, modality=Modality.TEXT, score=0.8, reason="b"),
    ]
    reranked = IdentityReranker().rerank("adapter", hits, top_k=2)

    assert [hit.doc_id for hit in reranked] == ["1", "2"]


def test_keyword_boost_reranker_prefers_label_overlap() -> None:
    hits = [
        RetrievalHit(
            doc_id="1",
            title="Table",
            page=1,
            modality=Modality.TEXT,
            score=0.6,
            reason="table result",
            snippet="comparison baseline",
            metadata={"label": "Table 2"},
        ),
        RetrievalHit(
            doc_id="2",
            title="Section",
            page=2,
            modality=Modality.TEXT,
            score=0.6,
            reason="plain result",
            snippet="plain text",
        ),
    ]
    reranked = KeywordBoostReranker().rerank("comparison table", hits, top_k=2)

    assert reranked[0].doc_id == "1"


def test_unstructured_parser_builds_mare_corpus_with_fake_module(tmp_path: Path, monkeypatch) -> None:
    class _FakeMetadata:
        def __init__(self, page_number: int) -> None:
            self.page_number = page_number

    class _FakeElement:
        def __init__(self, text: str, category: str, page_number: int) -> None:
            self.text = text
            self.category = category
            self.metadata = _FakeMetadata(page_number)

    def _fake_partition_pdf(filename: str, strategy: str, include_page_breaks: bool):
        assert strategy == "hi_res"
        assert include_page_breaks is True
        return [
            _FakeElement("Wake on LAN feature", "Title", 1),
            _FakeElement("Table 1. Settings matrix", "Table", 1),
            _FakeElement("Architecture diagram", "Image", 2),
        ]

    fake_pdf_module = types.ModuleType("unstructured.partition.pdf")
    fake_pdf_module.partition_pdf = _fake_partition_pdf
    monkeypatch.setitem(sys.modules, "unstructured", types.ModuleType("unstructured"))
    monkeypatch.setitem(sys.modules, "unstructured.partition", types.ModuleType("unstructured.partition"))
    monkeypatch.setitem(sys.modules, "unstructured.partition.pdf", fake_pdf_module)
    monkeypatch.setattr(
        ingest_module,
        "_render_page_images",
        lambda pdf_path, image_dir, scale=1.5: [str(image_dir / "page-1.png"), str(image_dir / "page-2.png")],
    )

    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_text("placeholder")
    output_path = tmp_path / "sample.json"

    parser = UnstructuredParser()
    parser.ingest(pdf_path, output_path)
    payload = json.loads(output_path.read_text())

    assert len(payload["documents"]) == 2
    assert payload["documents"][0]["metadata"]["parser"] == "unstructured"
    assert any(obj["object_type"] == "table" for obj in payload["documents"][0]["objects"])
    assert any(obj["object_type"] == "figure" for obj in payload["documents"][1]["objects"])


def test_docling_parser_builds_mare_corpus_with_fake_module(tmp_path: Path, monkeypatch) -> None:
    class _FakePage:
        def __init__(self, page_no: int, assembled: str) -> None:
            self.page_no = page_no
            self.assembled = assembled

    class _FakeDocument:
        def export_to_markdown(self) -> str:
            return "# Fallback markdown"

    class _FakeResult:
        def __init__(self) -> None:
            self.pages = [
                _FakePage(1, "Wake on LAN feature"),
                _FakePage(2, "Table 1. Settings matrix"),
            ]
            self.document = _FakeDocument()
            self.confidence = 0.91

    class _FakeDocumentConverter:
        def convert(self, source: str):
            assert source.endswith("sample.pdf")
            return _FakeResult()

    fake_docling_converter = types.ModuleType("docling.document_converter")
    fake_docling_converter.DocumentConverter = _FakeDocumentConverter
    monkeypatch.setitem(sys.modules, "docling", types.ModuleType("docling"))
    monkeypatch.setitem(sys.modules, "docling.document_converter", fake_docling_converter)
    monkeypatch.setattr(
        ingest_module,
        "_render_page_images",
        lambda pdf_path, image_dir, scale=1.5: [str(image_dir / "page-1.png"), str(image_dir / "page-2.png")],
    )

    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_text("placeholder")
    output_path = tmp_path / "sample.json"

    parser = DoclingParser()
    parser.ingest(pdf_path, output_path)
    payload = json.loads(output_path.read_text())

    assert len(payload["documents"]) == 2
    assert payload["documents"][0]["metadata"]["parser"] == "docling"
    assert payload["documents"][0]["metadata"]["confidence"] == "0.91"
    assert payload["documents"][1]["text"].startswith("Table 1")


def test_paddleocr_parser_builds_mare_corpus_with_fake_module(tmp_path: Path, monkeypatch) -> None:
    class _FakeOCRResult:
        def __init__(self, texts, boxes, scores) -> None:
            self.res = {
                "rec_texts": texts,
                "rec_boxes": boxes,
                "rec_scores": scores,
            }

    class _FakePaddleOCR:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        def predict(self, image_path: str):
            if image_path.endswith("page-1.png"):
                return [_FakeOCRResult(["Wake on LAN feature", "Table 1 Settings"], [[0, 0, 10, 10], [0, 10, 10, 20]], [0.99, 0.95])]
            return [_FakeOCRResult(["Connect the AC adapter"], [[0, 0, 12, 12]], [0.97])]

    fake_paddleocr = types.ModuleType("paddleocr")
    fake_paddleocr.PaddleOCR = _FakePaddleOCR
    monkeypatch.setitem(sys.modules, "paddleocr", fake_paddleocr)
    monkeypatch.setattr(
        ingest_module,
        "_render_page_images",
        lambda pdf_path, image_dir, scale=1.5: [str(image_dir / "page-1.png"), str(image_dir / "page-2.png")],
    )

    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_text("placeholder")
    output_path = tmp_path / "sample.json"

    parser = PaddleOCRParser(lang="en")
    parser.ingest(pdf_path, output_path)
    payload = json.loads(output_path.read_text())

    assert len(payload["documents"]) == 2
    assert payload["documents"][0]["metadata"]["parser"] == "paddleocr"
    assert "Wake on LAN feature" in payload["documents"][0]["text"]
    assert len(payload["documents"][0]["objects"]) >= 2


def test_surya_parser_builds_mare_corpus_with_fake_module(tmp_path: Path, monkeypatch) -> None:
    class _FakeImage:
        def __init__(self, path: str) -> None:
            self.path = path

    class _FakeImageModule:
        @staticmethod
        def open(path: str):
            return _FakeImage(path)

    class _FakeFoundationPredictor:
        pass

    class _FakeRecognitionPredictor:
        def __init__(self, foundation_predictor) -> None:
            self.foundation_predictor = foundation_predictor

        def __call__(self, images, det_predictor=None):
            image = images[0]
            if image.path.endswith("page-1.png"):
                return [{"text_lines": [{"text": "Wake on LAN feature", "bbox": [0, 0, 10, 10], "confidence": 0.98}]}]
            return [{"text_lines": [{"text": "Connect the AC adapter", "bbox": [0, 0, 11, 11], "confidence": 0.97}]}]

    class _FakeDetectionPredictor:
        pass

    class _FakeLayoutPredictor:
        def __init__(self, foundation_predictor) -> None:
            self.foundation_predictor = foundation_predictor

        def __call__(self, images):
            image = images[0]
            if image.path.endswith("page-1.png"):
                return [{"bboxes": [{"label": "Table", "bbox": [0, 20, 100, 60]}]}]
            return [{"bboxes": [{"label": "Section-header", "bbox": [0, 0, 100, 20]}]}]

    fake_pil = types.ModuleType("PIL")
    fake_pil_image = types.ModuleType("PIL.Image")
    fake_pil_image.open = _FakeImageModule.open
    monkeypatch.setitem(sys.modules, "PIL", fake_pil)
    monkeypatch.setitem(sys.modules, "PIL.Image", fake_pil_image)

    fake_surya_foundation = types.ModuleType("surya.foundation")
    fake_surya_foundation.FoundationPredictor = _FakeFoundationPredictor
    fake_surya_recognition = types.ModuleType("surya.recognition")
    fake_surya_recognition.RecognitionPredictor = _FakeRecognitionPredictor
    fake_surya_detection = types.ModuleType("surya.detection")
    fake_surya_detection.DetectionPredictor = _FakeDetectionPredictor
    fake_surya_layout = types.ModuleType("surya.layout")
    fake_surya_layout.LayoutPredictor = _FakeLayoutPredictor
    monkeypatch.setitem(sys.modules, "surya", types.ModuleType("surya"))
    monkeypatch.setitem(sys.modules, "surya.foundation", fake_surya_foundation)
    monkeypatch.setitem(sys.modules, "surya.recognition", fake_surya_recognition)
    monkeypatch.setitem(sys.modules, "surya.detection", fake_surya_detection)
    monkeypatch.setitem(sys.modules, "surya.layout", fake_surya_layout)
    monkeypatch.setattr(
        ingest_module,
        "_render_page_images",
        lambda pdf_path, image_dir, scale=1.5: [str(image_dir / "page-1.png"), str(image_dir / "page-2.png")],
    )

    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_text("placeholder")
    output_path = tmp_path / "sample.json"

    parser = SuryaParser()
    parser.ingest(pdf_path, output_path)
    payload = json.loads(output_path.read_text())

    assert len(payload["documents"]) == 2
    assert payload["documents"][0]["metadata"]["parser"] == "surya"
    assert "Wake on LAN feature" in payload["documents"][0]["text"]
    assert any(obj["object_type"] == "table" for obj in payload["documents"][0]["objects"])


def test_fastembed_reranker_uses_cross_encoder_scores(monkeypatch) -> None:
    class _FakeCrossEncoder:
        def __init__(self, model_name: str) -> None:
            self.model_name = model_name

        def rerank(self, query: str, documents: list[str]):
            assert query == "comparison table"
            return [0.2, 0.9]

    fake_cross_encoder_module = types.ModuleType("fastembed.rerank.cross_encoder")
    fake_cross_encoder_module.TextCrossEncoder = _FakeCrossEncoder
    monkeypatch.setitem(sys.modules, "fastembed", types.ModuleType("fastembed"))
    monkeypatch.setitem(sys.modules, "fastembed.rerank", types.ModuleType("fastembed.rerank"))
    monkeypatch.setitem(sys.modules, "fastembed.rerank.cross_encoder", fake_cross_encoder_module)

    hits = [
        RetrievalHit(doc_id="1", title="A", page=1, modality=Modality.TEXT, score=0.1, reason="a", snippet="alpha"),
        RetrievalHit(doc_id="2", title="B", page=2, modality=Modality.TEXT, score=0.1, reason="b", snippet="beta"),
    ]

    reranked = FastEmbedReranker().rerank("comparison table", hits, top_k=2)

    assert [hit.doc_id for hit in reranked] == ["2", "1"]
    assert reranked[0].score == 0.9


def test_qdrant_hybrid_retriever_maps_payloads_to_mare_hits(monkeypatch) -> None:
    class _FakeDocument:
        def __init__(self, text: str, model: str) -> None:
            self.text = text
            self.model = model

    class _FakePoint:
        def __init__(self, point_id: str, score: float, payload: dict) -> None:
            self.id = point_id
            self.score = score
            self.payload = payload

    class _FakeResponse:
        def __init__(self, points) -> None:
            self.points = points

    class _FakeClient:
        def query_points(self, **kwargs):
            query = kwargs["query"]
            assert query.text == "wake on lan"
            assert kwargs["collection_name"] == "mare-docs"
            assert kwargs["using"] == "text"
            return _FakeResponse(
                [
                    _FakePoint(
                        "doc-61",
                        0.83,
                        {
                            "doc_id": "doc-61",
                            "title": "Manual",
                            "page": 61,
                            "snippet": "Wake on LAN feature...",
                            "page_image_path": "generated/manual/page-61.png",
                            "object_type": "procedure",
                            "metadata": {"label": "Wake on LAN"},
                        },
                    )
                ]
            )

    fake_models = types.SimpleNamespace(Document=_FakeDocument)
    fake_qdrant = types.ModuleType("qdrant_client")
    fake_qdrant.models = fake_models
    monkeypatch.setitem(sys.modules, "qdrant_client", fake_qdrant)

    retriever = QdrantHybridRetriever(
        [],
        collection_name="mare-docs",
        client=_FakeClient(),
        vector_name="text",
    )
    hits = retriever.retrieve("wake on lan", top_k=1)

    assert len(hits) == 1
    assert hits[0].doc_id == "doc-61"
    assert hits[0].object_type == "procedure"
    assert hits[0].metadata["label"] == "Wake on LAN"


def test_sentence_transformers_retriever_uses_semantic_similarity(monkeypatch) -> None:
    class _FakeSentenceTransformer:
        def __init__(self, model_name: str) -> None:
            self.model_name = model_name

        def encode(self, texts, **kwargs):
            vectors = []
            for text in texts:
                normalized = text.lower()
                if "adapter" in normalized:
                    vectors.append([1.0, 0.0])
                elif "wake on lan" in normalized:
                    vectors.append([0.0, 1.0])
                else:
                    vectors.append([0.5, 0.5])
            return vectors

    fake_st_module = types.ModuleType("sentence_transformers")
    fake_st_module.SentenceTransformer = _FakeSentenceTransformer
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_st_module)

    documents = [
        Document(doc_id="doc-1", title="Manual", page=10, text="Connect the AC adapter to the laptop."),
        Document(doc_id="doc-2", title="Manual", page=61, text="Wake on LAN feature setup instructions."),
    ]

    retriever = SentenceTransformersRetriever(documents)
    hits = retriever.retrieve("how do I connect the adapter", top_k=2)

    assert len(hits) == 1
    assert hits[0].doc_id == "doc-1"
    assert "sentence-transformers semantic match" in hits[0].reason
    assert math.isclose(hits[0].score, 1.0, rel_tol=0.0, abs_tol=1e-6)


def test_sentence_transformers_retriever_surfaces_environment_guidance(monkeypatch) -> None:
    class _BrokenSentenceTransformer:
        def __init__(self, model_name: str) -> None:
            raise RuntimeError("NumPy compatibility issue")

    fake_st_module = types.ModuleType("sentence_transformers")
    fake_st_module.SentenceTransformer = _BrokenSentenceTransformer
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_st_module)

    retriever = SentenceTransformersRetriever(
        [Document(doc_id="doc-1", title="Manual", page=1, text="Connect the adapter.")]
    )

    with pytest.raises(RuntimeError, match="numpy<2"):
        retriever.retrieve("adapter", top_k=1)


def test_sentence_transformers_retriever_preserves_object_and_highlight_enrichment(monkeypatch, tmp_path: Path) -> None:
    class _FakeSentenceTransformer:
        def __init__(self, model_name: str) -> None:
            self.model_name = model_name

        def encode(self, texts, **kwargs):
            return [[1.0, 0.0] for _ in texts]

    fake_st_module = types.ModuleType("sentence_transformers")
    fake_st_module.SentenceTransformer = _FakeSentenceTransformer
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_st_module)

    highlight_path = tmp_path / "highlight.png"
    highlight_path.write_bytes(b"fake")
    monkeypatch.setattr("mare.highlight.render_highlighted_page", lambda **kwargs: str(highlight_path))

    documents = [
        Document(
            doc_id="doc-1",
            title="Manual",
            page=10,
            text="Connect the AC adapter to the laptop.",
            page_image_path=str(tmp_path / "page-10.png"),
            metadata={"source": str(tmp_path / "manual.pdf")},
                objects=[
                    DocumentObject(
                        object_id="doc-1:procedure:1",
                        doc_id="doc-1",
                        page=10,
                        object_type=ObjectType.PROCEDURE,
                        content="Connect the AC adapter to the laptop.",
                        metadata={},
                    )
            ],
        )
    ]

    retriever = SentenceTransformersRetriever(documents)
    hits = retriever.retrieve("how do I connect the adapter", top_k=1)

    assert len(hits) == 1
    assert hits[0].object_type == "procedure"
    assert hits[0].highlight_image_path == str(highlight_path)
    assert "AC adapter" in hits[0].snippet


def test_qdrant_indexer_builds_collection_and_upserts_points(monkeypatch) -> None:
    class _FakeSentenceTransformer:
        def __init__(self, model_name: str) -> None:
            self.model_name = model_name

        def encode(self, texts, **kwargs):
            return [[float(index + 1), float(index + 2)] for index, _ in enumerate(texts)]

    class _FakeVectorParams:
        def __init__(self, size: int, distance) -> None:
            self.size = size
            self.distance = distance

    class _FakePointStruct:
        def __init__(self, id, vector, payload) -> None:
            self.id = id
            self.vector = vector
            self.payload = payload

    class _FakeClient:
        def __init__(self) -> None:
            self.created = None
            self.deleted = []
            self.upserts = []
            self.exists = False

        def collection_exists(self, name: str) -> bool:
            return self.exists

        def delete_collection(self, name: str) -> None:
            self.deleted.append(name)
            self.exists = False

        def create_collection(self, **kwargs) -> None:
            self.created = kwargs
            self.exists = True

        def upsert(self, collection_name: str, points) -> None:
            self.upserts.append((collection_name, points))

    fake_st_module = types.ModuleType("sentence_transformers")
    fake_st_module.SentenceTransformer = _FakeSentenceTransformer
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_st_module)

    fake_models = types.SimpleNamespace(
        VectorParams=_FakeVectorParams,
        PointStruct=_FakePointStruct,
        Distance=types.SimpleNamespace(COSINE="cosine"),
    )
    fake_qdrant = types.ModuleType("qdrant_client")
    fake_qdrant.models = fake_models
    fake_qdrant.QdrantClient = _FakeClient
    monkeypatch.setitem(sys.modules, "qdrant_client", fake_qdrant)

    client = _FakeClient()
    documents = [
        Document(doc_id="doc-1", title="Manual", page=1, text="Connect the AC adapter.", metadata={"section": "power"}),
        Document(doc_id="doc-2", title="Manual", page=2, text="Wake on LAN feature.", metadata={"section": "network"}),
    ]

    indexer = QdrantIndexer(collection_name="mare-docs", client=client, vector_name="text")
    indexed = indexer.index_documents(documents, recreate=True)

    assert indexed == 2
    assert client.created["collection_name"] == "mare-docs"
    assert "text" in client.created["vectors_config"]
    assert len(client.upserts) == 1
    collection_name, points = client.upserts[0]
    assert collection_name == "mare-docs"
    assert len(points) == 2
    assert points[0].id == "doc-1"
    assert points[0].vector == {"text": [1.0, 2.0]}
    assert points[0].payload["metadata"]["section"] == "power"


def test_faiss_indexer_writes_index_and_metadata(monkeypatch, tmp_path: Path) -> None:
    class _FakeSentenceTransformer:
        def __init__(self, model_name: str) -> None:
            self.model_name = model_name

        def encode(self, texts, **kwargs):
            return [[float(index + 1), float(index + 2)] for index, _ in enumerate(texts)]

    class _FakeIndex:
        def __init__(self, dim: int) -> None:
            self.dim = dim
            self.vectors = []

        def add(self, vectors) -> None:
            self.vectors = list(vectors)

    written = {}

    def _write_index(index, path: str) -> None:
        written["path"] = path
        written["vectors"] = index.vectors

    fake_st_module = types.ModuleType("sentence_transformers")
    fake_st_module.SentenceTransformer = _FakeSentenceTransformer
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_st_module)

    fake_faiss = types.ModuleType("faiss")
    fake_faiss.IndexFlatIP = _FakeIndex
    fake_faiss.write_index = _write_index
    monkeypatch.setitem(sys.modules, "faiss", fake_faiss)

    index_path = tmp_path / "manual.faiss"
    metadata_path = tmp_path / "manual.metadata.json"
    documents = [
        Document(doc_id="doc-1", title="Manual", page=1, text="Connect the AC adapter.", metadata={"section": "power"}),
        Document(doc_id="doc-2", title="Manual", page=2, text="Wake on LAN feature.", metadata={"section": "network"}),
    ]

    indexer = FAISSIndexer(index_path=index_path, metadata_path=metadata_path)
    indexed = indexer.index_documents(documents, recreate=True)

    assert indexed == 2
    assert written["path"] == str(index_path)
    assert len(written["vectors"]) == 2
    payload = json.loads(metadata_path.read_text())
    assert payload[0]["doc_id"] == "doc-1"
    assert payload[0]["metadata"]["section"] == "power"


def test_faiss_retriever_loads_saved_index(monkeypatch, tmp_path: Path) -> None:
    class _FakeSentenceTransformer:
        def __init__(self, model_name: str) -> None:
            self.model_name = model_name

        def encode(self, texts, **kwargs):
            vectors = []
            for text in texts:
                normalized = text.lower()
                if "adapter" in normalized:
                    vectors.append([1.0, 0.0])
                else:
                    vectors.append([0.0, 1.0])
            return vectors

    class _FakeIndex:
        def search(self, query_vector, top_k: int):
            return [[0.92]], [[0]]

    fake_st_module = types.ModuleType("sentence_transformers")
    fake_st_module.SentenceTransformer = _FakeSentenceTransformer
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_st_module)

    fake_faiss = types.ModuleType("faiss")
    fake_faiss.read_index = lambda path: _FakeIndex()
    monkeypatch.setitem(sys.modules, "faiss", fake_faiss)

    index_path = tmp_path / "manual.faiss"
    index_path.write_text("placeholder")
    metadata_path = tmp_path / "manual.metadata.json"
    metadata_path.write_text(
        json.dumps(
            [
                {
                    "doc_id": "doc-1",
                    "title": "Manual",
                    "page": 1,
                    "text": "Connect the AC adapter to the computer.",
                    "snippet": "Connect the AC adapter to the computer.",
                    "page_image_path": "generated/manual/page-1.png",
                    "metadata": {"section": "power"},
                }
            ]
        )
    )

    retriever = FAISSRetriever([], index_path=index_path, metadata_path=metadata_path)
    hits = retriever.retrieve("connect the adapter", top_k=1)

    assert len(hits) == 1
    assert hits[0].doc_id == "doc-1"
    assert hits[0].score == 0.92
    assert hits[0].metadata["section"] == "power"
