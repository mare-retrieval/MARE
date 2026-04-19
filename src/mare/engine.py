from __future__ import annotations

from mare.extensions import MAREConfig
from mare.fusion import WeightedScoreFusion
from mare.retrievers.base import BaseRetriever
from mare.retrievers.image import ImageRetriever, LayoutRetriever
from mare.retrievers.text import TextRetriever
from mare.router import HeuristicModalityRouter
from mare.types import Document, Modality, RetrievalExplanation


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

    def explain(self, query: str, top_k: int = 5) -> RetrievalExplanation:
        plan = self.router.route(query)
        per_modality_results = {
            modality: self.retrievers[modality].retrieve(query=query, top_k=top_k)
            for modality in plan.selected_modalities
        }
        fused_results = self.fusion.fuse(per_modality_results, top_k=top_k)
        if self.config.reranker is not None:
            fused_results = self.config.reranker.rerank(query=query, hits=fused_results, top_k=top_k)
        return RetrievalExplanation(
            plan=plan,
            per_modality_results=per_modality_results,
            fused_results=fused_results,
        )

    def retrieve(self, query: str, top_k: int = 5):
        return self.explain(query=query, top_k=top_k).fused_results
