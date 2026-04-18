"""Tests for EnvSettingsSource."""

import json
import os
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from unittest.mock import patch

import pytest
from pydantic import BaseModel, Field, StrictBool

from pydantic_settings import BaseSettings
from pydantic_settings.sources.providers.env import EnvSettingsSource
from pydantic_settings.sources.types import EnvNoneType


class SimpleSettings(BaseSettings):
    my_var: str = 'default'
    my_int: int = 0


class NestedSubModel(BaseModel):
    val: str = 'sub_default'
    count: int = 0


class NestedSettings(BaseSettings):
    sub: NestedSubModel = NestedSubModel()
    name: str = 'test'

    model_config = {'env_nested_delimiter': '__'}


class DeeplyNestedInner(BaseModel):
    deep_val: str = 'deep'


class DeeplyNestedOuter(BaseModel):
    inner: DeeplyNestedInner = DeeplyNestedInner()
    label: str = 'outer'


class DeeplyNestedSettings(BaseSettings):
    outer: DeeplyNestedOuter = DeeplyNestedOuter()

    model_config = {'env_nested_delimiter': '__'}


class DictSettings(BaseSettings):
    data: Dict[str, Any] = {}

    model_config = {'env_nested_delimiter': '__'}


class ListSettings(BaseSettings):
    items: List[str] = []


class OptionalComplexSettings(BaseSettings):
    maybe_sub: Optional[NestedSubModel] = None

    model_config = {'env_nested_delimiter': '__'}


class PrefixedSettings(BaseSettings):
    my_var: str = 'default'

    model_config = {'env_prefix': 'APP_'}


class CaseSensitiveSettings(BaseSettings):
    My_Var: str = 'default'

    model_config = {'case_sensitive': True}


class IgnoreEmptySettings(BaseSettings):
    my_var: str = 'default'

    model_config = {'env_ignore_empty': True}


class ParseNoneSettings(BaseSettings):
    my_var: Optional[str] = 'default'

    model_config = {'env_parse_none_str': 'null'}


class StrictSettings(BaseSettings):
    flag: Optional[StrictBool] = None

    model_config = {'strict': True}


# --- Tests ---


class TestEnvSettingsSourceInit:
    def test_basic_init(self):
        source = EnvSettingsSource(SimpleSettings)
        assert source.env_nested_delimiter is None
        assert source.env_nested_max_split is None
        assert source.env_prefix == ''
        assert source.env_prefix_len == 0
        assert source.case_sensitive is False

    def test_init_with_env_prefix(self):
        source = EnvSettingsSource(SimpleSettings, env_prefix='APP_')
        assert source.env_prefix == 'APP_'
        assert source.env_prefix_len == 4

    def test_init_with_nested_delimiter(self):
        source = EnvSettingsSource(SimpleSettings, env_nested_delimiter='__')
        assert source.env_nested_delimiter == '__'

    def test_init_with_nested_max_split(self):
        source = EnvSettingsSource(SimpleSettings, env_nested_delimiter='__', env_nested_max_split=3)
        assert source.env_nested_max_split == 3
        assert source.maxsplit == 2

    def test_init_case_sensitive(self):
        source = EnvSettingsSource(SimpleSettings, case_sensitive=True)
        assert source.case_sensitive is True

    def test_init_env_ignore_empty(self):
        source = EnvSettingsSource(SimpleSettings, env_ignore_empty=True)
        assert source.env_ignore_empty is True

    def test_init_env_parse_none_str(self):
        source = EnvSettingsSource(SimpleSettings, env_parse_none_str='null')
        assert source.env_parse_none_str == 'null'

    def test_init_env_parse_enums(self):
        source = EnvSettingsSource(SimpleSettings, env_parse_enums=True)
        assert source.env_parse_enums is True

    def test_init_from_model_config(self):
        source = EnvSettingsSource(NestedSettings)
        assert source.env_nested_delimiter == '__'

    def test_init_maxsplit_with_no_max_split(self):
        source = EnvSettingsSource(SimpleSettings, env_nested_delimiter='__')
        assert source.maxsplit == -1


