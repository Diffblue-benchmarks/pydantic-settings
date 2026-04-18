"""Tests for JsonConfigSettingsSource."""

import json
import tempfile
from pathlib import Path

import pytest

from pydantic_settings import BaseSettings
from pydantic_settings.sources import JsonConfigSettingsSource


class SimpleSettings(BaseSettings):
    """Simple settings class for testing."""

    name: str = 'default'
    value: int = 0


class SettingsWithJsonConfig(BaseSettings):
    """Settings with json_file configured in model_config."""

    name: str = 'default'
    value: int = 0

    model_config = {
        'json_file': None,
        'json_file_encoding': 'utf-8',
    }


class TestJsonConfigSettingsSourceInit:
    """Tests for JsonConfigSettingsSource.__init__"""

    def test_init_with_explicit_json_file(self, tmp_path: Path) -> None:
        """Test initialization with explicit json_file path."""
        json_file = tmp_path / 'config.json'
        json_file.write_text('{"name": "test", "value": 42}')

        source = JsonConfigSettingsSource(SimpleSettings, json_file=json_file)

        assert source.json_file_path == json_file
        assert source.json_data == {'name': 'test', 'value': 42}

    def test_init_with_json_file_encoding(self, tmp_path: Path) -> None:
        """Test initialization with explicit encoding."""
        json_file = tmp_path / 'config.json'
        json_file.write_text('{"name": "encoded", "value": 100}', encoding='utf-8')

        source = JsonConfigSettingsSource(
            SimpleSettings,
            json_file=json_file,
            json_file_encoding='utf-8',
        )

        assert source.json_file_encoding == 'utf-8'
        assert source.json_data == {'name': 'encoded', 'value': 100}

    def test_init_uses_model_config_json_file(self, tmp_path: Path) -> None:
        """Test that init uses model_config json_file when not explicitly provided."""

        class SettingsWithConfigFile(BaseSettings):
            name: str = 'default'

            model_config = {'json_file': tmp_path / 'model_config.json'}

        json_file = tmp_path / 'model_config.json'
        json_file.write_text('{"name": "from_model_config"}')

        source = JsonConfigSettingsSource(SettingsWithConfigFile)

        assert source.json_file_path == json_file
        assert source.json_data == {'name': 'from_model_config'}

    def test_init_uses_model_config_encoding(self, tmp_path: Path) -> None:
        """Test that init uses model_config json_file_encoding when not explicitly provided."""
        json_file = tmp_path / 'config.json'
        json_file.write_text('{"name": "test"}', encoding='utf-8')

        class SettingsWithEncoding(BaseSettings):
            name: str = 'default'

            model_config = {
                'json_file': json_file,
                'json_file_encoding': 'utf-8',
            }

        source = JsonConfigSettingsSource(SettingsWithEncoding)

        assert source.json_file_encoding == 'utf-8'

    def test_init_with_nonexistent_file(self, tmp_path: Path) -> None:
        """Test initialization with non-existent file returns empty data."""
        nonexistent = tmp_path / 'does_not_exist.json'

        source = JsonConfigSettingsSource(SimpleSettings, json_file=nonexistent)

        assert source.json_file_path == nonexistent
        assert source.json_data == {}

    def test_init_with_none_json_file(self) -> None:
        """Test initialization with None json_file."""
        source = JsonConfigSettingsSource(SimpleSettings, json_file=None)

        assert source.json_file_path is None
        assert source.json_data == {}

    def test_init_with_deep_merge_true(self, tmp_path: Path) -> None:
        """Test initialization with deep_merge=True."""
        json_file = tmp_path / 'config.json'
        json_file.write_text('{"name": "merged"}')

        source = JsonConfigSettingsSource(
            SimpleSettings,
            json_file=json_file,
            deep_merge=True,
        )

        assert source.json_data == {'name': 'merged'}

    def test_init_with_multiple_files(self, tmp_path: Path) -> None:
        """Test initialization with multiple JSON files."""
        file1 = tmp_path / 'config1.json'
        file2 = tmp_path / 'config2.json'
        file1.write_text('{"name": "first"}')
        file2.write_text('{"value": 99}')

        source = JsonConfigSettingsSource(
            SimpleSettings,
            json_file=[file1, file2],
        )

        assert source.json_data == {'name': 'first', 'value': 99}


class TestJsonConfigSettingsSourceReadFile:
    """Tests for JsonConfigSettingsSource._read_file"""

    def test_read_file_simple(self, tmp_path: Path) -> None:
        """Test reading a simple JSON file."""
        json_file = tmp_path / 'simple.json'
        json_file.write_text('{"key": "value", "number": 123}')

        source = JsonConfigSettingsSource(SimpleSettings, json_file=json_file)
        result = source._read_file(json_file)

        assert result == {'key': 'value', 'number': 123}

    def test_read_file_with_encoding(self, tmp_path: Path) -> None:
        """Test reading JSON file with specific encoding."""
        json_file = tmp_path / 'encoded.json'
        content = '{"message": "hello"}'
        json_file.write_text(content, encoding='utf-8')

        source = JsonConfigSettingsSource(
            SimpleSettings,
            json_file=json_file,
            json_file_encoding='utf-8',
        )
        result = source._read_file(json_file)

        assert result == {'message': 'hello'}

    def test_read_file_nested_data(self, tmp_path: Path) -> None:
        """Test reading JSON file with nested structure."""
        json_file = tmp_path / 'nested.json'
        nested_data = {'outer': {'inner': {'deep': 'value'}}, 'array': [1, 2, 3]}
        json_file.write_text(json.dumps(nested_data))

        source = JsonConfigSettingsSource(SimpleSettings, json_file=json_file)
        result = source._read_file(json_file)

        assert result == nested_data


class TestJsonConfigSettingsSourceRepr:
    """Tests for JsonConfigSettingsSource.__repr__"""

    def test_repr_with_path(self, tmp_path: Path) -> None:
        """Test __repr__ with a file path."""
        json_file = tmp_path / 'config.json'
        json_file.write_text('{}')

        source = JsonConfigSettingsSource(SimpleSettings, json_file=json_file)
        result = repr(source)

        assert 'JsonConfigSettingsSource' in result
        assert str(json_file) in result

    def test_repr_with_none_path(self) -> None:
        """Test __repr__ with None path."""
        source = JsonConfigSettingsSource(SimpleSettings, json_file=None)
        result = repr(source)

        assert 'JsonConfigSettingsSource' in result
        assert 'None' in result

    def test_repr_format(self, tmp_path: Path) -> None:
        """Test __repr__ returns expected format."""
        json_file = tmp_path / 'test.json'
        json_file.write_text('{}')

        source = JsonConfigSettingsSource(SimpleSettings, json_file=json_file)
        result = repr(source)

        expected = f'JsonConfigSettingsSource(json_file={json_file})'
        assert result == expected
