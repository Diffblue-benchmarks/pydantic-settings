"""Tests for NestedSecretsSettingsSource."""

import os
import warnings
from pathlib import Path
from typing import Optional

import pytest

from pydantic_settings import BaseSettings
from pydantic_settings.exceptions import SettingsError
from pydantic_settings.sources import SecretsSettingsSource
from pydantic_settings.sources.providers.nested_secrets import (
    NestedSecretsSettingsSource,
    first_not_none,
)


class SimpleSettings(BaseSettings):
    """Simple settings model for testing."""

    name: str = "default"
    value: int = 0
    enabled: bool = False


class SettingsWithSecretsConfig(BaseSettings):
    """Settings model with secrets configuration in model_config."""

    name: str = "default"
    value: int = 0
    nested_field: Optional[str] = None

    model_config = {
        "secrets_dir": "/tmp/secrets",
        "secrets_dir_missing": "warn",
        "secrets_dir_max_size": 1024,
        "secrets_case_sensitive": False,
        "secrets_prefix": "APP_",
        "secrets_nested_delimiter": "__",
    }


class TestFirstNotNone:
    """Tests for first_not_none utility function."""

    def test_first_not_none_with_first_value(self):
        """Test first_not_none returns first non-None value."""
        # Act
        result = first_not_none(1, 2, 3)

        # Assert
        assert result == 1

    def test_first_not_none_with_middle_value(self):
        """Test first_not_none returns middle value when first is None."""
        # Act
        result = first_not_none(None, 2, 3)

        # Assert
        assert result == 2

    def test_first_not_none_with_all_none(self):
        """Test first_not_none returns None when all values are None."""
        # Act
        result = first_not_none(None, None, None)

        # Assert
        assert result is None

    def test_first_not_none_with_single_value(self):
        """Test first_not_none with a single value."""
        # Act
        result = first_not_none(42)

        # Assert
        assert result == 42

    def test_first_not_none_with_falsy_values(self):
        """Test first_not_none distinguishes None from other falsy values."""
        # Act
        result = first_not_none(None, 0, False)

        # Assert
        assert result == 0


