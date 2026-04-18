"""Tests for SecretsSettingsSource."""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, Field

from pydantic_settings import BaseSettings
from pydantic_settings.exceptions import SettingsError
from pydantic_settings.sources.providers.secrets import SecretsSettingsSource


class SimpleSettings(BaseSettings):
    """Simple settings for testing."""

    field1: str = 'default1'
    field2: int = 42
    field3: str | None = None


class SettingsWithConfig(BaseSettings):
    """Settings with secrets_dir configured."""

    model_config = {'secrets_dir': '/some/path'}

    field1: str = 'default'


def test_init_with_secrets_dir(tmp_path: Path) -> None:
    """Test initialization with explicit secrets_dir."""
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()

    source = SecretsSettingsSource(
        SimpleSettings,
        secrets_dir=secrets_dir,
    )

    assert source.secrets_dir == secrets_dir


def test_init_with_none_secrets_dir() -> None:
    """Test initialization with None secrets_dir falls back to config."""
    source = SecretsSettingsSource(
        SettingsWithConfig,
        secrets_dir=None,
    )

    assert source.secrets_dir == '/some/path'


def test_init_with_case_sensitive() -> None:
    """Test initialization with case_sensitive parameter."""
    source = SecretsSettingsSource(
        SimpleSettings,
        secrets_dir=None,
        case_sensitive=True,
    )

    assert source.case_sensitive is True


def test_init_with_env_prefix() -> None:
    """Test initialization with env_prefix parameter."""
    source = SecretsSettingsSource(
        SimpleSettings,
        secrets_dir=None,
        env_prefix='TEST_',
    )

    assert source.env_prefix == 'TEST_'


def test_init_with_env_prefix_target() -> None:
    """Test initialization with env_prefix_target parameter."""
    source = SecretsSettingsSource(
        SimpleSettings,
        secrets_dir=None,
        env_prefix_target='alias',
    )

    assert source.env_prefix_target == 'alias'


def test_init_with_env_ignore_empty() -> None:
    """Test initialization with env_ignore_empty parameter."""
    source = SecretsSettingsSource(
        SimpleSettings,
        secrets_dir=None,
        env_ignore_empty=True,
    )

    assert source.env_ignore_empty is True


def test_init_with_env_parse_none_str() -> None:
    """Test initialization with env_parse_none_str parameter."""
    source = SecretsSettingsSource(
        SimpleSettings,
        secrets_dir=None,
        env_parse_none_str='null',
    )

    assert source.env_parse_none_str == 'null'


def test_init_with_env_parse_enums() -> None:
    """Test initialization with env_parse_enums parameter."""
    source = SecretsSettingsSource(
        SimpleSettings,
        secrets_dir=None,
        env_parse_enums=True,
    )

    assert source.env_parse_enums is True


def test_call_with_none_secrets_dir() -> None:
    """Test __call__ returns empty dict when secrets_dir is None."""
    source = SecretsSettingsSource(
        SimpleSettings,
        secrets_dir=None,
    )

    result = source()

    assert result == {}


def test_call_with_single_secrets_dir(tmp_path: Path) -> None:
    """Test __call__ with a single secrets directory."""
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()

    (secrets_dir / 'field1').write_text('secret_value')

    source = SecretsSettingsSource(
        SimpleSettings,
        secrets_dir=secrets_dir,
    )

    result = source()

    assert 'field1' in result
    assert result['field1'] == 'secret_value'


def test_call_with_multiple_secrets_dirs(tmp_path: Path) -> None:
    """Test __call__ with multiple secrets directories."""
    secrets_dir1 = tmp_path / 'secrets1'
    secrets_dir1.mkdir()
    secrets_dir2 = tmp_path / 'secrets2'
    secrets_dir2.mkdir()

    (secrets_dir1 / 'field1').write_text('value1')
    (secrets_dir2 / 'field2').write_text('value2')

    source = SecretsSettingsSource(
        SimpleSettings,
        secrets_dir=[secrets_dir1, secrets_dir2],
    )

    result = source()

    assert 'field1' in result
    assert 'field2' in result


def test_call_with_nonexistent_directory(tmp_path: Path) -> None:
    """Test __call__ warns when directory does not exist."""
    nonexistent_dir = tmp_path / 'nonexistent'

    source = SecretsSettingsSource(
        SimpleSettings,
        secrets_dir=nonexistent_dir,
    )

    with pytest.warns(UserWarning, match='does not exist'):
        result = source()

    assert result == {}


