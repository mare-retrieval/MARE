from __future__ import annotations

import zipfile
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

spec = spec_from_file_location("check_public_artifacts", Path(__file__).parents[1] / "scripts/check_public_artifacts.py")
assert spec is not None and spec.loader is not None
check_public_artifacts = module_from_spec(spec)
spec.loader.exec_module(check_public_artifacts)


def test_skill_paths_are_detected_inside_source_and_wheel_archives() -> None:
    assert check_public_artifacts._is_internal_skill("skills/mare-repo-context/SKILL.md")
    assert check_public_artifacts._is_internal_skill("package-1.0/skills/context/notes.md")
    assert check_public_artifacts._is_internal_skill("package/SKILL.md")
    assert not check_public_artifacts._is_internal_skill("mare/retrievers/text.py")


def test_public_artifact_check_rejects_packaged_skills(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(check_public_artifacts.subprocess, "check_output", lambda _args: b"")
    dist = tmp_path / "dist"
    dist.mkdir()
    with zipfile.ZipFile(dist / "mare-1.0-py3-none-any.whl", "w") as package:
        package.writestr("skills/private/SKILL.md", "internal")

    assert check_public_artifacts.main() == 1
    assert "skills/private/SKILL.md" in capsys.readouterr().err
