"""Unit tests for NestedSecretsSettingsSource."""
from __future__ import annotations

import os
import warnings
from pathlib import Path
from typing import Optional

import pytest

from pydantic_settings import BaseSettings
from pydantic_settings.exceptions import SettingsError
from pydantic_settings.sources.providers.nested_secrets import (
    NestedSecretsSettingsSource,
    first_not_none,
)
from pydantic_settings.sources.providers.secrets import SecretsSettingsSource


class SimpleSettings(BaseSettings):
    model_config = {'secrets_dir': None}
    username: str = 'default'
    password: Optional[str] = None


# ---------------------------------------------------------------------------
# first_not_none
# ---------------------------------------------------------------------------


def test_first_not_none_returns_first_non_none():
    assert first_not_none(None, None, 'value', 'other') == 'value'


def test_first_not_none_all_none_returns_none():
    assert first_not_none(None, None) is None


def test_first_not_none_first_value_returned():
    assert first_not_none(1, 2, 3) == 1


# ---------------------------------------------------------------------------
# NestedSecretsSettingsSource.__repr__
# ---------------------------------------------------------------------------


def test_repr_with_no_secrets_dir():
    source = NestedSecretsSettingsSource(SimpleSettings)
    assert 'NestedSecretsSettingsSource' in repr(source)
    assert 'secrets_dir=None' in repr(source)


def test_repr_with_secrets_dir(tmp_path):
    source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir=tmp_path)
    assert repr(source) == f'NestedSecretsSettingsSource(secrets_dir={tmp_path!r})'


# ---------------------------------------------------------------------------
# NestedSecretsSettingsSource.__init__ – basic construction
# ---------------------------------------------------------------------------


def test_init_with_no_secrets_dir():
    source = NestedSecretsSettingsSource(SimpleSettings)
    assert source.secrets_dir is None
    assert source.env_vars == {}


def test_init_with_explicit_secrets_dir(tmp_path):
    source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir=tmp_path)
    assert source.secrets_dir == tmp_path


def test_init_with_secrets_settings_source(tmp_path):
    secrets_source = SecretsSettingsSource(SimpleSettings, secrets_dir=tmp_path)
    source = NestedSecretsSettingsSource(secrets_source)
    assert source.secrets_dir == tmp_path


def test_init_secrets_dir_from_model_config(tmp_path):
    class SettingsWithDir(BaseSettings):
        model_config = {'secrets_dir': str(tmp_path)}
        username: str = 'default'

    source = NestedSecretsSettingsSource(SettingsWithDir)
    assert source.secrets_dir == str(tmp_path)


def test_init_secrets_dir_list(tmp_path):
    dir1 = tmp_path / 'dir1'
    dir1.mkdir()
    dir2 = tmp_path / 'dir2'
    dir2.mkdir()
    source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir=[dir1, dir2])
    assert len(source.secrets_paths) == 2


def test_init_default_case_sensitive_is_false():
    source = NestedSecretsSettingsSource(SimpleSettings)
    assert source.case_sensitive is False


def test_init_case_sensitive_from_arg(tmp_path):
    source = NestedSecretsSettingsSource(SimpleSettings, secrets_case_sensitive=True)
    assert source.case_sensitive is True


def test_init_default_secrets_dir_missing_is_warn():
    source = NestedSecretsSettingsSource(SimpleSettings)
    assert source.secrets_dir_missing == 'warn'


def test_init_secrets_dir_missing_override():
    source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir_missing='ok')
    assert source.secrets_dir_missing == 'ok'


def test_init_invalid_secrets_dir_missing_raises():
    with pytest.raises(SettingsError, match='invalid secrets_dir_missing'):
        NestedSecretsSettingsSource(SimpleSettings, secrets_dir_missing='invalid')  # type: ignore[arg-type]


def test_init_secrets_prefix_default_empty():
    source = NestedSecretsSettingsSource(SimpleSettings)
    assert source.secrets_prefix == ''


def test_init_secrets_prefix_from_arg():
    source = NestedSecretsSettingsSource(SimpleSettings, secrets_prefix='APP_')
    assert source.secrets_prefix == 'APP_'


def test_init_secrets_nested_delimiter_none_by_default():
    source = NestedSecretsSettingsSource(SimpleSettings)
    assert source.secrets_nested_delimiter is None


def test_init_secrets_nested_delimiter_set():
    source = NestedSecretsSettingsSource(SimpleSettings, secrets_nested_delimiter='__')
    assert source.secrets_nested_delimiter == '__'


def test_init_secrets_nested_subdir_false_by_default():
    source = NestedSecretsSettingsSource(SimpleSettings)
    assert source.secrets_nested_subdir is False


def test_init_secrets_nested_subdir_sets_delimiter_to_sep():
    source = NestedSecretsSettingsSource(SimpleSettings, secrets_nested_subdir=True)
    assert source.secrets_nested_subdir is True
    assert source.secrets_nested_delimiter == os.sep


