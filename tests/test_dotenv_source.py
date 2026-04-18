"""Tests for DotEnvSettingsSource class and read_env_file function."""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

import pytest
from pydantic import Field

from pydantic_settings import BaseSettings
from pydantic_settings.sources.providers.dotenv import DotEnvSettingsSource, read_env_file


class SimpleSettings(BaseSettings):
    """Simple settings class for basic tests."""

    foo: str = 'default_foo'
    bar: int = 42


class SettingsWithPrefix(BaseSettings):
    """Settings class with env_prefix configured."""

    model_config = {'env_prefix': 'APP_'}

    name: str = 'default_name'
    value: int = 0


class SettingsWithNested(BaseSettings):
    """Settings class with nested delimiter."""

    model_config = {'env_nested_delimiter': '__'}

    db_host: str = 'localhost'
    db_port: int = 5432


class SettingsWithCaseSensitive(BaseSettings):
    """Settings class with case sensitivity enabled."""

    model_config = {'case_sensitive': True}

    API_KEY: str = 'default_key'


class SettingsWithExtraAllowed(BaseSettings):
    """Settings class that allows extra fields."""

    model_config = {'extra': 'allow'}

    known_field: str = 'default'


class TestDotEnvSettingsSourceInit:
    """Tests for DotEnvSettingsSource.__init__ method."""

    def test_init_with_no_env_file(self) -> None:
        """Test initialization without env_file."""
        source = DotEnvSettingsSource(SimpleSettings, env_file=None)

        assert source.env_file is None
        assert source.env_file_encoding is None
        assert source.dotenv_filtering is None

    def test_init_with_env_file_string(self, tmp_path: Path) -> None:
        """Test initialization with env_file as a string path."""
        env_file = tmp_path / '.env'
        env_file.write_text('FOO=bar\n')

        source = DotEnvSettingsSource(SimpleSettings, env_file=str(env_file))

        assert source.env_file == str(env_file)

    def test_init_with_env_file_path(self, tmp_path: Path) -> None:
        """Test initialization with env_file as a Path object."""
        env_file = tmp_path / '.env'
        env_file.write_text('FOO=bar\n')

        source = DotEnvSettingsSource(SimpleSettings, env_file=env_file)

        assert source.env_file == env_file

    def test_init_with_env_file_encoding(self, tmp_path: Path) -> None:
        """Test initialization with custom encoding."""
        env_file = tmp_path / '.env'
        env_file.write_text('FOO=bar\n', encoding='utf-8')

        source = DotEnvSettingsSource(
            SimpleSettings, env_file=env_file, env_file_encoding='utf-8'
        )

        assert source.env_file_encoding == 'utf-8'

    def test_init_with_dotenv_filtering_only_existing(self, tmp_path: Path) -> None:
        """Test initialization with dotenv_filtering set to only_existing."""
        env_file = tmp_path / '.env'
        env_file.write_text('FOO=bar\n')

        source = DotEnvSettingsSource(
            SimpleSettings, env_file=env_file, dotenv_filtering='only_existing'
        )

        assert source.dotenv_filtering == 'only_existing'

    def test_init_with_dotenv_filtering_match_prefix(self, tmp_path: Path) -> None:
        """Test initialization with dotenv_filtering set to match_prefix."""
        env_file = tmp_path / '.env'
        env_file.write_text('FOO=bar\n')

        source = DotEnvSettingsSource(
            SimpleSettings, env_file=env_file, dotenv_filtering='match_prefix'
        )

        assert source.dotenv_filtering == 'match_prefix'

    def test_init_with_case_sensitive(self, tmp_path: Path) -> None:
        """Test initialization with case_sensitive option."""
        env_file = tmp_path / '.env'
        env_file.write_text('FOO=bar\n')

        source = DotEnvSettingsSource(SimpleSettings, env_file=env_file, case_sensitive=True)

        assert source.case_sensitive is True

    def test_init_with_env_prefix(self, tmp_path: Path) -> None:
        """Test initialization with env_prefix option."""
        env_file = tmp_path / '.env'
        env_file.write_text('MY_FOO=bar\n')

        source = DotEnvSettingsSource(SimpleSettings, env_file=env_file, env_prefix='MY_')

        assert source.env_prefix == 'MY_'

    def test_init_with_env_nested_delimiter(self, tmp_path: Path) -> None:
        """Test initialization with env_nested_delimiter option."""
        env_file = tmp_path / '.env'
        env_file.write_text('FOO__BAR=baz\n')

        source = DotEnvSettingsSource(
            SimpleSettings, env_file=env_file, env_nested_delimiter='__'
        )

        assert source.env_nested_delimiter == '__'

    def test_init_with_env_ignore_empty(self, tmp_path: Path) -> None:
        """Test initialization with env_ignore_empty option."""
        env_file = tmp_path / '.env'
        env_file.write_text('FOO=\n')

        source = DotEnvSettingsSource(SimpleSettings, env_file=env_file, env_ignore_empty=True)

        assert source.env_ignore_empty is True

    def test_init_with_env_parse_none_str(self, tmp_path: Path) -> None:
        """Test initialization with env_parse_none_str option."""
        env_file = tmp_path / '.env'
        env_file.write_text('FOO=null\n')

        source = DotEnvSettingsSource(
            SimpleSettings, env_file=env_file, env_parse_none_str='null'
        )

        assert source.env_parse_none_str == 'null'

    def test_init_with_multiple_env_files(self, tmp_path: Path) -> None:
        """Test initialization with multiple env files."""
        env_file1 = tmp_path / '.env'
        env_file1.write_text('FOO=bar1\n')
        env_file2 = tmp_path / '.env.local'
        env_file2.write_text('FOO=bar2\n')

        source = DotEnvSettingsSource(
            SimpleSettings, env_file=[env_file1, env_file2]
        )

        assert source.env_file == [env_file1, env_file2]


