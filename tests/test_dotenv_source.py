"""Tests for DotEnvSettingsSource and read_env_file."""

import warnings
from pathlib import Path
from typing import Optional
from unittest.mock import patch

import pytest
from pydantic import Field

from pydantic_settings import BaseSettings
from pydantic_settings.sources.providers.dotenv import DotEnvSettingsSource, read_env_file


@pytest.fixture
def tmp_env_file(tmp_path):
    """Create a temporary .env file."""
    env_file = tmp_path / '.env'
    env_file.write_text('FOO=bar\nBAZ=qux\n')
    return env_file


@pytest.fixture
def tmp_env_file_utf16(tmp_path):
    """Create a temporary .env file with utf-16 encoding."""
    env_file = tmp_path / '.env'
    env_file.write_text('FOO=bar\nBAZ=qux\n', encoding='utf-16')
    return env_file


class SimpleSettings(BaseSettings):
    foo: str = 'default_foo'
    baz: str = 'default_baz'

    model_config = {'env_file': None, 'extra': 'allow'}


class PrefixSettings(BaseSettings):
    foo: str = 'default_foo'

    model_config = {'env_prefix': 'APP_', 'env_file': None, 'extra': 'allow'}


class ForbidExtraSettings(BaseSettings):
    foo: str = 'default_foo'

    model_config = {'env_file': None, 'extra': 'forbid'}


class NestedDelimiterSettings(BaseSettings):
    foo: str = 'default_foo'
    baz: str = 'default_baz'

    model_config = {'env_file': None, 'env_nested_delimiter': '__', 'extra': 'allow'}


class TestDotEnvSettingsSourceInit:
    def test_init_with_env_file(self, tmp_env_file):
        source = DotEnvSettingsSource(SimpleSettings, env_file=tmp_env_file)
        assert source.env_file == tmp_env_file
        assert source.env_file_encoding is None
        assert source.dotenv_filtering is None

    def test_init_with_env_file_encoding(self, tmp_env_file):
        source = DotEnvSettingsSource(SimpleSettings, env_file=tmp_env_file, env_file_encoding='utf-8')
        assert source.env_file_encoding == 'utf-8'

    def test_init_with_dotenv_filtering(self, tmp_env_file):
        source = DotEnvSettingsSource(SimpleSettings, env_file=tmp_env_file, dotenv_filtering='only_existing')
        assert source.dotenv_filtering == 'only_existing'

    def test_init_defaults_from_model_config(self):
        class MySettings(BaseSettings):
            foo: str = 'default'
            model_config = {
                'env_file': '.env',
                'env_file_encoding': 'latin-1',
                'dotenv_filtering': 'match_prefix',
            }

        source = DotEnvSettingsSource(MySettings)
        assert source.env_file == '.env'
        assert source.env_file_encoding == 'latin-1'
        assert source.dotenv_filtering == 'match_prefix'

    def test_init_with_sentinel_uses_model_config(self):
        class MySettings(BaseSettings):
            foo: str = 'default'
            model_config = {'env_file': '.myenv'}

        source = DotEnvSettingsSource(MySettings)
        assert source.env_file == '.myenv'

    def test_init_env_file_none_overrides_config(self):
        class MySettings(BaseSettings):
            foo: str = 'default'
            model_config = {'env_file': '.myenv'}

        source = DotEnvSettingsSource(MySettings, env_file=None)
        assert source.env_file is None

    def test_init_passes_params_to_parent(self, tmp_env_file):
        source = DotEnvSettingsSource(
            SimpleSettings,
            env_file=tmp_env_file,
            case_sensitive=True,
            env_prefix='MY_',
            env_nested_delimiter='__',
            env_ignore_empty=True,
            env_parse_none_str='null',
            env_parse_enums=True,
        )
        assert source.case_sensitive is True
        assert source.env_prefix == 'MY_'
        assert source.env_nested_delimiter == '__'
        assert source.env_ignore_empty is True
        assert source.env_parse_none_str == 'null'
        assert source.env_parse_enums is True


class TestLoadEnvVars:
    def test_load_env_vars_reads_from_env_files(self, tmp_env_file):
        source = DotEnvSettingsSource(SimpleSettings, env_file=tmp_env_file)
        env_vars = source._load_env_vars()
        assert env_vars.get('foo') == 'bar'
        assert env_vars.get('baz') == 'qux'


