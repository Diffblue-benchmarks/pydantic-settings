"""Tests for pydantic_settings.sources.utils module."""

from collections import deque
from dataclasses import dataclass
from enum import Enum, IntEnum
from types import FunctionType, BuiltinFunctionType
from typing import Annotated, Any, Dict, List, Optional, Set, TypeVar, Union

import pytest
from pydantic import BaseModel, Field, Json, Secret, RootModel
from pydantic.dataclasses import dataclass as pydantic_dataclass
from pydantic.fields import FieldInfo
from pydantic.types import Strict

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
from pydantic_settings.sources.types import EnvNoneType


# Test fixtures
class Color(Enum):
    RED = 'red'
    GREEN = 'green'
    BLUE = 'blue'


class Priority(IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3


@pydantic_dataclass
class SampleDataclass:
    name: str
    age: int


class SampleModel(BaseModel):
    name: str
    age: int


class SampleRootModel(RootModel[Dict[str, Any]]):
    pass


# Tests for _get_env_var_key
def test_get_env_var_key_case_sensitive():
    assert _get_env_var_key('MY_VAR', case_sensitive=True) == 'MY_VAR'


def test_get_env_var_key_case_insensitive():
    assert _get_env_var_key('MY_VAR', case_sensitive=False) == 'my_var'


# Tests for _parse_env_none_str
def test_parse_env_none_str_no_none_str():
    assert _parse_env_none_str('value') == 'value'


def test_parse_env_none_str_with_none_str_matching():
    result = _parse_env_none_str('null', parse_none_str='null')
    assert isinstance(result, EnvNoneType)


def test_parse_env_none_str_with_none_str_not_matching():
    assert _parse_env_none_str('value', parse_none_str='null') == 'value'


def test_parse_env_none_str_with_none_value():
    assert _parse_env_none_str(None, parse_none_str='null') is None


# Tests for parse_env_vars
def test_parse_env_vars_basic():
    env_vars = {'KEY1': 'value1', 'KEY2': 'value2'}
    result = parse_env_vars(env_vars)
    assert result == {'key1': 'value1', 'key2': 'value2'}


def test_parse_env_vars_case_sensitive():
    env_vars = {'KEY1': 'value1', 'KEY2': 'value2'}
    result = parse_env_vars(env_vars, case_sensitive=True)
    assert result == {'KEY1': 'value1', 'KEY2': 'value2'}


def test_parse_env_vars_ignore_empty():
    env_vars = {'KEY1': 'value1', 'KEY2': '', 'KEY3': 'value3'}
    result = parse_env_vars(env_vars, ignore_empty=True)
    assert result == {'key1': 'value1', 'key3': 'value3'}


def test_parse_env_vars_with_parse_none_str():
    env_vars = {'KEY1': 'null', 'KEY2': 'value2'}
    result = parse_env_vars(env_vars, parse_none_str='null')
    assert isinstance(result['key1'], EnvNoneType)
    assert result['key2'] == 'value2'


# Tests for _substitute_typevars
def test_substitute_typevars_simple():
    T = TypeVar('T')
    param_map = {T: int}
    result = _substitute_typevars(T, param_map)
    assert result == int


def test_substitute_typevars_no_substitution():
    result = _substitute_typevars(int, {})
    assert result == int


def test_substitute_typevars_with_generic():
    T = TypeVar('T')
    param_map = {T: str}
    result = _substitute_typevars(List[T], param_map)
    # In Python 3.9+, result is list[str] (builtin generic)
    from typing import get_origin, get_args
    assert get_origin(result) in (list, List)
    assert get_args(result) == (str,)


def test_substitute_typevars_nested():
    T = TypeVar('T')
    param_map = {T: int}
    result = _substitute_typevars(Dict[str, T], param_map)
    # In Python 3.9+, result is dict[str, int] (builtin generic)
    from typing import get_origin, get_args
    assert get_origin(result) in (dict, Dict)
    assert get_args(result) == (str, int)


def test_substitute_typevars_union():
    T = TypeVar('T')
    param_map = {T: int}
    result = _substitute_typevars(Union[T, str], param_map)
    # Union types can be represented differently, so check both forms
    assert result == Union[int, str] or result == int | str


# Tests for _resolve_type_alias
def test_resolve_type_alias_non_alias():
    result = _resolve_type_alias(str)
    assert result == str


@pytest.mark.skip(reason="TypeAliasType requires Python 3.12+")
def test_resolve_type_alias_type_alias():
    # This test would require Python 3.12+ TypeAliasType
    pass


# Tests for _annotation_is_complex
def test_annotation_is_complex_simple_type():
    assert not _annotation_is_complex(int, [])


def test_annotation_is_complex_base_model():
    assert _annotation_is_complex(SampleModel, [])


def test_annotation_is_complex_list():
    assert _annotation_is_complex(List[int], [])


def test_annotation_is_complex_dict():
    assert _annotation_is_complex(Dict[str, int], [])


def test_annotation_is_complex_json_metadata():
    assert not _annotation_is_complex(str, [Json()])


def test_annotation_is_complex_secret():
    assert not _annotation_is_complex(Secret[str], [])


def test_annotation_is_complex_annotated():
    assert not _annotation_is_complex(Annotated[str, Field(...)], [])


def test_annotation_is_complex_root_model():
    assert _annotation_is_complex(SampleRootModel, [])


# Tests for _get_field_metadata
def test_get_field_metadata_basic():
    field_info = FieldInfo(annotation=str, default='test')
    metadata = _get_field_metadata(field_info)
    assert isinstance(metadata, list)


def test_get_field_metadata_with_annotated():
    field_info = FieldInfo(annotation=Annotated[str, 'meta1', 'meta2'], default='test')
    metadata = _get_field_metadata(field_info)
    assert 'meta1' in metadata
    assert 'meta2' in metadata


# Tests for _annotation_is_complex_inner
def test_annotation_is_complex_inner_str():
    assert not _annotation_is_complex_inner(str)


def test_annotation_is_complex_inner_bytes():
    assert not _annotation_is_complex_inner(bytes)


def test_annotation_is_complex_inner_base_model():
    assert _annotation_is_complex_inner(SampleModel)


def test_annotation_is_complex_inner_mapping():
    assert _annotation_is_complex_inner(dict)


def test_annotation_is_complex_inner_sequence():
    assert _annotation_is_complex_inner(list)


def test_annotation_is_complex_inner_tuple():
    assert _annotation_is_complex_inner(tuple)


def test_annotation_is_complex_inner_deque():
    assert _annotation_is_complex_inner(deque)


def test_annotation_is_complex_inner_dataclass():
    @dataclass
    class MyDataclass:
        x: int

    assert _annotation_is_complex_inner(MyDataclass)


# Tests for _union_is_complex
def test_union_is_complex_simple():
    assert not _union_is_complex(Union[int, str], [])


def test_union_is_complex_with_model():
    assert _union_is_complex(Union[int, SampleModel], [])


def test_union_is_complex_with_list():
    assert _union_is_complex(Union[int, List[str]], [])


def test_union_is_complex_nested_union():
    assert _union_is_complex(Union[int, Union[str, List[int]]], [])


def test_union_is_complex_with_json_metadata():
    assert not _union_is_complex(Union[int, Annotated[List[str], Json()]], [])


# Tests for _union_has_strict_types
def test_union_has_strict_types_no_strict():
    assert not _union_has_strict_types(Union[int, str])


def test_union_has_strict_types_with_strict():
    assert _union_has_strict_types(Union[Annotated[int, Strict()], str])


# Tests for _annotation_contains_types
def test_annotation_contains_types_direct_match():
    assert _annotation_contains_types(list, (list,))


def test_annotation_contains_types_no_match():
    assert not _annotation_contains_types(int, (str, list))


def test_annotation_contains_types_origin_match():
    assert _annotation_contains_types(List[int], (list,))


def test_annotation_contains_types_nested():
    assert _annotation_contains_types(Dict[str, List[int]], (list,))


def test_annotation_contains_types_with_collect():
    collect = set()
    _annotation_contains_types(Dict[str, List[int]], (list,), collect=collect)
    assert len(collect) > 0


def test_annotation_contains_types_strip_annotated():
    assert _annotation_contains_types(Annotated[List[int], 'meta'], (list,), is_strip_annotated=True)


def test_annotation_contains_types_is_instance():
    assert _annotation_contains_types(List[int], (list,), is_instance=True)


# Tests for _strip_annotated
def test_strip_annotated_basic():
    result = _strip_annotated(Annotated[str, 'meta'])
    assert result == str


def test_strip_annotated_non_annotated():
    result = _strip_annotated(str)
    assert result == str


# Tests for _annotation_enum_val_to_name
def test_annotation_enum_val_to_name_found():
    result = _annotation_enum_val_to_name(Color, Color.RED)
    assert result == 'RED'


def test_annotation_enum_val_to_name_not_found():
    result = _annotation_enum_val_to_name(Color, 'yellow')
    assert result is None


def test_annotation_enum_val_to_name_int_enum():
    result = _annotation_enum_val_to_name(Priority, 1)
    assert result == 'LOW'


# Tests for _annotation_enum_name_to_val
def test_annotation_enum_name_to_val_found():
    result = _annotation_enum_name_to_val(Color, 'RED')
    assert result == Color.RED


def test_annotation_enum_name_to_val_not_found():
    result = _annotation_enum_name_to_val(Color, 'YELLOW')
    assert result is None


def test_annotation_enum_name_to_val_int_enum():
    result = _annotation_enum_name_to_val(Priority, 'LOW')
    assert result == Priority.LOW


# Tests for _literal_has_numeric_enum
def test_literal_has_numeric_enum_true():
    from typing import Literal
    result = _literal_has_numeric_enum(Literal[Priority.LOW, Priority.HIGH])
    assert result is True


def test_literal_has_numeric_enum_false():
    from typing import Literal
    result = _literal_has_numeric_enum(Literal['a', 'b'])
    assert result is False


def test_literal_has_numeric_enum_annotated():
    from typing import Literal
    result = _literal_has_numeric_enum(Annotated[Literal[Priority.LOW], Field(...)])
    assert result is True


def test_literal_has_numeric_enum_optional():
    from typing import Literal
    result = _literal_has_numeric_enum(Optional[Literal[Priority.HIGH]])
    assert result is True


def test_literal_has_numeric_enum_non_literal():
    result = _literal_has_numeric_enum(int)
    assert result is False


# Tests for _get_model_fields
def test_get_model_fields_base_model():
    fields = _get_model_fields(SampleModel)
    assert 'name' in fields
    assert 'age' in fields


def test_get_model_fields_pydantic_dataclass():
    fields = _get_model_fields(SampleDataclass)
    assert 'name' in fields
    assert 'age' in fields


def test_get_model_fields_invalid():
    with pytest.raises(Exception):
        _get_model_fields(str)


# Tests for _get_alias_names
def test_get_alias_names_no_alias():
    field_info = FieldInfo(annotation=str, default='test')
    alias_names, is_alias_path_only = _get_alias_names('field_name', field_info)
    assert 'field_name' in alias_names
    assert not is_alias_path_only


def test_get_alias_names_with_alias():
    field_info = FieldInfo(annotation=str, default='test', alias='alias_name')
    alias_names, is_alias_path_only = _get_alias_names('field_name', field_info)
    assert 'alias_name' in alias_names
    assert not is_alias_path_only


def test_get_alias_names_case_insensitive():
    field_info = FieldInfo(annotation=str, default='test', alias='AliasName')
    alias_names, is_alias_path_only = _get_alias_names('field_name', field_info, case_sensitive=False)
    assert 'aliasname' in alias_names


def test_get_alias_names_populate_by_name():
    field_info = FieldInfo(annotation=str, default='test', alias='alias_name')
    alias_names, is_alias_path_only = _get_alias_names('field_name', field_info, populate_by_name=True)
    assert 'field_name' in alias_names
    assert 'alias_name' in alias_names


def test_get_alias_names_validation_alias():
    field_info = FieldInfo(annotation=str, default='test', validation_alias='valid_alias')
    alias_names, is_alias_path_only = _get_alias_names('field_name', field_info)
    assert 'valid_alias' in alias_names


def test_get_alias_names_alias_choices():
    from pydantic import AliasChoices
    field_info = FieldInfo(
        annotation=str,
        default='test',
        validation_alias=AliasChoices('alias1', 'alias2')
    )
    alias_names, is_alias_path_only = _get_alias_names('field_name', field_info)
    assert 'alias1' in alias_names
    assert 'alias2' in alias_names


def test_get_alias_names_alias_path():
    from pydantic import AliasPath
    field_info = FieldInfo(
        annotation=str,
        default='test',
        validation_alias=AliasPath('nested', 0)
    )
    alias_path_args = {}
    alias_names, is_alias_path_only = _get_alias_names('field_name', field_info, alias_path_args=alias_path_args)
    assert 'nested' in alias_names
    assert alias_path_args.get('nested') == 0


def test_get_alias_names_alias_path_no_index():
    from pydantic import AliasPath
    field_info = FieldInfo(
        annotation=str,
        default='test',
        validation_alias=AliasPath('nested')
    )
    alias_path_args = {}
    alias_names, is_alias_path_only = _get_alias_names('field_name', field_info, alias_path_args=alias_path_args)
    assert 'nested' in alias_names
    assert alias_path_args.get('nested') is None


# Tests for _is_function
def test_is_function_lambda():
    assert _is_function(lambda x: x)


def test_is_function_def():
    def my_func():
        pass

    assert _is_function(my_func)


def test_is_function_builtin():
    assert _is_function(len)


def test_is_function_not_function():
    assert not _is_function(42)
    assert not _is_function('string')
    assert not _is_function(SampleModel)
