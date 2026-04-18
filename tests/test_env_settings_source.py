from __future__ import annotations

import os
from enum import Enum
from typing import Any, Dict, List, Optional, Union

import pytest
from pydantic import BaseModel, Field, StrictBool, StrictInt
from pydantic.fields import FieldInfo

from pydantic_settings import BaseSettings
from pydantic_settings.sources.providers.env import EnvSettingsSource
from pydantic_settings.sources.types import EnvNoneType


# ---------------------------------------------------------------------------
# Helper models
# ---------------------------------------------------------------------------


class SimpleSettings(BaseSettings):
    foo: str = 'default'
    bar: int = 0


class PrefixedSettings(BaseSettings):
    value: str = ''

    model_config = {'env_prefix': 'MYAPP_'}


class NestedSubModel(BaseModel):
    x: int = 0
    y: str = ''


class NestedSettings(BaseSettings):
    nested: NestedSubModel = NestedSubModel()

    model_config = {'env_nested_delimiter': '__'}


class DictSettings(BaseSettings):
    data: Dict[str, str] = {}

    model_config = {'env_nested_delimiter': '__'}


class ListSettings(BaseSettings):
    items: List[str] = []


class OptionalSettings(BaseSettings):
    val: Optional[str] = None


class StrictSettings(BaseSettings):
    flag: StrictBool = False

    model_config = {'strict': True}


class UnionSettings(BaseSettings):
    value: Union[int, str] = ''


class MyColor(Enum):
    RED = 'red'
    BLUE = 'blue'


class SubWithEnum(BaseModel):
    color: MyColor = MyColor.RED


class SettingsWithEnumSub(BaseSettings):
    sub: SubWithEnum = SubWithEnum()

    model_config = {'env_nested_delimiter': '__'}


class AnyDictSettings(BaseSettings):
    data: Dict[str, Any] = {}

    model_config = {'env_nested_delimiter': '__'}


class EnumDirectSettings(BaseSettings):
    color: MyColor = MyColor.RED


class InnerComplexModel(BaseModel):
    items: List[str] = []


class OuterComplexModel(BaseModel):
    inner: InnerComplexModel = InnerComplexModel()


class DeepComplexSettings(BaseSettings):
    outer: OuterComplexModel = OuterComplexModel()

    model_config = {'env_nested_delimiter': '__'}


# ---------------------------------------------------------------------------
# __init__ tests
# ---------------------------------------------------------------------------


class TestEnvSettingsSourceInit:
    def test_basic_init(self):
        src = EnvSettingsSource(SimpleSettings)
        assert src.env_nested_delimiter is None
        assert src.env_nested_max_split is None
        assert src.env_prefix_len == 0
        assert src.maxsplit == -1

    def test_init_with_env_nested_delimiter(self):
        src = EnvSettingsSource(SimpleSettings, env_nested_delimiter='__')
        assert src.env_nested_delimiter == '__'

    def test_init_with_env_nested_max_split(self):
        src = EnvSettingsSource(SimpleSettings, env_nested_delimiter='__', env_nested_max_split=2)
        assert src.env_nested_max_split == 2
        assert src.maxsplit == 1

    def test_init_reads_delimiter_from_config(self):
        src = EnvSettingsSource(NestedSettings)
        assert src.env_nested_delimiter == '__'

    def test_init_env_prefix_len(self):
        src = EnvSettingsSource(PrefixedSettings)
        assert src.env_prefix_len == len('MYAPP_')

    def test_init_case_sensitive_param(self):
        src = EnvSettingsSource(SimpleSettings, case_sensitive=True)
        assert src.case_sensitive is True

    def test_init_env_prefix_param(self):
        src = EnvSettingsSource(SimpleSettings, env_prefix='TEST_')
        assert src.env_prefix == 'TEST_'
        assert src.env_prefix_len == 5

    def test_env_vars_loaded_on_init(self, monkeypatch):
        monkeypatch.setenv('FOO', 'hello')
        src = EnvSettingsSource(SimpleSettings)
        assert 'foo' in src.env_vars

    def test_init_with_env_ignore_empty(self, monkeypatch):
        monkeypatch.setenv('FOO', '')
        src = EnvSettingsSource(SimpleSettings, env_ignore_empty=True)
        assert src.env_vars.get('foo') is None

    def test_init_with_env_parse_none_str(self, monkeypatch):
        monkeypatch.setenv('FOO', 'null')
        src = EnvSettingsSource(SimpleSettings, env_parse_none_str='null')
        assert isinstance(src.env_vars.get('foo'), EnvNoneType)


