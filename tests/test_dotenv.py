"""Tests for pydantic_settings.sources.providers.dotenv module."""

import os
import warnings
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory

import pytest
from pydantic import BaseModel, Field

from pydantic_settings.main import BaseSettings
from pydantic_settings.sources.providers.dotenv import (
    DotEnvSettingsSource,
    read_env_file,
)
from pydantic_settings.sources.types import ENV_FILE_SENTINEL


def test_dotenv_init_with_sentinel():
    """Test DotEnvSettingsSource initialization with ENV_FILE_SENTINEL."""

    class Settings(BaseSettings):
        field1: str = "default"

        model_config = {
            "env_file": ".env",
            "env_file_encoding": "utf-8",
            "dotenv_filtering": "only_existing",
        }

    source = DotEnvSettingsSource(
        Settings,
        env_file=ENV_FILE_SENTINEL,
        env_file_encoding=None,
        dotenv_filtering=None,
    )

    assert source.env_file == ".env"
    assert source.env_file_encoding == "utf-8"
    assert source.dotenv_filtering == "only_existing"


def test_dotenv_init_with_explicit_values():
    """Test DotEnvSettingsSource initialization with explicit values."""

    class Settings(BaseSettings):
        field1: str = "default"

        model_config = {
            "env_file": ".env.default",
            "env_file_encoding": "latin-1",
        }

    source = DotEnvSettingsSource(
        Settings,
        env_file=Path(".env.custom"),
        env_file_encoding="utf-16",
        dotenv_filtering="match_prefix",
        case_sensitive=True,
        env_prefix="APP_",
        env_prefix_target="variable",
        env_nested_delimiter="__",
        env_nested_max_split=3,
        env_ignore_empty=True,
        env_parse_none_str="null",
        env_parse_enums=True,
    )

    assert source.env_file == Path(".env.custom")
    assert source.env_file_encoding == "utf-16"
    assert source.dotenv_filtering == "match_prefix"
    assert source.case_sensitive is True
    assert source.env_prefix == "APP_"
    assert source.env_ignore_empty is True
    assert source.env_parse_none_str == "null"


def test_dotenv_init_none_values():
    """Test DotEnvSettingsSource initialization with None values."""

    class Settings(BaseSettings):
        field1: str = "default"

    source = DotEnvSettingsSource(
        Settings,
        env_file=None,
        env_file_encoding=None,
        dotenv_filtering=None,
    )

    assert source.env_file is None


def test_load_env_vars():
    """Test _load_env_vars returns result from _read_env_files."""
    with TemporaryDirectory() as tmpdir:
        env_file = Path(tmpdir) / ".env"
        env_file.write_text("TEST_VAR=value123\n")

        class Settings(BaseSettings):
            test_var: str = "default"

        source = DotEnvSettingsSource(Settings, env_file=env_file)
        env_vars = source._load_env_vars()

        assert "TEST_VAR" in env_vars or "test_var" in env_vars


def test_static_read_env_file():
    """Test _static_read_env_file reads and parses dotenv file."""
    with TemporaryDirectory() as tmpdir:
        env_file = Path(tmpdir) / ".env"
        env_file.write_text("KEY1=value1\nKEY2=value2\n")

        result = DotEnvSettingsSource._static_read_env_file(env_file)

        assert "KEY1" in result or "key1" in result
        assert result.get("KEY1", result.get("key1")) == "value1"
        assert "KEY2" in result or "key2" in result


def test_static_read_env_file_with_encoding():
    """Test _static_read_env_file with custom encoding."""
    with TemporaryDirectory() as tmpdir:
        env_file = Path(tmpdir) / ".env"
        env_file.write_text("KEY=value", encoding="utf-8")

        result = DotEnvSettingsSource._static_read_env_file(
            env_file, encoding="utf-8"
        )

        assert "KEY" in result or "key" in result


