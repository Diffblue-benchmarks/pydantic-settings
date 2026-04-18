"""Tests for NestedSecretsSettingsSource."""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from pydantic_settings import BaseSettings
from pydantic_settings.exceptions import SettingsError
from pydantic_settings.sources.providers.nested_secrets import NestedSecretsSettingsSource, first_not_none
from pydantic_settings.sources.providers.secrets import SecretsSettingsSource


class SimpleSettings(BaseSettings):
    username: str = 'default'
    password: str = 'secret'


class SettingsWithSecretsDir(BaseSettings):
    model_config = {'secrets_dir': '/tmp/test_secrets'}

    username: str = 'default'


class NestedSettings(BaseSettings):
    username: str = 'default'
    db__host: str = 'localhost'


# Tests for first_not_none


def test_first_not_none_returns_first_non_none():
    result = first_not_none(None, None, 'value', 'other')
    assert result == 'value'


def test_first_not_none_returns_none_when_all_none():
    result = first_not_none(None, None, None)
    assert result is None


def test_first_not_none_returns_first_argument_if_not_none():
    result = first_not_none('first', 'second')
    assert result == 'first'


def test_first_not_none_returns_none_with_no_args():
    result = first_not_none()
    assert result is None


def test_first_not_none_handles_falsy_non_none():
    result = first_not_none(None, 0, None)
    assert result == 0


def test_first_not_none_handles_empty_string():
    result = first_not_none(None, '', None)
    assert result == ''


def test_first_not_none_handles_false():
    result = first_not_none(None, False, True)
    assert result is False


# Tests for NestedSecretsSettingsSource.__init__


def test_init_with_settings_class_no_secrets_dir():
    source = NestedSecretsSettingsSource(SimpleSettings)
    assert source.secrets_dir is None
    assert source.secrets_paths == []
    assert source.env_vars == {}


def test_init_with_settings_class_and_secrets_dir(tmp_path: Path):
    source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir=tmp_path)
    assert source.secrets_dir == tmp_path
    assert source.secrets_paths == [tmp_path]


def test_init_with_secrets_source_instance(tmp_path: Path):
    secrets_source = SecretsSettingsSource(SimpleSettings, secrets_dir=tmp_path)
    source = NestedSecretsSettingsSource(secrets_source)
    assert source.secrets_dir == tmp_path


def test_init_defaults():
    source = NestedSecretsSettingsSource(SimpleSettings)
    assert source.secrets_dir_missing == 'warn'
    assert source.case_sensitive is False
    assert source.secrets_prefix == ''
    assert source.secrets_nested_delimiter is None
    assert source.secrets_nested_subdir is False


def test_init_invalid_secrets_dir_missing():
    with pytest.raises(SettingsError, match='invalid secrets_dir_missing value'):
        NestedSecretsSettingsSource(SimpleSettings, secrets_dir_missing='invalid')  # type: ignore[arg-type]


def test_init_secrets_nested_subdir_sets_delimiter(tmp_path: Path):
    import os
    source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir=tmp_path, secrets_nested_subdir=True)
    assert source.secrets_nested_delimiter == os.sep
    assert source.secrets_nested_subdir is True


def test_init_secrets_nested_subdir_conflicts_with_delimiter(tmp_path: Path):
    with pytest.raises(SettingsError, match='mutually exclusive'):
        NestedSecretsSettingsSource(
            SimpleSettings,
            secrets_dir=tmp_path,
            secrets_nested_subdir=True,
            secrets_nested_delimiter='__',
        )


def test_init_with_secrets_dir_as_string(tmp_path: Path):
    source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir=str(tmp_path))
    assert source.secrets_paths == [tmp_path]


def test_init_with_secrets_dir_as_list(tmp_path: Path):
    dir1 = tmp_path / 'dir1'
    dir1.mkdir()
    dir2 = tmp_path / 'dir2'
    dir2.mkdir()
    source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir=[dir1, dir2])
    assert len(source.secrets_paths) == 2


def test_init_case_sensitive_override(tmp_path: Path):
    source = NestedSecretsSettingsSource(SimpleSettings, secrets_case_sensitive=True)
    assert source.case_sensitive is True


def test_init_secrets_prefix_override(tmp_path: Path):
    source = NestedSecretsSettingsSource(SimpleSettings, secrets_prefix='APP_')
    assert source.secrets_prefix == 'APP_'


