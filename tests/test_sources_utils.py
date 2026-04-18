"""Tests for pydantic_settings.sources.utils module."""

from __future__ import annotations

import enum
from collections import deque
from typing import Annotated, Any, Dict, List, Literal, Optional, TypeVar, Union

import pytest
from pydantic import AliasChoices, AliasPath, BaseModel, Field, Json, RootModel, Secret
from pydantic.fields import FieldInfo
from pydantic.types import Strict

from pydantic_settings.exceptions import SettingsError
from pydantic_settings.sources.types import EnvNoneType
from pydantic_settings.sources.utils import (
    _annotation_contains_types,
    _annotation_enum_name_to_val,
    _annotation_enum_val_to_name,
    _annotation_is_complex,
    _annotation_is_complex_inner,
    _get_alias_names,
    _get_env_var_key,
    _get_field_metadata,
    _get_model_fields,
    _is_function,
    _literal_has_numeric_enum,
    _parse_env_none_str,
    _resolve_type_alias,
    _strip_annotated,
    _substitute_typevars,
    _union_has_strict_types,
    _union_is_complex,
    parse_env_vars,
)


# --- Helper types for testing ---


class MyModel(BaseModel):
    name: str = 'default'
    age: int = 0


class MyRootModel(RootModel[List[int]]):
    pass


class Color(enum.Enum):
    RED = 1
    GREEN = 2
    BLUE = 3


class IntColor(enum.IntEnum):
    RED = 1
    GREEN = 2
    BLUE = 3


class FloatColor(float, enum.Enum):
    RED = 1.0
    GREEN = 2.0
    BLUE = 3.0


# --- Tests for _get_env_var_key ---


def test_get_env_var_key_case_insensitive():
    assert _get_env_var_key('MY_VAR') == 'my_var'


def test_get_env_var_key_case_sensitive():
    assert _get_env_var_key('MY_VAR', case_sensitive=True) == 'MY_VAR'


def test_get_env_var_key_already_lower():
    assert _get_env_var_key('my_var') == 'my_var'


# --- Tests for _parse_env_none_str ---


def test_parse_env_none_str_no_match():
    assert _parse_env_none_str('hello', 'None') == 'hello'


def test_parse_env_none_str_match():
    result = _parse_env_none_str('None', 'None')
    assert isinstance(result, EnvNoneType)
    assert result == 'None'


def test_parse_env_none_str_none_parse_none_str():
    assert _parse_env_none_str('hello', None) == 'hello'


def test_parse_env_none_str_none_value():
    assert _parse_env_none_str(None, 'None') is None


# --- Tests for parse_env_vars ---


def test_parse_env_vars_basic():
    env = {'MY_KEY': 'value', 'OTHER': 'data'}
    result = parse_env_vars(env)
    assert result == {'my_key': 'value', 'other': 'data'}


def test_parse_env_vars_case_sensitive():
    env = {'MY_KEY': 'value'}
    result = parse_env_vars(env, case_sensitive=True)
    assert result == {'MY_KEY': 'value'}


def test_parse_env_vars_ignore_empty():
    env = {'KEY1': 'value', 'KEY2': '', 'KEY3': 'data'}
    result = parse_env_vars(env, ignore_empty=True)
    assert 'key2' not in result
    assert result['key1'] == 'value'
    assert result['key3'] == 'data'


def test_parse_env_vars_ignore_empty_false():
    env = {'KEY1': '', 'KEY2': 'data'}
    result = parse_env_vars(env, ignore_empty=False)
    assert 'key1' in result
    assert result['key1'] == ''


def test_parse_env_vars_parse_none_str():
    env = {'KEY1': 'None', 'KEY2': 'data'}
    result = parse_env_vars(env, parse_none_str='None')
    assert isinstance(result['key1'], EnvNoneType)
    assert result['key2'] == 'data'


# --- Tests for _substitute_typevars ---


def test_substitute_typevars_with_typevar():
    T = TypeVar('T')
    param_map = {T: int}
    assert _substitute_typevars(T, param_map) is int


def test_substitute_typevars_no_match():
    T = TypeVar('T')
    U = TypeVar('U')
    param_map = {U: int}
    assert _substitute_typevars(T, param_map) is T


def test_substitute_typevars_plain_type():
    assert _substitute_typevars(int, {}) is int


def test_substitute_typevars_generic_type():
    T = TypeVar('T')
    param_map = {T: int}
    tp = List[T]
    result = _substitute_typevars(tp, param_map)
    assert result == list[int]


def test_substitute_typevars_no_change():
    tp = List[int]
    result = _substitute_typevars(tp, {})
    assert result is tp


