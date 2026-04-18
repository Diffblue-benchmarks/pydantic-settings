"""Tests for pydantic_settings.sources.providers.dotenv module."""

from __future__ import annotations

import os
import tempfile
import warnings
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from pydantic_settings import BaseSettings
from pydantic_settings.sources.providers.dotenv import DotEnvSettingsSource, read_env_file
from pydantic_settings.sources.types import ENV_FILE_SENTINEL


class SimpleSettings(BaseSettings):
    """Simple settings class for testing."""

    model_config = {
        'env_file': None,
        'env_file_encoding': None,
        'dotenv_filtering': None,
    }

    name: str | None = None
    debug: bool | None = None


class PrefixedSettings(BaseSettings):
    """Settings with prefix."""

    model_config = {
        'env_file': None,
        'env_file_encoding': None,
        'env_prefix': 'APP_',
    }

    name: str | None = None
    value: str | None = None


class TestDotEnvSettingsSourceInit:
    """Test DotEnvSettingsSource.__init__ method."""

    def test_init_with_sentinel_env_file(self):
        """Test __init__ uses model_config env_file when ENV_FILE_SENTINEL is passed."""
        test_file = Path('test.env')

        class Settings(BaseSettings):
            model_config = {
                'env_file': test_file,
                'env_file_encoding': None,
                'dotenv_filtering': None,
            }
            field: str | None = None

        source = DotEnvSettingsSource(Settings, env_file=ENV_FILE_SENTINEL)
        assert source.env_file == test_file

    def test_init_with_explicit_env_file(self):
        """Test __init__ uses explicit env_file parameter."""
        explicit_file = Path('custom.env')
        model_file = Path('model.env')

        class Settings(BaseSettings):
            model_config = {
                'env_file': model_file,
                'env_file_encoding': None,
                'dotenv_filtering': None,
            }
            field: str | None = None

        source = DotEnvSettingsSource(Settings, env_file=explicit_file)
        assert source.env_file == explicit_file

    def test_init_with_none_env_file(self):
        """Test __init__ with None env_file."""
        class Settings(BaseSettings):
            model_config = {
                'env_file': None,
                'env_file_encoding': None,
                'dotenv_filtering': None,
            }
            field: str | None = None

        source = DotEnvSettingsSource(Settings, env_file=None)
        assert source.env_file is None

    def test_init_with_explicit_encoding(self):
        """Test __init__ uses explicit env_file_encoding parameter."""
        class Settings(BaseSettings):
            model_config = {
                'env_file': None,
                'env_file_encoding': 'utf-8',
                'dotenv_filtering': None,
            }
            field: str | None = None

        source = DotEnvSettingsSource(Settings, env_file_encoding='latin-1')
        assert source.env_file_encoding == 'latin-1'

    def test_init_with_encoding_from_model_config(self):
        """Test __init__ uses model_config encoding when parameter is None."""
        class Settings(BaseSettings):
            model_config = {
                'env_file': None,
                'env_file_encoding': 'iso-8859-1',
                'dotenv_filtering': None,
            }
            field: str | None = None

        source = DotEnvSettingsSource(Settings, env_file_encoding=None)
        assert source.env_file_encoding == 'iso-8859-1'

    def test_init_with_dotenv_filtering(self):
        """Test __init__ with dotenv_filtering parameter."""
        class Settings(BaseSettings):
            model_config = {
                'env_file': None,
                'env_file_encoding': None,
                'dotenv_filtering': 'only_existing',
            }
            field: str | None = None

        source = DotEnvSettingsSource(Settings, dotenv_filtering='match_prefix')
        assert source.dotenv_filtering == 'match_prefix'

    def test_init_with_all_parameters(self):
        """Test __init__ with all parameters specified."""
        test_file = Path('test.env')

        class Settings(BaseSettings):
            model_config = {
                'env_file': Path('model.env'),
                'env_file_encoding': 'utf-8',
                'dotenv_filtering': 'only_existing',
                'case_sensitive': False,
                'env_prefix': 'APP_',
                'env_nested_delimiter': '__',
                'env_nested_max_split': 2,
                'env_ignore_empty': True,
                'env_parse_none_str': 'null',
                'env_parse_enums': False,
            }
            field: str | None = None

        source = DotEnvSettingsSource(
            Settings,
            env_file=test_file,
            env_file_encoding='latin-1',
            dotenv_filtering='match_prefix',
            case_sensitive=True,
            env_prefix='CUSTOM_',
            env_nested_delimiter='::',
            env_nested_max_split=5,
            env_ignore_empty=False,
            env_parse_none_str='NONE',
            env_parse_enums=True,
        )
        assert source.env_file == test_file
        assert source.env_file_encoding == 'latin-1'
        assert source.dotenv_filtering == 'match_prefix'
        assert source.case_sensitive is True
        assert source.env_prefix == 'CUSTOM_'
        assert source.env_nested_delimiter == '::'
        assert source.env_nested_max_split == 5
        assert source.env_ignore_empty is False
        assert source.env_parse_none_str == 'NONE'


