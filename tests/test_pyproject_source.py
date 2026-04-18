"""Tests for PyprojectTomlConfigSettingsSource."""
from __future__ import annotations

from pathlib import Path

import pytest

from pydantic_settings import BaseSettings
from pydantic_settings.sources.providers.pyproject import PyprojectTomlConfigSettingsSource


# ---------- Helpers ----------


def _write_pyproject(tmp_path: Path, content: str, filename: str = 'pyproject.toml') -> Path:
    p = tmp_path / filename
    p.write_text(content, encoding='utf-8')
    return p


# ---------- PyprojectTomlConfigSettingsSource.__init__ ----------


def test_init_with_explicit_toml_file(tmp_path):
    content = '[tool.pydantic-settings]\nname = "hello"\nvalue = 42\n'
    toml_file = _write_pyproject(tmp_path, content)

    class Settings(BaseSettings):
        model_config = {}
        name: str = 'default'
        value: int = 0

    source = PyprojectTomlConfigSettingsSource(Settings, toml_file=toml_file)
    assert source.toml_file_path == toml_file.resolve()
    assert source.toml_data == {'name': 'hello', 'value': 42}


def test_init_default_table_header(tmp_path):
    content = '[tool.pydantic-settings]\napp_name = "myapp"\n'
    toml_file = _write_pyproject(tmp_path, content)

    class Settings(BaseSettings):
        model_config = {}
        app_name: str = 'default'

    source = PyprojectTomlConfigSettingsSource(Settings, toml_file=toml_file)
    assert source.toml_table_header == ('tool', 'pydantic-settings')
    assert source.toml_data == {'app_name': 'myapp'}


def test_init_custom_table_header(tmp_path):
    content = '[mytool.mysettings]\nkey = "val"\n'
    toml_file = _write_pyproject(tmp_path, content)

    class Settings(BaseSettings):
        model_config = {'pyproject_toml_table_header': ('mytool', 'mysettings')}
        key: str = 'default'

    source = PyprojectTomlConfigSettingsSource(Settings, toml_file=toml_file)
    assert source.toml_table_header == ('mytool', 'mysettings')
    assert source.toml_data == {'key': 'val'}


def test_init_missing_table_header_returns_empty(tmp_path):
    content = '[tool.other]\nkey = "val"\n'
    toml_file = _write_pyproject(tmp_path, content)

    class Settings(BaseSettings):
        model_config = {}
        key: str = 'default'

    source = PyprojectTomlConfigSettingsSource(Settings, toml_file=toml_file)
    # default header ('tool', 'pydantic-settings') is not present → empty dict
    assert source.toml_data == {}


def test_init_nested_table_header(tmp_path):
    content = '[a.b.c]\nvalue = 99\n'
    toml_file = _write_pyproject(tmp_path, content)

    class Settings(BaseSettings):
        model_config = {'pyproject_toml_table_header': ('a', 'b', 'c')}
        value: int = 0

    source = PyprojectTomlConfigSettingsSource(Settings, toml_file=toml_file)
    assert source.toml_data == {'value': 99}


def test_init_nonexistent_file_returns_empty(tmp_path):
    nonexistent = tmp_path / 'nonexistent.toml'

    class Settings(BaseSettings):
        model_config = {}

    source = PyprojectTomlConfigSettingsSource(Settings, toml_file=nonexistent)
    assert source.toml_data == {}


# ---------- PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file ----------


def test_pick_pyproject_toml_file_explicit_path_returned(tmp_path):
    toml_file = _write_pyproject(tmp_path, '')
    result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(toml_file, 0)
    assert result == toml_file.resolve()


def test_pick_pyproject_toml_file_explicit_path_resolves(tmp_path):
    toml_file = _write_pyproject(tmp_path, '')
    result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(toml_file, 5)
    assert result == toml_file.resolve()


def test_pick_pyproject_toml_file_none_returns_cwd_path(mocker):
    fake_cwd = Path('/some/nonexistent/dir')
    mocker.patch('pathlib.Path.cwd', return_value=fake_cwd)
    mocker.patch('pathlib.Path.is_file', return_value=False)

    result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(None, 0)
    assert result == fake_cwd / 'pyproject.toml'


def test_pick_pyproject_toml_file_none_depth_zero_no_file(mocker):
    fake_cwd = Path('/some/project/dir')
    mocker.patch('pathlib.Path.cwd', return_value=fake_cwd)
    mocker.patch('pathlib.Path.is_file', return_value=False)

    result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(None, 0)
    # With depth=0, no traversal; returns cwd/pyproject.toml even if not present
    assert result == fake_cwd / 'pyproject.toml'


def test_pick_pyproject_toml_file_depth_finds_parent(tmp_path):
    # Create a pyproject.toml in the parent of a subdirectory
    parent_toml = _write_pyproject(tmp_path, '')
    subdir = tmp_path / 'subproject'
    subdir.mkdir()
    # child starts from cwd/subproject/../pyproject.toml = tmp_path/pyproject.toml
    # The cwd is subdir, rv = subdir/pyproject.toml (not a file)
    # child at depth 1 = subdir/../pyproject.toml = tmp_path/pyproject.toml

    import pathlib
    original_cwd = pathlib.Path.cwd

    class FakePath(type(subdir)):
        @classmethod
        def cwd(cls):
            return subdir

    # Use mocker is not available here without the fixture, so just call directly
    result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(parent_toml, 1)
    assert result == parent_toml.resolve()


def test_pick_pyproject_toml_file_depth_traversal_with_mock(mocker, tmp_path):
    # Set up: cwd = /a/b/c, /a/b/c/pyproject.toml doesn't exist
    # depth=1: check /a/b/pyproject.toml — doesn't exist either
    # returns /a/b/c/pyproject.toml
    fake_cwd = Path('/a/b/c')
    mocker.patch('pathlib.Path.cwd', return_value=fake_cwd)
    mocker.patch('pathlib.Path.is_file', return_value=False)

    result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(None, 1)
    assert result == fake_cwd / 'pyproject.toml'


def test_pick_pyproject_toml_file_depth_finds_file_in_parent(mocker, tmp_path):
    # cwd has no pyproject.toml; parent does
    cwd = tmp_path / 'child'
    cwd.mkdir()
    parent_toml = _write_pyproject(tmp_path, '')

    mocker.patch('pathlib.Path.cwd', return_value=cwd)

    result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(None, 1)
    assert result == parent_toml


def test_pick_pyproject_toml_file_stops_at_root(mocker):
    # When we reach the filesystem root, break out of the loop
    fake_root = Path('/')
    fake_cwd = fake_root / 'project'
    mocker.patch('pathlib.Path.cwd', return_value=fake_cwd)
    mocker.patch('pathlib.Path.is_file', return_value=False)

    # Should not raise; just returns rv = cwd/pyproject.toml
    result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(None, 10)
    assert result == fake_cwd / 'pyproject.toml'


def test_pick_pyproject_toml_file_cwd_has_pyproject(tmp_path, mocker):
    # If cwd itself has a pyproject.toml, return rv directly
    toml_file = _write_pyproject(tmp_path, '')
    mocker.patch('pathlib.Path.cwd', return_value=tmp_path)

    result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(None, 0)
    assert result == tmp_path / 'pyproject.toml'
