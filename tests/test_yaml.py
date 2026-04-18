"""Tests for pydantic_settings.sources.providers.yaml module."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pydantic_settings.main import BaseSettings


class TestImportYaml:
    """Tests for the import_yaml function."""

    def test_import_yaml_success(self):
        """Test that import_yaml successfully imports yaml when available."""
        from pydantic_settings.sources.providers import yaml as yaml_module

        # Reset yaml to None to test the import
        original_yaml = yaml_module.yaml
        yaml_module.yaml = None

        try:
            yaml_module.import_yaml()
            # After import, yaml should be set
            assert yaml_module.yaml is not None
        finally:
            yaml_module.yaml = original_yaml

    def test_import_yaml_already_imported(self):
        """Test that import_yaml does nothing when yaml is already imported."""
        from pydantic_settings.sources.providers import yaml as yaml_module

        # Ensure yaml is imported first
        yaml_module.import_yaml()
        original_yaml = yaml_module.yaml

        # Call again - should return early
        yaml_module.import_yaml()

        assert yaml_module.yaml is original_yaml

    @pytest.mark.skip(reason="Cannot reliably mock yaml import when already installed")
    def test_import_yaml_not_installed(self):
        """Test that import_yaml raises ImportError when PyYAML is not installed."""
        # This test requires PyYAML to not be installed, which cannot be easily
        # simulated in an environment where it is already installed.
        pass


class TestYamlConfigSettingsSource:
    """Tests for the YamlConfigSettingsSource class."""

    def test_init_with_yaml_file(self, tmp_path):
        """Test __init__ with a yaml file path."""
        yaml_content = 'name: test\nvalue: 42\n'
        yaml_file = tmp_path / 'config.yaml'
        yaml_file.write_text(yaml_content)

        class Settings(BaseSettings):
            name: str = ''
            value: int = 0

        from pydantic_settings.sources.providers.yaml import YamlConfigSettingsSource

        source = YamlConfigSettingsSource(Settings, yaml_file=yaml_file)

        assert source.yaml_file_path == yaml_file
        assert source.yaml_data == {'name': 'test', 'value': 42}

    def test_init_with_default_path(self, tmp_path):
        """Test __init__ uses model_config yaml_file when yaml_file is DEFAULT_PATH."""
        yaml_content = 'name: from_config\n'
        yaml_file = tmp_path / 'default_config.yaml'
        yaml_file.write_text(yaml_content)

        class Settings(BaseSettings):
            name: str = ''

            model_config = {'yaml_file': yaml_file}

        from pydantic_settings.sources.providers.yaml import YamlConfigSettingsSource

        source = YamlConfigSettingsSource(Settings)

        assert source.yaml_file_path == yaml_file
        assert source.yaml_data == {'name': 'from_config'}

    def test_init_with_yaml_file_encoding(self, tmp_path):
        """Test __init__ with yaml_file_encoding parameter."""
        yaml_content = 'name: encoded\n'
        yaml_file = tmp_path / 'encoded.yaml'
        yaml_file.write_text(yaml_content, encoding='utf-8')

        class Settings(BaseSettings):
            name: str = ''

        from pydantic_settings.sources.providers.yaml import YamlConfigSettingsSource

        source = YamlConfigSettingsSource(
            Settings, yaml_file=yaml_file, yaml_file_encoding='utf-8'
        )

        assert source.yaml_file_encoding == 'utf-8'
        assert source.yaml_data == {'name': 'encoded'}

    def test_init_with_yaml_file_encoding_from_config(self, tmp_path):
        """Test __init__ gets yaml_file_encoding from model_config."""
        yaml_content = 'name: test\n'
        yaml_file = tmp_path / 'config.yaml'
        yaml_file.write_text(yaml_content)

        class Settings(BaseSettings):
            name: str = ''

            model_config = {'yaml_file_encoding': 'utf-8'}

        from pydantic_settings.sources.providers.yaml import YamlConfigSettingsSource

        source = YamlConfigSettingsSource(Settings, yaml_file=yaml_file)

        assert source.yaml_file_encoding == 'utf-8'

    def test_init_with_yaml_config_section(self, tmp_path):
        """Test __init__ with yaml_config_section parameter."""
        yaml_content = 'app:\n  name: nested_value\n  value: 100\n'
        yaml_file = tmp_path / 'sectioned.yaml'
        yaml_file.write_text(yaml_content)

        class Settings(BaseSettings):
            name: str = ''
            value: int = 0

        from pydantic_settings.sources.providers.yaml import YamlConfigSettingsSource

        source = YamlConfigSettingsSource(
            Settings, yaml_file=yaml_file, yaml_config_section='app'
        )

        assert source.yaml_config_section == 'app'
        assert source.yaml_data == {'name': 'nested_value', 'value': 100}

    def test_init_with_yaml_config_section_from_config(self, tmp_path):
        """Test __init__ gets yaml_config_section from model_config."""
        yaml_content = 'settings:\n  name: from_section\n'
        yaml_file = tmp_path / 'config.yaml'
        yaml_file.write_text(yaml_content)

        class Settings(BaseSettings):
            name: str = ''

            model_config = {'yaml_config_section': 'settings'}

        from pydantic_settings.sources.providers.yaml import YamlConfigSettingsSource

        source = YamlConfigSettingsSource(Settings, yaml_file=yaml_file)

        assert source.yaml_config_section == 'settings'
        assert source.yaml_data == {'name': 'from_section'}

    def test_init_with_nonexistent_file(self, tmp_path):
        """Test __init__ with a file that doesn't exist."""

        class Settings(BaseSettings):
            name: str = ''

        from pydantic_settings.sources.providers.yaml import YamlConfigSettingsSource

        nonexistent = tmp_path / 'nonexistent.yaml'
        source = YamlConfigSettingsSource(Settings, yaml_file=nonexistent)

        assert source.yaml_data == {}

    def test_init_with_deep_merge(self, tmp_path):
        """Test __init__ with deep_merge parameter."""
        yaml1 = tmp_path / 'config1.yaml'
        yaml2 = tmp_path / 'config2.yaml'
        yaml1.write_text('db:\n  host: localhost\n')
        yaml2.write_text('db:\n  port: 5432\n')

        class Settings(BaseSettings):
            pass

        from pydantic_settings.sources.providers.yaml import YamlConfigSettingsSource

        source = YamlConfigSettingsSource(
            Settings, yaml_file=[yaml1, yaml2], deep_merge=True
        )

        assert source.yaml_data == {'db': {'host': 'localhost', 'port': 5432}}


