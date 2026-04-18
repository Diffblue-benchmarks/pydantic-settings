"""Tests for SecretsSettingsSource."""
from __future__ import annotations

import warnings
from pathlib import Path
from typing import Optional

import pytest
from pydantic import Field
from pydantic.fields import FieldInfo

from pydantic_settings import BaseSettings
from pydantic_settings.sources.providers.secrets import SecretsSettingsSource


class SimpleSettings(BaseSettings):
    model_config = {'secrets_dir': None}

    username: str = 'default_user'
    password: str = 'default_pass'
    api_key: Optional[str] = None


class PrefixedSettings(BaseSettings):
    model_config = {'secrets_dir': None, 'env_prefix': 'APP_'}

    username: str = 'default_user'


# ---------- __init__ ----------


def test_init_with_explicit_secrets_dir(tmp_path):
    source = SecretsSettingsSource(SimpleSettings, secrets_dir=tmp_path)
    assert source.secrets_dir == tmp_path


def test_init_uses_config_secrets_dir_when_none_passed(tmp_path):
    class SettingsWithDir(BaseSettings):
        model_config = {'secrets_dir': tmp_path}
        username: str = 'default'

    source = SecretsSettingsSource(SettingsWithDir)
    assert source.secrets_dir == tmp_path


def test_init_secrets_dir_none_when_not_in_config():
    source = SecretsSettingsSource(SimpleSettings)
    assert source.secrets_dir is None


def test_init_with_case_sensitive():
    source = SecretsSettingsSource(SimpleSettings, case_sensitive=True)
    assert source.case_sensitive is True


def test_init_with_env_prefix():
    source = SecretsSettingsSource(SimpleSettings, env_prefix='MY_')
    assert source.env_prefix == 'MY_'


def test_init_with_multiple_params(tmp_path):
    source = SecretsSettingsSource(
        SimpleSettings,
        secrets_dir=tmp_path,
        case_sensitive=False,
        env_prefix='SVC_',
        env_ignore_empty=True,
        env_parse_none_str='null',
        env_parse_enums=True,
    )
    assert source.secrets_dir == tmp_path
    assert source.case_sensitive is False
    assert source.env_prefix == 'SVC_'


# ---------- __repr__ ----------


def test_repr_with_path(tmp_path):
    source = SecretsSettingsSource(SimpleSettings, secrets_dir=tmp_path)
    result = repr(source)
    assert result.startswith('SecretsSettingsSource(secrets_dir=')
    assert str(tmp_path) in result


def test_repr_with_none():
    source = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
    assert repr(source) == 'SecretsSettingsSource(secrets_dir=None)'


def test_repr_with_string_path(tmp_path):
    source = SecretsSettingsSource(SimpleSettings, secrets_dir=str(tmp_path))
    result = repr(source)
    assert 'SecretsSettingsSource(secrets_dir=' in result


# ---------- __call__ ----------


def test_call_returns_empty_when_secrets_dir_none():
    source = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
    result = source()
    assert result == {}


def test_call_warns_when_directory_does_not_exist(tmp_path):
    nonexistent = tmp_path / 'no_such_dir'
    source = SecretsSettingsSource(SimpleSettings, secrets_dir=nonexistent)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter('always')
        result = source()
    assert result == {}
    assert any('does not exist' in str(warning.message) for warning in w)


def test_call_raises_when_secrets_path_is_file(tmp_path):
    secret_file = tmp_path / 'notadir'
    secret_file.write_text('value')
    source = SecretsSettingsSource(SimpleSettings, secrets_dir=secret_file)
    with pytest.raises(Exception, match='secrets_dir must reference a directory'):
        source()


def test_call_reads_secret_from_directory(tmp_path):
    (tmp_path / 'username').write_text('secret_user')
    source = SecretsSettingsSource(SimpleSettings, secrets_dir=tmp_path)
    result = source()
    assert result.get('username') == 'secret_user'


def test_call_returns_empty_when_all_dirs_missing(tmp_path):
    missing1 = tmp_path / 'dir1'
    missing2 = tmp_path / 'dir2'
    source = SecretsSettingsSource(SimpleSettings, secrets_dir=[missing1, missing2])
    with warnings.catch_warnings(record=True):
        warnings.simplefilter('always')
        result = source()
    assert result == {}


def test_call_with_multiple_secrets_dirs_last_wins(tmp_path):
    dir1 = tmp_path / 'dir1'
    dir2 = tmp_path / 'dir2'
    dir1.mkdir()
    dir2.mkdir()
    (dir1 / 'username').write_text('user_from_dir1')
    (dir2 / 'username').write_text('user_from_dir2')
    source = SecretsSettingsSource(SimpleSettings, secrets_dir=[dir1, dir2])
    result = source()
    assert result.get('username') == 'user_from_dir2'


