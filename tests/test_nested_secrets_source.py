"""Tests for NestedSecretsSettingsSource."""

import os
import warnings
from pathlib import Path

import pytest

from pydantic_settings import BaseSettings
from pydantic_settings.exceptions import SettingsError
from pydantic_settings.sources.providers.nested_secrets import (
    NestedSecretsSettingsSource,
    first_not_none,
)
from pydantic_settings.sources.providers.secrets import SecretsSettingsSource


class SimpleSettings(BaseSettings):
    my_var: str = 'default'
    other_var: int = 0


class PrefixedSettings(BaseSettings):
    model_config = {'env_prefix': 'APP_'}

    my_var: str = 'default'


class NestedDelimSettings(BaseSettings):
    model_config = {'secrets_nested_delimiter': '__'}

    my_var: str = 'default'


class CaseSensitiveSettings(BaseSettings):
    model_config = {'case_sensitive': True}

    my_var: str = 'default'


class SecretsCaseSensitiveSettings(BaseSettings):
    model_config = {'secrets_case_sensitive': True}

    my_var: str = 'default'


class SecretsPrefixSettings(BaseSettings):
    model_config = {'secrets_prefix': 'SECRET_'}

    my_var: str = 'default'


class SecretsDirMissingOkSettings(BaseSettings):
    model_config = {'secrets_dir_missing': 'ok'}

    my_var: str = 'default'


class SecretsDirMissingErrorSettings(BaseSettings):
    model_config = {'secrets_dir_missing': 'error'}

    my_var: str = 'default'


class SecretsDirMaxSizeSettings(BaseSettings):
    model_config = {'secrets_dir_max_size': 10}

    my_var: str = 'default'


class NestedSubdirSettings(BaseSettings):
    model_config = {'secrets_nested_subdir': True}

    my_var: str = 'default'


# --- first_not_none tests ---


def test_first_not_none_returns_first():
    assert first_not_none(1, 2, 3) == 1


def test_first_not_none_skips_none():
    assert first_not_none(None, None, 42) == 42


def test_first_not_none_all_none():
    assert first_not_none(None, None) is None


def test_first_not_none_empty():
    assert first_not_none() is None


def test_first_not_none_false_not_skipped():
    assert first_not_none(None, False, True) is False


def test_first_not_none_empty_string_not_skipped():
    assert first_not_none(None, '', 'hello') == ''


# --- __init__ tests with settings_cls directly ---


def test_init_with_settings_cls_no_secrets_dir():
    source = NestedSecretsSettingsSource(SimpleSettings)
    assert source.secrets_dir is None
    assert source.env_vars == {}


def test_init_with_secrets_dir(tmp_path):
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()
    source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir=secrets_dir)
    assert source.secrets_dir == secrets_dir
    assert source.secrets_paths == [secrets_dir.resolve()]


def test_init_with_string_secrets_dir(tmp_path):
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()
    source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir=str(secrets_dir))
    assert source.secrets_dir == str(secrets_dir)
    assert len(source.secrets_paths) == 1


def test_init_with_list_secrets_dir(tmp_path):
    dir1 = tmp_path / 'dir1'
    dir1.mkdir()
    dir2 = tmp_path / 'dir2'
    dir2.mkdir()
    source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir=[dir1, dir2])
    assert len(source.secrets_paths) == 2


# --- __init__ with SecretsSettingsSource ---


def test_init_with_secrets_settings_source(tmp_path):
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()
    file_secret_source = SecretsSettingsSource(SimpleSettings, secrets_dir=secrets_dir)
    source = NestedSecretsSettingsSource(file_secret_source)
    assert source.secrets_dir == secrets_dir


# --- config resolution tests ---


def test_init_secrets_dir_missing_warn_default(tmp_path):
    missing_dir = tmp_path / 'nonexistent'
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter('always')
        source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir=missing_dir)
    assert source.secrets_dir_missing == 'warn'
    assert len(w) == 1
    assert 'does not exist' in str(w[0].message)


def test_init_secrets_dir_missing_ok(tmp_path):
    missing_dir = tmp_path / 'nonexistent'
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter('always')
        source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir=missing_dir, secrets_dir_missing='ok')
    assert source.secrets_dir_missing == 'ok'
    assert len(w) == 0


def test_init_secrets_dir_missing_error(tmp_path):
    missing_dir = tmp_path / 'nonexistent'
    with pytest.raises(SettingsError, match='does not exist'):
        NestedSecretsSettingsSource(SimpleSettings, secrets_dir=missing_dir, secrets_dir_missing='error')