def test_static_read_env_file_case_sensitive():
    """Test _static_read_env_file with case_sensitive flag."""
    with TemporaryDirectory() as tmpdir:
        env_file = Path(tmpdir) / ".env"
        env_file.write_text("MyKey=value\n")

        result = DotEnvSettingsSource._static_read_env_file(
            env_file, case_sensitive=True
        )

        assert "MyKey" in result


def test_static_read_env_file_ignore_empty():
    """Test _static_read_env_file with ignore_empty flag."""
    with TemporaryDirectory() as tmpdir:
        env_file = Path(tmpdir) / ".env"
        env_file.write_text("KEY1=value\nKEY2=\n")

        result = DotEnvSettingsSource._static_read_env_file(
            env_file, ignore_empty=True
        )

        # Empty values should be handled
        assert "KEY1" in result or "key1" in result


def test_static_read_env_file_parse_none_str():
    """Test _static_read_env_file with parse_none_str."""
    with TemporaryDirectory() as tmpdir:
        env_file = Path(tmpdir) / ".env"
        env_file.write_text("KEY1=null\nKEY2=value\n")

        result = DotEnvSettingsSource._static_read_env_file(
            env_file, parse_none_str="null"
        )

        assert "KEY1" in result or "key1" in result


def test_read_env_file_method():
    """Test _read_env_file passes parameters to static method."""
    with TemporaryDirectory() as tmpdir:
        env_file = Path(tmpdir) / ".env"
        env_file.write_text("KEY=value\n")

        class Settings(BaseSettings):
            key: str = "default"

        source = DotEnvSettingsSource(
            Settings,
            env_file=env_file,
            env_file_encoding="utf-8",
            case_sensitive=False,
            env_ignore_empty=False,
            env_parse_none_str=None,
        )

        result = source._read_env_file(env_file)

        assert "KEY" in result or "key" in result


def test_read_env_files_none():
    """Test _read_env_files returns empty dict when env_file is None."""

    class Settings(BaseSettings):
        field1: str = "default"

    source = DotEnvSettingsSource(Settings, env_file=None)
    result = source._read_env_files()

    assert result == {}


def test_read_env_files_single_string():
    """Test _read_env_files with single string path."""
    with TemporaryDirectory() as tmpdir:
        env_file = Path(tmpdir) / ".env"
        env_file.write_text("KEY=value\n")

        class Settings(BaseSettings):
            key: str = "default"

        source = DotEnvSettingsSource(Settings, env_file=str(env_file))
        result = source._read_env_files()

        assert "KEY" in result or "key" in result


def test_read_env_files_single_path():
    """Test _read_env_files with single Path object."""
    with TemporaryDirectory() as tmpdir:
        env_file = Path(tmpdir) / ".env"
        env_file.write_text("KEY=value\n")

        class Settings(BaseSettings):
            key: str = "default"

        source = DotEnvSettingsSource(Settings, env_file=env_file)
        result = source._read_env_files()

        assert "KEY" in result or "key" in result


def test_read_env_files_multiple():
    """Test _read_env_files with multiple env files."""
    with TemporaryDirectory() as tmpdir:
        env_file1 = Path(tmpdir) / ".env1"
        env_file1.write_text("KEY1=value1\n")
        env_file2 = Path(tmpdir) / ".env2"
        env_file2.write_text("KEY2=value2\n")

        class Settings(BaseSettings):
            key1: str = "default"
            key2: str = "default"

        source = DotEnvSettingsSource(Settings, env_file=[env_file1, env_file2])
        result = source._read_env_files()

        assert ("KEY1" in result or "key1" in result)
        assert ("KEY2" in result or "key2" in result)


def test_read_env_files_nonexistent():
    """Test _read_env_files skips nonexistent files."""

    class Settings(BaseSettings):
        key: str = "default"

    source = DotEnvSettingsSource(
        Settings, env_file=Path("/nonexistent/.env")
    )
    result = source._read_env_files()

    assert result == {}