class TestNestedSecretsSettingsSourceInit:
    """Tests for NestedSecretsSettingsSource.__init__ method."""

    def test_init_with_settings_cls(self, tmp_path):
        """Test initialization with BaseSettings class directly."""
        # Arrange
        secrets_dir = tmp_path / "secrets"
        secrets_dir.mkdir()

        # Act
        source = NestedSecretsSettingsSource(
            SimpleSettings, secrets_dir=secrets_dir
        )

        # Assert
        assert source.secrets_dir == secrets_dir
        assert source.secrets_dir_missing == "warn"
        assert source.case_sensitive is False
        assert source.secrets_prefix == ""

    def test_init_with_secrets_settings_source(self, tmp_path):
        """Test initialization with SecretsSettingsSource instance."""
        # Arrange
        secrets_dir = tmp_path / "secrets"
        secrets_dir.mkdir()
        secrets_source = SecretsSettingsSource(
            SimpleSettings, secrets_dir=secrets_dir
        )

        # Act
        source = NestedSecretsSettingsSource(secrets_source)

        # Assert
        assert source.secrets_dir == secrets_dir
        assert isinstance(source.secrets_paths, list)
        assert len(source.secrets_paths) == 1

    def test_init_with_explicit_secrets_dir(self, tmp_path):
        """Test initialization with explicit secrets_dir parameter."""
        # Arrange
        secrets_dir = tmp_path / "secrets"
        secrets_dir.mkdir()

        # Act
        source = NestedSecretsSettingsSource(
            SimpleSettings, secrets_dir=secrets_dir
        )

        # Assert
        assert source.secrets_paths[0] == secrets_dir.resolve()

    def test_init_with_multiple_secrets_dirs(self, tmp_path):
        """Test initialization with multiple secrets directories."""
        # Arrange
        secrets_dir1 = tmp_path / "secrets1"
        secrets_dir2 = tmp_path / "secrets2"
        secrets_dir1.mkdir()
        secrets_dir2.mkdir()

        # Act
        source = NestedSecretsSettingsSource(
            SimpleSettings, secrets_dir=[secrets_dir1, secrets_dir2]
        )

        # Assert
        assert len(source.secrets_paths) == 2
        assert source.secrets_paths[0] == secrets_dir1.resolve()
        assert source.secrets_paths[1] == secrets_dir2.resolve()

    def test_init_with_string_path(self, tmp_path):
        """Test initialization with secrets_dir as string."""
        # Arrange
        secrets_dir = tmp_path / "secrets"
        secrets_dir.mkdir()

        # Act
        source = NestedSecretsSettingsSource(
            SimpleSettings, secrets_dir=str(secrets_dir)
        )

        # Assert
        assert source.secrets_paths[0] == secrets_dir.resolve()

    def test_init_with_secrets_dir_missing_ok(self, tmp_path):
        """Test initialization with secrets_dir_missing='ok' for non-existent dir."""
        # Arrange
        secrets_dir = tmp_path / "nonexistent"

        # Act
        source = NestedSecretsSettingsSource(
            SimpleSettings,
            secrets_dir=secrets_dir,
            secrets_dir_missing="ok",
        )

        # Assert
        assert source.secrets_dir_missing == "ok"

    def test_init_with_secrets_dir_missing_warn(self, tmp_path):
        """Test initialization with secrets_dir_missing='warn' for non-existent dir."""
        # Arrange
        secrets_dir = tmp_path / "nonexistent"

        # Act & Assert
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            source = NestedSecretsSettingsSource(
                SimpleSettings,
                secrets_dir=secrets_dir,
                secrets_dir_missing="warn",
            )
            assert len(w) == 1
            assert "does not exist" in str(w[0].message)

    def test_init_with_secrets_dir_missing_error(self, tmp_path):
        """Test initialization with secrets_dir_missing='error' for non-existent dir."""
        # Arrange
        secrets_dir = tmp_path / "nonexistent"

        # Act & Assert
        with pytest.raises(SettingsError, match="does not exist"):
            NestedSecretsSettingsSource(
                SimpleSettings,
                secrets_dir=secrets_dir,
                secrets_dir_missing="error",
            )

    def test_init_with_invalid_secrets_dir_missing(self, tmp_path):
        """Test initialization with invalid secrets_dir_missing value."""
        # Arrange
        secrets_dir = tmp_path / "secrets"
        secrets_dir.mkdir()

        # Act & Assert
        with pytest.raises(SettingsError, match="invalid secrets_dir_missing value"):
            NestedSecretsSettingsSource(
                SimpleSettings,
                secrets_dir=secrets_dir,
                secrets_dir_missing="invalid",
            )

    def test_init_with_secrets_dir_max_size(self, tmp_path):
        """Test initialization with explicit secrets_dir_max_size."""
        # Arrange
        secrets_dir = tmp_path / "secrets"
        secrets_dir.mkdir()

        # Act
        source = NestedSecretsSettingsSource(
            SimpleSettings,
            secrets_dir=secrets_dir,
            secrets_dir_max_size=2048,
        )

        # Assert
        assert source.secrets_dir_max_size == 2048

    def test_init_with_case_sensitive(self, tmp_path):
        """Test initialization with case_sensitive parameter."""
        # Arrange
        secrets_dir = tmp_path / "secrets"
        secrets_dir.mkdir()

        # Act
        source = NestedSecretsSettingsSource(
            SimpleSettings,
            secrets_dir=secrets_dir,
            secrets_case_sensitive=True,
        )

        # Assert
        assert source.case_sensitive is True

    def test_init_with_secrets_prefix(self, tmp_path):
        """Test initialization with secrets_prefix parameter."""
        # Arrange
        secrets_dir = tmp_path / "secrets"
        secrets_dir.mkdir()

        # Act
        source = NestedSecretsSettingsSource(
            SimpleSettings,
            secrets_dir=secrets_dir,
            secrets_prefix="APP_",
        )

        # Assert
        assert source.secrets_prefix == "APP_"

    def test_init_with_env_prefix_fallback(self, tmp_path):
        """Test initialization with env_prefix as fallback for secrets_prefix."""
        # Arrange
        secrets_dir = tmp_path / "secrets"
        secrets_dir.mkdir()

        # Act
        source = NestedSecretsSettingsSource(
            SimpleSettings,
            secrets_dir=secrets_dir,
            env_prefix="ENV_",
        )

        # Assert
        assert source.secrets_prefix == "ENV_"

    def test_init_with_secrets_nested_delimiter(self, tmp_path):
        """Test initialization with secrets_nested_delimiter parameter."""
        # Arrange
        secrets_dir = tmp_path / "secrets"
        secrets_dir.mkdir()

        # Act
        source = NestedSecretsSettingsSource(
            SimpleSettings,
            secrets_dir=secrets_dir,
            secrets_nested_delimiter="__",
        )

        # Assert
        assert source.secrets_nested_delimiter == "__"

    def test_init_with_secrets_nested_subdir_true(self, tmp_path):
        """Test initialization with secrets_nested_subdir=True."""
        # Arrange
        secrets_dir = tmp_path / "secrets"
        secrets_dir.mkdir()

        # Act
        source = NestedSecretsSettingsSource(
            SimpleSettings,
            secrets_dir=secrets_dir,
            secrets_nested_subdir=True,
        )

        # Assert
        assert source.secrets_nested_subdir is True
        assert source.secrets_nested_delimiter == os.sep

    def test_init_with_mutually_exclusive_nested_options(self, tmp_path):
        """Test initialization with both nested_delimiter and nested_subdir raises error."""
        # Arrange
        secrets_dir = tmp_path / "secrets"
        secrets_dir.mkdir()

        # Act & Assert
        with pytest.raises(SettingsError, match="mutually exclusive"):
            NestedSecretsSettingsSource(
                SimpleSettings,
                secrets_dir=secrets_dir,
                secrets_nested_delimiter="__",
                secrets_nested_subdir=True,
            )

    def test_init_with_none_secrets_dir(self):
        """Test initialization with None secrets_dir."""
        # Act
        source = NestedSecretsSettingsSource(
            SimpleSettings, secrets_dir=None
        )

        # Assert
        assert source.secrets_dir is None
        assert source.secrets_paths == []
        assert source.env_vars == {}

    def test_init_with_secrets_from_model_config(self, tmp_path):
        """Test initialization uses values from model_config."""
        # Arrange
        secrets_dir = tmp_path / "secrets"
        secrets_dir.mkdir()

        # Override model_config
        original_config = SettingsWithSecretsConfig.model_config.copy()
        SettingsWithSecretsConfig.model_config["secrets_dir"] = str(secrets_dir)

        try:
            # Act
            source = NestedSecretsSettingsSource(SettingsWithSecretsConfig)

            # Assert
            assert source.secrets_prefix == "APP_"
            assert source.secrets_nested_delimiter == "__"
            assert source.secrets_dir_max_size == 1024
            assert source.secrets_dir_missing == "warn"
        finally:
            # Restore original config
            SettingsWithSecretsConfig.model_config.update(original_config)

    def test_init_with_secrets_loads_files(self, tmp_path):
        """Test initialization loads secrets from files."""
        # Arrange
        secrets_dir = tmp_path / "secrets"
        secrets_dir.mkdir()
        (secrets_dir / "secret1").write_text("value1")
        (secrets_dir / "secret2").write_text("value2")

        # Act
        source = NestedSecretsSettingsSource(
            SimpleSettings, secrets_dir=secrets_dir
        )

        # Assert
        assert "secret1" in source.env_vars
        assert "secret2" in source.env_vars


