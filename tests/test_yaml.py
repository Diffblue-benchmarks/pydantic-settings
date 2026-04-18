"""Tests for YAML configuration settings source."""

import os
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from pydantic import BaseModel
from pydantic_settings import BaseSettings
from pydantic_settings.sources.providers.yaml import (
    YamlConfigSettingsSource,
    import_yaml,
)


class TestImportYaml:
    """Tests for import_yaml function."""

    def test_import_yaml_first_call(self):
        """Test import_yaml imports yaml module on first call."""
        import pydantic_settings.sources.providers.yaml as yaml_module

        # Save original state
        original_yaml = yaml_module.yaml
        try:
            # Reset yaml to None to simulate first import
            yaml_module.yaml = None

            # Call import_yaml
            import_yaml()

            # Verify yaml is now imported
            assert yaml_module.yaml is not None
        finally:
            # Restore original state
            yaml_module.yaml = original_yaml

    def test_import_yaml_idempotent(self):
        """Test import_yaml is idempotent when called multiple times."""
        import pydantic_settings.sources.providers.yaml as yaml_module

        original_yaml = yaml_module.yaml
        try:
            # Ensure yaml is imported
            import_yaml()
            first_import = yaml_module.yaml

            # Call again
            import_yaml()
            second_import = yaml_module.yaml

            # Should be the same object
            assert first_import is second_import
        finally:
            yaml_module.yaml = original_yaml

    def test_import_yaml_raises_on_missing_pyyaml(self):
        """Test import_yaml raises ImportError when PyYAML is not installed."""
        import pydantic_settings.sources.providers.yaml as yaml_module

        original_yaml = yaml_module.yaml
        try:
            # Reset yaml to None
            yaml_module.yaml = None

            # Mock __import__ to raise ImportError for yaml
            with patch('builtins.__import__', side_effect=ImportError('No module named yaml')):
                with pytest.raises(ImportError, match='PyYAML is not installed'):
                    import_yaml()
        finally:
            yaml_module.yaml = original_yaml


class SimpleSettings(BaseSettings):
    """Simple settings class for testing."""
    test_field: str = 'default'

    model_config = {
        'yaml_file': None,
    }


class TestYamlConfigSettingsSourceInit:
    """Tests for YamlConfigSettingsSource.__init__."""

    def test_init_with_no_yaml_file(self):
        """Test initialization with no yaml file."""
        source = YamlConfigSettingsSource(SimpleSettings)
        assert source.yaml_file_path is None
        assert source.yaml_config_section is None

    def test_init_with_explicit_yaml_file(self, tmp_path):
        """Test initialization with explicit yaml file."""
        yaml_file = tmp_path / 'test.yaml'
        yaml_file.write_text('test_field: value_from_yaml')

        source = YamlConfigSettingsSource(
            SimpleSettings,
            yaml_file=str(yaml_file)
        )
        assert source.yaml_file_path == str(yaml_file)

    def test_init_with_yaml_file_from_model_config(self, tmp_path):
        """Test initialization pulls yaml_file from model_config."""
        yaml_file = tmp_path / 'config.yaml'
        yaml_file.write_text('test_field: from_config')

        class SettingsWithYamlFile(BaseSettings):
            test_field: str = 'default'

            model_config = {
                'yaml_file': str(yaml_file),
            }

        source = YamlConfigSettingsSource(SettingsWithYamlFile)
        assert source.yaml_file_path == str(yaml_file)

    def test_init_explicit_yaml_file_overrides_model_config(self, tmp_path):
        """Test explicit yaml_file parameter overrides model_config."""
        yaml_file1 = tmp_path / 'config1.yaml'
        yaml_file1.write_text('test_field: from_config')

        yaml_file2 = tmp_path / 'config2.yaml'
        yaml_file2.write_text('test_field: from_param')

        class SettingsWithYamlFile(BaseSettings):
            test_field: str = 'default'

            model_config = {
                'yaml_file': str(yaml_file1),
            }

        source = YamlConfigSettingsSource(
            SettingsWithYamlFile,
            yaml_file=str(yaml_file2)
        )
        assert source.yaml_file_path == str(yaml_file2)

    def test_init_with_yaml_file_encoding(self, tmp_path):
        """Test initialization with explicit yaml_file_encoding."""
        yaml_file = tmp_path / 'test.yaml'
        yaml_file.write_text('test_field: value', encoding='utf-8')

        source = YamlConfigSettingsSource(
            SimpleSettings,
            yaml_file=str(yaml_file),
            yaml_file_encoding='utf-8'
        )
        assert source.yaml_file_encoding == 'utf-8'

    def test_init_with_yaml_file_encoding_from_model_config(self, tmp_path):
        """Test initialization pulls yaml_file_encoding from model_config."""
        yaml_file = tmp_path / 'config.yaml'
        yaml_file.write_text('test_field: value', encoding='utf-8')

        class SettingsWithEncoding(BaseSettings):
            test_field: str = 'default'

            model_config = {
                'yaml_file': str(yaml_file),
                'yaml_file_encoding': 'utf-8',  # Use a valid encoding that matches file
            }

        source = YamlConfigSettingsSource(SettingsWithEncoding)
        assert source.yaml_file_encoding == 'utf-8'

    def test_init_with_yaml_config_section(self, tmp_path):
        """Test initialization with yaml_config_section."""
        yaml_file = tmp_path / 'config.yaml'
        yaml_file.write_text('database:\n  host: localhost\n  port: 5432')

        class DatabaseSettings(BaseSettings):
            host: str = 'default'

            model_config = {
                'yaml_file': str(yaml_file),
            }

        source = YamlConfigSettingsSource(
            DatabaseSettings,
            yaml_config_section='database'
        )
        assert source.yaml_config_section == 'database'
        assert source.yaml_data == {'host': 'localhost', 'port': 5432}

    def test_init_with_deep_merge(self, tmp_path):
        """Test initialization with deep_merge enabled."""
        yaml_file1 = tmp_path / 'config1.yaml'
        yaml_file1.write_text('database:\n  host: localhost')

        yaml_file2 = tmp_path / 'config2.yaml'
        yaml_file2.write_text('database:\n  port: 5432')

        class MergeSettings(BaseSettings):
            model_config = {}

        source = YamlConfigSettingsSource(
            MergeSettings,
            yaml_file=[str(yaml_file1), str(yaml_file2)],
            deep_merge=True
        )
        # Both files should be merged
        assert 'database' in source.yaml_data
        assert source.yaml_data['database']['host'] == 'localhost'
        assert source.yaml_data['database']['port'] == 5432

    def test_init_without_deep_merge(self, tmp_path):
        """Test initialization without deep_merge (default behavior)."""
        yaml_file1 = tmp_path / 'config1.yaml'
        yaml_file1.write_text('database:\n  host: localhost')

        yaml_file2 = tmp_path / 'config2.yaml'
        yaml_file2.write_text('database:\n  port: 5432')

        class MergeSettings(BaseSettings):
            model_config = {}

        source = YamlConfigSettingsSource(
            MergeSettings,
            yaml_file=[str(yaml_file1), str(yaml_file2)],
            deep_merge=False
        )
        # Second file overwrites first (no deep merge)
        assert source.yaml_data['database']['port'] == 5432
        assert 'host' not in source.yaml_data['database']


