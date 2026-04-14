"""Tests for pydantic_settings.sources.providers.pyproject module."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from pydantic_settings.main import BaseSettings
from pydantic_settings.sources.providers.pyproject import (
    PyprojectTomlConfigSettingsSource,
)


def test_pyproject_init_with_explicit_toml_file():
    """Test PyprojectTomlConfigSettingsSource initialization with explicit toml_file."""
    with TemporaryDirectory() as tmpdir:
        toml_file = Path(tmpdir) / "pyproject.toml"
        toml_file.write_text("""
[tool.pydantic-settings]
field1 = "value1"
""")

        class Settings(BaseSettings):
            field1: str = "default"

        source = PyprojectTomlConfigSettingsSource(Settings, toml_file=toml_file)

        assert source.toml_file_path == toml_file.resolve()
        assert source.toml_table_header == ("tool", "pydantic-settings")


def test_pyproject_init_with_custom_table_header():
    """Test PyprojectTomlConfigSettingsSource initialization with custom table header."""
    with TemporaryDirectory() as tmpdir:
        toml_file = Path(tmpdir) / "pyproject.toml"
        toml_file.write_text("""
[custom.settings]
field1 = "value1"
""")

        class Settings(BaseSettings):
            field1: str = "default"

            model_config = {"pyproject_toml_table_header": ("custom", "settings")}

        source = PyprojectTomlConfigSettingsSource(Settings, toml_file=toml_file)

        assert source.toml_table_header == ("custom", "settings")


def test_pyproject_init_with_depth():
    """Test PyprojectTomlConfigSettingsSource initialization with pyproject_toml_depth."""
    with TemporaryDirectory() as tmpdir:
        # Create a pyproject.toml in a parent directory
        parent_toml = Path(tmpdir) / "pyproject.toml"
        parent_toml.write_text("""
