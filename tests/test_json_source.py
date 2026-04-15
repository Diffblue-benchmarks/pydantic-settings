"""Tests for JsonConfigSettingsSource."""

import json
import tempfile
from pathlib import Path

import pytest
from pydantic import Field

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic_settings.sources.providers.json import JsonConfigSettingsSource


class SimpleSettings(BaseSettings):
    model_config = SettingsConfigDict(json_file=None)

    name: str = "default"
    value: int = 0


@pytest.fixture
def json_file(tmp_path):
    data = {"name": "test_name", "value": 42}
    file = tmp_path / "settings.json"
    file.write_text(json.dumps(data))
    return file


@pytest.fixture
def json_file_utf8(tmp_path):
    data = {"name": "héllo"}
    file = tmp_path / "settings_utf8.json"
    file.write_text(json.dumps(data), encoding="utf-8")
    return file


def test_init_with_explicit_json_file(json_file):
    source = JsonConfigSettingsSource(SimpleSettings, json_file=json_file)
    assert source.json_file_path == json_file
    assert source.json_data == {"name": "test_name", "value": 42}


def test_init_uses_model_config_json_file(tmp_path):
    data = {"name": "from_config"}
    file = tmp_path / "config.json"
    file.write_text(json.dumps(data))

    class ConfigSettings(BaseSettings):
        model_config = SettingsConfigDict(json_file=str(file))
        name: str = "default"

    source = JsonConfigSettingsSource(ConfigSettings)
    assert source.json_data.get("name") == "from_config"


def test_init_with_explicit_encoding(json_file_utf8):
    source = JsonConfigSettingsSource(
        SimpleSettings, json_file=json_file_utf8, json_file_encoding="utf-8"
    )
    assert source.json_file_encoding == "utf-8"
    assert source.json_data["name"] == "héllo"


def test_init_uses_model_config_encoding(tmp_path):
    data = {"name": "héllo"}
    file = tmp_path / "settings_enc.json"
    file.write_text(json.dumps(data), encoding="utf-8")

    class EncodingSettings(BaseSettings):
        model_config = SettingsConfigDict(json_file=str(file), json_file_encoding="utf-8")
        name: str = "default"

    source = JsonConfigSettingsSource(EncodingSettings)
    assert source.json_file_encoding == "utf-8"
    assert source.json_data["name"] == "héllo"


def test_init_no_json_file():
    source = JsonConfigSettingsSource(SimpleSettings, json_file=None)
    assert source.json_file_path is None
    assert source.json_data == {}


def test_init_deep_merge(tmp_path):
    file1 = tmp_path / "s1.json"
    file2 = tmp_path / "s2.json"
    file1.write_text(json.dumps({"name": "first", "value": 1}))
    file2.write_text(json.dumps({"name": "second"}))

    source = JsonConfigSettingsSource(
        SimpleSettings, json_file=[file1, file2], deep_merge=True
    )
    assert source.json_data["name"] == "second"
    assert source.json_data["value"] == 1


def test_read_file(json_file):
    source = JsonConfigSettingsSource(SimpleSettings, json_file=None)
    source.json_file_encoding = None
    result = source._read_file(json_file)
    assert result == {"name": "test_name", "value": 42}


def test_read_file_with_encoding(json_file_utf8):
    source = JsonConfigSettingsSource(SimpleSettings, json_file=None)
    source.json_file_encoding = "utf-8"
    result = source._read_file(json_file_utf8)
    assert result["name"] == "héllo"


def test_repr_with_file(json_file):
    source = JsonConfigSettingsSource(SimpleSettings, json_file=json_file)
    repr_str = repr(source)
    assert "JsonConfigSettingsSource" in repr_str
    assert "json_file=" in repr_str


def test_repr_without_file():
    source = JsonConfigSettingsSource(SimpleSettings, json_file=None)
    assert repr(source) == "JsonConfigSettingsSource(json_file=None)"
