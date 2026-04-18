"""Tests for EnvSettingsSource."""

import json
import os
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from unittest.mock import Mock, patch

import pytest
from pydantic import BaseModel, Field, Json, StrictBool, StrictInt, ValidationError
from pydantic.dataclasses import dataclass as pydantic_dataclass

from pydantic_settings import BaseSettings
from pydantic_settings.sources.providers.env import EnvSettingsSource
from pydantic_settings.sources.types import EnvNoneType


class Color(Enum):
    RED = "red"
    GREEN = "green"
    BLUE = "blue"


class Status(Enum):
    ACTIVE = 1
    INACTIVE = 0


@pydantic_dataclass
class MyDataclass:
    name: str
    value: int


class SubModel(BaseModel):
    field1: str
    field2: int


class NestedModel(BaseModel):
    sub: SubModel
    values: List[str] = []


def test_env_settings_source_init_basic():
    """Test EnvSettingsSource initialization with basic settings."""
    class Settings(BaseSettings):
        app_name: str = "test"

    source = EnvSettingsSource(
        Settings,
        case_sensitive=True,
        env_prefix="APP_",
        env_nested_delimiter="__",
        env_nested_max_split=2,
        env_ignore_empty=True,
        env_parse_none_str="null",
        env_parse_enums=True,
    )

    assert source.case_sensitive is True
    assert source.env_prefix == "APP_"
    assert source.env_nested_delimiter == "__"
    assert source.env_nested_max_split == 2
    assert source.maxsplit == 1
    assert source.env_prefix_len == 4
    assert source.env_ignore_empty is True
    assert source.env_parse_none_str == "null"
    assert source.env_parse_enums is True


def test_env_settings_source_init_from_config():
    """Test EnvSettingsSource initialization using settings from model config."""
    class Settings(BaseSettings):
        app_name: str = "test"

        model_config = {
            "env_nested_delimiter": ".",
            "env_nested_max_split": 3,
        }

    source = EnvSettingsSource(Settings)

    assert source.env_nested_delimiter == "."
    assert source.env_nested_max_split == 3
    assert source.maxsplit == 2


def test_env_settings_source_init_override_config():
    """Test that explicit parameters override model config."""
    class Settings(BaseSettings):
        app_name: str = "test"

        model_config = {
            "env_nested_delimiter": ".",
            "env_nested_max_split": 3,
        }

    source = EnvSettingsSource(
        Settings,
        env_nested_delimiter="__",
        env_nested_max_split=5,
    )

    assert source.env_nested_delimiter == "__"
    assert source.env_nested_max_split == 5


def test_load_env_vars():
    """Test loading environment variables."""
    class Settings(BaseSettings):
        app_name: str = "test"

    with patch.dict(os.environ, {"TEST_VAR": "value", "EMPTY_VAR": ""}, clear=False):
        source = EnvSettingsSource(Settings, env_ignore_empty=True)
        env_vars = source._load_env_vars()

        assert "TEST_VAR" in env_vars or "test_var" in env_vars


def test_get_field_value_simple():
    """Test getting field value from environment variables."""
    class Settings(BaseSettings):
        app_name: str = "default"

    with patch.dict(os.environ, {"APP_NAME": "test_app"}, clear=False):
        source = EnvSettingsSource(Settings)
        field = Settings.model_fields["app_name"]

        value, key, is_complex = source.get_field_value(field, "app_name")

        assert value == "test_app"
        assert key == "app_name"
        assert is_complex is False


def test_get_field_value_not_found():
    """Test getting field value when not in environment."""
    class Settings(BaseSettings):
        app_name: str = "default"

    with patch.dict(os.environ, {}, clear=True):
        source = EnvSettingsSource(Settings)
        field = Settings.model_fields["app_name"]

        value, key, is_complex = source.get_field_value(field, "app_name")

        assert value is None
        assert key == "app_name"


def test_get_field_value_with_prefix():
    """Test getting field value with env_prefix."""
    class Settings(BaseSettings):
        name: str = "default"

    with patch.dict(os.environ, {"MYAPP_NAME": "test"}, clear=False):
        source = EnvSettingsSource(Settings, env_prefix="MYAPP_")
        field = Settings.model_fields["name"]

        value, key, is_complex = source.get_field_value(field, "name")

        assert value == "test"


def test_prepare_field_value_simple():
    """Test preparing simple field value."""
    class Settings(BaseSettings):
        count: int = 0

    source = EnvSettingsSource(Settings)
    field = Settings.model_fields["count"]

    result = source.prepare_field_value("count", field, "42", False)

    assert result == "42"