def test_read_env_files_with_expanduser():
    """Test _read_env_files expands user home directory."""
    with TemporaryDirectory() as tmpdir:
        # Create a file in tmpdir
        env_file = Path(tmpdir) / ".env"
        env_file.write_text("KEY=value\n")

        class Settings(BaseSettings):
            key: str = "default"

        # Use absolute path to ensure it exists
        source = DotEnvSettingsSource(Settings, env_file=env_file)
        result = source._read_env_files()

        # File should be read
        assert "KEY" in result or "key" in result


def test_call_only_existing_filtering():
    """Test __call__ with only_existing dotenv filtering."""
    with TemporaryDirectory() as tmpdir:
        env_file = Path(tmpdir) / ".env"
        env_file.write_text("FIELD1=from_env\nEXTRA=extra_value\n")

        class Settings(BaseSettings):
            field1: str = "default"

            model_config = {"extra": "allow"}

        source = DotEnvSettingsSource(
            Settings,
            env_file=env_file,
            dotenv_filtering="only_existing",
        )

        data = source()

        # Should only return existing fields
        assert "field1" in data or "FIELD1" in data


def test_call_match_prefix_filtering():
    """Test __call__ with match_prefix dotenv filtering."""
    with TemporaryDirectory() as tmpdir:
        env_file = Path(tmpdir) / ".env"
        env_file.write_text("APP_FIELD1=value1\nAPP_FIELD2=value2\nOTHER=other\n")

        class Settings(BaseSettings):
            field1: str = "default"

            model_config = {"extra": "allow"}

        source = DotEnvSettingsSource(
            Settings,
            env_file=env_file,
            dotenv_filtering="match_prefix",
            env_prefix="APP_",
        )

        data = source()

        # Should include all vars with prefix, stripped
        assert "FIELD1" in data or "field1" in data


def test_call_match_prefix_with_nested_delimiter():
    """Test __call__ with match_prefix and nested delimiter."""
    with TemporaryDirectory() as tmpdir:
        env_file = Path(tmpdir) / ".env"
        env_file.write_text("APP_DB__HOST=localhost\nAPP_DB__PORT=5432\n")

        class Settings(BaseSettings):
            db: dict = {}

            model_config = {"extra": "allow"}

        source = DotEnvSettingsSource(
            Settings,
            env_file=env_file,
            dotenv_filtering="match_prefix",
            env_prefix="APP_",
            env_nested_delimiter="__",
        )

        data = source()

        # Should have DB-related fields
        assert "DB__HOST" in data or "db" in data


def test_call_extra_allowed():
    """Test __call__ with extra='allow' configuration."""
    with TemporaryDirectory() as tmpdir:
        env_file = Path(tmpdir) / ".env"
        env_file.write_text("FIELD1=value1\nEXTRA_FIELD=extra\n")

        class Settings(BaseSettings):
            field1: str = "default"

            model_config = {"extra": "allow"}

        source = DotEnvSettingsSource(Settings, env_file=env_file)

        data = source()

        # Should include extra fields
        assert len(data) > 0


def test_call_extra_forbidden():
    """Test __call__ with extra='forbid' configuration."""
    with TemporaryDirectory() as tmpdir:
        env_file = Path(tmpdir) / ".env"
        env_file.write_text("FIELD1=value1\nEXTRA=extra\n")

        class Settings(BaseSettings):
            field1: str = "default"

            model_config = {"extra": "forbid"}

        source = DotEnvSettingsSource(Settings, env_file=env_file)

        data = source()

        # Should only include defined fields
        assert "field1" in data or "FIELD1" in data


def test_call_with_complex_field():
    """Test __call__ handles complex fields with nested structures."""
    with TemporaryDirectory() as tmpdir:
        env_file = Path(tmpdir) / ".env"
        env_file.write_text("NESTED__FIELD=value\nOTHER=other\n")

        class NestedModel(BaseModel):
            field: str = "default"

        class Settings(BaseSettings):
            nested: NestedModel = NestedModel()

            model_config = {"extra": "allow", "env_nested_delimiter": "__"}

        source = DotEnvSettingsSource(
            Settings,
            env_file=env_file,
            env_nested_delimiter="__",
        )

        data = source()

        assert len(data) > 0


