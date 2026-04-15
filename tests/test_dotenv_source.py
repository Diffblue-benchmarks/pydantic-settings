"""Tests for DotEnvSettingsSource and read_env_file."""

import warnings
from pathlib import Path

import pytest
from pydantic import Field

from pydantic_settings import BaseSettings
from pydantic_settings.sources.providers.dotenv import DotEnvSettingsSource, read_env_file
from pydantic_settings.sources.types import EnvNoneType


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_env_file(tmp_path):
    """Return a factory that creates .env files in a temporary directory."""

    def _make(content: str, name: str = ".env") -> Path:
        p = tmp_path / name
        p.write_text(content)
        return p

    return _make


class SimpleSettings(BaseSettings):
    model_config = {"env_file": None}

    name: str = "default"
    value: int = 0


class PrefixSettings(BaseSettings):
    model_config = {"env_prefix": "APP_", "env_file": None}

    name: str = "default"


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------


def test_init_uses_sentinel_env_file_from_model_config(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("NAME=hello\n")

    class S(BaseSettings):
        model_config = {"env_file": str(env_file)}
        name: str = "default"

    src = DotEnvSettingsSource(S)
    assert src.env_file == str(env_file)


def test_init_explicit_env_file_overrides_model_config(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("")

    class S(BaseSettings):
        model_config = {"env_file": "other.env"}
        name: str = "default"

    src = DotEnvSettingsSource(S, env_file=str(env_file))
    assert src.env_file == str(env_file)


def test_init_env_file_none_disables_loading():
    src = DotEnvSettingsSource(SimpleSettings, env_file=None)
    assert src.env_file is None


def test_init_encoding_from_model_config():
    class S(BaseSettings):
        model_config = {"env_file": None, "env_file_encoding": "latin-1"}
        name: str = "default"

    src = DotEnvSettingsSource(S)
    assert src.env_file_encoding == "latin-1"


def test_init_explicit_encoding_overrides_model_config():
    class S(BaseSettings):
        model_config = {"env_file": None, "env_file_encoding": "latin-1"}
        name: str = "default"

    src = DotEnvSettingsSource(S, env_file_encoding="utf-8")
    assert src.env_file_encoding == "utf-8"


def test_init_dotenv_filtering_from_model_config():
    class S(BaseSettings):
        model_config = {"env_file": None, "dotenv_filtering": "only_existing"}
        name: str = "default"

    src = DotEnvSettingsSource(S)
    assert src.dotenv_filtering == "only_existing"


def test_init_explicit_dotenv_filtering_overrides_model_config():
    class S(BaseSettings):
        model_config = {"env_file": None, "dotenv_filtering": "only_existing"}
        name: str = "default"

    src = DotEnvSettingsSource(S, dotenv_filtering="match_prefix")
    assert src.dotenv_filtering == "match_prefix"


# ---------------------------------------------------------------------------
# _load_env_vars
# ---------------------------------------------------------------------------


def test_load_env_vars_returns_mapping_from_file(tmp_env_file):
    env_path = tmp_env_file("NAME=world\nVALUE=42\n")

    class S(BaseSettings):
        model_config = {"env_file": None}
        name: str = "default"
        value: int = 0

    src = DotEnvSettingsSource(S, env_file=str(env_path))
    result = src._load_env_vars()
    assert result.get("name") == "world"
    assert result.get("value") == "42"


def test_load_env_vars_returns_empty_when_no_file():
    src = DotEnvSettingsSource(SimpleSettings, env_file=None)
    result = src._load_env_vars()
    assert dict(result) == {}


# ---------------------------------------------------------------------------
# _static_read_env_file
# ---------------------------------------------------------------------------


def test_static_read_env_file_basic(tmp_env_file):
    env_path = tmp_env_file("KEY=val\nOTHER=123\n")
    result = DotEnvSettingsSource._static_read_env_file(env_path)
    assert result["key"] == "val"
    assert result["other"] == "123"


def test_static_read_env_file_case_sensitive(tmp_env_file):
    env_path = tmp_env_file("KEY=val\n")
    result = DotEnvSettingsSource._static_read_env_file(env_path, case_sensitive=True)
    assert "KEY" in result
    assert "key" not in result


def test_static_read_env_file_ignore_empty(tmp_env_file):
    env_path = tmp_env_file("KEY=\nOTHER=val\n")
    result = DotEnvSettingsSource._static_read_env_file(env_path, ignore_empty=True)
    assert "key" not in result
    assert result.get("other") == "val"


def test_static_read_env_file_parse_none_str(tmp_env_file):
    env_path = tmp_env_file("KEY=null\n")
    result = DotEnvSettingsSource._static_read_env_file(env_path, parse_none_str="null")
    assert isinstance(result["key"], EnvNoneType)


# ---------------------------------------------------------------------------
# _read_env_file
# ---------------------------------------------------------------------------


def test_read_env_file_delegates_to_static(tmp_env_file):
    env_path = tmp_env_file("KEY=hello\n")
    src = DotEnvSettingsSource(SimpleSettings, env_file=None)
    result = src._read_env_file(env_path)
    assert result.get("key") == "hello"


def test_read_env_file_uses_source_encoding(tmp_env_file):
    env_path = tmp_env_file("KEY=hello\n")
    src = DotEnvSettingsSource(SimpleSettings, env_file=None, env_file_encoding="utf-8")
    result = src._read_env_file(env_path)
    assert result.get("key") == "hello"


# ---------------------------------------------------------------------------
# _read_env_files
# ---------------------------------------------------------------------------


def test_read_env_files_none_returns_empty():
    src = DotEnvSettingsSource(SimpleSettings, env_file=None)
    result = src._read_env_files()
    assert dict(result) == {}


def test_read_env_files_single_string(tmp_env_file):
    env_path = tmp_env_file("NAME=hi\n")
    src = DotEnvSettingsSource(SimpleSettings, env_file=str(env_path))
    result = src._read_env_files()
    assert result.get("name") == "hi"


def test_read_env_files_path_object(tmp_env_file):
    env_path = tmp_env_file("NAME=frompath\n")
    src = DotEnvSettingsSource(SimpleSettings, env_file=env_path)
    result = src._read_env_files()
    assert result.get("name") == "frompath"


def test_read_env_files_list_of_files(tmp_path):
    f1 = tmp_path / ".env.base"
    f1.write_text("KEY1=a\n")
    f2 = tmp_path / ".env.override"
    f2.write_text("KEY2=b\n")
    src = DotEnvSettingsSource(SimpleSettings, env_file=[str(f1), str(f2)])
    result = src._read_env_files()
    assert result.get("key1") == "a"
    assert result.get("key2") == "b"


def test_read_env_files_later_file_overrides_earlier(tmp_path):
    f1 = tmp_path / ".env.base"
    f1.write_text("NAME=first\n")
    f2 = tmp_path / ".env.override"
    f2.write_text("NAME=second\n")
    src = DotEnvSettingsSource(SimpleSettings, env_file=[str(f1), str(f2)])
    result = src._read_env_files()
    assert result.get("name") == "second"


def test_read_env_files_nonexistent_file_is_skipped(tmp_path):
    src = DotEnvSettingsSource(SimpleSettings, env_file=str(tmp_path / "nonexistent.env"))
    result = src._read_env_files()
    assert dict(result) == {}


# ---------------------------------------------------------------------------
# __call__
# ---------------------------------------------------------------------------


def test_call_returns_known_fields(tmp_env_file):
    env_path = tmp_env_file("NAME=loaded\nVALUE=7\n")

    class S(BaseSettings):
        model_config = {"env_file": None}
        name: str = "default"
        value: int = 0

    src = DotEnvSettingsSource(S, env_file=str(env_path))
    result = src()
    assert result["name"] == "loaded"
    assert result["value"] == "7"


def test_call_extra_vars_included_when_extra_allowed(tmp_env_file):
    env_path = tmp_env_file("EXTRA_KEY=extra_val\n")

    class S(BaseSettings):
        model_config = {"env_file": None, "extra": "allow"}
        name: str = "default"

    src = DotEnvSettingsSource(S, env_file=str(env_path))
    result = src()
    assert "extra_key" in result


def test_call_dotenv_filtering_only_existing(tmp_env_file):
    env_path = tmp_env_file("NAME=fromfile\nUNKNOWN=extra\n")

    class S(BaseSettings):
        model_config = {"env_file": None, "extra": "allow"}
        name: str = "default"

    src = DotEnvSettingsSource(S, env_file=str(env_path), dotenv_filtering="only_existing")
    result = src()
    # With only_existing filtering, only model fields are returned
    assert "name" in result


def test_call_dotenv_filtering_match_prefix(tmp_env_file):
    env_path = tmp_env_file("APP_NAME=prefixed\nOTHER=ignored\n")

    class S(BaseSettings):
        model_config = {"env_file": None, "env_prefix": "APP_"}
        name: str = "default"

    src = DotEnvSettingsSource(S, env_file=str(env_path), dotenv_filtering="match_prefix")
    result = src()
    assert "name" in result
    assert result["name"] == "prefixed"


def test_call_with_env_prefix_strips_prefix_for_extra(tmp_env_file):
    env_path = tmp_env_file("APP_EXTRA=val\n")

    class S(BaseSettings):
        model_config = {"env_file": None, "env_prefix": "APP_", "extra": "allow"}
        name: str = "default"

    src = DotEnvSettingsSource(S, env_file=str(env_path))
    result = src()
    # Without case-sensitive matching, env_name is lowercased ('app_extra')
    # which doesn't match prefix 'APP_', so it is stored under the raw env_name key
    assert "app_extra" in result


# ---------------------------------------------------------------------------
# __repr__
# ---------------------------------------------------------------------------


def test_repr_contains_env_file():
    src = DotEnvSettingsSource(SimpleSettings, env_file="my.env")
    r = repr(src)
    assert "DotEnvSettingsSource" in r
    assert "my.env" in r
    assert "env_file_encoding" in r
    assert "env_nested_delimiter" in r
    assert "env_prefix_len" in r


def test_repr_with_none_env_file():
    src = DotEnvSettingsSource(SimpleSettings, env_file=None)
    r = repr(src)
    assert "None" in r


# ---------------------------------------------------------------------------
# read_env_file (deprecated function)
# ---------------------------------------------------------------------------


def test_read_env_file_deprecated_warning(tmp_env_file):
    env_path = tmp_env_file("KEY=val\n")
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = read_env_file(env_path)
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert "read_env_file" in str(w[0].message)
    assert result.get("key") == "val"


def test_read_env_file_deprecated_case_sensitive(tmp_env_file):
    env_path = tmp_env_file("MYKEY=val\n")
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        result = read_env_file(env_path, case_sensitive=True)
    assert "MYKEY" in result
    assert "mykey" not in result


def test_read_env_file_deprecated_ignore_empty(tmp_env_file):
    env_path = tmp_env_file("MYKEY=\n")
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        result = read_env_file(env_path, ignore_empty=True)
    assert "mykey" not in result


def test_read_env_file_deprecated_parse_none_str(tmp_env_file):
    env_path = tmp_env_file("MYKEY=null\n")
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        result = read_env_file(env_path, parse_none_str="null")
    assert isinstance(result.get("mykey"), EnvNoneType)
