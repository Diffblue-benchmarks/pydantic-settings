"""Tests for NestedSecretsSettingsSource."""

import os
import warnings
from pathlib import Path
from typing import Optional

import pytest

from pydantic_settings import BaseSettings
from pydantic_settings.exceptions import SettingsError
from pydantic_settings.sources.providers.nested_secrets import (
    SECRETS_DIR_MAX_SIZE,
    NestedSecretsSettingsSource,
    first_not_none,
)
from pydantic_settings.sources.providers.secrets import SecretsSettingsSource


class SimpleSettings(BaseSettings):
    """Simple settings model for testing."""

    api_key: str = ''
    database_url: str = ''
    optional_value: Optional[str] = None


class NestedSettings(BaseSettings):
    """Nested settings model for testing."""

    db_host: str = ''
    db_port: int = 5432
    db_user: str = ''


class TestFirstNotNone:
    """Tests for first_not_none helper function."""

    def test_first_not_none_returns_first_non_none(self) -> None:
        """Test that first_not_none returns the first non-None value."""
        result = first_not_none(None, 'first', 'second')
        assert result == 'first'

    def test_first_not_none_all_none_returns_none(self) -> None:
        """Test that first_not_none returns None when all values are None."""
        result = first_not_none(None, None, None)
        assert result is None

    def test_first_not_none_first_value_not_none(self) -> None:
        """Test that first_not_none returns the first argument if not None."""
        result = first_not_none('value', None, 'other')
        assert result == 'value'

    def test_first_not_none_empty_returns_none(self) -> None:
        """Test that first_not_none returns None with no arguments."""
        result = first_not_none()
        assert result is None

    def test_first_not_none_with_falsy_values(self) -> None:
        """Test that first_not_none distinguishes None from other falsy values."""
        result = first_not_none(None, 0, False, '')
        assert result == 0