class TestYamlConfigSettingsSourceReadFile:
    """Tests for YamlConfigSettingsSource._read_file."""

    def test_read_file_valid_yaml(self, tmp_path):
        """Test reading a valid YAML file."""
        yaml_file = tmp_path / 'test.yaml'
        yaml_file.write_text('key: value\nnumber: 42')

        source = YamlConfigSettingsSource(SimpleSettings, yaml_file=str(yaml_file))
        result = source._read_file(yaml_file)

        assert result == {'key': 'value', 'number': 42}

    def test_read_file_empty_yaml(self, tmp_path):
        """Test reading an empty YAML file returns empty dict."""
        yaml_file = tmp_path / 'empty.yaml'
        yaml_file.write_text('')

        source = YamlConfigSettingsSource(SimpleSettings, yaml_file=str(yaml_file))
        result = source._read_file(yaml_file)

        assert result == {}

    def test_read_file_nested_yaml(self, tmp_path):
        """Test reading nested YAML structure."""
        yaml_file = tmp_path / 'nested.yaml'
        yaml_file.write_text('database:\n  host: localhost\n  port: 5432\n  credentials:\n    user: admin')

        source = YamlConfigSettingsSource(SimpleSettings, yaml_file=str(yaml_file))
        result = source._read_file(yaml_file)

        assert result['database']['host'] == 'localhost'
        assert result['database']['port'] == 5432
        assert result['database']['credentials']['user'] == 'admin'

    def test_read_file_with_custom_encoding(self, tmp_path):
        """Test reading YAML file with custom encoding."""
        yaml_file = tmp_path / 'encoded.yaml'
        yaml_file.write_text('key: value', encoding='utf-8')

        source = YamlConfigSettingsSource(
            SimpleSettings,
            yaml_file=str(yaml_file),
            yaml_file_encoding='utf-8'
        )
        result = source._read_file(yaml_file)

        assert result == {'key': 'value'}

    def test_read_file_with_special_characters(self, tmp_path):
        """Test reading YAML file with special characters."""
        yaml_file = tmp_path / 'special.yaml'
        yaml_file.write_text('message: "Hello, World! 你好"')

        source = YamlConfigSettingsSource(SimpleSettings, yaml_file=str(yaml_file))
        result = source._read_file(yaml_file)

        assert 'Hello' in result['message']


