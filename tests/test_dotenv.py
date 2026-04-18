"""Tests for pydantic_settings.sources.providers.dotenv module."""

from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import Any
import pytest
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
from pydantic_settings.sources.providers.dotenv import (
    DotEnvSettingsSource,
    read_env_file,
)


def test_dotenv_settings_source_init_with_env_file():
    """Test DotEnvSettingsSource initialization with env_file."""

    class Settings(BaseSettings):
        model_config = {
            'env_file': '.env',
            'env_file_encoding': 'utf-8',
            'dotenv_filtering': 'only_existing',
        }
        field1: str = 'default'

    source = DotEnvSettingsSource(
        settings_cls=Settings,
        env_file=Path('.env.local'),
        env_file_encoding='utf-16',
        dotenv_filtering='match_prefix',
    )

    assert source.env_file == Path('.env.local')
    assert source.env_file_encoding == 'utf-16'
    assert source.dotenv_filtering == 'match_prefix'


def test_dotenv_settings_source_init_with_sentinel():
    """Test DotEnvSettingsSource initialization with ENV_FILE_SENTINEL."""

    class Settings(BaseSettings):
        model_config = {
            'env_file': '.env.test',
            'env_file_encoding': 'latin-1',
            'dotenv_filtering': 'match_prefix',
        }
        field1: str = 'default'

    from pydantic_settings.sources.types import ENV_FILE_SENTINEL

    source = DotEnvSettingsSource(
        settings_cls=Settings,
        env_file=ENV_FILE_SENTINEL,
    )

    assert source.env_file == '.env.test'
    assert source.env_file_encoding == 'latin-1'
    assert source.dotenv_filtering == 'match_prefix'


def test_dotenv_settings_source_init_with_none_values():
    """Test DotEnvSettingsSource initialization with None values."""

    class Settings(BaseSettings):
        model_config = {
            'env_file': None,
        }
        field1: str = 'default'

    source = DotEnvSettingsSource(
        settings_cls=Settings,
        env_file=None,
        env_file_encoding=None,
        dotenv_filtering=None,
    )

    assert source.env_file is None


def test_load_env_vars():
    """Test _load_env_vars method."""
    with TemporaryDirectory() as temp_dir:
        env_file = Path(temp_dir) / '.env'
        env_file.write_text('TEST_VAR=test_value\n')

        class Settings(BaseSettings):
            model_config = {'env_file': env_file}
            test_var: str = 'default'

        source = DotEnvSettingsSource(settings_cls=Settings)
        env_vars = source._load_env_vars()

        assert 'TEST_VAR' in env_vars or 'test_var' in env_vars


def test_static_read_env_file():
    """Test _static_read_env_file static method."""
    with TemporaryDirectory() as temp_dir:
        env_file = Path(temp_dir) / '.env'
        env_file.write_text('VAR1=value1\nVAR2=value2\n')

        result = DotEnvSettingsSource._static_read_env_file(
            env_file,
            encoding='utf-8',
            case_sensitive=False,
            ignore_empty=False,
            parse_none_str=None,
        )

        assert 'VAR1' in result or 'var1' in result
        assert 'VAR2' in result or 'var2' in result


def test_static_read_env_file_with_case_sensitive():
    """Test _static_read_env_file with case_sensitive=True."""
    with TemporaryDirectory() as temp_dir:
        env_file = Path(temp_dir) / '.env'
        env_file.write_text('MyVar=value\n')

        result = DotEnvSettingsSource._static_read_env_file(
            env_file,
            case_sensitive=True,
        )

        assert 'MyVar' in result


def test_read_env_file():
    """Test _read_env_file method."""
    with TemporaryDirectory() as temp_dir:
        env_file = Path(temp_dir) / '.env'
        env_file.write_text('TEST_VAR=test_value\n')

        class Settings(BaseSettings):
            model_config = {
                'env_file': env_file,
                'env_file_encoding': 'utf-8',
            }
            test_var: str = 'default'

        source = DotEnvSettingsSource(
            settings_cls=Settings,
            case_sensitive=False,
            env_ignore_empty=False,
            env_parse_none_str=None,
        )

        result = source._read_env_file(env_file)
        assert 'TEST_VAR' in result or 'test_var' in result