class TestDotEnvSettingsSourceLoadEnvVars:
    """Test DotEnvSettingsSource._load_env_vars method."""

    def test_load_env_vars_no_file(self):
        """Test _load_env_vars returns empty dict when no env_file is set."""
        class Settings(BaseSettings):
            model_config = {
                'env_file': None,
                'env_file_encoding': None,
                'dotenv_filtering': None,
            }
            field: str | None = None

        source = DotEnvSettingsSource(Settings, env_file=None)
        env_vars = source._load_env_vars()
        assert isinstance(env_vars, dict)
        assert env_vars == {}

    def test_load_env_vars_with_file(self):
        """Test _load_env_vars loads variables from env file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write('TEST_VAR=test_value\n')
            f.flush()
            env_file = Path(f.name)

        try:
            class Settings(BaseSettings):
                model_config = {
                    'env_file': env_file,
                    'env_file_encoding': None,
                    'dotenv_filtering': None,
                }
                field: str | None = None

            source = DotEnvSettingsSource(Settings)
            env_vars = source._load_env_vars()
            assert 'test_var' in env_vars
            assert env_vars['test_var'] == 'test_value'
        finally:
            env_file.unlink()


class TestDotEnvSettingsSourceStaticReadEnvFile:
    """Test DotEnvSettingsSource._static_read_env_file method."""

    def test_static_read_env_file_basic(self):
        """Test _static_read_env_file reads a basic env file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write('KEY1=value1\n')
            f.write('KEY2=value2\n')
            f.flush()
            env_file = Path(f.name)

        try:
            result = DotEnvSettingsSource._static_read_env_file(env_file)
            assert result['key1'] == 'value1'
            assert result['key2'] == 'value2'
        finally:
            env_file.unlink()

    def test_static_read_env_file_case_sensitive(self):
        """Test _static_read_env_file with case_sensitive=True."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write('KEY=upper\n')
            f.write('key=lower\n')
            f.flush()
            env_file = Path(f.name)

        try:
            result = DotEnvSettingsSource._static_read_env_file(env_file, case_sensitive=True)
            assert result['KEY'] == 'upper'
            assert result['key'] == 'lower'
        finally:
            env_file.unlink()

    def test_static_read_env_file_ignore_empty(self):
        """Test _static_read_env_file with ignore_empty=True."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write('KEY1=value\n')
            f.write('KEY2=\n')
            f.write('KEY3=another\n')
            f.flush()
            env_file = Path(f.name)

        try:
            result = DotEnvSettingsSource._static_read_env_file(env_file, ignore_empty=True)
            assert 'key1' in result
            assert 'key2' not in result
            assert 'key3' in result
        finally:
            env_file.unlink()

    def test_static_read_env_file_parse_none_str(self):
        """Test _static_read_env_file with parse_none_str parameter."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write('KEY1=value\n')
            f.write('KEY2=null\n')
            f.write('KEY3=none\n')
            f.flush()
            env_file = Path(f.name)

        try:
            result = DotEnvSettingsSource._static_read_env_file(env_file, parse_none_str='null')
            assert result['key1'] == 'value'
            # null should be parsed as EnvNoneType
            assert str(result['key2']) == 'null'
            assert result['key3'] == 'none'
        finally:
            env_file.unlink()


class TestDotEnvSettingsSourceReadEnvFile:
    """Test DotEnvSettingsSource._read_env_file method."""

    def test_read_env_file_basic(self):
        """Test _read_env_file reads env file with instance settings."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write('NAME=John\n')
            f.write('DEBUG=true\n')
            f.flush()
            env_file = Path(f.name)

        try:
            class Settings(BaseSettings):
                model_config = {
                    'env_file': env_file,
                    'env_file_encoding': 'utf-8',
                    'dotenv_filtering': None,
                }
                name: str | None = None
                debug: bool | None = None

            source = DotEnvSettingsSource(Settings, env_file_encoding='utf-8')
            result = source._read_env_file(env_file)
            assert 'name' in result
            assert result['name'] == 'John'
        finally:
            env_file.unlink()

    def test_read_env_file_with_encoding(self):
        """Test _read_env_file respects encoding setting."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False, encoding='utf-8') as f:
            f.write('KEY=café\n')
            f.flush()
            env_file = Path(f.name)

        try:
            class Settings(BaseSettings):
                model_config = {
                    'env_file': env_file,
                    'env_file_encoding': 'utf-8',
                    'dotenv_filtering': None,
                }
                field: str | None = None

            source = DotEnvSettingsSource(Settings, env_file_encoding='utf-8')
            result = source._read_env_file(env_file)
            assert result['key'] == 'café'
        finally:
            env_file.unlink()


class TestDotEnvSettingsSourceReadEnvFiles:
    """Test DotEnvSettingsSource._read_env_files method."""

    def test_read_env_files_no_files(self):
        """Test _read_env_files with no env_file configured."""
        class Settings(BaseSettings):
            model_config = {
                'env_file': None,
                'env_file_encoding': None,
                'dotenv_filtering': None,
            }
            field: str | None = None

        source = DotEnvSettingsSource(Settings, env_file=None)
        result = source._read_env_files()
        assert result == {}

    def test_read_env_files_single_file(self):
        """Test _read_env_files with a single env file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write('VAR1=value1\n')
            f.flush()
            env_file = Path(f.name)

        try:
            class Settings(BaseSettings):
                model_config = {
                    'env_file': env_file,
                    'env_file_encoding': None,
                    'dotenv_filtering': None,
                }
                field: str | None = None

            source = DotEnvSettingsSource(Settings, env_file=env_file)
            result = source._read_env_files()
            assert result['var1'] == 'value1'
        finally:
            env_file.unlink()

    def test_read_env_files_multiple_files(self):
        """Test _read_env_files with multiple env files."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f1:
            f1.write('VAR1=value1\n')
            f1.flush()
            file1 = Path(f1.name)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f2:
            f2.write('VAR2=value2\n')
            f2.flush()
            file2 = Path(f2.name)

        try:
            class Settings(BaseSettings):
                model_config = {
                    'env_file': [file1, file2],
                    'env_file_encoding': None,
                    'dotenv_filtering': None,
                }
                field: str | None = None

            source = DotEnvSettingsSource(Settings, env_file=[file1, file2])
            result = source._read_env_files()
            assert result['var1'] == 'value1'
            assert result['var2'] == 'value2'
        finally:
            file1.unlink()
            file2.unlink()

    def test_read_env_files_string_path(self):
        """Test _read_env_files with string path instead of Path object."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write('VAR=value\n')
            f.flush()
            env_file_path = f.name

        try:
            class Settings(BaseSettings):
                model_config = {
                    'env_file': env_file_path,
                    'env_file_encoding': None,
                    'dotenv_filtering': None,
                }
                field: str | None = None

            source = DotEnvSettingsSource(Settings, env_file=env_file_path)
            result = source._read_env_files()
            assert result['var'] == 'value'
        finally:
            Path(env_file_path).unlink()

    def test_read_env_files_nonexistent_file(self):
        """Test _read_env_files skips nonexistent files."""
        nonexistent = Path('/tmp/nonexistent_env_file_12345.env')

        class Settings(BaseSettings):
            model_config = {
                'env_file': nonexistent,
                'env_file_encoding': None,
                'dotenv_filtering': None,
            }
            field: str | None = None

        source = DotEnvSettingsSource(Settings, env_file=nonexistent)
        result = source._read_env_files()
        assert result == {}

    def test_read_env_files_expanduser(self):
        """Test _read_env_files expands ~ in paths."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write('VAR=value\n')
            f.flush()
            real_path = Path(f.name)

        try:
            class Settings(BaseSettings):
                model_config = {
                    'env_file': real_path,
                    'env_file_encoding': None,
                    'dotenv_filtering': None,
                }
                field: str | None = None

            source = DotEnvSettingsSource(Settings, env_file=real_path)
            result = source._read_env_files()
            assert 'var' in result
        finally:
            real_path.unlink()


class TestDotEnvSettingsSourceCall:
    """Test DotEnvSettingsSource.__call__ method."""

    def test_call_basic(self):
        """Test __call__ returns data from parent and dotenv."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write('NAME=DotEnv\n')
            f.flush()
            env_file = Path(f.name)

        try:
            class Settings(BaseSettings):
                model_config = {
                    'env_file': env_file,
                    'env_file_encoding': None,
                    'dotenv_filtering': None,
                }
                name: str | None = None

            source = DotEnvSettingsSource(Settings, env_file=env_file)
            result = source()
            assert isinstance(result, dict)
        finally:
            env_file.unlink()

    def test_call_only_existing_filtering(self):
        """Test __call__ with dotenv_filtering='only_existing'."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write('NAME=DotEnv\n')
            f.write('EXTRA=extra_value\n')
            f.flush()
            env_file = Path(f.name)

        try:
            class Settings(BaseSettings):
                model_config = {
                    'env_file': env_file,
                    'env_file_encoding': None,
                    'dotenv_filtering': 'only_existing',
                }
                name: str | None = None

            source = DotEnvSettingsSource(Settings, env_file=env_file, dotenv_filtering='only_existing')
            result = source()
            assert isinstance(result, dict)
        finally:
            env_file.unlink()

    def test_call_match_prefix_filtering(self):
        """Test __call__ with dotenv_filtering='match_prefix'."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write('APP_NAME=DotEnv\n')
            f.write('APP_DEBUG=true\n')
            f.write('OTHER=value\n')
            f.flush()
            env_file = Path(f.name)

        try:
            class Settings(BaseSettings):
                model_config = {
                    'env_file': env_file,
                    'env_file_encoding': None,
                    'dotenv_filtering': 'match_prefix',
                    'env_prefix': 'APP_',
                }
                name: str | None = None
                debug: bool | None = None

            source = DotEnvSettingsSource(
                Settings,
                env_file=env_file,
                dotenv_filtering='match_prefix',
                env_prefix='APP_',
            )
            result = source()
            assert isinstance(result, dict)
        finally:
            env_file.unlink()

    def test_call_with_nested_delimiter(self):
        """Test __call__ handles nested delimiters properly."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write('DB__HOST=localhost\n')
            f.write('DB__PORT=5432\n')
            f.flush()
            env_file = Path(f.name)

        try:
            class DbSettings(BaseModel):
                host: str | None = None
                port: int | None = None

            class Settings(BaseSettings):
                model_config = {
                    'env_file': env_file,
                    'env_file_encoding': None,
                    'dotenv_filtering': None,
                    'env_nested_delimiter': '__',
                }
                db: DbSettings | None = None

            source = DotEnvSettingsSource(
                Settings,
                env_file=env_file,
                env_nested_delimiter='__',
            )
            result = source()
            assert isinstance(result, dict)
        finally:
            env_file.unlink()

    def test_call_empty_env_value_handling(self):
        """Test __call__ handles empty env values."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write('NAME=\n')
            f.write('DEBUG=false\n')
            f.flush()
            env_file = Path(f.name)

        try:
            class Settings(BaseSettings):
                model_config = {
                    'env_file': env_file,
                    'env_file_encoding': None,
                    'dotenv_filtering': None,
                }
                name: str | None = None
                debug: bool | None = None

            source = DotEnvSettingsSource(Settings, env_file=env_file)
            result = source()
            assert isinstance(result, dict)
        finally:
            env_file.unlink()


