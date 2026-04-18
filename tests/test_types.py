"""Tests for pydantic_settings.sources.types module."""

import pytest
from pydantic_settings.sources.types import SecretVersion


class TestSecretVersion:
    """Test the SecretVersion class."""

    def test_secret_version_init(self):
        """Test SecretVersion.__init__ stores the version attribute."""
        version = "v1.2.3"
        secret = SecretVersion(version)
        assert secret.version == version

    def test_secret_version_init_with_empty_string(self):
        """Test SecretVersion.__init__ with empty string."""
        secret = SecretVersion("")
        assert secret.version == ""

    def test_secret_version_repr(self):
        """Test SecretVersion.__repr__ returns correct representation."""
        secret = SecretVersion("v1.0.0")
        expected = "SecretVersion('v1.0.0')"
        assert repr(secret) == expected

    def test_secret_version_repr_with_special_chars(self):
        """Test SecretVersion.__repr__ with special characters in version."""
        secret = SecretVersion("v1.0.0-beta+build.1")
        expected = "SecretVersion('v1.0.0-beta+build.1')"
        assert repr(secret) == expected

    def test_secret_version_repr_with_quotes(self):
        """Test SecretVersion.__repr__ with quotes in version."""
        secret = SecretVersion("v1.0.0'test")
        # The repr should show the escaped version string
        result = repr(secret)
        assert "SecretVersion" in result
        assert "v1.0.0" in result
