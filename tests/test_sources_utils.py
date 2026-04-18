"""Tests for pydantic_settings.sources.utils."""

from __future__ import annotations

import enum
from collections import deque
from typing import Annotated, Any, Dict, FrozenSet, List, Literal, Optional, Set, Tuple, TypeVar, Union

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


# --- helpers ---


class MyModel(BaseModel):
    x: int = 0
    y: str = 'hello'


class MyEnum(enum.Enum):
    A = 'a'
    B = 'b'


class MyIntEnum(enum.IntEnum):
    ONE = 1
    TWO = 2


class MyRootModel(RootModel[List[int]]):
    pass


class SimpleRootModel(RootModel[str]):
    pass


# --- _get_env_var_key ---


def test_get_env_var_key_case_sensitive():
    assert _get_env_var_key('MY_VAR', case_sensitive=True) == 'MY_VAR'


def test_get_env_var_key_case_insensitive():
    assert _get_env_var_key('MY_VAR', case_sensitive=False) == 'my_var'


def test_get_env_var_key_default():
    assert _get_env_var_key('Hello') == 'hello'


# --- _parse_env_none_str ---


def test_parse_env_none_str_no_match():
    assert _parse_env_none_str('value', parse_none_str='none') == 'value'


def test_parse_env_none_str_match():
    result = _parse_env_none_str('none', parse_none_str='none')
    assert isinstance(result, EnvNoneType)
    assert result == 'none'


def test_parse_env_none_str_none_value():
    assert _parse_env_none_str(None) is None


def test_parse_env_none_str_none_parse_none_str():
    assert _parse_env_none_str('value', parse_none_str=None) == 'value'


# --- parse_env_vars ---


def test_parse_env_vars_basic():
    env = {'MY_VAR': 'val', 'OTHER': 'x'}
    result = parse_env_vars(env)
    assert result == {'my_var': 'val', 'other': 'x'}


def test_parse_env_vars_case_sensitive():
    env = {'MY_VAR': 'val'}
    result = parse_env_vars(env, case_sensitive=True)
    assert result == {'MY_VAR': 'val'}


def test_parse_env_vars_ignore_empty():
    env = {'A': '', 'B': 'val'}
    result = parse_env_vars(env, ignore_empty=True)
    assert result == {'b': 'val'}


def test_parse_env_vars_keep_empty():
    env = {'A': '', 'B': 'val'}
    result = parse_env_vars(env, ignore_empty=False)
    assert result == {'a': '', 'b': 'val'}


def test_parse_env_vars_parse_none_str():
    env = {'A': 'None', 'B': 'val'}
    result = parse_env_vars(env, parse_none_str='None')
    assert isinstance(result['a'], EnvNoneType)
    assert result['b'] == 'val'


def test_parse_env_vars_none_value():
    env = {'A': None}
    result = parse_env_vars(env)
    assert result == {'a': None}


# --- _substitute_typevars ---


def test_substitute_typevars_plain_type():
    assert _substitute_typevars(int, {}) is int


def test_substitute_typevars_typevar_match():
    T = TypeVar('T')
    result = _substitute_typevars(T, {T: str})
    assert result is str


def test_substitute_typevars_typevar_no_match():
    T = TypeVar('T')
    S = TypeVar('S')
    result = _substitute_typevars(T, {S: str})
    assert result is T


def test_substitute_typevars_generic():
    T = TypeVar('T')
    tp = List[T]
    result = _substitute_typevars(tp, {T: int})
    assert result == list[int]


def test_substitute_typevars_no_change():
    tp = List[int]
    result = _substitute_typevars(tp, {})
    assert result is tp


def test_substitute_typevars_union():
    T = TypeVar('T')
    tp = Union[T, int]
    result = _substitute_typevars(tp, {T: str})
    assert result == Union[str, int]


# --- _resolve_type_alias ---


def test_resolve_type_alias_plain_type():
    assert _resolve_type_alias(int) is int


def test_resolve_type_alias_non_alias():
    assert _resolve_type_alias(List[int]) == List[int]


# --- _annotation_is_complex ---


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


def test_annotation_is_complex_set():
    assert _annotation_is_complex(Set[int], []) is True


def test_annotation_is_complex_frozenset():
    assert _annotation_is_complex(FrozenSet[int], []) is True


def test_annotation_is_complex_tuple():
    assert _annotation_is_complex(Tuple[int, str], []) is True


def test_annotation_is_complex_deque():
    assert _annotation_is_complex(deque, []) is True


def test_annotation_is_complex_json_metadata():
    assert _annotation_is_complex(Dict[str, int], [Json()]) is False


def test_annotation_is_complex_root_model():
    assert _annotation_is_complex(MyRootModel, []) is True


def test_annotation_is_complex_simple_root_model():
    assert _annotation_is_complex(SimpleRootModel, []) is False


def test_annotation_is_complex_annotated():
    assert _annotation_is_complex(Annotated[List[int], 'some_meta'], []) is True


def test_annotation_is_complex_annotated_str():
    assert _annotation_is_complex(Annotated[str, 'some_meta'], []) is False


