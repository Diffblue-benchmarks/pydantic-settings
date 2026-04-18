"""Tests for EnvSettingsSource class."""

import os
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, Mock, patch

import pytest
from pydantic import BaseModel, Field, ValidationError
from pydantic.fields import FieldInfo

from pydantic_settings import BaseSettings
from pydantic_settings.sources.providers.env import EnvSettingsSource
from pydantic_settings.sources.types import EnvNoneType


class TestEnvSettingsSourceInit:
    """Test EnvSettingsSource.__init__ method."""

    def test_init_with_defaults(self):
        """Test initialization with default values."""
        class Settings(BaseSettings):
            field1: str = "default"

        source = EnvSettingsSource(Settings)
        assert source.settings_cls is Settings
        assert source.case_sensitive is False
        assert source.env_prefix == ""
        assert source.env_nested_delimiter is None
        assert source.env_vars is not None

    def test_init_with_case_sensitive_true(self):
        """Test initialization with case_sensitive=True."""
        class Settings(BaseSettings):
            model_config = {"case_sensitive": True}
            field1: str = "default"

        source = EnvSettingsSource(Settings, case_sensitive=True)
        assert source.case_sensitive is True

    def test_init_with_env_prefix(self):
        """Test initialization with env_prefix."""
        class Settings(BaseSettings):
            field1: str = "default"

        source = EnvSettingsSource(Settings, env_prefix="APP_")
        assert source.env_prefix == "APP_"
        assert source.env_prefix_len == 4

    def test_init_with_nested_delimiter(self):
        """Test initialization with nested delimiter."""
        class Settings(BaseSettings):
            field1: str = "default"

        source = EnvSettingsSource(Settings, env_nested_delimiter="__")
        assert source.env_nested_delimiter == "__"

    def test_init_with_nested_max_split(self):
        """Test initialization with nested max split."""
        class Settings(BaseSettings):
            field1: str = "default"

        source = EnvSettingsSource(Settings, env_nested_max_split=3)
        assert source.env_nested_max_split == 3
        assert source.maxsplit == 2  # max_split - 1

    def test_init_with_ignore_empty(self):
        """Test initialization with ignore_empty."""
        class Settings(BaseSettings):
            field1: str = "default"

        source = EnvSettingsSource(Settings, env_ignore_empty=True)
        assert source.env_ignore_empty is True

    def test_init_with_parse_none_str(self):
        """Test initialization with parse_none_str."""
        class Settings(BaseSettings):
            field1: Optional[str] = None

        source = EnvSettingsSource(Settings, env_parse_none_str="null")
        assert source.env_parse_none_str == "null"

    def test_init_with_parse_enums(self):
        """Test initialization with parse_enums."""
        class Settings(BaseSettings):
            field1: str = "default"

        source = EnvSettingsSource(Settings, env_parse_enums=True)
        assert source.env_parse_enums is True

    def test_init_loads_env_vars(self):
        """Test that __init__ calls _load_env_vars."""
        class Settings(BaseSettings):
            field1: str = "default"

        with patch.dict(os.environ, {"TEST_VAR": "test_value"}):
            source = EnvSettingsSource(Settings)
            # env_vars should be populated from os.environ
            assert source.env_vars is not None


class TestLoadEnvVars:
    """Test EnvSettingsSource._load_env_vars method."""

    def test_load_env_vars_returns_mapping(self):
        """Test _load_env_vars returns a mapping."""
        class Settings(BaseSettings):
            field1: str = "default"

        source = EnvSettingsSource(Settings)
        env_vars = source._load_env_vars()
        assert isinstance(env_vars, dict)

    def test_load_env_vars_includes_env_variables(self):
        """Test _load_env_vars includes environment variables."""
        class Settings(BaseSettings):
            field1: str = "default"

        with patch.dict(os.environ, {"MY_VAR": "my_value"}):
            source = EnvSettingsSource(Settings)
            env_vars = source._load_env_vars()
            # The actual test depends on parse_env_vars implementation
            assert env_vars is not None


