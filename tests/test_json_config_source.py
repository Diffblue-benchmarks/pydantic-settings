"""Tests for JsonConfigSettingsSource."""

import json
from pathlib import Path
from typing import Optional

import pytest
from pydantic import BaseModel

from pydantic_settings import BaseSettings
from pydantic_settings.sources import JsonConfigSettingsSource


class SimpleSettings(BaseSettings):
    """Simple settings model for testing."""

    name: str = "default"
    value: int = 0
    enabled: bool = False


class SettingsWithJsonConfig(BaseSettings):
    """Settings model with json_file in model_config."""

    name: str = "default"
    value: int = 0

    model_config = {"json_file": "config.json", "json_file_encoding": "utf-8"}


class TestJsonConfigSettingsSource:
    """Tests for JsonConfigSettingsSource class."""

    def test_init_with_explicit_json_file(self, tmp_path):
        """Test initialization with an explicit JSON file path."""
        # Arrange
        json_file = tmp_path / "test.json"
        json_file.write_text('{"name": "test", "value": 42}')

        # Act
        source = JsonConfigSettingsSource(
            settings_cls=SimpleSettings, json_file=json_file
        )

        # Assert
        assert source.json_file_path == json_file
        assert source.json_data == {"name": "test", "value": 42}

    def test_init_with_default_path_uses_model_config(self, tmp_path):
        """Test initialization with DEFAULT_PATH uses model_config json_file."""
        # Arrange
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "from_config", "value": 99}')

        # Need to temporarily set the json_file in model_config to an absolute path
        original_config = SettingsWithJsonConfig.model_config.copy()
        SettingsWithJsonConfig.model_config["json_file"] = str(json_file)

        try:
            # Act
            from pydantic_settings.sources.types import DEFAULT_PATH

            source = JsonConfigSettingsSource(
                settings_cls=SettingsWithJsonConfig, json_file=DEFAULT_PATH
            )

            # Assert
            assert source.json_file_path == str(json_file)
            assert source.json_data == {"name": "from_config", "value": 99}
        finally:
            # Restore original config
            SettingsWithJsonConfig.model_config.update(original_config)

    def test_init_with_explicit_encoding(self, tmp_path):
        """Test initialization with an explicit encoding."""
        # Arrange
        json_file = tmp_path / "test_utf8.json"
        json_file.write_text('{"name": "テスト", "value": 1}', encoding="utf-8")

        # Act
        source = JsonConfigSettingsSource(
            settings_cls=SimpleSettings, json_file=json_file, json_file_encoding="utf-8"
        )

        # Assert
        assert source.json_file_encoding == "utf-8"
        assert source.json_data == {"name": "テスト", "value": 1}

    def test_init_with_encoding_from_model_config(self, tmp_path):
        """Test initialization uses encoding from model_config when not provided."""
        # Arrange
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "test", "value": 10}', encoding="utf-8")

        # Need to set json_file to absolute path
        original_config = SettingsWithJsonConfig.model_config.copy()
        SettingsWithJsonConfig.model_config["json_file"] = str(json_file)

        try:
            # Act
            from pydantic_settings.sources.types import DEFAULT_PATH

            source = JsonConfigSettingsSource(
                settings_cls=SettingsWithJsonConfig, json_file=DEFAULT_PATH
            )

            # Assert
            assert source.json_file_encoding == "utf-8"
        finally:
            # Restore original config
            SettingsWithJsonConfig.model_config.update(original_config)

    def test_init_with_deep_merge_false(self, tmp_path):
        """Test initialization with deep_merge=False."""
        # Arrange
        json_file = tmp_path / "test.json"
        json_file.write_text('{"name": "test", "value": 5}')

        # Act
        source = JsonConfigSettingsSource(
            settings_cls=SimpleSettings, json_file=json_file, deep_merge=False
        )

        # Assert
        assert source.json_data == {"name": "test", "value": 5}

    def test_init_with_deep_merge_true(self, tmp_path):
        """Test initialization with deep_merge=True."""
        # Arrange
        json_file1 = tmp_path / "test1.json"
        json_file2 = tmp_path / "test2.json"
        json_file1.write_text('{"name": "first", "value": 1}')
        json_file2.write_text('{"name": "second", "enabled": true}')

        # Act
        source = JsonConfigSettingsSource(
            settings_cls=SimpleSettings, json_file=[json_file1, json_file2], deep_merge=True
        )

        # Assert
        assert source.json_data["name"] == "second"
        assert source.json_data["value"] == 1

    def test_init_with_none_json_file(self):
        """Test initialization with None json_file."""
        # Act
        source = JsonConfigSettingsSource(
            settings_cls=SimpleSettings, json_file=None
        )

        # Assert
        assert source.json_file_path is None
        assert source.json_data == {}

    def test_init_with_multiple_json_files(self, tmp_path):
        """Test initialization with multiple JSON files."""
        # Arrange
        json_file1 = tmp_path / "test1.json"
        json_file2 = tmp_path / "test2.json"
        json_file1.write_text('{"name": "first", "value": 1}')
        json_file2.write_text('{"value": 2, "enabled": true}')

        # Act
        source = JsonConfigSettingsSource(
            settings_cls=SimpleSettings, json_file=[json_file1, json_file2]
        )

        # Assert
        assert source.json_data == {"name": "first", "value": 2, "enabled": True}

    def test_read_file_basic(self, tmp_path):
        """Test _read_file with a basic JSON file."""
        # Arrange
        json_file = tmp_path / "test.json"
        json_content = {"key1": "value1", "key2": 123, "key3": True}
        json_file.write_text(json.dumps(json_content))

        source = JsonConfigSettingsSource(
            settings_cls=SimpleSettings, json_file=json_file
        )

        # Act
        result = source._read_file(json_file)

        # Assert
        assert result == json_content

    def test_read_file_with_encoding(self, tmp_path):
        """Test _read_file respects encoding."""
        # Arrange
        json_file = tmp_path / "test_encoded.json"
        json_content = {"name": "日本語", "value": 42}
        json_file.write_text(json.dumps(json_content), encoding="utf-8")

        source = JsonConfigSettingsSource(
            settings_cls=SimpleSettings, json_file=json_file, json_file_encoding="utf-8"
        )

        # Act
        result = source._read_file(json_file)

        # Assert
        assert result == json_content

    def test_read_file_with_nested_structure(self, tmp_path):
        """Test _read_file with nested JSON structure."""
        # Arrange
        json_file = tmp_path / "nested.json"
        json_content = {
            "name": "test",
            "nested": {"key": "value", "number": 123},
            "list": [1, 2, 3],
        }
        json_file.write_text(json.dumps(json_content))

        source = JsonConfigSettingsSource(
            settings_cls=SimpleSettings, json_file=json_file
        )

        # Act
        result = source._read_file(json_file)

        # Assert
        assert result == json_content

    def test_repr_with_file_path(self, tmp_path):
        """Test __repr__ with a file path."""
        # Arrange
        json_file = tmp_path / "test.json"
        json_file.write_text('{"name": "test"}')

        source = JsonConfigSettingsSource(
            settings_cls=SimpleSettings, json_file=json_file
        )

        # Act
        repr_str = repr(source)

        # Assert
        assert "JsonConfigSettingsSource" in repr_str
        assert str(json_file) in repr_str

    def test_repr_with_none_path(self):
        """Test __repr__ with None path."""
        # Act
        source = JsonConfigSettingsSource(
            settings_cls=SimpleSettings, json_file=None
        )

        # Act
        repr_str = repr(source)

        # Assert
        assert "JsonConfigSettingsSource" in repr_str
        assert "None" in repr_str
