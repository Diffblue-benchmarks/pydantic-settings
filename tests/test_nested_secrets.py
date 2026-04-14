"""Tests for NestedSecretsSettingsSource."""

from __future__ import annotations

import os
import warnings
from pathlib import Path

import pytest

from pydantic_settings import BaseSettings
from pydantic_settings.exceptions import SettingsError
from pydantic_settings.sources.providers.nested_secrets import (
    NestedSecretsSettingsSource,
    first_not_none,
)
from pydantic_settings.sources.providers.secrets import SecretsSettingsSource


class SimpleSettings(BaseSettings):
    """Simple settings for testing."""

    username: str = 'default_user'
    password: str = 'default_pass'
    api_key: str | None = None


class SettingsWithConfig(BaseSettings):
    """Settings with various config options."""

    username: str = 'default_user'

    model_config = {
        'secrets_dir': '/tmp/test_secrets',
        'secrets_dir_missing': 'error',
        'secrets_dir_max_size': 1024,
        'secrets_case_sensitive': True,
        'secrets_prefix': 'MY_',
        'secrets_nested_delimiter': '__',
    }


class SettingsWithNestedSubdir(BaseSettings):
    """Settings with nested subdir config."""

    username: str = 'default_user'

    model_config = {
        'secrets_nested_subdir': True,
    }


def test_first_not_none_returns_first_non_none() -> None:
    """Test first_not_none returns the first non-None value."""
    result = first_not_none(None, None, 'first', 'second')

    assert result == 'first'


def test_first_not_none_returns_none_when_all_none() -> None:
    """Test first_not_none returns None when all arguments are None."""
    result = first_not_none(None, None, None)

    assert result is None


def test_first_not_none_returns_first_value_even_if_falsy() -> None:
    """Test first_not_none returns first non-None value even if it's falsy."""
    result = first_not_none(None, 0, 'second')

    assert result == 0


def test_init_with_secrets_settings_source(tmp_path: Path) -> None:
    """Test initialization with SecretsSettingsSource instance."""
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()

    secrets_source = SecretsSettingsSource(SimpleSettings, secrets_dir=secrets_dir)
    source = NestedSecretsSettingsSource(secrets_source)

    assert source.secrets_dir == secrets_dir
    assert source.secrets_paths == [secrets_dir.resolve()]


def test_init_with_settings_cls_directly(tmp_path: Path) -> None:
    """Test initialization with settings class directly."""
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()

    source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir=secrets_dir)

    assert source.secrets_dir == secrets_dir
    assert source.secrets_paths == [secrets_dir.resolve()]


def test_init_with_none_secrets_dir() -> None:
    """Test initialization with None secrets_dir."""
    source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir=None)

    assert source.secrets_dir is None
    assert source.secrets_paths == []
    assert source.env_vars == {}


def test_init_with_string_secrets_dir(tmp_path: Path) -> None:
    """Test initialization with string secrets_dir."""
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()

    source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir=str(secrets_dir))

    assert source.secrets_paths == [secrets_dir.resolve()]


def test_init_with_list_of_paths(tmp_path: Path) -> None:
    """Test initialization with a list of directory paths."""
    secrets_dir1 = tmp_path / 'secrets1'
    secrets_dir1.mkdir()
    secrets_dir2 = tmp_path / 'secrets2'
    secrets_dir2.mkdir()

    source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir=[secrets_dir1, secrets_dir2])

    assert len(source.secrets_paths) == 2
    assert secrets_dir1.resolve() in source.secrets_paths
    assert secrets_dir2.resolve() in source.secrets_paths


def test_init_with_config_options(tmp_path: Path) -> None:
    """Test initialization uses config options from settings."""
    secrets_dir = tmp_path / 'test_secrets'
    secrets_dir.mkdir()

    # Create a custom settings class with the tmp_path
    class SettingsWithTmpConfig(BaseSettings):
        username: str = 'default_user'
        model_config = {
            'secrets_dir': str(secrets_dir),
            'secrets_dir_missing': 'error',
            'secrets_dir_max_size': 1024,
            'secrets_case_sensitive': True,
            'secrets_prefix': 'MY_',
            'secrets_nested_delimiter': '__',
        }

    source = NestedSecretsSettingsSource(SettingsWithTmpConfig)

    assert source.secrets_dir_missing == 'error'
    assert source.secrets_dir_max_size == 1024
    assert source.case_sensitive is True
    assert source.secrets_prefix == 'MY_'
    assert source.secrets_nested_delimiter == '__'


