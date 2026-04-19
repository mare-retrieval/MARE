from __future__ import annotations

"""
Example: advanced MARE setup with open-source components.

This shows how a developer can keep the MARE app surface while swapping in:
- Docling or Unstructured for parsing
- Qdrant for vector-backed retrieval
- FastEmbed for reranking

Adjust the imports/config below to match the integrations installed in your env.
"""

from mare import (
    DoclingParser,
    FastEmbedReranker,
    MAREApp,
    MAREConfig,
    Modality,
    QdrantHybridRetriever,
)


def build_app(pdf_path: str) -> MAREApp:
    config = MAREConfig(
        reranker=FastEmbedReranker(),
        retriever_factories={
            Modality.TEXT: lambda documents: QdrantHybridRetriever(
                documents,
                collection_name="mare-docs",
                url="http://localhost:6333",
                vector_name="text",
            )
        },
    )

    return MAREApp.from_pdf(
        pdf_path,
        parser=DoclingParser(),
        config=config,
    )


if __name__ == "__main__":
    app = build_app("manual.pdf")
    best = app.best_match("how do I configure wake on lan")
    print(best)