class TestLoadEnvVars:
    def test_load_env_vars_picks_up_os_environ(self):
        with patch.dict(os.environ, {'MY_VAR': 'test_value'}, clear=False):
            source = EnvSettingsSource(SimpleSettings)
            assert 'my_var' in source.env_vars
            assert source.env_vars['my_var'] == 'test_value'

    def test_load_env_vars_case_sensitive(self):
        with patch.dict(os.environ, {'My_Var': 'test_value'}, clear=False):
            source = EnvSettingsSource(CaseSensitiveSettings, case_sensitive=True)
            assert 'My_Var' in source.env_vars


class TestGetFieldValue:
    def test_get_field_value_found(self):
        with patch.dict(os.environ, {'MY_VAR': 'hello'}, clear=False):
            source = EnvSettingsSource(SimpleSettings)
            field = SimpleSettings.model_fields['my_var']
            env_val, field_key, value_is_complex = source.get_field_value(field, 'my_var')
            assert env_val == 'hello'
            assert field_key == 'my_var'
            assert value_is_complex is False

    def test_get_field_value_not_found(self):
        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(SimpleSettings)
            field = SimpleSettings.model_fields['my_var']
            env_val, field_key, value_is_complex = source.get_field_value(field, 'my_var')
            assert env_val is None

    def test_get_field_value_with_prefix(self):
        with patch.dict(os.environ, {'APP_MY_VAR': 'prefixed'}, clear=False):
            source = EnvSettingsSource(PrefixedSettings)
            field = PrefixedSettings.model_fields['my_var']
            env_val, field_key, value_is_complex = source.get_field_value(field, 'my_var')
            assert env_val == 'prefixed'


class TestPrepareFieldValue:
    def test_prepare_simple_value(self):
        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(SimpleSettings)
            field = SimpleSettings.model_fields['my_var']
            result = source.prepare_field_value('my_var', field, 'hello', False)
            assert result == 'hello'

    def test_prepare_none_value_simple(self):
        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(SimpleSettings)
            field = SimpleSettings.model_fields['my_var']
            result = source.prepare_field_value('my_var', field, None, False)
            assert result is None

    def test_prepare_complex_value_json(self):
        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(ListSettings)
            field = ListSettings.model_fields['items']
            result = source.prepare_field_value('items', field, '["a","b"]', False)
            assert result == ['a', 'b']

    def test_prepare_env_none_type_complex(self):
        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(ListSettings)
            field = ListSettings.model_fields['items']
            env_none = EnvNoneType('null')
            result = source.prepare_field_value('items', field, env_none, True)
            assert isinstance(result, EnvNoneType)

    def test_prepare_complex_value_none_with_explode(self):
        with patch.dict(os.environ, {'SUB__VAL': 'exploded'}, clear=True):
            source = EnvSettingsSource(NestedSettings)
            field = NestedSettings.model_fields['sub']
            result = source.prepare_field_value('sub', field, None, False)
            assert isinstance(result, dict)
            assert result.get('val') == 'exploded'

    def test_prepare_complex_value_dict_with_deep_update(self):
        with patch.dict(os.environ, {'SUB__COUNT': '99'}, clear=True):
            source = EnvSettingsSource(NestedSettings)
            field = NestedSettings.model_fields['sub']
            result = source.prepare_field_value('sub', field, '{"val": "from_json"}', False)
            assert isinstance(result, dict)
            assert result['val'] == 'from_json'
            assert result['count'] == '99'


class TestFieldIsComplex:
    def test_simple_field_not_complex(self):
        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(SimpleSettings)
            field = SimpleSettings.model_fields['my_var']
            is_complex, allow_parse_failure = source._field_is_complex(field)
            assert is_complex is False
            assert allow_parse_failure is False

    def test_complex_field(self):
        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(NestedSettings)
            field = NestedSettings.model_fields['sub']
            is_complex, allow_parse_failure = source._field_is_complex(field)
            assert is_complex is True
            assert allow_parse_failure is False

    def test_optional_complex_field(self):
        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(OptionalComplexSettings)
            field = OptionalComplexSettings.model_fields['maybe_sub']
            is_complex, allow_parse_failure = source._field_is_complex(field)
            assert is_complex is True
            assert allow_parse_failure is True


