"""Tests for EnvSettingsSource class."""

from __future__ import annotations

import json
import os
from enum import Enum, IntEnum
from typing import Any, Dict, List, Optional, Union
from unittest.mock import patch

import pytest
from pydantic import BaseModel, Field, Json, StrictBool
from typing_extensions import Annotated

from pydantic_settings import BaseSettings
from pydantic_settings.sources.providers.env import EnvSettingsSource


class Color(Enum):
    RED = 'red'
    GREEN = 'green'
    BLUE = 'blue'


class Priority(IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3


class SubModel(BaseModel):
    val: str = 'default'
    count: int = 0


class SubSubModel(BaseModel):
    nested_val: str = 'nested_default'


class NestedModel(BaseModel):
    sub: SubModel = Field(default_factory=SubModel)
    name: str = 'nested'


class TestEnvSettingsSourceInit:
    """Tests for EnvSettingsSource.__init__"""

    def test_init_default_values(self):
        """Test initialization with default values."""

        class Settings(BaseSettings):
            name: str = 'test'

        source = EnvSettingsSource(Settings)
        assert source.env_nested_delimiter is None
        assert source.env_nested_max_split is None
        assert source.env_prefix_len == 0

    def test_init_with_env_prefix(self):
        """Test initialization with env_prefix."""

        class Settings(BaseSettings):
            name: str = 'test'
            model_config = {'env_prefix': 'APP_'}

        source = EnvSettingsSource(Settings)
        assert source.env_prefix == 'APP_'
        assert source.env_prefix_len == 4

    def test_init_with_env_nested_delimiter(self):
        """Test initialization with env_nested_delimiter."""

        class Settings(BaseSettings):
            name: str = 'test'
            model_config = {'env_nested_delimiter': '__'}

        source = EnvSettingsSource(Settings)
        assert source.env_nested_delimiter == '__'

    def test_init_with_env_nested_max_split(self):
        """Test initialization with env_nested_max_split."""

        class Settings(BaseSettings):
            name: str = 'test'
            model_config = {'env_nested_delimiter': '__', 'env_nested_max_split': 2}

        source = EnvSettingsSource(Settings)
        assert source.env_nested_max_split == 2
        assert source.maxsplit == 1  # maxsplit = env_nested_max_split - 1

    def test_init_override_parameters(self):
        """Test initialization with overridden parameters."""

        class Settings(BaseSettings):
            name: str = 'test'
            model_config = {'env_prefix': 'CONFIG_', 'env_nested_delimiter': '.'}

        source = EnvSettingsSource(
            Settings,
            env_prefix='OVERRIDE_',
            env_nested_delimiter='__',
            env_nested_max_split=3,
        )
        assert source.env_prefix == 'OVERRIDE_'
        assert source.env_nested_delimiter == '__'
        assert source.env_nested_max_split == 3
        assert source.env_prefix_len == 9


class TestEnvSettingsSourceLoadEnvVars:
    """Tests for EnvSettingsSource._load_env_vars"""

    def test_load_env_vars_basic(self):
        """Test basic loading of environment variables."""

        class Settings(BaseSettings):
            name: str = 'test'

        with patch.dict(os.environ, {'NAME': 'value'}, clear=True):
            source = EnvSettingsSource(Settings)
            assert 'name' in source.env_vars
            assert source.env_vars['name'] == 'value'

    def test_load_env_vars_case_sensitive(self):
        """Test case-sensitive loading of environment variables."""

        class Settings(BaseSettings):
            name: str = 'test'
            model_config = {'case_sensitive': True}

        with patch.dict(os.environ, {'NAME': 'upper', 'name': 'lower'}, clear=True):
            source = EnvSettingsSource(Settings)
            assert 'NAME' in source.env_vars
            assert 'name' in source.env_vars


class TestEnvSettingsSourceGetFieldValue:
    """Tests for EnvSettingsSource.get_field_value"""

    def test_get_field_value_found(self):
        """Test get_field_value when env var exists."""

        class Settings(BaseSettings):
            name: str = 'default'

        with patch.dict(os.environ, {'NAME': 'from_env'}, clear=True):
            source = EnvSettingsSource(Settings)
            field = Settings.model_fields['name']
            value, key, is_complex = source.get_field_value(field, 'name')
            assert value == 'from_env'
            assert key == 'name'
            assert is_complex is False

    def test_get_field_value_not_found(self):
        """Test get_field_value when env var doesn't exist."""

        class Settings(BaseSettings):
            name: str = 'default'

        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(Settings)
            field = Settings.model_fields['name']
            value, key, is_complex = source.get_field_value(field, 'name')
            assert value is None

    def test_get_field_value_with_prefix(self):
        """Test get_field_value with env prefix."""

        class Settings(BaseSettings):
            name: str = 'default'
            model_config = {'env_prefix': 'APP_'}

        with patch.dict(os.environ, {'APP_NAME': 'from_env'}, clear=True):
            source = EnvSettingsSource(Settings)
            field = Settings.model_fields['name']
            value, key, is_complex = source.get_field_value(field, 'name')
            assert value == 'from_env'


class TestEnvSettingsSourcePrepareFieldValue:
    """Tests for EnvSettingsSource.prepare_field_value"""

    def test_prepare_field_value_simple(self):
        """Test prepare_field_value for simple string."""

        class Settings(BaseSettings):
            name: str = 'default'

        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(Settings)
            field = Settings.model_fields['name']
            result = source.prepare_field_value('name', field, 'test_value', False)
            assert result == 'test_value'

    def test_prepare_field_value_complex_dict(self):
        """Test prepare_field_value for complex dict field."""

        class Settings(BaseSettings):
            data: Dict[str, Any] = Field(default_factory=dict)

        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(Settings)
            field = Settings.model_fields['data']
            result = source.prepare_field_value('data', field, '{"key": "value"}', True)
            assert result == {'key': 'value'}

    def test_prepare_field_value_complex_list(self):
        """Test prepare_field_value for complex list field."""

        class Settings(BaseSettings):
            items: List[str] = Field(default_factory=list)

        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(Settings)
            field = Settings.model_fields['items']
            result = source.prepare_field_value('items', field, '["a", "b", "c"]', True)
            assert result == ['a', 'b', 'c']

    def test_prepare_field_value_with_env_parse_enums(self):
        """Test prepare_field_value with env_parse_enums enabled."""

        class Settings(BaseSettings):
            color: Color = Color.RED
            model_config = {'env_parse_enums': True}

        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(Settings)
            field = Settings.model_fields['color']
            result = source.prepare_field_value('color', field, 'GREEN', False)
            assert result == Color.GREEN

    def test_prepare_field_value_none(self):
        """Test prepare_field_value when value is None."""

        class Settings(BaseSettings):
            name: Optional[str] = None

        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(Settings)
            field = Settings.model_fields['name']
            result = source.prepare_field_value('name', field, None, False)
            assert result is None


class TestEnvSettingsSourceFieldIsComplex:
    """Tests for EnvSettingsSource._field_is_complex"""

    def test_field_is_complex_simple_types(self):
        """Test _field_is_complex for simple types."""

        class Settings(BaseSettings):
            name: str = 'default'
            count: int = 0

        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(Settings)
            is_complex, allow_failure = source._field_is_complex(Settings.model_fields['name'])
            assert is_complex is False
            assert allow_failure is False

    def test_field_is_complex_dict(self):
        """Test _field_is_complex for dict type."""

        class Settings(BaseSettings):
            data: Dict[str, Any] = Field(default_factory=dict)

        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(Settings)
            is_complex, allow_failure = source._field_is_complex(Settings.model_fields['data'])
            assert is_complex is True
            assert allow_failure is False

    def test_field_is_complex_model(self):
        """Test _field_is_complex for model type."""

        class Settings(BaseSettings):
            sub: SubModel = Field(default_factory=SubModel)

        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(Settings)
            is_complex, allow_failure = source._field_is_complex(Settings.model_fields['sub'])
            assert is_complex is True

    def test_field_is_complex_optional_complex(self):
        """Test _field_is_complex for Optional complex type."""

        class Settings(BaseSettings):
            data: Optional[Dict[str, Any]] = None

        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(Settings)
            is_complex, allow_failure = source._field_is_complex(Settings.model_fields['data'])
            assert is_complex is True
            assert allow_failure is True


class TestEnvSettingsSourceNextField:
    """Tests for EnvSettingsSource.next_field"""

    def test_next_field_none(self):
        """Test next_field with None field."""

        class Settings(BaseSettings):
            name: str = 'test'

        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(Settings)
            result = source.next_field(None, 'key')
            assert result is None

    def test_next_field_submodel(self):
        """Test next_field with nested model."""

        class SubSub(BaseSettings):
            inner_val: str = 'inner'

        class Sub(BaseSettings):
            outer_val: str = 'outer'
            subsub: SubSub = Field(default_factory=SubSub)

        class Settings(BaseSettings):
            sub: Sub = Field(default_factory=Sub)
            model_config = {'env_nested_delimiter': '__'}

        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(Settings)
            field = Settings.model_fields['sub']
            result = source.next_field(field, 'outer_val')
            assert result is not None

    def test_next_field_dict_type(self):
        """Test next_field with dict type annotation."""

        class Settings(BaseSettings):
            data: Dict[str, int] = Field(default_factory=dict)
            model_config = {'env_nested_delimiter': '__'}

        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(Settings)
            field = Settings.model_fields['data']
            result = source.next_field(field, 'any_key')
            assert result == int

    def test_next_field_case_insensitive(self):
        """Test next_field with case insensitive matching."""

        class Sub(BaseSettings):
            Value: str = 'val'

        class Settings(BaseSettings):
            sub: Sub = Field(default_factory=Sub)
            model_config = {'env_nested_delimiter': '__', 'case_sensitive': False}

        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(Settings)
            field = Settings.model_fields['sub']
            result = source.next_field(field, 'value', case_sensitive=False)
            assert result is not None


class TestEnvSettingsSourceExplodeEnvVars:
    """Tests for EnvSettingsSource.explode_env_vars"""

    def test_explode_env_vars_no_delimiter(self):
        """Test explode_env_vars without nested delimiter."""

        class Settings(BaseSettings):
            sub: SubModel = Field(default_factory=SubModel)

        with patch.dict(os.environ, {'SUB__VAL': 'nested_value'}, clear=True):
            source = EnvSettingsSource(Settings)
            field = Settings.model_fields['sub']
            result = source.explode_env_vars('sub', field, source.env_vars)
            assert result == {}

    def test_explode_env_vars_with_delimiter(self):
        """Test explode_env_vars with nested delimiter."""

        class Settings(BaseSettings):
            sub: SubModel = Field(default_factory=SubModel)
            model_config = {'env_nested_delimiter': '__'}

        with patch.dict(os.environ, {'SUB__VAL': 'nested_value'}, clear=True):
            source = EnvSettingsSource(Settings)
            field = Settings.model_fields['sub']
            result = source.explode_env_vars('sub', field, source.env_vars)
            assert result == {'val': 'nested_value'}

    def test_explode_env_vars_dict_field(self):
        """Test explode_env_vars with dict field."""

        class Settings(BaseSettings):
            data: Dict[str, str] = Field(default_factory=dict)
            model_config = {'env_nested_delimiter': '__'}

        with patch.dict(os.environ, {'DATA__KEY1': 'val1', 'DATA__KEY2': 'val2'}, clear=True):
            source = EnvSettingsSource(Settings)
            field = Settings.model_fields['data']
            result = source.explode_env_vars('data', field, source.env_vars)
            assert result == {'key1': 'val1', 'key2': 'val2'}

    def test_explode_env_vars_deeply_nested(self):
        """Test explode_env_vars with deeply nested structure."""

        class SubSub(BaseModel):
            deep_val: str = 'deep'

        class Sub(BaseModel):
            subsub: SubSub = Field(default_factory=SubSub)

        class Settings(BaseSettings):
            sub: Sub = Field(default_factory=Sub)
            model_config = {'env_nested_delimiter': '__'}

        with patch.dict(os.environ, {'SUB__SUBSUB__DEEP_VAL': 'very_deep'}, clear=True):
            source = EnvSettingsSource(Settings)
            field = Settings.model_fields['sub']
            result = source.explode_env_vars('sub', field, source.env_vars)
            assert result == {'subsub': {'deep_val': 'very_deep'}}

    def test_explode_env_vars_with_prefix(self):
        """Test explode_env_vars with env prefix."""

        class Settings(BaseSettings):
            sub: SubModel = Field(default_factory=SubModel)
            model_config = {'env_prefix': 'APP_', 'env_nested_delimiter': '__'}

        with patch.dict(os.environ, {'APP_SUB__VAL': 'prefixed'}, clear=True):
            source = EnvSettingsSource(Settings)
            field = Settings.model_fields['sub']
            result = source.explode_env_vars('sub', field, source.env_vars)
            assert result == {'val': 'prefixed'}


class TestEnvSettingsSourceCoerceEnvValStrict:
    """Tests for EnvSettingsSource._coerce_env_val_strict"""

    def test_coerce_env_val_strict_non_strict_mode(self):
        """Test _coerce_env_val_strict in non-strict mode."""

        class Settings(BaseSettings):
            name: str = 'default'

        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(Settings)
            field = Settings.model_fields['name']
            result = source._coerce_env_val_strict(field, 'test')
            assert result == 'test'

    def test_coerce_env_val_strict_strict_mode_bool(self):
        """Test _coerce_env_val_strict with strict bool."""

        class Settings(BaseSettings):
            flag: StrictBool = False
            model_config = {'strict': True}

        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(Settings)
            field = Settings.model_fields['flag']
            result = source._coerce_env_val_strict(field, 'true')
            assert result is True

    def test_coerce_env_val_strict_optional_strict_bool(self):
        """Test _coerce_env_val_strict with Optional[StrictBool]."""

        class Settings(BaseSettings):
            flag: Optional[StrictBool] = None

        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(Settings)
            field = Settings.model_fields['flag']
            result = source._coerce_env_val_strict(field, 'false')
            assert result is False

    def test_coerce_env_val_strict_none_field(self):
        """Test _coerce_env_val_strict with None field."""

        class Settings(BaseSettings):
            name: str = 'default'

        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(Settings)
            result = source._coerce_env_val_strict(None, 'test')
            assert result == 'test'

    def test_coerce_env_val_strict_env_parse_none_str(self):
        """Test _coerce_env_val_strict returns value unchanged when it matches env_parse_none_str."""

        class Settings(BaseSettings):
            flag: Optional[StrictBool] = None
            model_config = {'strict': True, 'env_parse_none_str': 'null'}

        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(Settings)
            field = Settings.model_fields['flag']
            # When value matches env_parse_none_str, it should return the value as-is (line 304)
            result = source._coerce_env_val_strict(field, 'null')
            assert result == 'null'

    def test_coerce_env_val_strict_invalid_json_raises(self):
        """Test _coerce_env_val_strict raises JSONDecodeError for invalid JSON string."""

        class Settings(BaseSettings):
            flag: Optional[StrictBool] = None
            model_config = {'strict': True}

        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(Settings)
            field = Settings.model_fields['flag']
            # 'not_valid_json' cannot be parsed by TypeAdapter for StrictBool,
            # and also cannot be decoded by json.loads (lines 312-313)
            # The exception re-raises and propagates
            with pytest.raises(json.JSONDecodeError):
                source._coerce_env_val_strict(field, 'not_valid_json')

    def test_coerce_env_val_strict_json_decodes_to_string(self):
        """Test _coerce_env_val_strict when JSON decodes to a string value."""

        class Settings(BaseSettings):
            flag: Optional[StrictBool] = None
            model_config = {'strict': True}

        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(Settings)
            field = Settings.model_fields['flag']
            # '"hello"' is valid JSON that decodes to a string "hello"
            # This triggers the isinstance(decoded, str) check (lines 316-317)
            result = source._coerce_env_val_strict(field, '"hello"')
            # Should return the original value when JSON decodes to a string
            assert result == '"hello"'


class TestEnvSettingsSourceRepr:
    """Tests for EnvSettingsSource.__repr__"""

    def test_repr_default(self):
        """Test __repr__ with default values."""

        class Settings(BaseSettings):
            name: str = 'test'

        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(Settings)
            repr_str = repr(source)
            assert 'EnvSettingsSource' in repr_str
            assert 'env_nested_delimiter=None' in repr_str
            assert 'env_prefix_len=0' in repr_str

    def test_repr_with_values(self):
        """Test __repr__ with custom values."""

        class Settings(BaseSettings):
            name: str = 'test'
            model_config = {'env_prefix': 'APP_', 'env_nested_delimiter': '__'}

        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(Settings)
            repr_str = repr(source)
            assert 'EnvSettingsSource' in repr_str
            assert "env_nested_delimiter='__'" in repr_str
            assert 'env_prefix_len=4' in repr_str


class TestEnvSettingsSourceIntegration:
    """Integration tests for EnvSettingsSource"""

    def test_basic_settings(self):
        """Test basic settings loading from environment."""

        class Settings(BaseSettings):
            name: str = 'default'
            count: int = 0

        with patch.dict(os.environ, {'NAME': 'from_env', 'COUNT': '42'}, clear=True):
            settings = Settings()
            assert settings.name == 'from_env'
            assert settings.count == 42

    def test_nested_settings(self):
        """Test nested settings loading from environment."""

        class Settings(BaseSettings):
            sub: SubModel = Field(default_factory=SubModel)
            model_config = {'env_nested_delimiter': '__'}

        with patch.dict(os.environ, {'SUB__VAL': 'nested', 'SUB__COUNT': '10'}, clear=True):
            settings = Settings()
            assert settings.sub.val == 'nested'
            assert settings.sub.count == 10

    def test_json_complex_field(self):
        """Test loading complex JSON field from environment."""

        class Settings(BaseSettings):
            data: Dict[str, int] = Field(default_factory=dict)

        with patch.dict(os.environ, {'DATA': '{"a": 1, "b": 2}'}, clear=True):
            settings = Settings()
            assert settings.data == {'a': 1, 'b': 2}

    def test_prefixed_settings(self):
        """Test settings with env prefix."""

        class Settings(BaseSettings):
            name: str = 'default'
            model_config = {'env_prefix': 'MYAPP_'}

        with patch.dict(os.environ, {'MYAPP_NAME': 'prefixed'}, clear=True):
            settings = Settings()
            assert settings.name == 'prefixed'

    def test_env_parse_none_str(self):
        """Test parsing none string from environment."""

        class Settings(BaseSettings):
            name: Optional[str] = 'default'
            model_config = {'env_parse_none_str': 'null'}

        with patch.dict(os.environ, {'NAME': 'null'}, clear=True):
            settings = Settings()
            assert settings.name is None

    def test_env_ignore_empty(self):
        """Test ignoring empty environment variables."""

        class Settings(BaseSettings):
            name: str = 'default'
            model_config = {'env_ignore_empty': True}

        with patch.dict(os.environ, {'NAME': ''}, clear=True):
            settings = Settings()
            assert settings.name == 'default'

    def test_enum_settings(self):
        """Test enum settings loading from environment."""

        class Settings(BaseSettings):
            color: Color = Color.RED
            model_config = {'env_parse_enums': True}

        with patch.dict(os.environ, {'COLOR': 'BLUE'}, clear=True):
            settings = Settings()
            assert settings.color == Color.BLUE
