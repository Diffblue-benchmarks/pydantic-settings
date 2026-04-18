import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pydantic_settings import BaseSettings
from pydantic_settings.sources.providers.toml import (
    TomlConfigSettingsSource,
    import_toml,
)


def test_import_toml_python_3_11_or_higher():
    """Test import_toml for Python 3.11+."""
    if sys.version_info < (3, 11):
        pytest.skip("This test is for Python 3.11+")

    import pydantic_settings.sources.providers.toml as toml_module

    # Reset globals
    toml_module.tomllib = None

    # Import should succeed
    import_toml()

    assert toml_module.tomllib is not None


def test_import_toml_python_below_3_11_success():
    """Test import_toml for Python < 3.11 with tomli installed."""
    if sys.version_info >= (3, 11):
        pytest.skip("This test is for Python < 3.11")

    import pydantic_settings.sources.providers.toml as toml_module

    # Reset globals
    toml_module.tomli = None

    # Import should succeed with tomli installed
    import_toml()

    assert toml_module.tomli is not None


def test_import_toml_python_below_3_11_import_error():
    """Test import_toml error when tomli is not installed on Python < 3.11."""
    if sys.version_info >= (3, 11):
        pytest.skip("This test is for Python < 3.11")

    import pydantic_settings.sources.providers.toml as toml_module

    # Reset globals
    toml_module.tomli = None

    # Mock the import to raise ImportError
    with patch('builtins.__import__', side_effect=ImportError('tomli not installed')):
        with pytest.raises(ImportError, match='tomli is not installed'):
            import_toml()


def test_import_toml_already_imported():
    """Test import_toml when library is already imported."""
    import pydantic_settings.sources.providers.toml as toml_module

    if sys.version_info < (3, 11):
        # Set tomli to a dummy value
        toml_module.tomli = MagicMock()
        original_tomli = toml_module.tomli

        # Call import_toml again - it should return early
        import_toml()

        # tomli should still be the same object
        assert toml_module.tomli is original_tomli
    else:
        # Set tomllib to a dummy value
        toml_module.tomllib = MagicMock()
        original_tomllib = toml_module.tomllib

        # Call import_toml again - it should return early
        import_toml()

        # tomllib should still be the same object
        assert toml_module.tomllib is original_tomllib


class SimpleSettings(BaseSettings):
    """Simple settings for testing."""
    database_url: str = 'default'
    api_key: str = 'default_key'


def test_toml_config_settings_source_init_with_file():
    """Test initialization of TomlConfigSettingsSource with a file path."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
        f.write('[settings]\ndatabase_url = "postgres://localhost/db"\n')
        toml_file_path = Path(f.name)

    try:
        source = TomlConfigSettingsSource(
            settings_cls=SimpleSettings,
            toml_file=toml_file_path
        )

        assert source.toml_file_path == toml_file_path
        assert isinstance(source.toml_data, dict)
    finally:
        toml_file_path.unlink()


def test_toml_config_settings_source_init_with_default_path():
    """Test initialization with DEFAULT_PATH uses model_config."""
    from pydantic_settings.sources.types import DEFAULT_PATH

    with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
        f.write('[settings]\ndatabase_url = "postgres://localhost/db"\n')
        toml_file_path = Path(f.name)

    class SettingsWithConfig(BaseSettings):
        database_url: str = 'default'

        model_config = {'toml_file': toml_file_path}

    try:
        source = TomlConfigSettingsSource(
            settings_cls=SettingsWithConfig,
            toml_file=DEFAULT_PATH
        )

        assert source.toml_file_path == toml_file_path
    finally:
        toml_file_path.unlink()


def test_toml_config_settings_source_init_with_deep_merge():
    """Test initialization with deep_merge parameter."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
        f.write('[settings]\ndatabase_url = "postgres://localhost/db"\n')
        toml_file_path = Path(f.name)

    try:
        source = TomlConfigSettingsSource(
            settings_cls=SimpleSettings,
            toml_file=toml_file_path,
            deep_merge=True
        )

        assert source.toml_file_path == toml_file_path
        assert isinstance(source.toml_data, dict)
    finally:
        toml_file_path.unlink()


def test_read_file_python_3_11_or_higher():
    """Test _read_file for Python 3.11+."""
    if sys.version_info < (3, 11):
        pytest.skip("This test is for Python 3.11+")

    # Re-import to ensure clean state
    import pydantic_settings.sources.providers.toml as toml_module
    toml_module.tomllib = None
    import_toml()

    with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
        f.write('database_url = "postgres://localhost/db"\napi_key = "secret123"\n')
        toml_file_path = Path(f.name)

    try:
        source = TomlConfigSettingsSource(
            settings_cls=SimpleSettings,
            toml_file=toml_file_path
        )

        data = source._read_file(toml_file_path)

        assert isinstance(data, dict)
        assert data['database_url'] == 'postgres://localhost/db'
        assert data['api_key'] == 'secret123'
    finally:
        toml_file_path.unlink()


def test_read_file_python_below_3_11():
    """Test _read_file for Python < 3.11."""
    if sys.version_info >= (3, 11):
        pytest.skip("This test is for Python < 3.11")

    # Re-import to ensure clean state
    import pydantic_settings.sources.providers.toml as toml_module
    toml_module.tomli = None
    import_toml()

    with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
        f.write('database_url = "postgres://localhost/db"\napi_key = "secret123"\n')
        toml_file_path = Path(f.name)

    try:
        source = TomlConfigSettingsSource(
            settings_cls=SimpleSettings,
            toml_file=toml_file_path
        )

        data = source._read_file(toml_file_path)

        assert isinstance(data, dict)
        assert data['database_url'] == 'postgres://localhost/db'
        assert data['api_key'] == 'secret123'
    finally:
        toml_file_path.unlink()


def test_toml_config_settings_source_repr():
    """Test __repr__ method of TomlConfigSettingsSource."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
        f.write('[settings]\ndatabase_url = "postgres://localhost/db"\n')
        toml_file_path = Path(f.name)

    try:
        source = TomlConfigSettingsSource(
            settings_cls=SimpleSettings,
            toml_file=toml_file_path
        )

        repr_str = repr(source)

        assert 'TomlConfigSettingsSource' in repr_str
        assert str(toml_file_path) in repr_str
    finally:
        toml_file_path.unlink()
