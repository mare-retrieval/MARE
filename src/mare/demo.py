from __future__ import annotations

import argparse
import json
from pathlib import Path

from mare.engine import MAREngine
from mare.types import Document, DocumentObject, ObjectType


def load_documents(path: Path) -> list[Document]:
    payload = json.loads(path.read_text())
    documents: list[Document] = []
    for item in payload["documents"]:
        raw_objects = item.get("objects", [])
        item["objects"] = [
            DocumentObject(
                object_id=obj["object_id"],
                doc_id=obj["doc_id"],
                page=obj["page"],
                object_type=ObjectType(obj["object_type"]),
                content=obj["content"],
                metadata=obj.get("metadata", {}),
            )
            for obj in raw_objects
        ]
        documents.append(Document(**item))
    return documents


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a MARE retrieval demo")
    parser.add_argument("--query", required=True, help="User query to route and retrieve against")
    parser.add_argument(
        "--corpus",
        default="examples/sample_corpus.json",
        help="Path to a JSON corpus with text/image/layout fields",
    )
    parser.add_argument("--top-k", type=int, default=3, help="How many results to return")
    args = parser.parse_args()

    documents = load_documents(Path(args.corpus))
    engine = MAREngine(documents)
    explanation = engine.explain(args.query, top_k=args.top_k)

    print(
        json.dumps(
            {
                "query": explanation.plan.query,
                "intent": explanation.plan.intent,
                "selected_modalities": [item.value for item in explanation.plan.selected_modalities],
                "discarded_modalities": [item.value for item in explanation.plan.discarded_modalities],
                "confidence": explanation.plan.confidence,
                "rationale": explanation.plan.rationale,
                "results": [
                    {
                        "doc_id": hit.doc_id,
                        "title": hit.title,
                        "page": hit.page,
                        "score": hit.score,
                        "reason": hit.reason,
                        "snippet": hit.snippet,
                        "page_image_path": hit.page_image_path,
                        "highlight_image_path": hit.highlight_image_path,
                        "object_id": hit.object_id,
                        "object_type": hit.object_type,
                    }
                    for hit in explanation.fused_results
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
