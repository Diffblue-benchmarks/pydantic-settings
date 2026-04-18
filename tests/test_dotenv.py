"""Tests for DotEnvSettingsSource and read_env_file in pydantic_settings."""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any, Optional

import pytest
from pydantic import Field

from pydantic_settings import BaseSettings
from pydantic_settings.sources.providers.dotenv import DotEnvSettingsSource, read_env_file
from pydantic_settings.sources.types import EnvNoneType


@pytest.fixture
def env_file(tmp_path):
    f = tmp_path / '.env'
    f.write_text('APP_HOST=localhost\nAPP_PORT=8080\nSECRET=mysecret\n')
    return f


@pytest.fixture
def env_file_unicode(tmp_path):
    f = tmp_path / '.env.unicode'
    f.write_text('GREETING=héllo\n', encoding='utf-8')
    return f


class SimpleSettings(BaseSettings):
    app_host: str = 'default_host'
    app_port: int = 0


class PrefixedSettings(BaseSettings):
    model_config = {'env_prefix': 'APP_'}

    host: str = 'default'
    port: int = 0


# ── __init__ ──────────────────────────────────────────────────────────────────


def test_init_uses_sentinel_to_pick_from_model_config(tmp_path):
    env_file = tmp_path / '.env'
    env_file.write_text('APP_HOST=cfghost\n')

    class CfgSettings(BaseSettings):
        model_config = {'env_file': str(env_file)}
        app_host: str = 'x'

    src = DotEnvSettingsSource(CfgSettings)
    assert src.env_file == str(env_file)


def test_init_explicit_env_file_overrides_model_config(tmp_path):
    env_file_a = tmp_path / 'a.env'
    env_file_a.write_text('APP_HOST=ahost\n')
    env_file_b = tmp_path / 'b.env'
    env_file_b.write_text('APP_HOST=bhost\n')

    class CfgSettings(BaseSettings):
        model_config = {'env_file': str(env_file_a)}
        app_host: str = 'x'

    src = DotEnvSettingsSource(CfgSettings, env_file=str(env_file_b))
    assert src.env_file == str(env_file_b)


def test_init_env_file_none_disables_loading():
    src = DotEnvSettingsSource(SimpleSettings, env_file=None)
    assert src.env_file is None
    assert src.env_vars == {}


def test_init_env_file_encoding_from_param():
    src = DotEnvSettingsSource(SimpleSettings, env_file=None, env_file_encoding='latin-1')
    assert src.env_file_encoding == 'latin-1'


def test_init_env_file_encoding_from_model_config():
    class CfgSettings(BaseSettings):
        model_config = {'env_file_encoding': 'utf-16'}
        app_host: str = 'x'

    src = DotEnvSettingsSource(CfgSettings, env_file=None)
    assert src.env_file_encoding == 'utf-16'


def test_init_dotenv_filtering_from_param():
    src = DotEnvSettingsSource(SimpleSettings, env_file=None, dotenv_filtering='only_existing')
    assert src.dotenv_filtering == 'only_existing'


def test_init_dotenv_filtering_from_model_config():
    class CfgSettings(BaseSettings):
        model_config = {'dotenv_filtering': 'match_prefix'}
        app_host: str = 'x'

    src = DotEnvSettingsSource(CfgSettings, env_file=None)
    assert src.dotenv_filtering == 'match_prefix'


def test_init_passes_through_env_nested_delimiter():
    src = DotEnvSettingsSource(SimpleSettings, env_file=None, env_nested_delimiter='__')
    assert src.env_nested_delimiter == '__'


def test_init_passes_through_case_sensitive():
    src = DotEnvSettingsSource(SimpleSettings, env_file=None, case_sensitive=True)
    assert src.case_sensitive is True


# ── _load_env_vars ─────────────────────────────────────────────────────────────


def test_load_env_vars_returns_read_env_files(env_file):
    src = DotEnvSettingsSource(SimpleSettings, env_file=str(env_file))
    result = src._load_env_vars()
    assert 'app_host' in result


def test_load_env_vars_empty_when_no_file():
    src = DotEnvSettingsSource(SimpleSettings, env_file=None)
    assert src._load_env_vars() == {}


# ── _static_read_env_file ──────────────────────────────────────────────────────


def test_static_read_env_file_basic(env_file):
    result = DotEnvSettingsSource._static_read_env_file(env_file)
    assert result['app_host'] == 'localhost'
    assert result['app_port'] == '8080'


