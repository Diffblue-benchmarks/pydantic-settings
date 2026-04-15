"""Unit tests for TomlConfigSettingsSource."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import pytest

from pydantic_settings import BaseSettings
from pydantic_settings.sources.providers.toml import TomlConfigSettingsSource, import_toml


class SimpleTomlSettings(BaseSettings):
    model_config = {'toml_file': None}
    name: str = 'default'
    value: int = 0


def test_import_toml_sets_global():
    import_toml()
    import pydantic_settings.sources.providers.toml as toml_mod
    if sys.version_info < (3, 11):
        assert toml_mod.tomli is not None
    else:
        assert toml_mod.tomllib is not None


def test_import_toml_python_lt_311_tomli_is_none(mocker):
    import pydantic_settings.sources.providers.toml as toml_mod

    mock_sys = mocker.MagicMock()
    mock_sys.version_info = (3, 10, 0)
    mocker.patch.object(toml_mod, 'sys', mock_sys)
    mocker.patch.object(toml_mod, 'tomli', None)

    import_toml()

    assert toml_mod.tomli is not None


def test_import_toml_python_lt_311_tomli_already_set(mocker):
    import pydantic_settings.sources.providers.toml as toml_mod

    fake_tomli = mocker.MagicMock()
    mock_sys = mocker.MagicMock()
    mock_sys.version_info = (3, 10, 0)
    mocker.patch.object(toml_mod, 'sys', mock_sys)
    mocker.patch.object(toml_mod, 'tomli', fake_tomli)

    import_toml()

    assert toml_mod.tomli is fake_tomli


def test_import_toml_idempotent():
    import_toml()
    import_toml()
    import pydantic_settings.sources.providers.toml as toml_mod
    if sys.version_info < (3, 11):
        assert toml_mod.tomli is not None
    else:
        assert toml_mod.tomllib is not None


def test_init_with_explicit_toml_file(tmp_path):
    toml_file = tmp_path / 'settings.toml'
    toml_file.write_bytes(b'name = "hello"\nvalue = 42\n')
    source = TomlConfigSettingsSource(SimpleTomlSettings, toml_file=toml_file)
    assert source.toml_file_path == toml_file


def test_init_with_no_toml_file():
    source = TomlConfigSettingsSource(SimpleTomlSettings, toml_file=None)
    assert source.toml_file_path is None
    assert source.toml_data == {}


def test_init_uses_model_config_toml_file(tmp_path):
    toml_file = tmp_path / 'config.toml'
    toml_file.write_bytes(b'name = "from_config"\n')

    class SettingsWithToml(BaseSettings):
        model_config = {'toml_file': str(toml_file)}
        name: str = 'default'

    source = TomlConfigSettingsSource(SettingsWithToml)
    assert source.toml_data.get('name') == 'from_config'


def test_init_loads_toml_data(tmp_path):
    toml_file = tmp_path / 'settings.toml'
    toml_file.write_bytes(b'name = "hello"\nvalue = 42\n')
    source = TomlConfigSettingsSource(SimpleTomlSettings, toml_file=toml_file)
    assert source.toml_data.get('name') == 'hello'
    assert source.toml_data.get('value') == 42


def test_read_file_returns_dict(tmp_path):
    toml_file = tmp_path / 'settings.toml'
    toml_file.write_bytes(b'name = "test"\nvalue = 10\n')
    source = TomlConfigSettingsSource(SimpleTomlSettings, toml_file=None)
    result = source._read_file(toml_file)
    assert result == {'name': 'test', 'value': 10}


def test_read_file_nested(tmp_path):
    toml_file = tmp_path / 'settings.toml'
    toml_file.write_bytes(b'[section]\nkey = "nested_value"\n')
    source = TomlConfigSettingsSource(SimpleTomlSettings, toml_file=None)
    result = source._read_file(toml_file)
    assert result == {'section': {'key': 'nested_value'}}


def test_repr_with_file_path(tmp_path):
    toml_file = tmp_path / 'settings.toml'
    toml_file.write_bytes(b'name = "test"\n')
    source = TomlConfigSettingsSource(SimpleTomlSettings, toml_file=toml_file)
    result = repr(source)
    assert result == f'TomlConfigSettingsSource(toml_file={toml_file})'


def test_repr_with_none():
    source = TomlConfigSettingsSource(SimpleTomlSettings, toml_file=None)
    result = repr(source)
    assert result == 'TomlConfigSettingsSource(toml_file=None)'


def test_init_deep_merge(tmp_path):
    toml_file1 = tmp_path / 'base.toml'
    toml_file1.write_bytes(b'[section]\nkey1 = "value1"\nkey2 = "value2"\n')
    toml_file2 = tmp_path / 'override.toml'
    toml_file2.write_bytes(b'[section]\nkey1 = "overridden"\n')

    class MultiFileSettings(BaseSettings):
        model_config = {'toml_file': None}

    source = TomlConfigSettingsSource(
        MultiFileSettings,
        toml_file=[toml_file1, toml_file2],
        deep_merge=True,
    )
    assert source.toml_data['section']['key1'] == 'overridden'
    assert source.toml_data['section']['key2'] == 'value2'