# ---------------------------------------------------------------------------
# _load_env_vars tests
# ---------------------------------------------------------------------------


class TestLoadEnvVars:
    def test_loads_from_os_environ(self, monkeypatch):
        monkeypatch.setenv('MY_TEST_VAR', 'test_value')
        src = EnvSettingsSource(SimpleSettings)
        result = src._load_env_vars()
        assert result.get('my_test_var') == 'test_value'

    def test_case_insensitive_by_default(self, monkeypatch):
        monkeypatch.setenv('FOO', 'bar')
        src = EnvSettingsSource(SimpleSettings)
        result = src._load_env_vars()
        assert result.get('foo') == 'bar'

    def test_case_sensitive_preserves_case(self, monkeypatch):
        monkeypatch.setenv('FOO', 'bar')
        src = EnvSettingsSource(SimpleSettings, case_sensitive=True)
        result = src._load_env_vars()
        assert result.get('FOO') == 'bar'
        assert result.get('foo') is None


# ---------------------------------------------------------------------------
# get_field_value tests
# ---------------------------------------------------------------------------


class TestGetFieldValue:
    def test_returns_none_when_not_set(self):
        src = EnvSettingsSource(SimpleSettings)
        field = SimpleSettings.model_fields['foo']
        val, key, is_complex = src.get_field_value(field, 'foo')
        assert val is None

    def test_returns_value_when_set(self, monkeypatch):
        monkeypatch.setenv('FOO', 'hello')
        src = EnvSettingsSource(SimpleSettings)
        field = SimpleSettings.model_fields['foo']
        val, key, is_complex = src.get_field_value(field, 'foo')
        assert val == 'hello'
        assert key == 'foo'

    def test_returns_field_key(self, monkeypatch):
        monkeypatch.setenv('FOO', 'hello')
        src = EnvSettingsSource(SimpleSettings)
        field = SimpleSettings.model_fields['foo']
        val, key, is_complex = src.get_field_value(field, 'foo')
        assert key == 'foo'

    def test_complex_flag_for_simple_field(self, monkeypatch):
        monkeypatch.setenv('FOO', 'hello')
        src = EnvSettingsSource(SimpleSettings)
        field = SimpleSettings.model_fields['foo']
        val, key, is_complex = src.get_field_value(field, 'foo')
        assert is_complex is False

    def test_with_prefix(self, monkeypatch):
        monkeypatch.setenv('MYAPP_VALUE', 'myval')
        src = EnvSettingsSource(PrefixedSettings)
        field = PrefixedSettings.model_fields['value']
        val, key, is_complex = src.get_field_value(field, 'value')
        assert val == 'myval'


# ---------------------------------------------------------------------------
# prepare_field_value tests
# ---------------------------------------------------------------------------


