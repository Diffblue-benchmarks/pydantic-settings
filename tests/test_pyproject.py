"""Tests for pydantic_settings.sources.providers.pyproject module."""

from pathlib import Path
from tempfile import TemporaryDirectory
import pytest
from pydantic_settings import BaseSettings
from pydantic_settings.sources.providers.pyproject import (
    PyprojectTomlConfigSettingsSource,
)


def test_pyproject_toml_settings_source_init_with_provided_file(tmp_path):
    """Test PyprojectTomlConfigSettingsSource initialization with provided file."""
    # Create a temporary pyproject.toml file
    toml_file = tmp_path / "pyproject.toml"
    toml_file.write_text(
        """
[tool.pydantic-settings]
field1 = "value1"
field2 = 42
"""
    )

    class Settings(BaseSettings):
        field1: str = 'default'
        field2: int = 0

    source = PyprojectTomlConfigSettingsSource(
        settings_cls=Settings,
        toml_file=toml_file,
    )

    assert source.toml_file_path == toml_file.resolve()
    assert source.toml_table_header == ('tool', 'pydantic-settings')
    assert source.toml_data == {'field1': 'value1', 'field2': 42}


def test_pyproject_toml_settings_source_init_with_custom_table_header(tmp_path):
    """Test PyprojectTomlConfigSettingsSource with custom table header."""
    toml_file = tmp_path / "pyproject.toml"
    toml_file.write_text(
        """
[custom.app.config]
field1 = "custom_value"
"""
    )

    class Settings(BaseSettings):
        model_config = {
            'pyproject_toml_table_header': ('custom', 'app', 'config'),
        }
        field1: str = 'default'

    source = PyprojectTomlConfigSettingsSource(
        settings_cls=Settings,
        toml_file=toml_file,
    )

    assert source.toml_table_header == ('custom', 'app', 'config')
    assert source.toml_data == {'field1': 'custom_value'}


def test_pyproject_toml_settings_source_init_with_custom_depth(tmp_path):
    """Test PyprojectTomlConfigSettingsSource with custom depth."""
    # Create nested directory structure with pyproject.toml
    parent_dir = tmp_path / "parent"
    parent_dir.mkdir()
    toml_file = parent_dir / "pyproject.toml"
    toml_file.write_text(
        """
[tool.pydantic-settings]
field1 = "parent_value"
"""
    )

    # Create child directory
    child_dir = parent_dir / "child" / "grandchild"
    child_dir.mkdir(parents=True)

    class Settings(BaseSettings):
        model_config = {
            'pyproject_toml_depth': 2,
        }
        field1: str = 'default'

    # Change to child directory for testing depth search
    import os
    original_cwd = os.getcwd()
    try:
        os.chdir(child_dir)
        source = PyprojectTomlConfigSettingsSource(
            settings_cls=Settings,
        )
        assert source.toml_data == {'field1': 'parent_value'}
    finally:
        os.chdir(original_cwd)


def test_pyproject_toml_settings_source_init_missing_table(tmp_path):
    """Test PyprojectTomlConfigSettingsSource with missing table."""
    toml_file = tmp_path / "pyproject.toml"
    toml_file.write_text(
        """
[tool.other]
field1 = "value1"
"""
    )

    class Settings(BaseSettings):
        field1: str = 'default'

    source = PyprojectTomlConfigSettingsSource(
        settings_cls=Settings,
        toml_file=toml_file,
    )

    # When the table doesn't exist, toml_data should be empty
    assert source.toml_data == {}


def test_pick_pyproject_toml_file_with_provided_path(tmp_path):
    """Test _pick_pyproject_toml_file with provided path."""
    toml_file = tmp_path / "custom.toml"
    toml_file.write_text("")

    result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(
        provided=toml_file,
        depth=0,
    )

    assert result == toml_file.resolve()


def test_pick_pyproject_toml_file_in_cwd(tmp_path):
    """Test _pick_pyproject_toml_file finds file in cwd."""
    toml_file = tmp_path / "pyproject.toml"
    toml_file.write_text("")

    import os
    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(
            provided=None,
            depth=0,
        )
        assert result == Path.cwd() / 'pyproject.toml'
    finally:
        os.chdir(original_cwd)


def test_pick_pyproject_toml_file_search_parent_depth_0(tmp_path):
    """Test _pick_pyproject_toml_file with depth 0 doesn't search parents."""
    # Create parent with pyproject.toml
    parent_dir = tmp_path / "parent"
    parent_dir.mkdir()
    parent_toml = parent_dir / "pyproject.toml"
    parent_toml.write_text("")

    # Create child directory without pyproject.toml
    child_dir = parent_dir / "child"
    child_dir.mkdir()

    import os
    original_cwd = os.getcwd()
    try:
        os.chdir(child_dir)
        result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(
            provided=None,
            depth=0,
        )
        # Should return cwd/pyproject.toml even if it doesn't exist
        assert result == Path.cwd() / 'pyproject.toml'
        assert not result.is_file()
    finally:
        os.chdir(original_cwd)


def test_pick_pyproject_toml_file_search_parent_depth_1(tmp_path):
    """Test _pick_pyproject_toml_file with depth 1 searches parent."""
    # Create parent with pyproject.toml
    parent_dir = tmp_path / "parent"
    parent_dir.mkdir()
    parent_toml = parent_dir / "pyproject.toml"
    parent_toml.write_text("")

    # Create child directory without pyproject.toml
    child_dir = parent_dir / "child"
    child_dir.mkdir()

    import os
    original_cwd = os.getcwd()
    try:
        os.chdir(child_dir)
        result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(
            provided=None,
            depth=1,
        )
        # Should find parent's pyproject.toml
        assert result == parent_toml
        assert result.is_file()
    finally:
        os.chdir(original_cwd)


def test_pick_pyproject_toml_file_search_grandparent_depth_2(tmp_path):
    """Test _pick_pyproject_toml_file with depth 2 searches grandparent."""
    # Create grandparent with pyproject.toml
    grandparent_dir = tmp_path / "grandparent"
    grandparent_dir.mkdir()
    grandparent_toml = grandparent_dir / "pyproject.toml"
    grandparent_toml.write_text("")

    # Create nested child directories without pyproject.toml
    child_dir = grandparent_dir / "parent" / "child"
    child_dir.mkdir(parents=True)

    import os
    original_cwd = os.getcwd()
    try:
        os.chdir(child_dir)
        result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(
            provided=None,
            depth=2,
        )
        # Should find grandparent's pyproject.toml
        assert result == grandparent_toml
        assert result.is_file()
    finally:
        os.chdir(original_cwd)


def test_pick_pyproject_toml_file_stops_at_root():
    """Test _pick_pyproject_toml_file stops at filesystem root."""
    # Use a large depth that would exceed filesystem depth
    result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(
        provided=None,
        depth=1000,
    )

    # Should return some path (either found or cwd/pyproject.toml)
    # The important thing is it doesn't crash or go into infinite loop
    assert isinstance(result, Path)


def test_pick_pyproject_toml_file_no_file_found_returns_cwd(tmp_path):
    """Test _pick_pyproject_toml_file returns cwd path when no file found."""
    # Create a directory structure without any pyproject.toml
    test_dir = tmp_path / "empty" / "nested"
    test_dir.mkdir(parents=True)

    import os
    original_cwd = os.getcwd()
    try:
        os.chdir(test_dir)
        result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(
            provided=None,
            depth=2,
        )
        # Should return cwd/pyproject.toml even though it doesn't exist
        assert result == Path.cwd() / 'pyproject.toml'
    finally:
        os.chdir(original_cwd)
