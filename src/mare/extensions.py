from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol

from mare.ingest import ingest_pdf
from mare.objects import extract_document_objects
from mare.retrievers.base import BaseRetriever
from mare.retrievers.text import TextRetriever
from mare.types import DocumentObject, Modality, ObjectType, RetrievalHit


class DocumentParser(Protocol):
    """Build or update a MARE corpus from a source document."""

    def ingest(self, pdf_path: Path, output_path: Path) -> Path:
        """Return the path to the generated corpus file."""


class ResultReranker(Protocol):
    """Optional second-stage reranker for fused results."""

    def rerank(self, query: str, hits: list[RetrievalHit], top_k: int = 5) -> list[RetrievalHit]:
        """Return reranked hits, usually on a small candidate set."""


RetrieverFactory = Callable[[list], BaseRetriever]


def _to_vector_list(vector) -> list[float]:
    if hasattr(vector, "tolist"):
        values = vector.tolist()
        if isinstance(values, list):
            return [float(item) for item in values]
    return [float(item) for item in vector]


def _cosine_similarity(left, right) -> float:
    left_vec = _to_vector_list(left)
    right_vec = _to_vector_list(right)
    if not left_vec or not right_vec or len(left_vec) != len(right_vec):
        return 0.0
    numerator = sum(a * b for a, b in zip(left_vec, right_vec))
    left_norm = math.sqrt(sum(a * a for a in left_vec))
    right_norm = math.sqrt(sum(b * b for b in right_vec))
    if not left_norm or not right_norm:
        return 0.0
    return numerator / (left_norm * right_norm)


def _encode_with_fallback(model, texts):
    call_variants = [
        {"convert_to_numpy": True, "normalize_embeddings": True},
        {"convert_to_numpy": True},
        {},
    ]
    for kwargs in call_variants:
        try:
            return model.encode(texts, **kwargs)
        except TypeError:
            continue
    return model.encode(texts)


def _document_payload(document) -> dict:
    snippet = (document.text or "")[:240]
    return {
        "doc_id": document.doc_id,
        "title": document.title,
        "page": document.page,
        "text": document.text,
        "snippet": snippet,
        "page_image_path": document.page_image_path,
        "metadata": document.metadata,
    }


@dataclass
class MAREConfig:
    parser: str | DocumentParser | None = None
    retriever_factories: dict[Modality, RetrieverFactory] = field(default_factory=dict)
    reranker: ResultReranker | None = None


class BuiltinPDFParser:
    """Default local parser that uses MARE's built-in PDF ingestion."""

    def ingest(self, pdf_path: Path, output_path: Path) -> Path:
        ingest_pdf(pdf_path=pdf_path, output_path=output_path)
        return output_path


def _build_payload_document(
    *,
    pdf_path: Path,
    title: str,
    page_number: int,
    text: str,
    page_image_path: str,
    objects: list[DocumentObject],
    parser_name: str,
    collection_name: str,
    extra_metadata: dict[str, str] | None = None,
) -> dict:
    normalized_text = text.strip()
    if normalized_text:
        from mare.ingest import _infer_layout_hints, _infer_page_signals, _normalize_text

        text_value = _normalize_text(normalized_text)
        layout_hints = _infer_layout_hints(text_value)
        signals = _infer_page_signals(text_value)
    else:
        text_value = f"[No extractable text found on page {page_number}]"
        layout_hints = ""
        signals = ""

    metadata = {
        "source": str(pdf_path),
        "collection": collection_name,
        "signals": signals,
        "parser": parser_name,
    }
    if extra_metadata:
        metadata.update(extra_metadata)

    return {
        "doc_id": f"{pdf_path.stem.lower().replace(' ', '-')}-p{page_number}",
        "title": title,
        "page": page_number,
        "text": text_value,
        "image_caption": "",
        "layout_hints": layout_hints,
        "page_image_path": page_image_path,
        "objects": [
            {
                "object_id": obj.object_id,
                "doc_id": obj.doc_id,
                "page": obj.page,
                "object_type": obj.object_type.value,
                "content": obj.content,
                "metadata": obj.metadata,
            }
            for obj in objects
        ],
        "metadata": metadata,
    }


def _write_payload(output_path: Path, pdf_path: Path, payload_documents: list[dict]) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps({"source_pdf": str(pdf_path), "documents": payload_documents}, indent=2))
    return output_path