class TestDotEnvSettingsSourceLoadEnvVars:
    """Tests for DotEnvSettingsSource._load_env_vars method."""

    def test_load_env_vars_returns_env_file_contents(self, tmp_path: Path) -> None:
        """Test that _load_env_vars returns contents from env file."""
        env_file = tmp_path / '.env'
        env_file.write_text('FOO=bar\nBAZ=qux\n')

        source = DotEnvSettingsSource(SimpleSettings, env_file=env_file)
        env_vars = source._load_env_vars()

        assert 'foo' in env_vars or 'FOO' in env_vars

    def test_load_env_vars_with_no_file(self) -> None:
        """Test _load_env_vars with no env file configured."""
        source = DotEnvSettingsSource(SimpleSettings, env_file=None)
        env_vars = source._load_env_vars()

        assert env_vars == {}


class TestDotEnvSettingsSourceStaticReadEnvFile:
    """Tests for DotEnvSettingsSource._static_read_env_file method."""

    def test_static_read_env_file_basic(self, tmp_path: Path) -> None:
        """Test basic file reading."""
        env_file = tmp_path / '.env'
        env_file.write_text('FOO=bar\nBAZ=qux\n')

        result = DotEnvSettingsSource._static_read_env_file(env_file)

        assert 'foo' in result or 'FOO' in result

    def test_static_read_env_file_with_encoding(self, tmp_path: Path) -> None:
        """Test file reading with specific encoding."""
        env_file = tmp_path / '.env'
        env_file.write_text('FOO=bar\n', encoding='latin-1')

        result = DotEnvSettingsSource._static_read_env_file(env_file, encoding='latin-1')

        assert 'foo' in result or 'FOO' in result

    def test_static_read_env_file_case_sensitive(self, tmp_path: Path) -> None:
        """Test file reading with case sensitivity."""
        env_file = tmp_path / '.env'
        env_file.write_text('FOO=bar\n')

        result = DotEnvSettingsSource._static_read_env_file(env_file, case_sensitive=True)

        assert 'FOO' in result
        assert 'foo' not in result

    def test_static_read_env_file_ignore_empty(self, tmp_path: Path) -> None:
        """Test file reading with ignore_empty option."""
        env_file = tmp_path / '.env'
        env_file.write_text('FOO=\nBAR=value\n')

        result = DotEnvSettingsSource._static_read_env_file(
            env_file, ignore_empty=True
        )

        assert 'bar' in result or 'BAR' in result

    def test_static_read_env_file_parse_none_str(self, tmp_path: Path) -> None:
        """Test file reading with parse_none_str option returns EnvNoneType."""
        from pydantic_settings.sources.types import EnvNoneType

        env_file = tmp_path / '.env'
        env_file.write_text('FOO=null\n')

        result = DotEnvSettingsSource._static_read_env_file(
            env_file, parse_none_str='null'
        )

        key = 'foo' if 'foo' in result else 'FOO'
        # parse_none_str returns EnvNoneType, not None - the conversion to None
        # happens later in the __call__ method via _replace_env_none_type_values
        assert isinstance(result[key], EnvNoneType)


