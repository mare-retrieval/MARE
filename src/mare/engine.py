from __future__ import annotations

from mare.extensions import MAREConfig
from mare.fusion import WeightedScoreFusion
from mare.retrievers.base import BaseRetriever
from mare.retrievers.image import ImageRetriever, LayoutRetriever
from mare.retrievers.text import TextRetriever
from mare.router import HeuristicModalityRouter
from mare.types import Document, Modality, RetrievalExplanation, RetrievalFilters


class MAREngine:
    """Routes a query to modality-specific retrievers, then fuses their results."""

    def __init__(
        self,
        documents: list[Document],
        router: HeuristicModalityRouter | None = None,
        fusion: WeightedScoreFusion | None = None,
        config: MAREConfig | None = None,
    ) -> None:
        self.documents = documents
        self.router = router or HeuristicModalityRouter()
        self.fusion = fusion or WeightedScoreFusion()
        self.config = config or MAREConfig()
        self.retrievers: dict[Modality, BaseRetriever] = {
            Modality.TEXT: TextRetriever(documents),
            Modality.IMAGE: ImageRetriever(documents),
            Modality.LAYOUT: LayoutRetriever(documents),
        }
        for modality, factory in self.config.retriever_factories.items():
            self.retrievers[modality] = factory(documents)

    def explain(self, query: str, top_k: int = 5, filters: RetrievalFilters | None = None) -> RetrievalExplanation:
        plan = self.router.route(query)
        per_modality_results = {}
        for modality in plan.selected_modalities:
            retriever = self.retrievers[modality]
            candidate_k = top_k
            if filters is not None:
                if type(retriever) in {TextRetriever, ImageRetriever, LayoutRetriever}:
                    # Built-in retrievers can search only eligible pages; custom retrievers
                    # retain exhaustive post-filtering because their filtering API is unknown.
                    eligible = [document for document in self.documents if self._matches_document(document, filters)]
                    retriever = type(retriever)(eligible)
                    candidate_k = max(top_k, sum(1 + len(document.objects) for document in eligible))
                else:
                    candidate_k = max(top_k, sum(1 + len(document.objects) for document in self.documents))
            per_modality_results[modality] = [
                hit for hit in retriever.retrieve(query=query, top_k=candidate_k)
                if filters is None or filters.matches(hit)
            ]
        fused_results = self.fusion.fuse(per_modality_results, top_k=top_k)
        if self.config.reranker is not None:
            fused_results = self.config.reranker.rerank(query=query, hits=fused_results, top_k=top_k)
        return RetrievalExplanation(
            plan=plan,
            per_modality_results=per_modality_results,
            fused_results=fused_results,
        )

    @staticmethod
    def _matches_document(document: Document, filters: RetrievalFilters) -> bool:
        if filters.document_ids and document.doc_id not in filters.document_ids:
            return False
        if filters.pages and document.page not in filters.pages:
            return False
        if filters.sources:
            from pathlib import Path

            source = str(document.metadata.get("source") or document.title)
            allowed = {item.casefold() for item in filters.sources}
            if source.casefold() not in allowed and Path(source).name.casefold() not in allowed:
                return False
        return all(str(document.metadata.get(key, "")).casefold() == value.casefold()
                   for key, value in filters.metadata.items())

    def retrieve(self, query: str, top_k: int = 5, filters: RetrievalFilters | None = None):
        return self.explain(query=query, top_k=top_k, filters=filters).fused_results
