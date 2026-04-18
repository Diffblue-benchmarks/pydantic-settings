"""Tests for PyprojectTomlConfigSettingsSource."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from pydantic_settings import BaseSettings
from pydantic_settings.sources.providers.pyproject import PyprojectTomlConfigSettingsSource


class TestPyprojectTomlConfigSettingsSource:
    """Tests for PyprojectTomlConfigSettingsSource class."""

    def test_pick_pyproject_toml_file_with_provided_path(self, tmp_path: Path) -> None:
        """Test _pick_pyproject_toml_file returns resolved path when provided."""
        toml_file = tmp_path / 'pyproject.toml'
        toml_file.touch()

        result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(toml_file, 0)

        assert result == toml_file.resolve()

    def test_pick_pyproject_toml_file_with_no_provided_path_cwd_exists(self, tmp_path: Path) -> None:
        """Test _pick_pyproject_toml_file returns cwd/pyproject.toml when it exists."""
        toml_file = tmp_path / 'pyproject.toml'
        toml_file.touch()

        with patch.object(Path, 'cwd', return_value=tmp_path):
            result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(None, 0)

        assert result == toml_file

    def test_pick_pyproject_toml_file_no_file_depth_zero(self, tmp_path: Path) -> None:
        """Test _pick_pyproject_toml_file returns cwd path when no file exists and depth is 0."""
        with patch.object(Path, 'cwd', return_value=tmp_path):
            result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(None, 0)

        assert result == tmp_path / 'pyproject.toml'

    def test_pick_pyproject_toml_file_finds_parent_file(self, tmp_path: Path) -> None:
        """Test _pick_pyproject_toml_file finds pyproject.toml in parent directory."""
        parent_toml = tmp_path / 'pyproject.toml'
        parent_toml.touch()

        subdir = tmp_path / 'subdir'
        subdir.mkdir()

        with patch.object(Path, 'cwd', return_value=subdir):
            result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(None, 1)

        assert result == parent_toml

    def test_pick_pyproject_toml_file_finds_grandparent_file(self, tmp_path: Path) -> None:
        """Test _pick_pyproject_toml_file finds pyproject.toml in grandparent directory with depth 2."""
        grandparent_toml = tmp_path / 'pyproject.toml'
        grandparent_toml.touch()

        subdir = tmp_path / 'subdir'
        subdir.mkdir()

        subsubdir = subdir / 'subsubdir'
        subsubdir.mkdir()

        with patch.object(Path, 'cwd', return_value=subsubdir):
            result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(None, 2)

        assert result == grandparent_toml

    def test_pick_pyproject_toml_file_returns_default_when_depth_too_shallow(self, tmp_path: Path) -> None:
        """Test _pick_pyproject_toml_file returns default when depth is insufficient."""
        grandparent_toml = tmp_path / 'pyproject.toml'
        grandparent_toml.touch()

        subdir = tmp_path / 'subdir'
        subdir.mkdir()

        subsubdir = subdir / 'subsubdir'
        subsubdir.mkdir()

        with patch.object(Path, 'cwd', return_value=subsubdir):
            result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(None, 1)

        assert result == subsubdir / 'pyproject.toml'

    def test_init_with_default_settings(self, tmp_path: Path) -> None:
        """Test __init__ with default configuration."""
        toml_content = """
[tool.pydantic-settings]
app_name = "TestApp"
debug = true
"""
        toml_file = tmp_path / 'pyproject.toml'
        toml_file.write_text(toml_content)

        class Settings(BaseSettings):
            app_name: str = 'default'
            debug: bool = False

        source = PyprojectTomlConfigSettingsSource(Settings, toml_file=toml_file)

        assert source.toml_file_path == toml_file.resolve()
        assert source.toml_table_header == ('tool', 'pydantic-settings')
        assert source.toml_data == {'app_name': 'TestApp', 'debug': True}

    def test_init_with_custom_table_header(self, tmp_path: Path) -> None:
        """Test __init__ with custom pyproject_toml_table_header."""
        toml_content = """