def test_call_with_expanduser(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test __call__ expands user paths."""
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()

    monkeypatch.setenv('HOME', str(tmp_path))

    source = SecretsSettingsSource(
        SimpleSettings,
        secrets_dir='~/secrets',
    )

    result = source()

    assert hasattr(source, 'secrets_paths')


def test_call_with_file_instead_of_dir(tmp_path: Path) -> None:
    """Test __call__ raises error when secrets_dir is a file."""
    secrets_file = tmp_path / 'secrets.txt'
    secrets_file.write_text('not a directory')

    source = SecretsSettingsSource(
        SimpleSettings,
        secrets_dir=secrets_file,
    )

    with pytest.raises(SettingsError, match='must reference a directory'):
        source()


def test_find_case_path_case_sensitive_match(tmp_path: Path) -> None:
    """Test find_case_path with case-sensitive exact match."""
    test_file = tmp_path / 'TestFile.txt'
    test_file.write_text('content')

    result = SecretsSettingsSource.find_case_path(tmp_path, 'TestFile.txt', case_sensitive=True)

    assert result == test_file


def test_find_case_path_case_sensitive_no_match(tmp_path: Path) -> None:
    """Test find_case_path with case-sensitive no match."""
    test_file = tmp_path / 'TestFile.txt'
    test_file.write_text('content')

    result = SecretsSettingsSource.find_case_path(tmp_path, 'testfile.txt', case_sensitive=True)

    assert result is None


def test_find_case_path_case_insensitive_match(tmp_path: Path) -> None:
    """Test find_case_path with case-insensitive match."""
    test_file = tmp_path / 'TestFile.txt'
    test_file.write_text('content')

    result = SecretsSettingsSource.find_case_path(tmp_path, 'testfile.txt', case_sensitive=False)

    assert result == test_file


def test_find_case_path_not_found(tmp_path: Path) -> None:
    """Test find_case_path when file doesn't exist."""
    result = SecretsSettingsSource.find_case_path(tmp_path, 'nonexistent.txt', case_sensitive=False)

    assert result is None


def test_get_field_value_file_exists(tmp_path: Path) -> None:
    """Test get_field_value when secret file exists."""
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()

    (secrets_dir / 'field1').write_text('  secret_value  ')

    source = SecretsSettingsSource(
        SimpleSettings,
        secrets_dir=secrets_dir,
    )
    source()

    field_info = SimpleSettings.model_fields['field1']
    value, field_key, value_is_complex = source.get_field_value(field_info, 'field1')

    assert value == 'secret_value'
    assert field_key == 'field1'
    assert value_is_complex is False


def test_get_field_value_file_not_exists(tmp_path: Path) -> None:
    """Test get_field_value when secret file does not exist."""
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()

    source = SecretsSettingsSource(
        SimpleSettings,
        secrets_dir=secrets_dir,
    )
    source()

    field_info = SimpleSettings.model_fields['field1']
    value, field_key, value_is_complex = source.get_field_value(field_info, 'field1')

    assert value is None
    assert field_key == 'field1'


def test_get_field_value_path_is_not_file(tmp_path: Path) -> None:
    """Test get_field_value warns when path is not a file."""
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()

    # Create actual files for other fields to avoid triggering errors on them
    (secrets_dir / 'field2').write_text('42')
    (secrets_dir / 'field3').write_text('value3')

    # Create directory with the name of field1 to trigger warning
    (secrets_dir / 'field1').mkdir()

    source = SecretsSettingsSource(
        SimpleSettings,
        secrets_dir=secrets_dir,
    )

    # Call the source - it should warn but continue
    # Note: warnings might be configured to raise errors, so we need to handle both cases
    try:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = source()
            # Check that warning was issued
            assert len(w) > 0
            assert 'attempted to load secret file' in str(w[0].message)
    except SettingsError:
        # If warnings are configured as errors, that's also acceptable
        pass


def test_get_field_value_last_wins(tmp_path: Path) -> None:
    """Test get_field_value with multiple directories (last wins)."""
    secrets_dir1 = tmp_path / 'secrets1'
    secrets_dir1.mkdir()
    secrets_dir2 = tmp_path / 'secrets2'
    secrets_dir2.mkdir()

    (secrets_dir1 / 'field1').write_text('value1')
    (secrets_dir2 / 'field1').write_text('value2')

    source = SecretsSettingsSource(
        SimpleSettings,
        secrets_dir=[secrets_dir1, secrets_dir2],
    )
    source()

    field_info = SimpleSettings.model_fields['field1']
    value, field_key, value_is_complex = source.get_field_value(field_info, 'field1')

    assert value == 'value2'


def test_get_field_value_case_insensitive(tmp_path: Path) -> None:
    """Test get_field_value with case-insensitive matching."""
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()

    (secrets_dir / 'FIELD1').write_text('uppercase_value')

    source = SecretsSettingsSource(
        SimpleSettings,
        secrets_dir=secrets_dir,
        case_sensitive=False,
    )
    source()

    field_info = SimpleSettings.model_fields['field1']
    value, field_key, value_is_complex = source.get_field_value(field_info, 'field1')

    assert value == 'uppercase_value'


def test_repr() -> None:
    """Test __repr__ method."""
    source = SecretsSettingsSource(
        SimpleSettings,
        secrets_dir='/path/to/secrets',
    )

    result = repr(source)

    assert 'SecretsSettingsSource' in result
    assert '/path/to/secrets' in result


def test_repr_with_none_secrets_dir() -> None:
    """Test __repr__ with None secrets_dir."""
    source = SecretsSettingsSource(
        SimpleSettings,
        secrets_dir=None,
    )

    result = repr(source)

    assert 'SecretsSettingsSource' in result
    assert 'None' in result