class TestDotEnvSettingsSourceRepr:
    """Test DotEnvSettingsSource.__repr__ method."""

    def test_repr_basic(self):
        """Test __repr__ returns string representation."""
        class Settings(BaseSettings):
            model_config = {
                'env_file': None,
                'env_file_encoding': None,
                'dotenv_filtering': None,
            }
            field: str | None = None

        source = DotEnvSettingsSource(Settings, env_file=None)
        repr_str = repr(source)
        assert isinstance(repr_str, str)
        assert 'DotEnvSettingsSource' in repr_str

    def test_repr_includes_env_file(self):
        """Test __repr__ includes env_file."""
        test_file = Path('test.env')

        class Settings(BaseSettings):
            model_config = {
                'env_file': test_file,
                'env_file_encoding': None,
                'dotenv_filtering': None,
            }
            field: str | None = None

        source = DotEnvSettingsSource(Settings, env_file=test_file)
        repr_str = repr(source)
        assert 'env_file' in repr_str

    def test_repr_includes_encoding(self):
        """Test __repr__ includes env_file_encoding."""
        class Settings(BaseSettings):
            model_config = {
                'env_file': None,
                'env_file_encoding': 'utf-8',
                'dotenv_filtering': None,
            }
            field: str | None = None

        source = DotEnvSettingsSource(Settings, env_file_encoding='utf-8')
        repr_str = repr(source)
        assert 'env_file_encoding' in repr_str or 'utf-8' in repr_str

    def test_repr_includes_delimiter(self):
        """Test __repr__ includes env_nested_delimiter."""
        class Settings(BaseSettings):
            model_config = {
                'env_file': None,
                'env_file_encoding': None,
                'dotenv_filtering': None,
                'env_nested_delimiter': '__',
            }
            field: str | None = None

        source = DotEnvSettingsSource(Settings, env_nested_delimiter='__')
        repr_str = repr(source)
        assert 'env_nested_delimiter' in repr_str or '__' in repr_str