class TestYamlConfigSettingsSourceReadFile:
    """Tests for the _read_file method."""

    def test_read_file_basic(self, tmp_path):
        """Test _read_file reads yaml content correctly."""
        yaml_content = 'key: value\nnumber: 123\n'
        yaml_file = tmp_path / 'test.yaml'
        yaml_file.write_text(yaml_content)

        class Settings(BaseSettings):
            pass

        from pydantic_settings.sources.providers.yaml import YamlConfigSettingsSource

        source = YamlConfigSettingsSource(Settings, yaml_file=None)
        result = source._read_file(yaml_file)

        assert result == {'key': 'value', 'number': 123}

    def test_read_file_empty(self, tmp_path):
        """Test _read_file returns empty dict for empty file."""
        yaml_file = tmp_path / 'empty.yaml'
        yaml_file.write_text('')

        class Settings(BaseSettings):
            pass

        from pydantic_settings.sources.providers.yaml import YamlConfigSettingsSource

        source = YamlConfigSettingsSource(Settings, yaml_file=None)
        result = source._read_file(yaml_file)

        assert result == {}

    def test_read_file_with_encoding(self, tmp_path):
        """Test _read_file uses the specified encoding."""
        yaml_content = 'name: тест\n'
        yaml_file = tmp_path / 'encoded.yaml'
        yaml_file.write_text(yaml_content, encoding='utf-8')

        class Settings(BaseSettings):
            pass

        from pydantic_settings.sources.providers.yaml import YamlConfigSettingsSource

        source = YamlConfigSettingsSource(
            Settings, yaml_file=None, yaml_file_encoding='utf-8'
        )
        result = source._read_file(yaml_file)

        assert result == {'name': 'тест'}


