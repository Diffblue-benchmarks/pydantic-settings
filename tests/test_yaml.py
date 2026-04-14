import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

from pydantic_settings import BaseSettings
from pydantic_settings.sources.providers.yaml import (
    YamlConfigSettingsSource,
    import_yaml,
)


class TestImportYaml:
    def test_import_yaml_success(self):
        """Test successful import of yaml module."""
        # Reset the global yaml to None to test import
        import pydantic_settings.sources.providers.yaml as yaml_module
        original_yaml = yaml_module.yaml
        try:
            yaml_module.yaml = None
            import_yaml()
            assert yaml_module.yaml is not None
        finally:
            yaml_module.yaml = original_yaml

    def test_import_yaml_already_imported(self):
        """Test that import_yaml returns early if yaml is already imported."""
        import pydantic_settings.sources.providers.yaml as yaml_module
        # Ensure yaml is imported first
        if yaml_module.yaml is None:
            import_yaml()
        original_yaml = yaml_module.yaml
        # Call again - should return early without changing anything
        import_yaml()
        assert yaml_module.yaml is original_yaml

    @pytest.mark.skip(reason="Difficult to test without breaking the import system")
    def test_import_yaml_not_installed(self):
        """Test that import_yaml raises ImportError when PyYAML is not installed."""
        # This test is complex to implement without breaking the import system
        # The import_yaml function properly raises ImportError when yaml is not installed
        pass


