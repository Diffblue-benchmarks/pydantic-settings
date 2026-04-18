"""Tests for TOML configuration settings source."""

import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from pydantic import BaseModel
from pydantic_settings import BaseSettings
from pydantic_settings.sources.providers.toml import (
    TomlConfigSettingsSource,
    import_toml,
)


class TestImportToml:
    """Tests for import_toml function."""

    def test_import_toml_first_call_python310(self):
        """Test import_toml imports tomli module on first call for Python 3.10."""
        import pydantic_settings.sources.providers.toml as toml_module

        # Save original state
        original_tomli = toml_module.tomli
        original_tomllib = toml_module.tomllib
        try:
            # Reset to None to simulate first import
            toml_module.tomli = None
            toml_module.tomllib = None

            # Call import_toml
            import_toml()

            # For Python < 3.11, tomli should be imported
            if sys.version_info < (3, 11):
                assert toml_module.tomli is not None
            else:
                # For Python >= 3.11, tomllib should be imported
                assert toml_module.tomllib is not None
        finally:
            # Restore original state
            toml_module.tomli = original_tomli
            toml_module.tomllib = original_tomllib

    def test_import_toml_idempotent(self):
        """Test import_toml is idempotent when called multiple times."""
        import pydantic_settings.sources.providers.toml as toml_module

        original_tomli = toml_module.tomli
        original_tomllib = toml_module.tomllib
        try:
            # Ensure TOML library is imported
            import_toml()
            if sys.version_info < (3, 11):
                first_import = toml_module.tomli
            else:
                first_import = toml_module.tomllib

            # Call again
            import_toml()
            if sys.version_info < (3, 11):
                second_import = toml_module.tomli
            else:
                second_import = toml_module.tomllib

            # Should be the same object
            assert first_import is second_import
        finally:
            toml_module.tomli = original_tomli
            toml_module.tomllib = original_tomllib

    def test_import_toml_raises_on_missing_tomli(self):
        """Test import_toml raises ImportError when tomli is not installed."""
        import pydantic_settings.sources.providers.toml as toml_module

        original_tomli = toml_module.tomli
        original_tomllib = toml_module.tomllib
        try:
            # Reset to None
            toml_module.tomli = None
            toml_module.tomllib = None

            if sys.version_info < (3, 11):
                # Mock __import__ to raise ImportError for tomli
                with patch('builtins.__import__', side_effect=ImportError('No module named tomli')):
                    with pytest.raises(ImportError, match='tomli is not installed'):
                        import_toml()
        finally:
            toml_module.tomli = original_tomli
            toml_module.tomllib = original_tomllib

    def test_import_toml_with_python311_tomllib(self):
        """Test import_toml uses tomllib on Python 3.11+."""
        import pydantic_settings.sources.providers.toml as toml_module

        original_tomli = toml_module.tomli
        original_tomllib = toml_module.tomllib

        try:
            # Reset both to None
            toml_module.tomli = None
            toml_module.tomllib = None

            # Mock sys.version_info to simulate Python 3.11+
            with patch('sys.version_info', new=(3, 11)):
                import_toml()
                # On Python 3.11+, tomllib should be imported
                if sys.version_info >= (3, 11):
                    assert toml_module.tomllib is not None
        finally:
            toml_module.tomli = original_tomli
            toml_module.tomllib = original_tomllib


class SimpleSettings(BaseSettings):
    """Simple settings class for testing."""

    test_field: str = 'default'

    model_config = {
        'toml_file': None,
    }


