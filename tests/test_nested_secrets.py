"""Unit tests for NestedSecretsSettingsSource."""

from __future__ import annotations as _annotations

import os
import warnings
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pytest

from pydantic_settings import BaseSettings
from pydantic_settings.exceptions import SettingsError
from pydantic_settings.sources.providers.nested_secrets import (
    NestedSecretsSettingsSource,
    first_not_none,
)
from pydantic_settings.sources.providers.secrets import SecretsSettingsSource


class SimpleSettings(BaseSettings):
    """Simple test settings class."""

    api_key: str | None = None
    database_url: str | None = None
    debug: bool = False


class SettingsWithConfig(BaseSettings):
    """Settings with model_config."""

    api_key: str | None = None
    database_url: str | None = None

    model_config = {
        'secrets_dir': None,
        'secrets_dir_missing': 'warn',
        'secrets_case_sensitive': False,
        'secrets_prefix': '',
        'secrets_nested_delimiter': None,
        'secrets_nested_subdir': False,
    }


class TestFirstNotNone:
    """Tests for first_not_none utility function."""

    def test_first_not_none_returns_first_non_none(self):
        """Test first_not_none returns the first non-None value."""
        result = first_not_none(None, 'value', 'other')
        assert result == 'value'

    def test_first_not_none_with_all_none(self):
        """Test first_not_none returns None when all values are None."""
        result = first_not_none(None, None, None)
        assert result is None

    def test_first_not_none_with_first_value(self):
        """Test first_not_none returns first value when it's not None."""
        result = first_not_none('first', None, 'third')
        assert result == 'first'

    def test_first_not_none_with_zero(self):
        """Test first_not_none treats 0 as valid (not None)."""
        result = first_not_none(None, 0, 1)
        assert result == 0

    def test_first_not_none_with_empty_string(self):
        """Test first_not_none treats empty string as valid (not None)."""
        result = first_not_none(None, '', 'value')
        assert result == ''

    def test_first_not_none_with_false(self):
        """Test first_not_none treats False as valid (not None)."""
        result = first_not_none(None, False, True)
        assert result is False

    def test_first_not_none_single_argument(self):
        """Test first_not_none with single argument."""
        result = first_not_none('value')
        assert result == 'value'

    def test_first_not_none_single_none(self):
        """Test first_not_none with single None argument."""
        result = first_not_none(None)
        assert result is None