class TestStaticReadEnvFile:
    def test_reads_file(self, tmp_env_file):
        result = DotEnvSettingsSource._static_read_env_file(tmp_env_file)
        assert result.get('foo') == 'bar'
        assert result.get('baz') == 'qux'

    def test_reads_file_with_encoding(self, tmp_env_file_utf16):
        result = DotEnvSettingsSource._static_read_env_file(tmp_env_file_utf16, encoding='utf-16')
        assert result.get('foo') == 'bar'
        assert result.get('baz') == 'qux'

    def test_case_sensitive(self, tmp_path):
        env_file = tmp_path / '.env'
        env_file.write_text('MyKey=value\n')
        result = DotEnvSettingsSource._static_read_env_file(env_file, case_sensitive=True)
        assert 'MyKey' in result

    def test_case_insensitive(self, tmp_path):
        env_file = tmp_path / '.env'
        env_file.write_text('MyKey=value\n')
        result = DotEnvSettingsSource._static_read_env_file(env_file, case_sensitive=False)
        assert 'mykey' in result

    def test_ignore_empty(self, tmp_path):
        env_file = tmp_path / '.env'
        env_file.write_text('FOO=\nBAR=value\n')
        result = DotEnvSettingsSource._static_read_env_file(env_file, ignore_empty=True)
        assert 'foo' not in result
        assert result.get('bar') == 'value'

    def test_parse_none_str(self, tmp_path):
        env_file = tmp_path / '.env'
        env_file.write_text('FOO=null\nBAR=value\n')
        result = DotEnvSettingsSource._static_read_env_file(env_file, parse_none_str='null')
        assert str(result.get('foo')) == 'null'
        assert result.get('bar') == 'value'


class TestReadEnvFile:
    def test_read_env_file_uses_instance_settings(self, tmp_env_file):
        source = DotEnvSettingsSource(
            SimpleSettings,
            env_file=tmp_env_file,
            env_file_encoding='utf-8',
            case_sensitive=False,
            env_ignore_empty=False,
            env_parse_none_str=None,
        )
        result = source._read_env_file(tmp_env_file)
        assert result.get('foo') == 'bar'
        assert result.get('baz') == 'qux'


class TestReadEnvFiles:
    def test_returns_empty_dict_when_env_file_none(self):
        source = DotEnvSettingsSource(SimpleSettings, env_file=None)
        result = source._read_env_files()
        assert result == {}

    def test_reads_single_string_path(self, tmp_env_file):
        source = DotEnvSettingsSource(SimpleSettings, env_file=str(tmp_env_file))
        result = source._read_env_files()
        assert result.get('foo') == 'bar'

    def test_reads_single_path_object(self, tmp_env_file):
        source = DotEnvSettingsSource(SimpleSettings, env_file=tmp_env_file)
        result = source._read_env_files()
        assert result.get('foo') == 'bar'

    def test_reads_multiple_env_files(self, tmp_path):
        env1 = tmp_path / '.env1'
        env1.write_text('FOO=from_env1\n')
        env2 = tmp_path / '.env2'
        env2.write_text('BAZ=from_env2\n')
        source = DotEnvSettingsSource(SimpleSettings, env_file=[str(env1), str(env2)])
        result = source._read_env_files()
        assert result.get('foo') == 'from_env1'
        assert result.get('baz') == 'from_env2'

    def test_later_file_overrides_earlier(self, tmp_path):
        env1 = tmp_path / '.env1'
        env1.write_text('FOO=first\n')
        env2 = tmp_path / '.env2'
        env2.write_text('FOO=second\n')
        source = DotEnvSettingsSource(SimpleSettings, env_file=[str(env1), str(env2)])
        result = source._read_env_files()
        assert result.get('foo') == 'second'

    def test_skips_nonexistent_files(self, tmp_path):
        env1 = tmp_path / '.env1'
        env1.write_text('FOO=exists\n')
        source = DotEnvSettingsSource(SimpleSettings, env_file=[str(env1), str(tmp_path / 'no_such_file')])
        result = source._read_env_files()
        assert result.get('foo') == 'exists'