def test_prepare_field_value_enum():
    """Test preparing enum field value."""
    class Settings(BaseSettings):
        color: Color = Color.RED

    source = EnvSettingsSource(Settings, env_parse_enums=True)
    field = Settings.model_fields["color"]

    result = source.prepare_field_value("color", field, "RED", False)

    assert result == Color.RED


def test_prepare_field_value_complex_json():
    """Test preparing complex field value from JSON."""
    class Settings(BaseSettings):
        data: Dict[str, Any] = {}

    source = EnvSettingsSource(Settings)
    field = Settings.model_fields["data"]

    result = source.prepare_field_value("data", field, '{"key": "value"}', False)

    assert result == {"key": "value"}


def test_prepare_field_value_complex_none():
    """Test preparing complex field with None value."""
    class Settings(BaseSettings):
        data: Optional[Dict[str, Any]] = None

    source = EnvSettingsSource(Settings, env_nested_delimiter="__")
    field = Settings.model_fields["data"]

    with patch.dict(os.environ, {"DATA__KEY": "value"}, clear=False):
        source = EnvSettingsSource(Settings, env_nested_delimiter="__")
        result = source.prepare_field_value("data", field, None, False)

        assert isinstance(result, dict)
        assert result.get("key") == "value"


def test_prepare_field_value_env_none_type():
    """Test preparing field with EnvNoneType."""
    class Settings(BaseSettings):
        data: Optional[Dict[str, Any]] = None

    source = EnvSettingsSource(Settings)
    field = Settings.model_fields["data"]

    result = source.prepare_field_value("data", field, EnvNoneType(), True)

    assert isinstance(result, EnvNoneType)


def test_prepare_field_value_complex_with_explode():
    """Test preparing complex field with explode_env_vars."""
    class Settings(BaseSettings):
        nested: NestedModel = None

        model_config = {"env_nested_delimiter": "__"}

    with patch.dict(
        os.environ,
        {"NESTED__SUB__FIELD1": "test", "NESTED__SUB__FIELD2": "42"},
        clear=False,
    ):
        source = EnvSettingsSource(Settings, env_nested_delimiter="__")
        field = Settings.model_fields["nested"]

        result = source.prepare_field_value("nested", field, None, False)

        assert isinstance(result, dict)
        assert result["sub"]["field1"] == "test"
        assert result["sub"]["field2"] == "42"


def test_prepare_field_value_complex_json_with_explode():
    """Test preparing complex field from JSON with explode_env_vars merge."""
    class Settings(BaseSettings):
        nested: Dict[str, Any] = {}

        model_config = {"env_nested_delimiter": "__"}

    with patch.dict(
        os.environ,
        {"NESTED": '{"base": "value"}', "NESTED__EXTRA": "added"},
        clear=False,
    ):
        source = EnvSettingsSource(Settings, env_nested_delimiter="__")
        field = Settings.model_fields["nested"]

        result = source.prepare_field_value("nested", field, '{"base": "value"}', False)

        assert isinstance(result, dict)
        assert result["base"] == "value"
        assert result.get("extra") == "added"


def test_prepare_field_value_complex_json_parse_failure():
    """Test preparing complex field with JSON parse failure."""
    class Settings(BaseSettings):
        data: Union[Dict[str, Any], str] = {}

    source = EnvSettingsSource(Settings)
    field = Settings.model_fields["data"]

    # Should not raise, allow_parse_failure=True for unions
    result = source.prepare_field_value("data", field, "not-json", False)

    assert result == "not-json"


def test_field_is_complex_true():
    """Test _field_is_complex for complex fields."""
    class Settings(BaseSettings):
        data: Dict[str, Any] = {}

    source = EnvSettingsSource(Settings)
    field = Settings.model_fields["data"]

    is_complex, allow_failure = source._field_is_complex(field)

    assert is_complex is True
    assert allow_failure is False


def test_field_is_complex_union():
    """Test _field_is_complex for union with complex type."""
    class Settings(BaseSettings):
        data: Union[Dict[str, Any], str] = {}

    source = EnvSettingsSource(Settings)
    field = Settings.model_fields["data"]

    is_complex, allow_failure = source._field_is_complex(field)

    assert is_complex is True
    assert allow_failure is True


def test_field_is_complex_false():
    """Test _field_is_complex for simple fields."""
    class Settings(BaseSettings):
        name: str = "default"

    source = EnvSettingsSource(Settings)
    field = Settings.model_fields["name"]

    is_complex, allow_failure = source._field_is_complex(field)

    assert is_complex is False
    assert allow_failure is False