class PaddleOCRParser:
    """OCR-first parser backed by PaddleOCR 3.x pipeline APIs."""

    def __init__(self, lang: str | None = None, device: str | None = None) -> None:
        self.lang = lang
        self.device = device

    def ingest(self, pdf_path: Path, output_path: Path) -> Path:
        try:
            from paddleocr import PaddleOCR
        except ImportError as exc:
            raise RuntimeError(
                "PaddleOCRParser requires `paddleocr`. Install it with "
                "`pip install 'mare-retrieval[paddleocr]'` or `pip install paddleocr`."
            ) from exc

        from mare.ingest import _render_page_images

        output_path.parent.mkdir(parents=True, exist_ok=True)
        page_images = _render_page_images(pdf_path, output_path.with_suffix(""))
        title = pdf_path.stem
        payload_documents: list[dict] = []

        init_kwargs = {
            "use_doc_orientation_classify": False,
            "use_doc_unwarping": False,
            "use_textline_orientation": False,
        }
        if self.lang:
            init_kwargs["lang"] = self.lang
        if self.device:
            init_kwargs["device"] = self.device

        ocr = PaddleOCR(**init_kwargs)

        for page_number, image_path in enumerate(page_images, start=1):
            result = ocr.predict(image_path)
            text, objects = self._extract_page_text_and_objects(
                result=result,
                doc_id=f"{pdf_path.stem.lower().replace(' ', '-')}-p{page_number}",
                page_number=page_number,
            )
            payload_documents.append(
                _build_payload_document(
                    pdf_path=pdf_path,
                    title=title,
                    page_number=page_number,
                    text=text,
                    page_image_path=image_path,
                    objects=objects,
                    parser_name="paddleocr",
                    collection_name="paddleocr-ingest",
                )
            )

        return _write_payload(output_path, pdf_path, payload_documents)

    @staticmethod
    def _extract_page_text_and_objects(result, doc_id: str, page_number: int) -> tuple[str, list[DocumentObject]]:
        page_items = list(result) if isinstance(result, (list, tuple)) else [result]
        lines: list[str] = []
        objects: list[DocumentObject] = []

        for item in page_items:
            text_lines = PaddleOCRParser._extract_text_lines(item)
            for index, line in enumerate(text_lines, start=1):
                normalized = str(line.get("text") or "").strip()
                if not normalized:
                    continue
                lines.append(normalized)
                metadata = {}
                bbox = line.get("bbox")
                confidence = line.get("confidence")
                if bbox is not None:
                    metadata["bbox"] = json.dumps(bbox)
                if confidence is not None:
                    metadata["confidence"] = str(confidence)
                objects.append(
                    DocumentObject(
                        object_id=f"{doc_id}:ocr-line:{index}",
                        doc_id=doc_id,
                        page=page_number,
                        object_type=ObjectType.SECTION,
                        content=normalized,
                        metadata=metadata,
                    )
                )

        return "\n".join(lines), objects

    @staticmethod
    def _extract_text_lines(item) -> list[dict]:
        if hasattr(item, "res"):
            return PaddleOCRParser._extract_text_lines(getattr(item, "res"))
        if hasattr(item, "json"):
            try:
                return PaddleOCRParser._extract_text_lines(item.json())
            except TypeError:
                pass
        if isinstance(item, dict):
            if "rec_texts" in item:
                boxes = item.get("rec_boxes") or item.get("dt_polys") or []
                scores = item.get("rec_scores") or []
                lines = []
                for index, text in enumerate(item.get("rec_texts") or []):
                    lines.append(
                        {
                            "text": text,
                            "bbox": boxes[index] if index < len(boxes) else None,
                            "confidence": scores[index] if index < len(scores) else None,
                        }
                    )
                return lines
            if "texts" in item:
                return [{"text": text} for text in item.get("texts") or []]
            if "text" in item and isinstance(item.get("text"), str):
                return [{"text": item["text"], "bbox": item.get("bbox"), "confidence": item.get("confidence")}]
        if isinstance(item, list):
            lines = []
            for entry in item:
                if isinstance(entry, dict):
                    lines.extend(PaddleOCRParser._extract_text_lines(entry))
                elif isinstance(entry, (list, tuple)) and len(entry) >= 2:
                    maybe_text = entry[1]
                    if isinstance(maybe_text, (list, tuple)) and maybe_text:
                        text = maybe_text[0]
                        confidence = maybe_text[1] if len(maybe_text) > 1 else None
                    else:
                        text = maybe_text
                        confidence = None
                    lines.append({"text": text, "bbox": entry[0], "confidence": confidence})
            return lines
        return []