def test_static_read_env_file_case_insensitive_lowercases_keys(env_file):
    result = DotEnvSettingsSource._static_read_env_file(env_file, case_sensitive=False)
    assert 'app_host' in result
    assert 'APP_HOST' not in result


def test_static_read_env_file_case_sensitive_keeps_keys(env_file):
    result = DotEnvSettingsSource._static_read_env_file(env_file, case_sensitive=True)
    assert 'APP_HOST' in result


def test_static_read_env_file_ignore_empty(tmp_path):
    f = tmp_path / '.env'
    f.write_text('EMPTY=\nFULL=value\n')
    result = DotEnvSettingsSource._static_read_env_file(f, ignore_empty=True)
    assert 'empty' not in result
    assert result['full'] == 'value'


def test_static_read_env_file_parse_none_str(tmp_path):
    f = tmp_path / '.env'
    f.write_text('VAL=null\n')
    result = DotEnvSettingsSource._static_read_env_file(f, parse_none_str='null')
    assert isinstance(result['val'], EnvNoneType)


def test_static_read_env_file_unicode_encoding(env_file_unicode):
    result = DotEnvSettingsSource._static_read_env_file(env_file_unicode, encoding='utf-8')
    assert result['greeting'] == 'héllo'


# ── _read_env_file ─────────────────────────────────────────────────────────────


def test_read_env_file_delegates_to_static(env_file):
    src = DotEnvSettingsSource(SimpleSettings, env_file=str(env_file))
    result = src._read_env_file(env_file)
    assert 'app_host' in result


def test_read_env_file_uses_instance_encoding(env_file_unicode):
    src = DotEnvSettingsSource(SimpleSettings, env_file=str(env_file_unicode), env_file_encoding='utf-8')
    result = src._read_env_file(env_file_unicode)
    assert result['greeting'] == 'héllo'


# ── _read_env_files ─────────────────────────────────────────────────────────────


def test_read_env_files_returns_empty_when_env_file_is_none():
    src = DotEnvSettingsSource(SimpleSettings, env_file=None)
    assert src._read_env_files() == {}


def test_read_env_files_single_file(env_file):
    src = DotEnvSettingsSource(SimpleSettings, env_file=str(env_file))
    result = src._read_env_files()
    assert result['app_host'] == 'localhost'


def test_read_env_files_list_of_files(tmp_path):
    f1 = tmp_path / 'a.env'
    f1.write_text('KEY1=val1\n')
    f2 = tmp_path / 'b.env'
    f2.write_text('KEY2=val2\n')
    src = DotEnvSettingsSource(SimpleSettings, env_file=[str(f1), str(f2)])
    result = src._read_env_files()
    assert result['key1'] == 'val1'
    assert result['key2'] == 'val2'


def test_read_env_files_later_file_overrides_earlier(tmp_path):
    f1 = tmp_path / 'a.env'
    f1.write_text('KEY=first\n')
    f2 = tmp_path / 'b.env'
    f2.write_text('KEY=second\n')
    src = DotEnvSettingsSource(SimpleSettings, env_file=[str(f1), str(f2)])
    result = src._read_env_files()
    assert result['key'] == 'second'


def test_read_env_files_missing_file_is_skipped(tmp_path):
    real = tmp_path / 'real.env'
    real.write_text('PRESENT=yes\n')
    missing = tmp_path / 'missing.env'
    src = DotEnvSettingsSource(SimpleSettings, env_file=[str(real), str(missing)])
    result = src._read_env_files()
    assert result['present'] == 'yes'


def test_read_env_files_path_object(env_file):
    src = DotEnvSettingsSource(SimpleSettings, env_file=env_file)
    result = src._read_env_files()
    assert result['app_host'] == 'localhost'


# ── __call__ ───────────────────────────────────────────────────────────────────


def test_call_returns_known_fields(env_file):
    src = DotEnvSettingsSource(SimpleSettings, env_file=str(env_file))
    data = src()
    assert data['app_host'] == 'localhost'
    assert data['app_port'] == '8080'


def test_call_dotenv_filtering_only_existing(tmp_path):
    f = tmp_path / '.env'
    f.write_text('APP_HOST=filtered_host\nEXTRA_KEY=extra_val\n')

    class Cfg(BaseSettings):
        app_host: str = 'x'

    src = DotEnvSettingsSource(Cfg, env_file=str(f), dotenv_filtering='only_existing')
    data = src()
    assert data['app_host'] == 'filtered_host'
    assert 'extra_key' not in data


