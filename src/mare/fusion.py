from __future__ import annotations

from collections import defaultdict

from mare.types import Modality, RetrievalHit

# Text hits carry real document evidence (object content, snippet windows, citation
# metadata). Image captions are weaker; layout hits only carry page-level labels such
# as "procedure" or "table", which must never be shown to a user as the evidence.
_EVIDENCE_PRIORITY = {
    Modality.TEXT: 0,
    Modality.IMAGE: 1,
    Modality.LAYOUT: 2,
}


class WeightedScoreFusion:
    """Simple late fusion with modality-aware weights."""

    def __init__(self, weights: dict[Modality, float] | None = None) -> None:
        self.weights = weights or {
            Modality.TEXT: 1.0,
            Modality.IMAGE: 1.1,
            Modality.LAYOUT: 0.9,
        }

    def fuse(self, results: dict[Modality, list[RetrievalHit]], top_k: int = 5) -> list[RetrievalHit]:
        scores: dict[str, float] = defaultdict(float)
        reasons: dict[str, list[str]] = defaultdict(list)
        contributions: dict[str, list[tuple[Modality, RetrievalHit]]] = defaultdict(list)

        for modality, hits in results.items():
            weight = self.weights.get(modality, 1.0)
            for hit in hits:
                scores[hit.doc_id] += hit.score * weight
                reasons[hit.doc_id].append(f"{modality.value}:{hit.reason}")
                contributions[hit.doc_id].append((modality, hit))

        fused: list[RetrievalHit] = []
        for doc_id, items in contributions.items():
            # Prefer evidence from the most evidence-bearing modality; break ties by score.
            ordered = sorted(
                items,
                key=lambda item: (_EVIDENCE_PRIORITY.get(item[0], 1), -item[1].score),
            )
            primary = ordered[0][1]

            def first(attribute: str) -> str:
                for _, hit in ordered:
                    value = getattr(hit, attribute)
                    if value:
                        return value
                return ""

            fused.append(
                RetrievalHit(
                    doc_id=doc_id,
                    title=primary.title,
                    page=primary.page,
                    modality=Modality.TEXT,
                    score=round(float(scores[doc_id]), 4),
                    reason=" | ".join(reasons[doc_id]),
                    snippet=first("snippet"),
                    page_image_path=first("page_image_path"),
                    highlight_image_path=first("highlight_image_path"),
                    object_id=first("object_id"),
                    object_type=first("object_type"),
                    metadata=dict(primary.metadata),
                )
            )

        return sorted(fused, key=lambda hit: hit.score, reverse=True)[:top_k]
