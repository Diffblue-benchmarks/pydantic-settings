"""Tests for pydantic_settings.sources.providers.pyproject module."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from pydantic_settings import BaseSettings
from pydantic_settings.sources.providers.pyproject import PyprojectTomlConfigSettingsSource


# ── Helper to write a minimal pyproject.toml ──────────────────────────────

def _write_pyproject(path: Path, data: dict) -> Path:
    """Write a pyproject.toml file with nested dict data using tomli_w or manual TOML."""
    lines: list[str] = []
    _dict_to_toml(lines, data, prefix=())
    path.write_text('\n'.join(lines) + '\n')
    return path


def _dict_to_toml(lines: list[str], data: dict, prefix: tuple[str, ...]) -> None:
    """Minimal dict-to-TOML serialiser (flat keys + sub-tables only)."""
    simple: dict[str, object] = {}
    tables: dict[str, dict] = {}
    for k, v in data.items():
        if isinstance(v, dict):
            tables[k] = v
        else:
            simple[k] = v
    if prefix:
        header_parts = '.'.join(f'"{p}"' if '.' in p or '-' in p else p for p in prefix)
        lines.append(f'[{header_parts}]')
    for k, v in simple.items():
        if isinstance(v, str):
            lines.append(f'{k} = "{v}"')
        elif isinstance(v, (int, float)):
            lines.append(f'{k} = {v}')
        elif isinstance(v, bool):
            lines.append(f'{k} = {"true" if v else "false"}')
    for k, v in tables.items():
        _dict_to_toml(lines, v, prefix=(*prefix, k))


# ── _pick_pyproject_toml_file ─────────────────────────────────────────────


def test_pick_returns_resolved_provided_path(tmp_path):
    """When an explicit path is provided, it should be resolved and returned."""
    toml_file = tmp_path / 'custom' / 'pyproject.toml'
    toml_file.parent.mkdir(parents=True, exist_ok=True)
    toml_file.touch()
    result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(toml_file, 0)
    assert result == toml_file.resolve()
    assert result.is_absolute()


def test_pick_returns_cwd_path_when_no_provided_and_file_exists(tmp_path):
    """When no path is provided and pyproject.toml exists in cwd, return it."""
    toml_file = tmp_path / 'pyproject.toml'
    toml_file.touch()
    with patch.object(Path, 'cwd', return_value=tmp_path):
        result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(None, 0)
    assert result == toml_file


def test_pick_returns_cwd_path_when_no_file_exists_and_depth_zero(tmp_path):
    """When no path is provided and no pyproject.toml exists, return cwd-based path anyway."""
    with patch.object(Path, 'cwd', return_value=tmp_path):
        result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(None, 0)
    assert result == tmp_path / 'pyproject.toml'


def test_pick_traverses_parent_dirs_with_depth(tmp_path):
    """When depth > 0 and pyproject.toml exists in a parent, find it."""
    # Create structure: tmp_path/pyproject.toml and tmp_path/sub/child as cwd
    parent_toml = tmp_path / 'pyproject.toml'
    parent_toml.touch()
    child_dir = tmp_path / 'sub' / 'child'
    child_dir.mkdir(parents=True)
    with patch.object(Path, 'cwd', return_value=child_dir):
        result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(None, 2)
    assert result == parent_toml


def test_pick_does_not_exceed_depth(tmp_path):
    """When depth is too small to reach the parent pyproject.toml, return cwd path."""
    parent_toml = tmp_path / 'pyproject.toml'
    parent_toml.touch()
    deep_dir = tmp_path / 'a' / 'b' / 'c' / 'd'
    deep_dir.mkdir(parents=True)
    with patch.object(Path, 'cwd', return_value=deep_dir):
        result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(None, 1)
    # depth=1 should only check one parent up from cwd, not reach tmp_path
    assert result == deep_dir / 'pyproject.toml'


def test_pick_stops_at_filesystem_root(tmp_path):
    """When traversal reaches the filesystem root, stop without error."""
    # Use a dir close to root to test the root-check branch
    with patch.object(Path, 'cwd', return_value=tmp_path):
        result = PyprojectTomlConfigSettingsSource._pick_pyproject_toml_file(None, 9999)
    # Should return the cwd-based path without raising
    assert result == tmp_path / 'pyproject.toml'


# ── __init__ ──────────────────────────────────────────────────────────────


class SimplePyprojectSettings(BaseSettings):
    model_config = {
        'pyproject_toml_depth': 0,
        'pyproject_toml_table_header': ('tool', 'pydantic-settings'),
    }
    name: str = 'default'
    value: int = 0


def test_init_reads_toml_with_default_table_header(tmp_path):
    """__init__ should read settings from the default [tool.pydantic-settings] table."""
    toml_file = tmp_path / 'pyproject.toml'
    _write_pyproject(toml_file, {
        'tool': {
            'pydantic-settings': {
                'name': 'from_toml',
                'value': 99,
            }
        }
    })

    source = PyprojectTomlConfigSettingsSource(SimplePyprojectSettings, toml_file=toml_file)
    assert source.toml_file_path == toml_file.resolve()
    assert source.toml_table_header == ('tool', 'pydantic-settings')
    assert source.toml_data == {'name': 'from_toml', 'value': 99}


def test_init_with_custom_table_header(tmp_path):
    """__init__ should navigate to a custom table header."""

    class CustomHeaderSettings(BaseSettings):
        model_config = {
            'pyproject_toml_depth': 0,
            'pyproject_toml_table_header': ('tool', 'myapp'),
        }
        app_name: str = 'default'

    toml_file = tmp_path / 'pyproject.toml'
    _write_pyproject(toml_file, {
        'tool': {
            'myapp': {
                'app_name': 'custom_app',
            }
        }
    })

    source = PyprojectTomlConfigSettingsSource(CustomHeaderSettings, toml_file=toml_file)
    assert source.toml_data == {'app_name': 'custom_app'}


def test_init_missing_table_returns_empty_dict(tmp_path):
    """When the table header path doesn't exist in TOML, toml_data should be empty."""
    toml_file = tmp_path / 'pyproject.toml'
    _write_pyproject(toml_file, {
        'tool': {
            'other': {
                'key': 'val',
            }
        }
    })

    source = PyprojectTomlConfigSettingsSource(SimplePyprojectSettings, toml_file=toml_file)
    assert source.toml_data == {}