def test_init_with_explicit_parameters_override_config(tmp_path: Path) -> None:
    """Test explicit parameters override config values."""
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()

    source = NestedSecretsSettingsSource(
        SettingsWithConfig,
        secrets_dir=secrets_dir,
        secrets_dir_missing='ok',
        secrets_dir_max_size=2048,
        secrets_case_sensitive=False,
        secrets_prefix='OTHER_',
        secrets_nested_delimiter='--',
    )

    assert source.secrets_dir == secrets_dir
    assert source.secrets_dir_missing == 'ok'
    assert source.secrets_dir_max_size == 2048
    assert source.case_sensitive is False
    assert source.secrets_prefix == 'OTHER_'
    assert source.secrets_nested_delimiter == '--'


def test_init_with_invalid_secrets_dir_missing() -> None:
    """Test initialization raises error with invalid secrets_dir_missing."""
    with pytest.raises(SettingsError, match='invalid secrets_dir_missing value'):
        NestedSecretsSettingsSource(SimpleSettings, secrets_dir=None, secrets_dir_missing='invalid')


def test_init_with_nested_subdir_sets_delimiter_to_os_sep(tmp_path: Path) -> None:
    """Test nested_subdir option sets delimiter to os.sep."""
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()

    source = NestedSecretsSettingsSource(
        SimpleSettings,
        secrets_dir=secrets_dir,
        secrets_nested_subdir=True,
    )

    assert source.secrets_nested_delimiter == os.sep
    assert source.secrets_nested_subdir is True


def test_init_with_both_nested_delimiter_and_subdir_raises_error(tmp_path: Path) -> None:
    """Test initialization raises error when both nested_delimiter and nested_subdir are set."""
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()

    with pytest.raises(SettingsError, match='mutually exclusive'):
        NestedSecretsSettingsSource(
            SimpleSettings,
            secrets_dir=secrets_dir,
            secrets_nested_delimiter='__',
            secrets_nested_subdir=True,
        )


def test_init_with_config_nested_delimiter_and_subdir_raises_error() -> None:
    """Test initialization raises error when config has both nested_delimiter and nested_subdir is passed."""
    with pytest.raises(SettingsError, match='mutually exclusive'):
        NestedSecretsSettingsSource(
            SettingsWithConfig,
            secrets_nested_subdir=True,
        )


def test_init_with_deprecated_case_sensitive_parameter(tmp_path: Path) -> None:
    """Test initialization with deprecated case_sensitive parameter."""
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()

    source = NestedSecretsSettingsSource(
        SimpleSettings,
        secrets_dir=secrets_dir,
        case_sensitive=True,
    )

    assert source.case_sensitive is True


def test_init_with_deprecated_env_prefix_parameter(tmp_path: Path) -> None:
    """Test initialization with deprecated env_prefix parameter."""
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()

    source = NestedSecretsSettingsSource(
        SimpleSettings,
        secrets_dir=secrets_dir,
        env_prefix='APP_',
    )

    assert source.secrets_prefix == 'APP_'


def test_init_loads_secrets_from_directory(tmp_path: Path) -> None:
    """Test initialization loads secrets from directory."""
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()
    (secrets_dir / 'username').write_text('test_user')
    (secrets_dir / 'password').write_text('test_pass')

    source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir=secrets_dir)

    assert 'username' in source.env_vars
    assert 'password' in source.env_vars


def test_init_loads_secrets_from_multiple_directories(tmp_path: Path) -> None:
    """Test initialization loads secrets from multiple directories."""
    secrets_dir1 = tmp_path / 'secrets1'
    secrets_dir1.mkdir()
    secrets_dir2 = tmp_path / 'secrets2'
    secrets_dir2.mkdir()

    (secrets_dir1 / 'username').write_text('user1')
    (secrets_dir2 / 'password').write_text('pass2')

    source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir=[secrets_dir1, secrets_dir2])

    assert 'username' in source.env_vars
    assert 'password' in source.env_vars


def test_validate_secrets_path_with_nonexistent_dir_ok(tmp_path: Path) -> None:
    """Test validate_secrets_path with nonexistent directory and secrets_dir_missing='ok'."""
    nonexistent_dir = tmp_path / 'nonexistent'
    source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir=None, secrets_dir_missing='ok')

    # Should not raise or warn
    source.validate_secrets_path(nonexistent_dir)


def test_validate_secrets_path_with_nonexistent_dir_warn(tmp_path: Path) -> None:
    """Test validate_secrets_path with nonexistent directory and secrets_dir_missing='warn'."""
    nonexistent_dir = tmp_path / 'nonexistent'
    source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir=None, secrets_dir_missing='warn')

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter('always')
        source.validate_secrets_path(nonexistent_dir)

        assert len(w) == 1
        assert 'does not exist' in str(w[0].message)


def test_validate_secrets_path_with_nonexistent_dir_error(tmp_path: Path) -> None:
    """Test validate_secrets_path with nonexistent directory and secrets_dir_missing='error'."""
    nonexistent_dir = tmp_path / 'nonexistent'
    source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir=None, secrets_dir_missing='error')

    with pytest.raises(SettingsError, match='does not exist'):
        source.validate_secrets_path(nonexistent_dir)


