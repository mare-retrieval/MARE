from __future__ import annotations

from .types import Modality, QueryPlan


class HeuristicModalityRouter:
    """A small baseline router that can later be replaced with an LLM or classifier."""

    IMAGE_HINTS = {
        "diagram",
        "figure",
        "image",
        "visual",
        "architecture",
        "screenshot",
        "flowchart",
    }
    LAYOUT_HINTS = {
        "table",
        "layout",
        "section",
        "page",
        "compare",
        "comparison",
        "column",
    }
    TEXT_HINTS = {
        "what",
        "why",
        "how",
        "formula",
        "equation",
        "method",
        "instruction",
        "definition",
    }

    def route(self, query: str) -> QueryPlan:
        lowered = query.lower()
        tokens = set(lowered.replace("-", " ").split())

        scores = {
            Modality.TEXT: len(tokens & self.TEXT_HINTS),
            Modality.IMAGE: len(tokens & self.IMAGE_HINTS),
            Modality.LAYOUT: len(tokens & self.LAYOUT_HINTS),
        }

        if max(scores.values()) == 0:
            selected = [Modality.TEXT]
            discarded = [Modality.IMAGE, Modality.LAYOUT]
            return QueryPlan(
                query=query,
                selected_modalities=selected,
                discarded_modalities=discarded,
                confidence=0.55,
                intent="general_lookup",
                rationale="No strong visual or layout cues were detected, so the router defaulted to text retrieval.",
            )

        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        top_score = ranked[0][1]
        selected = [modality for modality, score in ranked if score > 0 and score >= top_score - 1]
        if Modality.LAYOUT in selected and Modality.TEXT not in selected:
            selected.append(Modality.TEXT)
        if Modality.IMAGE in selected and Modality.TEXT not in selected and ("figure" in tokens or "diagram" in tokens):
            selected.append(Modality.TEXT)
        discarded = [modality for modality in Modality if modality not in selected]

        intent = "visual_lookup" if Modality.IMAGE in selected else "structured_lookup"
        if selected == [Modality.TEXT]:
            intent = "semantic_lookup"
        elif Modality.TEXT in selected and len(selected) > 1:
            intent = "hybrid_lookup"

        confidence = min(0.95, 0.55 + (0.1 * top_score) + (0.05 * len(selected)))
        rationale = (
            f"Detected modality cues in query tokens. Selected {', '.join(mod.value for mod in selected)} "
            f"based on keyword overlap with routing hints."
        )

        return QueryPlan(
            query=query,
            selected_modalities=selected,
            discarded_modalities=discarded,
            confidence=confidence,
            intent=intent,
            rationale=rationale,
        )
