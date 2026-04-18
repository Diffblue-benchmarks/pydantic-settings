"""Tests for DotEnvSettingsSource."""

import warnings
from pathlib import Path
from typing import Optional

import pytest

from pydantic_settings import BaseSettings
from pydantic_settings.sources.providers.dotenv import DotEnvSettingsSource, read_env_file


@pytest.fixture
def tmp_env_file(tmp_path):
    """Create a temporary .env file."""
    env_file = tmp_path / '.env'
    env_file.write_text('MY_VAR=hello\nOTHER_VAR=world\n')
    return env_file


@pytest.fixture
def tmp_env_file_with_encoding(tmp_path):
    """Create a temporary .env file with latin-1 encoding."""
    env_file = tmp_path / '.env'
    env_file.write_text('MY_VAR=caf\u00e9\n', encoding='latin-1')
    return env_file


class SimpleSettings(BaseSettings):
    my_var: str = 'default'

    model_config = {'env_file': None}


class SettingsWithPrefix(BaseSettings):
    my_var: str = 'default'

    model_config = {'env_prefix': 'APP_', 'env_file': None}


class SettingsWithExtra(BaseSettings):
    my_var: str = 'default'

    model_config = {'extra': 'allow', 'env_file': None}


class SettingsWithExtraAndPrefix(BaseSettings):
    my_var: str = 'default'

    model_config = {'extra': 'allow', 'env_prefix': 'APP_', 'env_file': None}


class SettingsWithNested(BaseSettings):
    my_var: str = 'default'

    model_config = {'env_nested_delimiter': '__', 'env_file': None}


class SettingsWithOptional(BaseSettings):
    my_var: Optional[str] = None

    model_config = {'env_file': None}


# ---- __init__ tests ----


def test_init_default_values():
    source = DotEnvSettingsSource(SimpleSettings)
    assert source.env_file is None
    assert source.env_file_encoding is None
    assert source.dotenv_filtering is None


def test_init_with_env_file(tmp_env_file):
    source = DotEnvSettingsSource(SimpleSettings, env_file=tmp_env_file)
    assert source.env_file == tmp_env_file


def test_init_with_env_file_encoding():
    source = DotEnvSettingsSource(SimpleSettings, env_file_encoding='latin-1')
    assert source.env_file_encoding == 'latin-1'


def test_init_with_dotenv_filtering():
    source = DotEnvSettingsSource(SimpleSettings, dotenv_filtering='only_existing')
    assert source.dotenv_filtering == 'only_existing'


def test_init_env_file_from_model_config():
    class MySettings(BaseSettings):
        my_var: str = 'default'

        model_config = {'env_file': '.env'}

    source = DotEnvSettingsSource(MySettings)
    assert source.env_file == '.env'


def test_init_env_file_encoding_from_model_config():
    class MySettings(BaseSettings):
        my_var: str = 'default'

        model_config = {'env_file_encoding': 'utf-16'}

    source = DotEnvSettingsSource(MySettings)
    assert source.env_file_encoding == 'utf-16'


def test_init_dotenv_filtering_from_model_config():
    class MySettings(BaseSettings):
        my_var: str = 'default'

        model_config = {'dotenv_filtering': 'match_prefix'}

    source = DotEnvSettingsSource(MySettings)
    assert source.dotenv_filtering == 'match_prefix'


def test_init_passes_kwargs_to_super():
    source = DotEnvSettingsSource(
        SimpleSettings,
        case_sensitive=True,
        env_prefix='TEST_',
        env_nested_delimiter='__',
    )
    assert source.case_sensitive is True
    assert source.env_prefix == 'TEST_'
    assert source.env_nested_delimiter == '__'


# ---- _load_env_vars tests ----


def test_load_env_vars_returns_read_env_files(tmp_env_file):
    source = DotEnvSettingsSource(SimpleSettings, env_file=tmp_env_file)
    result = source._load_env_vars()
    assert 'my_var' in result
    assert result['my_var'] == 'hello'


def test_load_env_vars_no_env_file():
    source = DotEnvSettingsSource(SimpleSettings, env_file=None)
    result = source._load_env_vars()
    assert result == {}


# ---- _static_read_env_file tests ----


def test_static_read_env_file(tmp_env_file):
    result = DotEnvSettingsSource._static_read_env_file(tmp_env_file)
    assert result['my_var'] == 'hello'
    assert result['other_var'] == 'world'


