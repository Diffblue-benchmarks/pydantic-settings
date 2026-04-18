"""Tests for SecretsSettingsSource."""

import warnings
from pathlib import Path

import pytest

from pydantic_settings import BaseSettings
from pydantic_settings.exceptions import SettingsError
from pydantic_settings.sources.providers.secrets import SecretsSettingsSource


class SimpleSettings(BaseSettings):
    my_var: str = 'default'
    other_var: int = 0


class MultiFieldSettings(BaseSettings):
    field_a: str = 'a'
    field_b: str = 'b'


# --- __init__ tests ---


def test_init_with_secrets_dir(tmp_path):
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()
    source = SecretsSettingsSource(SimpleSettings, secrets_dir=secrets_dir)
    assert source.secrets_dir == secrets_dir


def test_init_without_secrets_dir():
    source = SecretsSettingsSource(SimpleSettings)
    assert source.secrets_dir is None


def test_init_secrets_dir_from_config():
    class ConfiguredSettings(BaseSettings):
        my_var: str = 'default'

        model_config = {'secrets_dir': '/tmp/some_dir'}

    source = SecretsSettingsSource(ConfiguredSettings)
    assert source.secrets_dir == '/tmp/some_dir'


def test_init_with_case_sensitive():
    source = SecretsSettingsSource(SimpleSettings, case_sensitive=True)
    assert source.case_sensitive is True


def test_init_with_env_prefix():
    source = SecretsSettingsSource(SimpleSettings, env_prefix='APP_')
    assert source.env_prefix == 'APP_'


def test_init_with_env_prefix_target():
    source = SecretsSettingsSource(SimpleSettings, env_prefix_target='alias')
    assert source.env_prefix_target == 'alias'


def test_init_with_env_ignore_empty():
    source = SecretsSettingsSource(SimpleSettings, env_ignore_empty=True)
    assert source.env_ignore_empty is True


def test_init_with_env_parse_none_str():
    source = SecretsSettingsSource(SimpleSettings, env_parse_none_str='null')
    assert source.env_parse_none_str == 'null'


def test_init_with_env_parse_enums():
    source = SecretsSettingsSource(SimpleSettings, env_parse_enums=True)
    assert source.env_parse_enums is True


# --- __call__ tests ---


def test_call_returns_empty_when_no_secrets_dir():
    source = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
    result = source()
    assert result == {}


def test_call_warns_when_dir_does_not_exist(tmp_path):
    missing_dir = tmp_path / 'nonexistent'
    source = SecretsSettingsSource(SimpleSettings, secrets_dir=missing_dir)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter('always')
        result = source()
    assert result == {}
    assert len(w) == 1
    assert 'does not exist' in str(w[0].message)


def test_call_returns_empty_when_all_dirs_missing(tmp_path):
    missing1 = tmp_path / 'missing1'
    missing2 = tmp_path / 'missing2'
    source = SecretsSettingsSource(SimpleSettings, secrets_dir=[missing1, missing2])
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter('always')
        result = source()
    assert result == {}
    assert len(w) == 2


def test_call_raises_error_when_path_is_file(tmp_path):
    secret_file = tmp_path / 'not_a_dir'
    secret_file.write_text('content')
    source = SecretsSettingsSource(SimpleSettings, secrets_dir=secret_file)
    with pytest.raises(SettingsError, match='secrets_dir must reference a directory'):
        source()


def test_call_reads_secret_from_file(tmp_path):
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()
    (secrets_dir / 'my_var').write_text('secret_value')
    source = SecretsSettingsSource(SimpleSettings, secrets_dir=secrets_dir)
    result = source()
    assert result['my_var'] == 'secret_value'


def test_call_with_multiple_secrets_dirs(tmp_path):
    dir1 = tmp_path / 'secrets1'
    dir1.mkdir()
    dir2 = tmp_path / 'secrets2'
    dir2.mkdir()
    (dir1 / 'my_var').write_text('value1')
    (dir2 / 'my_var').write_text('value2')
    source = SecretsSettingsSource(SimpleSettings, secrets_dir=[dir1, dir2])
    result = source()
    # Last dir wins (reversed in get_field_value)
    assert result['my_var'] == 'value2'


def test_call_with_string_secrets_dir(tmp_path):
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()
    (secrets_dir / 'my_var').write_text('from_string')
    source = SecretsSettingsSource(SimpleSettings, secrets_dir=str(secrets_dir))
    result = source()
    assert result['my_var'] == 'from_string'


def test_call_with_list_of_string_secrets_dirs(tmp_path):
    dir1 = tmp_path / 'secrets1'
    dir1.mkdir()
    (dir1 / 'my_var').write_text('list_val')
    source = SecretsSettingsSource(SimpleSettings, secrets_dir=[str(dir1)])
    result = source()
    assert result['my_var'] == 'list_val'


