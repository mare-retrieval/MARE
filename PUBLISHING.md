# Publishing MARE

This repo is set up for both local package builds and GitHub Actions based PyPI publishing.

## Before the first release

1. Create a PyPI project named `mare`.
2. In PyPI, configure trusted publishing for this GitHub repository.
3. In GitHub, keep the `publish.yml` workflow enabled.
4. Bump the version in:
   - `pyproject.toml`
   - `setup.py`

## Local release check

Create a fresh virtual environment and run:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,publish]"
python -m pytest -q
python -m build
python -m twine check dist/*
```

This verifies:

- tests pass
- source distribution builds
- wheel builds
- PyPI metadata is valid

## Publish through GitHub

The repository includes `.github/workflows/publish.yml`.

It will publish when:

- a GitHub release is published
- or the workflow is triggered manually

## Recommended release flow

1. Update version numbers.
2. Run the local release check.
3. Commit and push.
4. Create a GitHub release for that version.
5. Let GitHub Actions publish to PyPI.

## Install commands after release

Once published, users will be able to install with:

```bash
pip install mare-retrieval
```

Optional UI extras:

```bash
pip install "mare-retrieval[ui]"
```