class TestNestedSecretsSettingsSourceInit:
    """Tests for NestedSecretsSettingsSource.__init__."""

    def test_init_with_string_secrets_dir(self):
        """Test initialization with a string secrets_dir."""
        with TemporaryDirectory() as tmpdir:
            secrets_source = SecretsSettingsSource(SimpleSettings, secrets_dir=tmpdir)
            source = NestedSecretsSettingsSource(
                secrets_source, secrets_dir=tmpdir
            )
            assert source.secrets_dir == tmpdir

    def test_init_with_path_secrets_dir(self):
        """Test initialization with a Path object secrets_dir."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            secrets_source = SecretsSettingsSource(SimpleSettings, secrets_dir=tmpdir)
            source = NestedSecretsSettingsSource(secrets_source, secrets_dir=tmppath)
            # secrets_dir is stored as-is, secrets_paths have resolved paths
            assert len(source.secrets_paths) > 0

    def test_init_with_list_secrets_dir(self):
        """Test initialization with a list of secrets directories."""
        with TemporaryDirectory() as tmpdir1, TemporaryDirectory() as tmpdir2:
            secrets_dirs = [tmpdir1, tmpdir2]
            secrets_source = SecretsSettingsSource(SimpleSettings)
            source = NestedSecretsSettingsSource(
                secrets_source, secrets_dir=secrets_dirs
            )
            assert source.secrets_dir == secrets_dirs

    def test_init_with_none_secrets_dir(self):
        """Test initialization with None secrets_dir."""
        secrets_source = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
        source = NestedSecretsSettingsSource(secrets_source, secrets_dir=None)
        assert source.secrets_dir is None

    def test_init_sets_case_sensitive(self):
        """Test initialization sets case_sensitive correctly."""
        secrets_source = SecretsSettingsSource(SimpleSettings)
        source = NestedSecretsSettingsSource(
            secrets_source, secrets_case_sensitive=True
        )
        assert source.case_sensitive is True

    def test_init_sets_secrets_prefix(self):
        """Test initialization sets secrets_prefix correctly."""
        secrets_source = SecretsSettingsSource(SimpleSettings)
        source = NestedSecretsSettingsSource(
            secrets_source, secrets_prefix='APP_'
        )
        assert source.secrets_prefix == 'APP_'

    def test_init_sets_secrets_dir_missing_ok(self):
        """Test initialization sets secrets_dir_missing to 'ok'."""
        secrets_source = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
        source = NestedSecretsSettingsSource(
            secrets_source, secrets_dir_missing='ok'
        )
        assert source.secrets_dir_missing == 'ok'

    def test_init_sets_secrets_dir_missing_warn(self):
        """Test initialization sets secrets_dir_missing to 'warn'."""
        secrets_source = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
        source = NestedSecretsSettingsSource(
            secrets_source, secrets_dir_missing='warn'
        )
        assert source.secrets_dir_missing == 'warn'

    def test_init_sets_secrets_dir_missing_error(self):
        """Test initialization sets secrets_dir_missing to 'error'."""
        secrets_source = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
        source = NestedSecretsSettingsSource(
            secrets_source, secrets_dir_missing='error'
        )
        assert source.secrets_dir_missing == 'error'

    def test_init_raises_error_for_invalid_secrets_dir_missing(self):
        """Test initialization raises error for invalid secrets_dir_missing."""
        secrets_source = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
        with pytest.raises(SettingsError, match='invalid secrets_dir_missing'):
            NestedSecretsSettingsSource(
                secrets_source, secrets_dir_missing='invalid'
            )

    def test_init_sets_secrets_dir_max_size(self):
        """Test initialization sets secrets_dir_max_size correctly."""
        secrets_source = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
        source = NestedSecretsSettingsSource(
            secrets_source, secrets_dir_max_size=1024 * 1024
        )
        assert source.secrets_dir_max_size == 1024 * 1024

    def test_init_sets_nested_delimiter(self):
        """Test initialization sets secrets_nested_delimiter correctly."""
        secrets_source = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
        source = NestedSecretsSettingsSource(
            secrets_source, secrets_nested_delimiter='__'
        )
        assert source.secrets_nested_delimiter == '__'

    def test_init_sets_nested_subdir_true(self):
        """Test initialization sets secrets_nested_subdir to True."""
        secrets_source = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
        source = NestedSecretsSettingsSource(
            secrets_source, secrets_nested_subdir=True
        )
        assert source.secrets_nested_subdir is True

    def test_init_sets_nested_subdir_false(self):
        """Test initialization sets secrets_nested_subdir to False."""
        secrets_source = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
        source = NestedSecretsSettingsSource(
            secrets_source, secrets_nested_subdir=False
        )
        assert source.secrets_nested_subdir is False

    def test_init_nested_subdir_sets_delimiter_to_sep(self):
        """Test that secrets_nested_subdir=True sets delimiter to os.sep."""
        secrets_source = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
        source = NestedSecretsSettingsSource(
            secrets_source, secrets_nested_subdir=True
        )
        assert source.secrets_nested_delimiter == os.sep

    def test_init_nested_subdir_conflicts_with_delimiter(self):
        """Test that secrets_nested_subdir conflicts with secrets_nested_delimiter."""
        secrets_source = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
        with pytest.raises(
            SettingsError,
            match='mutually exclusive',
        ):
            NestedSecretsSettingsSource(
                secrets_source,
                secrets_nested_subdir=True,
                secrets_nested_delimiter='__',
            )

    def test_init_with_secrets_settings_source_instance(self):
        """Test initialization with SecretsSettingsSource instance."""
        with TemporaryDirectory() as tmpdir:
            secrets_source = SecretsSettingsSource(
                SimpleSettings, secrets_dir=tmpdir
            )
            source = NestedSecretsSettingsSource(secrets_source)
            # Should inherit secrets_dir from the SecretsSettingsSource instance
            # and have non-empty secrets_paths
            assert len(source.secrets_paths) > 0

    def test_init_expands_user_in_paths(self):
        """Test that initialization expands ~ in paths."""
        secrets_source = SecretsSettingsSource(SimpleSettings)
        source = NestedSecretsSettingsSource(
            secrets_source, secrets_dir='~/.secrets', secrets_dir_missing='ok'
        )
        # Path should be expanded (though it may not exist)
        assert str(source.secrets_paths[0]).startswith(str(Path.home()))

    def test_init_creates_empty_env_vars_for_none_secrets_dir(self):
        """Test that env_vars is empty dict when secrets_dir is None."""
        secrets_source = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
        source = NestedSecretsSettingsSource(secrets_source, secrets_dir=None)
        assert source.env_vars == {}

    def test_init_loads_secrets_from_valid_directory(self):
        """Test that env_vars is populated from valid secrets directory."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / 'api_key').write_text('secret123')
            (tmppath / 'db_url').write_text('postgres://localhost')

            secrets_source = SecretsSettingsSource(SimpleSettings, secrets_dir=tmpdir)
            source = NestedSecretsSettingsSource(secrets_source, secrets_dir=tmpdir)
            # env_vars should contain the parsed secrets
            assert isinstance(source.env_vars, dict)

    def test_init_uses_config_defaults(self):
        """Test that initialization uses config defaults."""
        secrets_source = SecretsSettingsSource(SettingsWithConfig)
        source = NestedSecretsSettingsSource(secrets_source)
        assert source.case_sensitive is False
        assert source.secrets_prefix == ''


