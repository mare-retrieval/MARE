from __future__ import annotations

"""
Example: advanced MARE setup with open-source components.

This script is meant to be a practical, end-to-end developer example. It shows
how to keep MARE's evidence-first application surface while swapping in:

- Built-in, Docling, or Unstructured parsing
- Sentence-transformers semantic retrieval
- Qdrant indexing + retrieval
- FastEmbed reranking
- LangChain / LlamaIndex adapter output
- LangGraph-ready tool output

Typical usage:

1. Local semantic retrieval on a generated corpus
   PYTHONPATH=src python3 examples/advanced_stack.py \
     --corpus generated/manual.json \
     --query "how do I configure wake on lan" \
     --semantic

2. Parse a PDF with Docling, index it into Qdrant, then query it
   PYTHONPATH=src python3 examples/advanced_stack.py \
     --pdf manual.pdf \
     --parser docling \
     --query "show me the comparison table" \
     --qdrant-url http://localhost:6333 \
     --qdrant-collection mare-docs \
     --index-qdrant \
     --use-qdrant \
     --reranker fastembed

3. Return LangChain documents or LlamaIndex nodes for downstream orchestration
   PYTHONPATH=src python3 examples/advanced_stack.py \
     --corpus generated/manual.json \
     --query "how do I connect the AC adapter" \
     --langchain

4. Return a LangGraph-ready evidence tool payload
   PYTHONPATH=src python3 examples/advanced_stack.py \
     --corpus generated/manual.json \
     --query "how do I connect the AC adapter" \
     --langgraph
"""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from mare import (
    DoclingParser,
    FastEmbedReranker,
    MAREApp,
    MAREConfig,
    Modality,
    QdrantHybridRetriever,
    QdrantIndexer,
    SentenceTransformersRetriever,
    UnstructuredParser,
)


def _build_parser_adapter(name: str):
    if name == "builtin":
        return "builtin"
    if name == "docling":
        return DoclingParser()
    if name == "unstructured":
        return UnstructuredParser(strategy="hi_res")
    raise ValueError(f"Unsupported parser: {name}")


def _build_config(args: argparse.Namespace) -> MAREConfig:
    retriever_factories = {}

    if args.use_qdrant:
        retriever_factories[Modality.TEXT] = lambda documents: QdrantHybridRetriever(
            documents,
            collection_name=args.qdrant_collection,
            url=args.qdrant_url,
            vector_name=args.qdrant_vector_name,
        )
    elif args.semantic:
        retriever_factories[Modality.TEXT] = lambda documents: SentenceTransformersRetriever(
            documents,
            model_name=args.embedding_model,
        )

    reranker = FastEmbedReranker() if args.reranker == "fastembed" else None
    return MAREConfig(retriever_factories=retriever_factories, reranker=reranker)


def _load_app(args: argparse.Namespace) -> MAREApp:
    config = _build_config(args)

    if args.corpus:
        return MAREApp.from_corpus(args.corpus, config=config)

    if not args.pdf:
        raise ValueError("Provide either --corpus or --pdf.")

    return MAREApp.from_pdf(
        args.pdf,
        output_path=args.output_path,
        reuse=args.reuse,
        parser=_build_parser_adapter(args.parser),
        config=config,
    )


def _maybe_index_qdrant(app: MAREApp, args: argparse.Namespace) -> int:
    if not args.index_qdrant:
        return 0

    indexer = QdrantIndexer(
        collection_name=args.qdrant_collection,
        url=args.qdrant_url,
        vector_name=args.qdrant_vector_name,
        model_name=args.embedding_model,
    )
    return indexer.index_documents(app.documents, recreate=args.recreate_qdrant)


def _langchain_payload(app: MAREApp, query: str, top_k: int) -> dict:
    retriever = app.as_langchain_retriever(top_k=top_k)
    documents = retriever.invoke(query)
    return {
        "framework": "langchain",
        "query": query,
        "results": [
            {
                "page_content": document.page_content,
                "metadata": document.metadata,
            }
            for document in documents
        ],
    }


def _langgraph_payload(app: MAREApp, query: str, top_k: int) -> dict:
    tool = app.as_langgraph_tool(top_k=top_k)
    result = tool.invoke({"query": query})
    return {
        "framework": "langgraph",
        "query": query,
        "tool_name": getattr(tool, "name", "mare_retrieve"),
        "result": result,
    }


