import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from pydantic import BaseModel
from pydantic_settings import BaseSettings
from pydantic_settings.sources.providers.yaml import (
    YamlConfigSettingsSource,
    import_yaml,
)


class TestImportYaml:
    """Tests for import_yaml function."""

    def test_import_yaml_success(self):
        """Test that yaml is imported successfully."""
        # Reset the global yaml variable
        import pydantic_settings.sources.providers.yaml as yaml_module
        original_yaml = yaml_module.yaml
        yaml_module.yaml = None

        try:
            import_yaml()
            assert yaml_module.yaml is not None
        finally:
            yaml_module.yaml = original_yaml

    def test_import_yaml_already_imported(self):
        """Test that import_yaml returns early if yaml is already imported."""
        import pydantic_settings.sources.providers.yaml as yaml_module

        # Ensure yaml is already imported
        import_yaml()
        original_yaml = yaml_module.yaml

        # Should not attempt to import again
        import_yaml()
        assert yaml_module.yaml is original_yaml

    def test_import_yaml_missing_dependency(self):
        """Test that import_yaml raises ImportError when PyYAML is not available."""
        import pydantic_settings.sources.providers.yaml as yaml_module
        original_yaml = yaml_module.yaml
        yaml_module.yaml = None

        try:
            with patch.dict('sys.modules', {'yaml': None}):
                with pytest.raises(ImportError, match='PyYAML is not installed'):
                    import_yaml()
        finally:
            yaml_module.yaml = original_yaml