def test_substitute_typevars_union_type():
    T = TypeVar('T')
    param_map = {T: str}
    tp = Union[T, int]
    result = _substitute_typevars(tp, param_map)
    assert result == Union[str, int]


# --- Tests for _resolve_type_alias ---


def test_resolve_type_alias_non_alias():
    assert _resolve_type_alias(int) is int


def test_resolve_type_alias_plain_type():
    assert _resolve_type_alias(List[int]) == List[int]


# --- Tests for _annotation_is_complex ---


def test_annotation_is_complex_str():
    assert _annotation_is_complex(str, []) is False


def test_annotation_is_complex_int():
    assert _annotation_is_complex(int, []) is False


def test_annotation_is_complex_model():
    assert _annotation_is_complex(MyModel, []) is True


def test_annotation_is_complex_list():
    assert _annotation_is_complex(List[int], []) is True


def test_annotation_is_complex_dict():
    assert _annotation_is_complex(Dict[str, int], []) is True


def test_annotation_is_complex_json_metadata():
    assert _annotation_is_complex(List[int], [Json()]) is False


def test_annotation_is_complex_annotated():
    annotation = Annotated[List[int], 'some_metadata']
    assert _annotation_is_complex(annotation, []) is True


def test_annotation_is_complex_annotated_str():
    annotation = Annotated[str, 'some_metadata']
    assert _annotation_is_complex(annotation, []) is False


def test_annotation_is_complex_root_model():
    assert _annotation_is_complex(MyRootModel, []) is True


def test_annotation_is_complex_secret():
    assert _annotation_is_complex(Secret[str], []) is False


def test_annotation_is_complex_set():
    assert _annotation_is_complex(set, []) is True


def test_annotation_is_complex_frozenset():
    assert _annotation_is_complex(frozenset, []) is True


def test_annotation_is_complex_tuple():
    assert _annotation_is_complex(tuple, []) is True


def test_annotation_is_complex_deque():
    assert _annotation_is_complex(deque, []) is True


def test_annotation_is_complex_bytes():
    assert _annotation_is_complex(bytes, []) is False


# --- Tests for _get_field_metadata ---


def test_get_field_metadata_plain():
    field = FieldInfo(annotation=str)
    result = _get_field_metadata(field)
    assert isinstance(result, list)


def test_get_field_metadata_annotated():
    field = FieldInfo(annotation=Annotated[str, Strict()])
    result = _get_field_metadata(field)
    assert any(isinstance(m, Strict) for m in result)


# --- Tests for _annotation_is_complex_inner ---


def test_annotation_is_complex_inner_str():
    assert _annotation_is_complex_inner(str) is False


def test_annotation_is_complex_inner_bytes():
    assert _annotation_is_complex_inner(bytes) is False


def test_annotation_is_complex_inner_model():
    assert _annotation_is_complex_inner(MyModel) is True


def test_annotation_is_complex_inner_list():
    assert _annotation_is_complex_inner(list) is True


def test_annotation_is_complex_inner_dict():
    assert _annotation_is_complex_inner(dict) is True


def test_annotation_is_complex_inner_tuple():
    assert _annotation_is_complex_inner(tuple) is True


def test_annotation_is_complex_inner_set():
    assert _annotation_is_complex_inner(set) is True


def test_annotation_is_complex_inner_frozenset():
    assert _annotation_is_complex_inner(frozenset) is True


def test_annotation_is_complex_inner_deque():
    assert _annotation_is_complex_inner(deque) is True


def test_annotation_is_complex_inner_none():
    assert _annotation_is_complex_inner(None) is False


def test_annotation_is_complex_inner_int():
    assert _annotation_is_complex_inner(int) is False


# --- Tests for _union_is_complex ---


def test_union_is_complex_with_model():
    assert _union_is_complex(Union[str, MyModel], []) is True


def test_union_is_complex_simple_types():
    assert _union_is_complex(Union[str, int], []) is False


def test_union_is_complex_with_list():
    assert _union_is_complex(Union[str, List[int]], []) is True


def test_union_is_complex_optional_str():
    assert _union_is_complex(Optional[str], []) is False


def test_union_is_complex_optional_model():
    assert _union_is_complex(Optional[MyModel], []) is True


def test_union_is_complex_annotated_union_with_json_skips():
    """An Annotated[Union[...], Json()] arg should be skipped (not flagged as complex)."""
    annotation = Union[str, Annotated[Union[str, MyModel], Json()]]
    assert _union_is_complex(annotation, []) is False


def test_union_is_complex_annotated_nested_union_recurses():
    """An Annotated[Union[...], non-Json] arg should recurse into the inner Union."""
    annotation = Union[str, Annotated[Union[str, MyModel], 'some_meta']]
    assert _union_is_complex(annotation, []) is True