[tool.myapp.config]
app_name = "CustomApp"
"""
        toml_file = tmp_path / 'pyproject.toml'
        toml_file.write_text(toml_content)

        class Settings(BaseSettings):
            model_config = {'pyproject_toml_table_header': ('tool', 'myapp', 'config')}
            app_name: str = 'default'

        source = PyprojectTomlConfigSettingsSource(Settings, toml_file=toml_file)

        assert source.toml_table_header == ('tool', 'myapp', 'config')
        assert source.toml_data == {'app_name': 'CustomApp'}

    def test_init_with_missing_table_header(self, tmp_path: Path) -> None:
        """Test __init__ when configured table header doesn't exist in TOML."""
        toml_content = """
[other.section]
value = 1
"""
        toml_file = tmp_path / 'pyproject.toml'
        toml_file.write_text(toml_content)

        class Settings(BaseSettings):
            app_name: str = 'default'

        source = PyprojectTomlConfigSettingsSource(Settings, toml_file=toml_file)

        assert source.toml_data == {}

    def test_init_with_empty_pyproject(self, tmp_path: Path) -> None:
        """Test __init__ with empty pyproject.toml file."""
        toml_file = tmp_path / 'pyproject.toml'
        toml_file.write_text('')

        class Settings(BaseSettings):
            app_name: str = 'default'

        source = PyprojectTomlConfigSettingsSource(Settings, toml_file=toml_file)

        assert source.toml_data == {}

    def test_init_with_pyproject_toml_depth(self, tmp_path: Path) -> None:
        """Test __init__ respects pyproject_toml_depth configuration."""
        parent_toml_content = """
[tool.pydantic-settings]
app_name = "ParentApp"
"""
        parent_toml = tmp_path / 'pyproject.toml'
        parent_toml.write_text(parent_toml_content)

        subdir = tmp_path / 'subdir'
        subdir.mkdir()

        class Settings(BaseSettings):
            model_config = {'pyproject_toml_depth': 1}
            app_name: str = 'default'

        with patch.object(Path, 'cwd', return_value=subdir):
            source = PyprojectTomlConfigSettingsSource(Settings, toml_file=None)

        assert source.toml_data == {'app_name': 'ParentApp'}

    def test_init_with_nested_table_header(self, tmp_path: Path) -> None:
        """Test __init__ navigates through multiple nested keys."""
        toml_content = """
[tool.my-app.sub.config]
setting = "nested_value"
"""
        toml_file = tmp_path / 'pyproject.toml'
        toml_file.write_text(toml_content)

        class Settings(BaseSettings):
            model_config = {'pyproject_toml_table_header': ('tool', 'my-app', 'sub', 'config')}
            setting: str = 'default'

        source = PyprojectTomlConfigSettingsSource(Settings, toml_file=toml_file)

        assert source.toml_data == {'setting': 'nested_value'}

    def test_pick_pyproject_toml_file_stops_at_root(self) -> None:
        """Test _pick_pyproject_toml_file breaks out of loop when reaching root."""
        # Use a path close to root to force the root detection logic
        # We use /tmp as our 'cwd' and set a high depth that exceeds hierarchy
        mock_cwd = Path('/tmp/a/b')

        with patch.object(Path, 'cwd', return_value=mock_cwd):
            # With very high depth, it should traverse up and hit root detection
            result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(None, 100)

        # Should return the default path since no pyproject.toml exists
        assert result == mock_cwd / 'pyproject.toml'

    def test_pick_pyproject_toml_file_iterates_multiple_parents(self, tmp_path: Path) -> None:
        """Test _pick_pyproject_toml_file iterates through multiple parent directories."""
        # Create a deep directory structure
        deep_dir = tmp_path / 'a' / 'b' / 'c' / 'd'
        deep_dir.mkdir(parents=True)

        # Put pyproject.toml at level 'b' (2 directories up from 'd')
        toml_file = tmp_path / 'a' / 'b' / 'pyproject.toml'
        toml_file.touch()

        with patch.object(Path, 'cwd', return_value=deep_dir):
            # First iteration checks 'c', second iteration checks 'b' where the file exists
            result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(None, 2)

        assert result == toml_file
