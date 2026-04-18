"""Tests for PyprojectTomlConfigSettingsSource."""

from pathlib import Path
from unittest.mock import patch

import pytest

from pydantic_settings import BaseSettings
from pydantic_settings.sources.providers.pyproject import PyprojectTomlConfigSettingsSource


class TestPickPyprojectTomlFile:
    """Tests for _pick_pyproject_toml_file static method."""

    def test_provided_path_is_resolved(self, tmp_path):
        """When an explicit path is provided, it should be resolved."""
        provided = tmp_path / 'subdir' / '..' / 'pyproject.toml'
        result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(provided, 0)
        assert result == (tmp_path / 'pyproject.toml').resolve()

    def test_provided_path_returns_resolved_even_if_not_exists(self, tmp_path):
        """When provided path doesn't exist, it still resolves and returns it."""
        provided = tmp_path / 'nonexistent' / 'pyproject.toml'
        result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(provided, 0)
        assert result == provided.resolve()

    def test_no_provided_returns_cwd_pyproject(self, tmp_path):
        """When no path provided and cwd has pyproject.toml, return cwd/pyproject.toml."""
        pyproject = tmp_path / 'pyproject.toml'
        pyproject.touch()
        with patch.object(Path, 'cwd', return_value=tmp_path):
            result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(None, 0)
        assert result == pyproject

    def test_no_provided_no_file_returns_cwd_pyproject(self, tmp_path):
        """When no path provided and cwd has no pyproject.toml, still return cwd/pyproject.toml with depth 0."""
        with patch.object(Path, 'cwd', return_value=tmp_path):
            result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(None, 0)
        assert result == tmp_path / 'pyproject.toml'

    def test_depth_search_finds_parent_pyproject(self, tmp_path):
        """When depth > 0 and parent has pyproject.toml, it should find it."""
        # Create structure: tmp_path/pyproject.toml and tmp_path/child/
        parent_pyproject = tmp_path / 'pyproject.toml'
        parent_pyproject.touch()
        child_dir = tmp_path / 'child'
        child_dir.mkdir()

        with patch.object(Path, 'cwd', return_value=child_dir):
            result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(None, 1)
        assert result == parent_pyproject

    def test_depth_search_not_deep_enough(self, tmp_path):
        """When depth is not sufficient, return cwd/pyproject.toml (default)."""
        # Create structure: tmp_path/pyproject.toml and tmp_path/a/b/
        grandparent_pyproject = tmp_path / 'pyproject.toml'
        grandparent_pyproject.touch()
        nested_dir = tmp_path / 'a' / 'b'
        nested_dir.mkdir(parents=True)

        with patch.object(Path, 'cwd', return_value=nested_dir):
            result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(None, 1)
        # depth=1 checks one level up from parent, which is tmp_path/a/pyproject.toml
        # That doesn't exist. With depth=1, count goes 0 then stops.
        # So it returns the default cwd/pyproject.toml
        assert result == nested_dir / 'pyproject.toml'

    def test_depth_search_sufficient_depth(self, tmp_path):
        """When depth is sufficient, the grandparent pyproject.toml is found."""
        grandparent_pyproject = tmp_path / 'pyproject.toml'
        grandparent_pyproject.touch()
        nested_dir = tmp_path / 'a' / 'b'
        nested_dir.mkdir(parents=True)

        with patch.object(Path, 'cwd', return_value=nested_dir):
            result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(None, 2)
        assert result == grandparent_pyproject

    def test_depth_search_stops_at_root(self, tmp_path):
        """When traversal reaches root, stop even if depth allows more."""
        # Use a shallow directory so root is reached quickly
        with patch.object(Path, 'cwd', return_value=Path('/tmp')):
            result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(None, 100)
        # Should not crash and should return default
        assert result == Path('/tmp') / 'pyproject.toml'

    def test_cwd_file_exists_no_traversal(self, tmp_path):
        """When pyproject.toml exists in cwd, no upward traversal happens regardless of depth."""
        pyproject = tmp_path / 'pyproject.toml'
        pyproject.touch()
        child_dir = tmp_path / 'child'
        child_dir.mkdir()
        # Also place one in cwd
        cwd_pyproject = child_dir / 'pyproject.toml'
        cwd_pyproject.touch()

        with patch.object(Path, 'cwd', return_value=child_dir):
            result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(None, 5)
        # cwd's pyproject.toml exists, so it returns it directly (no upward search)
        assert result == cwd_pyproject


