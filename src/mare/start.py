from __future__ import annotations

import argparse
from pathlib import Path


SUPPORTED_DOCUMENT_SUFFIXES = {".pdf", ".md", ".markdown", ".txt", ".docx"}
DEFAULT_DEMO_FOLDER = Path("examples/mixed_docs")
DEFAULT_CHAT_QUERY = "show me the onboarding steps"
DEFAULT_DOCUMENT_QUERY = "what are the key setup steps"


def _supported_files(folder: Path) -> list[Path]:
    return sorted(
        path
        for path in folder.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_DOCUMENT_SUFFIXES
    )


def _format_path(path: Path) -> str:
    return path.as_posix()


def _print_intro() -> None:
    print("MARE start")
    print("")
    print("Best first run: point MARE at a document or folder and ask a concrete question with proof.")
    print("")


def _print_folder_plan(folder: Path, files: list[Path]) -> None:
    print(f"Folder: {_format_path(folder)}")
    print(f"Supported documents found: {len(files)}")
    print("")
    print("Recommended next steps")
    print("  1. Start with chat for the fastest trust-building workflow")
    print(f"     mare chat --folder {_format_path(folder)}")
    print(f"  2. Try a concrete question")
    print(f'     {DEFAULT_CHAT_QUERY}')
    print("  3. If you want the visual proof view and have UI deps installed")
    print("     mare ui")
    print("")


def _print_document_plan(document: Path) -> None:
    print(f"Document: {_format_path(document)}")
    print("")
    print("Recommended next steps")
    if document.suffix.lower() == ".pdf":
        print("  1. Ask a single PDF the fastest way")
        print(f'     mare ask {_format_path(document)} "{DEFAULT_DOCUMENT_QUERY}"')
        print("  2. If you want the visual proof view and have UI deps installed")
        print("     mare ui")
    else:
        print("  1. Use workflow for a single non-PDF document")
        print(f'     mare workflow --document {_format_path(document)} --query "{DEFAULT_DOCUMENT_QUERY}"')
        print("  2. If you want an agent-style loop, put this file in a folder and run")
        print(f"     mare chat --folder {_format_path(document.parent)}")
    print("")


def _print_demo_plan() -> None:
    print("No path provided, so start with the bundled mixed-document example.")
    print("")
    print("Recommended next steps")
    print(f"  1. Explore the example folder")
    print(f"     mare chat --folder {_format_path(DEFAULT_DEMO_FOLDER)}")
    print(f"  2. Try a concrete question")
    print(f'     {DEFAULT_CHAT_QUERY}')
    print("  3. If you want the visual proof view and have UI deps installed")
    print("     mare ui")
    print("")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Guide the fastest first-run path for MARE based on a document or folder."
    )
    parser.add_argument(
        "path",
        nargs="?",
        help="Optional document or folder path. If omitted, MARE uses the bundled mixed-document example.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    _print_intro()

    if not args.path:
        _print_demo_plan()
        return

    path = Path(args.path)
    if not path.exists():
        raise SystemExit(f"Path not found: {path}")

    if path.is_dir():
        files = _supported_files(path)
        if not files:
            print(f"Folder: {_format_path(path)}")
            print("No supported documents found yet.")
            print("")
            print("Supported types: .pdf, .md, .markdown, .txt, .docx")
            return
        _print_folder_plan(path, files)
        return

    if path.suffix.lower() not in SUPPORTED_DOCUMENT_SUFFIXES:
        raise SystemExit(
            "Unsupported file type for `mare start`. Supported types: .pdf, .md, .markdown, .txt, .docx"
        )

    _print_document_plan(path)


if __name__ == "__main__":
    main()