class SuryaParser:
    """OCR/layout parser backed by Surya's Python predictors."""

    def ingest(self, pdf_path: Path, output_path: Path) -> Path:
        try:
            from PIL import Image
            from surya.detection import DetectionPredictor
            from surya.foundation import FoundationPredictor
            from surya.layout import LayoutPredictor
            from surya.recognition import RecognitionPredictor
        except ImportError as exc:
            raise RuntimeError(
                "SuryaParser requires `surya-ocr` and Pillow. Install it with "
                "`pip install 'mare-retrieval[surya]'` or `pip install surya-ocr pillow`."
            ) from exc

        from mare.ingest import _render_page_images

        output_path.parent.mkdir(parents=True, exist_ok=True)
        page_images = _render_page_images(pdf_path, output_path.with_suffix(""))
        title = pdf_path.stem
        payload_documents: list[dict] = []

        foundation_predictor = FoundationPredictor()
        recognition_predictor = RecognitionPredictor(foundation_predictor)
        detection_predictor = DetectionPredictor()
        layout_predictor = LayoutPredictor(foundation_predictor)

        for page_number, image_path in enumerate(page_images, start=1):
            image = Image.open(image_path)
            recognition_predictions = recognition_predictor([image], det_predictor=detection_predictor)
            layout_predictions = layout_predictor([image])
            text, objects = self._extract_page_text_and_objects(
                recognition_predictions=recognition_predictions,
                layout_predictions=layout_predictions,
                doc_id=f"{pdf_path.stem.lower().replace(' ', '-')}-p{page_number}",
                page_number=page_number,
            )
            payload_documents.append(
                _build_payload_document(
                    pdf_path=pdf_path,
                    title=title,
                    page_number=page_number,
                    text=text,
                    page_image_path=image_path,
                    objects=objects,
                    parser_name="surya",
                    collection_name="surya-ingest",
                )
            )

        return _write_payload(output_path, pdf_path, payload_documents)

    @staticmethod
    def _extract_page_text_and_objects(recognition_predictions, layout_predictions, doc_id: str, page_number: int):
        lines: list[str] = []
        objects: list[DocumentObject] = []

        for prediction in recognition_predictions or []:
            for index, line in enumerate(SuryaParser._extract_text_lines(prediction), start=1):
                text = str(line.get("text") or "").strip()
                if not text:
                    continue
                lines.append(text)
                metadata = {}
                bbox = line.get("bbox")
                confidence = line.get("confidence")
                if bbox is not None:
                    metadata["bbox"] = json.dumps(bbox)
                if confidence is not None:
                    metadata["confidence"] = str(confidence)
                objects.append(
                    DocumentObject(
                        object_id=f"{doc_id}:ocr-line:{index}",
                        doc_id=doc_id,
                        page=page_number,
                        object_type=ObjectType.SECTION,
                        content=text,
                        metadata=metadata,
                    )
                )

        layout_index = len(objects)
        for prediction in layout_predictions or []:
            for entry in SuryaParser._extract_layout_entries(prediction):
                label = str(entry.get("label") or "").strip()
                bbox = entry.get("bbox")
                object_type = SuryaParser._map_layout_label(label)
                if object_type is None:
                    continue
                metadata = {"label": label}
                if bbox is not None:
                    metadata["region_hint"] = json.dumps(bbox)
                    metadata["bbox"] = json.dumps(bbox)
                top_k = entry.get("top_k")
                if top_k:
                    metadata["top_k"] = json.dumps(top_k)
                layout_index += 1
                objects.append(
                    DocumentObject(
                        object_id=f"{doc_id}:layout:{layout_index}",
                        doc_id=doc_id,
                        page=page_number,
                        object_type=object_type,
                        content=label or object_type.value,
                        metadata=metadata,
                    )
                )

        return "\n".join(lines), objects

    @staticmethod
    def _extract_text_lines(prediction) -> list[dict]:
        if isinstance(prediction, dict):
            if "text_lines" in prediction:
                return list(prediction.get("text_lines") or [])
            if "lines" in prediction:
                return list(prediction.get("lines") or [])
        text_lines = getattr(prediction, "text_lines", None)
        if text_lines is not None:
            return [SuryaParser._to_line_dict(line) for line in text_lines]
        lines = getattr(prediction, "lines", None)
        if lines is not None:
            return [SuryaParser._to_line_dict(line) for line in lines]
        return []

    @staticmethod
    def _to_line_dict(line) -> dict:
        if isinstance(line, dict):
            return line
        return {
            "text": getattr(line, "text", ""),
            "bbox": getattr(line, "bbox", None),
            "confidence": getattr(line, "confidence", None),
        }

    @staticmethod
    def _extract_layout_entries(prediction) -> list[dict]:
        if isinstance(prediction, dict):
            if "bboxes" in prediction:
                return list(prediction.get("bboxes") or [])
            if "boxes" in prediction:
                return list(prediction.get("boxes") or [])
        bboxes = getattr(prediction, "bboxes", None)
        if bboxes is not None:
            return [SuryaParser._to_layout_dict(item) for item in bboxes]
        boxes = getattr(prediction, "boxes", None)
        if boxes is not None:
            return [SuryaParser._to_layout_dict(item) for item in boxes]
        return []

    @staticmethod
    def _to_layout_dict(item) -> dict:
        if isinstance(item, dict):
            return item
        return {
            "label": getattr(item, "label", None),
            "bbox": getattr(item, "bbox", None),
            "top_k": getattr(item, "top_k", None),
        }

    @staticmethod
    def _map_layout_label(label: str) -> ObjectType | None:
        normalized = label.lower()
        if "table" in normalized or "form" in normalized:
            return ObjectType.TABLE
        if "figure" in normalized or "picture" in normalized or "caption" in normalized or "image" in normalized:
            return ObjectType.FIGURE
        if "section" in normalized or "header" in normalized or "text" in normalized:
            return ObjectType.SECTION
        return None