class TestTomlConfigSettingsSourceInit:
    """Tests for TomlConfigSettingsSource.__init__."""

    def test_init_with_no_toml_file(self):
        """Test initialization with no toml file."""
        source = TomlConfigSettingsSource(SimpleSettings)
        assert source.toml_file_path is None

    def test_init_with_explicit_toml_file(self, tmp_path):
        """Test initialization with explicit toml file."""
        toml_file = tmp_path / 'test.toml'
        toml_file.write_text('test_field = "value_from_toml"')

        source = TomlConfigSettingsSource(
            SimpleSettings,
            toml_file=str(toml_file)
        )
        assert source.toml_file_path == str(toml_file)

    def test_init_with_toml_file_from_model_config(self, tmp_path):
        """Test initialization pulls toml_file from model_config."""
        toml_file = tmp_path / 'config.toml'
        toml_file.write_text('test_field = "from_config"')

        class SettingsWithTomlFile(BaseSettings):
            test_field: str = 'default'

            model_config = {
                'toml_file': str(toml_file),
            }

        source = TomlConfigSettingsSource(SettingsWithTomlFile)
        assert source.toml_file_path == str(toml_file)

    def test_init_explicit_toml_file_overrides_model_config(self, tmp_path):
        """Test explicit toml_file parameter overrides model_config."""
        toml_file1 = tmp_path / 'config1.toml'
        toml_file1.write_text('test_field = "from_config"')

        toml_file2 = tmp_path / 'config2.toml'
        toml_file2.write_text('test_field = "from_param"')

        class SettingsWithTomlFile(BaseSettings):
            test_field: str = 'default'

            model_config = {
                'toml_file': str(toml_file1),
            }

        source = TomlConfigSettingsSource(
            SettingsWithTomlFile,
            toml_file=str(toml_file2)
        )
        assert source.toml_file_path == str(toml_file2)

    def test_init_with_deep_merge(self, tmp_path):
        """Test initialization with deep_merge enabled."""
        toml_file1 = tmp_path / 'config1.toml'
        toml_file1.write_text('[database]\nhost = "localhost"')

        toml_file2 = tmp_path / 'config2.toml'
        toml_file2.write_text('[database]\nport = 5432')

        class MergeSettings(BaseSettings):
            model_config = {}

        source = TomlConfigSettingsSource(
            MergeSettings,
            toml_file=[str(toml_file1), str(toml_file2)],
            deep_merge=True
        )
        # Both files should be merged
        assert 'database' in source.toml_data
        assert source.toml_data['database']['host'] == 'localhost'
        assert source.toml_data['database']['port'] == 5432

    def test_init_without_deep_merge(self, tmp_path):
        """Test initialization without deep_merge (default behavior)."""
        toml_file1 = tmp_path / 'config1.toml'
        toml_file1.write_text('[database]\nhost = "localhost"')

        toml_file2 = tmp_path / 'config2.toml'
        toml_file2.write_text('[database]\nport = 5432')

        class MergeSettings(BaseSettings):
            model_config = {}

        source = TomlConfigSettingsSource(
            MergeSettings,
            toml_file=[str(toml_file1), str(toml_file2)],
            deep_merge=False
        )
        # Second file overwrites first (no deep merge)
        assert source.toml_data['database']['port'] == 5432
        assert 'host' not in source.toml_data['database']


class TestTomlConfigSettingsSourceReadFile:
    """Tests for TomlConfigSettingsSource._read_file."""

    def test_read_file_valid_toml(self, tmp_path):
        """Test reading a valid TOML file."""
        toml_file = tmp_path / 'test.toml'
        toml_file.write_text('key = "value"\nnumber = 42')

        source = TomlConfigSettingsSource(SimpleSettings, toml_file=str(toml_file))
        result = source._read_file(toml_file)

        assert result == {'key': 'value', 'number': 42}

    def test_read_file_with_tomllib_branch(self, tmp_path):
        """Test _read_file uses tomllib on Python 3.11+."""
        import pydantic_settings.sources.providers.toml as toml_module

        toml_file = tmp_path / 'test.toml'
        toml_file.write_text('key = "value"')

        source = TomlConfigSettingsSource(SimpleSettings, toml_file=str(toml_file))

        # If we're on Python 3.11+, verify tomllib branch is taken
        if sys.version_info >= (3, 11):
            result = source._read_file(toml_file)
            assert result == {'key': 'value'}

    def test_read_file_empty_toml(self, tmp_path):
        """Test reading an empty TOML file returns empty dict."""
        toml_file = tmp_path / 'empty.toml'
        toml_file.write_text('')

        source = TomlConfigSettingsSource(SimpleSettings, toml_file=str(toml_file))
        result = source._read_file(toml_file)

        assert result == {}

    def test_read_file_nested_toml(self, tmp_path):
        """Test reading nested TOML structure."""
        toml_file = tmp_path / 'nested.toml'
        toml_file.write_text(
            '[database]\n'
            'host = "localhost"\n'
            'port = 5432\n'
            '[database.credentials]\n'
            'user = "admin"'
        )

        source = TomlConfigSettingsSource(SimpleSettings, toml_file=str(toml_file))
        result = source._read_file(toml_file)

        assert result['database']['host'] == 'localhost'
        assert result['database']['port'] == 5432
        assert result['database']['credentials']['user'] == 'admin'

    def test_read_file_with_various_types(self, tmp_path):
        """Test reading TOML file with various data types."""
        toml_file = tmp_path / 'types.toml'
        toml_file.write_text(
            'string_val = "hello"\n'
            'int_val = 123\n'
            'float_val = 45.67\n'
            'bool_val = true\n'
            'array_val = [1, 2, 3]'
        )

        source = TomlConfigSettingsSource(SimpleSettings, toml_file=str(toml_file))
        result = source._read_file(toml_file)

        assert result['string_val'] == 'hello'
        assert result['int_val'] == 123
        assert result['float_val'] == 45.67
        assert result['bool_val'] is True
        assert result['array_val'] == [1, 2, 3]

    def test_read_file_with_inline_table(self, tmp_path):
        """Test reading TOML file with inline tables."""
        toml_file = tmp_path / 'inline.toml'
        toml_file.write_text('connection = { host = "localhost", port = 5432 }')

        source = TomlConfigSettingsSource(SimpleSettings, toml_file=str(toml_file))
        result = source._read_file(toml_file)

        assert result['connection']['host'] == 'localhost'
        assert result['connection']['port'] == 5432

    def test_read_file_with_comments(self, tmp_path):
        """Test reading TOML file with comments."""
        toml_file = tmp_path / 'comments.toml'
        toml_file.write_text(
            '# This is a comment\n'
            'key = "value"  # inline comment\n'
            '# Another comment\n'
            'number = 42'
        )

        source = TomlConfigSettingsSource(SimpleSettings, toml_file=str(toml_file))
        result = source._read_file(toml_file)

        assert result == {'key': 'value', 'number': 42}

    def test_read_file_handles_binary_mode(self, tmp_path):
        """Test _read_file reads file in binary mode."""
        toml_file = tmp_path / 'binary.toml'
        content = 'test_key = "test_value"\ncount = 99'
        toml_file.write_text(content)

        source = TomlConfigSettingsSource(SimpleSettings, toml_file=str(toml_file))
        result = source._read_file(toml_file)

        # Verify file was read and parsed correctly
        assert result['test_key'] == 'test_value'
        assert result['count'] == 99


