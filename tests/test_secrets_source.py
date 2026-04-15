"""Unit tests for SecretsSettingsSource."""
from __future__ import annotations

import warnings
from pathlib import Path
from typing import Optional

import pytest
from pydantic.fields import FieldInfo

from pydantic_settings import BaseSettings
from pydantic_settings.sources.providers.secrets import SecretsSettingsSource


class SimpleSettings(BaseSettings):
    model_config = {'secrets_dir': None}
    username: str = 'default'
    password: Optional[str] = None


class SimpleSettingsWithDir(BaseSettings):
    model_config = {'secrets_dir': None}
    username: str = 'default'
    password: Optional[str] = None


def test_init_with_explicit_secrets_dir(tmp_path):
    source = SecretsSettingsSource(SimpleSettings, secrets_dir=tmp_path)
    assert source.secrets_dir == tmp_path


def test_init_with_no_secrets_dir():
    source = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
    assert source.secrets_dir is None


def test_init_uses_config_secrets_dir_when_none_provided(tmp_path):
    class SettingsWithDir(BaseSettings):
        model_config = {'secrets_dir': str(tmp_path)}
        username: str = 'default'

    source = SecretsSettingsSource(SettingsWithDir, secrets_dir=None)
    assert source.secrets_dir == str(tmp_path)


def test_call_returns_empty_when_no_secrets_dir():
    source = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
    result = source()
    assert result == {}


def test_call_warns_when_directory_does_not_exist(tmp_path):
    nonexistent = tmp_path / 'nonexistent'
    source = SecretsSettingsSource(SimpleSettings, secrets_dir=nonexistent)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter('always')
        result = source()
    assert result == {}
    assert any('does not exist' in str(warning.message) for warning in w)


def test_call_returns_empty_when_all_paths_missing(tmp_path):
    nonexistent1 = tmp_path / 'missing1'
    nonexistent2 = tmp_path / 'missing2'
    source = SecretsSettingsSource(SimpleSettings, secrets_dir=[nonexistent1, nonexistent2])
    with warnings.catch_warnings(record=True):
        warnings.simplefilter('always')
        result = source()
    assert result == {}


def test_call_raises_when_secrets_dir_is_file(tmp_path):
    secret_file = tmp_path / 'notadir'
    secret_file.write_text('something')
    from pydantic_settings.exceptions import SettingsError
    source = SecretsSettingsSource(SimpleSettings, secrets_dir=secret_file)
    with pytest.raises(SettingsError, match='must reference a directory'):
        source()


def test_call_reads_secrets_from_directory(tmp_path):
    (tmp_path / 'username').write_text('secret_user')

    class MySettings(BaseSettings):
        model_config = {'secrets_dir': None}
        username: str = 'default'

    source = SecretsSettingsSource(MySettings, secrets_dir=tmp_path)
    result = source()
    assert result.get('username') == 'secret_user'


def test_find_case_path_exact_match(tmp_path):
    (tmp_path / 'myfile').write_text('')
    result = SecretsSettingsSource.find_case_path(tmp_path, 'myfile', case_sensitive=True)
    assert result is not None
    assert result.name == 'myfile'


def test_find_case_path_case_insensitive_match(tmp_path):
    (tmp_path / 'MyFile').write_text('')
    result = SecretsSettingsSource.find_case_path(tmp_path, 'myfile', case_sensitive=False)
    assert result is not None
    assert result.name == 'MyFile'


def test_find_case_path_case_sensitive_no_match(tmp_path):
    (tmp_path / 'MyFile').write_text('')
    result = SecretsSettingsSource.find_case_path(tmp_path, 'myfile', case_sensitive=True)
    assert result is None


def test_find_case_path_returns_none_when_no_match(tmp_path):
    result = SecretsSettingsSource.find_case_path(tmp_path, 'nonexistent', case_sensitive=True)
    assert result is None


def test_get_field_value_returns_none_when_no_file(tmp_path):
    source = SecretsSettingsSource(SimpleSettings, secrets_dir=tmp_path)
    source()  # populate secrets_paths
    field = FieldInfo(annotation=str)
    value, key, is_complex = source.get_field_value(field, 'username')
    assert value is None


def test_get_field_value_reads_file_content(tmp_path):
    (tmp_path / 'username').write_text('  secret_value  ')

    class MySettings(BaseSettings):
        model_config = {'secrets_dir': None}
        username: str = 'default'

    source = SecretsSettingsSource(MySettings, secrets_dir=tmp_path)
    source()  # populate secrets_paths
    field = FieldInfo(annotation=str)
    value, key, is_complex = source.get_field_value(field, 'username')
    assert value == 'secret_value'


def test_get_field_value_warns_when_secret_is_not_file(tmp_path):
    subdir = tmp_path / 'username'
    subdir.mkdir()

    class MySettings(BaseSettings):
        model_config = {'secrets_dir': None}
        username: str = 'default'

    source = SecretsSettingsSource(MySettings, secrets_dir=tmp_path)
    # Manually populate secrets_paths to avoid going through the full __call__ flow
    source.secrets_paths = [tmp_path]
    field = FieldInfo(annotation=str)

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter('always')
        value, key, is_complex = source.get_field_value(field, 'username')
    assert value is None
    assert any('attempted to load secret file' in str(warning.message) for warning in w)


def test_repr_with_secrets_dir(tmp_path):
    source = SecretsSettingsSource(SimpleSettings, secrets_dir=tmp_path)
    repr_str = repr(source)
    assert 'SecretsSettingsSource' in repr_str
    assert 'secrets_dir' in repr_str


def test_repr_with_no_secrets_dir():
    source = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
    repr_str = repr(source)
    assert repr_str == 'SecretsSettingsSource(secrets_dir=None)'


def test_call_with_multiple_secrets_dirs_last_wins(tmp_path):
    dir1 = tmp_path / 'dir1'
    dir2 = tmp_path / 'dir2'
    dir1.mkdir()
    dir2.mkdir()
    (dir1 / 'username').write_text('user_from_dir1')
    (dir2 / 'username').write_text('user_from_dir2')

    class MySettings(BaseSettings):
        model_config = {'secrets_dir': None}
        username: str = 'default'

    source = SecretsSettingsSource(MySettings, secrets_dir=[dir1, dir2])
    result = source()
    assert result.get('username') == 'user_from_dir2'