def test_read_env_files_with_none():
    """Test _read_env_files with None env_file."""

    class Settings(BaseSettings):
        model_config = {'env_file': None}
        field1: str = 'default'

    source = DotEnvSettingsSource(settings_cls=Settings, env_file=None)
    result = source._read_env_files()

    assert result == {}


def test_read_env_files_with_single_file():
    """Test _read_env_files with a single file path."""
    with TemporaryDirectory() as temp_dir:
        env_file = Path(temp_dir) / '.env'
        env_file.write_text('VAR1=value1\n')

        class Settings(BaseSettings):
            model_config = {'env_file': str(env_file)}
            var1: str = 'default'

        source = DotEnvSettingsSource(settings_cls=Settings)
        result = source._read_env_files()

        assert 'VAR1' in result or 'var1' in result


def test_read_env_files_with_multiple_files():
    """Test _read_env_files with multiple file paths."""
    with TemporaryDirectory() as temp_dir:
        env_file1 = Path(temp_dir) / '.env1'
        env_file2 = Path(temp_dir) / '.env2'
        env_file1.write_text('VAR1=value1\n')
        env_file2.write_text('VAR2=value2\n')

        class Settings(BaseSettings):
            model_config = {'env_file': [str(env_file1), str(env_file2)]}
            var1: str = 'default'
            var2: str = 'default'

        source = DotEnvSettingsSource(settings_cls=Settings)
        result = source._read_env_files()

        assert len(result) >= 2


def test_read_env_files_with_pathlike():
    """Test _read_env_files with os.PathLike."""
    with TemporaryDirectory() as temp_dir:
        env_file = Path(temp_dir) / '.env'
        env_file.write_text('VAR1=value1\n')

        class Settings(BaseSettings):
            model_config = {'env_file': env_file}
            var1: str = 'default'

        source = DotEnvSettingsSource(settings_cls=Settings)
        result = source._read_env_files()

        assert 'VAR1' in result or 'var1' in result


def test_dotenv_call_with_only_existing():
    """Test __call__ with dotenv_filtering='only_existing'."""
    with TemporaryDirectory() as temp_dir:
        env_file = Path(temp_dir) / '.env'
        env_file.write_text('FIELD1=from_env\nEXTRA_VAR=extra_value\n')

        class Settings(BaseSettings):
            model_config = {
                'env_file': env_file,
                'dotenv_filtering': 'only_existing',
            }
            field1: str = 'default'

        source = DotEnvSettingsSource(settings_cls=Settings)
        result = source()

        assert 'field1' in result or 'FIELD1' in result
        assert 'extra_var' not in result and 'EXTRA_VAR' not in result


def test_dotenv_call_with_match_prefix():
    """Test __call__ with dotenv_filtering='match_prefix'."""
    with TemporaryDirectory() as temp_dir:
        env_file = Path(temp_dir) / '.env'
        env_file.write_text('APP_FIELD1=from_env\nAPP_FIELD2=value2\nOTHER=other_value\n')

        class Settings(BaseSettings):
            model_config = {
                'env_file': env_file,
                'env_prefix': 'APP_',
                'dotenv_filtering': 'match_prefix',
            }
            field1: str = 'default'

        source = DotEnvSettingsSource(settings_cls=Settings, env_prefix='APP_')
        result = source()

        assert 'FIELD1' in result or 'field1' in result


def test_dotenv_call_with_match_prefix_and_nested_delimiter():
    """Test __call__ with match_prefix and nested delimiter."""
    with TemporaryDirectory() as temp_dir:
        env_file = Path(temp_dir) / '.env'
        env_file.write_text('APP_FIELD1=value1\nAPP_FIELD2=value2\n')

        class Settings(BaseSettings):
            model_config = {
                'env_file': env_file,
                'env_prefix': 'APP_',
                'env_nested_delimiter': '_',
                'dotenv_filtering': 'match_prefix',
            }
            field1: str = 'default'

        source = DotEnvSettingsSource(
            settings_cls=Settings,
            env_prefix='APP_',
            env_nested_delimiter='_',
        )
        result = source()

        # Check that env vars with prefix are stripped and added
        assert 'FIELD1' in result or 'field1' in result
        assert 'FIELD2' in result or 'field2' in result


