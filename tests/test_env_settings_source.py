"""Tests for EnvSettingsSource."""
from __future__ import annotations

import os
from enum import Enum
from typing import Dict, List, Optional

import pytest
from pydantic import Field, StrictBool, StrictInt
from pydantic.fields import FieldInfo

from pydantic_settings import BaseSettings, EnvSettingsSource


# ── Helpers ──────────────────────────────────────────────────────────────────

class SimpleSettings(BaseSettings):
    foo: str = 'default'
    bar: int = 0


class PrefixedSettings(BaseSettings):
    model_config = {'env_prefix': 'APP_'}
    value: str = 'default'


class NestedSettings(BaseSettings):
    model_config = {'env_nested_delimiter': '__'}
    db: Dict[str, str] = {}


class ComplexSettings(BaseSettings):
    items: List[str] = []
    mapping: Dict[str, int] = {}


class StrictSettings(BaseSettings):
    model_config = {'strict': True}
    flag: bool = False
    count: int = 0


class SubModel(BaseSettings):
    val: str = 'x'


class ParentSettings(BaseSettings):
    model_config = {'env_nested_delimiter': '__'}
    sub: Optional[SubModel] = None


# ── __init__ ─────────────────────────────────────────────────────────────────

def test_init_defaults(monkeypatch):
    monkeypatch.setenv('FOO', 'hello')
    src = EnvSettingsSource(SimpleSettings)
    assert src.env_nested_delimiter is None
    assert src.env_nested_max_split is None
    assert src.env_prefix_len == 0
    assert 'foo' in src.env_vars or 'FOO' in src.env_vars


def test_init_with_nested_delimiter():
    src = EnvSettingsSource(SimpleSettings, env_nested_delimiter='__')
    assert src.env_nested_delimiter == '__'


def test_init_with_nested_max_split():
    src = EnvSettingsSource(SimpleSettings, env_nested_delimiter='__', env_nested_max_split=2)
    assert src.env_nested_max_split == 2
    assert src.maxsplit == 1


def test_init_env_prefix_len():
    src = EnvSettingsSource(PrefixedSettings)
    assert src.env_prefix_len == len('APP_')


def test_init_case_insensitive(monkeypatch):
    monkeypatch.setenv('FOO', 'bar')
    src = EnvSettingsSource(SimpleSettings, case_sensitive=False)
    assert src.case_sensitive is False


def test_init_case_sensitive(monkeypatch):
    monkeypatch.setenv('FOO', 'bar')
    src = EnvSettingsSource(SimpleSettings, case_sensitive=True)
    assert src.case_sensitive is True


def test_init_env_ignore_empty():
    src = EnvSettingsSource(SimpleSettings, env_ignore_empty=True)
    assert src.env_ignore_empty is True


def test_init_env_parse_none_str():
    src = EnvSettingsSource(SimpleSettings, env_parse_none_str='null')
    assert src.env_parse_none_str == 'null'


def test_init_env_parse_enums():
    src = EnvSettingsSource(SimpleSettings, env_parse_enums=True)
    assert src.env_parse_enums is True


def test_init_maxsplit_zero_when_none():
    src = EnvSettingsSource(SimpleSettings)
    assert src.maxsplit == -1  # (0 or 0) - 1 == -1


def test_init_nested_delimiter_from_config():
    class CfgSettings(BaseSettings):
        model_config = {'env_nested_delimiter': '|'}
        x: str = ''

    src = EnvSettingsSource(CfgSettings)
    assert src.env_nested_delimiter == '|'


# ── _load_env_vars ────────────────────────────────────────────────────────────

def test_load_env_vars_returns_mapping(monkeypatch):
    monkeypatch.setenv('MYVAR', 'myval')
    src = EnvSettingsSource(SimpleSettings, case_sensitive=True)
    env_vars = src._load_env_vars()
    assert env_vars.get('MYVAR') == 'myval'


def test_load_env_vars_case_insensitive(monkeypatch):
    monkeypatch.setenv('MYVAR', 'myval')
    src = EnvSettingsSource(SimpleSettings, case_sensitive=False)
    env_vars = src._load_env_vars()
    assert env_vars.get('myvar') == 'myval'


# ── get_field_value ───────────────────────────────────────────────────────────

