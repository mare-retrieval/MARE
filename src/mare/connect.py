"""Print (or write) ready-to-use MCP configuration for popular agent clients.

The most common reason a local MCP server "does not show up" is that the client cannot
find the executable: desktop apps do not inherit a virtualenv's PATH. ``mare connect``
therefore always emits the absolute path of the interpreter MARE is installed in, plus a
``--root`` so indexes land in the user's project instead of the client's launch directory.
"""

from __future__ import annotations

import argparse
import json
import shlex
import shutil
import sys
from pathlib import Path
from typing import Any

SERVER_NAME = "mare"

CLIENTS: dict[str, dict[str, str]] = {
    "claude-code": {"label": "Claude Code", "project_file": ".mcp.json", "key": "mcpServers"},
    "claude-desktop": {"label": "Claude Desktop", "project_file": "", "key": "mcpServers"},
    "cursor": {"label": "Cursor", "project_file": ".cursor/mcp.json", "key": "mcpServers"},
    "vscode": {"label": "VS Code (GitHub Copilot agent mode)", "project_file": ".vscode/mcp.json", "key": "servers"},
    "codex": {"label": "OpenAI Codex CLI", "project_file": "", "key": ""},
    "gemini": {"label": "Gemini CLI", "project_file": ".gemini/settings.json", "key": "mcpServers"},
}


def server_command(root: Path) -> tuple[str, list[str]]:
    """Absolute command + args that launch the MARE MCP server over stdio."""
    executable = shutil.which("mare")
    sibling = Path(sys.executable).with_name("mare")
    if sibling.exists():
        # Prefer the entry point next to the running interpreter (the active virtualenv).
        executable = str(sibling)
    if executable:
        return str(Path(executable).resolve()), ["mcp", "--root", str(root)]
    return str(Path(sys.executable).resolve()), ["-m", "mare.cli", "mcp", "--root", str(root)]


def server_entry(client: str, root: Path) -> dict[str, Any]:
    command, args = server_command(root)
    entry: dict[str, Any] = {"command": command, "args": args}
    if client == "vscode":
        entry = {"type": "stdio", **entry}
    return entry


def _claude_desktop_config_path() -> str:
    if sys.platform == "darwin":
        return "~/Library/Application Support/Claude/claude_desktop_config.json"
    if sys.platform.startswith("win"):
        return r"%APPDATA%\Claude\claude_desktop_config.json"
    return "~/.config/Claude/claude_desktop_config.json"


def _toml_string(value: str) -> str:
    return json.dumps(value)


def render(client: str, root: Path) -> str:
    spec = CLIENTS[client]
    command, args = server_command(root)
    shell_command = " ".join(shlex.quote(part) for part in [command, *args])
    lines = [f"# {spec['label']}"]

    if client == "claude-code":
        lines += [
            "Run once (add --scope project to share it through .mcp.json):",
            f"  claude mcp add {SERVER_NAME} -- {shell_command}",
            "",
            "Or write the project file with: mare connect claude-code --write",
        ]
        return "\n".join(lines)

    if client == "codex":
        lines += [
            "Run once:",
            f"  codex mcp add {SERVER_NAME} -- {shell_command}",
            "",
            "Or add to ~/.codex/config.toml:",
            f"[mcp_servers.{SERVER_NAME}]",
            f"command = {_toml_string(command)}",
            "args = [" + ", ".join(_toml_string(item) for item in args) + "]",
        ]
        return "\n".join(lines)

    payload = {spec["key"]: {SERVER_NAME: server_entry(client, root)}}
    if client == "claude-desktop":
        lines.append(f"Merge into {_claude_desktop_config_path()} and restart Claude Desktop:")
    else:
        lines.append(f"Merge into {spec['project_file']} (or run: mare connect {client} --write):")
    lines.append(json.dumps(payload, indent=2))
    return "\n".join(lines)


def write_project_config(client: str, root: Path) -> Path:
    spec = CLIENTS[client]
    if not spec["project_file"]:
        raise SystemExit(f"{spec['label']} has no project-level config file; paste the printed config instead.")
    target = root / spec["project_file"]
    existing: dict[str, Any] = {}
    if target.exists():
        try:
            existing = json.loads(target.read_text() or "{}")
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Refusing to edit {target}: it is not valid JSON ({exc}).") from exc
        if not isinstance(existing, dict):
            raise SystemExit(f"Refusing to edit {target}: expected a JSON object.")
    servers = existing.setdefault(spec["key"], {})
    if not isinstance(servers, dict):
        raise SystemExit(f"Refusing to edit {target}: '{spec['key']}' is not an object.")
    servers[SERVER_NAME] = server_entry(client, root)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(existing, indent=2) + "\n")
    return target


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mare connect",
        description="Print MCP config that connects MARE to an agent client.",
    )
    parser.add_argument("client", nargs="?", choices=sorted(CLIENTS), help="Client to configure. Omit to show all.")
    parser.add_argument(
        "--root",
        default=".",
        help="Project folder MARE should treat as its working directory. Default: current directory.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Merge the config into the client's project-level file instead of printing it.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_arg_parser().parse_args(argv)
    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        raise SystemExit(f"--root is not a directory: {args.root}")

    if args.write:
        if not args.client:
            raise SystemExit("Choose a client to write, e.g. `mare connect cursor --write`.")
        target = write_project_config(args.client, root)
        print(f"Added '{SERVER_NAME}' to {target}. Restart or reload {CLIENTS[args.client]['label']} to pick it up.")
        return

    clients = [args.client] if args.client else list(CLIENTS)
    print("\n\n".join(render(client, root) for client in clients))
    try:
        import mcp  # noqa: F401
    except ImportError:
        print("\nNote: install MCP support first: pip install 'mare-retrieval[mcp]'")
    print("\nThen ask your agent something like: \"Use MARE to find what ./docs says about onboarding, with citations.\"")


if __name__ == "__main__":
    main()
