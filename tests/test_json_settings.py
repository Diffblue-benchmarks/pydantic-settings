"""Tests for JsonConfigSettingsSource."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import Field

from pydantic_settings import BaseSettings
from pydantic_settings.sources.providers.json import JsonConfigSettingsSource


@pytest.fixture
def json_file(tmp_path: Path) -> Path:
    data = {'app_name': 'test_app', 'debug': True, 'port': 8080}
    file = tmp_path / 'settings.json'
    file.write_text(json.dumps(data))
    return file


@pytest.fixture
def nested_json_file(tmp_path: Path) -> Path:
    data = {'app_name': 'nested_app', 'nested': {'key': 'value'}}
    file = tmp_path / 'nested.json'
    file.write_text(json.dumps(data))
    return file


class SimpleSettings(BaseSettings):
    app_name: str = 'default'
    debug: bool = False
    port: int = 3000


class SettingsWithJsonConfig(BaseSettings):
    model_config = {'json_file': None, 'json_file_encoding': None}

    app_name: str = 'default'
    debug: bool = False
    port: int = 3000


def test_init_with_explicit_json_file(json_file: Path) -> None:
    source = JsonConfigSettingsSource(SimpleSettings, json_file=json_file)
    assert source.json_file_path == json_file
    assert source.json_data == {'app_name': 'test_app', 'debug': True, 'port': 8080}


def test_init_uses_model_config_json_file(json_file: Path) -> None:
    class ConfiguredSettings(BaseSettings):
        model_config = {'json_file': json_file}

        app_name: str = 'default'

    source = JsonConfigSettingsSource(ConfiguredSettings)
    assert source.json_file_path == json_file
    assert source.json_data.get('app_name') == 'test_app'


def test_init_with_explicit_encoding(json_file: Path) -> None:
    source = JsonConfigSettingsSource(SimpleSettings, json_file=json_file, json_file_encoding='utf-8')
    assert source.json_file_encoding == 'utf-8'


def test_init_uses_model_config_encoding(json_file: Path) -> None:
    class ConfiguredSettings(BaseSettings):
        model_config = {'json_file': json_file, 'json_file_encoding': 'utf-8'}

        app_name: str = 'default'

    source = JsonConfigSettingsSource(ConfiguredSettings)
    assert source.json_file_encoding == 'utf-8'


def test_init_encoding_none_when_not_set(json_file: Path) -> None:
    source = JsonConfigSettingsSource(SimpleSettings, json_file=json_file)
    assert source.json_file_encoding is None


def test_init_with_none_json_file() -> None:
    source = JsonConfigSettingsSource(SimpleSettings, json_file=None)
    assert source.json_file_path is None
    assert source.json_data == {}


def test_init_deep_merge(tmp_path: Path) -> None:
    file1 = tmp_path / 'first.json'
    file2 = tmp_path / 'second.json'
    file1.write_text(json.dumps({'a': 1, 'nested': {'x': 1, 'y': 2}}))
    file2.write_text(json.dumps({'b': 2, 'nested': {'y': 99, 'z': 3}}))

    source = JsonConfigSettingsSource(
        SimpleSettings, json_file=[file1, file2], deep_merge=True
    )
    assert source.json_data['nested'] == {'x': 1, 'y': 99, 'z': 3}


def test_init_no_deep_merge(tmp_path: Path) -> None:
    file1 = tmp_path / 'first.json'
    file2 = tmp_path / 'second.json'
    file1.write_text(json.dumps({'a': 1, 'nested': {'x': 1}}))
    file2.write_text(json.dumps({'b': 2, 'nested': {'y': 99}}))

    source = JsonConfigSettingsSource(
        SimpleSettings, json_file=[file1, file2], deep_merge=False
    )
    assert source.json_data['nested'] == {'y': 99}


def test_read_file(json_file: Path) -> None:
    source = JsonConfigSettingsSource(SimpleSettings, json_file=json_file)
    result = source._read_file(json_file)
    assert result == {'app_name': 'test_app', 'debug': True, 'port': 8080}


def test_read_file_with_encoding(tmp_path: Path) -> None:
    data = {'name': 'caf\u00e9'}
    file = tmp_path / 'utf8.json'
    file.write_text(json.dumps(data), encoding='utf-8')

    source = JsonConfigSettingsSource(SimpleSettings, json_file=file, json_file_encoding='utf-8')
    result = source._read_file(file)
    assert result == {'name': 'caf\u00e9'}


def test_repr_with_file_path(json_file: Path) -> None:
    source = JsonConfigSettingsSource(SimpleSettings, json_file=json_file)
    assert repr(source) == f'JsonConfigSettingsSource(json_file={json_file})'


def test_repr_with_none() -> None:
    source = JsonConfigSettingsSource(SimpleSettings, json_file=None)
    assert repr(source) == 'JsonConfigSettingsSource(json_file=None)'


def test_repr_with_list_of_files(tmp_path: Path) -> None:
    file1 = tmp_path / 'a.json'
    file2 = tmp_path / 'b.json'
    file1.write_text('{}')
    file2.write_text('{}')
    files = [file1, file2]
    source = JsonConfigSettingsSource(SimpleSettings, json_file=files)
    assert repr(source) == f'JsonConfigSettingsSource(json_file={files})'


def test_init_missing_file_ignored() -> None:
    source = JsonConfigSettingsSource(SimpleSettings, json_file=Path('/nonexistent/path/settings.json'))
    assert source.json_data == {}


def test_json_data_populates_settings(json_file: Path) -> None:
    class MySettings(BaseSettings):
        model_config = {'json_file': json_file, 'extra': 'ignore'}

        app_name: str = 'default'
        port: int = 3000

        @classmethod
        def settings_customise_sources(cls, settings_cls, **kwargs):
            return (JsonConfigSettingsSource(settings_cls),)

    settings = MySettings()
    assert settings.app_name == 'test_app'
    assert settings.port == 8080