class TestPyprojectTomlInit:
    """Tests for PyprojectTomlConfigSettingsSource.__init__."""

    def test_init_with_valid_toml_file(self, tmp_path):
        """Test initialization with a valid pyproject.toml file containing settings."""
        toml_content = b'[tool.pydantic-settings]\napp_name = "test_app"\n'
        toml_file = tmp_path / 'pyproject.toml'
        toml_file.write_bytes(toml_content)

        class MySettings(BaseSettings):
            app_name: str = 'default'

        source = PyprojectTomlConfigSettingsSource(MySettings, toml_file=toml_file)
        assert source.toml_file_path == toml_file.resolve()
        assert source.toml_table_header == ('tool', 'pydantic-settings')
        assert source.toml_data == {'app_name': 'test_app'}

    def test_init_with_custom_table_header(self, tmp_path):
        """Test initialization with a custom pyproject_toml_table_header."""
        toml_content = b'[tool.myapp]\nvalue = "hello"\n'
        toml_file = tmp_path / 'pyproject.toml'
        toml_file.write_bytes(toml_content)

        class MySettings(BaseSettings):
            model_config = {'pyproject_toml_table_header': ('tool', 'myapp')}
            value: str = 'default'

        source = PyprojectTomlConfigSettingsSource(MySettings, toml_file=toml_file)
        assert source.toml_table_header == ('tool', 'myapp')
        assert source.toml_data == {'value': 'hello'}

    def test_init_with_missing_table_header(self, tmp_path):
        """Test initialization when the table header doesn't exist in the TOML file."""
        toml_content = b'[tool.other]\nfoo = "bar"\n'
        toml_file = tmp_path / 'pyproject.toml'
        toml_file.write_bytes(toml_content)

        class MySettings(BaseSettings):
            app_name: str = 'default'

        source = PyprojectTomlConfigSettingsSource(MySettings, toml_file=toml_file)
        assert source.toml_data == {}

    def test_init_with_nonexistent_file(self, tmp_path):
        """Test initialization with a path that doesn't exist."""
        toml_file = tmp_path / 'nonexistent' / 'pyproject.toml'

        class MySettings(BaseSettings):
            app_name: str = 'default'

        source = PyprojectTomlConfigSettingsSource(MySettings, toml_file=toml_file)
        assert source.toml_data == {}

    def test_init_with_empty_table_header(self, tmp_path):
        """Test initialization with an empty table header (root table)."""
        toml_content = b'app_name = "root_value"\n'
        toml_file = tmp_path / 'pyproject.toml'
        toml_file.write_bytes(toml_content)

        class MySettings(BaseSettings):
            model_config = {'pyproject_toml_table_header': ()}
            app_name: str = 'default'

        source = PyprojectTomlConfigSettingsSource(MySettings, toml_file=toml_file)
        assert source.toml_table_header == ()
        assert 'app_name' in source.toml_data
        assert source.toml_data['app_name'] == 'root_value'

    def test_init_with_pyproject_toml_depth(self, tmp_path):
        """Test initialization uses pyproject_toml_depth from model_config."""
        parent_toml = tmp_path / 'pyproject.toml'
        parent_toml.write_bytes(b'[tool.pydantic-settings]\napp_name = "found"\n')
        child_dir = tmp_path / 'child'
        child_dir.mkdir()

        class MySettings(BaseSettings):
            model_config = {'pyproject_toml_depth': 1}
            app_name: str = 'default'

        with patch.object(Path, 'cwd', return_value=child_dir):
            source = PyprojectTomlConfigSettingsSource(MySettings)
        assert source.toml_data == {'app_name': 'found'}