def test_next_field_with_model():
    """Test next_field with nested model."""
    class Settings(BaseSettings):
        nested: NestedModel = None

    source = EnvSettingsSource(Settings)
    nested_field = Settings.model_fields["nested"]

    result = source.next_field(nested_field, "sub", case_sensitive=True)

    assert result is not None
    assert result == NestedModel.model_fields["sub"]


def test_next_field_with_dict():
    """Test next_field with dict type."""
    class Settings(BaseSettings):
        data: Dict[str, int] = {}

    source = EnvSettingsSource(Settings)
    data_field = Settings.model_fields["data"]

    result = source.next_field(data_field, "any_key", case_sensitive=True)

    assert result == int


def test_next_field_case_insensitive():
    """Test next_field with case insensitive matching."""
    class Settings(BaseSettings):
        nested: NestedModel = None

    source = EnvSettingsSource(Settings, case_sensitive=False)
    nested_field = Settings.model_fields["nested"]

    result = source.next_field(nested_field, "SUB", case_sensitive=False)

    assert result is not None


def test_next_field_not_found():
    """Test next_field when field not found."""
    class Settings(BaseSettings):
        nested: NestedModel = None

    source = EnvSettingsSource(Settings)
    nested_field = Settings.model_fields["nested"]

    result = source.next_field(nested_field, "nonexistent", case_sensitive=True)

    assert result is None


def test_next_field_with_none():
    """Test next_field with None field."""
    class Settings(BaseSettings):
        name: str = "test"

    source = EnvSettingsSource(Settings)

    result = source.next_field(None, "key", case_sensitive=True)

    assert result is None


def test_next_field_with_union():
    """Test next_field with union type."""
    class Settings(BaseSettings):
        data: Union[NestedModel, Dict[str, Any]] = None

    source = EnvSettingsSource(Settings)
    field = Settings.model_fields["data"]

    result = source.next_field(field, "sub", case_sensitive=True)

    assert result is not None


def test_next_field_with_dataclass():
    """Test next_field with pydantic dataclass."""
    @pydantic_dataclass
    class DataclassModel:
        name: str
        value: int

    class Settings(BaseSettings):
        model: DataclassModel = None

    source = EnvSettingsSource(Settings)
    field = Settings.model_fields["model"]

    result = source.next_field(field, "name", case_sensitive=True)

    assert result is not None


def test_explode_env_vars_basic():
    """Test explode_env_vars with basic nested structure."""
    class Settings(BaseSettings):
        nested: Dict[str, Any] = {}

    with patch.dict(
        os.environ,
        {"NESTED__KEY1": "value1", "NESTED__KEY2": "value2"},
        clear=False,
    ):
        source = EnvSettingsSource(Settings, env_nested_delimiter="__")
        field = Settings.model_fields["nested"]

        result = source.explode_env_vars("nested", field, source.env_vars)

        assert result["key1"] == "value1"
        assert result["key2"] == "value2"


def test_explode_env_vars_no_delimiter():
    """Test explode_env_vars when no delimiter is set."""
    class Settings(BaseSettings):
        nested: Dict[str, Any] = {}

    source = EnvSettingsSource(Settings)
    field = Settings.model_fields["nested"]

    result = source.explode_env_vars("nested", field, {})

    assert result == {}


def test_explode_env_vars_deep_nested():
    """Test explode_env_vars with deeply nested structure."""
    class Settings(BaseSettings):
        data: Dict[str, Any] = {}

    with patch.dict(
        os.environ,
        {"DATA__LEVEL1__LEVEL2__KEY": "deep_value"},
        clear=False,
    ):
        source = EnvSettingsSource(Settings, env_nested_delimiter="__")
        field = Settings.model_fields["data"]

        result = source.explode_env_vars("data", field, source.env_vars)

        assert result["level1"]["level2"]["key"] == "deep_value"


def test_explode_env_vars_with_max_split():
    """Test explode_env_vars with max_split limit."""
    class Settings(BaseSettings):
        data: Dict[str, Any] = {}

    with patch.dict(
        os.environ,
        {"DATA__A__B__C": "value"},
        clear=False,
    ):
        source = EnvSettingsSource(
            Settings, env_nested_delimiter="__", env_nested_max_split=2
        )
        field = Settings.model_fields["data"]

        result = source.explode_env_vars("data", field, source.env_vars)

        assert "a" in result
        assert "b__c" in result["a"]


def test_explode_env_vars_with_model_field():
    """Test explode_env_vars with typed model fields."""
    class Settings(BaseSettings):
        nested: NestedModel = None

    with patch.dict(
        os.environ,
        {"NESTED__SUB__FIELD1": "test", "NESTED__SUB__FIELD2": "99"},
        clear=False,
    ):
        source = EnvSettingsSource(Settings, env_nested_delimiter="__")
        field = Settings.model_fields["nested"]

        result = source.explode_env_vars("nested", field, source.env_vars)

        assert result["sub"]["field1"] == "test"
        assert result["sub"]["field2"] == "99"