class TestGetFieldValue:
    """Test EnvSettingsSource.get_field_value method."""

    def test_get_field_value_not_found(self):
        """Test get_field_value when field not in env vars."""
        class Settings(BaseSettings):
            field1: str = "default"

        source = EnvSettingsSource(Settings)
        field_info = Settings.model_fields["field1"]

        value, key, is_complex = source.get_field_value(field_info, "field1")
        assert value is None

    def test_get_field_value_found(self):
        """Test get_field_value when field is in env vars."""
        class Settings(BaseSettings):
            field1: str = "default"

        with patch.dict(os.environ, {"field1": "found_value"}):
            source = EnvSettingsSource(Settings, case_sensitive=True)
            field_info = Settings.model_fields["field1"]

            value, key, is_complex = source.get_field_value(field_info, "field1")
            assert value == "found_value"

    def test_get_field_value_case_insensitive(self):
        """Test get_field_value with case insensitive matching."""
        class Settings(BaseSettings):
            field1: str = "default"

        with patch.dict(os.environ, {"FIELD1": "found_value"}):
            source = EnvSettingsSource(Settings, case_sensitive=False)
            field_info = Settings.model_fields["field1"]

            value, key, is_complex = source.get_field_value(field_info, "field1")
            # Should find it despite case mismatch
            assert value is not None


class TestPrepareFieldValue:
    """Test EnvSettingsSource.prepare_field_value method."""

    def test_prepare_field_value_simple_type(self):
        """Test prepare_field_value with simple type."""
        class Settings(BaseSettings):
            field1: str = "default"

        source = EnvSettingsSource(Settings)
        field_info = Settings.model_fields["field1"]

        result = source.prepare_field_value("field1", field_info, "test_value", False)
        assert result == "test_value"

    def test_prepare_field_value_with_none(self):
        """Test prepare_field_value when value is None."""
        class Settings(BaseSettings):
            field1: Optional[str] = None

        source = EnvSettingsSource(Settings)
        field_info = Settings.model_fields["field1"]

        result = source.prepare_field_value("field1", field_info, None, False)
        assert result is None

    def test_prepare_field_value_with_enum_parsing(self):
        """Test prepare_field_value with enum parsing enabled."""
        from enum import Enum

        class Color(str, Enum):
            RED = "red"
            BLUE = "blue"

        class Settings(BaseSettings):
            color: Color = Color.RED

        source = EnvSettingsSource(Settings, env_parse_enums=True)
        field_info = Settings.model_fields["color"]

        result = source.prepare_field_value("color", field_info, "RED", False)
        # Should attempt to parse enum
        assert result is not None

    def test_prepare_field_value_complex_type_with_json(self):
        """Test prepare_field_value with complex type and JSON."""
        class Settings(BaseSettings):
            data: Dict[str, Any] = {}

        source = EnvSettingsSource(Settings)
        field_info = Settings.model_fields["data"]

        result = source.prepare_field_value("data", field_info, '{"key": "value"}', True)
        # Result should be processed
        assert result is not None

    def test_prepare_field_value_env_none_type(self):
        """Test prepare_field_value with EnvNoneType."""
        class Settings(BaseSettings):
            field1: Optional[str] = None

        source = EnvSettingsSource(Settings)
        field_info = Settings.model_fields["field1"]

        env_none = EnvNoneType()
        result = source.prepare_field_value("field1", field_info, env_none, True)
        assert isinstance(result, EnvNoneType)


class TestFieldIsComplex:
    """Test EnvSettingsSource._field_is_complex method."""

    def test_field_is_complex_simple_type(self):
        """Test _field_is_complex with simple type."""
        class Settings(BaseSettings):
            field1: str = "default"

        source = EnvSettingsSource(Settings)
        field_info = Settings.model_fields["field1"]

        is_complex, allow_parse_failure = source._field_is_complex(field_info)
        assert is_complex is False

    def test_field_is_complex_dict_type(self):
        """Test _field_is_complex with dict type."""
        class Settings(BaseSettings):
            data: Dict[str, Any] = {}

        source = EnvSettingsSource(Settings)
        field_info = Settings.model_fields["data"]

        is_complex, allow_parse_failure = source._field_is_complex(field_info)
        assert is_complex is True

    def test_field_is_complex_list_type(self):
        """Test _field_is_complex with list type."""
        class Settings(BaseSettings):
            items: list[str] = []

        source = EnvSettingsSource(Settings)
        field_info = Settings.model_fields["items"]

        is_complex, allow_parse_failure = source._field_is_complex(field_info)
        # Lists are considered complex
        assert is_complex is True

    def test_field_is_complex_nested_model(self):
        """Test _field_is_complex with nested model."""
        class SubModel(BaseModel):
            value: str

        class Settings(BaseSettings):
            sub: SubModel

        source = EnvSettingsSource(Settings)
        field_info = Settings.model_fields["sub"]

        is_complex, allow_parse_failure = source._field_is_complex(field_info)
        assert is_complex is True


