"""Tests for SecretsSettingsSource."""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, Field
from pydantic.fields import FieldInfo

from pydantic_settings import BaseSettings
from pydantic_settings.exceptions import SettingsError
from pydantic_settings.sources.providers.secrets import SecretsSettingsSource


class SimpleSettings(BaseSettings):
    """Simple settings for testing."""

    username: str = 'default_user'
    password: str = 'default_pass'
    api_key: str | None = None


class SettingsWithConfig(BaseSettings):
    """Settings with config."""

    username: str = 'default_user'

    model_config = {'secrets_dir': '/tmp/test_secrets'}


def test_init_with_explicit_secrets_dir(tmp_path: Path) -> None:
    """Test initialization with explicit secrets_dir."""
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()

    source = SecretsSettingsSource(SimpleSettings, secrets_dir=secrets_dir)

    assert source.secrets_dir == secrets_dir
    assert source.settings_cls == SimpleSettings


def test_init_with_none_secrets_dir_uses_config() -> None:
    """Test initialization with None secrets_dir uses config value."""
    source = SecretsSettingsSource(SettingsWithConfig, secrets_dir=None)

    assert source.secrets_dir == '/tmp/test_secrets'


def test_init_with_case_sensitive() -> None:
    """Test initialization with case_sensitive parameter."""
    source = SecretsSettingsSource(SimpleSettings, secrets_dir='/tmp/secrets', case_sensitive=True)

    assert source.case_sensitive is True


def test_init_with_env_prefix() -> None:
    """Test initialization with env_prefix parameter."""
    source = SecretsSettingsSource(SimpleSettings, secrets_dir='/tmp/secrets', env_prefix='APP_')

    assert source.env_prefix == 'APP_'


def test_init_with_all_parameters(tmp_path: Path) -> None:
    """Test initialization with all parameters."""
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()

    source = SecretsSettingsSource(
        SimpleSettings,
        secrets_dir=secrets_dir,
        case_sensitive=True,
        env_prefix='TEST_',
        env_prefix_target='all',
        env_ignore_empty=True,
        env_parse_none_str='null',
        env_parse_enums=True,
    )

    assert source.secrets_dir == secrets_dir
    assert source.case_sensitive is True
    assert source.env_prefix == 'TEST_'
    assert source.env_ignore_empty is True


def test_call_with_none_secrets_dir() -> None:
    """Test __call__ returns empty dict when secrets_dir is None."""
    source = SecretsSettingsSource(SimpleSettings, secrets_dir=None)

    result = source()

    assert result == {}


def test_call_with_nonexistent_directory(tmp_path: Path) -> None:
    """Test __call__ warns when directory does not exist."""
    nonexistent_dir = tmp_path / 'nonexistent'

    source = SecretsSettingsSource(SimpleSettings, secrets_dir=nonexistent_dir)

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter('always')
        result = source()

        assert len(w) == 1
        assert 'does not exist' in str(w[0].message)
        assert result == {}


def test_call_with_multiple_dirs_some_nonexistent(tmp_path: Path) -> None:
    """Test __call__ with multiple directories where some don't exist."""
    existing_dir = tmp_path / 'existing'
    existing_dir.mkdir()
    nonexistent_dir = tmp_path / 'nonexistent'

    source = SecretsSettingsSource(SimpleSettings, secrets_dir=[existing_dir, nonexistent_dir])

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter('always')
        result = source()

        assert len(w) == 1
        assert 'does not exist' in str(w[0].message)
        assert result == {}


def test_call_with_file_instead_of_directory(tmp_path: Path) -> None:
    """Test __call__ raises error when secrets_dir is a file."""
    secrets_file = tmp_path / 'secrets.txt'
    secrets_file.write_text('secret')

    source = SecretsSettingsSource(SimpleSettings, secrets_dir=secrets_file)

    with pytest.raises(SettingsError, match='secrets_dir must reference a directory'):
        source()


def test_call_with_valid_directory(tmp_path: Path) -> None:
    """Test __call__ succeeds with valid directory."""
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()
    (secrets_dir / 'username').write_text('test_user')

    source = SecretsSettingsSource(SimpleSettings, secrets_dir=secrets_dir)

    result = source()

    assert isinstance(result, dict)


def test_call_with_list_of_directories(tmp_path: Path) -> None:
    """Test __call__ with a list of directory paths."""
    secrets_dir1 = tmp_path / 'secrets1'
    secrets_dir1.mkdir()
    secrets_dir2 = tmp_path / 'secrets2'
    secrets_dir2.mkdir()

    (secrets_dir1 / 'username').write_text('user1')
    (secrets_dir2 / 'password').write_text('pass2')

    source = SecretsSettingsSource(SimpleSettings, secrets_dir=[secrets_dir1, secrets_dir2])

    result = source()

    assert isinstance(result, dict)