class TestNextField:
    def test_next_field_none_input(self):
        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(NestedSettings)
            result = source.next_field(None, 'val')
            assert result is None

    def test_next_field_finds_submodel_field(self):
        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(NestedSettings)
            field = NestedSettings.model_fields['sub']
            result = source.next_field(field, 'val')
            assert result is not None

    def test_next_field_not_found(self):
        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(NestedSettings)
            field = NestedSettings.model_fields['sub']
            result = source.next_field(field, 'nonexistent_field')
            assert result is None

    def test_next_field_deeply_nested(self):
        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(DeeplyNestedSettings)
            outer_field = DeeplyNestedSettings.model_fields['outer']
            result = source.next_field(outer_field, 'inner')
            assert result is not None

    def test_next_field_dict_type(self):
        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(DictSettings)
            field = DictSettings.model_fields['data']
            result = source.next_field(field, 'any_key')
            # For dict fields, returns the value type annotation
            assert result is not None

    def test_next_field_case_insensitive(self):
        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(NestedSettings)
            field = NestedSettings.model_fields['sub']
            result = source.next_field(field, 'VAL', case_sensitive=False)
            assert result is not None

    def test_next_field_case_sensitive(self):
        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(NestedSettings)
            field = NestedSettings.model_fields['sub']
            result = source.next_field(field, 'VAL', case_sensitive=True)
            assert result is None


class TestExplodeEnvVars:
    def test_explode_no_delimiter(self):
        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(SimpleSettings)
            field = SimpleSettings.model_fields['my_var']
            result = source.explode_env_vars('my_var', field, {})
            assert result == {}

    def test_explode_basic_nested(self):
        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(NestedSettings)
            field = NestedSettings.model_fields['sub']
            env_vars = {'sub__val': 'exploded_val', 'sub__count': '42'}
            result = source.explode_env_vars('sub', field, env_vars)
            assert result == {'val': 'exploded_val', 'count': '42'}

    def test_explode_deeply_nested(self):
        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(DeeplyNestedSettings)
            field = DeeplyNestedSettings.model_fields['outer']
            env_vars = {'outer__inner__deep_val': 'deep_value', 'outer__label': 'my_label'}
            result = source.explode_env_vars('outer', field, env_vars)
            assert result['label'] == 'my_label'
            assert 'inner' in result
            assert result['inner']['deep_val'] == 'deep_value'

    def test_explode_dict_field(self):
        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(DictSettings)
            field = DictSettings.model_fields['data']
            env_vars = {'data__key1': 'value1', 'data__key2': 'value2'}
            result = source.explode_env_vars('data', field, env_vars)
            assert result == {'key1': 'value1', 'key2': 'value2'}

    def test_explode_no_matching_prefix(self):
        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(NestedSettings)
            field = NestedSettings.model_fields['sub']
            env_vars = {'other__val': 'nope'}
            result = source.explode_env_vars('sub', field, env_vars)
            assert result == {}

    def test_explode_env_none_type_skipped_when_value_exists(self):
        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(NestedSettings)
            field = NestedSettings.model_fields['sub']
            env_vars = {'sub__val': 'real_val'}
            result = source.explode_env_vars('sub', field, env_vars)
            assert result['val'] == 'real_val'


class TestCoerceEnvValStrict:
    def test_coerce_non_strict_returns_value(self):
        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(SimpleSettings)
            field = SimpleSettings.model_fields['my_var']
            result = source._coerce_env_val_strict(field, 'hello')
            assert result == 'hello'

    def test_coerce_strict_bool_true(self):
        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(StrictSettings)
            field = StrictSettings.model_fields['flag']
            result = source._coerce_env_val_strict(field, 'true')
            assert result is True

    def test_coerce_strict_bool_false(self):
        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(StrictSettings)
            field = StrictSettings.model_fields['flag']
            result = source._coerce_env_val_strict(field, 'false')
            assert result is False

    def test_coerce_none_field(self):
        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(SimpleSettings)
            result = source._coerce_env_val_strict(None, 'hello')
            assert result == 'hello'

    def test_coerce_non_string_value(self):
        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(StrictSettings)
            field = StrictSettings.model_fields['flag']
            result = source._coerce_env_val_strict(field, True)
            assert result is True

    def test_coerce_parse_none_str_returns_as_is(self):
        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(StrictSettings, env_parse_none_str='null')
            field = StrictSettings.model_fields['flag']
            result = source._coerce_env_val_strict(field, 'null')
            assert result == 'null'

    def test_coerce_strict_invalid_json_raises(self):
        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(StrictSettings)
            field = StrictSettings.model_fields['flag']
            with pytest.raises(json.JSONDecodeError):
                source._coerce_env_val_strict(field, 'not_valid_json')

    def test_coerce_strict_json_string_returns_original(self):
        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(StrictSettings)
            field = StrictSettings.model_fields['flag']
            result = source._coerce_env_val_strict(field, '"hello"')
            assert result == '"hello"'