def test_annotation_is_complex_bytes():
    assert _annotation_is_complex(bytes, []) is False


def test_annotation_is_complex_secret():
    assert _annotation_is_complex(Secret[str], []) is False


# --- _get_field_metadata ---


def test_get_field_metadata_plain():
    field = FieldInfo(annotation=int)
    meta = _get_field_metadata(field)
    assert isinstance(meta, list)


def test_get_field_metadata_annotated():
    field = FieldInfo(annotation=Annotated[int, 'extra'])
    meta = _get_field_metadata(field)
    assert 'extra' in meta


# --- _annotation_is_complex_inner ---


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


def test_annotation_is_complex_inner_set():
    assert _annotation_is_complex_inner(set) is True


def test_annotation_is_complex_inner_frozenset():
    assert _annotation_is_complex_inner(frozenset) is True


def test_annotation_is_complex_inner_tuple():
    assert _annotation_is_complex_inner(tuple) is True


def test_annotation_is_complex_inner_deque():
    assert _annotation_is_complex_inner(deque) is True


def test_annotation_is_complex_inner_none():
    assert _annotation_is_complex_inner(None) is False


def test_annotation_is_complex_inner_int():
    assert _annotation_is_complex_inner(int) is False


# --- _union_is_complex ---


def test_union_is_complex_with_model():
    assert _union_is_complex(Union[str, MyModel], []) is True


def test_union_is_complex_simple():
    assert _union_is_complex(Union[str, int], []) is False


def test_union_is_complex_with_list():
    assert _union_is_complex(Union[str, List[int]], []) is True


def test_union_is_complex_optional_model():
    assert _union_is_complex(Optional[MyModel], []) is True


def test_union_is_complex_optional_str():
    assert _union_is_complex(Optional[str], []) is False


# --- _union_has_strict_types ---


def test_union_has_strict_types_true():
    annotation = Union[Annotated[int, Strict()], str]
    assert _union_has_strict_types(annotation) is True


def test_union_has_strict_types_false():
    annotation = Union[int, str]
    assert _union_has_strict_types(annotation) is False


def test_union_has_strict_types_no_strict_metadata():
    annotation = Union[Annotated[int, 'not_strict'], str]
    assert _union_has_strict_types(annotation) is False


# --- _annotation_contains_types ---


def test_annotation_contains_types_direct_match():
    assert _annotation_contains_types(int, (int,)) is True


def test_annotation_contains_types_no_match():
    assert _annotation_contains_types(int, (str,)) is False


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
    _annotation_contains_types(List[int], (list,), collect=collected)
    assert len(collected) == 1


def test_annotation_contains_types_collect_multiple():
    collected: set[Any] = set()
    _annotation_contains_types(List[Dict[str, int]], (list, dict), collect=collected)
    assert len(collected) == 2


def test_annotation_contains_types_is_instance():
    assert _annotation_contains_types(int, (type,), is_instance=True) is True


def test_annotation_contains_types_is_instance_collect():
    collected: set[Any] = set()
    _annotation_contains_types(int, (type,), is_instance=True, collect=collected)
    assert int in collected


def test_annotation_contains_types_origin_is_instance_collect():
    collected: set[Any] = set()
    _annotation_contains_types(List[int], (type,), is_instance=True, collect=collected)
    assert List[int] in collected


# --- _strip_annotated ---


def test_strip_annotated_annotated():
    annotation = Annotated[int, 'meta']
    assert _strip_annotated(annotation) is int


def test_strip_annotated_plain():
    assert _strip_annotated(int) is int


def test_strip_annotated_list():
    assert _strip_annotated(List[int]) == List[int]


# --- _annotation_enum_val_to_name ---


def test_annotation_enum_val_to_name_found():
    assert _annotation_enum_val_to_name(MyEnum, MyEnum.A) == 'A'


def test_annotation_enum_val_to_name_not_found():
    assert _annotation_enum_val_to_name(MyEnum, 'z') is None


def test_annotation_enum_val_to_name_non_enum():
    assert _annotation_enum_val_to_name(int, 1) is None


def test_annotation_enum_val_to_name_none():
    assert _annotation_enum_val_to_name(None, 'a') is None


# --- _annotation_enum_name_to_val ---


def test_annotation_enum_name_to_val_found():
    result = _annotation_enum_name_to_val(MyEnum, 'A')
    assert result is MyEnum.A


def test_annotation_enum_name_to_val_not_found():
    assert _annotation_enum_name_to_val(MyEnum, 'Z') is None


def test_annotation_enum_name_to_val_non_enum():
    assert _annotation_enum_name_to_val(int, 'A') is None


def test_annotation_enum_name_to_val_none():
    assert _annotation_enum_name_to_val(None, 'A') is None


# --- _literal_has_numeric_enum ---


def test_literal_has_numeric_enum_true():
    annotation = Literal[MyIntEnum.ONE, MyIntEnum.TWO]
    assert _literal_has_numeric_enum(annotation) is True


