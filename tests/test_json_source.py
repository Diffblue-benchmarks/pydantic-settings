"""Tests for JsonConfigSettingsSource."""

import json
import tempfile
from pathlib import Path

import pytest
from pydantic import BaseModel

from pydantic_settings import BaseSettings
from pydantic_settings.sources import DEFAULT_PATH
from pydantic_settings.sources.providers.json import JsonConfigSettingsSource


class TestJsonConfigSettingsSource:
    """Tests for JsonConfigSettingsSource class."""

    def test_init_with_default_path_and_model_config(self, tmp_path):
        """Test __init__ when json_file is DEFAULT_PATH and model has json_file config."""
        json_file = tmp_path / "config.json"
        json_file.write_text('{"value": "from_json"}')

        class Settings(BaseSettings):
            value: str = "default"
            model_config = {"json_file": json_file}

        source = JsonConfigSettingsSource(settings_cls=Settings, json_file=DEFAULT_PATH)

        assert source.json_file_path == json_file
        assert source.json_data == {"value": "from_json"}

    def test_init_with_explicit_json_file(self, tmp_path):
        """Test __init__ with explicitly provided json_file parameter."""
        json_file = tmp_path / "config.json"
        json_file.write_text('{"value": "explicit_file"}')

        class Settings(BaseSettings):
            value: str = "default"

        source = JsonConfigSettingsSource(settings_cls=Settings, json_file=json_file)

        assert source.json_file_path == json_file
        assert source.json_data == {"value": "explicit_file"}

    def test_init_with_json_file_encoding_param(self, tmp_path):
        """Test __init__ with json_file_encoding parameter."""
        json_file = tmp_path / "config.json"
        json_file.write_text('{"value": "test"}', encoding="utf-8")

        class Settings(BaseSettings):
            value: str = "default"

        source = JsonConfigSettingsSource(
            settings_cls=Settings, json_file=json_file, json_file_encoding="utf-8"
        )

        assert source.json_file_encoding == "utf-8"
        assert source.json_data == {"value": "test"}

    def test_init_with_model_config_encoding(self, tmp_path):
        """Test __init__ when json_file_encoding comes from model_config."""
        json_file = tmp_path / "config.json"
        json_file.write_text('{"value": "config_encoding"}', encoding="utf-8")

        class Settings(BaseSettings):
            value: str = "default"
            model_config = {"json_file_encoding": "utf-8"}

        source = JsonConfigSettingsSource(settings_cls=Settings, json_file=json_file)

        assert source.json_file_encoding == "utf-8"
        assert source.json_data == {"value": "config_encoding"}

    def test_init_encoding_param_overrides_model_config(self, tmp_path):
        """Test that json_file_encoding parameter overrides model_config."""
        json_file = tmp_path / "config.json"
        json_file.write_text('{"value": "override"}', encoding="utf-8")

        class Settings(BaseSettings):
            value: str = "default"
            model_config = {"json_file_encoding": "latin-1"}

        source = JsonConfigSettingsSource(
            settings_cls=Settings, json_file=json_file, json_file_encoding="utf-8"
        )

        assert source.json_file_encoding == "utf-8"
        assert source.json_data == {"value": "override"}

    def test_init_with_deep_merge_true(self, tmp_path):
        """Test __init__ with deep_merge=True."""
        json_file = tmp_path / "config.json"
        json_file.write_text('{"nested": {"key": "value"}}')

        class Settings(BaseSettings):
            nested: dict = {}

        source = JsonConfigSettingsSource(
            settings_cls=Settings, json_file=json_file, deep_merge=True
        )

        assert source.json_data == {"nested": {"key": "value"}}

    def test_init_with_deep_merge_false(self, tmp_path):
        """Test __init__ with deep_merge=False (default)."""
        json_file = tmp_path / "config.json"
        json_file.write_text('{"key": "value"}')

        class Settings(BaseSettings):
            key: str = "default"

        source = JsonConfigSettingsSource(
            settings_cls=Settings, json_file=json_file, deep_merge=False
        )

        assert source.json_data == {"key": "value"}

    def test_init_with_none_json_file(self):
        """Test __init__ when json_file is None."""
        class Settings(BaseSettings):
            value: str = "default"

        source = JsonConfigSettingsSource(settings_cls=Settings, json_file=None)

        assert source.json_file_path is None
        assert source.json_data == {}

    def test_init_with_nonexistent_file(self, tmp_path):
        """Test __init__ when json_file does not exist."""
        json_file = tmp_path / "nonexistent.json"

        class Settings(BaseSettings):
            value: str = "default"

        source = JsonConfigSettingsSource(settings_cls=Settings, json_file=json_file)

        assert source.json_file_path == json_file
        assert source.json_data == {}

    def test_read_file_basic(self, tmp_path):
        """Test _read_file with a basic JSON file."""
        json_file = tmp_path / "test.json"
        test_data = {"key1": "value1", "key2": 42, "key3": [1, 2, 3]}
        json_file.write_text(json.dumps(test_data))

        class Settings(BaseSettings):
            pass

        source = JsonConfigSettingsSource(settings_cls=Settings, json_file=json_file)
        result = source._read_file(json_file)

        assert result == test_data

    def test_read_file_with_encoding(self, tmp_path):
        """Test _read_file with specific encoding."""
        json_file = tmp_path / "encoded.json"
        test_data = {"key": "value with special chars: \u00e9\u00e0\u00fc"}
        json_file.write_text(json.dumps(test_data), encoding="utf-8")

        class Settings(BaseSettings):
            pass

        source = JsonConfigSettingsSource(
            settings_cls=Settings, json_file=json_file, json_file_encoding="utf-8"
        )
        result = source._read_file(json_file)

        assert result == test_data

    def test_read_file_complex_structure(self, tmp_path):
        """Test _read_file with nested JSON structure."""
        json_file = tmp_path / "complex.json"
        test_data = {
            "database": {"host": "localhost", "port": 5432, "credentials": {"user": "admin"}},
            "features": ["auth", "logging", "monitoring"],
        }
        json_file.write_text(json.dumps(test_data))

        class Settings(BaseSettings):
            pass

        source = JsonConfigSettingsSource(settings_cls=Settings, json_file=json_file)
        result = source._read_file(json_file)

        assert result == test_data

    def test_repr_with_path(self, tmp_path):
        """Test __repr__ returns correct string representation."""
        json_file = tmp_path / "config.json"
        json_file.write_text('{"key": "value"}')

        class Settings(BaseSettings):
            pass

        source = JsonConfigSettingsSource(settings_cls=Settings, json_file=json_file)
        repr_str = repr(source)

        assert repr_str == f"JsonConfigSettingsSource(json_file={json_file})"

    def test_repr_with_none(self):
        """Test __repr__ when json_file_path is None."""
        class Settings(BaseSettings):
            pass

        source = JsonConfigSettingsSource(settings_cls=Settings, json_file=None)
        repr_str = repr(source)

        assert repr_str == "JsonConfigSettingsSource(json_file=None)"