def test_init_nested_subdir_and_delimiter_mutually_exclusive():
    with pytest.raises(SettingsError, match='mutually exclusive'):
        NestedSecretsSettingsSource(
            SimpleSettings,
            secrets_nested_subdir=True,
            secrets_nested_delimiter='__',
        )


def test_init_nested_subdir_and_delimiter_from_config_raises():
    class SettingsWithDelimiter(BaseSettings):
        model_config = {'secrets_nested_delimiter': '__'}
        username: str = 'default'

    with pytest.raises(SettingsError, match='mutually exclusive'):
        NestedSecretsSettingsSource(SettingsWithDelimiter, secrets_nested_subdir=True)


def test_init_loads_secrets_from_dir(tmp_path):
    (tmp_path / 'username').write_text('alice')

    class MySettings(BaseSettings):
        model_config = {'secrets_dir': None}
        username: str = 'default'

    source = NestedSecretsSettingsSource(MySettings, secrets_dir=tmp_path)
    assert 'username' in source.env_vars


def test_init_loads_secrets_from_multiple_dirs(tmp_path):
    dir1 = tmp_path / 'dir1'
    dir1.mkdir()
    dir2 = tmp_path / 'dir2'
    dir2.mkdir()
    (dir1 / 'username').write_text('alice')
    (dir2 / 'password').write_text('secret')

    class MySettings(BaseSettings):
        model_config = {'secrets_dir': None}
        username: str = 'default'
        password: Optional[str] = None

    source = NestedSecretsSettingsSource(MySettings, secrets_dir=[dir1, dir2])
    assert 'username' in source.env_vars
    assert 'password' in source.env_vars


def test_init_compat_case_sensitive_arg():
    source = NestedSecretsSettingsSource(SimpleSettings, case_sensitive=True)
    assert source.case_sensitive is True


def test_init_compat_env_prefix_arg():
    source = NestedSecretsSettingsSource(SimpleSettings, env_prefix='MY_')
    assert source.secrets_prefix == 'MY_'


# ---------------------------------------------------------------------------
# validate_secrets_path
# ---------------------------------------------------------------------------


def test_validate_secrets_path_ok_when_missing_and_mode_ok(tmp_path):
    nonexistent = tmp_path / 'missing'
    source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir_missing='ok')
    # Should not raise
    source.validate_secrets_path(nonexistent)


def test_validate_secrets_path_warns_when_missing_and_mode_warn(tmp_path):
    nonexistent = tmp_path / 'missing'
    source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir_missing='warn')
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter('always')
        source.validate_secrets_path(nonexistent)
    assert any('does not exist' in str(warning.message) for warning in w)


def test_validate_secrets_path_raises_when_missing_and_mode_error(tmp_path):
    nonexistent = tmp_path / 'missing'
    source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir_missing='error')
    with pytest.raises(SettingsError, match='does not exist'):
        source.validate_secrets_path(nonexistent)


def test_validate_secrets_path_raises_when_path_is_file(tmp_path):
    f = tmp_path / 'notadir'
    f.write_text('content')
    source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir_missing='ok')
    with pytest.raises(SettingsError, match='must reference a directory'):
        source.validate_secrets_path(f)


def test_validate_secrets_path_raises_when_dir_too_large(tmp_path):
    (tmp_path / 'bigfile').write_text('x')
    # Build source without secrets_dir, then override max_size to test directly
    source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir_missing='ok')
    source.secrets_dir_max_size = 0
    with pytest.raises(SettingsError, match='above'):
        source.validate_secrets_path(tmp_path)


def test_validate_secrets_path_passes_for_valid_dir(tmp_path):
    source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir_missing='ok')
    # Should not raise
    source.validate_secrets_path(tmp_path)


# ---------------------------------------------------------------------------
# load_secrets
# ---------------------------------------------------------------------------


def test_load_secrets_returns_file_contents(tmp_path):
    (tmp_path / 'username').write_text('  alice  ')
    result = NestedSecretsSettingsSource.load_secrets(tmp_path)
    assert result['username'] == 'alice'


def test_load_secrets_returns_nested_files(tmp_path):
    subdir = tmp_path / 'db'
    subdir.mkdir()
    (subdir / 'password').write_text('dbpass')
    result = NestedSecretsSettingsSource.load_secrets(tmp_path)
    assert f'db{os.sep}password' in result
    assert result[f'db{os.sep}password'] == 'dbpass'


def test_load_secrets_empty_dir(tmp_path):
    result = NestedSecretsSettingsSource.load_secrets(tmp_path)
    assert result == {}


def test_load_secrets_strips_whitespace(tmp_path):
    (tmp_path / 'key').write_text('\n  value  \n')
    result = NestedSecretsSettingsSource.load_secrets(tmp_path)
    assert result['key'] == 'value'
