"""Tests for pydantic_settings.sources.types module."""

import pytest

from pydantic_settings.sources.types import SecretVersion


def test_secret_version_init():
    """Test SecretVersion initialization stores version correctly."""
    version_str = "v1.2.3"
    secret_version = SecretVersion(version_str)
    assert secret_version.version == version_str


def test_secret_version_repr():
    """Test SecretVersion __repr__ returns expected format."""
    version_str = "v1.2.3"
    secret_version = SecretVersion(version_str)
    expected = "SecretVersion('v1.2.3')"
    assert repr(secret_version) == expected


def test_secret_version_repr_with_special_chars():
    """Test SecretVersion __repr__ handles special characters."""
    version_str = "v1.2.3-beta+build"
    secret_version = SecretVersion(version_str)
    expected = "SecretVersion('v1.2.3-beta+build')"
    assert repr(secret_version) == expected