class TestYamlConfigSettingsSourceTraverseNestedSection:
    """Tests for YamlConfigSettingsSource._traverse_nested_section."""

    def test_traverse_simple_key(self):
        """Test traversing a simple key."""
        data = {'database': {'host': 'localhost'}}
        source = YamlConfigSettingsSource(SimpleSettings)

        result = source._traverse_nested_section(data, 'database')
        assert result == {'host': 'localhost'}

    def test_traverse_nested_path_with_dots(self):
        """Test traversing nested path using dot notation."""
        data = {'database': {'connection': {'host': 'localhost', 'port': 5432}}}
        source = YamlConfigSettingsSource(SimpleSettings)

        result = source._traverse_nested_section(data, 'database.connection')
        assert result == {'host': 'localhost', 'port': 5432}

    def test_traverse_deeply_nested_path(self):
        """Test traversing deeply nested path."""
        data = {
            'app': {
                'db': {
                    'primary': {
                        'host': 'primary-db',
                        'port': 5432
                    }
                }
            }
        }
        source = YamlConfigSettingsSource(SimpleSettings)

        result = source._traverse_nested_section(data, 'app.db.primary')
        assert result == {'host': 'primary-db', 'port': 5432}

    def test_traverse_key_with_literal_dot(self):
        """Test traversing a key that contains a literal dot."""
        data = {'database.primary': {'host': 'localhost'}}
        source = YamlConfigSettingsSource(SimpleSettings)

        result = source._traverse_nested_section(data, 'database.primary')
        assert result == {'host': 'localhost'}

    def test_traverse_empty_section_raises_error(self):
        """Test that empty section path raises ValueError."""
        data = {'section': {}}
        source = YamlConfigSettingsSource(SimpleSettings)

        with pytest.raises(ValueError, match='yaml_config_section cannot be empty'):
            source._traverse_nested_section(data, '', 'original')

    def test_traverse_missing_key_raises_error(self):
        """Test that missing key raises KeyError."""
        data = {'section': {}}
        source = YamlConfigSettingsSource(SimpleSettings)

        with pytest.raises(KeyError, match='yaml_config_section key "missing" not found'):
            source._traverse_nested_section(data, 'missing')

    def test_traverse_missing_nested_key_raises_error(self):
        """Test that missing nested key raises KeyError."""
        data = {'database': {'host': 'localhost'}}
        source = YamlConfigSettingsSource(SimpleSettings, yaml_file='test.yaml')

        with pytest.raises(KeyError, match='yaml_config_section key "database.port.number" not found'):
            source._traverse_nested_section(data, 'database.port.number')

    def test_traverse_non_dict_intermediate_raises_typeerror(self):
        """Test that non-dict intermediate value raises TypeError."""
        data = {'database': 'not_a_dict'}
        source = YamlConfigSettingsSource(SimpleSettings, yaml_file='test.yaml')

        with pytest.raises(TypeError, match='An intermediate value is not a dictionary'):
            source._traverse_nested_section(data, 'database.host')

    def test_traverse_with_numeric_values(self):
        """Test traversing to section containing numeric values."""
        data = {'config': {'timeout': 30, 'retries': 3}}
        source = YamlConfigSettingsSource(SimpleSettings)

        result = source._traverse_nested_section(data, 'config')
        assert result == {'timeout': 30, 'retries': 3}

    def test_traverse_with_list_values(self):
        """Test traversing to section containing list values."""
        data = {'servers': {'hosts': ['host1', 'host2']}}
        source = YamlConfigSettingsSource(SimpleSettings)

        result = source._traverse_nested_section(data, 'servers')
        assert result == {'hosts': ['host1', 'host2']}

    def test_traverse_with_boolean_values(self):
        """Test traversing to section containing boolean values."""
        data = {'feature': {'enabled': True, 'debug': False}}
        source = YamlConfigSettingsSource(SimpleSettings)

        result = source._traverse_nested_section(data, 'feature')
        assert result == {'enabled': True, 'debug': False}

    def test_traverse_multiple_dots_in_key(self):
        """Test traversing with multiple consecutive dots."""
        data = {'a..b': {'value': 'nested'}, 'a': {'b': 'simple'}}
        source = YamlConfigSettingsSource(SimpleSettings)

        # Try to access literal key with dots first
        result = source._traverse_nested_section(data, 'a..b')
        assert result == {'value': 'nested'}

    def test_traverse_partial_literal_key_match(self):
        """Test that longest literal key is tried first before splitting."""
        data = {
            'a.b.c': {'value': 'literal'},
            'a.b': {'c': {'value': 'nested'}},
        }
        source = YamlConfigSettingsSource(SimpleSettings)

        # Should find 'a.b.c' as literal key first
        result = source._traverse_nested_section(data, 'a.b.c')
        assert result == {'value': 'literal'}

    def test_traverse_fallback_to_nested_when_literal_missing(self):
        """Test fallback to nested traversal when literal key not found."""
        data = {
            'a': {
                'b': {
                    'c': {'value': 'nested'}
                }
            }
        }
        source = YamlConfigSettingsSource(SimpleSettings)

        result = source._traverse_nested_section(data, 'a.b.c')
        assert result == {'value': 'nested'}


