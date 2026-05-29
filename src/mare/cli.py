from __future__ import annotations

import sys


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] in {"-h", "--help", "help"}:
        print("MARE")
        print("")
        print("Grounded answers over documents and folders, with proof.")
        print("")
        print("Start here:")
        print("  mare start         See the fastest first-run path for your documents")
        print("")
        print("Product modes:")
        print("  mare ui            Launch the visual playground")
        print("  mare chat          Ask questions over a folder of mixed documents")
        print("  mare ask           Ask one PDF a question")
        print("  mare workflow      Run the structured evidence workflow")
        print("  mare ingest        Ingest a PDF into a MARE corpus")
        print("  mare eval          Run the eval harness")
        print("  mare mcp           Run the MCP server")
        print("")
        print("Examples")
        print("  mare start")
        print("  mare start ./examples/mixed_docs")
        print("  mare ui")
        print("  mare chat --folder ./docs")
        print('  mare ask manual.pdf "how do I connect the AC adapter"')
        print("  mare workflow --pdf manual.pdf --query \"how do I connect the AC adapter\"")
        return

    command, *rest = args
    dispatch = {
        "start": "mare.start",
        "ui": "mare.ui",
        "chat": "mare.chat",
        "ask": "mare.ask",
        "workflow": "mare.workflow",
        "ingest": "mare.ingest",
        "eval": "mare.eval",
        "mcp": "mare.mcp_server",
    }
    target = dispatch.get(command)
    if target is None:
        raise SystemExit(f"Unknown subcommand: {command}. Run `mare --help` for usage.")

    module = __import__(target, fromlist=["main"])
    sys.argv = [f"mare {command}", *rest]
    module.main()


if __name__ == "__main__":
    main()
