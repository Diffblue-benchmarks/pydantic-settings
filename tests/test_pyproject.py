"""Unit tests for PyprojectTomlConfigSettingsSource."""

from __future__ import annotations as _annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pytest
from pydantic import BaseModel, Field

from pydantic_settings import BaseSettings
from pydantic_settings.sources.providers.pyproject import PyprojectTomlConfigSettingsSource


class SimpleSettings(BaseSettings):
    """Simple test settings class for pyproject testing."""

    app_name: str | None = None
    version: str | None = None
    debug: bool = False

    model_config = {
        'pyproject_toml_table_header': ('tool', 'pydantic-settings'),
        'pyproject_toml_depth': 0,
    }


class SettingsWithCustomHeader(BaseSettings):
    """Settings with custom pyproject.toml table header."""

    database_url: str | None = None
    port: int | None = None

    model_config = {
        'pyproject_toml_table_header': ('tool', 'myapp'),
        'pyproject_toml_depth': 2,
    }


class SettingsWithoutConfig(BaseSettings):
    """Settings without pyproject config defaults."""

    value: str | None = None


class TestPyprojectTomlConfigSettingsSourceInit:
    """Tests for PyprojectTomlConfigSettingsSource.__init__."""

    def test_init_with_explicit_toml_file(self, tmp_path):
        """Test initialization with an explicitly provided pyproject.toml file."""
        # Create a temporary pyproject.toml file
        toml_file = tmp_path / 'pyproject.toml'
        toml_file.write_text(
            '[tool.pydantic-settings]\napp_name = "test-app"\nversion = "1.0"\n'
        )

        source = PyprojectTomlConfigSettingsSource(SimpleSettings, toml_file=toml_file)

        # Verify the toml_file_path is set correctly
        assert source.toml_file_path == toml_file.resolve()

    def test_init_with_default_toml_header(self, tmp_path):
        """Test initialization uses default table header from model_config."""
        toml_file = tmp_path / 'pyproject.toml'
        toml_file.write_text(
            '[tool.pydantic-settings]\napp_name = "myapp"\n'
        )

        source = PyprojectTomlConfigSettingsSource(SimpleSettings, toml_file=toml_file)

        # Verify the default table header is set
        assert source.toml_table_header == ('tool', 'pydantic-settings')

    def test_init_with_custom_toml_header(self, tmp_path):
        """Test initialization with custom table header from model_config."""
        toml_file = tmp_path / 'pyproject.toml'
        toml_file.write_text(
            '[tool.myapp]\ndatabase_url = "postgresql://localhost"\n'
        )

        source = PyprojectTomlConfigSettingsSource(
            SettingsWithCustomHeader, toml_file=toml_file
        )

        # Verify the custom table header is set
        assert source.toml_table_header == ('tool', 'myapp')

    def test_init_with_nested_table_structure(self, tmp_path):
        """Test initialization correctly reads nested TOML structure."""
        toml_file = tmp_path / 'pyproject.toml'
        toml_file.write_text(
            '[tool.pydantic-settings]\n'
            'app_name = "nested-app"\n'
            'version = "2.0"\n'
            'debug = true\n'
        )

        source = PyprojectTomlConfigSettingsSource(SimpleSettings, toml_file=toml_file)

        # Verify the TOML data is correctly parsed
        assert 'app_name' in source.toml_data
        assert source.toml_data['app_name'] == 'nested-app'
        assert source.toml_data['debug'] is True

    def test_init_with_nonexistent_toml_file(self, tmp_path):
        """Test initialization with a nonexistent pyproject.toml file."""
        nonexistent_file = tmp_path / 'nonexistent' / 'pyproject.toml'

        source = PyprojectTomlConfigSettingsSource(
            SimpleSettings, toml_file=nonexistent_file
        )

        # Should return the file path even if it doesn't exist
        assert source.toml_file_path == nonexistent_file.resolve()

    def test_init_with_empty_toml_file(self, tmp_path):
        """Test initialization with an empty pyproject.toml file."""
        toml_file = tmp_path / 'pyproject.toml'
        toml_file.write_text('')

        source = PyprojectTomlConfigSettingsSource(SimpleSettings, toml_file=toml_file)

        # Empty TOML should result in empty config section
        assert source.toml_data == {}

    def test_init_with_missing_table_header(self, tmp_path):
        """Test initialization when table header is missing from TOML."""
        toml_file = tmp_path / 'pyproject.toml'
        toml_file.write_text('[tool.other]\nvalue = "something"\n')

        source = PyprojectTomlConfigSettingsSource(SimpleSettings, toml_file=toml_file)

        # When table is missing, should result in empty data
        assert source.toml_data == {}

    def test_init_with_partial_table_header(self, tmp_path):
        """Test initialization when only partial table header exists."""
        toml_file = tmp_path / 'pyproject.toml'
        toml_file.write_text('[tool]\n')

        source = PyprojectTomlConfigSettingsSource(SimpleSettings, toml_file=toml_file)

        # When nested table is missing, should result in empty data
        assert source.toml_data == {}

    def test_init_preserves_file_path_resolution(self, tmp_path):
        """Test that initialization properly resolves relative paths."""
        toml_file = tmp_path / 'config' / 'pyproject.toml'
        toml_file.parent.mkdir(parents=True)
        toml_file.write_text('[tool.pydantic-settings]\n')

        source = PyprojectTomlConfigSettingsSource(SimpleSettings, toml_file=toml_file)

        # Path should be resolved to absolute
        assert source.toml_file_path.is_absolute()
        assert source.toml_file_path == toml_file.resolve()


