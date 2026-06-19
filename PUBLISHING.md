# Publishing MARE

This repo is set up for both local package builds and GitHub Actions based PyPI publishing.

## Before the first release

1. Create or verify the PyPI project named `mare-retrieval`.
2. In PyPI, configure trusted publishing for this GitHub repository with these exact values:
   - Owner: `mare-retrieval`
   - Repository: `MARE`
   - Workflow file: `publish.yml`
   - Environment: `pypi`
3. In GitHub, keep the `publish.yml` workflow enabled.
4. Bump the version in `pyproject.toml`.

### Trusted publishing troubleshooting

If PyPI returns:

```text
invalid-publisher: valid token, but no corresponding publisher
```

the GitHub workflow claims did not match the trusted publisher entry on PyPI.

For this repo, the expected claims are:

- `repository`: `mare-retrieval/MARE`
- `workflow_ref`: `mare-retrieval/MARE/.github/workflows/publish.yml@refs/tags/<tag>`
- `environment`: `pypi`

The most common fix is to open the `mare-retrieval` project on PyPI and update the trusted publisher so it matches:

- owner/org: `mare-retrieval`
- repository: `MARE`
- workflow: `publish.yml`
- environment: `pypi`

After updating the PyPI trusted publisher, rerun the failed GitHub Actions publish job or trigger the workflow manually.

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

1. Update the version number in `pyproject.toml`.
2. Write a release notes file such as `releases/RELEASE_NOTES_0.4.0.md`.
3. Skim the README install and feature sections so the public story matches the release.
4. Run the local release check.
5. Commit and push.
6. Create a GitHub release for that version using the release notes file.
7. Let GitHub Actions publish to PyPI.

## Install commands after release

Once published, users will be able to install with:

```bash
pip install mare-retrieval
```

Optional UI extras:

```bash
pip install "mare-retrieval[ui]"
```

Optional integration extras:

```bash
pip install "mare-retrieval[docling]"
pip install "mare-retrieval[unstructured]"
pip install "mare-retrieval[fastembed]"
pip install "mare-retrieval[integrations]"
```