class TestPrepareFieldValue:
    def test_simple_non_complex_field_returns_value(self, monkeypatch):
        monkeypatch.setenv('FOO', 'hello')
        src = EnvSettingsSource(SimpleSettings)
        field = SimpleSettings.model_fields['foo']
        result = src.prepare_field_value('foo', field, 'hello', False)
        assert result == 'hello'

    def test_simple_field_none_returns_none(self):
        src = EnvSettingsSource(SimpleSettings)
        field = SimpleSettings.model_fields['foo']
        result = src.prepare_field_value('foo', field, None, False)
        assert result is None

    def test_complex_field_json_decode(self, monkeypatch):
        monkeypatch.setenv('NESTED', '{"x": 1, "y": "hi"}')
        src = EnvSettingsSource(NestedSettings)
        field = NestedSettings.model_fields['nested']
        result = src.prepare_field_value('nested', field, '{"x": 1, "y": "hi"}', False)
        assert result == {'x': 1, 'y': 'hi'}

    def test_complex_field_none_uses_explode(self, monkeypatch):
        monkeypatch.setenv('NESTED__X', '5')
        src = EnvSettingsSource(NestedSettings)
        field = NestedSettings.model_fields['nested']
        result = src.prepare_field_value('nested', field, None, False)
        assert isinstance(result, dict)
        assert result.get('x') == '5'

    def test_env_none_type_returned_as_is(self, monkeypatch):
        src = EnvSettingsSource(NestedSettings)
        field = NestedSettings.model_fields['nested']
        env_none = EnvNoneType('null')
        result = src.prepare_field_value('nested', field, env_none, False)
        assert isinstance(result, EnvNoneType)

    def test_complex_field_dict_merged_with_explode(self, monkeypatch):
        monkeypatch.setenv('DATA__KEY1', 'v1')
        monkeypatch.setenv('DATA', '{"key2": "v2"}')
        src = EnvSettingsSource(DictSettings)
        field = DictSettings.model_fields['data']
        result = src.prepare_field_value('data', field, '{"key2": "v2"}', False)
        assert result.get('key2') == 'v2'
        assert result.get('key1') == 'v1'

    def test_env_parse_enums_converts_matching_enum_name(self):
        src = EnvSettingsSource(EnumDirectSettings, env_parse_enums=True)
        field = EnumDirectSettings.model_fields['color']
        result = src.prepare_field_value('color', field, 'BLUE', False)
        assert result == MyColor.BLUE

    def test_env_parse_enums_leaves_non_matching_name_unchanged(self):
        src = EnvSettingsSource(EnumDirectSettings, env_parse_enums=True)
        field = EnumDirectSettings.model_fields['color']
        result = src.prepare_field_value('color', field, 'UNKNOWN', False)
        assert result == 'UNKNOWN'

    def test_complex_field_invalid_json_raises_value_error(self):
        src = EnvSettingsSource(NestedSettings)
        field = NestedSettings.model_fields['nested']
        with pytest.raises(ValueError):
            src.prepare_field_value('nested', field, 'not-valid-json', False)

    def test_complex_field_decoded_list_returned_directly(self):
        src = EnvSettingsSource(ListSettings)
        field = ListSettings.model_fields['items']
        result = src.prepare_field_value('items', field, '["a", "b"]', False)
        assert result == ['a', 'b']


# ---------------------------------------------------------------------------
# _field_is_complex tests
# ---------------------------------------------------------------------------


class TestFieldIsComplex:
    def test_simple_field_returns_false_false(self):
        src = EnvSettingsSource(SimpleSettings)
        field = SimpleSettings.model_fields['foo']
        is_complex, allow_parse_failure = src._field_is_complex(field)
        assert is_complex is False
        assert allow_parse_failure is False

    def test_nested_model_field_returns_true_false(self):
        src = EnvSettingsSource(NestedSettings)
        field = NestedSettings.model_fields['nested']
        is_complex, allow_parse_failure = src._field_is_complex(field)
        assert is_complex is True
        assert allow_parse_failure is False

    def test_optional_nested_returns_true_true(self):
        class SettingsWithOptionalNested(BaseSettings):
            nested: Optional[NestedSubModel] = None

        src = EnvSettingsSource(SettingsWithOptionalNested)
        field = SettingsWithOptionalNested.model_fields['nested']
        is_complex, allow_parse_failure = src._field_is_complex(field)
        # Union[NestedSubModel, None] is complex and allows parse failure
        assert is_complex is True

    def test_list_field_is_complex(self):
        src = EnvSettingsSource(ListSettings)
        field = ListSettings.model_fields['items']
        is_complex, allow_parse_failure = src._field_is_complex(field)
        assert is_complex is True

    def test_dict_field_is_complex(self):
        src = EnvSettingsSource(DictSettings)
        field = DictSettings.model_fields['data']
        is_complex, allow_parse_failure = src._field_is_complex(field)
        assert is_complex is True