# --- find_case_path tests ---


def test_find_case_path_exact_match(tmp_path):
    (tmp_path / 'MY_VAR').write_text('val')
    result = SecretsSettingsSource.find_case_path(tmp_path, 'MY_VAR', case_sensitive=True)
    assert result is not None
    assert result.name == 'MY_VAR'


def test_find_case_path_case_sensitive_no_match(tmp_path):
    (tmp_path / 'my_var').write_text('val')
    result = SecretsSettingsSource.find_case_path(tmp_path, 'MY_VAR', case_sensitive=True)
    assert result is None


def test_find_case_path_case_insensitive_match(tmp_path):
    (tmp_path / 'MY_VAR').write_text('val')
    result = SecretsSettingsSource.find_case_path(tmp_path, 'my_var', case_sensitive=False)
    assert result is not None
    assert result.name == 'MY_VAR'


def test_find_case_path_no_files(tmp_path):
    result = SecretsSettingsSource.find_case_path(tmp_path, 'anything', case_sensitive=False)
    assert result is None


def test_find_case_path_exact_preferred_over_case_insensitive(tmp_path):
    (tmp_path / 'my_var').write_text('exact')
    result = SecretsSettingsSource.find_case_path(tmp_path, 'my_var', case_sensitive=False)
    assert result is not None
    assert result.name == 'my_var'


# --- get_field_value tests ---


def test_get_field_value_reads_file(tmp_path):
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()
    (secrets_dir / 'my_var').write_text('  secret_val  ')
    source = SecretsSettingsSource(SimpleSettings, secrets_dir=secrets_dir)
    source()  # populates secrets_paths
    field = SimpleSettings.model_fields['my_var']
    value, key, is_complex = source.get_field_value(field, 'my_var')
    assert value == 'secret_val'


def test_get_field_value_returns_none_when_no_file(tmp_path):
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()
    source = SecretsSettingsSource(SimpleSettings, secrets_dir=secrets_dir)
    source()  # populates secrets_paths
    field = SimpleSettings.model_fields['my_var']
    value, key, is_complex = source.get_field_value(field, 'my_var')
    assert value is None


def test_get_field_value_warns_on_directory_secret(tmp_path):
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()
    (secrets_dir / 'my_var').mkdir()  # directory instead of file
    source = SecretsSettingsSource(SimpleSettings, secrets_dir=secrets_dir)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter('always')
        source()  # populates secrets_paths
        field = SimpleSettings.model_fields['my_var']
        value, key, is_complex = source.get_field_value(field, 'my_var')
    warning_messages = [str(msg.message) for msg in w]
    assert any('found a directory instead' in msg for msg in warning_messages)
    assert value is None


def test_get_field_value_strips_whitespace(tmp_path):
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()
    (secrets_dir / 'my_var').write_text('\n  hello_world  \n')
    source = SecretsSettingsSource(SimpleSettings, secrets_dir=secrets_dir)
    source()
    field = SimpleSettings.model_fields['my_var']
    value, key, is_complex = source.get_field_value(field, 'my_var')
    assert value == 'hello_world'


def test_get_field_value_last_dir_wins(tmp_path):
    dir1 = tmp_path / 'dir1'
    dir1.mkdir()
    dir2 = tmp_path / 'dir2'
    dir2.mkdir()
    (dir1 / 'my_var').write_text('from_dir1')
    (dir2 / 'my_var').write_text('from_dir2')
    source = SecretsSettingsSource(SimpleSettings, secrets_dir=[dir1, dir2])
    source()
    field = SimpleSettings.model_fields['my_var']
    value, key, is_complex = source.get_field_value(field, 'my_var')
    assert value == 'from_dir2'


# --- __repr__ tests ---


def test_repr_with_none():
    source = SecretsSettingsSource(SimpleSettings)
    assert repr(source) == "SecretsSettingsSource(secrets_dir=None)"


def test_repr_with_path(tmp_path):
    source = SecretsSettingsSource(SimpleSettings, secrets_dir=tmp_path)
    expected = f'SecretsSettingsSource(secrets_dir={tmp_path!r})'
    assert repr(source) == expected


# --- Integration tests ---


def test_settings_with_secrets_dir(tmp_path):
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()
    (secrets_dir / 'my_var').write_text('integrated')

    s = SimpleSettings(_secrets_dir=secrets_dir)
    assert s.my_var == 'integrated'


def test_settings_with_no_matching_secret(tmp_path):
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()
    # No file matching any field
    s = SimpleSettings(_secrets_dir=secrets_dir)
    assert s.my_var == 'default'


def test_case_insensitive_secrets(tmp_path):
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir()
    (secrets_dir / 'MY_VAR').write_text('case_insensitive_val')

    s = SimpleSettings(_secrets_dir=secrets_dir, _case_sensitive=False)
    assert s.my_var == 'case_insensitive_val'