class TestYamlConfigSettingsSourceInit:
    """Tests for YamlConfigSettingsSource.__init__."""

    def test_init_with_yaml_file(self):
        """Test initialization with a yaml file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp_file:
            tmp_file.write("key: value\n")
            tmp_file.flush()
            tmp_path = Path(tmp_file.name)

        try:
            class Settings(BaseSettings):
                key: str = 'default'

            source = YamlConfigSettingsSource(Settings, yaml_file=tmp_path)
            assert source.yaml_file_path == tmp_path
            assert source.yaml_data == {'key': 'value'}
        finally:
            tmp_path.unlink()

    def test_init_with_default_path(self):
        """Test initialization with DEFAULT_PATH."""
        from pydantic_settings.sources.types import DEFAULT_PATH

        class Settings(BaseSettings):
            key: str = 'default'
            model_config = {'yaml_file': None}

        source = YamlConfigSettingsSource(Settings, yaml_file=DEFAULT_PATH)
        assert source.yaml_file_path is None

    def test_init_with_yaml_file_encoding(self):
        """Test initialization with yaml_file_encoding."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as tmp_file:
            tmp_file.write("key: value\n")
            tmp_file.flush()
            tmp_path = Path(tmp_file.name)

        try:
            class Settings(BaseSettings):
                key: str = 'default'

            source = YamlConfigSettingsSource(Settings, yaml_file=tmp_path, yaml_file_encoding='utf-8')
            assert source.yaml_file_encoding == 'utf-8'
        finally:
            tmp_path.unlink()

    def test_init_with_yaml_config_section(self):
        """Test initialization with yaml_config_section."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp_file:
            tmp_file.write("section:\n  key: value\n")
            tmp_file.flush()
            tmp_path = Path(tmp_file.name)

        try:
            class Settings(BaseSettings):
                key: str = 'default'

            source = YamlConfigSettingsSource(Settings, yaml_file=tmp_path, yaml_config_section='section')
            assert source.yaml_config_section == 'section'
            assert source.yaml_data == {'key': 'value'}
        finally:
            tmp_path.unlink()

    def test_init_with_model_config_yaml_file(self):
        """Test initialization with yaml_file from model_config."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp_file:
            tmp_file.write("key: value\n")
            tmp_file.flush()
            tmp_path = Path(tmp_file.name)

        try:
            from pydantic_settings.sources.types import DEFAULT_PATH

            class Settings(BaseSettings):
                key: str = 'default'
                model_config = {'yaml_file': tmp_path}

            source = YamlConfigSettingsSource(Settings, yaml_file=DEFAULT_PATH)
            assert source.yaml_file_path == tmp_path
        finally:
            tmp_path.unlink()

    def test_init_with_deep_merge(self):
        """Test initialization with deep_merge=True."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp_file:
            tmp_file.write("key: value\n")
            tmp_file.flush()
            tmp_path = Path(tmp_file.name)

        try:
            class Settings(BaseSettings):
                key: str = 'default'

            source = YamlConfigSettingsSource(Settings, yaml_file=tmp_path, deep_merge=True)
            assert source.yaml_data == {'key': 'value'}
        finally:
            tmp_path.unlink()


class TestYamlConfigSettingsSourceReadFile:
    """Tests for YamlConfigSettingsSource._read_file."""

    def test_read_file_simple_yaml(self):
        """Test reading a simple YAML file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp_file:
            tmp_file.write("key: value\n")
            tmp_file.flush()
            tmp_path = Path(tmp_file.name)

        try:
            class Settings(BaseSettings):
                key: str = 'default'

            source = YamlConfigSettingsSource(Settings, yaml_file=tmp_path)
            result = source._read_file(tmp_path)
            assert result == {'key': 'value'}
        finally:
            tmp_path.unlink()

    def test_read_file_empty_yaml(self):
        """Test reading an empty YAML file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp_file:
            tmp_file.write("")
            tmp_file.flush()
            tmp_path = Path(tmp_file.name)

        try:
            class Settings(BaseSettings):
                key: str = 'default'

            source = YamlConfigSettingsSource(Settings, yaml_file=tmp_path)
            result = source._read_file(tmp_path)
            assert result == {}
        finally:
            tmp_path.unlink()


class TestYamlConfigSettingsSourceTraverseNestedSection:
    """Tests for YamlConfigSettingsSource._traverse_nested_section."""

    def test_traverse_nested_section_simple(self):
        """Test traversing a simple nested section."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp_file:
            tmp_file.write("section:\n  key: value\n")
            tmp_file.flush()
            tmp_path = Path(tmp_file.name)

        try:
            class Settings(BaseSettings):
                key: str = 'default'

            source = YamlConfigSettingsSource(Settings, yaml_file=tmp_path)
            result = source._traverse_nested_section({'section': {'key': 'value'}}, 'section')
            assert result == {'key': 'value'}
        finally:
            tmp_path.unlink()

    def test_traverse_nested_section_dot_notation(self):
        """Test traversing nested sections with dot notation."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp_file:
            tmp_file.write("key: value\n")
            tmp_file.flush()
            tmp_path = Path(tmp_file.name)

        try:
            class Settings(BaseSettings):
                key: str = 'default'

            source = YamlConfigSettingsSource(Settings, yaml_file=tmp_path)
            data = {'a': {'b': {'c': 'value'}}}
            result = source._traverse_nested_section(data, 'a.b.c')
            assert result == 'value'
        finally:
            tmp_path.unlink()

    def test_traverse_nested_section_literal_key_with_dot(self):
        """Test traversing when key literally contains a dot."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp_file:
            tmp_file.write("key: value\n")
            tmp_file.flush()
            tmp_path = Path(tmp_file.name)

        try:
            class Settings(BaseSettings):
                key: str = 'default'

            source = YamlConfigSettingsSource(Settings, yaml_file=tmp_path)
            data = {'a.b.c': 'value'}
            result = source._traverse_nested_section(data, 'a.b.c')
            assert result == 'value'
        finally:
            tmp_path.unlink()

    def test_traverse_nested_section_greedy_prefix_match(self):
        """Test greedy prefix matching for keys with dots."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp_file:
            tmp_file.write("key: value\n")
            tmp_file.flush()
            tmp_path = Path(tmp_file.name)

        try:
            class Settings(BaseSettings):
                key: str = 'default'

            source = YamlConfigSettingsSource(Settings, yaml_file=tmp_path)
            data = {'a.b': {'c': 'value'}}
            result = source._traverse_nested_section(data, 'a.b.c')
            assert result == 'value'
        finally:
            tmp_path.unlink()

    def test_traverse_nested_section_empty_path_error(self):
        """Test that empty path raises ValueError."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp_file:
            tmp_file.write("key: value\n")
            tmp_file.flush()
            tmp_path = Path(tmp_file.name)

        try:
            class Settings(BaseSettings):
                key: str = 'default'

            source = YamlConfigSettingsSource(Settings, yaml_file=tmp_path)
            with pytest.raises(ValueError, match='yaml_config_section cannot be empty'):
                source._traverse_nested_section({'key': 'value'}, '')
        finally:
            tmp_path.unlink()

    def test_traverse_nested_section_key_not_found(self):
        """Test that missing key raises KeyError."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp_file:
            tmp_file.write("key: value\n")
            tmp_file.flush()
            tmp_path = Path(tmp_file.name)

        try:
            class Settings(BaseSettings):
                key: str = 'default'

            source = YamlConfigSettingsSource(Settings, yaml_file=tmp_path)
            with pytest.raises(KeyError, match='yaml_config_section key "missing" not found'):
                source._traverse_nested_section({'key': 'value'}, 'missing')
        finally:
            tmp_path.unlink()

    def test_traverse_nested_section_type_error_on_non_dict(self):
        """Test that TypeError is raised when traversing non-dict value."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp_file:
            tmp_file.write("key: value\n")
            tmp_file.flush()
            tmp_path = Path(tmp_file.name)

        try:
            class Settings(BaseSettings):
                key: str = 'default'

            source = YamlConfigSettingsSource(Settings, yaml_file=tmp_path)
            # Try to traverse 'a.b' when 'a' is a string, not a dict
            data = {'a': 'string_value'}
            with pytest.raises(TypeError, match='cannot be traversed'):
                source._traverse_nested_section(data, 'a.b')
        finally:
            tmp_path.unlink()

    def test_traverse_nested_section_type_error_on_intermediate_non_dict(self):
        """Test TypeError when intermediate value is not a dictionary."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp_file:
            tmp_file.write("key: value\n")
            tmp_file.flush()
            tmp_path = Path(tmp_file.name)

        try:
            class Settings(BaseSettings):
                key: str = 'default'

            source = YamlConfigSettingsSource(Settings, yaml_file=tmp_path)
            # 'a.b' exists as literal key but maps to string, trying to traverse further
            data = {'a.b': 'value'}
            with pytest.raises(TypeError, match='cannot be traversed'):
                source._traverse_nested_section(data, 'a.b.c')
        finally:
            tmp_path.unlink()

    def test_traverse_nested_section_no_dot_key_not_found(self):
        """Test KeyError when key without dot is not found."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp_file:
            tmp_file.write("key: value\n")
            tmp_file.flush()
            tmp_path = Path(tmp_file.name)

        try:
            class Settings(BaseSettings):
                key: str = 'default'

            source = YamlConfigSettingsSource(Settings, yaml_file=tmp_path)
            with pytest.raises(KeyError, match='yaml_config_section key "missing" not found'):
                source._traverse_nested_section({'key': 'value'}, 'missing')
        finally:
            tmp_path.unlink()

    def test_traverse_nested_section_preserves_original_path_in_error(self):
        """Test that original path is preserved in error messages."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp_file:
            tmp_file.write("key: value\n")
            tmp_file.flush()
            tmp_path = Path(tmp_file.name)

        try:
            class Settings(BaseSettings):
                key: str = 'default'

            source = YamlConfigSettingsSource(Settings, yaml_file=tmp_path)
            data = {'a': {'b': {'c': 'value'}}}
            with pytest.raises(KeyError, match='yaml_config_section key "a.b.missing" not found'):
                source._traverse_nested_section(data, 'a.b.missing')
        finally:
            tmp_path.unlink()


class TestYamlConfigSettingsSourceRepr:
    """Tests for YamlConfigSettingsSource.__repr__."""

    def test_repr(self):
        """Test string representation of YamlConfigSettingsSource."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp_file:
            tmp_file.write("key: value\n")
            tmp_file.flush()
            tmp_path = Path(tmp_file.name)

        try:
            class Settings(BaseSettings):
                key: str = 'default'

            source = YamlConfigSettingsSource(Settings, yaml_file=tmp_path)
            repr_str = repr(source)
            assert 'YamlConfigSettingsSource' in repr_str
            assert str(tmp_path) in repr_str
        finally:
            tmp_path.unlink()
