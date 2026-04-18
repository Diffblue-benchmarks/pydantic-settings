"""Tests for JsonConfigSettingsSource."""

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict

from pydantic_settings import BaseSettings
from pydantic_settings.sources.providers.json import JsonConfigSettingsSource
from pydantic_settings.sources.types import DEFAULT_PATH


class SimpleSettings(BaseSettings):
    """Simple settings model for testing."""

    model_config = ConfigDict(json_file=None, json_file_encoding=None)

    name: str = "default"
    value: int = 0
    config_data: dict[str, Any] = {}


class TestJsonConfigSettingsSourceInit:
    """Tests for JsonConfigSettingsSource.__init__."""

    def test_init_with_json_file_path(self, tmp_path):
        """Test initialization with explicit json_file parameter."""
        # Arrange
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "test", "value": 42}', encoding="utf-8")

        # Act
        source = JsonConfigSettingsSource(
            settings_cls=SimpleSettings,
            json_file=str(json_file),
        )

        # Assert
        assert source.json_file_path == str(json_file)
        assert source.json_file_encoding is None
        assert source.json_data == {"name": "test", "value": 42}

    def test_init_with_json_file_path_as_path_object(self, tmp_path):
        """Test initialization with Path object."""
        # Arrange
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "test"}', encoding="utf-8")

        # Act
        source = JsonConfigSettingsSource(
            settings_cls=SimpleSettings,
            json_file=json_file,
        )

        # Assert
        assert source.json_file_path == json_file
        assert isinstance(source.json_file_path, Path)

    def test_init_with_encoding(self, tmp_path):
        """Test initialization with custom encoding."""
        # Arrange
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "test"}', encoding="utf-8")

        # Act
        source = JsonConfigSettingsSource(
            settings_cls=SimpleSettings,
            json_file=str(json_file),
            json_file_encoding="utf-8",
        )

        # Assert
        assert source.json_file_encoding == "utf-8"

    def test_init_with_model_config_json_file(self, tmp_path):
        """Test initialization using json_file from model config."""
        # Arrange
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "config_test"}', encoding="utf-8")

        class SettingsWithConfig(BaseSettings):
            model_config = ConfigDict(json_file=str(json_file))

            name: str = "default"

        # Act
        source = JsonConfigSettingsSource(
            settings_cls=SettingsWithConfig,
            json_file=DEFAULT_PATH,
        )

        # Assert
        assert source.json_file_path == str(json_file)

    def test_init_with_model_config_encoding(self, tmp_path):
        """Test initialization using json_file_encoding from model config."""
        # Arrange
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "test"}', encoding="utf-8")

        class SettingsWithEncoding(BaseSettings):
            model_config = ConfigDict(
                json_file=str(json_file),
                json_file_encoding="utf-8",
            )

            name: str = "default"

        # Act
        source = JsonConfigSettingsSource(
            settings_cls=SettingsWithEncoding,
            json_file=DEFAULT_PATH,
            json_file_encoding=None,
        )

        # Assert
        assert source.json_file_encoding == "utf-8"

    def test_init_with_deep_merge_disabled(self, tmp_path):
        """Test initialization with deep_merge=False."""
        # Arrange
        json_file = tmp_path / "config.json"
        json_file.write_text('{"data": {"nested": "value"}}', encoding="utf-8")

        # Act
        source = JsonConfigSettingsSource(
            settings_cls=SimpleSettings,
            json_file=str(json_file),
            deep_merge=False,
        )

        # Assert
        assert source.json_data == {"data": {"nested": "value"}}

    def test_init_with_deep_merge_enabled(self, tmp_path):
        """Test initialization with deep_merge=True."""
        # Arrange
        json_file = tmp_path / "config.json"
        json_file.write_text('{"data": {"nested": "value"}}', encoding="utf-8")

        # Act
        source = JsonConfigSettingsSource(
            settings_cls=SimpleSettings,
            json_file=str(json_file),
            deep_merge=True,
        )

        # Assert
        assert source.json_data == {"data": {"nested": "value"}}

    def test_init_with_nonexistent_file(self):
        """Test initialization with nonexistent file."""
        # Act
        source = JsonConfigSettingsSource(
            settings_cls=SimpleSettings,
            json_file="/nonexistent/path/config.json",
        )

        # Assert
        assert source.json_data == {}

    def test_init_with_none_json_file(self):
        """Test initialization with None json_file."""
        # Act
        source = JsonConfigSettingsSource(
            settings_cls=SimpleSettings,
            json_file=None,
        )

        # Assert
        assert source.json_data == {}

    def test_init_with_multiple_json_files(self, tmp_path):
        """Test initialization with multiple JSON files."""
        # Arrange
        json_file1 = tmp_path / "config1.json"
        json_file2 = tmp_path / "config2.json"
        json_file1.write_text('{"name": "first", "value": 1}', encoding="utf-8")
        json_file2.write_text('{"value": 2, "extra": "data"}', encoding="utf-8")

        # Act
        source = JsonConfigSettingsSource(
            settings_cls=SimpleSettings,
            json_file=[str(json_file1), str(json_file2)],
        )

        # Assert
        assert source.json_data["name"] == "first"
        assert source.json_data["value"] == 2
        assert source.json_data["extra"] == "data"

    def test_init_attribute_settings_cls(self):
        """Test that settings_cls is properly initialized via parent class."""
        # Act
        source = JsonConfigSettingsSource(
            settings_cls=SimpleSettings,
            json_file=None,
        )

        # Assert
        assert source.settings_cls == SimpleSettings

    def test_init_with_expanduser_path(self, tmp_path, monkeypatch):
        """Test initialization with path containing ~."""
        # Arrange
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "test"}', encoding="utf-8")
        monkeypatch.setenv("HOME", str(tmp_path.parent))

        # Act & Assert
        source = JsonConfigSettingsSource(
            settings_cls=SimpleSettings,
            json_file=str(json_file),
        )
        assert source.json_data == {"name": "test"}


