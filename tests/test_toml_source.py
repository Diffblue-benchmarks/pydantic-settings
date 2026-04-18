"""Tests for TomlConfigSettingsSource class and import_toml function."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from pydantic_settings import BaseSettings
from pydantic_settings.sources.providers.toml import TomlConfigSettingsSource, import_toml


class SimpleTomlSettings(BaseSettings):
    """Simple settings class for basic TOML tests."""

    name: str = 'default_name'
    value: int = 42


class TomlSettingsWithTomlFile(BaseSettings):
    """Settings class with toml_file configured."""

    model_config = {'toml_file': 'config.toml'}

    name: str = 'default_name'
    value: int = 0


class TestImportToml:
    """Tests for import_toml function."""

    def test_import_toml_succeeds(self) -> None:
        """Test that import_toml successfully imports the TOML library."""
        import_toml()

        # Verify the global was set
        if sys.version_info < (3, 11):
            from pydantic_settings.sources.providers import toml as toml_module

            assert toml_module.tomli is not None
        else:
            from pydantic_settings.sources.providers import toml as toml_module

            assert toml_module.tomllib is not None

    def test_import_toml_idempotent(self) -> None:
        """Test that calling import_toml multiple times is safe."""
        import_toml()
        import_toml()  # Should not raise

    @pytest.mark.skipif(
        sys.version_info >= (3, 11),
        reason='Test only relevant for Python < 3.11 where tomli is used',
    )
    def test_import_toml_raises_import_error_when_tomli_missing(self) -> None:
        """Test that import_toml raises ImportError when tomli is not installed."""
        from pydantic_settings.sources.providers import toml as toml_module

        original_tomli = toml_module.tomli
        try:
            toml_module.tomli = None

            with patch.dict('sys.modules', {'tomli': None}):
                with patch('builtins.__import__', side_effect=ImportError('No module named tomli')):
                    with pytest.raises(ImportError, match='tomli is not installed'):
                        import_toml()
        finally:
            toml_module.tomli = original_tomli

    def test_import_toml_early_return_when_tomli_already_loaded(self) -> None:
        """Test early return path when tomli is already loaded on Python < 3.11."""
        from pydantic_settings.sources.providers import toml as toml_module

        original_tomli = toml_module.tomli
        try:
            # Simulate tomli already being loaded
            import tomli as real_tomli

            toml_module.tomli = real_tomli

            # Mock version_info to simulate Python < 3.11
            fake_version = (3, 10, 0)
            with patch.object(sys, 'version_info', fake_version):
                # This should hit the early return on line 32-33
                import_toml()

            # tomli should still be the same value (unchanged by the function)
            assert toml_module.tomli is real_tomli
        finally:
            toml_module.tomli = original_tomli

    def test_import_toml_imports_tomli_when_not_loaded(self) -> None:
        """Test that tomli is imported when not loaded on simulated Python < 3.11."""
        from pydantic_settings.sources.providers import toml as toml_module

        original_tomli = toml_module.tomli
        try:
            # Set tomli to None to simulate it not being loaded
            toml_module.tomli = None

            # Mock version_info to simulate Python < 3.11
            fake_version = (3, 10, 0)
            with patch.object(sys, 'version_info', fake_version):
                # This should hit lines 34-35, importing tomli
                import_toml()

            # tomli should now be loaded
            assert toml_module.tomli is not None
        finally:
            toml_module.tomli = original_tomli


class TestTomlConfigSettingsSourceInit:
    """Tests for TomlConfigSettingsSource.__init__ method."""

    def test_init_with_no_toml_file(self) -> None:
        """Test initialization without toml_file."""
        source = TomlConfigSettingsSource(SimpleTomlSettings, toml_file=None)

        assert source.toml_file_path is None
        assert source.toml_data == {}

    def test_init_with_toml_file_path(self, tmp_path: Path) -> None:
        """Test initialization with toml_file as a Path object."""
        toml_file = tmp_path / 'config.toml'
        toml_file.write_text('name = "from_toml"\nvalue = 123\n')

        source = TomlConfigSettingsSource(SimpleTomlSettings, toml_file=toml_file)

        assert source.toml_file_path == toml_file
        assert source.toml_data == {'name': 'from_toml', 'value': 123}

    def test_init_with_toml_file_string(self, tmp_path: Path) -> None:
        """Test initialization with toml_file as a string path."""
        toml_file = tmp_path / 'config.toml'
        toml_file.write_text('name = "string_path"\n')

        source = TomlConfigSettingsSource(SimpleTomlSettings, toml_file=str(toml_file))

        assert source.toml_file_path == str(toml_file)
        assert source.toml_data == {'name': 'string_path'}

    def test_init_with_deep_merge(self, tmp_path: Path) -> None:
        """Test initialization with deep_merge enabled."""
        toml_file1 = tmp_path / 'config1.toml'
        toml_file1.write_text('name = "first"\n')
        toml_file2 = tmp_path / 'config2.toml'
        toml_file2.write_text('value = 999\n')

        source = TomlConfigSettingsSource(
            SimpleTomlSettings, toml_file=[toml_file1, toml_file2], deep_merge=True
        )

        assert source.toml_data == {'name': 'first', 'value': 999}

    def test_init_uses_model_config_toml_file(self, tmp_path: Path) -> None:
        """Test initialization uses toml_file from model_config when not specified."""
        toml_file = tmp_path / 'config.toml'
        toml_file.write_text('name = "from_config"\nvalue = 55\n')

        with patch.object(
            TomlSettingsWithTomlFile,
            'model_config',
            {'toml_file': toml_file},
        ):
            source = TomlConfigSettingsSource(TomlSettingsWithTomlFile)

            assert source.toml_file_path == toml_file
            assert source.toml_data == {'name': 'from_config', 'value': 55}

    def test_init_with_nonexistent_file(self, tmp_path: Path) -> None:
        """Test initialization with non-existent file returns empty data."""
        nonexistent = tmp_path / 'nonexistent.toml'

        source = TomlConfigSettingsSource(SimpleTomlSettings, toml_file=nonexistent)

        assert source.toml_data == {}


class TestTomlConfigSettingsSourceReadFile:
    """Tests for TomlConfigSettingsSource._read_file method."""

    def test_read_file_parses_toml(self, tmp_path: Path) -> None:
        """Test that _read_file correctly parses TOML content."""
        toml_file = tmp_path / 'test.toml'
        toml_file.write_text('key = "value"\nnumber = 42\n')

        source = TomlConfigSettingsSource(SimpleTomlSettings, toml_file=None)
        result = source._read_file(toml_file)

        assert result == {'key': 'value', 'number': 42}

    def test_read_file_with_nested_tables(self, tmp_path: Path) -> None:
        """Test that _read_file handles nested TOML tables."""
        toml_file = tmp_path / 'nested.toml'
        toml_file.write_text('[section]\nkey = "value"\n\n[section.subsection]\ninner = 123\n')

        source = TomlConfigSettingsSource(SimpleTomlSettings, toml_file=None)
        result = source._read_file(toml_file)

        assert result == {'section': {'key': 'value', 'subsection': {'inner': 123}}}

    def test_read_file_with_arrays(self, tmp_path: Path) -> None:
        """Test that _read_file handles TOML arrays."""
        toml_file = tmp_path / 'arrays.toml'
        toml_file.write_text('items = [1, 2, 3]\nnames = ["a", "b"]\n')

        source = TomlConfigSettingsSource(SimpleTomlSettings, toml_file=None)
        result = source._read_file(toml_file)

        assert result == {'items': [1, 2, 3], 'names': ['a', 'b']}


class TestTomlConfigSettingsSourceRepr:
    """Tests for TomlConfigSettingsSource.__repr__ method."""

    def test_repr_contains_class_name(self) -> None:
        """Test that __repr__ contains the class name."""
        source = TomlConfigSettingsSource(SimpleTomlSettings, toml_file=None)
        repr_str = repr(source)

        assert 'TomlConfigSettingsSource' in repr_str

    def test_repr_contains_toml_file_path(self, tmp_path: Path) -> None:
        """Test that __repr__ contains toml_file value."""
        toml_file = tmp_path / 'config.toml'
        toml_file.write_text('name = "test"\n')

        source = TomlConfigSettingsSource(SimpleTomlSettings, toml_file=toml_file)
        repr_str = repr(source)

        assert 'toml_file=' in repr_str
        assert 'config.toml' in repr_str

    def test_repr_with_none_path(self) -> None:
        """Test that __repr__ handles None toml_file_path."""
        source = TomlConfigSettingsSource(SimpleTomlSettings, toml_file=None)
        repr_str = repr(source)

        assert 'toml_file=None' in repr_str


class TestTomlConfigSettingsSourceIntegration:
    """Integration tests for TomlConfigSettingsSource with BaseSettings."""

    def test_basic_toml_loading(self, tmp_path: Path) -> None:
        """Test basic TOML loading through TomlConfigSettingsSource."""
        toml_file = tmp_path / 'config.toml'
        toml_file.write_text('name = "toml_value"\nvalue = 789\n')

        source = TomlConfigSettingsSource(SimpleTomlSettings, toml_file=toml_file)
        data = source()

        assert data == {'name': 'toml_value', 'value': 789}

    def test_toml_with_multiple_files(self, tmp_path: Path) -> None:
        """Test TOML loading with multiple files."""
        toml_file1 = tmp_path / 'base.toml'
        toml_file1.write_text('name = "base"\nvalue = 100\n')
        toml_file2 = tmp_path / 'override.toml'
        toml_file2.write_text('value = 200\n')

        source = TomlConfigSettingsSource(
            SimpleTomlSettings, toml_file=[toml_file1, toml_file2]
        )
        data = source()

        assert data['value'] == 200

    def test_toml_call_returns_init_kwargs(self, tmp_path: Path) -> None:
        """Test that __call__ returns the parsed TOML data."""
        toml_file = tmp_path / 'config.toml'
        toml_file.write_text('name = "call_test"\n')

        source = TomlConfigSettingsSource(SimpleTomlSettings, toml_file=toml_file)
        result = source()

        assert isinstance(result, dict)
        assert result == {'name': 'call_test'}