class TestNestedSecretsSettingsSourceInit:
    """Tests for NestedSecretsSettingsSource.__init__."""

    def test_init_with_secrets_settings_source(self, tmp_path: Path) -> None:
        """Test initialization with a SecretsSettingsSource instance."""
        file_secret_settings = SecretsSettingsSource(SimpleSettings, secrets_dir=tmp_path)
        source = NestedSecretsSettingsSource(file_secret_settings)
        assert source.secrets_dir == tmp_path

    def test_init_with_settings_cls(self, tmp_path: Path) -> None:
        """Test initialization with a settings class directly."""
        source = NestedSecretsSettingsSource(
            SimpleSettings,  # type: ignore[arg-type]
            secrets_dir=tmp_path,
        )
        assert source.secrets_dir == tmp_path

    def test_init_with_none_secrets_dir(self) -> None:
        """Test initialization with None secrets_dir."""
        file_secret_settings = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
        source = NestedSecretsSettingsSource(file_secret_settings, secrets_dir=None)
        assert source.secrets_dir is None
        assert source.env_vars == {}

    def test_init_with_multiple_secrets_dirs(self, tmp_path: Path) -> None:
        """Test initialization with multiple secrets directories."""
        dir1 = tmp_path / 'secrets1'
        dir2 = tmp_path / 'secrets2'
        dir1.mkdir()
        dir2.mkdir()
        file_secret_settings = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
        source = NestedSecretsSettingsSource(
            file_secret_settings, secrets_dir=[dir1, dir2]
        )
        assert len(source.secrets_paths) == 2

    def test_init_secrets_dir_missing_ok(self, tmp_path: Path) -> None:
        """Test initialization with non-existent secrets_dir and missing='ok'."""
        nonexistent = tmp_path / 'nonexistent'
        file_secret_settings = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
        source = NestedSecretsSettingsSource(
            file_secret_settings,
            secrets_dir=nonexistent,
            secrets_dir_missing='ok',
        )
        assert source.secrets_dir == nonexistent

    def test_init_secrets_dir_missing_warn(self, tmp_path: Path) -> None:
        """Test initialization with non-existent secrets_dir and missing='warn'."""
        nonexistent = tmp_path / 'nonexistent'
        file_secret_settings = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            source = NestedSecretsSettingsSource(
                file_secret_settings,
                secrets_dir=nonexistent,
                secrets_dir_missing='warn',
            )
            assert len(w) == 1
            assert 'does not exist' in str(w[0].message)

    def test_init_secrets_dir_missing_error(self, tmp_path: Path) -> None:
        """Test initialization with non-existent secrets_dir and missing='error'."""
        nonexistent = tmp_path / 'nonexistent'
        file_secret_settings = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
        with pytest.raises(SettingsError) as exc_info:
            NestedSecretsSettingsSource(
                file_secret_settings,
                secrets_dir=nonexistent,
                secrets_dir_missing='error',
            )
        assert 'does not exist' in str(exc_info.value)

    def test_init_invalid_secrets_dir_missing_value(self, tmp_path: Path) -> None:
        """Test initialization with invalid secrets_dir_missing value."""
        file_secret_settings = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
        with pytest.raises(SettingsError) as exc_info:
            NestedSecretsSettingsSource(
                file_secret_settings,
                secrets_dir=tmp_path,
                secrets_dir_missing='invalid',  # type: ignore[arg-type]
            )
        assert 'invalid secrets_dir_missing value' in str(exc_info.value)

    def test_init_with_case_sensitive(self, tmp_path: Path) -> None:
        """Test initialization with case_sensitive parameter."""
        file_secret_settings = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
        source = NestedSecretsSettingsSource(
            file_secret_settings,
            secrets_dir=tmp_path,
            secrets_case_sensitive=True,
        )
        assert source.case_sensitive is True

    def test_init_with_secrets_prefix(self, tmp_path: Path) -> None:
        """Test initialization with secrets_prefix parameter."""
        file_secret_settings = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
        source = NestedSecretsSettingsSource(
            file_secret_settings,
            secrets_dir=tmp_path,
            secrets_prefix='APP_',
        )
        assert source.secrets_prefix == 'APP_'

    def test_init_with_env_prefix_fallback(self, tmp_path: Path) -> None:
        """Test initialization falls back to env_prefix when secrets_prefix is None."""
        file_secret_settings = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
        source = NestedSecretsSettingsSource(
            file_secret_settings,
            secrets_dir=tmp_path,
            env_prefix='FALLBACK_',
        )
        assert source.secrets_prefix == 'FALLBACK_'

    def test_init_with_secrets_nested_delimiter(self, tmp_path: Path) -> None:
        """Test initialization with secrets_nested_delimiter parameter."""
        file_secret_settings = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
        source = NestedSecretsSettingsSource(
            file_secret_settings,
            secrets_dir=tmp_path,
            secrets_nested_delimiter='__',
        )
        assert source.secrets_nested_delimiter == '__'

    def test_init_with_secrets_nested_subdir(self, tmp_path: Path) -> None:
        """Test initialization with secrets_nested_subdir parameter."""
        file_secret_settings = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
        source = NestedSecretsSettingsSource(
            file_secret_settings,
            secrets_dir=tmp_path,
            secrets_nested_subdir=True,
        )
        assert source.secrets_nested_subdir is True
        assert source.secrets_nested_delimiter == os.sep

    def test_init_mutually_exclusive_nested_options(self, tmp_path: Path) -> None:
        """Test that secrets_nested_delimiter and secrets_nested_subdir are mutually exclusive."""
        file_secret_settings = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
        with pytest.raises(SettingsError) as exc_info:
            NestedSecretsSettingsSource(
                file_secret_settings,
                secrets_dir=tmp_path,
                secrets_nested_delimiter='__',
                secrets_nested_subdir=True,
            )
        assert 'mutually exclusive' in str(exc_info.value)

    def test_init_with_secrets_dir_max_size(self, tmp_path: Path) -> None:
        """Test initialization with custom secrets_dir_max_size."""
        file_secret_settings = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
        custom_max_size = 1024 * 1024
        source = NestedSecretsSettingsSource(
            file_secret_settings,
            secrets_dir=tmp_path,
            secrets_dir_max_size=custom_max_size,
        )
        assert source.secrets_dir_max_size == custom_max_size

    def test_init_default_secrets_dir_max_size(self, tmp_path: Path) -> None:
        """Test that default secrets_dir_max_size is SECRETS_DIR_MAX_SIZE."""
        file_secret_settings = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
        source = NestedSecretsSettingsSource(
            file_secret_settings,
            secrets_dir=tmp_path,
        )
        assert source.secrets_dir_max_size == SECRETS_DIR_MAX_SIZE


