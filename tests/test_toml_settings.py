"""Tests for TomlConfigSettingsSource."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from pydantic_settings import BaseSettings
from pydantic_settings.sources.providers.toml import TomlConfigSettingsSource, import_toml


@pytest.fixture
def toml_file(tmp_path: Path) -> Path:
    data = 'app_name = "test_app"\ndebug = true\nport = 8080\n'
    file = tmp_path / 'settings.toml'
    file.write_text(data)
    return file


@pytest.fixture
def nested_toml_file(tmp_path: Path) -> Path:
    data = 'app_name = "nested_app"\n\n[nested]\nkey = "value"\n'
    file = tmp_path / 'nested.toml'
    file.write_text(data)
    return file


class SimpleSettings(BaseSettings):
    app_name: str = 'default'
    debug: bool = False
    port: int = 3000


def test_import_toml_sets_global() -> None:
    import pydantic_settings.sources.providers.toml as toml_module
    import_toml()
    if sys.version_info < (3, 11):
        assert toml_module.tomli is not None
    else:
        assert toml_module.tomllib is not None


def test_import_toml_idempotent() -> None:
    import_toml()
    import_toml()  # second call should return early without error


def test_init_with_explicit_toml_file(toml_file: Path) -> None:
    source = TomlConfigSettingsSource(SimpleSettings, toml_file=toml_file)
    assert source.toml_file_path == toml_file
    assert source.toml_data == {'app_name': 'test_app', 'debug': True, 'port': 8080}


def test_init_uses_model_config_toml_file(toml_file: Path) -> None:
    class ConfiguredSettings(BaseSettings):
        model_config = {'toml_file': toml_file}

        app_name: str = 'default'

    source = TomlConfigSettingsSource(ConfiguredSettings)
    assert source.toml_file_path == toml_file
    assert source.toml_data.get('app_name') == 'test_app'


def test_init_with_none_toml_file() -> None:
    source = TomlConfigSettingsSource(SimpleSettings, toml_file=None)
    assert source.toml_file_path is None
    assert source.toml_data == {}


def test_init_deep_merge(tmp_path: Path) -> None:
    file1 = tmp_path / 'first.toml'
    file2 = tmp_path / 'second.toml'
    file1.write_text('a = 1\n\n[nested]\nx = 1\ny = 2\n')
    file2.write_text('b = 2\n\n[nested]\ny = 99\nz = 3\n')

    source = TomlConfigSettingsSource(SimpleSettings, toml_file=[file1, file2], deep_merge=True)
    assert source.toml_data['nested'] == {'x': 1, 'y': 99, 'z': 3}


def test_init_no_deep_merge(tmp_path: Path) -> None:
    file1 = tmp_path / 'first.toml'
    file2 = tmp_path / 'second.toml'
    file1.write_text('a = 1\n\n[nested]\nx = 1\n')
    file2.write_text('b = 2\n\n[nested]\ny = 99\n')

    source = TomlConfigSettingsSource(SimpleSettings, toml_file=[file1, file2], deep_merge=False)
    assert source.toml_data['nested'] == {'y': 99}


def test_read_file(toml_file: Path) -> None:
    source = TomlConfigSettingsSource(SimpleSettings, toml_file=toml_file)
    result = source._read_file(toml_file)
    assert result == {'app_name': 'test_app', 'debug': True, 'port': 8080}


def test_repr_with_file_path(toml_file: Path) -> None:
    source = TomlConfigSettingsSource(SimpleSettings, toml_file=toml_file)
    assert repr(source) == f'TomlConfigSettingsSource(toml_file={toml_file})'


def test_repr_with_none() -> None:
    source = TomlConfigSettingsSource(SimpleSettings, toml_file=None)
    assert repr(source) == 'TomlConfigSettingsSource(toml_file=None)'


def test_repr_with_list_of_files(tmp_path: Path) -> None:
    file1 = tmp_path / 'a.toml'
    file2 = tmp_path / 'b.toml'
    file1.write_text('')
    file2.write_text('')
    files = [file1, file2]
    source = TomlConfigSettingsSource(SimpleSettings, toml_file=files)
    assert repr(source) == f'TomlConfigSettingsSource(toml_file={files})'


def test_init_missing_file_ignored() -> None:
    source = TomlConfigSettingsSource(SimpleSettings, toml_file=Path('/nonexistent/path/settings.toml'))
    assert source.toml_data == {}


def test_toml_data_populates_settings(toml_file: Path) -> None:
    class MySettings(BaseSettings):
        model_config = {'toml_file': toml_file, 'extra': 'ignore'}

        app_name: str = 'default'
        port: int = 3000

        @classmethod
        def settings_customise_sources(cls, settings_cls, **kwargs):
            return (TomlConfigSettingsSource(settings_cls),)

    settings = MySettings()
    assert settings.app_name == 'test_app'
    assert settings.port == 8080