class SentenceTransformersRetriever(BaseRetriever):
    """Semantic retriever backed by `sentence-transformers`."""

    modality = Modality.TEXT

    def __init__(self, documents: list, model_name: str = "sentence-transformers/all-MiniLM-L6-v2", model=None) -> None:
        super().__init__(documents)
        self.model_name = model_name
        self.model = model
        self._doc_embeddings = None

    def _get_model(self):
        if self.model is not None:
            return self.model
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "SentenceTransformersRetriever requires `sentence-transformers`. Install it with "
                "`pip install 'mare-retrieval[sentence-transformers]'` or `pip install sentence-transformers`."
            ) from exc
        try:
            self.model = SentenceTransformer(self.model_name)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                "SentenceTransformersRetriever could not initialize the sentence-transformers stack. "
                "A common cause is an incompatible NumPy / torch environment after installing heavier extras "
                "such as Docling. On this setup, the safest fix is usually to keep `numpy<2` and use a compatible "
                "torch stack such as `torch==2.2.2`, `transformers==4.49.0`, and `sentence-transformers==3.4.1`."
            ) from exc
        return self.model

    def _get_doc_embeddings(self):
        if self._doc_embeddings is not None:
            return self._doc_embeddings
        model = self._get_model()
        texts = [document.text or document.title for document in self.documents]
        self._doc_embeddings = list(_encode_with_fallback(model, texts))
        return self._doc_embeddings

    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievalHit]:
        from mare.highlight import render_highlighted_page, render_object_region_highlight
        from mare.retrievers.text import _best_object, _best_snippet, _content_tokens

        model = self._get_model()
        query_embedding = list(_encode_with_fallback(model, [query]))[0]
        query_tokens = _content_tokens(query)
        hits: list[RetrievalHit] = []

        for document, embedding in zip(self.documents, self._get_doc_embeddings()):
            score = round(_cosine_similarity(query_embedding, embedding), 4)
            if score <= 0:
                continue
            best_object, _, _, _ = _best_object(query_tokens, document.objects)
            snippet = best_object.content if best_object else _best_snippet(document.text or document.title, query)
            hit_metadata = dict(document.metadata)
            if best_object:
                hit_metadata.update(best_object.metadata)
            hits.append(
                RetrievalHit(
                    doc_id=document.doc_id,
                    title=document.title,
                    page=document.page,
                    modality=self.modality,
                    score=score,
                    reason=f"sentence-transformers semantic match via {self.model_name}",
                    snippet=snippet,
                    page_image_path=document.page_image_path,
                    object_id=best_object.object_id if best_object else "",
                    object_type=best_object.object_type.value if best_object else "",
                    metadata=hit_metadata,
                )
            )

        top_hits = sorted(hits, key=lambda hit: hit.score, reverse=True)[:top_k]
        for hit in top_hits:
            source_pdf = hit.metadata.get("source", "")
            if source_pdf and hit.page_image_path and hit.snippet:
                hit.highlight_image_path = render_highlighted_page(
                    pdf_path=source_pdf,
                    page_number=hit.page,
                    page_image_path=hit.page_image_path,
                    query=query,
                    snippet=hit.snippet,
                )
            if not hit.highlight_image_path and hit.page_image_path and hit.object_type in {"table", "figure", "section"}:
                hit.highlight_image_path = render_object_region_highlight(
                    page_image_path=hit.page_image_path,
                    page_number=hit.page,
                    object_type=hit.object_type,
                    metadata=hit.metadata,
                )

        return top_hits


class HybridSemanticRetriever(BaseRetriever):
    """Hybrid retriever that preserves MARE's lexical/object-aware behavior and adds semantic lift."""

    modality = Modality.TEXT

    def __init__(
        self,
        documents: list,
        *,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        lexical_weight: float = 0.7,
        semantic_weight: float = 0.3,
        semantic_retriever: SentenceTransformersRetriever | None = None,
        lexical_retriever: TextRetriever | None = None,
    ) -> None:
        super().__init__(documents)
        self.lexical_weight = lexical_weight
        self.semantic_weight = semantic_weight
        self.semantic_retriever = semantic_retriever or SentenceTransformersRetriever(documents, model_name=model_name)
        self.lexical_retriever = lexical_retriever or TextRetriever(documents)

    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievalHit]:
        lexical_hits = self.lexical_retriever.retrieve(query=query, top_k=max(top_k * 2, top_k))
        semantic_hits = self.semantic_retriever.retrieve(query=query, top_k=max(top_k * 2, top_k))

        lexical_by_doc = {hit.doc_id: hit for hit in lexical_hits}
        semantic_by_doc = {hit.doc_id: hit for hit in semantic_hits}
        doc_ids = list(dict.fromkeys([hit.doc_id for hit in lexical_hits + semantic_hits]))

        lexical_max = max((hit.score for hit in lexical_hits), default=1.0) or 1.0
        semantic_max = max((hit.score for hit in semantic_hits), default=1.0) or 1.0

        merged: list[RetrievalHit] = []
        for doc_id in doc_ids:
            lexical_hit = lexical_by_doc.get(doc_id)
            semantic_hit = semantic_by_doc.get(doc_id)
            if not lexical_hit and not semantic_hit:
                continue

            lexical_norm = (lexical_hit.score / lexical_max) if lexical_hit else 0.0
            semantic_norm = (semantic_hit.score / semantic_max) if semantic_hit else 0.0
            hybrid_score = round((self.lexical_weight * lexical_norm) + (self.semantic_weight * semantic_norm), 4)

            primary = lexical_hit or semantic_hit
            reason_parts: list[str] = []
            if lexical_hit:
                reason_parts.append(f"lexical:{lexical_hit.reason}")
            if semantic_hit:
                reason_parts.append(f"semantic:{semantic_hit.reason}")

            merged.append(
                RetrievalHit(
                    doc_id=primary.doc_id,
                    title=primary.title,
                    page=primary.page,
                    modality=self.modality,
                    score=hybrid_score,
                    reason=" | ".join(reason_parts),
                    snippet=lexical_hit.snippet if lexical_hit and lexical_hit.snippet else primary.snippet,
                    page_image_path=primary.page_image_path,
                    highlight_image_path=lexical_hit.highlight_image_path if lexical_hit else primary.highlight_image_path,
                    object_id=lexical_hit.object_id if lexical_hit else primary.object_id,
                    object_type=lexical_hit.object_type if lexical_hit else primary.object_type,
                    metadata=dict((lexical_hit or primary).metadata),
                )
            )

        return sorted(merged, key=lambda hit: hit.score, reverse=True)[:top_k]


