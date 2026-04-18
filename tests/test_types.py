"""Tests for pydantic_settings.sources.types module."""

from pydantic_settings.sources.types import SecretVersion


class TestSecretVersion:
    """Tests for the SecretVersion class."""

    def test_init_stores_version(self):
        """Test that __init__ stores the version string."""
        version = 'v1.0.0'
        secret_version = SecretVersion(version)

        assert secret_version.version == version

    def test_init_with_empty_string(self):
        """Test __init__ with empty string version."""
        secret_version = SecretVersion('')

        assert secret_version.version == ''

    def test_init_with_numeric_string(self):
        """Test __init__ with numeric string version."""
        secret_version = SecretVersion('123')

        assert secret_version.version == '123'

    def test_repr_format(self):
        """Test that __repr__ returns correct format."""
        version = 'v2.0.0'
        secret_version = SecretVersion(version)

        result = repr(secret_version)

        assert result == "SecretVersion('v2.0.0')"

    def test_repr_with_special_characters(self):
        """Test __repr__ with special characters in version."""
        version = "v1.0.0-beta+build'123"
        secret_version = SecretVersion(version)

        result = repr(secret_version)

        assert result == 'SecretVersion("v1.0.0-beta+build\'123")'

    def test_repr_with_empty_version(self):
        """Test __repr__ with empty version string."""
        secret_version = SecretVersion('')

        result = repr(secret_version)

        assert result == "SecretVersion('')"