class TestValidateSecretsPath:
    """Tests for NestedSecretsSettingsSource.validate_secrets_path method."""

    def test_validate_secrets_path_with_existing_directory(self, tmp_path):
        """Test validate_secrets_path with an existing directory."""
        # Arrange
        secrets_dir = tmp_path / "secrets"
        secrets_dir.mkdir()
        source = NestedSecretsSettingsSource(
            SimpleSettings, secrets_dir=secrets_dir
        )

        # Act & Assert (should not raise)
        source.validate_secrets_path(secrets_dir)

    def test_validate_secrets_path_with_missing_dir_ok(self, tmp_path):
        """Test validate_secrets_path with missing dir and secrets_dir_missing='ok'."""
        # Arrange
        secrets_dir = tmp_path / "secrets"
        secrets_dir.mkdir()
        source = NestedSecretsSettingsSource(
            SimpleSettings,
            secrets_dir=secrets_dir,
            secrets_dir_missing="ok",
        )
        nonexistent = tmp_path / "nonexistent"

        # Act & Assert (should not raise)
        source.validate_secrets_path(nonexistent)

    def test_validate_secrets_path_with_missing_dir_warn(self, tmp_path):
        """Test validate_secrets_path with missing dir and secrets_dir_missing='warn'."""
        # Arrange
        secrets_dir = tmp_path / "secrets"
        secrets_dir.mkdir()
        source = NestedSecretsSettingsSource(
            SimpleSettings,
            secrets_dir=secrets_dir,
            secrets_dir_missing="warn",
        )
        nonexistent = tmp_path / "nonexistent"

        # Act & Assert
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            source.validate_secrets_path(nonexistent)
            assert len(w) == 1
            assert "does not exist" in str(w[0].message)

    def test_validate_secrets_path_with_missing_dir_error(self, tmp_path):
        """Test validate_secrets_path with missing dir and secrets_dir_missing='error'."""
        # Arrange
        secrets_dir = tmp_path / "secrets"
        secrets_dir.mkdir()
        source = NestedSecretsSettingsSource(
            SimpleSettings,
            secrets_dir=secrets_dir,
            secrets_dir_missing="error",
        )
        nonexistent = tmp_path / "nonexistent"

        # Act & Assert
        with pytest.raises(SettingsError, match="does not exist"):
            source.validate_secrets_path(nonexistent)

    def test_validate_secrets_path_with_file_not_directory(self, tmp_path):
        """Test validate_secrets_path raises error when path is a file."""
        # Arrange
        secrets_dir = tmp_path / "secrets"
        secrets_dir.mkdir()
        file_path = tmp_path / "file.txt"
        file_path.write_text("content")
        source = NestedSecretsSettingsSource(
            SimpleSettings, secrets_dir=secrets_dir
        )

        # Act & Assert
        with pytest.raises(SettingsError, match="must reference a directory"):
            source.validate_secrets_path(file_path)

    def test_validate_secrets_path_exceeds_max_size(self, tmp_path):
        """Test validate_secrets_path raises error when directory exceeds max size."""
        # Arrange
        secrets_dir = tmp_path / "secrets"
        secrets_dir.mkdir()
        large_file = secrets_dir / "large_secret"
        large_file.write_text("x" * 2000)

        too_large_dir = tmp_path / "too_large"
        too_large_dir.mkdir()
        (too_large_dir / "large").write_text("x" * 2000)

        # Act & Assert
        with pytest.raises(SettingsError, match="size is above"):
            NestedSecretsSettingsSource(
                SimpleSettings,
                secrets_dir=too_large_dir,
                secrets_dir_max_size=1000,
            )