def test_get_field_value_found(monkeypatch):
    monkeypatch.setenv('foo', 'hello')
    src = EnvSettingsSource(SimpleSettings, case_sensitive=True)
    field = SimpleSettings.model_fields['foo']
    val, key, is_complex = src.get_field_value(field, 'foo')
    assert val == 'hello'


def test_get_field_value_not_found():
    src = EnvSettingsSource(SimpleSettings)
    field = SimpleSettings.model_fields['foo']
    val, key, is_complex = src.get_field_value(field, 'foo')
    assert val is None


def test_get_field_value_returns_field_key():
    src = EnvSettingsSource(SimpleSettings)
    field = SimpleSettings.model_fields['foo']
    val, key, is_complex = src.get_field_value(field, 'foo')
    assert isinstance(key, str)


def test_get_field_value_complex_list(monkeypatch):
    monkeypatch.setenv('items', '["a", "b"]')
    src = EnvSettingsSource(ComplexSettings, case_sensitive=True)
    field = ComplexSettings.model_fields['items']
    val, key, is_complex = src.get_field_value(field, 'items')
    assert val == '["a", "b"]'


# ── prepare_field_value ───────────────────────────────────────────────────────

def test_prepare_field_value_simple(monkeypatch):
    monkeypatch.setenv('FOO', 'world')
    src = EnvSettingsSource(SimpleSettings, case_sensitive=True)
    field = SimpleSettings.model_fields['foo']
    result = src.prepare_field_value('foo', field, 'world', False)
    assert result == 'world'


def test_prepare_field_value_none_not_complex():
    src = EnvSettingsSource(SimpleSettings)
    field = SimpleSettings.model_fields['foo']
    result = src.prepare_field_value('foo', field, None, False)
    assert result is None


def test_prepare_field_value_complex_none_no_explode():
    src = EnvSettingsSource(ComplexSettings)
    field = ComplexSettings.model_fields['items']
    result = src.prepare_field_value('items', field, None, True)
    assert result is None or result == {}


def test_prepare_field_value_complex_json(monkeypatch):
    monkeypatch.setenv('ITEMS', '["x", "y"]')
    src = EnvSettingsSource(ComplexSettings, case_sensitive=True)
    field = ComplexSettings.model_fields['items']
    result = src.prepare_field_value('items', field, '["x", "y"]', True)
    assert result == ['x', 'y']


def test_prepare_field_value_complex_dict_merge(monkeypatch):
    monkeypatch.setenv('MAPPING', '{"a": 1}')
    monkeypatch.setenv('MAPPING__B', '2')
    src = EnvSettingsSource(ComplexSettings, case_sensitive=True, env_nested_delimiter='__')
    field = ComplexSettings.model_fields['mapping']
    result = src.prepare_field_value('mapping', field, '{"a": 1}', True)
    assert isinstance(result, dict)
    assert result.get('a') == 1


# ── _field_is_complex ─────────────────────────────────────────────────────────

def test_field_is_complex_list():
    src = EnvSettingsSource(ComplexSettings)
    field = ComplexSettings.model_fields['items']
    is_complex, allow_failure = src._field_is_complex(field)
    assert is_complex is True


def test_field_is_complex_simple():
    src = EnvSettingsSource(SimpleSettings)
    field = SimpleSettings.model_fields['foo']
    is_complex, allow_failure = src._field_is_complex(field)
    assert is_complex is False
    assert allow_failure is False


def test_field_is_complex_dict():
    src = EnvSettingsSource(ComplexSettings)
    field = ComplexSettings.model_fields['mapping']
    is_complex, allow_failure = src._field_is_complex(field)
    assert is_complex is True


def test_field_is_complex_optional_str():
    class OptionalSettings(BaseSettings):
        val: Optional[str] = None

    src = EnvSettingsSource(OptionalSettings)
    field = OptionalSettings.model_fields['val']
    is_complex, allow_failure = src._field_is_complex(field)
    assert is_complex is False


# ── next_field ────────────────────────────────────────────────────────────────

def test_next_field_none():
    src = EnvSettingsSource(SimpleSettings)
    result = src.next_field(None, 'foo')
    assert result is None


def test_next_field_model_field():
    src = EnvSettingsSource(ParentSettings)
    field = ParentSettings.model_fields['sub']
    result = src.next_field(field, 'val')
    assert result is not None


def test_next_field_not_found():
    src = EnvSettingsSource(ParentSettings)
    field = ParentSettings.model_fields['sub']
    result = src.next_field(field, 'nonexistent_key')
    assert result is None


