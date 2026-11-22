from __future__ import annotations

import json
from pathlib import Path

import pytest

from mare.connect import main, render, server_command, write_project_config


def test_server_command_is_absolute_and_pins_root(tmp_path: Path) -> None:
    command, args = server_command(tmp_path)

    assert Path(command).is_absolute()
    assert args[-2:] == ["--root", str(tmp_path)]
    assert "mcp" in args


@pytest.mark.parametrize("client", ["claude-code", "claude-desktop", "cursor", "vscode", "codex", "gemini"])
def test_render_mentions_server_for_every_client(client: str, tmp_path: Path) -> None:
    text = render(client, tmp_path)

    assert "mare" in text
    assert str(tmp_path) in text


def test_vscode_uses_servers_key_and_stdio_type(tmp_path: Path) -> None:
    target = write_project_config("vscode", tmp_path)
    payload = json.loads(target.read_text())

    assert target == tmp_path / ".vscode" / "mcp.json"
    assert payload["servers"]["mare"]["type"] == "stdio"


def test_write_merges_without_dropping_other_servers(tmp_path: Path) -> None:
    config = tmp_path / ".cursor" / "mcp.json"
    config.parent.mkdir()
    config.write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}, "theme": "dark"}))

    write_project_config("cursor", tmp_path)
    payload = json.loads(config.read_text())

    assert payload["mcpServers"]["other"] == {"command": "x"}
    assert payload["theme"] == "dark"
    assert "mare" in payload["mcpServers"]


def test_write_refuses_to_overwrite_invalid_json(tmp_path: Path) -> None:
    config = tmp_path / ".mcp.json"
    config.write_text("{not json")

    with pytest.raises(SystemExit):
        write_project_config("claude-code", tmp_path)
    assert config.read_text() == "{not json"


def test_write_requires_project_file_client(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        main(["claude-desktop", "--write", "--root", str(tmp_path)])