class FAISSRetriever(BaseRetriever):
    """Local vector retriever backed by FAISS."""

    modality = Modality.TEXT

    def __init__(
        self,
        documents: list,
        *,
        index_path: str | Path | None = None,
        metadata_path: str | Path | None = None,
        embedder=None,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    ) -> None:
        super().__init__(documents)
        self.index_path = Path(index_path) if index_path is not None else None
        self.metadata_path = Path(metadata_path) if metadata_path is not None else None
        self.embedder = embedder
        self.model_name = model_name
        self._index = None
        self._payloads = None

    def _get_faiss(self):
        try:
            import faiss
        except ImportError as exc:
            raise RuntimeError(
                "FAISSRetriever requires `faiss-cpu`. Install it with "
                "`pip install 'mare-retrieval[faiss]'` or `pip install faiss-cpu`."
            ) from exc
        return faiss

    def _get_embedder(self):
        if self.embedder is not None:
            return self.embedder
        retriever = SentenceTransformersRetriever([], model_name=self.model_name)
        model = retriever._get_model()
        return lambda texts: list(_encode_with_fallback(model, texts))

    @staticmethod
    def _vector_matrix(vectors):
        try:
            import numpy as np
        except ImportError:
            return [_to_vector_list(vector) for vector in vectors]
        return np.array([_to_vector_list(vector) for vector in vectors], dtype="float32")

    def _build_in_memory_index(self):
        if not self.documents:
            return None, []
        faiss = self._get_faiss()
        embedder = self._get_embedder()
        texts = [document.text or document.title for document in self.documents]
        vectors = list(embedder(texts))
        first_vector = _to_vector_list(vectors[0])
        index = faiss.IndexFlatIP(len(first_vector))
        index.add(self._vector_matrix(vectors))
        payloads = [_document_payload(document) for document in self.documents]
        return index, payloads

    def _load_index_and_payloads(self):
        if self._index is not None and self._payloads is not None:
            return self._index, self._payloads

        if self.index_path and self.index_path.exists():
            faiss = self._get_faiss()
            self._index = faiss.read_index(str(self.index_path))
            if self.metadata_path is None:
                self.metadata_path = self.index_path.with_suffix(".metadata.json")
            if self.metadata_path.exists():
                self._payloads = json.loads(self.metadata_path.read_text())
            else:
                self._payloads = []
            return self._index, self._payloads

        self._index, self._payloads = self._build_in_memory_index()
        return self._index, self._payloads

    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievalHit]:
        from mare.retrievers.text import _best_snippet

        index, payloads = self._load_index_and_payloads()
        if index is None:
            return []

        embedder = self._get_embedder()
        query_vector = self._vector_matrix(list(embedder([query])))
        scores, indices = index.search(query_vector, top_k)

        hits: list[RetrievalHit] = []
        row_scores = list(scores[0]) if len(scores) else []
        row_indices = list(indices[0]) if len(indices) else []
        for score, hit_index in zip(row_scores, row_indices):
            if hit_index < 0 or hit_index >= len(payloads):
                continue
            payload = payloads[hit_index]
            snippet_source = str(payload.get("snippet") or payload.get("text") or "")
            hits.append(
                RetrievalHit(
                    doc_id=str(payload.get("doc_id") or hit_index),
                    title=str(payload.get("title") or payload.get("doc_id") or "FAISS result"),
                    page=int(payload.get("page") or 0),
                    modality=self.modality,
                    score=round(float(score), 4),
                    reason=f"FAISS semantic match via {self.model_name}",
                    snippet=_best_snippet(snippet_source, query),
                    page_image_path=str(payload.get("page_image_path") or ""),
                    metadata=dict(payload.get("metadata") or {}),
                )
            )

        return hits


class DoclingParser:
    """Parser adapter backed by Docling's document conversion pipeline."""

    def ingest(self, pdf_path: Path, output_path: Path) -> Path:
        try:
            from docling.document_converter import DocumentConverter
        except ImportError as exc:
            raise RuntimeError(
                "DoclingParser requires Docling. Install it with "
                "`pip install 'mare-retrieval[docling]'` or `pip install docling`."
            ) from exc

        from mare.ingest import _infer_layout_hints, _infer_page_signals, _normalize_text, _render_page_images

        output_path.parent.mkdir(parents=True, exist_ok=True)
        page_images = _render_page_images(pdf_path, output_path.with_suffix(""))
        converter = DocumentConverter()
        result = converter.convert(str(pdf_path))
        page_entries = self._extract_page_entries(result)

        payload_documents = []
        max_page = max(len(page_images), max((page_no for page_no, _ in page_entries), default=0))
        for page_number in range(1, max_page + 1):
            raw_text = next((text for page_no, text in page_entries if page_no == page_number), "").strip()
            text = _normalize_text(raw_text) if raw_text else f"[No extractable text found on page {page_number}]"
            doc_id = f"{pdf_path.stem.lower().replace(' ', '-')}-p{page_number}"
            objects = extract_document_objects(raw_text or text, doc_id, page_number)

            metadata = {
                "source": str(pdf_path),
                "collection": "docling-ingest",
                "signals": _infer_page_signals(text),
                "parser": "docling",
            }
            confidence = getattr(result, "confidence", None)
            if confidence is not None:
                metadata["confidence"] = str(confidence)

            payload_documents.append(
                {
                    "doc_id": doc_id,
                    "title": pdf_path.stem,
                    "page": page_number,
                    "text": text,
                    "image_caption": "",
                    "layout_hints": _infer_layout_hints(text),
                    "page_image_path": page_images[page_number - 1] if page_number - 1 < len(page_images) else "",
                    "objects": [
                        {
                            "object_id": obj.object_id,
                            "doc_id": obj.doc_id,
                            "page": obj.page,
                            "object_type": obj.object_type.value,
                            "content": obj.content,
                            "metadata": obj.metadata,
                        }
                        for obj in objects
                    ],
                    "metadata": metadata,
                }
            )

        output_path.write_text(json.dumps({"source_pdf": str(pdf_path), "documents": payload_documents}, indent=2))
        return output_path

    @staticmethod
    def _extract_page_entries(result) -> list[tuple[int, str]]:
        pages = getattr(result, "pages", None) or []
        extracted: list[tuple[int, str]] = []

        for index, page in enumerate(pages, start=1):
            page_no = getattr(page, "page_no", None) or getattr(page, "page_number", None) or index
            page_text = ""
            for candidate in ("assembled", "text", "content", "markdown"):
                value = getattr(page, candidate, None)
                if isinstance(value, str) and value.strip():
                    page_text = value
                    break
            if not page_text and isinstance(page, dict):
                for candidate in ("assembled", "text", "content", "markdown"):
                    value = page.get(candidate)
                    if isinstance(value, str) and value.strip():
                        page_text = value
                        break
                page_no = int(page.get("page_no") or page.get("page_number") or page_no)
            if page_text:
                extracted.append((int(page_no), page_text))

        if extracted:
            return extracted

        document = getattr(result, "document", None)
        if document is not None:
            export_markdown = getattr(document, "export_to_markdown", None)
            if callable(export_markdown):
                markdown = export_markdown()
                if markdown and markdown.strip():
                    return [(1, markdown)]

        return []