class TestLoadSecrets:
    """Tests for NestedSecretsSettingsSource.load_secrets static method."""

    def test_load_secrets_from_flat_directory(self, tmp_path):
        """Test load_secrets loads secrets from a flat directory."""
        # Arrange
        secrets_dir = tmp_path / "secrets"
        secrets_dir.mkdir()
        (secrets_dir / "secret1").write_text("value1\n")
        (secrets_dir / "secret2").write_text("value2 ")

        # Act
        secrets = NestedSecretsSettingsSource.load_secrets(secrets_dir)

        # Assert
        assert secrets == {"secret1": "value1", "secret2": "value2"}

    def test_load_secrets_from_nested_directory(self, tmp_path):
        """Test load_secrets loads secrets from nested directories."""
        # Arrange
        secrets_dir = tmp_path / "secrets"
        secrets_dir.mkdir()
        nested_dir = secrets_dir / "nested"
        nested_dir.mkdir()
        (secrets_dir / "root_secret").write_text("root_value")
        (nested_dir / "nested_secret").write_text("nested_value")

        # Act
        secrets = NestedSecretsSettingsSource.load_secrets(secrets_dir)

        # Assert
        assert "root_secret" in secrets
        assert secrets["root_secret"] == "root_value"
        # Use os.sep for platform independence
        nested_key = f"nested{os.sep}nested_secret"
        assert nested_key in secrets
        assert secrets[nested_key] == "nested_value"

    def test_load_secrets_strips_whitespace(self, tmp_path):
        """Test load_secrets strips leading and trailing whitespace."""
        # Arrange
        secrets_dir = tmp_path / "secrets"
        secrets_dir.mkdir()
        (secrets_dir / "secret").write_text("  value  \n")

        # Act
        secrets = NestedSecretsSettingsSource.load_secrets(secrets_dir)

        # Assert
        assert secrets["secret"] == "value"

    def test_load_secrets_ignores_directories(self, tmp_path):
        """Test load_secrets ignores directories, only loads files."""
        # Arrange
        secrets_dir = tmp_path / "secrets"
        secrets_dir.mkdir()
        (secrets_dir / "secret").write_text("value")
        nested_dir = secrets_dir / "nested"
        nested_dir.mkdir()

        # Act
        secrets = NestedSecretsSettingsSource.load_secrets(secrets_dir)

        # Assert
        assert "secret" in secrets
        assert "nested" not in secrets


class TestNestedSecretsSettingsSourceRepr:
    """Tests for NestedSecretsSettingsSource.__repr__ method."""

    def test_repr_with_secrets_dir(self, tmp_path):
        """Test __repr__ returns correct representation with secrets_dir."""
        # Arrange
        secrets_dir = tmp_path / "secrets"
        secrets_dir.mkdir()
        source = NestedSecretsSettingsSource(
            SimpleSettings, secrets_dir=secrets_dir
        )

        # Act
        repr_str = repr(source)

        # Assert
        assert "NestedSecretsSettingsSource" in repr_str
        assert "secrets_dir=" in repr_str

    def test_repr_with_none_secrets_dir(self):
        """Test __repr__ returns correct representation with None secrets_dir."""
        # Arrange
        source = NestedSecretsSettingsSource(
            SimpleSettings, secrets_dir=None
        )

        # Act
        repr_str = repr(source)

        # Assert
        assert "NestedSecretsSettingsSource" in repr_str
        assert "secrets_dir=None" in repr_str