def test_init_secrets_dir_missing_from_config(tmp_path):
    missing_dir = tmp_path / 'nonexistent'
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter('always')
        source = NestedSecretsSettingsSource(SecretsDirMissingOkSettings, secrets_dir=missing_dir)
    assert source.secrets_dir_missing == 'ok'
    assert len(w) == 0


def test_init_invalid_secrets_dir_missing():
    with pytest.raises(SettingsError, match='invalid secrets_dir_missing value'):
        NestedSecretsSettingsSource(SimpleSettings, secrets_dir_missing='invalid')  # type: ignore[arg-type]


def test_init_secrets_dir_max_size_default():
    source = NestedSecretsSettingsSource(SimpleSettings)
    assert source.secrets_dir_max_size == 16 * 2**20


def test_init_secrets_dir_max_size_override(tmp_path):
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()
    source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir=secrets_dir, secrets_dir_max_size=1024)
    assert source.secrets_dir_max_size == 1024


def test_init_case_sensitive_from_arg(tmp_path):
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()
    source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir=secrets_dir, secrets_case_sensitive=True)
    assert source.case_sensitive is True


def test_init_case_sensitive_from_config(tmp_path):
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()
    source = NestedSecretsSettingsSource(SecretsCaseSensitiveSettings, secrets_dir=secrets_dir)
    assert source.case_sensitive is True


def test_init_case_sensitive_fallback_to_case_sensitive_arg(tmp_path):
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()
    source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir=secrets_dir, case_sensitive=True)
    assert source.case_sensitive is True


def test_init_case_sensitive_default_false(tmp_path):
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()
    source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir=secrets_dir)
    assert source.case_sensitive is False


def test_init_secrets_prefix_from_arg(tmp_path):
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()
    source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir=secrets_dir, secrets_prefix='MY_')
    assert source.secrets_prefix == 'MY_'


def test_init_secrets_prefix_from_config(tmp_path):
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()
    source = NestedSecretsSettingsSource(SecretsPrefixSettings, secrets_dir=secrets_dir)
    assert source.secrets_prefix == 'SECRET_'


def test_init_secrets_prefix_fallback_to_env_prefix(tmp_path):
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()
    source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir=secrets_dir, env_prefix='ENV_')
    assert source.secrets_prefix == 'ENV_'


def test_init_secrets_prefix_fallback_to_config_env_prefix(tmp_path):
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()
    source = NestedSecretsSettingsSource(PrefixedSettings, secrets_dir=secrets_dir)
    assert source.secrets_prefix == 'APP_'


def test_init_secrets_prefix_default_empty(tmp_path):
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()
    source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir=secrets_dir)
    assert source.secrets_prefix == ''


# --- nested options tests ---


def test_init_nested_delimiter_from_arg(tmp_path):
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()
    source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir=secrets_dir, secrets_nested_delimiter='__')
    assert source.secrets_nested_delimiter == '__'


def test_init_nested_delimiter_from_config(tmp_path):
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()
    source = NestedSecretsSettingsSource(NestedDelimSettings, secrets_dir=secrets_dir)
    assert source.secrets_nested_delimiter == '__'


def test_init_nested_subdir_sets_delimiter_to_sep(tmp_path):
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()
    source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir=secrets_dir, secrets_nested_subdir=True)
    assert source.secrets_nested_subdir is True
    assert source.secrets_nested_delimiter == os.sep


def test_init_nested_subdir_from_config(tmp_path):
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()
    source = NestedSecretsSettingsSource(NestedSubdirSettings, secrets_dir=secrets_dir)
    assert source.secrets_nested_subdir is True
    assert source.secrets_nested_delimiter == os.sep


def test_init_nested_subdir_and_delimiter_mutually_exclusive():
    with pytest.raises(SettingsError, match='mutually exclusive'):
        NestedSecretsSettingsSource(
            SimpleSettings,
            secrets_nested_delimiter='__',
            secrets_nested_subdir=True,
        )


def test_init_nested_subdir_and_config_delimiter_mutually_exclusive():
    with pytest.raises(SettingsError, match='mutually exclusive'):
        NestedSecretsSettingsSource(
            NestedDelimSettings,
            secrets_nested_subdir=True,
        )


# --- validate_secrets_path tests ---


def test_validate_path_existing_dir(tmp_path):
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()
    source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir=secrets_dir)
    assert len(source.secrets_paths) == 1