class UnstructuredParser:
    """Parser adapter backed by Unstructured's PDF partitioning pipeline."""

    def __init__(self, strategy: str = "hi_res") -> None:
        self.strategy = strategy

    def ingest(self, pdf_path: Path, output_path: Path) -> Path:
        try:
            from unstructured.partition.pdf import partition_pdf
        except ImportError as exc:
            raise RuntimeError(
                "UnstructuredParser requires `unstructured[pdf]`. Install it with "
                "`pip install 'mare-retrieval[unstructured]'` or `pip install 'unstructured[pdf]'`."
            ) from exc

        from mare.ingest import _infer_layout_hints, _infer_page_signals, _normalize_text, _render_page_images

        output_path.parent.mkdir(parents=True, exist_ok=True)
        page_images = _render_page_images(pdf_path, output_path.with_suffix(""))
        elements = partition_pdf(filename=str(pdf_path), strategy=self.strategy, include_page_breaks=True)

        pages: dict[int, dict[str, object]] = {}

        for element in elements:
            metadata = getattr(element, "metadata", None)
            if metadata is None:
                page_number = 1
            elif isinstance(metadata, dict):
                page_number = int(metadata.get("page_number", 1) or 1)
            else:
                page_number = int(getattr(metadata, "page_number", 1) or 1)

            page_entry = pages.setdefault(page_number, {"lines": [], "objects": []})
            text = _normalize_text(getattr(element, "text", "") or "")
            if text:
                page_entry["lines"].append(text)

            category = getattr(element, "category", element.__class__.__name__)
            object_type = self._map_category_to_object_type(category)
            if object_type is None or not text:
                continue

            page_entry["objects"].append(
                DocumentObject(
                    object_id=f"{pdf_path.stem.lower().replace(' ', '-')}-{page_number}:{object_type.value}:{len(page_entry['objects']) + 1}",
                    doc_id=f"{pdf_path.stem.lower().replace(' ', '-')}-p{page_number}",
                    page=page_number,
                    object_type=object_type,
                    content=text,
                    metadata={"label": category, "source": "unstructured"},
                )
            )

        payload_documents = []
        max_page = max(len(page_images), max(pages.keys(), default=0))
        for page_number in range(1, max_page + 1):
            page_entry = pages.get(page_number, {"lines": [], "objects": []})
            raw_text = "\n".join(page_entry["lines"]).strip()
            text = _normalize_text(raw_text) if raw_text else f"[No extractable text found on page {page_number}]"
            doc_id = f"{pdf_path.stem.lower().replace(' ', '-')}-p{page_number}"
            objects = extract_document_objects(raw_text or text, doc_id, page_number)
            objects.extend(page_entry["objects"])

            payload_documents.append(
                {
                    "doc_id": doc_id,
                    "title": pdf_path.stem,
                    "page": page_number,
                    "text": text,
                    "image_caption": "",
                    "layout_hints": _infer_layout_hints(text),
                    "page_image_path": page_images[page_number - 1] if page_number - 1 < len(page_images) else "",
                    "objects": [
                        {
                            "object_id": obj.object_id,
                            "doc_id": obj.doc_id,
                            "page": obj.page,
                            "object_type": obj.object_type.value,
                            "content": obj.content,
                            "metadata": obj.metadata,
                        }
                        for obj in objects
                    ],
                    "metadata": {
                        "source": str(pdf_path),
                        "collection": "unstructured-ingest",
                        "signals": _infer_page_signals(text),
                        "parser": "unstructured",
                    },
                }
            )

        output_path.write_text(json.dumps({"source_pdf": str(pdf_path), "documents": payload_documents}, indent=2))
        return output_path

    @staticmethod
    def _map_category_to_object_type(category: str) -> ObjectType | None:
        normalized = category.lower()
        if "table" in normalized:
            return ObjectType.TABLE
        if "image" in normalized or "figure" in normalized or "picture" in normalized:
            return ObjectType.FIGURE
        if "title" in normalized or "header" in normalized:
            return ObjectType.SECTION
        return None


class IdentityReranker:
    """No-op reranker useful as a baseline or composition default."""

    def rerank(self, query: str, hits: list[RetrievalHit], top_k: int = 5) -> list[RetrievalHit]:
        return hits[:top_k]