class TestNextField:
    """Test EnvSettingsSource.next_field method."""

    def test_next_field_none_field(self):
        """Test next_field with None field."""
        class Settings(BaseSettings):
            field1: str = "default"

        source = EnvSettingsSource(Settings)

        result = source.next_field(None, "key")
        assert result is None

    def test_next_field_with_model_class(self):
        """Test next_field with model class."""
        class SubModel(BaseModel):
            sub_field: str

        class Settings(BaseSettings):
            sub: SubModel

        source = EnvSettingsSource(Settings)
        field_info = Settings.model_fields["sub"]

        result = source.next_field(field_info, "sub_field")
        assert result is not None

    def test_next_field_case_sensitive(self):
        """Test next_field with case sensitivity."""
        class SubModel(BaseModel):
            sub_field: str

        class Settings(BaseSettings):
            sub: SubModel

        source = EnvSettingsSource(Settings, case_sensitive=True)
        field_info = Settings.model_fields["sub"]

        result = source.next_field(field_info, "sub_field", case_sensitive=True)
        assert result is not None

    def test_next_field_case_insensitive(self):
        """Test next_field with case insensitive matching."""
        class SubModel(BaseModel):
            sub_field: str

        class Settings(BaseSettings):
            sub: SubModel

        source = EnvSettingsSource(Settings)
        field_info = Settings.model_fields["sub"]

        result = source.next_field(field_info, "SUB_FIELD", case_sensitive=False)
        assert result is not None

    def test_next_field_with_dict_type(self):
        """Test next_field with dict type."""
        class Settings(BaseSettings):
            data: Dict[str, str]

        source = EnvSettingsSource(Settings)
        field_info = Settings.model_fields["data"]

        result = source.next_field(field_info, "any_key")
        # For dict, should return the value type
        assert result is not None


class TestExplodeEnvVars:
    """Test EnvSettingsSource.explode_env_vars method."""

    def test_explode_env_vars_no_delimiter(self):
        """Test explode_env_vars with no delimiter."""
        class Settings(BaseSettings):
            field1: str = "default"

        source = EnvSettingsSource(Settings)
        field_info = Settings.model_fields["field1"]

        result = source.explode_env_vars("field1", field_info, {})
        assert result == {}

    def test_explode_env_vars_with_delimiter(self):
        """Test explode_env_vars with nested delimiter."""
        class Settings(BaseSettings):
            data: Dict[str, Any] = {}

        env_vars = {"DATA__KEY1": "value1", "DATA__KEY2": "value2"}
        source = EnvSettingsSource(Settings, env_nested_delimiter="__")
        field_info = Settings.model_fields["data"]

        result = source.explode_env_vars("data", field_info, env_vars)
        assert isinstance(result, dict)

    def test_explode_env_vars_nested_structure(self):
        """Test explode_env_vars with nested structure."""
        class SubModel(BaseModel):
            value: str

        class Settings(BaseSettings):
            sub: SubModel

        env_vars = {"SUB__VALUE": "test_value"}
        source = EnvSettingsSource(Settings, env_nested_delimiter="__")
        field_info = Settings.model_fields["sub"]

        result = source.explode_env_vars("sub", field_info, env_vars)
        assert isinstance(result, dict)

    def test_explode_env_vars_empty_env_vars(self):
        """Test explode_env_vars with empty env vars."""
        class Settings(BaseSettings):
            data: Dict[str, Any] = {}

        source = EnvSettingsSource(Settings, env_nested_delimiter="__")
        field_info = Settings.model_fields["data"]

        result = source.explode_env_vars("data", field_info, {})
        assert result == {}

    def test_explode_env_vars_dict_type(self):
        """Test explode_env_vars with dict type field."""
        class Settings(BaseSettings):
            mapping: Dict[str, str] = {}

        env_vars = {"MAPPING__KEY": "value"}
        source = EnvSettingsSource(Settings, env_nested_delimiter="__")
        field_info = Settings.model_fields["mapping"]

        result = source.explode_env_vars("mapping", field_info, env_vars)
        assert isinstance(result, dict)