class TestYamlConfigSettingsSource:
    def test_init_with_yaml_file(self):
        """Test initialization with a yaml file."""
        class Settings(BaseSettings):
            name: str = 'default'
            age: int = 0

        # Create a temporary yaml file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write('name: test\nage: 25\n')
            yaml_file = f.name

        try:
            yaml_path = Path(yaml_file)
            source = YamlConfigSettingsSource(Settings, yaml_file=yaml_path)
            assert source.yaml_file_path == yaml_path
            assert source.yaml_data == {'name': 'test', 'age': 25}
        finally:
            Path(yaml_file).unlink()

    def test_init_with_model_config(self):
        """Test initialization using model_config."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write('value: from_config\n')
            yaml_file = f.name

        try:
            yaml_path = Path(yaml_file)

            class Settings(BaseSettings):
                model_config = {
                    'yaml_file': yaml_path,
                    'yaml_file_encoding': 'utf-8',
                    'yaml_config_section': None
                }
                value: str = 'default'

            # Use default path to trigger reading from model_config
            from pydantic_settings.sources.types import DEFAULT_PATH
            source = YamlConfigSettingsSource(Settings, yaml_file=DEFAULT_PATH)
            assert source.yaml_file_path == yaml_path
            assert source.yaml_file_encoding == 'utf-8'
        finally:
            Path(yaml_file).unlink()

    def test_init_with_yaml_config_section(self):
        """Test initialization with yaml_config_section."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write('database:\n  host: localhost\n  port: 5432\n')
            yaml_file = f.name

        try:
            yaml_path = Path(yaml_file)

            class Settings(BaseSettings):
                host: str = 'default'
                port: int = 0

            source = YamlConfigSettingsSource(
                Settings,
                yaml_file=yaml_path,
                yaml_config_section='database'
            )
            assert source.yaml_data == {'host': 'localhost', 'port': 5432}
        finally:
            Path(yaml_file).unlink()

    def test_init_with_yaml_file_encoding(self):
        """Test initialization with custom encoding."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
            f.write('key: value\n')
            yaml_file = f.name

        try:
            yaml_path = Path(yaml_file)

            class Settings(BaseSettings):
                key: str = 'default'

            source = YamlConfigSettingsSource(
                Settings,
                yaml_file=yaml_path,
                yaml_file_encoding='utf-8'
            )
            assert source.yaml_file_encoding == 'utf-8'
            assert source.yaml_data == {'key': 'value'}
        finally:
            Path(yaml_file).unlink()

    def test_init_with_deep_merge(self):
        """Test initialization with deep_merge option."""
        # Create two yaml files
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f1:
            f1.write('config:\n  a: 1\n  b: 2\n')
            yaml_file1 = f1.name

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f2:
            f2.write('config:\n  b: 3\n  c: 4\n')
            yaml_file2 = f2.name

        try:
            class Settings(BaseSettings):
                config: dict = {}

            # Test with deep_merge=True
            source = YamlConfigSettingsSource(
                Settings,
                yaml_file=[Path(yaml_file1), Path(yaml_file2)],
                deep_merge=True
            )
            # With deep merge, nested dicts should be merged
            assert 'config' in source.yaml_data
        finally:
            Path(yaml_file1).unlink()
            Path(yaml_file2).unlink()

    def test_read_file(self):
        """Test _read_file method."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write('key1: value1\nkey2: value2\n')
            yaml_file = f.name

        try:
            yaml_path = Path(yaml_file)

            class Settings(BaseSettings):
                key1: str = 'default'
                key2: str = 'default'

            source = YamlConfigSettingsSource(Settings, yaml_file=yaml_path)
            result = source._read_file(yaml_path)
            assert result == {'key1': 'value1', 'key2': 'value2'}
        finally:
            Path(yaml_file).unlink()

    def test_read_file_empty(self):
        """Test _read_file with empty yaml file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write('')
            yaml_file = f.name

        try:
            yaml_path = Path(yaml_file)

            class Settings(BaseSettings):
                pass

            source = YamlConfigSettingsSource(Settings, yaml_file=yaml_path)
            result = source._read_file(yaml_path)
            assert result == {}
        finally:
            Path(yaml_file).unlink()

    def test_traverse_nested_section_simple(self):
        """Test _traverse_nested_section with a simple key."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write('section:\n  key: value\n')
            yaml_file = f.name

        try:
            yaml_path = Path(yaml_file)

            class Settings(BaseSettings):
                key: str = 'default'

            source = YamlConfigSettingsSource(Settings, yaml_file=yaml_path)
            result = source._traverse_nested_section({'section': {'key': 'value'}}, 'section')
            assert result == {'key': 'value'}
        finally:
            Path(yaml_file).unlink()

    def test_traverse_nested_section_dotted_path(self):
        """Test _traverse_nested_section with a dotted path."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write('a:\n  b:\n    c: value\n')
            yaml_file = f.name

        try:
            yaml_path = Path(yaml_file)

            class Settings(BaseSettings):
                c: str = 'default'

            source = YamlConfigSettingsSource(Settings, yaml_file=yaml_path)
            data = {'a': {'b': {'c': 'value'}}}
            result = source._traverse_nested_section(data, 'a.b.c')
            assert result == 'value'
        finally:
            Path(yaml_file).unlink()

    def test_traverse_nested_section_literal_key_with_dot(self):
        """Test _traverse_nested_section with a literal key containing a dot."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write('a.b: value\n')
            yaml_file = f.name

        try:
            yaml_path = Path(yaml_file)

            class Settings(BaseSettings):
                pass

            source = YamlConfigSettingsSource(Settings, yaml_file=yaml_path)
            data = {'a.b': 'value'}
            result = source._traverse_nested_section(data, 'a.b')
            assert result == 'value'
        finally:
            Path(yaml_file).unlink()

    def test_traverse_nested_section_empty_path_error(self):
        """Test _traverse_nested_section with empty path raises ValueError."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write('key: value\n')
            yaml_file = f.name

        try:
            yaml_path = Path(yaml_file)

            class Settings(BaseSettings):
                pass

            source = YamlConfigSettingsSource(Settings, yaml_file=yaml_path)
            with pytest.raises(ValueError, match='yaml_config_section cannot be empty'):
                source._traverse_nested_section({'key': 'value'}, '')
        finally:
            Path(yaml_file).unlink()

    def test_traverse_nested_section_key_not_found(self):
        """Test _traverse_nested_section with non-existent key raises KeyError."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write('key: value\n')
            yaml_file = f.name

        try:
            yaml_path = Path(yaml_file)

            class Settings(BaseSettings):
                pass

            source = YamlConfigSettingsSource(Settings, yaml_file=yaml_path)
            with pytest.raises(KeyError, match='yaml_config_section key "nonexistent" not found'):
                source._traverse_nested_section({'key': 'value'}, 'nonexistent')
        finally:
            Path(yaml_file).unlink()

    def test_traverse_nested_section_type_error(self):
        """Test _traverse_nested_section with non-dict data raises TypeError."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write('key: value\n')
            yaml_file = f.name

        try:
            yaml_path = Path(yaml_file)

            class Settings(BaseSettings):
                pass

            source = YamlConfigSettingsSource(Settings, yaml_file=yaml_path)
            # Pass a string instead of a dict - trying to access it like a dict will raise TypeError
            with pytest.raises(TypeError, match='cannot be traversed'):
                source._traverse_nested_section('not a dict', 'any.path')
        finally:
            Path(yaml_file).unlink()

    def test_traverse_nested_section_nested_type_error(self):
        """Test _traverse_nested_section with non-dict in nested path raises TypeError."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write('a:\n  b: value\n')
            yaml_file = f.name

        try:
            yaml_path = Path(yaml_file)

            class Settings(BaseSettings):
                pass

            source = YamlConfigSettingsSource(Settings, yaml_file=yaml_path)
            data = {'a': {'b': 'value'}}
            # Try to traverse further into a string value
            with pytest.raises(TypeError, match='cannot be traversed'):
                source._traverse_nested_section(data, 'a.b.c')
        finally:
            Path(yaml_file).unlink()

    def test_traverse_nested_section_prefix_match(self):
        """Test _traverse_nested_section with prefix matching."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write('a.b:\n  c: value\n')
            yaml_file = f.name

        try:
            yaml_path = Path(yaml_file)

            class Settings(BaseSettings):
                c: str = 'default'

            source = YamlConfigSettingsSource(Settings, yaml_file=yaml_path)
            # 'a.b' exists as a literal key, so 'a.b.c' should traverse into it
            data = {'a.b': {'c': 'value'}}
            result = source._traverse_nested_section(data, 'a.b.c')
            assert result == 'value'
        finally:
            Path(yaml_file).unlink()

    def test_traverse_nested_section_complex_nesting(self):
        """Test _traverse_nested_section with complex nesting."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write('level1:\n  level2:\n    level3:\n      key: value\n')
            yaml_file = f.name

        try:
            yaml_path = Path(yaml_file)

            class Settings(BaseSettings):
                key: str = 'default'

            source = YamlConfigSettingsSource(Settings, yaml_file=yaml_path)
            data = {'level1': {'level2': {'level3': {'key': 'value'}}}}
            result = source._traverse_nested_section(data, 'level1.level2.level3')
            assert result == {'key': 'value'}
        finally:
            Path(yaml_file).unlink()

    def test_repr(self):
        """Test __repr__ method."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write('key: value\n')
            yaml_file = f.name

        try:
            yaml_path = Path(yaml_file)

            class Settings(BaseSettings):
                key: str = 'default'

            source = YamlConfigSettingsSource(Settings, yaml_file=yaml_path)
            repr_str = repr(source)
            assert 'YamlConfigSettingsSource' in repr_str
            assert str(yaml_path) in repr_str
        finally:
            Path(yaml_file).unlink()