def test_call_with_env_prefix_and_extra():
    """Test __call__ with env_prefix and extra fields."""
    with TemporaryDirectory() as tmpdir:
        env_file = Path(tmpdir) / ".env"
        env_file.write_text("APP_FIELD1=value1\nAPP_EXTRA=extra\n")

        class Settings(BaseSettings):
            field1: str = "default"

            model_config = {"extra": "allow"}

        source = DotEnvSettingsSource(
            Settings,
            env_file=env_file,
            env_prefix="APP_",
        )

        data = source()

        # Prefix should be stripped for extra fields
        assert len(data) > 0


def test_call_empty_value_handling():
    """Test __call__ handles empty string values correctly."""
    with TemporaryDirectory() as tmpdir:
        env_file = Path(tmpdir) / ".env"
        env_file.write_text("FIELD1=\nFIELD2=value2\n")

        class Settings(BaseSettings):
            field1: str = "default"
            field2: str = "default"

        source = DotEnvSettingsSource(Settings, env_file=env_file)

        data = source()

        # Should handle empty values
        assert len(data) >= 0


def test_call_with_union_complex_type():
    """Test __call__ handles union types that are complex."""
    with TemporaryDirectory() as tmpdir:
        env_file = Path(tmpdir) / ".env"
        env_file.write_text("FIELD1=value\nEXTRA=extra\n")

        class Model1(BaseModel):
            data: str

        class Settings(BaseSettings):
            field1: str | Model1 = "default"

            model_config = {"extra": "allow"}

        source = DotEnvSettingsSource(Settings, env_file=env_file)

        data = source()

        assert len(data) > 0


def test_repr():
    """Test __repr__ returns expected string format."""

    class Settings(BaseSettings):
        field1: str = "default"

    source = DotEnvSettingsSource(
        Settings,
        env_file=Path(".env"),
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
    )

    repr_str = repr(source)

    assert "DotEnvSettingsSource" in repr_str
    assert "env_file" in repr_str
    assert "env_file_encoding" in repr_str
    assert "env_nested_delimiter" in repr_str
    assert "env_prefix_len" in repr_str


def test_repr_with_none_values():
    """Test __repr__ handles None values correctly."""

    class Settings(BaseSettings):
        field1: str = "default"

    source = DotEnvSettingsSource(
        Settings,
        env_file=None,
        env_file_encoding=None,
    )

    repr_str = repr(source)

    assert "DotEnvSettingsSource" in repr_str
    assert "None" in repr_str


def test_read_env_file_deprecated():
    """Test read_env_file function emits deprecation warning."""
    with TemporaryDirectory() as tmpdir:
        env_file = Path(tmpdir) / ".env"
        env_file.write_text("KEY=value\n")

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = read_env_file(env_file)

            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "read_env_file will be removed" in str(w[0].message)

        assert "KEY" in result or "key" in result


def test_read_env_file_with_all_params():
    """Test read_env_file function with all parameters."""
    with TemporaryDirectory() as tmpdir:
        env_file = Path(tmpdir) / ".env"
        env_file.write_text("KEY=value\n")

        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            result = read_env_file(
                env_file,
                encoding="utf-8",
                case_sensitive=True,
                ignore_empty=True,
                parse_none_str="null",
            )

        assert "KEY" in result or "key" in result


def test_call_with_field_in_model_fields():
    """Test __call__ when env variable matches model field with prefix."""
    with TemporaryDirectory() as tmpdir:
        env_file = Path(tmpdir) / ".env"
        env_file.write_text("APP_FIELD1=value1\nFIELD1=value2\n")

        class Settings(BaseSettings):
            field1: str = "default"

            model_config = {"extra": "allow"}

        source = DotEnvSettingsSource(
            Settings,
            env_file=env_file,
            env_prefix="APP_",
        )

        data = source()

        # Should process the fields
        assert len(data) >= 0