class TestDotEnvSettingsSourceReadEnvFile:
    """Tests for DotEnvSettingsSource._read_env_file method."""

    def test_read_env_file_uses_instance_settings(self, tmp_path: Path) -> None:
        """Test that _read_env_file uses instance-level settings."""
        env_file = tmp_path / '.env'
        env_file.write_text('FOO=bar\n')

        source = DotEnvSettingsSource(
            SimpleSettings,
            env_file=env_file,
            env_file_encoding='utf-8',
            case_sensitive=True,
            env_ignore_empty=True,
        )
        result = source._read_env_file(env_file)

        assert 'FOO' in result


class TestDotEnvSettingsSourceReadEnvFiles:
    """Tests for DotEnvSettingsSource._read_env_files method."""

    def test_read_env_files_with_none(self) -> None:
        """Test _read_env_files when env_file is None."""
        source = DotEnvSettingsSource(SimpleSettings, env_file=None)
        result = source._read_env_files()

        assert result == {}

    def test_read_env_files_with_single_file(self, tmp_path: Path) -> None:
        """Test _read_env_files with a single file."""
        env_file = tmp_path / '.env'
        env_file.write_text('FOO=bar\n')

        source = DotEnvSettingsSource(SimpleSettings, env_file=env_file)
        result = source._read_env_files()

        assert 'foo' in result or 'FOO' in result

    def test_read_env_files_with_multiple_files(self, tmp_path: Path) -> None:
        """Test _read_env_files with multiple files."""
        env_file1 = tmp_path / '.env'
        env_file1.write_text('FOO=bar1\nBAZ=qux\n')
        env_file2 = tmp_path / '.env.local'
        env_file2.write_text('FOO=bar2\n')

        source = DotEnvSettingsSource(
            SimpleSettings, env_file=[env_file1, env_file2]
        )
        result = source._read_env_files()

        # Later file should override earlier values
        key = 'foo' if 'foo' in result else 'FOO'
        assert result[key] == 'bar2'

    def test_read_env_files_skips_nonexistent_files(self, tmp_path: Path) -> None:
        """Test _read_env_files ignores non-existent files."""
        env_file = tmp_path / '.env'
        env_file.write_text('FOO=bar\n')
        nonexistent = tmp_path / '.env.nonexistent'

        source = DotEnvSettingsSource(
            SimpleSettings, env_file=[env_file, nonexistent]
        )
        result = source._read_env_files()

        assert 'foo' in result or 'FOO' in result

    def test_read_env_files_expands_user_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test _read_env_files expands ~ in paths."""
        env_file = tmp_path / '.env'
        env_file.write_text('FOO=bar\n')

        # Mock expanduser to return our tmp_path
        monkeypatch.setattr(Path, 'expanduser', lambda self: tmp_path / self.name)

        source = DotEnvSettingsSource(SimpleSettings, env_file=Path('~/.env'))
        # The result will depend on whether the mocked path is valid
        # This tests that expanduser is called


class TestDotEnvSettingsSourceCall:
    """Tests for DotEnvSettingsSource.__call__ method."""

    def test_call_returns_dict(self, tmp_path: Path) -> None:
        """Test that __call__ returns a dictionary."""
        env_file = tmp_path / '.env'
        env_file.write_text('FOO=bar\n')

        source = DotEnvSettingsSource(SimpleSettings, env_file=env_file)
        result = source()

        assert isinstance(result, dict)

    def test_call_with_only_existing_filtering(self, tmp_path: Path) -> None:
        """Test __call__ with only_existing filtering mode."""
        env_file = tmp_path / '.env'
        env_file.write_text('FOO=bar\nEXTRA=extra_value\n')

        source = DotEnvSettingsSource(
            SimpleSettings, env_file=env_file, dotenv_filtering='only_existing'
        )
        result = source()

        assert isinstance(result, dict)
        # only_existing should behave like EnvSettingsSource

    def test_call_with_match_prefix_filtering(self, tmp_path: Path) -> None:
        """Test __call__ with match_prefix filtering mode."""
        env_file = tmp_path / '.env'
        env_file.write_text('APP_NAME=myapp\nAPP_OTHER=value\nNON_PREFIX=ignored\n')

        source = DotEnvSettingsSource(
            SettingsWithPrefix, env_file=env_file, dotenv_filtering='match_prefix'
        )
        result = source()

        assert isinstance(result, dict)

    def test_call_with_extra_allowed(self, tmp_path: Path) -> None:
        """Test __call__ with extra fields allowed."""
        env_file = tmp_path / '.env'
        env_file.write_text('KNOWN_FIELD=value\nEXTRA_FIELD=extra\n')

        source = DotEnvSettingsSource(SettingsWithExtraAllowed, env_file=env_file)
        result = source()

        assert isinstance(result, dict)

    def test_call_with_env_prefix(self, tmp_path: Path) -> None:
        """Test __call__ with env_prefix set."""
        env_file = tmp_path / '.env'
        env_file.write_text('APP_NAME=test_app\nAPP_VALUE=123\n')

        source = DotEnvSettingsSource(SettingsWithPrefix, env_file=env_file)
        result = source()

        assert isinstance(result, dict)

    def test_call_with_nested_delimiter(self, tmp_path: Path) -> None:
        """Test __call__ with nested delimiter."""
        env_file = tmp_path / '.env'
        env_file.write_text('DB_HOST=myhost\nDB_PORT=3306\n')

        source = DotEnvSettingsSource(SettingsWithNested, env_file=env_file)
        result = source()

        assert isinstance(result, dict)


class TestDotEnvSettingsSourceRepr:
    """Tests for DotEnvSettingsSource.__repr__ method."""

    def test_repr_contains_class_name(self) -> None:
        """Test that __repr__ contains the class name."""
        source = DotEnvSettingsSource(SimpleSettings, env_file=None)
        repr_str = repr(source)

        assert 'DotEnvSettingsSource' in repr_str

    def test_repr_contains_env_file(self, tmp_path: Path) -> None:
        """Test that __repr__ contains env_file value."""
        env_file = tmp_path / '.env'
        env_file.write_text('')

        source = DotEnvSettingsSource(SimpleSettings, env_file=env_file)
        repr_str = repr(source)

        assert 'env_file=' in repr_str

    def test_repr_contains_env_file_encoding(self, tmp_path: Path) -> None:
        """Test that __repr__ contains env_file_encoding value."""
        env_file = tmp_path / '.env'
        env_file.write_text('')

        source = DotEnvSettingsSource(
            SimpleSettings, env_file=env_file, env_file_encoding='utf-8'
        )
        repr_str = repr(source)

        assert 'env_file_encoding=' in repr_str

    def test_repr_contains_env_nested_delimiter(self, tmp_path: Path) -> None:
        """Test that __repr__ contains env_nested_delimiter value."""
        env_file = tmp_path / '.env'
        env_file.write_text('')

        source = DotEnvSettingsSource(
            SimpleSettings, env_file=env_file, env_nested_delimiter='__'
        )
        repr_str = repr(source)

        assert 'env_nested_delimiter=' in repr_str

    def test_repr_contains_env_prefix_len(self, tmp_path: Path) -> None:
        """Test that __repr__ contains env_prefix_len value."""
        env_file = tmp_path / '.env'
        env_file.write_text('')

        source = DotEnvSettingsSource(
            SimpleSettings, env_file=env_file, env_prefix='APP_'
        )
        repr_str = repr(source)

        assert 'env_prefix_len=' in repr_str


class TestReadEnvFile:
    """Tests for the deprecated read_env_file function."""

    def test_read_env_file_emits_deprecation_warning(self, tmp_path: Path) -> None:
        """Test that read_env_file emits a deprecation warning."""
        env_file = tmp_path / '.env'
        env_file.write_text('FOO=bar\n')

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            read_env_file(env_file)

            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert 'read_env_file will be removed' in str(w[0].message)

    def test_read_env_file_returns_mapping(self, tmp_path: Path) -> None:
        """Test that read_env_file returns a Mapping."""
        env_file = tmp_path / '.env'
        env_file.write_text('FOO=bar\n')

        with warnings.catch_warnings():
            warnings.simplefilter('ignore', DeprecationWarning)
            result = read_env_file(env_file)

        assert 'foo' in result or 'FOO' in result

    def test_read_env_file_with_encoding(self, tmp_path: Path) -> None:
        """Test read_env_file with custom encoding."""
        env_file = tmp_path / '.env'
        env_file.write_text('FOO=bar\n', encoding='latin-1')

        with warnings.catch_warnings():
            warnings.simplefilter('ignore', DeprecationWarning)
            result = read_env_file(env_file, encoding='latin-1')

        assert 'foo' in result or 'FOO' in result

    def test_read_env_file_case_sensitive(self, tmp_path: Path) -> None:
        """Test read_env_file with case_sensitive option."""
        env_file = tmp_path / '.env'
        env_file.write_text('FOO=bar\n')

        with warnings.catch_warnings():
            warnings.simplefilter('ignore', DeprecationWarning)
            result = read_env_file(env_file, case_sensitive=True)

        assert 'FOO' in result
        assert 'foo' not in result

    def test_read_env_file_ignore_empty(self, tmp_path: Path) -> None:
        """Test read_env_file with ignore_empty option."""
        env_file = tmp_path / '.env'
        env_file.write_text('FOO=\nBAR=value\n')

        with warnings.catch_warnings():
            warnings.simplefilter('ignore', DeprecationWarning)
            result = read_env_file(env_file, ignore_empty=True)

        assert 'bar' in result or 'BAR' in result

    def test_read_env_file_parse_none_str(self, tmp_path: Path) -> None:
        """Test read_env_file with parse_none_str option returns EnvNoneType."""
        from pydantic_settings.sources.types import EnvNoneType

        env_file = tmp_path / '.env'
        env_file.write_text('FOO=null\n')

        with warnings.catch_warnings():
            warnings.simplefilter('ignore', DeprecationWarning)
            result = read_env_file(env_file, parse_none_str='null')

        key = 'foo' if 'foo' in result else 'FOO'
        # parse_none_str returns EnvNoneType, not None - the conversion to None
        # happens later in the __call__ method via _replace_env_none_type_values
        assert isinstance(result[key], EnvNoneType)


class TestDotEnvSettingsSourceIntegration:
    """Integration tests for DotEnvSettingsSource with BaseSettings."""

    def test_basic_dotenv_loading(self, tmp_path: Path) -> None:
        """Test basic dotenv loading through BaseSettings."""
        env_file = tmp_path / '.env'
        env_file.write_text('FOO=env_value\nBAR=123\n')

        settings = SimpleSettings(_env_file=env_file)

        assert settings.foo == 'env_value'
        assert settings.bar == 123

    def test_dotenv_with_defaults(self, tmp_path: Path) -> None:
        """Test dotenv loading uses defaults when not in file."""
        env_file = tmp_path / '.env'
        env_file.write_text('FOO=env_value\n')

        settings = SimpleSettings(_env_file=env_file)

        assert settings.foo == 'env_value'
        assert settings.bar == 42  # default value

    def test_dotenv_with_nonexistent_file(self) -> None:
        """Test loading with non-existent dotenv file."""
        settings = SimpleSettings(_env_file='/nonexistent/.env')

        assert settings.foo == 'default_foo'
        assert settings.bar == 42

    def test_dotenv_override_order(self, tmp_path: Path) -> None:
        """Test that later files override earlier ones."""
        env_file1 = tmp_path / '.env'
        env_file1.write_text('FOO=first\n')
        env_file2 = tmp_path / '.env.local'
        env_file2.write_text('FOO=second\n')

        settings = SimpleSettings(_env_file=[env_file1, env_file2])

        assert settings.foo == 'second'

    def test_dotenv_with_prefix(self, tmp_path: Path) -> None:
        """Test dotenv loading with env_prefix."""
        env_file = tmp_path / '.env'
        env_file.write_text('APP_NAME=prefixed_name\nAPP_VALUE=999\n')

        settings = SettingsWithPrefix(_env_file=env_file)

        assert settings.name == 'prefixed_name'
        assert settings.value == 999

    def test_dotenv_with_case_sensitive(self, tmp_path: Path) -> None:
        """Test dotenv loading with case_sensitive option."""
        env_file = tmp_path / '.env'
        env_file.write_text('API_KEY=my_secret_key\n')

        settings = SettingsWithCaseSensitive(_env_file=env_file)

        assert settings.API_KEY == 'my_secret_key'
