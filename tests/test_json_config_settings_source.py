"""Tests for JsonConfigSettingsSource."""

import json
from pathlib import Path

import pytest

from pydantic_settings import BaseSettings
from pydantic_settings.sources.providers.json import JsonConfigSettingsSource


@pytest.fixture
def json_file(tmp_path):
    """Create a temporary JSON settings file."""
    file_path = tmp_path / 'settings.json'
    file_path.write_text(json.dumps({'app_name': 'test_app', 'debug': True}))
    return file_path


@pytest.fixture
def json_file_encoded(tmp_path):
    """Create a temporary JSON settings file with specific encoding."""
    file_path = tmp_path / 'settings_encoded.json'
    file_path.write_text(json.dumps({'app_name': 'encoded_app'}), encoding='utf-8')
    return file_path


def test_init_with_explicit_json_file(json_file):
    class MySettings(BaseSettings):
        app_name: str = 'default'
        debug: bool = False

    source = JsonConfigSettingsSource(MySettings, json_file=json_file)
    assert source.json_file_path == json_file
    assert source.json_file_encoding is None
    assert source.json_data == {'app_name': 'test_app', 'debug': True}


def test_init_with_default_path_reads_from_model_config(json_file):
    class MySettings(BaseSettings):
        model_config = {'json_file': json_file}

        app_name: str = 'default'

    source = JsonConfigSettingsSource(MySettings)
    assert source.json_file_path == json_file
    assert source.json_data == {'app_name': 'test_app', 'debug': True}


def test_init_with_none_json_file():
    class MySettings(BaseSettings):
        app_name: str = 'default'

    source = JsonConfigSettingsSource(MySettings, json_file=None)
    assert source.json_file_path is None
    assert source.json_data == {}


def test_init_with_explicit_encoding(json_file_encoded):
    class MySettings(BaseSettings):
        app_name: str = 'default'

    source = JsonConfigSettingsSource(MySettings, json_file=json_file_encoded, json_file_encoding='utf-8')
    assert source.json_file_encoding == 'utf-8'
    assert source.json_data == {'app_name': 'encoded_app'}


def test_init_encoding_from_model_config(json_file):
    class MySettings(BaseSettings):
        model_config = {'json_file': json_file, 'json_file_encoding': 'utf-8'}

        app_name: str = 'default'

    source = JsonConfigSettingsSource(MySettings)
    assert source.json_file_encoding == 'utf-8'


def test_init_with_nonexistent_file(tmp_path):
    nonexistent = tmp_path / 'nonexistent.json'

    class MySettings(BaseSettings):
        app_name: str = 'default'

    source = JsonConfigSettingsSource(MySettings, json_file=nonexistent)
    assert source.json_data == {}


def test_init_with_deep_merge(tmp_path):
    file1 = tmp_path / 'settings1.json'
    file2 = tmp_path / 'settings2.json'
    file1.write_text(json.dumps({'nested': {'a': 1, 'b': 2}}))
    file2.write_text(json.dumps({'nested': {'b': 3, 'c': 4}}))

    class MySettings(BaseSettings):
        model_config = {'json_file': [file1, file2]}

    source = JsonConfigSettingsSource(MySettings, deep_merge=True)
    assert source.json_data == {'nested': {'a': 1, 'b': 3, 'c': 4}}


def test_read_file(json_file):
    class MySettings(BaseSettings):
        app_name: str = 'default'

    source = JsonConfigSettingsSource(MySettings, json_file=json_file)
    result = source._read_file(json_file)
    assert result == {'app_name': 'test_app', 'debug': True}


def test_repr(json_file):
    class MySettings(BaseSettings):
        app_name: str = 'default'

    source = JsonConfigSettingsSource(MySettings, json_file=json_file)
    result = repr(source)
    assert result == f'JsonConfigSettingsSource(json_file={json_file})'


def test_repr_with_none_file():
    class MySettings(BaseSettings):
        app_name: str = 'default'

    source = JsonConfigSettingsSource(MySettings, json_file=None)
    assert repr(source) == 'JsonConfigSettingsSource(json_file=None)'


def test_init_with_multiple_json_files(tmp_path):
    file1 = tmp_path / 'first.json'
    file2 = tmp_path / 'second.json'
    file1.write_text(json.dumps({'app_name': 'first'}))
    file2.write_text(json.dumps({'debug': True}))

    class MySettings(BaseSettings):
        app_name: str = 'default'
        debug: bool = False

    source = JsonConfigSettingsSource(MySettings, json_file=[file1, file2])
    assert source.json_data == {'app_name': 'first', 'debug': True}