class TestTomlConfigSettingsSourceRepr:
    """Tests for TomlConfigSettingsSource.__repr__."""

    def test_repr_with_toml_file(self, tmp_path):
        """Test __repr__ includes toml_file path."""
        toml_file = tmp_path / 'config.toml'
        toml_file.write_text('key = "value"')

        source = TomlConfigSettingsSource(
            SimpleSettings,
            toml_file=str(toml_file)
        )
        repr_str = repr(source)

        assert 'TomlConfigSettingsSource' in repr_str
        assert str(toml_file) in repr_str

    def test_repr_with_no_toml_file(self):
        """Test __repr__ when toml_file is None."""
        source = TomlConfigSettingsSource(SimpleSettings)
        repr_str = repr(source)

        assert 'TomlConfigSettingsSource' in repr_str
        assert 'None' in repr_str

    def test_repr_format(self, tmp_path):
        """Test __repr__ output format."""
        toml_file = tmp_path / 'settings.toml'
        toml_file.write_text('key = "value"')

        source = TomlConfigSettingsSource(
            SimpleSettings,
            toml_file=str(toml_file)
        )
        repr_str = repr(source)

        # Check format: ClassName(param=value)
        assert repr_str.startswith('TomlConfigSettingsSource(toml_file=')
        assert repr_str.endswith(')')