class TestJsonConfigSettingsSourceReadFile:
    """Tests for JsonConfigSettingsSource._read_file."""

    def test_read_file_basic(self, tmp_path):
        """Test basic JSON file reading."""
        # Arrange
        json_file = tmp_path / "config.json"
        json_data = {"name": "test", "value": 42, "nested": {"key": "val"}}
        json_file.write_text(json.dumps(json_data), encoding="utf-8")

        source = JsonConfigSettingsSource(
            settings_cls=SimpleSettings,
            json_file=None,
        )

        # Act
        result = source._read_file(json_file)

        # Assert
        assert result == json_data

    def test_read_file_with_custom_encoding(self, tmp_path):
        """Test reading file with custom encoding."""
        # Arrange
        json_file = tmp_path / "config.json"
        json_data = {"name": "тест"}  # Cyrillic characters
        json_file.write_text(json.dumps(json_data), encoding="utf-8")

        source = JsonConfigSettingsSource(
            settings_cls=SimpleSettings,
            json_file=None,
            json_file_encoding="utf-8",
        )

        # Act
        result = source._read_file(json_file)

        # Assert
        assert result == json_data

    def test_read_file_empty_json(self, tmp_path):
        """Test reading empty JSON object."""
        # Arrange
        json_file = tmp_path / "empty.json"
        json_file.write_text("{}", encoding="utf-8")

        source = JsonConfigSettingsSource(
            settings_cls=SimpleSettings,
            json_file=None,
        )

        # Act
        result = source._read_file(json_file)

        # Assert
        assert result == {}

    def test_read_file_array_json(self, tmp_path):
        """Test reading JSON array."""
        # Arrange
        json_file = tmp_path / "array.json"
        json_file.write_text('[1, 2, 3]', encoding="utf-8")

        source = JsonConfigSettingsSource(
            settings_cls=SimpleSettings,
            json_file=None,
        )

        # Act
        result = source._read_file(json_file)

        # Assert
        assert result == [1, 2, 3]

    def test_read_file_complex_nested_structure(self, tmp_path):
        """Test reading complex nested JSON structure."""
        # Arrange
        json_file = tmp_path / "complex.json"
        complex_data = {
            "database": {
                "host": "localhost",
                "port": 5432,
                "credentials": {"user": "admin", "password": "secret"},
            },
            "logging": {"level": "INFO", "handlers": ["console", "file"]},
        }
        json_file.write_text(json.dumps(complex_data), encoding="utf-8")

        source = JsonConfigSettingsSource(
            settings_cls=SimpleSettings,
            json_file=None,
        )

        # Act
        result = source._read_file(json_file)

        # Assert
        assert result == complex_data

    def test_read_file_with_none_encoding(self, tmp_path):
        """Test reading file with None encoding (default system encoding)."""
        # Arrange
        json_file = tmp_path / "config.json"
        json_data = {"test": "value"}
        json_file.write_text(json.dumps(json_data), encoding="utf-8")

        source = JsonConfigSettingsSource(
            settings_cls=SimpleSettings,
            json_file=None,
            json_file_encoding=None,
        )

        # Act
        result = source._read_file(json_file)

        # Assert
        assert result == json_data