class TestReadEnvFile:
    """Test the module-level read_env_file function."""

    def test_read_env_file_deprecation_warning(self):
        """Test read_env_file issues a DeprecationWarning."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write('VAR=value\n')
            f.flush()
            env_file = Path(f.name)

        try:
            with pytest.warns(DeprecationWarning, match='read_env_file will be removed'):
                result = read_env_file(env_file)
            assert result['var'] == 'value'
        finally:
            env_file.unlink()

    def test_read_env_file_basic(self):
        """Test read_env_file reads a file correctly."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write('KEY1=value1\n')
            f.write('KEY2=value2\n')
            f.flush()
            env_file = Path(f.name)

        try:
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', DeprecationWarning)
                result = read_env_file(env_file)
            assert result['key1'] == 'value1'
            assert result['key2'] == 'value2'
        finally:
            env_file.unlink()

    def test_read_env_file_with_encoding(self):
        """Test read_env_file with explicit encoding."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False, encoding='utf-8') as f:
            f.write('VAR=café\n')
            f.flush()
            env_file = Path(f.name)

        try:
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', DeprecationWarning)
                result = read_env_file(env_file, encoding='utf-8')
            assert result['var'] == 'café'
        finally:
            env_file.unlink()

    def test_read_env_file_case_sensitive(self):
        """Test read_env_file with case_sensitive=True."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write('VAR=upper\n')
            f.write('var=lower\n')
            f.flush()
            env_file = Path(f.name)

        try:
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', DeprecationWarning)
                result = read_env_file(env_file, case_sensitive=True)
            assert result['VAR'] == 'upper'
            assert result['var'] == 'lower'
        finally:
            env_file.unlink()

    def test_read_env_file_ignore_empty(self):
        """Test read_env_file with ignore_empty=True."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write('KEY1=value\n')
            f.write('KEY2=\n')
            f.flush()
            env_file = Path(f.name)

        try:
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', DeprecationWarning)
                result = read_env_file(env_file, ignore_empty=True)
            assert 'key1' in result
            assert 'key2' not in result
        finally:
            env_file.unlink()

    def test_read_env_file_parse_none_str(self):
        """Test read_env_file with parse_none_str parameter."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write('KEY1=value\n')
            f.write('KEY2=null\n')
            f.flush()
            env_file = Path(f.name)

        try:
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', DeprecationWarning)
                result = read_env_file(env_file, parse_none_str='null')
            assert result['key1'] == 'value'
            assert str(result['key2']) == 'null'
        finally:
            env_file.unlink()