def test_init_with_nonexistent_file(tmp_path):
    """When the toml file doesn't exist, toml_data should be empty."""
    toml_file = tmp_path / 'nonexistent.toml'
    source = PyprojectTomlConfigSettingsSource(SimplePyprojectSettings, toml_file=toml_file)
    assert source.toml_data == {}


def test_init_picks_file_from_cwd_when_no_file_provided(tmp_path):
    """When no toml_file is passed, __init__ should use _pick_pyproject_toml_file."""
    toml_file = tmp_path / 'pyproject.toml'
    _write_pyproject(toml_file, {
        'tool': {
            'pydantic-settings': {
                'name': 'discovered',
                'value': 7,
            }
        }
    })

    with patch.object(Path, 'cwd', return_value=tmp_path):
        source = PyprojectTomlConfigSettingsSource(SimplePyprojectSettings)
    assert source.toml_data == {'name': 'discovered', 'value': 7}


def test_init_uses_default_table_header_when_not_in_config(tmp_path):
    """When pyproject_toml_table_header is not set in config, use default."""

    class MinimalSettings(BaseSettings):
        model_config = {'pyproject_toml_depth': 0}
        name: str = 'default'

    toml_file = tmp_path / 'pyproject.toml'
    _write_pyproject(toml_file, {
        'tool': {
            'pydantic-settings': {
                'name': 'via_default_header',
            }
        }
    })

    source = PyprojectTomlConfigSettingsSource(MinimalSettings, toml_file=toml_file)
    assert source.toml_table_header == ('tool', 'pydantic-settings')
    assert source.toml_data == {'name': 'via_default_header'}