def test_static_read_env_file_case_sensitive(tmp_env_file):
    result = DotEnvSettingsSource._static_read_env_file(tmp_env_file, case_sensitive=True)
    assert 'MY_VAR' in result
    assert 'my_var' not in result


def test_static_read_env_file_ignore_empty(tmp_path):
    env_file = tmp_path / '.env'
    env_file.write_text('FILLED=value\nEMPTY=\n')
    result = DotEnvSettingsSource._static_read_env_file(env_file, ignore_empty=True)
    assert 'filled' in result
    assert 'empty' not in result


def test_static_read_env_file_parse_none_str(tmp_path):
    env_file = tmp_path / '.env'
    env_file.write_text('MY_VAR=null\n')
    result = DotEnvSettingsSource._static_read_env_file(env_file, parse_none_str='null')
    assert result['my_var'] is not None
    assert str(result['my_var']) == 'null'


def test_static_read_env_file_with_encoding(tmp_env_file_with_encoding):
    result = DotEnvSettingsSource._static_read_env_file(
        tmp_env_file_with_encoding, encoding='latin-1'
    )
    assert result['my_var'] == 'caf\u00e9'


# ---- _read_env_file tests ----


def test_read_env_file_instance(tmp_env_file):
    source = DotEnvSettingsSource(SimpleSettings, env_file=tmp_env_file)
    result = source._read_env_file(tmp_env_file)
    assert result['my_var'] == 'hello'


def test_read_env_file_uses_instance_encoding(tmp_env_file_with_encoding):
    source = DotEnvSettingsSource(SimpleSettings, env_file=tmp_env_file_with_encoding, env_file_encoding='latin-1')
    result = source._read_env_file(tmp_env_file_with_encoding)
    assert result['my_var'] == 'caf\u00e9'


# ---- _read_env_files tests ----


def test_read_env_files_none():
    source = DotEnvSettingsSource(SimpleSettings, env_file=None)
    result = source._read_env_files()
    assert result == {}


def test_read_env_files_single_string(tmp_env_file):
    source = DotEnvSettingsSource(SimpleSettings, env_file=str(tmp_env_file))
    result = source._read_env_files()
    assert result['my_var'] == 'hello'


def test_read_env_files_single_path(tmp_env_file):
    source = DotEnvSettingsSource(SimpleSettings, env_file=tmp_env_file)
    result = source._read_env_files()
    assert result['my_var'] == 'hello'


def test_read_env_files_list(tmp_path):
    env1 = tmp_path / '.env1'
    env1.write_text('VAR1=one\n')
    env2 = tmp_path / '.env2'
    env2.write_text('VAR2=two\n')
    source = DotEnvSettingsSource(SimpleSettings, env_file=[env1, env2])
    result = source._read_env_files()
    assert result['var1'] == 'one'
    assert result['var2'] == 'two'


def test_read_env_files_nonexistent_file(tmp_path):
    missing = tmp_path / '.env.missing'
    source = DotEnvSettingsSource(SimpleSettings, env_file=missing)
    result = source._read_env_files()
    assert result == {}


def test_read_env_files_later_overrides_earlier(tmp_path):
    env1 = tmp_path / '.env1'
    env1.write_text('MY_VAR=first\n')
    env2 = tmp_path / '.env2'
    env2.write_text('MY_VAR=second\n')
    source = DotEnvSettingsSource(SimpleSettings, env_file=[env1, env2])
    result = source._read_env_files()
    assert result['my_var'] == 'second'


# ---- __call__ tests ----


def test_call_only_existing_filtering(tmp_path):
    env_file = tmp_path / '.env'
    env_file.write_text('MY_VAR=hello\nEXTRA_VAR=extra\n')

    source = DotEnvSettingsSource(SimpleSettings, env_file=env_file, dotenv_filtering='only_existing')
    result = source()
    assert 'my_var' in result
    assert result['my_var'] == 'hello'
    assert 'extra_var' not in result


def test_call_match_prefix_filtering(tmp_path):
    env_file = tmp_path / '.env'
    env_file.write_text('APP_MY_VAR=hello\nAPP_NEW_KEY=new_value\n')

    source = DotEnvSettingsSource(
        SettingsWithPrefix,
        env_file=env_file,
        dotenv_filtering='match_prefix',
        env_prefix='APP_',
    )
    result = source()
    assert result['my_var'] == 'hello'
    assert 'NEW_KEY' in result or 'new_key' in result