def _llamaindex_payload(app: MAREApp, query: str, top_k: int) -> dict:
    try:
        from llama_index.core.schema import QueryBundle
    except ImportError as exc:
        raise RuntimeError(
            "LlamaIndex output requires `llama-index-core`. Install it with "
            "`pip install 'mare-retrieval[llamaindex]'`."
        ) from exc

    retriever = app.as_llamaindex_retriever(top_k=top_k)
    nodes = retriever.retrieve(QueryBundle(query))
    return {
        "framework": "llamaindex",
        "query": query,
        "results": [
            {
                "score": node.score,
                "text": getattr(node.node, "text", ""),
                "metadata": getattr(node.node, "metadata", {}),
            }
            for node in nodes
        ],
    }


def _mare_payload(app: MAREApp, query: str, top_k: int) -> dict:
    explanation = app.explain(query, top_k=top_k)
    return {
        "framework": "mare",
        "query": query,
        "plan": {
            "intent": explanation.plan.intent,
            "selected_modalities": [item.value for item in explanation.plan.selected_modalities],
            "discarded_modalities": [item.value for item in explanation.plan.discarded_modalities],
            "confidence": explanation.plan.confidence,
            "rationale": explanation.plan.rationale,
        },
        "results": [asdict(hit) for hit in explanation.fused_results],
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run an end-to-end advanced MARE workflow")
    parser.add_argument("--query", required=True, help="Question to ask of the document corpus")
    parser.add_argument("--corpus", help="Existing generated MARE corpus JSON")
    parser.add_argument("--pdf", help="PDF to ingest before retrieval")
    parser.add_argument("--output-path", help="Optional output path for generated corpus JSON")
    parser.add_argument("--reuse", action="store_true", help="Reuse an existing generated corpus if present")
    parser.add_argument(
        "--parser",
        choices=("builtin", "docling", "unstructured"),
        default="builtin",
        help="Parser to use when ingesting a PDF",
    )
    parser.add_argument("--semantic", action="store_true", help="Use sentence-transformers for text retrieval")
    parser.add_argument(
        "--embedding-model",
        default="sentence-transformers/all-MiniLM-L6-v2",
        help="Embedding model for sentence-transformers or Qdrant indexing",
    )
    parser.add_argument(
        "--reranker",
        choices=("none", "fastembed"),
        default="none",
        help="Optional second-stage reranker",
    )
    parser.add_argument("--qdrant-url", default="http://localhost:6333", help="Qdrant base URL")
    parser.add_argument("--qdrant-collection", default="mare-docs", help="Qdrant collection name")
    parser.add_argument("--qdrant-vector-name", default="text", help="Named Qdrant vector to use")
    parser.add_argument("--index-qdrant", action="store_true", help="Index the loaded corpus into Qdrant")
    parser.add_argument("--recreate-qdrant", action="store_true", help="Recreate the Qdrant collection when indexing")
    parser.add_argument("--use-qdrant", action="store_true", help="Use Qdrant for text retrieval")
    parser.add_argument("--langchain", action="store_true", help="Return LangChain documents instead of raw MARE hits")
    parser.add_argument("--langgraph", action="store_true", help="Return a LangGraph-ready tool result")
    parser.add_argument(
        "--llamaindex",
        action="store_true",
        help="Return LlamaIndex nodes instead of raw MARE hits",
    )
    parser.add_argument("--top-k", type=int, default=3, help="How many results to return")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    app = _load_app(args)
    indexed_count = _maybe_index_qdrant(app, args)

    selected_frameworks = sum([bool(args.langchain), bool(args.langgraph), bool(args.llamaindex)])
    if selected_frameworks > 1:
        raise SystemExit("Choose at most one of --langchain, --langgraph, or --llamaindex.")

    if args.langchain:
        payload = _langchain_payload(app, args.query, args.top_k)
    elif args.langgraph:
        payload = _langgraph_payload(app, args.query, args.top_k)
    elif args.llamaindex:
        payload = _llamaindex_payload(app, args.query, args.top_k)
    else:
        payload = _mare_payload(app, args.query, args.top_k)

    payload["source"] = {
        "pdf": str(app.source_pdf) if app.source_pdf else "",
        "corpus": str(app.corpus_path) if app.corpus_path else "",
        "documents": len(app.documents),
    }
    payload["stack"] = {
        "parser": args.parser if args.pdf else "corpus",
        "semantic": args.semantic,
        "reranker": args.reranker,
        "use_qdrant": args.use_qdrant,
        "qdrant_indexed_documents": indexed_count,
    }

    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