def test_call_with_list_of_secrets_dirs(tmp_path):
    dir1 = tmp_path / 'secrets'
    dir1.mkdir()
    (dir1 / 'api_key').write_text('my_api_key')
    source = SecretsSettingsSource(SimpleSettings, secrets_dir=[dir1])
    result = source()
    assert result.get('api_key') == 'my_api_key'


def test_call_strips_whitespace_from_secret(tmp_path):
    (tmp_path / 'username').write_text('  stripped_value  \n')
    source = SecretsSettingsSource(SimpleSettings, secrets_dir=tmp_path)
    result = source()
    assert result.get('username') == 'stripped_value'


# ---------- find_case_path ----------


def test_find_case_path_exact_match(tmp_path):
    (tmp_path / 'myfile').write_text('content')
    result = SecretsSettingsSource.find_case_path(tmp_path, 'myfile', case_sensitive=True)
    assert result is not None
    assert result.name == 'myfile'


def test_find_case_path_no_match(tmp_path):
    (tmp_path / 'myfile').write_text('content')
    result = SecretsSettingsSource.find_case_path(tmp_path, 'other', case_sensitive=True)
    assert result is None


def test_find_case_path_case_insensitive_match(tmp_path):
    (tmp_path / 'MYFILE').write_text('content')
    result = SecretsSettingsSource.find_case_path(tmp_path, 'myfile', case_sensitive=False)
    assert result is not None
    assert result.name == 'MYFILE'


def test_find_case_path_case_sensitive_no_match_on_different_case(tmp_path):
    (tmp_path / 'MYFILE').write_text('content')
    result = SecretsSettingsSource.find_case_path(tmp_path, 'myfile', case_sensitive=True)
    assert result is None


def test_find_case_path_empty_dir(tmp_path):
    result = SecretsSettingsSource.find_case_path(tmp_path, 'myfile', case_sensitive=True)
    assert result is None


def test_find_case_path_multiple_files(tmp_path):
    (tmp_path / 'file_a').write_text('a')
    (tmp_path / 'file_b').write_text('b')
    (tmp_path / 'target').write_text('target_val')
    result = SecretsSettingsSource.find_case_path(tmp_path, 'target', case_sensitive=True)
    assert result is not None
    assert result.name == 'target'


# ---------- get_field_value ----------


def test_get_field_value_returns_none_for_missing_secret(tmp_path):
    source = SecretsSettingsSource(SimpleSettings, secrets_dir=tmp_path)
    source.secrets_paths = [tmp_path]
    field_info = SimpleSettings.model_fields['username']
    value, key, is_complex = source.get_field_value(field_info, 'username')
    assert value is None


def test_get_field_value_reads_existing_secret(tmp_path):
    (tmp_path / 'username').write_text('found_user')
    source = SecretsSettingsSource(SimpleSettings, secrets_dir=tmp_path)
    source.secrets_paths = [tmp_path]
    field_info = SimpleSettings.model_fields['username']
    value, key, is_complex = source.get_field_value(field_info, 'username')
    assert value == 'found_user'
    assert key == 'username'


def test_get_field_value_warns_for_non_file_secret(tmp_path):
    secret_subdir = tmp_path / 'password'
    secret_subdir.mkdir()
    source = SecretsSettingsSource(SimpleSettings, secrets_dir=tmp_path)
    source.secrets_paths = [tmp_path]
    field_info = SimpleSettings.model_fields['password']
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter('always')
        value, key, is_complex = source.get_field_value(field_info, 'password')
    assert value is None
    assert any('attempted to load secret file' in str(warning.message) for warning in w)


def test_get_field_value_with_env_prefix(tmp_path):
    (tmp_path / 'app_username').write_text('prefixed_user')
    source = SecretsSettingsSource(PrefixedSettings, secrets_dir=tmp_path)
    source.secrets_paths = [tmp_path]
    field_info = PrefixedSettings.model_fields['username']
    value, key, is_complex = source.get_field_value(field_info, 'username')
    assert value == 'prefixed_user'


def test_get_field_value_case_insensitive(tmp_path):
    (tmp_path / 'USERNAME').write_text('case_insensitive_user')
    source = SecretsSettingsSource(SimpleSettings, secrets_dir=tmp_path, case_sensitive=False)
    source.secrets_paths = [tmp_path]
    field_info = SimpleSettings.model_fields['username']
    value, key, is_complex = source.get_field_value(field_info, 'username')
    assert value == 'case_insensitive_user'
