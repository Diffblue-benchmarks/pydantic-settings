from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from pydantic_settings import BaseSettings
from pydantic_settings.sources.providers.toml import (
    TomlConfigSettingsSource,
    import_toml,
)


@pytest.fixture
def temp_toml_file():
    """Fixture providing a temporary TOML file"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
        f.write('[settings]\n')
        f.write('key1 = "value1"\n')
        f.write('key2 = 42\n')
        temp_path = Path(f.name)

    yield temp_path

    temp_path.unlink()


def test_import_toml_python_311_or_later():
    """Test import_toml on Python 3.11+ using tomllib"""
    if sys.version_info < (3, 11):
        pytest.skip("Test requires Python 3.11+")

    import pydantic_settings.sources.providers.toml as toml_module
    toml_module.tomllib = None

    import_toml()

    assert toml_module.tomllib is not None


def test_import_toml_python_310_or_earlier():
    """Test import_toml on Python 3.10 or earlier using tomli"""
    if sys.version_info >= (3, 11):
        pytest.skip("Test requires Python < 3.11")

    import pydantic_settings.sources.providers.toml as toml_module
    toml_module.tomli = None

    import_toml()

    assert toml_module.tomli is not None


def test_import_toml_already_imported_python_310():
    """Test import_toml when tomli is already imported"""
    if sys.version_info >= (3, 11):
        pytest.skip("Test requires Python < 3.11")

    import pydantic_settings.sources.providers.toml as toml_module
    import tomli
    toml_module.tomli = tomli

    # Should return early without re-importing
    import_toml()

    assert toml_module.tomli is tomli


def test_import_toml_already_imported_python_311():
    """Test import_toml when tomllib is already imported"""
    if sys.version_info < (3, 11):
        pytest.skip("Test requires Python 3.11+")

    import pydantic_settings.sources.providers.toml as toml_module
    import tomllib
    toml_module.tomllib = tomllib

    # Should return early without re-importing
    import_toml()

    assert toml_module.tomllib is tomllib


def test_import_toml_missing_tomli():
    """Test import_toml raises ImportError when tomli is not installed on Python < 3.11"""
    if sys.version_info >= (3, 11):
        pytest.skip("Test requires Python < 3.11")

    import pydantic_settings.sources.providers.toml as toml_module

    with patch.dict('sys.modules', {'tomli': None}):
        toml_module.tomli = None
        with patch('builtins.__import__', side_effect=ImportError('No module named tomli')):
            with pytest.raises(ImportError, match='tomli is not installed'):
                import_toml()


def test_toml_config_settings_source_init_with_file(temp_toml_file):
    """Test TomlConfigSettingsSource initialization with explicit file path"""
    class Settings(BaseSettings):
        key1: str = 'default1'
        key2: int = 0

    source = TomlConfigSettingsSource(Settings, temp_toml_file)

    assert source.toml_file_path == temp_toml_file
    assert source.toml_data is not None


def test_toml_config_settings_source_init_with_default_path():
    """Test TomlConfigSettingsSource initialization with default path from model config"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
        f.write('[settings]\n')
        f.write('key1 = "value1"\n')
        temp_path = Path(f.name)

    try:
        class Settings(BaseSettings):
            key1: str = 'default1'

            model_config = {'toml_file': temp_path}

        from pydantic_settings.sources.types import DEFAULT_PATH
        source = TomlConfigSettingsSource(Settings, DEFAULT_PATH)

        assert source.toml_file_path == temp_path
    finally:
        temp_path.unlink()


def test_toml_config_settings_source_init_deep_merge(temp_toml_file):
    """Test TomlConfigSettingsSource initialization with deep_merge enabled"""
    class Settings(BaseSettings):
        key1: str = 'default1'
        key2: int = 0

    source = TomlConfigSettingsSource(Settings, temp_toml_file, deep_merge=True)

    assert source.toml_file_path == temp_toml_file


def test_toml_config_settings_source_read_file_python_310(temp_toml_file):
    """Test _read_file on Python 3.10 or earlier"""
    if sys.version_info >= (3, 11):
        pytest.skip("Test requires Python < 3.11")

    class Settings(BaseSettings):
        pass

    source = TomlConfigSettingsSource(Settings, temp_toml_file)
    data = source._read_file(temp_toml_file)

    assert isinstance(data, dict)
    assert 'settings' in data


def test_toml_config_settings_source_read_file_python_311(temp_toml_file):
    """Test _read_file on Python 3.11+"""
    if sys.version_info < (3, 11):
        pytest.skip("Test requires Python 3.11+")

    class Settings(BaseSettings):
        pass

    source = TomlConfigSettingsSource(Settings, temp_toml_file)
    data = source._read_file(temp_toml_file)

    assert isinstance(data, dict)
    assert 'settings' in data


def test_toml_config_settings_source_repr(temp_toml_file):
    """Test __repr__ method"""
    class Settings(BaseSettings):
        pass

    source = TomlConfigSettingsSource(Settings, temp_toml_file)

    repr_str = repr(source)

    assert 'TomlConfigSettingsSource' in repr_str
    assert str(temp_toml_file) in repr_str


def test_import_toml_early_return_when_already_loaded():
    """Test that import_toml returns early when tomli is already set (Python < 3.11 path)"""
    import pydantic_settings.sources.providers.toml as toml_module

    # Create a mock tomli module
    mock_tomli = MagicMock()
    mock_tomli.load = MagicMock()

    # Mock sys.version_info to simulate Python 3.10
    with patch.object(sys, 'version_info', (3, 10, 0)):
        # Set tomli as already loaded
        toml_module.tomli = mock_tomli

        # Call import_toml - should return early without changing tomli
        import_toml()

        # Verify tomli reference is unchanged (early return happened)
        assert toml_module.tomli is mock_tomli


def test_import_toml_successful_import_when_not_loaded():
    """Test successful import of tomli when not already imported (Python < 3.11 path)"""
    import pydantic_settings.sources.providers.toml as toml_module

    # Create a mock tomli module
    mock_tomli = MagicMock()
    mock_tomli.load = MagicMock()

    # Mock sys.version_info to simulate Python 3.10
    with patch.object(sys, 'version_info', (3, 10, 0)):
        with patch.dict('sys.modules', {'tomli': mock_tomli}):
            # Set tomli to None to force import
            toml_module.tomli = None

            # Call import_toml - should successfully import tomli
            import_toml()

            # Verify tomli was imported
            assert toml_module.tomli is not None
            assert toml_module.tomli is mock_tomli
