"""Tests for pydantic_settings.sources.types module."""

from pydantic_settings.sources.types import SecretVersion


def test_secret_version_init():
    """Test SecretVersion initialization."""
    version = SecretVersion('1.0.0')
    assert version.version == '1.0.0'


def test_secret_version_init_with_empty_string():
    """Test SecretVersion initialization with empty string."""
    version = SecretVersion('')
    assert version.version == ''


def test_secret_version_repr():
    """Test SecretVersion string representation."""
    version = SecretVersion('2.5.3')
    result = repr(version)
    assert result == "SecretVersion('2.5.3')"


def test_secret_version_repr_with_special_characters():
    """Test SecretVersion repr with special characters."""
    version = SecretVersion('v1.0-beta')
    result = repr(version)
    assert result == "SecretVersion('v1.0-beta')"