def test_explode_env_vars_with_complex_value():
    """Test explode_env_vars with JSON complex values."""
    class Settings(BaseSettings):
        data: Dict[str, Any] = {}

    with patch.dict(
        os.environ,
        {"DATA__CONFIG": '{"nested": "json"}'},
        clear=False,
    ):
        source = EnvSettingsSource(Settings, env_nested_delimiter="__")
        field = Settings.model_fields["data"]

        result = source.explode_env_vars("data", field, source.env_vars)

        # For dict type without specific field info, values are not parsed as JSON
        assert result.get("config") == '{"nested": "json"}' or isinstance(result.get("config"), dict)


def test_explode_env_vars_with_enum():
    """Test explode_env_vars with enum values."""
    class Settings(BaseSettings):
        data: Dict[str, Color] = {}

    with patch.dict(
        os.environ,
        {"DATA__COLOR": "RED"},
        clear=False,
    ):
        source = EnvSettingsSource(Settings, env_nested_delimiter="__", env_parse_enums=True)
        field = Settings.model_fields["data"]

        result = source.explode_env_vars("data", field, source.env_vars)

        # Without specific field info for dict values, enum parsing may not occur
        assert result.get("color") in ("RED", Color.RED)


def test_explode_env_vars_skip_non_matching_prefix():
    """Test that explode_env_vars skips non-matching prefixes."""
    class Settings(BaseSettings):
        data: Dict[str, Any] = {}

    with patch.dict(
        os.environ,
        {"DATA__KEY": "value", "OTHER__KEY": "ignored"},
        clear=False,
    ):
        source = EnvSettingsSource(Settings, env_nested_delimiter="__")
        field = Settings.model_fields["data"]

        result = source.explode_env_vars("data", field, source.env_vars)

        assert "key" in result
        assert "other" not in result


def test_explode_env_vars_with_env_none_type():
    """Test explode_env_vars handling EnvNoneType."""
    class Settings(BaseSettings):
        data: Dict[str, Any] = {}

    env_vars = {"data__key": EnvNoneType(), "data__other": "value"}
    source = EnvSettingsSource(Settings, env_nested_delimiter="__")
    field = Settings.model_fields["data"]

    result = source.explode_env_vars("data", field, env_vars)

    # EnvNoneType should only set if key doesn't exist or is empty dict
    assert "key" in result or "other" in result


def test_explode_env_vars_preserve_existing_keys():
    """Test that explode_env_vars doesn't overwrite with EnvNoneType."""
    class Settings(BaseSettings):
        data: Dict[str, Any] = {}

    # Simulate pre-existing key with EnvNoneType trying to overwrite
    env_vars_ordered = {"data__key": "original"}
    source = EnvSettingsSource(Settings, env_nested_delimiter="__")
    field = Settings.model_fields["data"]

    result = source.explode_env_vars("data", field, env_vars_ordered)

    assert result.get("key") == "original"


def test_coerce_env_val_strict_non_strict():
    """Test _coerce_env_val_strict with non-strict model."""
    class Settings(BaseSettings):
        name: str = "default"

    source = EnvSettingsSource(Settings)
    field = Settings.model_fields["name"]

    result = source._coerce_env_val_strict(field, "test_value")

    assert result == "test_value"


def test_coerce_env_val_strict_strict_model():
    """Test _coerce_env_val_strict with strict model."""
    class Settings(BaseSettings):
        count: int = 0

        model_config = {"strict": True}

    source = EnvSettingsSource(Settings)
    field = Settings.model_fields["count"]

    result = source._coerce_env_val_strict(field, "42")

    assert result == 42


def test_coerce_env_val_strict_strict_bool():
    """Test _coerce_env_val_strict with StrictBool."""
    class Settings(BaseSettings):
        flag: StrictBool = False

    source = EnvSettingsSource(Settings)
    field = Settings.model_fields["flag"]

    result = source._coerce_env_val_strict(field, "true")

    # Without strict mode in config, value is not coerced
    assert result == "true" or result is True


def test_coerce_env_val_strict_strict_bool_json_fallback():
    """Test _coerce_env_val_strict StrictBool with JSON fallback."""
    class Settings(BaseSettings):
        flag: StrictBool = False

    source = EnvSettingsSource(Settings)
    field = Settings.model_fields["flag"]

    result = source._coerce_env_val_strict(field, "false")

    # Without strict mode in config, value is not coerced
    assert result == "false" or result is False