class TestRepr:
    def test_repr(self):
        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(SimpleSettings, env_nested_delimiter='__')
            r = repr(source)
            assert 'EnvSettingsSource' in r
            assert 'env_nested_delimiter' in r
            assert "'__'" in r
            assert 'env_prefix_len' in r

    def test_repr_no_delimiter(self):
        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(SimpleSettings)
            r = repr(source)
            assert 'env_nested_delimiter=None' in r
            assert 'env_prefix_len=0' in r


class TestIntegration:
    def test_full_env_to_settings(self):
        with patch.dict(os.environ, {'MY_VAR': 'from_env', 'MY_INT': '42'}, clear=True):
            s = SimpleSettings()
            assert s.my_var == 'from_env'
            assert s.my_int == 42

    def test_nested_env_to_settings(self):
        with patch.dict(os.environ, {'SUB__VAL': 'nested_val', 'SUB__COUNT': '10'}, clear=True):
            s = NestedSettings()
            assert s.sub.val == 'nested_val'
            assert s.sub.count == 10

    def test_prefix_env_to_settings(self):
        with patch.dict(os.environ, {'APP_MY_VAR': 'prefixed_val'}, clear=True):
            s = PrefixedSettings()
            assert s.my_var == 'prefixed_val'

    def test_ignore_empty_env(self):
        with patch.dict(os.environ, {'MY_VAR': ''}, clear=True):
            s = IgnoreEmptySettings()
            assert s.my_var == 'default'

    def test_parse_none_str(self):
        with patch.dict(os.environ, {'MY_VAR': 'null'}, clear=True):
            s = ParseNoneSettings()
            assert s.my_var is None

    def test_case_sensitive_env(self):
        with patch.dict(os.environ, {'My_Var': 'sensitive'}, clear=True):
            s = CaseSensitiveSettings()
            assert s.My_Var == 'sensitive'

    def test_deeply_nested_env(self):
        with patch.dict(os.environ, {'OUTER__INNER__DEEP_VAL': 'very_deep', 'OUTER__LABEL': 'lbl'}, clear=True):
            s = DeeplyNestedSettings()
            assert s.outer.inner.deep_val == 'very_deep'
            assert s.outer.label == 'lbl'

    def test_dict_field_env(self):
        with patch.dict(os.environ, {'DATA__KEY1': 'val1', 'DATA__KEY2': 'val2'}, clear=True):
            s = DictSettings()
            assert s.data == {'key1': 'val1', 'key2': 'val2'}

    def test_json_complex_value(self):
        with patch.dict(os.environ, {'ITEMS': '["x", "y", "z"]'}, clear=True):
            s = ListSettings()
            assert s.items == ['x', 'y', 'z']

    def test_strict_bool_from_env(self):
        with patch.dict(os.environ, {'FLAG': 'true'}, clear=True):
            s = StrictSettings()
            assert s.flag is True


class TestMaxSplitNestedDelimiter:
    def test_max_split_limits_nesting(self):

        class MaxSplitSettings(BaseSettings):
            data: Dict[str, Any] = {}

            model_config = {'env_nested_delimiter': '__', 'env_nested_max_split': 2}

        with patch.dict(os.environ, {'DATA__A__B__C': 'val'}, clear=True):
            source = EnvSettingsSource(MaxSplitSettings)
            assert source.env_nested_max_split == 2
            assert source.maxsplit == 1