def test_next_field_case_insensitive():
    src = EnvSettingsSource(ParentSettings, case_sensitive=False)
    field = ParentSettings.model_fields['sub']
    result = src.next_field(field, 'VAL', case_sensitive=False)
    assert result is not None


def test_next_field_dict_type():
    from typing import Dict

    class DictSettings(BaseSettings):
        mapping: Dict[str, int] = {}

    src = EnvSettingsSource(DictSettings)
    field = DictSettings.model_fields['mapping']
    result = src.next_field(field, 'any_key')
    # For dict, returns the value type annotation
    assert result is not None


# ── explode_env_vars ──────────────────────────────────────────────────────────

def test_explode_env_vars_no_delimiter():
    src = EnvSettingsSource(SimpleSettings)
    field = SimpleSettings.model_fields['foo']
    result = src.explode_env_vars('foo', field, {'foo__bar': 'val'})
    assert result == {}


def test_explode_env_vars_basic(monkeypatch):
    src = EnvSettingsSource(ComplexSettings, env_nested_delimiter='__', case_sensitive=True)
    field = ComplexSettings.model_fields['mapping']
    env = {'mapping__a': '1', 'mapping__b': '2'}
    result = src.explode_env_vars('mapping', field, env)
    assert result == {'a': '1', 'b': '2'}


def test_explode_env_vars_no_matching_prefix():
    src = EnvSettingsSource(ComplexSettings, env_nested_delimiter='__', case_sensitive=True)
    field = ComplexSettings.model_fields['mapping']
    env = {'other__a': '1'}
    result = src.explode_env_vars('mapping', field, env)
    assert result == {}


def test_explode_env_vars_nested():
    class DeepSettings(BaseSettings):
        db: Dict[str, Dict[str, str]] = {}

    src = EnvSettingsSource(DeepSettings, env_nested_delimiter='__', case_sensitive=True)
    field = DeepSettings.model_fields['db']
    env = {'db__host__port': '5432'}
    result = src.explode_env_vars('db', field, env)
    assert 'host' in result
    assert str(result['host']['port']) == '5432'


def test_explode_env_vars_json_complex_value():
    src = EnvSettingsSource(ComplexSettings, env_nested_delimiter='__', case_sensitive=True)
    field = ComplexSettings.model_fields['mapping']
    env = {'mapping__a': '42'}
    result = src.explode_env_vars('mapping', field, env)
    assert 'a' in result


def test_explode_env_vars_empty_env():
    src = EnvSettingsSource(ComplexSettings, env_nested_delimiter='__', case_sensitive=True)
    field = ComplexSettings.model_fields['mapping']
    result = src.explode_env_vars('mapping', field, {})
    assert result == {}


def test_explode_env_vars_enum_name_conversion():
    """Lines 261-264: FieldInfo branch with env_parse_enums=True converts enum name to value."""

    class Color(Enum):
        RED = 'red'
        GREEN = 'green'

    from pydantic import BaseModel

    class SubModel(BaseModel):
        color: Color = Color.RED

    class EnumNestedSettings(BaseSettings):
        model_config = {'env_nested_delimiter': '__'}
        sub: SubModel = SubModel()

    src = EnvSettingsSource(EnumNestedSettings, env_nested_delimiter='__', case_sensitive=True, env_parse_enums=True)
    field = EnumNestedSettings.model_fields['sub']
    result = src.explode_env_vars('sub', field, {'sub__color': 'GREEN'})
    assert result['color'] == Color.GREEN


def test_explode_env_vars_enum_name_not_found_passthrough():
    """Lines 261-264: FieldInfo branch with env_parse_enums=True, unknown enum name passes through unchanged."""

    class Status(Enum):
        ACTIVE = 'active'
        INACTIVE = 'inactive'

    from pydantic import BaseModel

    class SubModel(BaseModel):
        status: Status = Status.ACTIVE

    class EnumPassthroughSettings(BaseSettings):
        model_config = {'env_nested_delimiter': '__'}
        sub: SubModel = SubModel()

    src = EnvSettingsSource(
        EnumPassthroughSettings, env_nested_delimiter='__', case_sensitive=True, env_parse_enums=True
    )
    field = EnumPassthroughSettings.model_fields['sub']
    result = src.explode_env_vars('sub', field, {'sub__status': 'active'})
    # 'active' is not a member name (it's a value), so enum_val is None and env_val passes through
    assert result['status'] == 'active'