def test_union_is_complex_annotated_nested_union_simple_types():
    """An Annotated[Union[simple, simple], non-Json] should return False when inner union is not complex."""
    annotation = Union[str, Annotated[Union[str, int], 'some_meta']]
    assert _union_is_complex(annotation, []) is False


# --- Tests for _union_has_strict_types ---


def test_union_has_strict_types_true():
    annotation = Union[str, Annotated[int, Strict()]]
    assert _union_has_strict_types(annotation) is True


def test_union_has_strict_types_false():
    annotation = Union[str, int]
    assert _union_has_strict_types(annotation) is False


def test_union_has_strict_types_no_annotated():
    annotation = Optional[str]
    assert _union_has_strict_types(annotation) is False


# --- Tests for _annotation_contains_types ---


def test_annotation_contains_types_direct_match():
    assert _annotation_contains_types(int, (int,)) is True


def test_annotation_contains_types_no_match():
    assert _annotation_contains_types(str, (int,)) is False


def test_annotation_contains_types_origin_match():
    assert _annotation_contains_types(List[int], (list,)) is True


def test_annotation_contains_types_nested():
    assert _annotation_contains_types(List[Dict[str, int]], (dict,)) is True


def test_annotation_contains_types_no_include_origin():
    assert _annotation_contains_types(List[int], (list,), is_include_origin=False) is False


def test_annotation_contains_types_strip_annotated():
    annotation = Annotated[List[int], 'meta']
    assert _annotation_contains_types(annotation, (list,), is_strip_annotated=True) is True


def test_annotation_contains_types_collect():
    collected: set[Any] = set()
    _annotation_contains_types(List[int], (int,), collect=collected)
    assert int in collected


def test_annotation_contains_types_is_instance():
    assert _annotation_contains_types(int, (type,), is_instance=True) is True


def test_annotation_contains_types_collect_with_origin():
    collected: set[Any] = set()
    _annotation_contains_types(List[int], (list,), collect=collected)
    assert List[int] in collected


def test_annotation_contains_types_is_instance_with_collect():
    collected: set[Any] = set()
    _annotation_contains_types(int, (type,), is_instance=True, collect=collected)
    assert int in collected


# --- Tests for _strip_annotated ---


def test_strip_annotated_with_annotated():
    annotation = Annotated[int, 'meta']
    result = _strip_annotated(annotation)
    assert result is int


def test_strip_annotated_without_annotated():
    result = _strip_annotated(int)
    assert result is int


def test_strip_annotated_list():
    result = _strip_annotated(List[int])
    assert result == List[int]


# --- Tests for _annotation_enum_val_to_name ---


def test_annotation_enum_val_to_name_found():
    assert _annotation_enum_val_to_name(Color, Color.RED) == 'RED'


def test_annotation_enum_val_to_name_not_found():
    assert _annotation_enum_val_to_name(Color, 'nonexistent') is None


def test_annotation_enum_val_to_name_none_annotation():
    assert _annotation_enum_val_to_name(None, 'val') is None


def test_annotation_enum_val_to_name_non_enum():
    assert _annotation_enum_val_to_name(int, 1) is None


# --- Tests for _annotation_enum_name_to_val ---


def test_annotation_enum_name_to_val_found():
    result = _annotation_enum_name_to_val(Color, 'RED')
    assert result is Color.RED


def test_annotation_enum_name_to_val_not_found():
    assert _annotation_enum_name_to_val(Color, 'PURPLE') is None


def test_annotation_enum_name_to_val_none_annotation():
    assert _annotation_enum_name_to_val(None, 'RED') is None


def test_annotation_enum_name_to_val_non_enum():
    assert _annotation_enum_name_to_val(str, 'x') is None


# --- Tests for _literal_has_numeric_enum ---


def test_literal_has_numeric_enum_int_enum():
    annotation = Literal[IntColor.RED, IntColor.GREEN]
    assert _literal_has_numeric_enum(annotation) is True


def test_literal_has_numeric_enum_float_enum():
    annotation = Literal[FloatColor.RED]
    assert _literal_has_numeric_enum(annotation) is True


def test_literal_has_numeric_enum_no_enum():
    annotation = Literal['a', 'b']
    assert _literal_has_numeric_enum(annotation) is False


def test_literal_has_numeric_enum_non_literal():
    assert _literal_has_numeric_enum(int) is False


def test_literal_has_numeric_enum_annotated():
    annotation = Annotated[Literal[IntColor.RED], 'meta']
    assert _literal_has_numeric_enum(annotation) is True