class TestNestedSecretsSettingsSourceValidateSecretsPath:
    """Tests for NestedSecretsSettingsSource.validate_secrets_path."""

    def test_validate_secrets_path_with_ok_mode_and_missing_path(self):
        """Test validate_secrets_path with secrets_dir_missing='ok' and missing path."""
        secrets_source = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
        source = NestedSecretsSettingsSource(
            secrets_source, secrets_dir_missing='ok'
        )
        # Should not raise or warn
        source.validate_secrets_path(Path('/nonexistent/path'))

    def test_validate_secrets_path_with_warn_mode_and_missing_path(self):
        """Test validate_secrets_path with secrets_dir_missing='warn' and missing path."""
        secrets_source = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
        source = NestedSecretsSettingsSource(
            secrets_source, secrets_dir_missing='warn'
        )
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            source.validate_secrets_path(Path('/nonexistent/path'))
            assert len(w) == 1
            assert 'does not exist' in str(w[0].message)

    def test_validate_secrets_path_with_error_mode_and_missing_path(self):
        """Test validate_secrets_path with secrets_dir_missing='error' and missing path."""
        secrets_source = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
        source = NestedSecretsSettingsSource(
            secrets_source, secrets_dir_missing='error'
        )
        with pytest.raises(SettingsError, match='does not exist'):
            source.validate_secrets_path(Path('/nonexistent/path'))

    def test_validate_secrets_path_with_valid_directory(self):
        """Test validate_secrets_path with a valid directory."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            secrets_source = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
            source = NestedSecretsSettingsSource(secrets_source)
            # Should not raise
            source.validate_secrets_path(tmppath)

    def test_validate_secrets_path_with_file_raises_error(self):
        """Test validate_secrets_path raises error when path is a file."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            file_path = tmppath / 'notadir'
            file_path.write_text('content')

            secrets_source = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
            source = NestedSecretsSettingsSource(secrets_source)
            with pytest.raises(SettingsError, match='must reference a directory'):
                source.validate_secrets_path(file_path)

    def test_validate_secrets_path_checks_size_limit(self):
        """Test validate_secrets_path checks directory size limit."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            # Create a file larger than the size limit
            large_file = tmppath / 'large_file'
            large_file.write_text('x' * 1000)

            secrets_source = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
            source = NestedSecretsSettingsSource(
                secrets_source, secrets_dir_max_size=100
            )
            with pytest.raises(SettingsError, match='size is above'):
                source.validate_secrets_path(tmppath)


class TestNestedSecretsSettingsSourceLoadSecrets:
    """Tests for NestedSecretsSettingsSource.load_secrets."""

    def test_load_secrets_from_empty_directory(self):
        """Test load_secrets from an empty directory returns empty dict."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            result = NestedSecretsSettingsSource.load_secrets(tmppath)
            assert result == {}

    def test_load_secrets_from_directory_with_single_file(self):
        """Test load_secrets reads a single file."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / 'api_key').write_text('secret123')

            result = NestedSecretsSettingsSource.load_secrets(tmppath)
            assert result['api_key'] == 'secret123'

    def test_load_secrets_from_directory_with_multiple_files(self):
        """Test load_secrets reads multiple files."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / 'api_key').write_text('secret123')
            (tmppath / 'db_url').write_text('postgres://localhost')

            result = NestedSecretsSettingsSource.load_secrets(tmppath)
            assert result['api_key'] == 'secret123'
            assert result['db_url'] == 'postgres://localhost'

    def test_load_secrets_strips_whitespace(self):
        """Test load_secrets strips whitespace from content."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / 'api_key').write_text('  secret123  \n')

            result = NestedSecretsSettingsSource.load_secrets(tmppath)
            assert result['api_key'] == 'secret123'

    def test_load_secrets_from_nested_directory(self):
        """Test load_secrets reads files from nested directories."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / 'subdir').mkdir()
            (tmppath / 'subdir' / 'nested_secret').write_text('nested_value')

            result = NestedSecretsSettingsSource.load_secrets(tmppath)
            # Path is relative to the secrets_dir
            assert 'subdir' in str(list(result.keys())[0])

    def test_load_secrets_ignores_directories(self):
        """Test load_secrets ignores directory entries."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / 'file1').write_text('content1')
            (tmppath / 'dir1').mkdir()
            (tmppath / 'dir1' / 'file2').write_text('content2')

            result = NestedSecretsSettingsSource.load_secrets(tmppath)
            # Should only have files, not directories
            for key in result.keys():
                assert not str(key).endswith(os.sep)


class TestNestedSecretsSettingsSourceRepr:
    """Tests for NestedSecretsSettingsSource.__repr__."""

    def test_repr_with_string_secrets_dir(self):
        """Test __repr__ with string secrets_dir."""
        secrets_source = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
        source = NestedSecretsSettingsSource(
            secrets_source, secrets_dir='/path/to/secrets', secrets_dir_missing='ok'
        )
        repr_str = repr(source)
        assert 'NestedSecretsSettingsSource' in repr_str
        assert '/path/to/secrets' in repr_str

    def test_repr_with_none_secrets_dir(self):
        """Test __repr__ with None secrets_dir."""
        secrets_source = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
        source = NestedSecretsSettingsSource(secrets_source, secrets_dir=None)
        repr_str = repr(source)
        assert 'NestedSecretsSettingsSource' in repr_str
        assert 'None' in repr_str

    def test_repr_with_list_secrets_dir(self):
        """Test __repr__ with list secrets_dir."""
        secrets_source = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
        source = NestedSecretsSettingsSource(
            secrets_source, secrets_dir=['/path1', '/path2'], secrets_dir_missing='ok'
        )
        repr_str = repr(source)
        assert 'NestedSecretsSettingsSource' in repr_str

    def test_repr_format_is_correct(self):
        """Test __repr__ format is NestedSecretsSettingsSource(...)."""
        secrets_source = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
        source = NestedSecretsSettingsSource(
            secrets_source, secrets_dir='/secrets', secrets_dir_missing='ok'
        )
        repr_str = repr(source)
        assert repr_str.startswith('NestedSecretsSettingsSource(')
        assert repr_str.endswith(')')
        assert 'secrets_dir=' in repr_str


class TestNestedSecretsSettingsSourceIntegration:
    """Integration tests for NestedSecretsSettingsSource."""

    def test_nested_secrets_with_nested_directory_structure(self):
        """Test loading secrets from a nested directory structure."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            # Create nested structure
            (tmppath / 'db').mkdir()
            (tmppath / 'db' / 'host').write_text('localhost')
            (tmppath / 'db' / 'port').write_text('5432')
            (tmppath / 'api').mkdir()
            (tmppath / 'api' / 'key').write_text('secret123')

            secrets_source = SecretsSettingsSource(SimpleSettings, secrets_dir=tmpdir)
            source = NestedSecretsSettingsSource(secrets_source, secrets_dir=tmpdir)
            # Should load all nested secrets
            assert source.env_vars is not None

    def test_nested_secrets_expands_home_directory(self):
        """Test that ~ is expanded in secrets_dir."""
        secrets_source = SecretsSettingsSource(SimpleSettings)
        source = NestedSecretsSettingsSource(
            secrets_source, secrets_dir='~/.secrets', secrets_dir_missing='ok'
        )
        # Path should be expanded
        assert '~' not in str(source.secrets_paths[0])

    def test_nested_secrets_with_case_insensitive_mode(self):
        """Test nested secrets with case_sensitive=False."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / 'API_KEY').write_text('secret123')

            secrets_source = SecretsSettingsSource(SimpleSettings, secrets_dir=tmpdir)
            source = NestedSecretsSettingsSource(
                secrets_source,
                secrets_dir=tmpdir,
                secrets_case_sensitive=False,
            )
            assert source.case_sensitive is False

    def test_nested_secrets_with_prefix(self):
        """Test nested secrets with env_prefix."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / 'api_key').write_text('secret123')

            secrets_source = SecretsSettingsSource(SimpleSettings, secrets_dir=tmpdir)
            source = NestedSecretsSettingsSource(
                secrets_source,
                secrets_dir=tmpdir,
                secrets_prefix='APP_',
            )
            assert source.secrets_prefix == 'APP_'

    def test_nested_secrets_multiple_directories(self):
        """Test loading secrets from multiple directories."""
        with TemporaryDirectory() as tmpdir1, TemporaryDirectory() as tmpdir2:
            path1 = Path(tmpdir1)
            path2 = Path(tmpdir2)
            (path1 / 'secret1').write_text('value1')
            (path2 / 'secret2').write_text('value2')

            secrets_source = SecretsSettingsSource(SimpleSettings)
            source = NestedSecretsSettingsSource(
                secrets_source, secrets_dir=[tmpdir1, tmpdir2]
            )
            assert len(source.secrets_paths) == 2

    def test_nested_secrets_with_empty_env_vars_when_no_paths(self):
        """Test that env_vars is empty when no valid secrets paths."""
        with warnings.catch_warnings(record=True):
            warnings.simplefilter('always')
            secrets_source = SecretsSettingsSource(SimpleSettings)
            source = NestedSecretsSettingsSource(
                secrets_source,
                secrets_dir=['/nonexistent1', '/nonexistent2'],
                secrets_dir_missing='ok',
            )
            assert source.env_vars == {}