class KeywordBoostReranker:
    """Small built-in reranker that rewards exact term overlap and metadata labels."""

    def rerank(self, query: str, hits: list[RetrievalHit], top_k: int = 5) -> list[RetrievalHit]:
        query_terms = set(query.lower().split())
        rescored: list[tuple[float, RetrievalHit]] = []
        for hit in hits:
            label_terms = set(str(hit.metadata.get("label", "")).lower().split())
            text_terms = set((hit.snippet or hit.reason or "").lower().split())
            overlap = len(query_terms & (label_terms | text_terms))
            rescored.append((hit.score + (0.03 * overlap), hit))

        rescored.sort(key=lambda item: item[0], reverse=True)
        reranked: list[RetrievalHit] = []
        for score, hit in rescored[:top_k]:
            hit.score = round(score, 4)
            reranked.append(hit)
        return reranked


class FastEmbedReranker:
    """Reranker backed by FastEmbed cross-encoders.

    Based on Qdrant/FastEmbed's documented `TextCrossEncoder` usage.
    """

    def __init__(self, model_name: str = "jinaai/jina-reranker-v2-base-multilingual") -> None:
        self.model_name = model_name
        self._model = None

    def _get_model(self):
        if self._model is None:
            try:
                from fastembed.rerank.cross_encoder import TextCrossEncoder
            except ImportError as exc:
                raise RuntimeError(
                    "FastEmbedReranker requires FastEmbed. Install it with "
                    "`pip install 'mare-retrieval[fastembed]'` or `pip install fastembed`."
                ) from exc
            self._model = TextCrossEncoder(model_name=self.model_name)
        return self._model

    def rerank(self, query: str, hits: list[RetrievalHit], top_k: int = 5) -> list[RetrievalHit]:
        if not hits:
            return []

        model = self._get_model()
        documents = [hit.snippet or hit.reason or hit.title for hit in hits]
        scores = list(model.rerank(query, documents))

        rescored: list[tuple[float, RetrievalHit]] = []
        for hit, rerank_score in zip(hits, scores):
            combined_score = float(rerank_score)
            hit.score = round(combined_score, 4)
            rescored.append((combined_score, hit))

        rescored.sort(key=lambda item: item[0], reverse=True)
        return [hit for _, hit in rescored[:top_k]]


class QdrantHybridRetriever(BaseRetriever):
    """Retriever backed by Qdrant query APIs.

    This is intended for developers who already have a Qdrant collection with
    payload fields compatible with MARE's result shape.
    """

    modality = Modality.TEXT

    def __init__(
        self,
        documents: list,
        *,
        collection_name: str,
        client=None,
        url: str | None = None,
        api_key: str | None = None,
        location: str | None = None,
        vector_name: str | None = None,
        embedding_model: str = "BAAI/bge-small-en-v1.5",
        payload_text_key: str = "text",
    ) -> None:
        super().__init__(documents)
        self.collection_name = collection_name
        self.client = client
        self.url = url
        self.api_key = api_key
        self.location = location
        self.vector_name = vector_name
        self.embedding_model = embedding_model
        self.payload_text_key = payload_text_key

    def _get_client(self):
        if self.client is not None:
            return self.client
        try:
            from qdrant_client import QdrantClient
        except ImportError as exc:
            raise RuntimeError(
                "QdrantHybridRetriever requires `qdrant-client`. Install it with "
                "`pip install 'mare-retrieval[integrations]'` or `pip install qdrant-client[fastembed]`."
            ) from exc
        self.client = QdrantClient(url=self.url, api_key=self.api_key, location=self.location)
        return self.client

    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievalHit]:
        client = self._get_client()
        try:
            from qdrant_client import models
        except ImportError as exc:
            raise RuntimeError(
                "QdrantHybridRetriever requires `qdrant-client`. Install it with "
                "`pip install 'mare-retrieval[integrations]'` or `pip install qdrant-client[fastembed]`."
            ) from exc

        query_document = models.Document(text=query, model=self.embedding_model)
        query_kwargs = {
            "collection_name": self.collection_name,
            "query": query_document,
            "with_payload": True,
            "limit": top_k,
        }
        if self.vector_name:
            query_kwargs["using"] = self.vector_name

        response = client.query_points(**query_kwargs)
        points = getattr(response, "points", response)

        hits: list[RetrievalHit] = []
        for point in points:
            payload = getattr(point, "payload", {}) or {}
            snippet = str(payload.get("snippet") or payload.get(self.payload_text_key) or "")
            title = str(payload.get("title") or payload.get("doc_id") or "Qdrant result")
            metadata = dict(payload.get("metadata") or {})
            if payload.get("label") and "label" not in metadata:
                metadata["label"] = str(payload["label"])

            hits.append(
                RetrievalHit(
                    doc_id=str(payload.get("doc_id") or getattr(point, "id", "")),
                    title=title,
                    page=int(payload.get("page") or 0),
                    modality=self.modality,
                    score=round(float(getattr(point, "score", 0.0)), 4),
                    reason=str(payload.get("reason") or f"Qdrant hit from collection '{self.collection_name}'"),
                    snippet=snippet,
                    page_image_path=str(payload.get("page_image_path") or ""),
                    highlight_image_path=str(payload.get("highlight_image_path") or ""),
                    object_id=str(payload.get("object_id") or ""),
                    object_type=str(payload.get("object_type") or ""),
                    metadata=metadata,
                )
            )

        return hits