def test_literal_has_numeric_enum_optional():
    annotation = Optional[Literal[IntColor.RED]]
    assert _literal_has_numeric_enum(annotation) is True


def test_literal_has_numeric_enum_optional_no_enum():
    annotation = Optional[Literal['a', 'b']]
    assert _literal_has_numeric_enum(annotation) is False


# --- Tests for _get_model_fields ---


def test_get_model_fields_base_model():
    fields = _get_model_fields(MyModel)
    assert 'name' in fields
    assert 'age' in fields


def test_get_model_fields_invalid():
    with pytest.raises(SettingsError, match='is not subclass of BaseModel'):
        _get_model_fields(int)  # type: ignore[arg-type]


# --- Tests for _get_alias_names ---


def test_get_alias_names_no_alias():
    field = FieldInfo(annotation=str)
    names, is_alias_path_only = _get_alias_names('my_field', field)
    assert 'my_field' in names
    assert is_alias_path_only is False


def test_get_alias_names_with_alias():

    class M(BaseModel):
        my_field: str = Field(alias='myField')

    field = M.model_fields['my_field']
    names, is_alias_path_only = _get_alias_names('my_field', field)
    assert 'myField' in names
    assert is_alias_path_only is False


def test_get_alias_names_case_insensitive():
    field = FieldInfo(annotation=str)
    names, _ = _get_alias_names('MY_FIELD', field, case_sensitive=False)
    assert 'my_field' in names


def test_get_alias_names_with_validation_alias_str():

    class M(BaseModel):
        my_field: str = Field(validation_alias='val_alias')

    field = M.model_fields['my_field']
    names, is_alias_path_only = _get_alias_names('my_field', field)
    assert 'val_alias' in names
    assert is_alias_path_only is False


def test_get_alias_names_with_alias_choices():

    class M(BaseModel):
        my_field: str = Field(validation_alias=AliasChoices('name1', 'name2'))

    field = M.model_fields['my_field']
    names, is_alias_path_only = _get_alias_names('my_field', field)
    assert 'name1' in names
    assert 'name2' in names
    assert is_alias_path_only is False


def test_get_alias_names_with_alias_path():

    class M(BaseModel):
        my_field: str = Field(validation_alias=AliasPath('nested', 0))

    field = M.model_fields['my_field']
    alias_path_args: dict[str, int | None] = {}
    names, is_alias_path_only = _get_alias_names('my_field', field, alias_path_args=alias_path_args)
    assert 'nested' in names
    assert is_alias_path_only is True
    assert alias_path_args.get('nested') == 0


def test_get_alias_names_with_alias_path_no_index():

    class M(BaseModel):
        my_field: str = Field(validation_alias=AliasPath('nested'))

    field = M.model_fields['my_field']
    alias_path_args: dict[str, int | None] = {}
    names, _ = _get_alias_names('my_field', field, alias_path_args=alias_path_args)
    assert 'nested' in names
    assert alias_path_args.get('nested') is None


def test_get_alias_names_with_alias_choices_containing_path():

    class M(BaseModel):
        my_field: str = Field(validation_alias=AliasChoices('str_name', AliasPath('path_name', 1)))

    field = M.model_fields['my_field']
    alias_path_args: dict[str, int | None] = {}
    names, is_alias_path_only = _get_alias_names('my_field', field, alias_path_args=alias_path_args)
    assert 'str_name' in names
    assert is_alias_path_only is False


def test_get_alias_names_populate_by_name():

    class M(BaseModel):
        my_field: str = Field(alias='myField')

    field = M.model_fields['my_field']
    names, _ = _get_alias_names('my_field', field, populate_by_name=True)
    assert 'myField' in names
    assert 'my_field' in names


def test_get_alias_names_populate_by_name_already_present():
    field = FieldInfo(annotation=str)
    names, _ = _get_alias_names('my_field', field, populate_by_name=True)
    assert names.count('my_field') == 1


def test_get_alias_names_alias_path_case_insensitive():

    class M(BaseModel):
        my_field: str = Field(validation_alias=AliasPath('NESTED', 0))

    field = M.model_fields['my_field']
    alias_path_args: dict[str, int | None] = {}
    names, _ = _get_alias_names('my_field', field, alias_path_args=alias_path_args, case_sensitive=False)
    assert 'nested' in names


# --- Tests for _is_function ---


def test_is_function_regular():
    def my_func():
        pass

    assert _is_function(my_func) is True


def test_is_function_builtin():
    assert _is_function(len) is True


def test_is_function_lambda():
    assert _is_function(lambda x: x) is True


def test_is_function_class():
    assert _is_function(int) is False


def test_is_function_string():
    assert _is_function('hello') is False


def test_is_function_none():
    assert _is_function(None) is False
