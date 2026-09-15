# MARE 0.4.8

MARE 0.4.8 is the Remote MCP Hardening and Evaluation release.

This patch release secures MARE's remote MCP document-access paths, adds continuous integration across supported Python versions, and expands retrieval evaluation with rank-aware and latency metrics.

## Security

- Reject URL ingestion targets that resolve to private, loopback, link-local, or reserved network addresses.
- Revalidate redirected URL targets before accepting downloaded content.
- Reject credential-bearing URLs.
- Apply a 20-second download timeout and a 25 MiB size limit.
- Verify downloaded content has a PDF signature before writing it.
- Restrict remote MCP local-file access to the server working directory.
- Use path-aware containment checks when serving proof assets.

## Evaluation

- Added Recall@k and mean reciprocal rank to evaluation summaries and stack comparisons.
- Added first-relevant-rank and reciprocal-rank details per query.
- Added average retrieval latency reporting.
- Included rank-aware evidence metrics in stack recommendations.

## Reliability

- Added GitHub Actions CI for Python 3.9 through 3.13.
- Added package build, metadata validation, and wheel installation smoke tests on every push and pull request.