def test_call_dotenv_filtering_match_prefix(tmp_path):
    f = tmp_path / '.env'
    f.write_text('APP_HOST=prefixed_host\nAPP_EXTRA=extra_val\nNOPREFIX=nope\n')

    class Cfg(BaseSettings):
        model_config = {'env_prefix': 'APP_'}
        host: str = 'x'

    src = DotEnvSettingsSource(Cfg, env_file=str(f), dotenv_filtering='match_prefix')
    data = src()
    assert 'host' in data
    assert 'NOPREFIX' not in data and 'noprefix' not in data


def test_call_includes_extra_env_vars_without_filtering(tmp_path):
    f = tmp_path / '.env'
    f.write_text('APP_HOST=myhost\nEXTRA_CUSTOM=custom_val\n')

    class Cfg(BaseSettings):
        model_config = {'extra': 'allow'}
        app_host: str = 'x'

    src = DotEnvSettingsSource(Cfg, env_file=str(f))
    data = src()
    assert 'extra_custom' in data or 'EXTRA_CUSTOM' in data


def test_call_with_env_prefix_and_extra(tmp_path):
    f = tmp_path / '.env'
    f.write_text('APP_HOST=myhost\nAPP_EXTRA_FIELD=extra_value\n')

    class Cfg(BaseSettings):
        model_config = {'env_prefix': 'APP_', 'extra': 'allow'}
        host: str = 'x'

    src = DotEnvSettingsSource(Cfg, env_file=str(f))
    data = src()
    assert data.get('host') == 'myhost'


def test_call_no_env_file_returns_empty():
    src = DotEnvSettingsSource(SimpleSettings, env_file=None)
    data = src()
    assert data == {}


# ── __repr__ ──────────────────────────────────────────────────────────────────


def test_repr_contains_class_name(env_file):
    src = DotEnvSettingsSource(SimpleSettings, env_file=str(env_file))
    r = repr(src)
    assert 'DotEnvSettingsSource' in r


def test_repr_contains_env_file(env_file):
    src = DotEnvSettingsSource(SimpleSettings, env_file=str(env_file))
    r = repr(src)
    assert 'env_file=' in r


def test_repr_contains_env_file_encoding():
    src = DotEnvSettingsSource(SimpleSettings, env_file=None, env_file_encoding='latin-1')
    r = repr(src)
    assert 'env_file_encoding=' in r


def test_repr_contains_env_nested_delimiter():
    src = DotEnvSettingsSource(SimpleSettings, env_file=None, env_nested_delimiter='__')
    r = repr(src)
    assert 'env_nested_delimiter=' in r


def test_repr_contains_env_prefix_len():
    src = DotEnvSettingsSource(SimpleSettings, env_file=None)
    r = repr(src)
    assert 'env_prefix_len=' in r


# ── read_env_file (standalone function) ───────────────────────────────────────


def test_read_env_file_emits_deprecation_warning(env_file):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        read_env_file(env_file)
    assert any(issubclass(w.category, DeprecationWarning) for w in caught)


def test_read_env_file_deprecation_message(env_file):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        read_env_file(env_file)
    messages = [str(w.message) for w in caught if issubclass(w.category, DeprecationWarning)]
    assert any('read_env_file' in m for m in messages)


def test_read_env_file_returns_correct_values(env_file):
    with warnings.catch_warnings(record=True):
        warnings.simplefilter('always')
        result = read_env_file(env_file)
    assert result['app_host'] == 'localhost'
    assert result['app_port'] == '8080'


def test_read_env_file_case_sensitive(env_file):
    with warnings.catch_warnings(record=True):
        warnings.simplefilter('always')
        result = read_env_file(env_file, case_sensitive=True)
    assert 'APP_HOST' in result


def test_read_env_file_ignore_empty(tmp_path):
    f = tmp_path / '.env'
    f.write_text('EMPTY=\nFULL=value\n')
    with warnings.catch_warnings(record=True):
        warnings.simplefilter('always')
        result = read_env_file(f, ignore_empty=True)
    assert 'empty' not in result
    assert result['full'] == 'value'


def test_read_env_file_parse_none_str(tmp_path):
    f = tmp_path / '.env'
    f.write_text('VAL=null\n')
    with warnings.catch_warnings(record=True):
        warnings.simplefilter('always')
        result = read_env_file(f, parse_none_str='null')
    assert isinstance(result['val'], EnvNoneType)


def test_read_env_file_with_encoding(env_file_unicode):
    with warnings.catch_warnings(record=True):
        warnings.simplefilter('always')
        result = read_env_file(env_file_unicode, encoding='utf-8')
    assert result['greeting'] == 'héllo'
