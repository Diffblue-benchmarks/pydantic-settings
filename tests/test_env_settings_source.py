"""Tests for EnvSettingsSource."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Union
from unittest.mock import patch

import pytest
from pydantic import BaseModel, Field, StrictBool, StrictInt
from pydantic.fields import FieldInfo

from pydantic_settings import BaseSettings
from pydantic_settings.sources.providers.env import EnvSettingsSource
from pydantic_settings.sources.types import EnvNoneType


class SimpleSettings(BaseSettings):
    app_name: str = 'default'
    debug: bool = False
    count: int = 0


class NestedSubModel(BaseModel):
    val: str = 'sub_default'
    num: int = 0


class NestedSettings(BaseSettings):
    model_config = {'env_nested_delimiter': '__'}

    sub: NestedSubModel = NestedSubModel()
    name: str = 'test'


class DictSettings(BaseSettings):
    model_config = {'env_nested_delimiter': '__'}

    data: Dict[str, Any] = {}


class ComplexSettings(BaseSettings):
    items: List[str] = []
    mapping: Dict[str, int] = {}


class OptionalComplexSettings(BaseSettings):
    sub: Optional[NestedSubModel] = None


class StrictSettings(BaseSettings):
    model_config = {'strict': True}

    flag: bool = False
    count: int = 0


class PrefixSettings(BaseSettings):
    model_config = {'env_prefix': 'MY_APP_'}

    name: str = 'default'
    debug: bool = False


class CaseSensitiveSettings(BaseSettings):
    model_config = {'case_sensitive': True}

    Name: str = 'default'


class IgnoreEmptySettings(BaseSettings):
    model_config = {'env_ignore_empty': True}

    value: str = 'default'


class ParseNoneSettings(BaseSettings):
    model_config = {'env_parse_none_str': 'null'}

    value: Optional[str] = 'default'


# --- Tests for __init__ ---


class TestEnvSettingsSourceInit:
    def test_basic_init(self):
        source = EnvSettingsSource(SimpleSettings)
        assert source.env_nested_delimiter is None
        assert source.env_nested_max_split is None
        assert source.maxsplit == -1
        assert source.env_prefix_len == 0
        assert source.env_vars is not None

    def test_init_with_nested_delimiter(self):
        source = EnvSettingsSource(SimpleSettings, env_nested_delimiter='__')
        assert source.env_nested_delimiter == '__'

    def test_init_with_nested_max_split(self):
        source = EnvSettingsSource(SimpleSettings, env_nested_max_split=3)
        assert source.env_nested_max_split == 3
        assert source.maxsplit == 2

    def test_init_with_prefix(self):
        source = EnvSettingsSource(SimpleSettings, env_prefix='APP_')
        assert source.env_prefix == 'APP_'
        assert source.env_prefix_len == 4

    def test_init_reads_config_defaults(self):
        source = EnvSettingsSource(NestedSettings)
        assert source.env_nested_delimiter == '__'

    def test_init_override_config_defaults(self):
        source = EnvSettingsSource(NestedSettings, env_nested_delimiter='.')
        assert source.env_nested_delimiter == '.'

    def test_init_case_sensitive(self):
        source = EnvSettingsSource(CaseSensitiveSettings)
        assert source.case_sensitive is True

    def test_init_env_ignore_empty(self):
        source = EnvSettingsSource(IgnoreEmptySettings)
        assert source.env_ignore_empty is True

    def test_init_env_parse_none_str(self):
        source = EnvSettingsSource(ParseNoneSettings)
        assert source.env_parse_none_str == 'null'


# --- Tests for _load_env_vars ---


class TestLoadEnvVars:
    def test_load_env_vars_reads_os_environ(self):
        with patch.dict(os.environ, {'TEST_VAR': 'value'}, clear=False):
            source = EnvSettingsSource(SimpleSettings)
            assert 'test_var' in source.env_vars

    def test_load_env_vars_case_sensitive(self):
        with patch.dict(os.environ, {'TestVar': 'value'}, clear=False):
            source = EnvSettingsSource(SimpleSettings, case_sensitive=True)
            assert 'TestVar' in source.env_vars


# --- Tests for get_field_value ---


class TestGetFieldValue:
    def test_get_field_value_found(self):
        with patch.dict(os.environ, {'APP_NAME': 'myapp'}, clear=False):
            source = EnvSettingsSource(SimpleSettings)
            field = SimpleSettings.model_fields['app_name']
            value, key, is_complex = source.get_field_value(field, 'app_name')
            assert value == 'myapp'
            assert key == 'app_name'
            assert is_complex is False

    def test_get_field_value_not_found(self):
        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(SimpleSettings)
            field = SimpleSettings.model_fields['app_name']
            value, key, is_complex = source.get_field_value(field, 'app_name')
            assert value is None

    def test_get_field_value_with_prefix(self):
        with patch.dict(os.environ, {'MY_APP_NAME': 'prefixed'}, clear=False):
            source = EnvSettingsSource(PrefixSettings)
            field = PrefixSettings.model_fields['name']
            value, key, is_complex = source.get_field_value(field, 'name')
            assert value == 'prefixed'


# --- Tests for prepare_field_value ---


class TestPrepareFieldValue:
    def test_prepare_simple_value(self):
        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(SimpleSettings)
            field = SimpleSettings.model_fields['app_name']
            result = source.prepare_field_value('app_name', field, 'hello', False)
            assert result == 'hello'

    def test_prepare_none_value_non_complex(self):
        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(SimpleSettings)
            field = SimpleSettings.model_fields['app_name']
            result = source.prepare_field_value('app_name', field, None, False)
            assert result is None

    def test_prepare_complex_value_json(self):
        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(ComplexSettings)
            field = ComplexSettings.model_fields['items']
            result = source.prepare_field_value('items', field, '["a","b"]', False)
            assert result == ['a', 'b']

    def test_prepare_complex_value_none_builds_from_env(self):
        with patch.dict(os.environ, {'SUB__VAL': 'nested_val'}, clear=True):
            source = EnvSettingsSource(NestedSettings)
            field = NestedSettings.model_fields['sub']
            result = source.prepare_field_value('sub', field, None, False)
            assert isinstance(result, dict)
            assert result.get('val') == 'nested_val'

    def test_prepare_env_none_type_value(self):
        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(SimpleSettings)
            field = SimpleSettings.model_fields['app_name']
            env_none = EnvNoneType('null')
            result = source.prepare_field_value('app_name', field, env_none, True)
            assert isinstance(result, EnvNoneType)

    def test_prepare_complex_dict_merges_with_explode(self):
        with patch.dict(os.environ, {'MAPPING': '{"a": 1}', 'MAPPING__B': '2'}, clear=True):
            source = EnvSettingsSource(ComplexSettings, env_nested_delimiter='__')
            field = ComplexSettings.model_fields['mapping']
            result = source.prepare_field_value('mapping', field, '{"a": 1}', False)
            assert isinstance(result, dict)
            assert result['a'] == 1


# --- Tests for _field_is_complex ---


class TestFieldIsComplex:
    def test_simple_field_not_complex(self):
        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(SimpleSettings)
            field = SimpleSettings.model_fields['app_name']
            is_complex, allow_failure = source._field_is_complex(field)
            assert is_complex is False
            assert allow_failure is False

    def test_list_field_is_complex(self):
        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(ComplexSettings)
            field = ComplexSettings.model_fields['items']
            is_complex, allow_failure = source._field_is_complex(field)
            assert is_complex is True
            assert allow_failure is False

    def test_dict_field_is_complex(self):
        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(ComplexSettings)
            field = ComplexSettings.model_fields['mapping']
            is_complex, allow_failure = source._field_is_complex(field)
            assert is_complex is True
            assert allow_failure is False

    def test_optional_model_union_is_complex(self):
        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(OptionalComplexSettings)
            field = OptionalComplexSettings.model_fields['sub']
            is_complex, allow_failure = source._field_is_complex(field)
            assert is_complex is True
            assert allow_failure is True


# --- Tests for next_field ---


class TestNextField:
    def test_next_field_none_input(self):
        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(NestedSettings)
            result = source.next_field(None, 'val')
            assert result is None

    def test_next_field_finds_sub_model_field(self):
        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(NestedSettings)
            field = NestedSettings.model_fields['sub']
            result = source.next_field(field, 'val')
            assert result is not None

    def test_next_field_not_found(self):
        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(NestedSettings)
            field = NestedSettings.model_fields['sub']
            result = source.next_field(field, 'nonexistent')
            assert result is None

    def test_next_field_case_insensitive(self):
        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(NestedSettings)
            field = NestedSettings.model_fields['sub']
            result = source.next_field(field, 'VAL', case_sensitive=False)
            assert result is not None

    def test_next_field_case_sensitive_mismatch(self):
        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(NestedSettings)
            field = NestedSettings.model_fields['sub']
            result = source.next_field(field, 'VAL', case_sensitive=True)
            assert result is None

    def test_next_field_dict_annotation(self):
        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(DictSettings)
            field = DictSettings.model_fields['data']
            result = source.next_field(field, 'any_key')
            # For dicts, it returns the value type annotation
            assert result is not None


# --- Tests for explode_env_vars ---


class TestExplodeEnvVars:
    def test_explode_no_delimiter_returns_empty(self):
        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(SimpleSettings)
            field = SimpleSettings.model_fields['app_name']
            result = source.explode_env_vars('app_name', field, {})
            assert result == {}

    def test_explode_with_delimiter(self):
        with patch.dict(os.environ, {'SUB__VAL': 'exploded'}, clear=True):
            source = EnvSettingsSource(NestedSettings)
            field = NestedSettings.model_fields['sub']
            result = source.explode_env_vars('sub', field, source.env_vars)
            assert 'val' in result
            assert result['val'] == 'exploded'

    def test_explode_nested_keys(self):
        class DeepSubModel(BaseModel):
            inner: NestedSubModel = NestedSubModel()

        class DeepSettings(BaseSettings):
            model_config = {'env_nested_delimiter': '__'}

            deep: DeepSubModel = DeepSubModel()

        with patch.dict(os.environ, {'DEEP__INNER__VAL': 'deep_val'}, clear=True):
            source = EnvSettingsSource(DeepSettings)
            field = DeepSettings.model_fields['deep']
            result = source.explode_env_vars('deep', field, source.env_vars)
            assert 'inner' in result
            assert result['inner']['val'] == 'deep_val'

    def test_explode_dict_field(self):
        with patch.dict(os.environ, {'DATA__KEY1': 'val1', 'DATA__KEY2': 'val2'}, clear=True):
            source = EnvSettingsSource(DictSettings)
            field = DictSettings.model_fields['data']
            result = source.explode_env_vars('data', field, source.env_vars)
            assert result.get('key1') == 'val1'
            assert result.get('key2') == 'val2'

    def test_explode_no_matching_prefix(self):
        with patch.dict(os.environ, {'OTHER__VAL': 'nope'}, clear=True):
            source = EnvSettingsSource(NestedSettings)
            field = NestedSettings.model_fields['sub']
            result = source.explode_env_vars('sub', field, source.env_vars)
            assert result == {}

    def test_explode_with_max_split(self):
        class MaxSplitSettings(BaseSettings):
            model_config = {'env_nested_delimiter': '__', 'env_nested_max_split': 1}

            data: Dict[str, Any] = {}

        with patch.dict(os.environ, {'DATA__KEY__EXTRA': 'val'}, clear=True):
            source = EnvSettingsSource(MaxSplitSettings)
            field = MaxSplitSettings.model_fields['data']
            result = source.explode_env_vars('data', field, source.env_vars)
            # With max_split=1, maxsplit=0 means no split on the remainder
            # so 'key__extra' becomes a single key
            assert 'key__extra' in result


# --- Tests for _coerce_env_val_strict ---


class TestCoerceEnvValStrict:
    def test_non_strict_returns_original(self):
        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(SimpleSettings)
            field = SimpleSettings.model_fields['debug']
            result = source._coerce_env_val_strict(field, 'true')
            assert result == 'true'

    def test_strict_bool_coercion(self):
        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(StrictSettings)
            field = StrictSettings.model_fields['flag']
            result = source._coerce_env_val_strict(field, 'true')
            assert result is True

    def test_strict_int_coercion(self):
        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(StrictSettings)
            field = StrictSettings.model_fields['count']
            result = source._coerce_env_val_strict(field, '42')
            assert result == 42

    def test_coerce_none_field_returns_value(self):
        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(SimpleSettings)
            result = source._coerce_env_val_strict(None, 'hello')
            assert result == 'hello'

    def test_coerce_non_string_value_returns_value(self):
        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(StrictSettings)
            field = StrictSettings.model_fields['flag']
            result = source._coerce_env_val_strict(field, True)
            assert result is True

    def test_strict_parse_none_str_passthrough(self):
        class StrictParseNoneSettings(BaseSettings):
            model_config = {'strict': True, 'env_parse_none_str': 'null'}

            value: Optional[str] = None

        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(StrictParseNoneSettings)
            field = StrictParseNoneSettings.model_fields['value']
            result = source._coerce_env_val_strict(field, 'null')
            assert result == 'null'

    def test_strict_coerce_union_strict_bool_json_fallback_true(self):
        """TypeAdapter fails for StrictBool string, json.loads('true') -> True succeeds."""

        class UnionStrictBoolSettings(BaseSettings):
            flag: Optional[StrictBool] = None

        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(UnionStrictBoolSettings)
            field = UnionStrictBoolSettings.model_fields['flag']
            result = source._coerce_env_val_strict(field, 'true')
            assert result is True

    def test_strict_coerce_union_strict_bool_json_fallback_false(self):
        """TypeAdapter fails for StrictBool string, json.loads('false') -> False succeeds."""

        class UnionStrictBoolSettings(BaseSettings):
            flag: Optional[StrictBool] = None

        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(UnionStrictBoolSettings)
            field = UnionStrictBoolSettings.model_fields['flag']
            result = source._coerce_env_val_strict(field, 'false')
            assert result is False

    def test_strict_coerce_union_strict_int_json_fallback(self):
        """TypeAdapter fails for StrictInt string, json.loads('42') -> 42 succeeds."""

        class UnionStrictIntSettings(BaseSettings):
            count: Optional[StrictInt] = None

        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(UnionStrictIntSettings)
            field = UnionStrictIntSettings.model_fields['count']
            result = source._coerce_env_val_strict(field, '42')
            assert result == 42
            assert isinstance(result, int)

    def test_strict_coerce_json_decoded_string_returns_original(self):
        """When json.loads returns a string, re-raise is caught by outer except, returns original."""

        class UnionStrictBoolSettings(BaseSettings):
            flag: Optional[StrictBool] = None

        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(UnionStrictBoolSettings)
            field = UnionStrictBoolSettings.model_fields['flag']
            result = source._coerce_env_val_strict(field, '"hello"')
            assert result == '"hello"'

    def test_strict_coerce_json_decode_failure_propagates(self):
        """When json.loads fails with JSONDecodeError, the error propagates."""

        class UnionStrictBoolSettings(BaseSettings):
            flag: Optional[StrictBool] = None

        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(UnionStrictBoolSettings)
            field = UnionStrictBoolSettings.model_fields['flag']
            with pytest.raises(json.JSONDecodeError):
                source._coerce_env_val_strict(field, 'yes')

    def test_strict_coerce_json_fallback_invalid_decoded_returns_original(self):
        """When json.loads succeeds but decoded value still fails validation, returns original."""

        class UnionStrictBoolSettings(BaseSettings):
            flag: Optional[StrictBool] = None

        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(UnionStrictBoolSettings)
            field = UnionStrictBoolSettings.model_fields['flag']
            # json.loads('42') -> 42 (int, not str), but 42 is not a valid StrictBool
            result = source._coerce_env_val_strict(field, '42')
            assert result == '42'


# --- Tests for __repr__ ---


class TestRepr:
    def test_repr_default(self):
        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(SimpleSettings)
            r = repr(source)
            assert 'EnvSettingsSource' in r
            assert 'env_nested_delimiter=None' in r
            assert 'env_prefix_len=0' in r

    def test_repr_with_delimiter(self):
        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(NestedSettings)
            r = repr(source)
            assert "env_nested_delimiter='__'" in r

    def test_repr_with_prefix(self):
        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(PrefixSettings)
            r = repr(source)
            assert 'env_prefix_len=7' in r


# --- Integration tests via BaseSettings ---


class TestIntegration:
    def test_simple_env_loading(self):
        with patch.dict(os.environ, {'APP_NAME': 'loaded', 'DEBUG': 'true', 'COUNT': '5'}, clear=True):
            settings = SimpleSettings()
            assert settings.app_name == 'loaded'
            assert settings.debug is True
            assert settings.count == 5

    def test_nested_env_loading(self):
        with patch.dict(os.environ, {'SUB__VAL': 'from_env', 'SUB__NUM': '42'}, clear=True):
            settings = NestedSettings()
            assert settings.sub.val == 'from_env'
            assert settings.sub.num == 42

    def test_prefix_env_loading(self):
        with patch.dict(os.environ, {'MY_APP_NAME': 'prefixed_app', 'MY_APP_DEBUG': 'true'}, clear=True):
            settings = PrefixSettings()
            assert settings.name == 'prefixed_app'
            assert settings.debug is True

    def test_case_sensitive_env_loading(self):
        with patch.dict(os.environ, {'Name': 'correct'}, clear=True):
            settings = CaseSensitiveSettings()
            assert settings.Name == 'correct'

    def test_ignore_empty_env(self):
        with patch.dict(os.environ, {'VALUE': ''}, clear=True):
            settings = IgnoreEmptySettings()
            assert settings.value == 'default'

    def test_parse_none_str(self):
        with patch.dict(os.environ, {'VALUE': 'null'}, clear=True):
            settings = ParseNoneSettings()
            assert settings.value is None

    def test_complex_json_env(self):
        with patch.dict(os.environ, {'ITEMS': '["x","y","z"]', 'MAPPING': '{"a": 1}'}, clear=True):
            settings = ComplexSettings()
            assert settings.items == ['x', 'y', 'z']
            assert settings.mapping == {'a': 1}

    def test_env_not_set_uses_default(self):
        with patch.dict(os.environ, {}, clear=True):
            settings = SimpleSettings()
            assert settings.app_name == 'default'
            assert settings.debug is False
            assert settings.count == 0