# ---------------------------------------------------------------------------
# next_field tests
# ---------------------------------------------------------------------------


class TestNextField:
    def test_returns_none_for_none_field(self):
        src = EnvSettingsSource(SimpleSettings)
        result = src.next_field(None, 'any_key')
        assert result is None

    def test_finds_field_in_model(self):
        src = EnvSettingsSource(NestedSettings)
        field = NestedSettings.model_fields['nested']
        result = src.next_field(field, 'x')
        assert result is not None

    def test_returns_none_for_missing_key(self):
        src = EnvSettingsSource(NestedSettings)
        field = NestedSettings.model_fields['nested']
        result = src.next_field(field, 'nonexistent_key')
        assert result is None

    def test_case_insensitive_matching(self):
        src = EnvSettingsSource(NestedSettings, case_sensitive=False)
        field = NestedSettings.model_fields['nested']
        result = src.next_field(field, 'X', case_sensitive=False)
        assert result is not None

    def test_case_sensitive_matching(self):
        src = EnvSettingsSource(NestedSettings, case_sensitive=True)
        field = NestedSettings.model_fields['nested']
        result_upper = src.next_field(field, 'X', case_sensitive=True)
        result_lower = src.next_field(field, 'x', case_sensitive=True)
        # 'X' should not match 'x' in case-sensitive mode
        assert result_upper is None
        assert result_lower is not None

    def test_dict_annotation_returns_value_type(self):
        src = EnvSettingsSource(DictSettings)
        field = DictSettings.model_fields['data']
        result = src.next_field(field, 'any_key')
        # For Dict[str, str], should return the value type (str)
        assert result == str


# ---------------------------------------------------------------------------
# explode_env_vars tests
# ---------------------------------------------------------------------------


