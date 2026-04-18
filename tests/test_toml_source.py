"""Tests for TomlConfigSettingsSource."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from pydantic_settings import BaseSettings
from pydantic_settings.sources.providers.toml import TomlConfigSettingsSource, import_toml


class SimpleTomlSettings(BaseSettings):
    name: str = 'default'
    value: int = 0


class TestImportToml:
    def test_import_toml_on_python_311_plus(self) -> None:
        """Test that import_toml imports tomllib on Python >= 3.11."""
        import pydantic_settings.sources.providers.toml as toml_module

        original_tomllib = toml_module.tomllib
        try:
            toml_module.tomllib = None
            with patch.object(sys, 'version_info', (3, 12, 0)):
                import_toml()
                assert toml_module.tomllib is not None
        finally:
            toml_module.tomllib = original_tomllib

    def test_import_toml_on_python_311_plus_already_imported(self) -> None:
        """Test that import_toml short-circuits when tomllib is already set."""
        import pydantic_settings.sources.providers.toml as toml_module

        sentinel = object()
        original_tomllib = toml_module.tomllib
        try:
            toml_module.tomllib = sentinel
            with patch.object(sys, 'version_info', (3, 12, 0)):
                import_toml()
                assert toml_module.tomllib is sentinel
        finally:
            toml_module.tomllib = original_tomllib

    def test_import_toml_on_python_310_with_tomli(self) -> None:
        """Test that import_toml imports tomli on Python < 3.11."""
        import pydantic_settings.sources.providers.toml as toml_module

        original_tomli = toml_module.tomli
        try:
            toml_module.tomli = None
            with patch.object(sys, 'version_info', (3, 10, 0)):
                with patch.dict('sys.modules', {'tomli': __import__('tomllib')}):
                    import_toml()
                    assert toml_module.tomli is not None
        finally:
            toml_module.tomli = original_tomli

    def test_import_toml_on_python_310_already_imported(self) -> None:
        """Test that import_toml short-circuits when tomli is already set."""
        import pydantic_settings.sources.providers.toml as toml_module

        sentinel = object()
        original_tomli = toml_module.tomli
        try:
            toml_module.tomli = sentinel
            with patch.object(sys, 'version_info', (3, 10, 0)):
                import_toml()
                assert toml_module.tomli is sentinel
        finally:
            toml_module.tomli = original_tomli


class TestTomlConfigSettingsSourceInit:
    def test_init_with_toml_file(self, tmp_path: Path) -> None:
        toml_file = tmp_path / 'settings.toml'
        toml_file.write_text('[default]\nname = "test_value"\nvalue = 42\n')
        source = TomlConfigSettingsSource(SimpleTomlSettings, toml_file=toml_file)
        assert source.toml_file_path == toml_file

    def test_init_with_default_path_uses_config(self) -> None:
        class SettingsWithToml(BaseSettings):
            name: str = 'default'
            model_config = {'toml_file': 'my_config.toml'}

        source = TomlConfigSettingsSource(SettingsWithToml)
        assert source.toml_file_path == 'my_config.toml'

    def test_init_with_none_toml_file(self) -> None:
        source = TomlConfigSettingsSource(SimpleTomlSettings, toml_file=None)
        assert source.toml_file_path is None
        assert source.toml_data == {}

    def test_init_with_nonexistent_file(self, tmp_path: Path) -> None:
        toml_file = tmp_path / 'nonexistent.toml'
        source = TomlConfigSettingsSource(SimpleTomlSettings, toml_file=toml_file)
        assert source.toml_data == {}

    def test_init_reads_toml_data(self, tmp_path: Path) -> None:
        toml_file = tmp_path / 'settings.toml'
        toml_file.write_text('name = "from_toml"\nvalue = 99\n')
        source = TomlConfigSettingsSource(SimpleTomlSettings, toml_file=toml_file)
        assert source.toml_data == {'name': 'from_toml', 'value': 99}


class TestTomlConfigSettingsSourceReadFile:
    def test_read_file_returns_dict(self, tmp_path: Path) -> None:
        toml_file = tmp_path / 'test.toml'
        toml_file.write_text('key = "value"\nnumber = 10\n')
        source = TomlConfigSettingsSource(SimpleTomlSettings, toml_file=None)
        result = source._read_file(toml_file)
        assert result == {'key': 'value', 'number': 10}

    def test_read_file_with_nested_tables(self, tmp_path: Path) -> None:
        toml_file = tmp_path / 'nested.toml'
        toml_file.write_text('[section]\nkey = "value"\n')
        source = TomlConfigSettingsSource(SimpleTomlSettings, toml_file=None)
        result = source._read_file(toml_file)
        assert result == {'section': {'key': 'value'}}

    def test_read_file_calls_import_toml(self, tmp_path: Path) -> None:
        toml_file = tmp_path / 'test.toml'
        toml_file.write_text('key = "value"\n')
        source = TomlConfigSettingsSource(SimpleTomlSettings, toml_file=None)
        with patch('pydantic_settings.sources.providers.toml.import_toml') as mock_import:
            source._read_file(toml_file)
            mock_import.assert_called_once()


class TestTomlConfigSettingsSourceRepr:
    def test_repr_with_path(self, tmp_path: Path) -> None:
        toml_file = tmp_path / 'settings.toml'
        toml_file.write_text('name = "test"\n')
        source = TomlConfigSettingsSource(SimpleTomlSettings, toml_file=toml_file)
        result = repr(source)
        assert result == f'TomlConfigSettingsSource(toml_file={toml_file})'

    def test_repr_with_none(self) -> None:
        source = TomlConfigSettingsSource(SimpleTomlSettings, toml_file=None)
        assert repr(source) == 'TomlConfigSettingsSource(toml_file=None)'


class TestTomlConfigSettingsSourceIntegration:
    def test_settings_loaded_from_toml(self, tmp_path: Path) -> None:
        toml_file = tmp_path / 'app.toml'
        toml_file.write_text('name = "integrated"\nvalue = 123\n')

        class MySettings(BaseSettings):
            name: str = 'default'
            value: int = 0

            @classmethod
            def settings_customise_sources(cls, settings_cls, **kwargs):
                return (TomlConfigSettingsSource(settings_cls, toml_file=toml_file),)

        settings = MySettings()
        assert settings.name == 'integrated'
        assert settings.value == 123