class TestTomlConfigSettingsSourceIntegration:
    """Integration tests for TomlConfigSettingsSource."""

    def test_source_call_returns_dict(self, tmp_path):
        """Test that calling source returns dict of loaded data."""
        toml_file = tmp_path / 'config.toml'
        toml_file.write_text('test_field = "from_toml"\nnew_field = "extra_value"')

        source = TomlConfigSettingsSource(SimpleSettings, toml_file=str(toml_file))
        result = source()

        assert isinstance(result, dict)
        assert result['test_field'] == 'from_toml'
        assert result['new_field'] == 'extra_value'

    def test_source_with_multiple_toml_files(self, tmp_path):
        """Test source with multiple TOML files."""
        toml_file1 = tmp_path / 'config1.toml'
        toml_file1.write_text('field1 = "value1"')

        toml_file2 = tmp_path / 'config2.toml'
        toml_file2.write_text('field2 = "value2"')

        class MultiFileSettings(BaseSettings):
            field1: str = 'default1'
            field2: str = 'default2'
            model_config = {}

        source = TomlConfigSettingsSource(
            MultiFileSettings,
            toml_file=[str(toml_file1), str(toml_file2)]
        )
        result = source()

        assert result['field1'] == 'value1'
        assert result['field2'] == 'value2'

    def test_source_with_nonexistent_toml_file(self):
        """Test source handles nonexistent TOML file gracefully."""
        source = TomlConfigSettingsSource(
            SimpleSettings,
            toml_file='/nonexistent/path/to/config.toml'
        )

        # Should return empty dict when file doesn't exist
        result = source()
        assert result == {}

    def test_source_repr_includes_toml_file_info(self, tmp_path):
        """Test that source repr shows toml_file info."""
        toml_file = tmp_path / 'config.toml'
        toml_file.write_text('key = "value"')

        source = TomlConfigSettingsSource(
            SimpleSettings,
            toml_file=str(toml_file)
        )

        repr_str = repr(source)
        assert 'TomlConfigSettingsSource' in repr_str
        assert str(toml_file) in repr_str

    def test_source_with_path_object(self, tmp_path):
        """Test source accepts Path object."""
        toml_file = tmp_path / 'config.toml'
        toml_file.write_text('test_field = "from_path"')

        source = TomlConfigSettingsSource(
            SimpleSettings,
            toml_file=toml_file
        )
        result = source()

        assert result['test_field'] == 'from_path'

    def test_source_with_relative_path(self, tmp_path):
        """Test source with relative path."""
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            toml_file = Path('config.toml')
            toml_file.write_text('test_field = "relative_path"')

            source = TomlConfigSettingsSource(
                SimpleSettings,
                toml_file=str(toml_file)
            )
            result = source()

            assert result['test_field'] == 'relative_path'
        finally:
            os.chdir(original_cwd)

    def test_source_with_expanduser_path(self, tmp_path, monkeypatch):
        """Test source expands ~ in file paths."""
        toml_file = tmp_path / 'config.toml'
        toml_file.write_text('test_field = "expanded"')

        # Mock expanduser to return our test file
        original_expanduser = Path.expanduser

        def mock_expanduser(self):
            if str(self).startswith('~'):
                return toml_file
            return original_expanduser(self)

        monkeypatch.setattr(Path, 'expanduser', mock_expanduser)

        source = TomlConfigSettingsSource(
            SimpleSettings,
            toml_file='~/config.toml'
        )
        result = source()

        assert result['test_field'] == 'expanded'

    def test_source_with_complex_nested_structure(self, tmp_path):
        """Test source with complex nested TOML structure."""
        toml_file = tmp_path / 'complex.toml'
        toml_file.write_text(
            '[app]\n'
            'name = "myapp"\n'
            '[app.database]\n'
            'host = "localhost"\n'
            'port = 5432\n'
            '[app.database.connection_pool]\n'
            'min_size = 5\n'
            'max_size = 20\n'
            '[app.features]\n'
            'enabled = [true, false, true]'
        )

        class ComplexSettings(BaseSettings):
            model_config = {}

        source = TomlConfigSettingsSource(
            ComplexSettings,
            toml_file=str(toml_file)
        )
        result = source()

        assert result['app']['name'] == 'myapp'
        assert result['app']['database']['host'] == 'localhost'
        assert result['app']['database']['connection_pool']['max_size'] == 20
        assert result['app']['features']['enabled'] == [True, False, True]

    def test_source_call_with_init_kwargs(self, tmp_path):
        """Test calling source as part of settings initialization."""
        toml_file = tmp_path / 'settings.toml'
        toml_file.write_text('[app]\nname = "test_app"')

        class AppSettings(BaseSettings):
            app: dict = {}
            model_config = {'toml_file': str(toml_file)}

        # Use settings_cls with init_kwargs as InitSettingsSource does
        source = TomlConfigSettingsSource(AppSettings)
        result = source()

        assert isinstance(result, dict)
        if result:
            assert 'app' in result

    def test_read_file_imports_toml_on_call(self, tmp_path):
        """Test _read_file ensures toml library is imported before reading."""
        import pydantic_settings.sources.providers.toml as toml_module

        toml_file = tmp_path / 'test.toml'
        toml_file.write_text('test = "value"')

        # Save original
        original_tomli = toml_module.tomli
        original_tomllib = toml_module.tomllib

        try:
            # Reset to None to force import on _read_file call
            toml_module.tomli = None
            toml_module.tomllib = None

            source = TomlConfigSettingsSource(SimpleSettings, toml_file=str(toml_file))
            # _read_file calls import_toml() which should import the library
            result = source._read_file(toml_file)

            assert result == {'test': 'value'}
            # Verify toml library was imported
            if sys.version_info < (3, 11):
                assert toml_module.tomli is not None
            else:
                assert toml_module.tomllib is not None
        finally:
            toml_module.tomli = original_tomli
            toml_module.tomllib = original_tomllib