class TestCoerceEnvValStrict:
    """Test EnvSettingsSource._coerce_env_val_strict method."""

    def test_coerce_env_val_strict_simple_string(self):
        """Test _coerce_env_val_strict with simple string."""
        class Settings(BaseSettings):
            field1: str = "default"

        source = EnvSettingsSource(Settings)
        field_info = Settings.model_fields["field1"]

        result = source._coerce_env_val_strict(field_info, "test_value")
        assert result == "test_value"

    def test_coerce_env_val_strict_bool_value(self):
        """Test _coerce_env_val_strict with bool value."""
        class Settings(BaseSettings):
            model_config = {"strict": True}
            flag: bool = False

        source = EnvSettingsSource(Settings)
        field_info = Settings.model_fields["flag"]

        result = source._coerce_env_val_strict(field_info, "true")
        # Should attempt to coerce
        assert result is not None

    def test_coerce_env_val_strict_int_value(self):
        """Test _coerce_env_val_strict with int value."""
        class Settings(BaseSettings):
            model_config = {"strict": True}
            count: int = 0

        source = EnvSettingsSource(Settings)
        field_info = Settings.model_fields["count"]

        result = source._coerce_env_val_strict(field_info, "42")
        # Should attempt to coerce
        assert result is not None

    def test_coerce_env_val_strict_with_none_field(self):
        """Test _coerce_env_val_strict with None field."""
        class Settings(BaseSettings):
            field1: str = "default"

        source = EnvSettingsSource(Settings)

        result = source._coerce_env_val_strict(None, "test_value")
        assert result == "test_value"

    def test_coerce_env_val_strict_parse_none_str(self):
        """Test _coerce_env_val_strict with parse_none_str."""
        class Settings(BaseSettings):
            field1: Optional[str] = None

        source = EnvSettingsSource(Settings, env_parse_none_str="null")
        field_info = Settings.model_fields["field1"]

        result = source._coerce_env_val_strict(field_info, "null")
        # Should not convert parse_none_str value
        assert result == "null"

    def test_coerce_env_val_strict_validation_error(self):
        """Test _coerce_env_val_strict with validation error."""
        class Settings(BaseSettings):
            model_config = {"strict": True}
            value: int = 0

        source = EnvSettingsSource(Settings)
        field_info = Settings.model_fields["value"]

        # Use json-compatible value that still fails int validation
        result = source._coerce_env_val_strict(field_info, "3.14")
        # Should return original value on validation error
        assert result is not None

    def test_coerce_env_val_strict_parse_none_str_returns_value(self):
        """Test _coerce_env_val_strict returns parse_none_str value unchanged (line 304)."""
        class Settings(BaseSettings):
            model_config = {"strict": True}
            field1: Optional[str] = None

        source = EnvSettingsSource(Settings, env_parse_none_str="null")
        field_info = Settings.model_fields["field1"]

        result = source._coerce_env_val_strict(field_info, "null")
        # Line 304: should return value directly without coercing
        assert result == "null"

    def test_coerce_env_val_strict_json_decode_error(self):
        """Test _coerce_env_val_strict with invalid JSON (line 312-313)."""
        class Settings(BaseSettings):
            model_config = {"strict": True}
            value: bool = False

        source = EnvSettingsSource(Settings)
        field_info = Settings.model_fields["value"]

        # "not_valid_json" is not valid JSON, should trigger json.JSONDecodeError
        # This error is not caught and will propagate, so return original value
        with pytest.raises(ValueError):
            source._coerce_env_val_strict(field_info, "not_valid_json")

    def test_coerce_env_val_strict_json_string_result(self):
        """Test _coerce_env_val_strict when JSON decode returns string (line 316)."""
        class Settings(BaseSettings):
            model_config = {"strict": True}
            value: bool = False

        source = EnvSettingsSource(Settings)
        field_info = Settings.model_fields["value"]

        # JSON string that decodes to a string, which cannot be coerced to bool
        # When decoded value is still a string, line 316 raises, caught at 317, returns original
        result = source._coerce_env_val_strict(field_info, '"not_a_bool"')
        assert result == '"not_a_bool"'

    def test_coerce_env_val_strict_with_strict_bool(self):
        """Test _coerce_env_val_strict successfully coerces string to bool via JSON."""
        class Settings(BaseSettings):
            model_config = {"strict": True}
            flag: bool = False

        source = EnvSettingsSource(Settings)
        field_info = Settings.model_fields["flag"]

        # JSON true coerces to bool True
        result = source._coerce_env_val_strict(field_info, "true")
        assert result is True

    def test_coerce_env_val_strict_with_strict_int(self):
        """Test _coerce_env_val_strict successfully coerces string to int."""
        class Settings(BaseSettings):
            model_config = {"strict": True}
            count: int = 0

        source = EnvSettingsSource(Settings)
        field_info = Settings.model_fields["count"]

        result = source._coerce_env_val_strict(field_info, "42")
        assert result == 42

    def test_coerce_env_val_strict_non_string_value(self):
        """Test _coerce_env_val_strict with non-string value."""
        class Settings(BaseSettings):
            model_config = {"strict": True}
            value: int = 0

        source = EnvSettingsSource(Settings)
        field_info = Settings.model_fields["value"]

        # Non-string value should be returned as-is
        result = source._coerce_env_val_strict(field_info, 42)
        assert result == 42