def test_find_case_path_exact_match(tmp_path: Path) -> None:
    """Test find_case_path with exact filename match."""
    (tmp_path / 'username').write_text('test')

    result = SecretsSettingsSource.find_case_path(tmp_path, 'username', case_sensitive=True)

    assert result is not None
    assert result.name == 'username'


def test_find_case_path_case_insensitive_match(tmp_path: Path) -> None:
    """Test find_case_path with case-insensitive match."""
    (tmp_path / 'USERNAME').write_text('test')

    result = SecretsSettingsSource.find_case_path(tmp_path, 'username', case_sensitive=False)

    assert result is not None
    assert result.name == 'USERNAME'


def test_find_case_path_case_sensitive_no_match(tmp_path: Path) -> None:
    """Test find_case_path with case-sensitive when case doesn't match."""
    (tmp_path / 'USERNAME').write_text('test')

    result = SecretsSettingsSource.find_case_path(tmp_path, 'username', case_sensitive=True)

    assert result is None


def test_find_case_path_no_file(tmp_path: Path) -> None:
    """Test find_case_path when file doesn't exist."""
    result = SecretsSettingsSource.find_case_path(tmp_path, 'nonexistent', case_sensitive=False)

    assert result is None


def test_find_case_path_multiple_case_variants(tmp_path: Path) -> None:
    """Test find_case_path finds file when multiple case variants exist."""
    (tmp_path / 'username').write_text('exact')
    (tmp_path / 'USERNAME').write_text('upper')

    result = SecretsSettingsSource.find_case_path(tmp_path, 'username', case_sensitive=False)

    assert result is not None
    assert result.name.lower() == 'username'


def test_get_field_value_reads_secret_file(tmp_path: Path) -> None:
    """Test get_field_value reads content from secret file."""
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()
    (secrets_dir / 'username').write_text('secret_user\n')

    source = SecretsSettingsSource(SimpleSettings, secrets_dir=secrets_dir)
    source.secrets_paths = [secrets_dir]

    field_info = FieldInfo(annotation=str, default='default')
    value, key, is_complex = source.get_field_value(field_info, 'username')

    assert value == 'secret_user'
    assert is_complex is False


def test_get_field_value_file_not_found(tmp_path: Path) -> None:
    """Test get_field_value returns None when file not found."""
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()

    source = SecretsSettingsSource(SimpleSettings, secrets_dir=secrets_dir)
    source.secrets_paths = [secrets_dir]

    field_info = FieldInfo(annotation=str, default='default')
    value, key, is_complex = source.get_field_value(field_info, 'nonexistent')

    assert value is None


def test_get_field_value_directory_instead_of_file(tmp_path: Path) -> None:
    """Test get_field_value warns when finding directory instead of file."""
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()
    (secrets_dir / 'username').mkdir()

    source = SecretsSettingsSource(SimpleSettings, secrets_dir=secrets_dir)
    source.secrets_paths = [secrets_dir]

    field_info = FieldInfo(annotation=str, default='default')

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter('always')
        value, key, is_complex = source.get_field_value(field_info, 'username')

        assert len(w) == 1
        assert 'attempted to load secret file' in str(w[0].message)
        assert value is None


def test_get_field_value_last_wins(tmp_path: Path) -> None:
    """Test get_field_value uses last directory (last-wins behavior)."""
    secrets_dir1 = tmp_path / 'secrets1'
    secrets_dir1.mkdir()
    (secrets_dir1 / 'username').write_text('user1')

    secrets_dir2 = tmp_path / 'secrets2'
    secrets_dir2.mkdir()
    (secrets_dir2 / 'username').write_text('user2')

    source = SecretsSettingsSource(SimpleSettings, secrets_dir=[secrets_dir1, secrets_dir2])
    source.secrets_paths = [secrets_dir1, secrets_dir2]

    field_info = FieldInfo(annotation=str, default='default')
    value, key, is_complex = source.get_field_value(field_info, 'username')

    assert value == 'user2'


def test_get_field_value_strips_whitespace(tmp_path: Path) -> None:
    """Test get_field_value strips trailing whitespace."""
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()
    (secrets_dir / 'password').write_text('  secret_pass  \n\n')

    source = SecretsSettingsSource(SimpleSettings, secrets_dir=secrets_dir)
    source.secrets_paths = [secrets_dir]

    field_info = FieldInfo(annotation=str, default='default')
    value, key, is_complex = source.get_field_value(field_info, 'password')

    assert value == 'secret_pass'


def test_repr() -> None:
    """Test __repr__ method."""
    source = SecretsSettingsSource(SimpleSettings, secrets_dir='/tmp/secrets')

    result = repr(source)

    assert result == "SecretsSettingsSource(secrets_dir='/tmp/secrets')"


def test_repr_with_path_object(tmp_path: Path) -> None:
    """Test __repr__ with Path object."""
    secrets_dir = tmp_path / 'secrets'
    source = SecretsSettingsSource(SimpleSettings, secrets_dir=secrets_dir)

    result = repr(source)

    assert 'SecretsSettingsSource' in result
    assert 'secrets_dir=' in result