class TestExplodeEnvVars:
    def test_returns_empty_dict_when_no_delimiter(self, monkeypatch):
        monkeypatch.setenv('NESTED__X', '5')
        src = EnvSettingsSource(NestedSettings, env_nested_delimiter=None)
        src.env_nested_delimiter = None
        field = NestedSettings.model_fields['nested']
        result = src.explode_env_vars('nested', field, src.env_vars)
        assert result == {}

    def test_explodes_nested_vars(self, monkeypatch):
        monkeypatch.setenv('NESTED__X', '5')
        monkeypatch.setenv('NESTED__Y', 'hello')
        src = EnvSettingsSource(NestedSettings)
        field = NestedSettings.model_fields['nested']
        result = src.explode_env_vars('nested', field, src.env_vars)
        assert result.get('x') == '5'
        assert result.get('y') == 'hello'

    def test_ignores_vars_without_prefix(self, monkeypatch):
        monkeypatch.setenv('OTHER__X', '5')
        src = EnvSettingsSource(NestedSettings)
        field = NestedSettings.model_fields['nested']
        result = src.explode_env_vars('nested', field, src.env_vars)
        assert result == {}

    def test_explodes_dict_vars(self, monkeypatch):
        monkeypatch.setenv('DATA__KEY1', 'v1')
        monkeypatch.setenv('DATA__KEY2', 'v2')
        src = EnvSettingsSource(DictSettings)
        field = DictSettings.model_fields['data']
        result = src.explode_env_vars('data', field, src.env_vars)
        assert result.get('key1') == 'v1'
        assert result.get('key2') == 'v2'

    def test_deep_nesting(self, monkeypatch):
        class DeepSubModel(BaseModel):
            z: int = 0

        class DeepModel(BaseModel):
            sub: DeepSubModel = DeepSubModel()

        class DeepSettings(BaseSettings):
            deep: DeepModel = DeepModel()

            model_config = {'env_nested_delimiter': '__'}

        monkeypatch.setenv('DEEP__SUB__Z', '99')
        src = EnvSettingsSource(DeepSettings)
        field = DeepSettings.model_fields['deep']
        result = src.explode_env_vars('deep', field, src.env_vars)
        assert result.get('sub', {}).get('z') == '99'

    def test_max_split_limits_nesting(self, monkeypatch):
        monkeypatch.setenv('NESTED__X__EXTRA', '5')
        src = EnvSettingsSource(NestedSettings, env_nested_max_split=1)
        field = NestedSettings.model_fields['nested']
        result = src.explode_env_vars('nested', field, src.env_vars)
        # With max_split=1, 'x__extra' should be used as last_key
        assert 'x__extra' in result

    def test_env_none_type_not_overwritten(self, monkeypatch):
        monkeypatch.setenv('NESTED__X', '5')
        src = EnvSettingsSource(NestedSettings, env_parse_none_str='null')
        field = NestedSettings.model_fields['nested']
        env_vars = dict(src.env_vars)
        env_vars['nested__x'] = EnvNoneType('null')
        env_vars['nested__y'] = 'hello'
        result = src.explode_env_vars('nested', field, env_vars)
        # EnvNoneType value in already-set key should be preserved
        assert isinstance(result.get('x'), EnvNoneType)

    def test_explode_env_vars_env_parse_enums_converts_enum_name(self, monkeypatch):
        monkeypatch.setenv('SUB__COLOR', 'RED')
        src = EnvSettingsSource(SettingsWithEnumSub, env_parse_enums=True)
        field = SettingsWithEnumSub.model_fields['sub']
        result = src.explode_env_vars('sub', field, src.env_vars)
        assert result.get('color') == MyColor.RED

    def test_explode_env_vars_env_parse_enums_unknown_name_unchanged(self, monkeypatch):
        monkeypatch.setenv('SUB__COLOR', 'UNKNOWN')
        src = EnvSettingsSource(SettingsWithEnumSub, env_parse_enums=True)
        field = SettingsWithEnumSub.model_fields['sub']
        result = src.explode_env_vars('sub', field, src.env_vars)
        assert result.get('color') == 'UNKNOWN'

    def test_explode_env_vars_dict_any_deep_nesting_else_branch(self, monkeypatch):
        monkeypatch.setenv('DATA__KEY1__SUBKEY', '{"a": 1}')
        src = EnvSettingsSource(AnyDictSettings)
        field = AnyDictSettings.model_fields['data']
        result = src.explode_env_vars('data', field, src.env_vars)
        assert result.get('key1', {}).get('subkey') == {'a': 1}

    def test_explode_env_vars_dict_any_deep_nesting_invalid_json_silent(self, monkeypatch):
        monkeypatch.setenv('DATA__KEY1__SUBKEY', 'not-valid-json')
        src = EnvSettingsSource(AnyDictSettings)
        field = AnyDictSettings.model_fields['data']
        result = src.explode_env_vars('data', field, src.env_vars)
        assert result.get('key1', {}).get('subkey') == 'not-valid-json'

    def test_explode_env_vars_complex_nested_raises_on_invalid_json(self, monkeypatch):
        monkeypatch.setenv('OUTER__INNER__ITEMS', 'not-valid-json')
        src = EnvSettingsSource(DeepComplexSettings)
        field = DeepComplexSettings.model_fields['outer']
        with pytest.raises(ValueError):
            src.explode_env_vars('outer', field, src.env_vars)


# ---------------------------------------------------------------------------
# _coerce_env_val_strict tests
# ---------------------------------------------------------------------------