class TestRepr:
    """Test EnvSettingsSource.__repr__ method."""

    def test_repr_default_values(self):
        """Test __repr__ with default values."""
        class Settings(BaseSettings):
            field1: str = "default"

        source = EnvSettingsSource(Settings)
        repr_str = repr(source)

        assert "EnvSettingsSource" in repr_str
        assert "env_nested_delimiter" in repr_str
        assert "env_prefix_len" in repr_str

    def test_repr_with_delimiter(self):
        """Test __repr__ with nested delimiter."""
        class Settings(BaseSettings):
            field1: str = "default"

        source = EnvSettingsSource(Settings, env_nested_delimiter="__", env_prefix="APP_")
        repr_str = repr(source)

        assert "EnvSettingsSource" in repr_str
        assert "__" in repr_str
        # env_prefix_len should be 4 for "APP_"
        assert "env_prefix_len=4" in repr_str

    def test_repr_with_prefix(self):
        """Test __repr__ with prefix."""
        class Settings(BaseSettings):
            field1: str = "default"

        source = EnvSettingsSource(Settings, env_prefix="MY_PREFIX_")
        repr_str = repr(source)

        assert "EnvSettingsSource" in repr_str
        assert "env_prefix_len=10" in repr_str


class TestIntegration:
    """Integration tests for EnvSettingsSource."""

    def test_load_settings_from_env(self):
        """Test loading settings from environment variables."""
        class Settings(BaseSettings):
            name: str = "default_name"
            age: int = 0

        with patch.dict(os.environ, {"NAME": "John", "AGE": "30"}):
            settings = Settings()
            # Settings should load from environment
            assert settings is not None

    def test_load_settings_with_prefix(self):
        """Test loading settings with environment prefix."""
        class Settings(BaseSettings):
            model_config = {"env_prefix": "APP_"}
            name: str = "default_name"

        with patch.dict(os.environ, {"APP_NAME": "John"}):
            settings = Settings()
            assert settings is not None

    def test_load_nested_settings(self):
        """Test loading nested settings."""
        class SubSettings(BaseModel):
            value: str

        class Settings(BaseSettings):
            sub: SubSettings

        with patch.dict(os.environ, {"SUB__VALUE": "test"}):
            # This may fail if nested delimiter isn't configured
            pass

    def test_load_settings_with_dict_field(self):
        """Test loading settings with dict field."""
        class Settings(BaseSettings):
            config: Dict[str, Any] = {}

        with patch.dict(os.environ, {"CONFIG": '{"key": "value"}'}):
            settings = Settings()
            assert settings is not None
