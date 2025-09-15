"""Nox configuration file for task automation."""

import nox

PYTHON_VERSIONS = ["3.12", "3.13"]

@nox.session(python=PYTHON_VERSIONS)
def tests(session):
    """Run the test suite."""
    session.install("-e", ".[dev]")
    session.run("pytest", *session.posargs)

@nox.session(python="3.12")
def lint(session):
    """Run linting checks."""
    session.install("ruff")
    session.run("ruff", "check", "src", "tests")
    session.run("ruff", "format", "--check", "src", "tests")

@nox.session(python="3.12")
def type_check(session):
    """Run type checking."""
    session.install("-e", ".[dev]")
    session.run("mypy", "src/event_selector")

@nox.session(python="3.12")
def docs(session):
    """Build documentation."""
    session.install("-e", ".[docs]")
    session.run("mkdocs", "build")

@nox.session(python="3.12")
def coverage(session):
    """Run tests with coverage report."""
    session.install("-e", ".[dev]")
    session.run(
        "pytest",
        "--cov=src/event_selector",
        "--cov-report=term-missing:skip-covered",
        "--cov-report=html",
        *session.posargs
    )
    session.notify("coverage_report")

@nox.session
def coverage_report(session):
    """Display coverage report."""
    session.run("open", "htmlcov/index.html", external=True)