def test_validate_path_not_a_dir(tmp_path):
    secret_file = tmp_path / 'not_a_dir'
    secret_file.write_text('content')
    with pytest.raises(SettingsError, match='secrets_dir must reference a directory'):
        NestedSecretsSettingsSource(SimpleSettings, secrets_dir=secret_file, secrets_dir_missing='error')


def test_validate_path_exceeds_max_size(tmp_path):
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()
    (secrets_dir / 'big_file').write_text('x' * 100)
    with pytest.raises(SettingsError, match='secrets_dir size is above'):
        NestedSecretsSettingsSource(SimpleSettings, secrets_dir=secrets_dir, secrets_dir_max_size=10)


def test_validate_path_missing_warn(tmp_path):
    missing_dir = tmp_path / 'nonexistent'
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter('always')
        NestedSecretsSettingsSource(SimpleSettings, secrets_dir=missing_dir, secrets_dir_missing='warn')
    assert len(w) == 1
    assert 'does not exist' in str(w[0].message)


def test_validate_path_missing_error(tmp_path):
    missing_dir = tmp_path / 'nonexistent'
    with pytest.raises(SettingsError, match='does not exist'):
        NestedSecretsSettingsSource(SimpleSettings, secrets_dir=missing_dir, secrets_dir_missing='error')


# --- load_secrets tests ---


def test_load_secrets_reads_files(tmp_path):
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()
    (secrets_dir / 'key1').write_text('value1')
    (secrets_dir / 'key2').write_text('  value2  ')
    result = NestedSecretsSettingsSource.load_secrets(secrets_dir)
    assert result['key1'] == 'value1'
    assert result['key2'] == 'value2'


def test_load_secrets_recursive(tmp_path):
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()
    subdir = secrets_dir / 'sub'
    subdir.mkdir()
    (subdir / 'nested_key').write_text('nested_value')
    result = NestedSecretsSettingsSource.load_secrets(secrets_dir)
    expected_key = str(Path('sub') / 'nested_key')
    assert result[expected_key] == 'nested_value'


def test_load_secrets_empty_dir(tmp_path):
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()
    result = NestedSecretsSettingsSource.load_secrets(secrets_dir)
    assert result == {}


# --- __repr__ tests ---


def test_repr_with_none():
    source = NestedSecretsSettingsSource(SimpleSettings)
    assert repr(source) == "NestedSecretsSettingsSource(secrets_dir=None)"


def test_repr_with_path(tmp_path):
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()
    source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir=secrets_dir)
    expected = f'NestedSecretsSettingsSource(secrets_dir={secrets_dir!r})'
    assert repr(source) == expected


# --- env_vars population tests ---


def test_env_vars_populated_from_secrets(tmp_path):
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()
    (secrets_dir / 'my_var').write_text('secret_val')
    source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir=secrets_dir)
    assert source.env_vars['my_var'] == 'secret_val'


def test_env_vars_empty_when_no_paths():
    source = NestedSecretsSettingsSource(SimpleSettings)
    assert source.env_vars == {}


def test_env_vars_merged_from_multiple_dirs(tmp_path):
    dir1 = tmp_path / 'dir1'
    dir1.mkdir()
    dir2 = tmp_path / 'dir2'
    dir2.mkdir()
    (dir1 / 'key_a').write_text('val_a')
    (dir2 / 'key_b').write_text('val_b')
    source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir=[dir1, dir2])
    assert source.env_vars['key_a'] == 'val_a'
    assert source.env_vars['key_b'] == 'val_b'


def test_env_vars_last_dir_wins(tmp_path):
    dir1 = tmp_path / 'dir1'
    dir1.mkdir()
    dir2 = tmp_path / 'dir2'
    dir2.mkdir()
    (dir1 / 'my_var').write_text('from_dir1')
    (dir2 / 'my_var').write_text('from_dir2')
    source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir=[dir1, dir2])
    assert source.env_vars['my_var'] == 'from_dir2'


def test_env_vars_case_insensitive_lowered(tmp_path):
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()
    (secrets_dir / 'MY_VAR').write_text('val')
    source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir=secrets_dir)
    assert 'my_var' in source.env_vars


def test_env_vars_case_sensitive_preserves_case(tmp_path):
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()
    (secrets_dir / 'MY_VAR').write_text('val')
    source = NestedSecretsSettingsSource(SimpleSettings, secrets_dir=secrets_dir, secrets_case_sensitive=True)
    assert 'MY_VAR' in source.env_vars


def test_env_parse_none_str_set_to_none():
    source = NestedSecretsSettingsSource(SimpleSettings)
    assert source.env_parse_none_str is None