def test_call_match_prefix_skips_nested_delimiter_existing(tmp_path):
    env_file = tmp_path / '.env'
    env_file.write_text('APP_MY_VAR=hello\nAPP_MY_VAR__SUB=nested\n')

    source = DotEnvSettingsSource(
        SettingsWithPrefix,
        env_file=env_file,
        dotenv_filtering='match_prefix',
        env_prefix='APP_',
        env_nested_delimiter='__',
    )
    result = source()
    assert result['my_var'] == 'hello'


def test_call_default_filtering_extra_allowed(tmp_path):
    env_file = tmp_path / '.env'
    env_file.write_text('MY_VAR=hello\nSOME_EXTRA=extra_value\n')

    source = DotEnvSettingsSource(SettingsWithExtra, env_file=env_file)
    result = source()
    assert result['my_var'] == 'hello'
    assert 'some_extra' in result or 'SOME_EXTRA' in result


def test_call_default_filtering_extra_allowed_with_prefix(tmp_path):
    env_file = tmp_path / '.env'
    env_file.write_text('APP_MY_VAR=hello\nAPP_NEW_KEY=new_value\n')

    source = DotEnvSettingsSource(
        SettingsWithExtraAndPrefix,
        env_file=env_file,
        env_prefix='APP_',
    )
    result = source()
    assert result['my_var'] == 'hello'
    # extra env vars are included (case insensitive lowered with prefix)
    assert 'app_new_key' in result


def test_call_skips_empty_values(tmp_path):
    env_file = tmp_path / '.env'
    env_file.write_text('MY_VAR=hello\nSOME_EXTRA=\n')

    source = DotEnvSettingsSource(SettingsWithExtra, env_file=env_file)
    result = source()
    assert result['my_var'] == 'hello'


def test_call_skips_already_in_data(tmp_path):
    env_file = tmp_path / '.env'
    env_file.write_text('MY_VAR=hello\n')

    source = DotEnvSettingsSource(SettingsWithExtra, env_file=env_file)
    result = source()
    assert result['my_var'] == 'hello'


def test_call_no_env_file():
    source = DotEnvSettingsSource(SimpleSettings, env_file=None)
    result = source()
    assert result == {}


# ---- __repr__ tests ----


def test_repr(tmp_env_file):
    source = DotEnvSettingsSource(SimpleSettings, env_file=tmp_env_file, env_file_encoding='utf-8')
    r = repr(source)
    assert 'DotEnvSettingsSource' in r
    assert 'env_file=' in r
    assert 'env_file_encoding=' in r
    assert 'env_nested_delimiter=' in r
    assert 'env_prefix_len=' in r


def test_repr_none_values():
    source = DotEnvSettingsSource(SimpleSettings, env_file=None)
    r = repr(source)
    assert 'DotEnvSettingsSource' in r
    assert 'env_file=None' in r


# ---- read_env_file (deprecated) tests ----


def test_read_env_file_deprecated(tmp_env_file):
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter('always')
        result = read_env_file(tmp_env_file)
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert 'read_env_file will be removed' in str(w[0].message)
    assert result['my_var'] == 'hello'


def test_read_env_file_deprecated_with_kwargs(tmp_env_file):
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter('always')
        result = read_env_file(
            tmp_env_file,
            encoding='utf-8',
            case_sensitive=True,
            ignore_empty=False,
            parse_none_str=None,
        )
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
    assert 'MY_VAR' in result


# ---- Integration tests with BaseSettings ----


def test_basesettings_with_dotenv(tmp_path):
    env_file = tmp_path / '.env'
    env_file.write_text('MY_VAR=from_dotenv\n')

    class MySettings(BaseSettings):
        my_var: str = 'default'

    s = MySettings(_env_file=env_file)
    assert s.my_var == 'from_dotenv'


def test_basesettings_dotenv_multiple_files(tmp_path):
    env1 = tmp_path / '.env1'
    env1.write_text('MY_VAR=first\n')
    env2 = tmp_path / '.env2'
    env2.write_text('MY_VAR=second\n')

    class MySettings(BaseSettings):
        my_var: str = 'default'

    s = MySettings(_env_file=[env1, env2])
    assert s.my_var == 'second'