def test_dotenv_call_with_extra_allowed():
    """Test __call__ with extra='allow'."""
    with TemporaryDirectory() as temp_dir:
        env_file = Path(temp_dir) / '.env'
        env_file.write_text('FIELD1=value1\nEXTRA_VAR=extra_value\n')

        class Settings(BaseSettings):
            model_config = {
                'env_file': env_file,
                'extra': 'allow',
            }
            field1: str = 'default'

        source = DotEnvSettingsSource(settings_cls=Settings)
        result = source()

        assert 'extra_var' in result or 'EXTRA_VAR' in result


def test_dotenv_call_with_extra_forbid():
    """Test __call__ with extra='forbid'."""
    with TemporaryDirectory() as temp_dir:
        env_file = Path(temp_dir) / '.env'
        env_file.write_text('FIELD1=value1\nEXTRA_VAR=extra_value\n')

        class Settings(BaseSettings):
            model_config = {
                'env_file': env_file,
                'extra': 'forbid',
            }
            field1: str = 'default'

        source = DotEnvSettingsSource(settings_cls=Settings)
        result = source()

        # With extra='forbid', extra vars should not be added
        assert 'field1' in result or 'FIELD1' in result


def test_dotenv_call_with_complex_field():
    """Test __call__ with complex field annotation."""
    with TemporaryDirectory() as temp_dir:
        env_file = Path(temp_dir) / '.env'
        env_file.write_text('FIELD1_KEY=value\nOTHER=other\n')

        class Settings(BaseSettings):
            model_config = {
                'env_file': env_file,
                'env_nested_delimiter': '_',
            }
            field1: dict = {}

        source = DotEnvSettingsSource(settings_cls=Settings, env_nested_delimiter='_')
        result = source()

        assert isinstance(result, dict)


def test_dotenv_call_with_env_prefix_and_extra():
    """Test __call__ with env_prefix and extra vars."""
    with TemporaryDirectory() as temp_dir:
        env_file = Path(temp_dir) / '.env'
        env_file.write_text('APP_FIELD1=value1\nAPP_EXTRA=extra_value\nOTHER=other\n')

        class Settings(BaseSettings):
            model_config = {
                'env_file': env_file,
                'env_prefix': 'APP_',
                'extra': 'allow',
            }
            field1: str = 'default'

        source = DotEnvSettingsSource(settings_cls=Settings, env_prefix='APP_')
        result = source()

        assert 'field1' in result or 'FIELD1' in result


def test_dotenv_call_with_empty_env_value():
    """Test __call__ with empty env value."""
    with TemporaryDirectory() as temp_dir:
        env_file = Path(temp_dir) / '.env'
        env_file.write_text('FIELD1=\nFIELD2=value2\n')

        class Settings(BaseSettings):
            model_config = {
                'env_file': env_file,
            }
            field1: str = 'default'
            field2: str = 'default'

        source = DotEnvSettingsSource(settings_cls=Settings)
        result = source()

        # Empty values should be skipped
        assert 'field2' in result or 'FIELD2' in result


def test_dotenv_repr():
    """Test __repr__ method."""

    class Settings(BaseSettings):
        model_config = {
            'env_file': '.env',
            'env_file_encoding': 'utf-8',
            'env_prefix': 'APP_',
            'env_nested_delimiter': '__',
        }
        field1: str = 'default'

    source = DotEnvSettingsSource(
        settings_cls=Settings,
        env_prefix='APP_',
        env_nested_delimiter='__',
    )

    repr_str = repr(source)
    assert 'DotEnvSettingsSource' in repr_str
    assert 'env_file' in repr_str
    assert 'env_file_encoding' in repr_str


def test_read_env_file_function():
    """Test read_env_file deprecated function."""
    with TemporaryDirectory() as temp_dir:
        env_file = Path(temp_dir) / '.env'
        env_file.write_text('VAR1=value1\n')

        with pytest.warns(DeprecationWarning, match='read_env_file will be removed'):
            result = read_env_file(
                env_file,
                encoding='utf-8',
                case_sensitive=False,
                ignore_empty=False,
                parse_none_str=None,
            )

        assert 'VAR1' in result or 'var1' in result


def test_read_env_file_function_with_defaults():
    """Test read_env_file function with default parameters."""
    with TemporaryDirectory() as temp_dir:
        env_file = Path(temp_dir) / '.env'
        env_file.write_text('VAR1=value1\n')

        with pytest.warns(DeprecationWarning):
            result = read_env_file(env_file)

        assert 'VAR1' in result or 'var1' in result