class TestYamlConfigSettingsSourceRepr:
    """Tests for YamlConfigSettingsSource.__repr__."""

    def test_repr_with_yaml_file(self, tmp_path):
        """Test __repr__ includes yaml_file path."""
        yaml_file = tmp_path / 'config.yaml'
        yaml_file.write_text('key: value')

        source = YamlConfigSettingsSource(
            SimpleSettings,
            yaml_file=str(yaml_file)
        )
        repr_str = repr(source)

        assert 'YamlConfigSettingsSource' in repr_str
        assert str(yaml_file) in repr_str

    def test_repr_with_no_yaml_file(self):
        """Test __repr__ when yaml_file is None."""
        source = YamlConfigSettingsSource(SimpleSettings)
        repr_str = repr(source)

        assert 'YamlConfigSettingsSource' in repr_str
        assert 'None' in repr_str

    def test_repr_format(self, tmp_path):
        """Test __repr__ output format."""
        yaml_file = tmp_path / 'settings.yaml'
        yaml_file.write_text('key: value')

        source = YamlConfigSettingsSource(
            SimpleSettings,
            yaml_file=str(yaml_file)
        )
        repr_str = repr(source)

        # Check format: ClassName(param=value)
        assert repr_str.startswith('YamlConfigSettingsSource(yaml_file=')
        assert repr_str.endswith(')')


class TestYamlConfigSettingsSourceIntegration:
    """Integration tests for YamlConfigSettingsSource."""

    def test_source_call_returns_dict(self, tmp_path):
        """Test that calling source returns dict of loaded data."""
        yaml_file = tmp_path / 'config.yaml'
        yaml_file.write_text('test_field: from_yaml\nnew_field: extra_value')

        source = YamlConfigSettingsSource(SimpleSettings, yaml_file=str(yaml_file))
        result = source()

        assert isinstance(result, dict)
        assert result['test_field'] == 'from_yaml'
        assert result['new_field'] == 'extra_value'

    def test_source_with_yaml_section_extraction(self, tmp_path):
        """Test source extracts YAML section correctly."""
        yaml_file = tmp_path / 'config.yaml'
        yaml_file.write_text(
            'database:\n'
            '  host: localhost\n'
            '  port: 5432\n'
            'other_section:\n'
            '  key: value'
        )

        class DatabaseSettings(BaseSettings):
            host: str = 'default'
            port: int = 3306
            model_config = {}

        source = YamlConfigSettingsSource(
            DatabaseSettings,
            yaml_file=str(yaml_file),
            yaml_config_section='database'
        )
        result = source()

        assert result['host'] == 'localhost'
        assert result['port'] == 5432
        assert 'other_section' not in str(result)

    def test_source_with_nonexistent_yaml_file(self):
        """Test source handles nonexistent YAML file gracefully."""
        source = YamlConfigSettingsSource(
            SimpleSettings,
            yaml_file='/nonexistent/path/to/config.yaml'
        )

        # Should return empty dict when file doesn't exist
        result = source()
        assert result == {}

    def test_source_multiple_yaml_files(self, tmp_path):
        """Test source with multiple YAML files."""
        yaml_file1 = tmp_path / 'config1.yaml'
        yaml_file1.write_text('field1: value1')

        yaml_file2 = tmp_path / 'config2.yaml'
        yaml_file2.write_text('field2: value2')

        class MultiFileSettings(BaseSettings):
            field1: str = 'default1'
            field2: str = 'default2'
            model_config = {}

        source = YamlConfigSettingsSource(
            MultiFileSettings,
            yaml_file=[str(yaml_file1), str(yaml_file2)]
        )
        result = source()

        assert result['field1'] == 'value1'
        assert result['field2'] == 'value2'

    def test_source_repr_includes_yaml_file_info(self, tmp_path):
        """Test that source repr shows yaml_file info."""
        yaml_file = tmp_path / 'config.yaml'
        yaml_file.write_text('key: value')

        source = YamlConfigSettingsSource(
            SimpleSettings,
            yaml_file=str(yaml_file)
        )

        repr_str = repr(source)
        assert 'YamlConfigSettingsSource' in repr_str
        assert str(yaml_file) in repr_str
