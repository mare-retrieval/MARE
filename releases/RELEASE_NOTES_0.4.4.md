## MARE v0.4.4

MARE `v0.4.4` focuses on adoption and lightweight document work.

This release makes the product easier to start and more useful once users are inside:

- better first-run guidance across CLI and UI
- a new `mare start` entrypoint
- grounded extraction workflows for actions, requirements, risks, and deadlines

### Highlights

- Added a new guided first-run command:
  - `mare start`
  - `mare start ./examples/mixed_docs`
  - `mare start ./docs`
- Improved top-level CLI help so MARE is presented as a mixed-document, folder-first product instead of a PDF-only workflow.
- Improved the Streamlit playground first-run experience with:
  - a clearer “Start Here” panel
  - stronger empty-state guidance
  - better starter prompts for real document work
- Added grounded extraction payloads for:
  - `actions`
  - `requirements`
  - `risks`
  - `deadlines`
- Added new `mare chat` commands:
  - `:actions`
  - `:requirements`
  - `:risks`
  - `:deadlines`
- Added new `mare workflow --task ...` views:
  - `--task actions`
  - `--task requirements`
  - `--task risks`
  - `--task deadlines`
  - plus `--task compare` and `--task summary` for cleaner terminal evaluation

### Why this release matters

Earlier releases made MARE’s evidence engine broader and more honest.

`v0.4.4` turns that engine into something users can adopt faster:

- new users can understand the first run in seconds
- operators can ask for actions instead of only retrieval
- policy and compliance reviews can surface deadlines, risks, and requirement language with citations
- the same evidence can now be consumed as human-readable task views or structured payloads

The product shape stays consistent:

```text
documents -> grounded retrieval -> proof -> concrete document-work output
```

### Example commands

Start here:

```bash
mare start
mare start ./examples/mixed_docs
```

Chat:

```bash
mare chat --folder ./docs
:actions onboarding tasks
:requirements vendor obligations
:risks battery safety warnings
:deadlines renewal dates
```

Workflow:

```bash
mare workflow --folder ./docs --query "vendor obligations" --task requirements
mare workflow --folder ./docs --query "training deadlines" --task deadlines
```

### Notes

- JSON evidence payloads now include a `findings` block with grounded extractions.
- This release continues to prefer inspectable proof over free-form unsupported generation.
- PDFs still provide the strongest visual proof flow, while mixed-document extraction now feels more productized across terminal and UI surfaces.