def test_explode_env_vars_complex_field_invalid_json_raises():
    """Lines 276-278: ValueError is raised when allow_json_failure is False (non-union complex field)."""

    from pydantic import BaseModel

    class InnerModel(BaseModel):
        items: List[str] = []

    class OuterSettings(BaseSettings):
        model_config = {'env_nested_delimiter': '__'}
        inner: InnerModel = InnerModel()

    src = EnvSettingsSource(OuterSettings, env_nested_delimiter='__', case_sensitive=True)
    field = OuterSettings.model_fields['inner']
    with pytest.raises(ValueError):
        src.explode_env_vars('inner', field, {'inner__items': 'not_valid_json'})


# ── _coerce_env_val_strict ────────────────────────────────────────────────────

def test_coerce_env_val_strict_not_strict():
    src = EnvSettingsSource(SimpleSettings)
    field = SimpleSettings.model_fields['foo']
    result = src._coerce_env_val_strict(field, 'hello')
    assert result == 'hello'


def test_coerce_env_val_strict_bool():
    src = EnvSettingsSource(StrictSettings)
    field = StrictSettings.model_fields['flag']
    result = src._coerce_env_val_strict(field, 'true')
    assert result is True


def test_coerce_env_val_strict_int():
    src = EnvSettingsSource(StrictSettings)
    field = StrictSettings.model_fields['count']
    result = src._coerce_env_val_strict(field, '42')
    assert result == 42


def test_coerce_env_val_strict_none_field():
    src = EnvSettingsSource(SimpleSettings)
    result = src._coerce_env_val_strict(None, 'hello')
    assert result == 'hello'


def test_coerce_env_val_strict_none_str_passthrough():
    src = EnvSettingsSource(StrictSettings, env_parse_none_str='null')
    field = StrictSettings.model_fields['flag']
    result = src._coerce_env_val_strict(field, 'null')
    assert result == 'null'


def test_coerce_env_val_strict_invalid_value():
    import json
    src = EnvSettingsSource(StrictSettings)
    field = StrictSettings.model_fields['count']
    # A value that is valid JSON string but can't be validated as int returns as-is
    result = src._coerce_env_val_strict(field, '"notanumber"')
    assert result == '"notanumber"'


def test_coerce_env_val_strict_non_string():
    src = EnvSettingsSource(StrictSettings)
    field = StrictSettings.model_fields['count']
    result = src._coerce_env_val_strict(field, 99)
    assert result == 99


# ── __repr__ ──────────────────────────────────────────────────────────────────

def test_repr_basic():
    src = EnvSettingsSource(SimpleSettings)
    r = repr(src)
    assert 'EnvSettingsSource' in r
    assert 'env_nested_delimiter' in r
    assert 'env_prefix_len' in r


def test_repr_with_delimiter():
    src = EnvSettingsSource(SimpleSettings, env_nested_delimiter='__')
    r = repr(src)
    assert "'__'" in r


def test_repr_with_prefix():
    src = EnvSettingsSource(PrefixedSettings)
    r = repr(src)
    assert '4' in r  # len('APP_') == 4


# ── Integration ───────────────────────────────────────────────────────────────

def test_full_settings_load_from_env(monkeypatch):
    monkeypatch.setenv('foo', 'from_env')
    monkeypatch.setenv('bar', '99')

    class MySrc(BaseSettings):
        foo: str = 'default'
        bar: int = 0

        @classmethod
        def settings_customise_sources(cls, settings_cls, **kwargs):
            return (EnvSettingsSource(settings_cls, case_sensitive=True),)

    s = MySrc()
    assert s.foo == 'from_env'
    assert s.bar == 99


def test_nested_delimiter_loads_dict(monkeypatch):
    monkeypatch.setenv('db__HOST', 'localhost')
    monkeypatch.setenv('db__PORT', '5432')

    class DBSettings(BaseSettings):
        db: Dict[str, str] = {}

        @classmethod
        def settings_customise_sources(cls, settings_cls, **kwargs):
            return (EnvSettingsSource(settings_cls, case_sensitive=True, env_nested_delimiter='__'),)

    s = DBSettings()
    assert s.db.get('HOST') == 'localhost'
    assert s.db.get('PORT') == '5432'
