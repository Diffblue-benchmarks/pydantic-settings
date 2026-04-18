"""Tests for JsonConfigSettingsSource."""

import json
from pathlib import Path

import pytest

from pydantic_settings import BaseSettings
from pydantic_settings.sources.providers.json import JsonConfigSettingsSource


@pytest.fixture
def tmp_json_file(tmp_path):
    """Create a temporary JSON file with sample settings."""
    json_file = tmp_path / 'settings.json'
    json_file.write_text(json.dumps({'app_name': 'test_app', 'debug': True}))
    return json_file


@pytest.fixture
def tmp_json_file_encoded(tmp_path):
    """Create a temporary JSON file with UTF-8 encoded content."""
    json_file = tmp_path / 'settings_encoded.json'
    json_file.write_text(json.dumps({'app_name': 'tëst_àpp'}), encoding='utf-8')
    return json_file


class SimpleSettings(BaseSettings):
    app_name: str = 'default'
    debug: bool = False


def test_init_with_explicit_json_file(tmp_json_file):
    source = JsonConfigSettingsSource(SimpleSettings, json_file=tmp_json_file)

    assert source.json_file_path == tmp_json_file
    assert source.json_file_encoding is None
    assert source.json_data == {'app_name': 'test_app', 'debug': True}


def test_init_with_encoding(tmp_json_file_encoded):
    source = JsonConfigSettingsSource(
        SimpleSettings, json_file=tmp_json_file_encoded, json_file_encoding='utf-8'
    )

    assert source.json_file_encoding == 'utf-8'
    assert source.json_data == {'app_name': 'tëst_àpp'}


def test_init_with_default_path_uses_model_config(tmp_json_file):
    class SettingsWithJsonFile(BaseSettings):
        model_config = {'json_file': tmp_json_file, 'json_file_encoding': 'utf-8'}  # type: ignore[assignment]
        app_name: str = 'default'
        debug: bool = False

    source = JsonConfigSettingsSource(SettingsWithJsonFile)

    assert source.json_file_path == tmp_json_file
    assert source.json_file_encoding == 'utf-8'
    assert source.json_data == {'app_name': 'test_app', 'debug': True}


def test_init_with_no_file():
    source = JsonConfigSettingsSource(SimpleSettings, json_file=None)

    assert source.json_file_path is None
    assert source.json_data == {}


def test_init_with_nonexistent_file(tmp_path):
    nonexistent = tmp_path / 'nonexistent.json'
    source = JsonConfigSettingsSource(SimpleSettings, json_file=nonexistent)

    assert source.json_file_path == nonexistent
    assert source.json_data == {}


def test_init_with_deep_merge(tmp_path):
    file1 = tmp_path / 'a.json'
    file2 = tmp_path / 'b.json'
    file1.write_text(json.dumps({'app_name': 'app1', 'debug': False}))
    file2.write_text(json.dumps({'app_name': 'app2'}))

    source = JsonConfigSettingsSource(
        SimpleSettings, json_file=[file1, file2], deep_merge=True
    )

    assert source.json_data == {'app_name': 'app2', 'debug': False}


def test_read_file(tmp_json_file):
    source = JsonConfigSettingsSource(SimpleSettings, json_file=tmp_json_file)
    result = source._read_file(tmp_json_file)

    assert result == {'app_name': 'test_app', 'debug': True}


def test_read_file_with_encoding(tmp_json_file_encoded):
    source = JsonConfigSettingsSource(
        SimpleSettings, json_file=tmp_json_file_encoded, json_file_encoding='utf-8'
    )
    result = source._read_file(tmp_json_file_encoded)

    assert result == {'app_name': 'tëst_àpp'}


def test_repr_with_file(tmp_json_file):
    source = JsonConfigSettingsSource(SimpleSettings, json_file=tmp_json_file)

    assert repr(source) == f'JsonConfigSettingsSource(json_file={tmp_json_file})'


def test_repr_with_none():
    source = JsonConfigSettingsSource(SimpleSettings, json_file=None)

    assert repr(source) == 'JsonConfigSettingsSource(json_file=None)'


def test_init_encoding_from_model_config(tmp_json_file_encoded):
    class SettingsWithEncoding(BaseSettings):
        model_config = {'json_file_encoding': 'utf-8'}  # type: ignore[assignment]
        app_name: str = 'default'

    source = JsonConfigSettingsSource(
        SettingsWithEncoding, json_file=tmp_json_file_encoded
    )

    assert source.json_file_encoding == 'utf-8'
    assert source.json_data == {'app_name': 'tëst_àpp'}