def test_validate_secrets_path_with_file_instead_of_directory(tmp_path: Path) -> None:
    """Test validate_secrets_path raises error when path is a file."""
    secrets_file = tmp_path / 'secrets.txt'
    secrets_file.write_text('secret')

    source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir=None)

    with pytest.raises(SettingsError, match='secrets_dir must reference a directory'):
        source.validate_secrets_path(secrets_file)


def test_validate_secrets_path_with_directory_exceeding_max_size(tmp_path: Path) -> None:
    """Test validate_secrets_path raises error when directory size exceeds max."""
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()
    # Create a file larger than max size (1024 bytes)
    (secrets_dir / 'large_file').write_text('x' * 2000)

    source = NestedSecretsSettingsSource(
        SimpleSettings,
        secrets_dir=None,
        secrets_dir_max_size=1024,
    )

    with pytest.raises(SettingsError, match='secrets_dir size is above'):
        source.validate_secrets_path(secrets_dir)


def test_validate_secrets_path_with_valid_directory(tmp_path: Path) -> None:
    """Test validate_secrets_path succeeds with valid directory."""
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()
    (secrets_dir / 'username').write_text('test_user')

    source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir=None)

    # Should not raise
    source.validate_secrets_path(secrets_dir)


def test_validate_secrets_path_with_nested_files(tmp_path: Path) -> None:
    """Test validate_secrets_path calculates size including nested files."""
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()
    nested_dir = secrets_dir / 'nested'
    nested_dir.mkdir()
    (secrets_dir / 'file1').write_text('x' * 500)
    (nested_dir / 'file2').write_text('x' * 600)

    source = NestedSecretsSettingsSource(
        SimpleSettings,
        secrets_dir=None,
        secrets_dir_max_size=1024,
    )

    with pytest.raises(SettingsError, match='secrets_dir size is above'):
        source.validate_secrets_path(secrets_dir)


def test_load_secrets_from_flat_directory(tmp_path: Path) -> None:
    """Test load_secrets loads files from a flat directory."""
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()
    (secrets_dir / 'username').write_text('test_user')
    (secrets_dir / 'password').write_text('test_pass  ')  # with trailing whitespace

    secrets = NestedSecretsSettingsSource.load_secrets(secrets_dir)

    assert secrets['username'] == 'test_user'
    assert secrets['password'] == 'test_pass'  # whitespace should be stripped


def test_load_secrets_from_nested_directory(tmp_path: Path) -> None:
    """Test load_secrets loads files from nested directories."""
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()
    nested_dir = secrets_dir / 'database'
    nested_dir.mkdir()
    (nested_dir / 'username').write_text('db_user')
    (nested_dir / 'password').write_text('db_pass')

    secrets = NestedSecretsSettingsSource.load_secrets(secrets_dir)

    # Keys should be relative paths
    assert f'database{os.sep}username' in secrets
    assert f'database{os.sep}password' in secrets


def test_load_secrets_from_empty_directory(tmp_path: Path) -> None:
    """Test load_secrets returns empty dict for empty directory."""
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()

    secrets = NestedSecretsSettingsSource.load_secrets(secrets_dir)

    assert secrets == {}


def test_load_secrets_ignores_subdirectories(tmp_path: Path) -> None:
    """Test load_secrets ignores subdirectories and only loads files."""
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()
    (secrets_dir / 'username').write_text('test_user')
    sub_dir = secrets_dir / 'subdir'
    sub_dir.mkdir()

    secrets = NestedSecretsSettingsSource.load_secrets(secrets_dir)

    # Should only have the file, not the directory
    assert 'username' in secrets
    assert 'subdir' not in secrets


def test_repr(tmp_path: Path) -> None:
    """Test __repr__ returns correct string representation."""
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()

    source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir=secrets_dir)

    repr_str = repr(source)

    assert 'NestedSecretsSettingsSource' in repr_str
    assert 'secrets' in repr_str


def test_repr_with_none_secrets_dir() -> None:
    """Test __repr__ with None secrets_dir."""
    source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir=None)

    repr_str = repr(source)

    assert 'NestedSecretsSettingsSource' in repr_str
    assert 'None' in repr_str


def test_repr_with_list_secrets_dir(tmp_path: Path) -> None:
    """Test __repr__ with list of secrets directories."""
    secrets_dir1 = tmp_path / 'secrets1'
    secrets_dir1.mkdir()
    secrets_dir2 = tmp_path / 'secrets2'
    secrets_dir2.mkdir()

    source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir=[secrets_dir1, secrets_dir2])

    repr_str = repr(source)

    assert 'NestedSecretsSettingsSource' in repr_str