class TestNestedSecretsSettingsSourceValidate:
    """Tests for NestedSecretsSettingsSource.validate_secrets_path."""

    def test_validate_secrets_path_not_dir(self, tmp_path: Path) -> None:
        """Test that validate_secrets_path raises error when path is a file."""
        secret_file = tmp_path / 'secret_file'
        secret_file.write_text('value')
        file_secret_settings = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
        with pytest.raises(SettingsError) as exc_info:
            NestedSecretsSettingsSource(
                file_secret_settings,
                secrets_dir=secret_file,
            )
        assert 'must reference a directory' in str(exc_info.value)

    def test_validate_secrets_path_size_exceeds_max(self, tmp_path: Path) -> None:
        """Test that validate_secrets_path raises error when dir size exceeds max."""
        secrets_dir = tmp_path / 'secrets'
        secrets_dir.mkdir()
        large_file = secrets_dir / 'large_secret'
        large_file.write_text('x' * 100)
        file_secret_settings = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
        with pytest.raises(SettingsError) as exc_info:
            NestedSecretsSettingsSource(
                file_secret_settings,
                secrets_dir=secrets_dir,
                secrets_dir_max_size=50,
            )
        assert 'secrets_dir size is above' in str(exc_info.value)


class TestNestedSecretsSettingsSourceLoadSecrets:
    """Tests for NestedSecretsSettingsSource.load_secrets."""

    def test_load_secrets_single_file(self, tmp_path: Path) -> None:
        """Test load_secrets loads a single secret file."""
        (tmp_path / 'api_key').write_text('secret123')
        result = NestedSecretsSettingsSource.load_secrets(tmp_path)
        assert result == {'api_key': 'secret123'}

    def test_load_secrets_multiple_files(self, tmp_path: Path) -> None:
        """Test load_secrets loads multiple secret files."""
        (tmp_path / 'api_key').write_text('key123')
        (tmp_path / 'db_password').write_text('pass456')
        result = NestedSecretsSettingsSource.load_secrets(tmp_path)
        assert result == {'api_key': 'key123', 'db_password': 'pass456'}

    def test_load_secrets_nested_files(self, tmp_path: Path) -> None:
        """Test load_secrets loads nested secret files."""
        subdir = tmp_path / 'subdir'
        subdir.mkdir()
        (subdir / 'nested_secret').write_text('nested_value')
        result = NestedSecretsSettingsSource.load_secrets(tmp_path)
        expected_key = str(Path('subdir') / 'nested_secret')
        assert result[expected_key] == 'nested_value'

    def test_load_secrets_strips_whitespace(self, tmp_path: Path) -> None:
        """Test load_secrets strips whitespace from secret values."""
        (tmp_path / 'secret').write_text('  value with spaces  \n')
        result = NestedSecretsSettingsSource.load_secrets(tmp_path)
        assert result == {'secret': 'value with spaces'}

    def test_load_secrets_empty_dir(self, tmp_path: Path) -> None:
        """Test load_secrets returns empty dict for empty directory."""
        result = NestedSecretsSettingsSource.load_secrets(tmp_path)
        assert result == {}


class TestNestedSecretsSettingsSourceRepr:
    """Tests for NestedSecretsSettingsSource.__repr__."""

    def test_repr_with_secrets_dir(self, tmp_path: Path) -> None:
        """Test __repr__ shows secrets_dir."""
        file_secret_settings = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
        source = NestedSecretsSettingsSource(
            file_secret_settings, secrets_dir=tmp_path
        )
        result = repr(source)
        assert 'NestedSecretsSettingsSource' in result
        assert str(tmp_path) in result

    def test_repr_with_none_secrets_dir(self) -> None:
        """Test __repr__ shows None for secrets_dir."""
        file_secret_settings = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
        source = NestedSecretsSettingsSource(
            file_secret_settings, secrets_dir=None
        )
        result = repr(source)
        assert 'NestedSecretsSettingsSource' in result
        assert 'None' in result


