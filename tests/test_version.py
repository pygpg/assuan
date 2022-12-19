"""Provide tests for project version."""

from assuan import __version__


def test_version() -> None:
    """Test project metadata version."""
    assert __version__ == '0.2.1b1'
