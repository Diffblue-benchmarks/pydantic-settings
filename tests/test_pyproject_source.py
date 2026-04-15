"""Tests for PyprojectTomlConfigSettingsSource."""

from pathlib import Path

import pytest

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic_settings.sources.providers.pyproject import PyprojectTomlConfigSettingsSource


@pytest.fixture
def pyproject_file(tmp_path):
    content = '[tool.pydantic-settings]\nname = "test_name"\nvalue = 42\n'
    file = tmp_path / "pyproject.toml"
    file.write_text(content)
    return file


class SimpleSettings(BaseSettings):
    model_config = SettingsConfigDict()
    name: str = "default"
    value: int = 0


def test_init_with_explicit_toml_file(pyproject_file):
    source = PyprojectTomlConfigSettingsSource(SimpleSettings, toml_file=pyproject_file)

    assert source.toml_file_path == pyproject_file.resolve()
    assert source.toml_data == {"name": "test_name", "value": 42}


def test_init_default_table_header(pyproject_file):
    source = PyprojectTomlConfigSettingsSource(SimpleSettings, toml_file=pyproject_file)

    assert source.toml_table_header == ("tool", "pydantic-settings")


def test_init_custom_table_header(tmp_path):
    content = '[mytool.mysettings]\nname = "custom"\n'
    file = tmp_path / "pyproject.toml"
    file.write_text(content)

    class CustomHeaderSettings(BaseSettings):
        model_config = SettingsConfigDict(pyproject_toml_table_header=("mytool", "mysettings"))
        name: str = "default"

    source = PyprojectTomlConfigSettingsSource(CustomHeaderSettings, toml_file=file)

    assert source.toml_table_header == ("mytool", "mysettings")
    assert source.toml_data == {"name": "custom"}


def test_init_missing_table_returns_empty(pyproject_file):
    class MissingHeaderSettings(BaseSettings):
        model_config = SettingsConfigDict(pyproject_toml_table_header=("nonexistent", "section"))
        name: str = "default"

    source = PyprojectTomlConfigSettingsSource(MissingHeaderSettings, toml_file=pyproject_file)

    assert source.toml_data == {}


def test_pick_pyproject_toml_file_with_provided_path(tmp_path):
    file = tmp_path / "pyproject.toml"
    file.write_text("")

    result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(file, 0)

    assert result == file.resolve()


def test_pick_pyproject_toml_file_no_provided_returns_cwd_path():
    result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(None, 0)
    expected = Path.cwd() / "pyproject.toml"

    assert result == expected


def test_pick_pyproject_toml_file_traverses_up(tmp_path, monkeypatch):
    subdir = tmp_path / "subdir"
    subsubdir = subdir / "subsubdir"
    subsubdir.mkdir(parents=True)
    pyproject = subdir / "pyproject.toml"
    pyproject.write_text("")

    monkeypatch.chdir(subsubdir)

    result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(None, 1)

    assert result == pyproject


def test_pick_pyproject_toml_file_depth_zero_no_traverse(tmp_path, monkeypatch):
    subdir = tmp_path / "subdir"
    parent_pyproject = tmp_path / "pyproject.toml"
    subdir.mkdir()
    parent_pyproject.write_text("")

    monkeypatch.chdir(subdir)

    result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(None, 0)

    assert result == subdir / "pyproject.toml"


def test_pick_pyproject_toml_file_depth_not_found_returns_rv(tmp_path, monkeypatch):
    subdir = tmp_path / "a" / "b" / "c"
    subdir.mkdir(parents=True)

    monkeypatch.chdir(subdir)

    result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(None, 1)

    assert result == subdir / "pyproject.toml"


def test_init_with_pyproject_toml_depth(tmp_path, monkeypatch):
    content = '[tool.pydantic-settings]\nname = "from_parent"\n'
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(content)

    subdir = tmp_path / "child"
    subdir.mkdir()
    monkeypatch.chdir(subdir)

    class DepthSettings(BaseSettings):
        model_config = SettingsConfigDict(pyproject_toml_depth=1)
        name: str = "default"

    source = PyprojectTomlConfigSettingsSource(DepthSettings)

    assert source.toml_data == {"name": "from_parent"}