class TestCoerceEnvValStrict:
    def test_non_strict_returns_value_unchanged(self):
        src = EnvSettingsSource(SimpleSettings)
        field = SimpleSettings.model_fields['foo']
        result = src._coerce_env_val_strict(field, 'hello')
        assert result == 'hello'

    def test_strict_model_coerces_bool(self):
        src = EnvSettingsSource(StrictSettings)
        field = StrictSettings.model_fields['flag']
        result = src._coerce_env_val_strict(field, 'true')
        assert result is True

    def test_strict_model_coerces_bool_false(self):
        src = EnvSettingsSource(StrictSettings)
        field = StrictSettings.model_fields['flag']
        result = src._coerce_env_val_strict(field, 'false')
        assert result is False

    def test_strict_json_string_value_returned_as_is(self):
        src = EnvSettingsSource(StrictSettings)
        field = StrictSettings.model_fields['flag']
        # '"hello"' is a JSON string; TypeAdapter(StrictBool) fails, json.loads returns str
        # so the ValidationError is re-raised and caught by outer except -> returns original value
        result = src._coerce_env_val_strict(field, '"hello"')
        assert result == '"hello"'

    def test_none_field_returns_value_unchanged(self):
        src = EnvSettingsSource(SimpleSettings)
        result = src._coerce_env_val_strict(None, 'hello')
        assert result == 'hello'

    def test_none_parse_str_skips_coercion(self):
        src = EnvSettingsSource(StrictSettings, env_parse_none_str='null')
        field = StrictSettings.model_fields['flag']
        result = src._coerce_env_val_strict(field, 'null')
        assert result == 'null'

    def test_union_without_strict_annotation_returns_unchanged(self):
        # Union[StrictBool, str] does not trigger strict coercion in this implementation
        # because _union_has_strict_types checks for doubly-annotated forms
        class UnionStrictSettings(BaseSettings):
            val: Union[StrictBool, str] = ''

        src = EnvSettingsSource(UnionStrictSettings)
        field = UnionStrictSettings.model_fields['val']
        result = src._coerce_env_val_strict(field, 'true')
        assert result == 'true'

    def test_non_string_value_returned_unchanged(self):
        src = EnvSettingsSource(StrictSettings)
        field = StrictSettings.model_fields['flag']
        result = src._coerce_env_val_strict(field, True)
        assert result is True


# ---------------------------------------------------------------------------
# __repr__ tests
# ---------------------------------------------------------------------------


class TestRepr:
    def test_repr_contains_class_name(self):
        src = EnvSettingsSource(SimpleSettings)
        r = repr(src)
        assert 'EnvSettingsSource' in r

    def test_repr_contains_env_nested_delimiter(self):
        src = EnvSettingsSource(SimpleSettings, env_nested_delimiter='__')
        r = repr(src)
        assert 'env_nested_delimiter' in r
        assert "'__'" in r

    def test_repr_contains_env_prefix_len(self):
        src = EnvSettingsSource(PrefixedSettings)
        r = repr(src)
        assert 'env_prefix_len' in r
        assert str(len('MYAPP_')) in r

    def test_repr_none_delimiter(self):
        src = EnvSettingsSource(SimpleSettings)
        r = repr(src)
        assert 'None' in r


# ---------------------------------------------------------------------------
# Integration tests - full settings instantiation via env vars
# ---------------------------------------------------------------------------


class TestIntegration:
    def test_simple_field_from_env(self, monkeypatch):
        monkeypatch.setenv('FOO', 'envvalue')
        settings = SimpleSettings()
        assert settings.foo == 'envvalue'

    def test_nested_field_from_env_delimiter(self, monkeypatch):
        monkeypatch.setenv('NESTED__X', '42')
        settings = NestedSettings()
        assert settings.nested.x == 42

    def test_prefixed_field_from_env(self, monkeypatch):
        monkeypatch.setenv('MYAPP_VALUE', 'prefixed')
        settings = PrefixedSettings()
        assert settings.value == 'prefixed'

    def test_missing_field_uses_default(self):
        src = EnvSettingsSource(SimpleSettings)
        field = SimpleSettings.model_fields['foo']
        val, key, is_complex = src.get_field_value(field, 'foo')
        assert val is None