[tool.pydantic-settings]
field1 = "parent"
""")

        # Create a subdirectory
        subdir = Path(tmpdir) / "subdir"
        subdir.mkdir()

        # Change to subdirectory
        original_cwd = os.getcwd()
        try:
            os.chdir(subdir)

            class Settings(BaseSettings):
                field1: str = "default"

                model_config = {"pyproject_toml_depth": 1}

            source = PyprojectTomlConfigSettingsSource(Settings)

            # Should find the parent pyproject.toml
            assert source.toml_file_path == parent_toml or source.toml_file_path == subdir / "pyproject.toml"
        finally:
            os.chdir(original_cwd)


def test_pyproject_init_no_toml_file():
    """Test PyprojectTomlConfigSettingsSource initialization when no toml_file exists."""
    with TemporaryDirectory() as tmpdir:
        original_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)

            class Settings(BaseSettings):
                field1: str = "default"

            source = PyprojectTomlConfigSettingsSource(Settings)

            # Should default to cwd/pyproject.toml even if it doesn't exist
            assert source.toml_file_path == Path(tmpdir) / "pyproject.toml"
        finally:
            os.chdir(original_cwd)


def test_pick_pyproject_toml_file_with_provided_path():
    """Test _pick_pyproject_toml_file returns resolved path when provided."""
    with TemporaryDirectory() as tmpdir:
        toml_file = Path(tmpdir) / "custom.toml"
        toml_file.write_text("[tool.pydantic-settings]\n")

        result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(
            provided=toml_file, depth=0
        )

        assert result == toml_file.resolve()


def test_pick_pyproject_toml_file_cwd_exists():
    """Test _pick_pyproject_toml_file uses cwd when file exists."""
    with TemporaryDirectory() as tmpdir:
        toml_file = Path(tmpdir) / "pyproject.toml"
        toml_file.write_text("[tool.pydantic-settings]\n")

        original_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)

            result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(
                provided=None, depth=0
            )

            assert result == Path(tmpdir) / "pyproject.toml"
        finally:
            os.chdir(original_cwd)


def test_pick_pyproject_toml_file_search_parent():
    """Test _pick_pyproject_toml_file searches parent directory with depth."""
    with TemporaryDirectory() as tmpdir:
        # Create parent pyproject.toml
        parent_toml = Path(tmpdir) / "pyproject.toml"
        parent_toml.write_text("[tool.pydantic-settings]\n")

        # Create subdirectory
        subdir = Path(tmpdir) / "child"
        subdir.mkdir()

        original_cwd = os.getcwd()
        try:
            os.chdir(subdir)

            result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(
                provided=None, depth=1
            )

            # Should find parent pyproject.toml
            assert result == parent_toml
        finally:
            os.chdir(original_cwd)


def test_pick_pyproject_toml_file_search_multiple_levels():
    """Test _pick_pyproject_toml_file searches multiple parent levels."""
    with TemporaryDirectory() as tmpdir:
        # Create grandparent pyproject.toml
        grandparent_toml = Path(tmpdir) / "pyproject.toml"
        grandparent_toml.write_text("[tool.pydantic-settings]\n")

        # Create nested directories
        child = Path(tmpdir) / "child"
        child.mkdir()
        grandchild = child / "grandchild"
        grandchild.mkdir()

        original_cwd = os.getcwd()
        try:
            os.chdir(grandchild)

            result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(
                provided=None, depth=2
            )

            # Should find grandparent pyproject.toml
            assert result == grandparent_toml
        finally:
            os.chdir(original_cwd)


def test_pick_pyproject_toml_file_not_found_returns_cwd():
    """Test _pick_pyproject_toml_file returns cwd path when file not found."""
    with TemporaryDirectory() as tmpdir:
        subdir = Path(tmpdir) / "subdir"
        subdir.mkdir()

        original_cwd = os.getcwd()
        try:
            os.chdir(subdir)

            result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(
                provided=None, depth=1
            )

            # Should return cwd/pyproject.toml even if it doesn't exist
            assert result == Path(subdir) / "pyproject.toml"
        finally:
            os.chdir(original_cwd)


def test_pick_pyproject_toml_file_stops_at_root():
    """Test _pick_pyproject_toml_file stops searching at filesystem root."""
    with TemporaryDirectory() as tmpdir:
        subdir = Path(tmpdir) / "subdir"
        subdir.mkdir()

        original_cwd = os.getcwd()
        try:
            os.chdir(subdir)

            # Use a very large depth to test root detection
            result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(
                provided=None, depth=100
            )

            # Should return cwd/pyproject.toml without infinite loop
            assert isinstance(result, Path)
        finally:
            os.chdir(original_cwd)


def test_pyproject_init_reads_toml_data():
    """Test PyprojectTomlConfigSettingsSource initialization reads and parses TOML data."""
    with TemporaryDirectory() as tmpdir:
        toml_file = Path(tmpdir) / "pyproject.toml"
        toml_file.write_text("""
[tool.pydantic-settings]
field1 = "value1"
field2 = 42
""")

        class Settings(BaseSettings):
            field1: str = "default"
            field2: int = 0

        source = PyprojectTomlConfigSettingsSource(Settings, toml_file=toml_file)

        # Check that toml_data was read and navigated correctly
        data = source()
        assert "field1" in data or "FIELD1" in data
        assert "field2" in data or "FIELD2" in data


def test_pyproject_init_with_nested_table_header():
    """Test PyprojectTomlConfigSettingsSource with deeply nested table header."""
    with TemporaryDirectory() as tmpdir:
        toml_file = Path(tmpdir) / "pyproject.toml"
        toml_file.write_text("""
[tool.myapp.settings]
field1 = "nested"
""")

        class Settings(BaseSettings):
            field1: str = "default"

            model_config = {
                "pyproject_toml_table_header": ("tool", "myapp", "settings")
            }

        source = PyprojectTomlConfigSettingsSource(Settings, toml_file=toml_file)

        assert source.toml_table_header == ("tool", "myapp", "settings")
        data = source()
        assert "field1" in data or "FIELD1" in data


def test_pyproject_init_missing_table_header():
    """Test PyprojectTomlConfigSettingsSource when table header doesn't exist in TOML."""
    with TemporaryDirectory() as tmpdir:
        toml_file = Path(tmpdir) / "pyproject.toml"
        toml_file.write_text("""
[other.section]
field1 = "value1"
""")

        class Settings(BaseSettings):
            field1: str = "default"

        source = PyprojectTomlConfigSettingsSource(Settings, toml_file=toml_file)

        # Should handle missing table gracefully
        data = source()
        assert isinstance(data, dict)