def test_literal_has_numeric_enum_false():
    annotation = Literal['a', 'b']
    assert _literal_has_numeric_enum(annotation) is False


def test_literal_has_numeric_enum_non_literal():
    assert _literal_has_numeric_enum(int) is False


def test_literal_has_numeric_enum_annotated():
    annotation = Annotated[Literal[MyIntEnum.ONE], 'meta']
    assert _literal_has_numeric_enum(annotation) is True


def test_literal_has_numeric_enum_optional():
    annotation = Optional[Literal[MyIntEnum.ONE]]
    assert _literal_has_numeric_enum(annotation) is True


def test_literal_has_numeric_enum_optional_no_enum():
    annotation = Optional[Literal['a']]
    assert _literal_has_numeric_enum(annotation) is False


# --- _get_model_fields ---


def test_get_model_fields_base_model():
    fields = _get_model_fields(MyModel)
    assert 'x' in fields
    assert 'y' in fields


def test_get_model_fields_invalid():
    with pytest.raises(SettingsError):
        _get_model_fields(int)  # type: ignore[arg-type]


# --- _get_alias_names ---


def test_get_alias_names_no_alias():
    field = FieldInfo(annotation=str)
    names, is_path_only = _get_alias_names('my_field', field)
    assert 'my_field' in names
    assert is_path_only is False


def test_get_alias_names_string_alias():
    field = FieldInfo(annotation=str, alias='myAlias')
    names, is_path_only = _get_alias_names('my_field', field)
    assert 'myAlias' in names
    assert is_path_only is False


def test_get_alias_names_validation_alias_str():
    field = FieldInfo(annotation=str, validation_alias='valAlias')
    names, is_path_only = _get_alias_names('my_field', field)
    assert 'valAlias' in names
    assert is_path_only is False


def test_get_alias_names_alias_path():
    field = FieldInfo(annotation=str, validation_alias=AliasPath('nested', 0))
    alias_path_args: dict[str, int | None] = {}
    names, is_path_only = _get_alias_names('my_field', field, alias_path_args=alias_path_args)
    assert 'nested' in names
    assert is_path_only is True
    assert alias_path_args.get('nested') == 0


def test_get_alias_names_alias_choices():
    field = FieldInfo(annotation=str, validation_alias=AliasChoices('opt1', 'opt2'))
    names, is_path_only = _get_alias_names('my_field', field)
    assert 'opt1' in names
    assert 'opt2' in names
    assert is_path_only is False


def test_get_alias_names_alias_choices_with_path():
    field = FieldInfo(annotation=str, validation_alias=AliasChoices('opt1', AliasPath('nested', 'key')))
    alias_path_args: dict[str, int | None] = {}
    names, is_path_only = _get_alias_names('my_field', field, alias_path_args=alias_path_args)
    assert 'opt1' in names
    assert is_path_only is False


def test_get_alias_names_case_insensitive():
    field = FieldInfo(annotation=str)
    names, _ = _get_alias_names('MY_FIELD', field, case_sensitive=False)
    assert 'my_field' in names


def test_get_alias_names_populate_by_name():
    field = FieldInfo(annotation=str, alias='myAlias')
    names, _ = _get_alias_names('my_field', field, populate_by_name=True)
    assert 'myAlias' in names
    assert 'my_field' in names


def test_get_alias_names_populate_by_name_already_present():
    field = FieldInfo(annotation=str)
    names, _ = _get_alias_names('my_field', field, populate_by_name=True)
    assert names.count('my_field') == 1


def test_get_alias_names_alias_path_no_int_second():
    field = FieldInfo(annotation=str, validation_alias=AliasPath('nested'))
    alias_path_args: dict[str, int | None] = {}
    names, is_path_only = _get_alias_names('my_field', field, alias_path_args=alias_path_args)
    assert 'nested' in names
    assert alias_path_args.get('nested') is None


def test_get_alias_names_alias_path_case_insensitive():
    field = FieldInfo(annotation=str, validation_alias=AliasPath('Nested', 0))
    alias_path_args: dict[str, int | None] = {}
    names, _ = _get_alias_names('my_field', field, alias_path_args=alias_path_args, case_sensitive=False)
    assert 'nested' in names


# --- _is_function ---


def test_is_function_true():
    def my_func():
        pass

    assert _is_function(my_func) is True


def test_is_function_lambda():
    assert _is_function(lambda: None) is True


def test_is_function_builtin():
    assert _is_function(len) is True


def test_is_function_class():
    assert _is_function(int) is False


def test_is_function_none():
    assert _is_function(None) is False


def test_is_function_string():
    assert _is_function('hello') is False


# --- _union_is_complex with nested annotated union ---


def test_union_is_complex_annotated_inner_json():
    annotation = Union[str, Annotated[Union[str, int], Json]]
    assert _union_is_complex(annotation, []) is False


def test_union_is_complex_annotated_inner_union_complex():
    annotation = Union[str, Annotated[Union[str, MyModel], 'meta']]
    assert _union_is_complex(annotation, []) is True