class TestYamlConfigSettingsSourceTraverseNestedSection:
    """Tests for the _traverse_nested_section method."""

    def test_traverse_simple_key(self, tmp_path):
        """Test traversing with a simple key."""
        yaml_file = tmp_path / 'test.yaml'
        yaml_file.write_text('app:\n  name: test\n')

        class Settings(BaseSettings):
            pass

        from pydantic_settings.sources.providers.yaml import YamlConfigSettingsSource

        source = YamlConfigSettingsSource(Settings, yaml_file=yaml_file)
        data = {'app': {'name': 'test'}}

        result = source._traverse_nested_section(data, 'app')

        assert result == {'name': 'test'}

    def test_traverse_dot_notation(self, tmp_path):
        """Test traversing with dot notation."""
        yaml_file = tmp_path / 'test.yaml'
        yaml_file.write_text('config:\n  app:\n    name: nested\n')

        class Settings(BaseSettings):
            pass

        from pydantic_settings.sources.providers.yaml import YamlConfigSettingsSource

        source = YamlConfigSettingsSource(Settings, yaml_file=yaml_file)
        data = {'config': {'app': {'name': 'nested'}}}

        result = source._traverse_nested_section(data, 'config.app')

        assert result == {'name': 'nested'}

    def test_traverse_literal_dotted_key(self, tmp_path):
        """Test traversing with a literal dotted key."""
        yaml_file = tmp_path / 'test.yaml'
        yaml_file.write_text('')

        class Settings(BaseSettings):
            pass

        from pydantic_settings.sources.providers.yaml import YamlConfigSettingsSource

        source = YamlConfigSettingsSource(Settings, yaml_file=yaml_file)
        data = {'a.b.c': {'name': 'literal'}}

        result = source._traverse_nested_section(data, 'a.b.c')

        assert result == {'name': 'literal'}

    def test_traverse_mixed_literal_and_nested(self, tmp_path):
        """Test traversing with mixed literal and nested keys."""
        yaml_file = tmp_path / 'test.yaml'
        yaml_file.write_text('')

        class Settings(BaseSettings):
            pass

        from pydantic_settings.sources.providers.yaml import YamlConfigSettingsSource

        source = YamlConfigSettingsSource(Settings, yaml_file=yaml_file)
        data = {'a.b': {'c': {'name': 'mixed'}}}

        result = source._traverse_nested_section(data, 'a.b.c')

        assert result == {'name': 'mixed'}

    def test_traverse_empty_path_raises_error(self, tmp_path):
        """Test that empty path raises ValueError."""
        yaml_file = tmp_path / 'test.yaml'
        yaml_file.write_text('')

        class Settings(BaseSettings):
            pass

        from pydantic_settings.sources.providers.yaml import YamlConfigSettingsSource

        source = YamlConfigSettingsSource(Settings, yaml_file=yaml_file)
        data = {'app': {'name': 'test'}}

        with pytest.raises(ValueError) as exc_info:
            source._traverse_nested_section(data, '')

        assert 'yaml_config_section cannot be empty' in str(exc_info.value)

    def test_traverse_key_not_found_raises_error(self, tmp_path):
        """Test that missing key raises KeyError."""
        yaml_file = tmp_path / 'test.yaml'
        yaml_file.write_text('')

        class Settings(BaseSettings):
            pass

        from pydantic_settings.sources.providers.yaml import YamlConfigSettingsSource

        source = YamlConfigSettingsSource(Settings, yaml_file=yaml_file)
        data = {'app': {'name': 'test'}}

        with pytest.raises(KeyError) as exc_info:
            source._traverse_nested_section(data, 'missing')

        assert 'not found' in str(exc_info.value)

    def test_traverse_nested_key_not_found_raises_error(self, tmp_path):
        """Test that missing nested key raises KeyError."""
        yaml_file = tmp_path / 'test.yaml'
        yaml_file.write_text('')

        class Settings(BaseSettings):
            pass

        from pydantic_settings.sources.providers.yaml import YamlConfigSettingsSource

        source = YamlConfigSettingsSource(Settings, yaml_file=yaml_file)
        data = {'app': {'name': 'test'}}

        with pytest.raises(KeyError) as exc_info:
            source._traverse_nested_section(data, 'app.missing')

        assert 'not found' in str(exc_info.value)

    def test_traverse_non_dict_intermediate_raises_error(self, tmp_path):
        """Test that non-dict intermediate value raises TypeError."""
        yaml_file = tmp_path / 'test.yaml'
        yaml_file.write_text('')

        class Settings(BaseSettings):
            pass

        from pydantic_settings.sources.providers.yaml import YamlConfigSettingsSource

        source = YamlConfigSettingsSource(Settings, yaml_file=yaml_file)
        data = {'app': 'not_a_dict'}

        with pytest.raises(TypeError) as exc_info:
            source._traverse_nested_section(data, 'app.sub')

        assert 'cannot be traversed' in str(exc_info.value)

    def test_traverse_deeply_nested_path(self, tmp_path):
        """Test traversing a deeply nested path."""
        yaml_file = tmp_path / 'test.yaml'
        yaml_file.write_text('')

        class Settings(BaseSettings):
            pass

        from pydantic_settings.sources.providers.yaml import YamlConfigSettingsSource

        source = YamlConfigSettingsSource(Settings, yaml_file=yaml_file)
        data = {'a': {'b': {'c': {'d': {'name': 'deep'}}}}}

        result = source._traverse_nested_section(data, 'a.b.c.d')

        assert result == {'name': 'deep'}


class TestYamlConfigSettingsSourceRepr:
    """Tests for the __repr__ method."""

    def test_repr_with_file_path(self, tmp_path):
        """Test __repr__ returns correct format with file path."""
        yaml_file = tmp_path / 'config.yaml'
        yaml_file.write_text('name: test\n')

        class Settings(BaseSettings):
            name: str = ''

        from pydantic_settings.sources.providers.yaml import YamlConfigSettingsSource

        source = YamlConfigSettingsSource(Settings, yaml_file=yaml_file)
        result = repr(source)

        assert result == f'YamlConfigSettingsSource(yaml_file={yaml_file})'

    def test_repr_with_none_path(self, tmp_path):
        """Test __repr__ with None yaml_file_path."""

        class Settings(BaseSettings):
            name: str = ''

        from pydantic_settings.sources.providers.yaml import YamlConfigSettingsSource

        source = YamlConfigSettingsSource(Settings, yaml_file=None)
        result = repr(source)

        assert result == 'YamlConfigSettingsSource(yaml_file=None)'