class TestExplodeEnvVarsEnumParsing:
    """Tests for lines 263-264: env_parse_enums in explode_env_vars."""

    def test_explode_env_vars_with_enum_parse(self):
        class Color(Enum):
            RED = 'red'
            GREEN = 'green'
            BLUE = 'blue'

        class SubWithEnum(BaseModel):
            color: Color = Color.RED

        class EnumNestedSettings(BaseSettings):
            sub: SubWithEnum = SubWithEnum()

            model_config = {'env_nested_delimiter': '__'}

        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(EnumNestedSettings, env_parse_enums=True)
            field = EnumNestedSettings.model_fields['sub']
            env_vars = {'sub__color': 'GREEN'}
            result = source.explode_env_vars('sub', field, env_vars)
            assert result['color'] == Color.GREEN

    def test_explode_env_vars_with_enum_parse_unknown_member(self):
        class Color(Enum):
            RED = 'red'
            GREEN = 'green'

        class SubWithEnum(BaseModel):
            color: Color = Color.RED

        class EnumNestedSettings(BaseSettings):
            sub: SubWithEnum = SubWithEnum()

            model_config = {'env_nested_delimiter': '__'}

        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(EnumNestedSettings, env_parse_enums=True)
            field = EnumNestedSettings.model_fields['sub']
            env_vars = {'sub__color': 'YELLOW'}
            result = source.explode_env_vars('sub', field, env_vars)
            # YELLOW is not a member, so env_val stays as string
            assert result['color'] == 'YELLOW'


class TestExplodeEnvVarsDeeplyNestedDict:
    """Tests for line 271: dict field with deeply nested keys where target_field is None."""

    def test_explode_dict_deeply_nested_json_value(self):
        """When a dict field has 2+ levels of nesting, target_field becomes None,
        hitting the else branch (line 271) with is_complex=True."""

        class DeepDictSettings(BaseSettings):
            data: Dict[str, Any] = {}

            model_config = {'env_nested_delimiter': '__'}

        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(DeepDictSettings)
            field = DeepDictSettings.model_fields['data']
            env_vars = {'data__key1__subkey': '{"nested": "value"}'}
            result = source.explode_env_vars('data', field, env_vars)
            assert result == {'key1': {'subkey': {'nested': 'value'}}}

    def test_explode_dict_deeply_nested_non_json_value(self):
        """When deeply nested dict value is not valid JSON, the ValueError is caught
        because allow_json_failure=True (lines 276-278, not re-raised)."""

        class DeepDictSettings(BaseSettings):
            data: Dict[str, Any] = {}

            model_config = {'env_nested_delimiter': '__'}

        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(DeepDictSettings)
            field = DeepDictSettings.model_fields['data']
            env_vars = {'data__key1__subkey': 'plain_string'}
            result = source.explode_env_vars('data', field, env_vars)
            # ValueError from json.loads is caught, original string preserved
            assert result == {'key1': {'subkey': 'plain_string'}}

    def test_explode_dict_deeply_nested_list_json(self):
        """Deeply nested dict with a JSON list value."""

        class DeepDictSettings(BaseSettings):
            data: Dict[str, Any] = {}

            model_config = {'env_nested_delimiter': '__'}

        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(DeepDictSettings)
            field = DeepDictSettings.model_fields['data']
            env_vars = {'data__section__items': '["a", "b", "c"]'}
            result = source.explode_env_vars('data', field, env_vars)
            assert result == {'section': {'items': ['a', 'b', 'c']}}


class TestExplodeEnvVarsComplexFieldValueError:
    """Tests for lines 273-278: complex value decoding with ValueError handling."""

    def test_explode_nested_model_complex_field_invalid_json_raises(self):
        """When a nested complex field (allow_json_failure=False) gets invalid JSON,
        the ValueError is re-raised (line 278)."""

        class InnerModel(BaseModel):
            items: List[str] = []

        class OuterSettings(BaseSettings):
            inner: InnerModel = InnerModel()

            model_config = {'env_nested_delimiter': '__'}

        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(OuterSettings)
            field = OuterSettings.model_fields['inner']
            env_vars = {'inner__items': 'not_valid_json'}
            with pytest.raises(ValueError):
                source.explode_env_vars('inner', field, env_vars)

    def test_explode_nested_model_complex_field_valid_json(self):
        """When a nested complex field gets valid JSON, it is decoded (lines 273-275)."""

        class InnerModel(BaseModel):
            items: List[str] = []

        class OuterSettings(BaseSettings):
            inner: InnerModel = InnerModel()

            model_config = {'env_nested_delimiter': '__'}

        with patch.dict(os.environ, {}, clear=True):
            source = EnvSettingsSource(OuterSettings)
            field = OuterSettings.model_fields['inner']
            env_vars = {'inner__items': '["x", "y"]'}
            result = source.explode_env_vars('inner', field, env_vars)
            assert result == {'items': ['x', 'y']}