class TestNestedSecretsSettingsSourceIntegration:
    """Integration tests for NestedSecretsSettingsSource."""

    def test_load_simple_secrets(self, tmp_path: Path) -> None:
        """Test loading simple secrets from directory."""
        (tmp_path / 'api_key').write_text('integration-key')
        (tmp_path / 'database_url').write_text('postgres://localhost/db')
        file_secret_settings = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
        source = NestedSecretsSettingsSource(
            file_secret_settings, secrets_dir=tmp_path
        )
        assert 'api_key' in source.env_vars
        assert source.env_vars['api_key'] == 'integration-key'

    def test_load_secrets_with_nested_delimiter(self, tmp_path: Path) -> None:
        """Test loading secrets with nested delimiter."""
        (tmp_path / 'db__host').write_text('localhost')
        (tmp_path / 'db__port').write_text('5432')
        file_secret_settings = SecretsSettingsSource(NestedSettings, secrets_dir=None)
        source = NestedSecretsSettingsSource(
            file_secret_settings,
            secrets_dir=tmp_path,
            secrets_nested_delimiter='__',
        )
        assert 'db__host' in source.env_vars
        assert 'db__port' in source.env_vars

    def test_load_secrets_from_multiple_dirs(self, tmp_path: Path) -> None:
        """Test loading secrets from multiple directories with override."""
        dir1 = tmp_path / 'secrets1'
        dir2 = tmp_path / 'secrets2'
        dir1.mkdir()
        dir2.mkdir()
        (dir1 / 'api_key').write_text('key1')
        (dir2 / 'api_key').write_text('key2')
        file_secret_settings = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
        source = NestedSecretsSettingsSource(
            file_secret_settings, secrets_dir=[dir1, dir2]
        )
        assert source.env_vars['api_key'] == 'key2'

    def test_load_nested_subdir_secrets(self, tmp_path: Path) -> None:
        """Test loading secrets with nested subdirectory structure."""
        subdir = tmp_path / 'db'
        subdir.mkdir()
        (subdir / 'host').write_text('localhost')
        (subdir / 'port').write_text('5432')
        file_secret_settings = SecretsSettingsSource(NestedSettings, secrets_dir=None)
        source = NestedSecretsSettingsSource(
            file_secret_settings,
            secrets_dir=tmp_path,
            secrets_nested_subdir=True,
        )
        expected_key = f'db{os.sep}host'
        assert expected_key in source.env_vars
        assert source.env_vars[expected_key] == 'localhost'

    def test_case_insensitive_secrets(self, tmp_path: Path) -> None:
        """Test loading secrets with case insensitivity."""
        (tmp_path / 'API_KEY').write_text('uppercase-key')
        file_secret_settings = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
        source = NestedSecretsSettingsSource(
            file_secret_settings,
            secrets_dir=tmp_path,
            secrets_case_sensitive=False,
        )
        assert 'api_key' in source.env_vars

    def test_case_sensitive_secrets(self, tmp_path: Path) -> None:
        """Test loading secrets with case sensitivity."""
        (tmp_path / 'API_KEY').write_text('uppercase-key')
        file_secret_settings = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
        source = NestedSecretsSettingsSource(
            file_secret_settings,
            secrets_dir=tmp_path,
            secrets_case_sensitive=True,
        )
        assert 'API_KEY' in source.env_vars
        assert 'api_key' not in source.env_vars

    def test_secrets_with_prefix(self, tmp_path: Path) -> None:
        """Test loading secrets with prefix."""
        (tmp_path / 'APP_api_key').write_text('prefixed-key')
        file_secret_settings = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
        source = NestedSecretsSettingsSource(
            file_secret_settings,
            secrets_dir=tmp_path,
            secrets_prefix='APP_',
        )
        # Default is case insensitive, so keys are lowercased
        assert 'app_api_key' in source.env_vars
        assert source.env_vars['app_api_key'] == 'prefixed-key'
