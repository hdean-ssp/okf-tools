# Contributing to okf-tools

## Development Setup

```bash
git clone <repo-url>
cd okf-tools
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Running Tests

```bash
pytest                    # all tests
pytest tests/test_bundle.py  # specific module
pytest -v                 # verbose output
```

The first run of tests that touch semantic search will download the embedding model (~30MB). Subsequent runs use the cached model at `~/.cache/fastembed/`.

## Code Style

- Python 3.9 compatible — no `match` statements, use `from __future__ import annotations`
- Type hints on all public functions
- Docstrings on all public functions and classes
- Keep modules focused — one responsibility per file
- Prefer clarity over cleverness

## Project Structure

```
src/okf_tools/
├── cli.py          # Click commands (thin — delegates to service)
├── service.py      # Workflow orchestration
├── bundle.py       # File parsing, writing, validation
├── search.py       # Vector index (sqlite-vec + fastembed)
├── graph.py        # Link graph (adjacency + BFS)
├── sync.py         # Incremental reindexing
├── validation.py   # Bundle-wide lint checks
├── config.py       # Configuration loading
├── skills.py       # Skill pack discovery
└── errors.py       # Error hierarchy
```

## Pull Request Guidelines

1. Branch from `main`
2. Keep PRs focused — one logical change per PR
3. Add tests for new functionality
4. Run `okf lint` on any test bundles you create
5. All tests must pass before merge
6. Update docs if you change CLI behaviour