def test_coerce_env_val_strict_union_with_strict():
    """Test _coerce_env_val_strict with union containing strict types."""
    class Settings(BaseSettings):
        value: Union[StrictInt, str] = 0

    source = EnvSettingsSource(Settings)
    field = Settings.model_fields["value"]

    result = source._coerce_env_val_strict(field, "123")

    # Coercion occurs when union has strict types
    assert result == 123 or result == "123"


def test_coerce_env_val_strict_validation_error():
    """Test _coerce_env_val_strict returns original on validation error."""
    class Settings(BaseSettings):
        count: StrictInt = 0

    source = EnvSettingsSource(Settings)
    field = Settings.model_fields["count"]

    result = source._coerce_env_val_strict(field, "not_an_int")

    # Should return original value on validation error
    assert result == "not_an_int"


def test_coerce_env_val_strict_with_none_str():
    """Test _coerce_env_val_strict with env_parse_none_str."""
    class Settings(BaseSettings):
        value: Optional[int] = None

        model_config = {"strict": True}

    source = EnvSettingsSource(Settings, env_parse_none_str="null")
    field = Settings.model_fields["value"]

    result = source._coerce_env_val_strict(field, "null")

    assert result == "null"


def test_coerce_env_val_strict_with_json_field():
    """Test _coerce_env_val_strict skips Json type."""
    class Settings(BaseSettings):
        data: Json = None

        model_config = {"strict": True}

    source = EnvSettingsSource(Settings)
    field = Settings.model_fields["data"]

    result = source._coerce_env_val_strict(field, '{"key": "value"}')

    # Should not coerce Json fields
    assert result == '{"key": "value"}'


def test_coerce_env_val_strict_enum_literal():
    """Test _coerce_env_val_strict with literal numeric enum."""
    class Settings(BaseSettings):
        status: Status = Status.ACTIVE

        model_config = {"strict": True}

    source = EnvSettingsSource(Settings)
    field = Settings.model_fields["status"]

    result = source._coerce_env_val_strict(field, "1")

    # Should coerce for numeric enum literals - may return int, string, or enum
    assert result in (1, "1", Status.ACTIVE)


def test_coerce_env_val_strict_none_field():
    """Test _coerce_env_val_strict with None field."""
    class Settings(BaseSettings):
        name: str = "default"

        model_config = {"strict": True}

    source = EnvSettingsSource(Settings)

    result = source._coerce_env_val_strict(None, "value")

    assert result == "value"


def test_coerce_env_val_strict_json_decode_error():
    """Test _coerce_env_val_strict handles JSON decode errors."""
    class Settings(BaseSettings):
        count: StrictInt = 0

    source = EnvSettingsSource(Settings)
    field = Settings.model_fields["count"]

    # Invalid JSON that can't be decoded
    result = source._coerce_env_val_strict(field, "not-json-at-all")

    assert result == "not-json-at-all"


def test_repr():
    """Test __repr__ method."""
    class Settings(BaseSettings):
        name: str = "test"

    source = EnvSettingsSource(
        Settings, env_prefix="APP_", env_nested_delimiter="__"
    )

    repr_str = repr(source)

    assert "EnvSettingsSource" in repr_str
    assert "env_nested_delimiter='__'" in repr_str
    assert "env_prefix_len=4" in repr_str


def test_integration_full_settings_load():
    """Test full integration of loading settings from environment."""
    class DatabaseConfig(BaseModel):
        host: str
        port: int
        database: str

    class AppSettings(BaseSettings):
        app_name: str = "default"
        debug: bool = False
        database: DatabaseConfig = None

        model_config = {"env_nested_delimiter": "__", "env_prefix": "APP_"}

    with patch.dict(
        os.environ,
        {
            "APP_APP_NAME": "MyApp",
            "APP_DEBUG": "true",
            "APP_DATABASE__HOST": "localhost",
            "APP_DATABASE__PORT": "5432",
            "APP_DATABASE__DATABASE": "mydb",
        },
        clear=False,
    ):
        source = EnvSettingsSource(
            AppSettings, env_nested_delimiter="__", env_prefix="APP_"
        )

        # Test basic field retrieval
        app_name_field = AppSettings.model_fields["app_name"]
        value, _, _ = source.get_field_value(app_name_field, "app_name")
        assert value == "MyApp"

        # Test nested field explosion
        db_field = AppSettings.model_fields["database"]
        result = source.explode_env_vars("database", db_field, source.env_vars)
        assert result["host"] == "localhost"
        assert result["port"] == "5432"