class TestPickPyprojectTomlFile:
    """Tests for PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file."""

    def test_pick_with_provided_file(self, tmp_path):
        """Test picking when an explicit file path is provided."""
        provided_file = tmp_path / 'custom.toml'
        provided_file.write_text('[tool]\n')

        result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(
            provided_file, depth=0
        )

        # Should return the provided file path, resolved
        assert result == provided_file.resolve()

    def test_pick_with_none_file_and_zero_depth(self, tmp_path):
        """Test picking with None file and zero depth uses current directory."""
        # Create pyproject.toml in a temporary directory
        toml_file = tmp_path / 'pyproject.toml'
        toml_file.write_text('[tool]\n')

        # Save original cwd and change to tmp_path
        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(
                None, depth=0
            )
            # Should return pyproject.toml in current directory
            assert result.name == 'pyproject.toml'
            assert result == (tmp_path / 'pyproject.toml').resolve()
        finally:
            os.chdir(original_cwd)

    def test_pick_with_no_local_file_returns_current_path(self, tmp_path):
        """Test picking when no local file exists returns current directory path."""
        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(
                None, depth=0
            )
            # Should return the expected path even if file doesn't exist
            expected_path = (tmp_path / 'pyproject.toml').resolve()
            assert result == expected_path
        finally:
            os.chdir(original_cwd)

    def test_pick_with_depth_traversal_finds_parent_file(self, tmp_path):
        """Test picking with depth > 0 traverses parent directories."""
        # Create pyproject.toml two levels up
        parent_file = tmp_path / 'pyproject.toml'
        parent_file.write_text('[tool]\n')

        # Create nested directory structure
        nested_dir = tmp_path / 'a' / 'b'
        nested_dir.mkdir(parents=True)

        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(nested_dir)
            result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(
                None, depth=2
            )
            # Should find the file in parent directory
            assert result == parent_file.resolve()
        finally:
            os.chdir(original_cwd)

    def test_pick_with_depth_zero_no_traversal(self, tmp_path):
        """Test that depth=0 does not traverse parent directories."""
        # Create pyproject.toml in parent
        parent_file = tmp_path / 'pyproject.toml'
        parent_file.write_text('[tool]\n')

        # Create nested directory without pyproject.toml
        nested_dir = tmp_path / 'nested'
        nested_dir.mkdir()

        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(nested_dir)
            result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(
                None, depth=0
            )
            # Should return current directory path, not parent
            expected_path = (nested_dir / 'pyproject.toml').resolve()
            assert result == expected_path
        finally:
            os.chdir(original_cwd)

    def test_pick_stops_at_filesystem_root(self, tmp_path):
        """Test that traversal stops at filesystem root."""
        # Create nested directory structure
        nested_dir = tmp_path / 'a' / 'b' / 'c'
        nested_dir.mkdir(parents=True)

        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(nested_dir)
            # Use large depth to ensure it would hit root
            result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(
                None, depth=100
            )
            # Should still return a valid path
            assert isinstance(result, Path)
        finally:
            os.chdir(original_cwd)

    def test_pick_with_multiple_depth_levels(self, tmp_path):
        """Test picking with depth parameter checking multiple levels."""
        # Create files at different levels
        level0 = tmp_path / 'level0'
        level0.mkdir()
        file_at_level0 = level0 / 'pyproject.toml'
        file_at_level0.write_text('[tool]\n')

        level1 = level0 / 'a'
        level1.mkdir()

        level2 = level1 / 'b'
        level2.mkdir()

        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(level2)
            result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(
                None, depth=3
            )
            # Should find the file two levels up
            assert result == file_at_level0.resolve()
        finally:
            os.chdir(original_cwd)

    def test_pick_prefers_provided_over_search(self, tmp_path):
        """Test that provided file path takes precedence over search."""
        # Create a file in current directory
        current_file = tmp_path / 'pyproject.toml'
        current_file.write_text('[tool.a]\n')

        # Create a different file to provide
        other_file = tmp_path / 'other.toml'
        other_file.write_text('[tool.b]\n')

        result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(
            other_file, depth=0
        )

        # Should return the provided file
        assert result == other_file.resolve()
        assert result != current_file.resolve()

    def test_pick_with_symlink_file(self, tmp_path):
        """Test picking with a symlinked pyproject.toml file."""
        actual_file = tmp_path / 'actual.toml'
        actual_file.write_text('[tool]\n')

        symlink_file = tmp_path / 'pyproject.toml'
        symlink_file.symlink_to(actual_file)

        result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(
            symlink_file, depth=0
        )

        # Should resolve the symlink
        assert result == symlink_file.resolve()

    def test_pick_with_relative_provided_path(self, tmp_path):
        """Test that relative provided paths are resolved."""
        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            # Create a file
            toml_file = tmp_path / 'pyproject.toml'
            toml_file.write_text('[tool]\n')

            # Pass a relative path
            from pathlib import Path as PathlibPath
            relative_path = PathlibPath('pyproject.toml')

            result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(
                relative_path, depth=0
            )

            # Should be resolved to absolute path
            assert result.is_absolute()
            assert result == toml_file.resolve()
        finally:
            os.chdir(original_cwd)