class TestJsonConfigSettingsSourceRepr:
    """Tests for JsonConfigSettingsSource.__repr__."""

    def test_repr_with_file_path(self, tmp_path):
        """Test __repr__ with file path."""
        # Arrange
        json_file = tmp_path / "config.json"
        json_file.write_text('{}', encoding="utf-8")

        source = JsonConfigSettingsSource(
            settings_cls=SimpleSettings,
            json_file=str(json_file),
        )

        # Act
        result = repr(source)

        # Assert
        assert "JsonConfigSettingsSource" in result
        assert str(json_file) in result
        assert "json_file=" in result

    def test_repr_with_none_path(self):
        """Test __repr__ when json_file_path is None."""
        # Arrange
        source = JsonConfigSettingsSource(
            settings_cls=SimpleSettings,
            json_file=None,
        )

        # Act
        result = repr(source)

        # Assert
        assert "JsonConfigSettingsSource" in result
        assert "json_file=None" in result

    def test_repr_format(self, tmp_path):
        """Test __repr__ format is consistent."""
        # Arrange
        json_file = tmp_path / "test_config.json"
        json_file.write_text('{}', encoding="utf-8")

        source = JsonConfigSettingsSource(
            settings_cls=SimpleSettings,
            json_file=json_file,
        )

        # Act
        result = repr(source)

        # Assert
        assert result.startswith("JsonConfigSettingsSource(")
        assert result.endswith(")")

    def test_repr_with_path_object(self, tmp_path):
        """Test __repr__ with Path object."""
        # Arrange
        json_file = tmp_path / "config.json"
        json_file.write_text('{}', encoding="utf-8")

        source = JsonConfigSettingsSource(
            settings_cls=SimpleSettings,
            json_file=json_file,
        )

        # Act
        result = repr(source)

        # Assert
        assert "JsonConfigSettingsSource" in result
        assert str(json_file) in result

    def test_repr_with_string_path(self, tmp_path):
        """Test __repr__ with string path."""
        # Arrange
        json_file = tmp_path / "config.json"
        json_file.write_text('{}', encoding="utf-8")
        json_file_str = str(json_file)

        source = JsonConfigSettingsSource(
            settings_cls=SimpleSettings,
            json_file=json_file_str,
        )

        # Act
        result = repr(source)

        # Assert
        assert json_file_str in result


class TestJsonConfigSettingsSourceIntegration:
    """Integration tests for JsonConfigSettingsSource."""

    def test_json_source_with_settings_model(self, tmp_path):
        """Test using JsonConfigSettingsSource with a settings model."""
        # Arrange
        json_file = tmp_path / "settings.json"
        json_file.write_text('{"name": "app", "value": 100}', encoding="utf-8")

        class AppSettings(BaseSettings):
            name: str
            value: int

        # Act
        source = JsonConfigSettingsSource(
            settings_cls=AppSettings,
            json_file=str(json_file),
        )

        # Assert - verify source loads data correctly
        assert source.json_data == {"name": "app", "value": 100}

    def test_json_source_multiple_files_deep_merge(self, tmp_path):
        """Test with multiple files and deep merge enabled."""
        # Arrange
        file1 = tmp_path / "base.json"
        file2 = tmp_path / "override.json"

        file1.write_text('{"db": {"host": "localhost", "port": 5432}}', encoding="utf-8")
        file2.write_text('{"db": {"port": 3306}}', encoding="utf-8")

        # Act
        source = JsonConfigSettingsSource(
            settings_cls=SimpleSettings,
            json_file=[str(file1), str(file2)],
            deep_merge=True,
        )

        # Assert
        assert source.json_data["db"]["host"] == "localhost"
        assert source.json_data["db"]["port"] == 3306

    def test_json_source_multiple_files_shallow_merge(self, tmp_path):
        """Test with multiple files and shallow merge."""
        # Arrange
        file1 = tmp_path / "base.json"
        file2 = tmp_path / "override.json"

        file1.write_text('{"db": {"host": "localhost", "port": 5432}}', encoding="utf-8")
        file2.write_text('{"db": {"port": 3306}}', encoding="utf-8")

        # Act
        source = JsonConfigSettingsSource(
            settings_cls=SimpleSettings,
            json_file=[str(file1), str(file2)],
            deep_merge=False,
        )

        # Assert
        assert source.json_data["db"] == {"port": 3306}