class QdrantIndexer:
    """Helper for indexing MARE documents into Qdrant."""

    def __init__(
        self,
        collection_name: str,
        *,
        client=None,
        url: str | None = None,
        api_key: str | None = None,
        location: str | None = None,
        vector_name: str | None = "text",
        embedder=None,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    ) -> None:
        self.collection_name = collection_name
        self.client = client
        self.url = url
        self.api_key = api_key
        self.location = location
        self.vector_name = vector_name
        self.embedder = embedder
        self.model_name = model_name

    def _get_client_and_models(self):
        try:
            from qdrant_client import QdrantClient, models
        except ImportError as exc:
            raise RuntimeError(
                "QdrantIndexer requires `qdrant-client`. Install it with "
                "`pip install 'mare-retrieval[integrations]'` or `pip install qdrant-client[fastembed]`."
            ) from exc
        if self.client is None:
            self.client = QdrantClient(url=self.url, api_key=self.api_key, location=self.location)
        return self.client, models

    def _get_embedder(self):
        if self.embedder is not None:
            return self.embedder
        retriever = SentenceTransformersRetriever([], model_name=self.model_name)
        model = retriever._get_model()
        return lambda texts: list(_encode_with_fallback(model, texts))

    def _payload_for_document(self, document) -> dict:
        return _document_payload(document)

    def index_documents(self, documents: list, recreate: bool = False) -> int:
        if not documents:
            return 0

        client, models = self._get_client_and_models()
        embedder = self._get_embedder()
        texts = [document.text or document.title for document in documents]
        vectors = list(embedder(texts))
        first_vector = _to_vector_list(vectors[0])
        vector_size = len(first_vector)

        vector_config = models.VectorParams(size=vector_size, distance=models.Distance.COSINE)
        collection_exists = getattr(client, "collection_exists", None)
        exists = collection_exists(self.collection_name) if callable(collection_exists) else False

        if recreate and hasattr(client, "delete_collection") and exists:
            client.delete_collection(self.collection_name)
            exists = False

        if not exists:
            create_kwargs = {"collection_name": self.collection_name}
            if self.vector_name:
                create_kwargs["vectors_config"] = {self.vector_name: vector_config}
            else:
                create_kwargs["vectors_config"] = vector_config
            client.create_collection(**create_kwargs)

        points = []
        for index, (document, vector) in enumerate(zip(documents, vectors), start=1):
            payload = self._payload_for_document(document)
            point_id = document.doc_id or str(index)
            vector_payload = _to_vector_list(vector)
            if self.vector_name:
                vector_payload = {self.vector_name: vector_payload}
            points.append(models.PointStruct(id=point_id, vector=vector_payload, payload=payload))

        client.upsert(collection_name=self.collection_name, points=points)
        return len(points)


class FAISSIndexer:
    """Helper for indexing MARE documents into a local FAISS index."""

    def __init__(
        self,
        index_path: str | Path,
        *,
        metadata_path: str | Path | None = None,
        embedder=None,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    ) -> None:
        self.index_path = Path(index_path)
        self.metadata_path = Path(metadata_path) if metadata_path is not None else self.index_path.with_suffix(".metadata.json")
        self.embedder = embedder
        self.model_name = model_name

    def _get_faiss(self):
        try:
            import faiss
        except ImportError as exc:
            raise RuntimeError(
                "FAISSIndexer requires `faiss-cpu`. Install it with "
                "`pip install 'mare-retrieval[faiss]'` or `pip install faiss-cpu`."
            ) from exc
        return faiss

    def _get_embedder(self):
        if self.embedder is not None:
            return self.embedder
        retriever = SentenceTransformersRetriever([], model_name=self.model_name)
        model = retriever._get_model()
        return lambda texts: list(_encode_with_fallback(model, texts))

    @staticmethod
    def _vector_matrix(vectors):
        try:
            import numpy as np
        except ImportError:
            return [_to_vector_list(vector) for vector in vectors]
        return np.array([_to_vector_list(vector) for vector in vectors], dtype="float32")

    def index_documents(self, documents: list, recreate: bool = False) -> int:
        if not documents:
            return 0

        faiss = self._get_faiss()
        embedder = self._get_embedder()
        texts = [document.text or document.title for document in documents]
        vectors = list(embedder(texts))
        first_vector = _to_vector_list(vectors[0])

        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.metadata_path.parent.mkdir(parents=True, exist_ok=True)

        if self.index_path.exists() and recreate:
            self.index_path.unlink()
        if self.metadata_path.exists() and recreate:
            self.metadata_path.unlink()

        index = faiss.IndexFlatIP(len(first_vector))
        index.add(self._vector_matrix(vectors))
        faiss.write_index(index, str(self.index_path))

        payloads = [_document_payload(document) for document in documents]
        self.metadata_path.write_text(json.dumps(payloads, indent=2))
        return len(payloads)


_PARSER_REGISTRY: dict[str, DocumentParser] = {
    "builtin": BuiltinPDFParser(),
    "docling": DoclingParser(),
    "paddleocr": PaddleOCRParser(),
    "surya": SuryaParser(),
    "unstructured": UnstructuredParser(),
}


def register_parser(name: str, parser: DocumentParser) -> None:
    _PARSER_REGISTRY[name] = parser


def get_parser(name: str) -> DocumentParser:
    try:
        return _PARSER_REGISTRY[name]
    except KeyError as exc:
        available = ", ".join(sorted(_PARSER_REGISTRY))
        raise KeyError(f"Unknown parser '{name}'. Available parsers: {available}") from exc
