from __future__ import annotations

from collections import defaultdict

from mare.types import Modality, RetrievalHit


class WeightedScoreFusion:
    """Simple late fusion with modality-aware weights."""

    def __init__(self, weights: dict[Modality, float] | None = None) -> None:
        self.weights = weights or {
            Modality.TEXT: 1.0,
            Modality.IMAGE: 1.1,
            Modality.LAYOUT: 0.9,
        }

    def fuse(self, results: dict[Modality, list[RetrievalHit]], top_k: int = 5) -> list[RetrievalHit]:
        merged: dict[str, dict[str, object]] = defaultdict(
            lambda: {
                "score": 0.0,
                "title": "",
                "page": 0,
                "reasons": [],
                "snippet": "",
                "page_image_path": "",
                "highlight_image_path": "",
                "object_id": "",
                "object_type": "",
                "metadata": {},
            }
        )

        for modality, hits in results.items():
            weight = self.weights.get(modality, 1.0)
            for hit in hits:
                bucket = merged[hit.doc_id]
                bucket["score"] = float(bucket["score"]) + (hit.score * weight)
                bucket["title"] = hit.title
                bucket["page"] = hit.page
                bucket["reasons"].append(f"{modality.value}:{hit.reason}")
                if not bucket["snippet"] and hit.snippet:
                    bucket["snippet"] = hit.snippet
                if not bucket["page_image_path"] and hit.page_image_path:
                    bucket["page_image_path"] = hit.page_image_path
                if not bucket["highlight_image_path"] and hit.highlight_image_path:
                    bucket["highlight_image_path"] = hit.highlight_image_path
                if not bucket["object_id"] and hit.object_id:
                    bucket["object_id"] = hit.object_id
                if not bucket["object_type"] and hit.object_type:
                    bucket["object_type"] = hit.object_type
                bucket["metadata"] = hit.metadata

        fused: list[RetrievalHit] = []
        for doc_id, payload in merged.items():
            fused.append(
                RetrievalHit(
                    doc_id=doc_id,
                    title=str(payload["title"]),
                    page=int(payload["page"]),
                    modality=Modality.TEXT,
                    score=round(float(payload["score"]), 4),
                    reason=" | ".join(payload["reasons"]),
                    snippet=str(payload["snippet"]),
                    page_image_path=str(payload["page_image_path"]),
                    highlight_image_path=str(payload["highlight_image_path"]),
                    object_id=str(payload["object_id"]),
                    object_type=str(payload["object_type"]),
                    metadata=dict(payload["metadata"]),
                )
            )

        return sorted(fused, key=lambda hit: hit.score, reverse=True)[:top_k]
