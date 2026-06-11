"""cleo — first-class command-line for the Cleo product-feedback operator.

Entry point lives in ``cli.main:main`` (wired via ``[project.scripts]``), so
``uv run cleo …`` and ``python -m cli.main …`` are the same program. Every
subcommand supports ``--json`` for machine-readable output; see docs/CLI.md.
"""