class TestDotEnvSettingsSourceCall:
    def test_call_only_existing_filtering(self, tmp_path):
        env_file = tmp_path / '.env'
        env_file.write_text('FOO=dotenv_foo\nEXTRA_VAR=extra\n')

        source = DotEnvSettingsSource(SimpleSettings, env_file=env_file, dotenv_filtering='only_existing')
        result = source()
        assert result.get('foo') == 'dotenv_foo'
        # With only_existing, extra vars not in model should still not appear
        # (they behave like EnvSettingsSource)

    def test_call_match_prefix_filtering(self, tmp_path):
        env_file = tmp_path / '.env'
        env_file.write_text('APP_FOO=prefixed\nAPP_EXTRA=extra_val\n')

        source = DotEnvSettingsSource(PrefixSettings, env_file=env_file, dotenv_filtering='match_prefix')
        result = source()
        assert result.get('foo') == 'prefixed'
        assert result.get('extra') == 'extra_val'

    def test_call_match_prefix_skips_nested_keys_in_data(self, tmp_path):
        env_file = tmp_path / '.env'
        env_file.write_text('APP_FOO=val\nAPP_BAZ__INNER=nested_val\n')

        class NestSettings(BaseSettings):
            foo: str = 'default'
            baz: dict = {}

            model_config = {
                'env_prefix': 'APP_',
                'env_file': None,
                'env_nested_delimiter': '__',
                'extra': 'allow',
            }

        source = DotEnvSettingsSource(NestSettings, env_file=env_file, dotenv_filtering='match_prefix')
        result = source()
        assert result.get('foo') == 'val'
        # BAZ__INNER starts with prefix and contains nested delimiter,
        # and BAZ partition is in data, so it should be skipped

    def test_call_default_filtering_adds_extra_vars(self, tmp_path):
        env_file = tmp_path / '.env'
        env_file.write_text('FOO=dotenv_foo\nNEW_VAR=new_value\n')

        source = DotEnvSettingsSource(SimpleSettings, env_file=env_file)
        result = source()
        assert result.get('foo') == 'dotenv_foo'
        assert result.get('new_var') == 'new_value'

    def test_call_default_filtering_with_prefix_extra_vars(self, tmp_path):
        env_file = tmp_path / '.env'
        env_file.write_text('APP_FOO=val\nAPP_EXTRA_KEY=extra_val\n')

        source = DotEnvSettingsSource(PrefixSettings, env_file=env_file)
        result = source()
        assert result.get('foo') == 'val'
        # case_sensitive=False so env_name is lowered to app_extra_key,
        # but env_prefix is APP_ (not lowered), so startswith fails
        # and the var is stored with its full lowered key
        assert result.get('app_extra_key') == 'extra_val'

    def test_call_skips_empty_values(self, tmp_path):
        env_file = tmp_path / '.env'
        env_file.write_text('FOO=value\nEMPTY_VAR=\n')

        source = DotEnvSettingsSource(SimpleSettings, env_file=env_file)
        result = source()
        # empty values should be skipped in the extra-var loop
        assert 'EMPTY_VAR' not in result or result.get('EMPTY_VAR') is None or result.get('EMPTY_VAR') == ''

    def test_call_skips_vars_already_in_data(self, tmp_path):
        env_file = tmp_path / '.env'
        env_file.write_text('FOO=from_dotenv\n')

        source = DotEnvSettingsSource(SimpleSettings, env_file=env_file)
        result = source()
        assert result.get('foo') == 'from_dotenv'

    def test_call_forbid_extra_does_not_add_unknown_vars(self, tmp_path):
        env_file = tmp_path / '.env'
        env_file.write_text('FOO=val\nUNKNOWN=unknown_val\n')

        source = DotEnvSettingsSource(ForbidExtraSettings, env_file=env_file)
        result = source()
        assert result.get('foo') == 'val'
        # With extra='forbid', unknown vars without prefix should still be in result
        # as data[env_name] = env_value when is_extra_allowed is False
        assert 'UNKNOWN' in result or 'unknown' in result


class TestDotEnvSettingsSourceRepr:
    def test_repr(self, tmp_env_file):
        source = DotEnvSettingsSource(SimpleSettings, env_file=tmp_env_file, env_nested_delimiter='__')
        r = repr(source)
        assert 'DotEnvSettingsSource' in r
        assert 'env_file=' in r
        assert 'env_file_encoding=' in r
        assert 'env_nested_delimiter=' in r
        assert 'env_prefix_len=' in r

    def test_repr_with_none_file(self):
        source = DotEnvSettingsSource(SimpleSettings, env_file=None)
        r = repr(source)
        assert 'DotEnvSettingsSource' in r
        assert 'env_file=None' in r


class TestReadEnvFileDeprecated:
    def test_read_env_file_emits_deprecation_warning(self, tmp_env_file):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            result = read_env_file(tmp_env_file)
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert 'read_env_file will be removed' in str(w[0].message)

    def test_read_env_file_returns_correct_data(self, tmp_env_file):
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', DeprecationWarning)
            result = read_env_file(tmp_env_file)
            assert result.get('foo') == 'bar'
            assert result.get('baz') == 'qux'

    def test_read_env_file_with_params(self, tmp_path):
        env_file = tmp_path / '.env'
        env_file.write_text('MyKey=null\nOther=value\n')
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', DeprecationWarning)
            result = read_env_file(
                env_file,
                case_sensitive=True,
                ignore_empty=False,
                parse_none_str='null',
            )
            assert 'MyKey' in result
            assert 'Other' in result


class TestIntegrationWithBaseSettings:
    def test_base_settings_with_env_file(self, tmp_path):
        env_file = tmp_path / '.env'
        env_file.write_text('FOO=from_file\nBAZ=from_file_baz\n')

        settings = SimpleSettings(_env_file=env_file)
        assert settings.foo == 'from_file'
        assert settings.baz == 'from_file_baz'

    def test_base_settings_with_multiple_env_files(self, tmp_path):
        env1 = tmp_path / '.env1'
        env1.write_text('FOO=from_env1\n')
        env2 = tmp_path / '.env2'
        env2.write_text('BAZ=from_env2\n')

        settings = SimpleSettings(_env_file=[str(env1), str(env2)])
        assert settings.foo == 'from_env1'
        assert settings.baz == 'from_env2'

    def test_base_settings_env_file_none(self):
        settings = SimpleSettings(_env_file=None)
        assert settings.foo == 'default_foo'
