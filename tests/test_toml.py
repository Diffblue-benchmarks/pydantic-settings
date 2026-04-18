"""Tests for TOML file settings source."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from pydantic_settings.main import BaseSettings
from pydantic_settings.sources.providers.toml import (
    TomlConfigSettingsSource,
    import_toml,
)


@pytest.fixture(autouse=True)
def _reset_toml_globals():
    """Reset the module-level tomli/tomllib globals before each test."""
    import pydantic_settings.sources.providers.toml as toml_mod

    old_tomli = toml_mod.tomli
    old_tomllib = toml_mod.tomllib
    toml_mod.tomli = None
    toml_mod.tomllib = None
    yield
    toml_mod.tomli = old_tomli
    toml_mod.tomllib = old_tomllib


class TestImportToml:
    def test_import_toml_sets_tomllib_on_311_plus(self) -> None:
        import pydantic_settings.sources.providers.toml as toml_mod

        with patch.object(sys, 'version_info', (3, 12, 0)):
            assert toml_mod.tomllib is None
            import_toml()
            assert toml_mod.tomllib is not None

    def test_import_toml_noop_when_tomllib_already_set(self) -> None:
        import pydantic_settings.sources.providers.toml as toml_mod

        sentinel = object()
        toml_mod.tomllib = sentinel  # type: ignore[assignment]
        with patch.object(sys, 'version_info', (3, 12, 0)):
            import_toml()
            assert toml_mod.tomllib is sentinel

    def test_import_toml_sets_tomli_on_310(self) -> None:
        import pydantic_settings.sources.providers.toml as toml_mod

        with patch.object(sys, 'version_info', (3, 10, 0)):
            assert toml_mod.tomli is None
            import_toml()
            assert toml_mod.tomli is not None

    def test_import_toml_noop_when_tomli_already_set(self) -> None:
        import pydantic_settings.sources.providers.toml as toml_mod

        sentinel = object()
        toml_mod.tomli = sentinel  # type: ignore[assignment]
        with patch.object(sys, 'version_info', (3, 10, 0)):
            import_toml()
            assert toml_mod.tomli is sentinel


class TestTomlConfigSettingsSourceInit:
    def test_init_with_explicit_toml_file(self, tmp_path: Path) -> None:
        toml_file = tmp_path / 'settings.toml'
        toml_file.write_text('[section]\nkey = "value"\n')

        class MySettings(BaseSettings):
            pass

        source = TomlConfigSettingsSource(MySettings, toml_file=toml_file)
        assert source.toml_file_path == toml_file
        assert source.toml_data == {'section': {'key': 'value'}}

    def test_init_with_none_toml_file(self) -> None:
        class MySettings(BaseSettings):
            pass

        source = TomlConfigSettingsSource(MySettings, toml_file=None)
        assert source.toml_file_path is None
        assert source.toml_data == {}

    def test_init_uses_model_config_toml_file(self, tmp_path: Path) -> None:
        toml_file = tmp_path / 'cfg.toml'
        toml_file.write_text('x = 1\n')

        class MySettings(BaseSettings):
            model_config = {'toml_file': toml_file}

        source = TomlConfigSettingsSource(MySettings)
        assert source.toml_file_path == toml_file
        assert source.toml_data == {'x': 1}

    def test_init_with_nonexistent_file(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / 'does_not_exist.toml'

        class MySettings(BaseSettings):
            pass

        source = TomlConfigSettingsSource(MySettings, toml_file=nonexistent)
        assert source.toml_data == {}

    def test_init_with_deep_merge(self, tmp_path: Path) -> None:
        f1 = tmp_path / 'a.toml'
        f2 = tmp_path / 'b.toml'
        f1.write_text('[db]\nhost = "localhost"\nport = 5432\n')
        f2.write_text('[db]\nport = 3306\nname = "mydb"\n')

        class MySettings(BaseSettings):
            pass

        source = TomlConfigSettingsSource(MySettings, toml_file=[f1, f2], deep_merge=True)
        assert source.toml_data == {'db': {'host': 'localhost', 'port': 3306, 'name': 'mydb'}}


class TestTomlConfigSettingsSourceReadFile:
    def test_read_file_returns_parsed_toml(self, tmp_path: Path) -> None:
        toml_file = tmp_path / 'test.toml'
        toml_file.write_text('name = "test"\ncount = 42\n')

        class MySettings(BaseSettings):
            pass

        source = TomlConfigSettingsSource(MySettings, toml_file=toml_file)
        assert source.toml_data == {'name': 'test', 'count': 42}

    def test_read_file_with_nested_tables(self, tmp_path: Path) -> None:
        toml_file = tmp_path / 'nested.toml'
        toml_file.write_text('[database]\nhost = "localhost"\nport = 5432\n\n[database.credentials]\nuser = "admin"\n')

        class MySettings(BaseSettings):
            pass

        source = TomlConfigSettingsSource(MySettings, toml_file=toml_file)
        assert source.toml_data == {
            'database': {
                'host': 'localhost',
                'port': 5432,
                'credentials': {'user': 'admin'},
            }
        }


class TestTomlConfigSettingsSourceRepr:
    def test_repr_with_file_path(self, tmp_path: Path) -> None:
        toml_file = tmp_path / 'settings.toml'
        toml_file.write_text('key = "val"\n')

        class MySettings(BaseSettings):
            pass

        source = TomlConfigSettingsSource(MySettings, toml_file=toml_file)
        assert repr(source) == f'TomlConfigSettingsSource(toml_file={toml_file})'

    def test_repr_with_none(self) -> None:
        class MySettings(BaseSettings):
            pass

        source = TomlConfigSettingsSource(MySettings, toml_file=None)
        assert repr(source) == 'TomlConfigSettingsSource(toml_file=None)'