def test_init_nested_delimiter_override(tmp_path: Path):
    source = NestedSecretsSettingsSource(SimpleSettings, secrets_nested_delimiter='__')
    assert source.secrets_nested_delimiter == '__'


def test_init_loads_secrets_from_dir(tmp_path: Path):
    (tmp_path / 'username').write_text('alice')
    (tmp_path / 'password').write_text('supersecret')
    source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir=tmp_path)
    assert 'username' in source.env_vars or 'USERNAME' in source.env_vars


def test_init_with_secrets_source_no_secrets_dir():
    secrets_source = SecretsSettingsSource(SimpleSettings)
    source = NestedSecretsSettingsSource(secrets_source)
    assert source.secrets_dir is None
    assert source.env_vars == {}


def test_init_secrets_dir_missing_ok_with_nonexistent_dir(tmp_path: Path):
    missing = tmp_path / 'nonexistent'
    source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir=missing, secrets_dir_missing='ok')
    assert source.secrets_paths == [missing]


def test_init_env_prefix_compat_arg(tmp_path: Path):
    source = NestedSecretsSettingsSource(SimpleSettings, env_prefix='MY_')
    assert source.secrets_prefix == 'MY_'


def test_init_case_sensitive_compat_arg(tmp_path: Path):
    source = NestedSecretsSettingsSource(SimpleSettings, case_sensitive=True)
    assert source.case_sensitive is True


# Tests for validate_secrets_path


def test_validate_secrets_path_missing_ok(tmp_path: Path):
    missing = tmp_path / 'nonexistent'
    source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir_missing='ok')
    # Should not raise
    source.validate_secrets_path(missing)


def test_validate_secrets_path_missing_warn(tmp_path: Path):
    missing = tmp_path / 'nonexistent'
    source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir_missing='warn')
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter('always')
        source.validate_secrets_path(missing)
    assert len(w) == 1
    assert 'does not exist' in str(w[0].message)


def test_validate_secrets_path_missing_error(tmp_path: Path):
    missing = tmp_path / 'nonexistent'
    source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir_missing='error')
    with pytest.raises(SettingsError, match='does not exist'):
        source.validate_secrets_path(missing)


def test_validate_secrets_path_not_a_directory(tmp_path: Path):
    file_path = tmp_path / 'not_a_dir.txt'
    file_path.write_text('content')
    source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir_missing='ok')
    with pytest.raises(SettingsError, match='secrets_dir must reference a directory'):
        source.validate_secrets_path(file_path)


def test_validate_secrets_path_too_large(tmp_path: Path):
    large_file = tmp_path / 'large_secret'
    large_file.write_bytes(b'x' * 100)
    source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir_max_size=10, secrets_dir_missing='ok')
    with pytest.raises(SettingsError, match='secrets_dir size is above'):
        source.validate_secrets_path(tmp_path)


def test_validate_secrets_path_valid_directory(tmp_path: Path):
    source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir_missing='ok')
    # Should not raise for a valid empty directory
    source.validate_secrets_path(tmp_path)


# Tests for load_secrets


def test_load_secrets_flat_files(tmp_path: Path):
    (tmp_path / 'username').write_text('alice')
    (tmp_path / 'password').write_text('  secret  ')
    result = NestedSecretsSettingsSource.load_secrets(tmp_path)
    assert result['username'] == 'alice'
    assert result['password'] == 'secret'


def test_load_secrets_nested_files(tmp_path: Path):
    sub = tmp_path / 'db'
    sub.mkdir()
    (sub / 'host').write_text('localhost')
    result = NestedSecretsSettingsSource.load_secrets(tmp_path)
    import os
    key = os.path.join('db', 'host')
    assert result[key] == 'localhost'


def test_load_secrets_empty_directory(tmp_path: Path):
    result = NestedSecretsSettingsSource.load_secrets(tmp_path)
    assert result == {}


def test_load_secrets_strips_whitespace(tmp_path: Path):
    (tmp_path / 'mykey').write_text('\n  value\n  ')
    result = NestedSecretsSettingsSource.load_secrets(tmp_path)
    assert result['mykey'] == 'value'


# Tests for __repr__


def test_repr_with_secrets_dir(tmp_path: Path):
    source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir=tmp_path)
    r = repr(source)
    assert r.startswith('NestedSecretsSettingsSource(')
    assert 'secrets_dir=' in r


def test_repr_without_secrets_dir():
    source = NestedSecretsSettingsSource(SimpleSettings)
    r = repr(source)
    assert r == 'NestedSecretsSettingsSource(secrets_dir=None)'
