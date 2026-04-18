"""Tests for pydantic_settings/sources/utils.py"""
from __future__ import annotations

import sys
from collections import deque
from enum import Enum, IntEnum
from typing import Any, Dict, List, Literal, Optional, TypeVar, Union

import pytest
from pydantic import AliasChoices, AliasPath, BaseModel, Json, RootModel, Secret
from pydantic.dataclasses import dataclass as pydantic_dataclass
from pydantic.fields import FieldInfo
from pydantic.types import Strict
from typing import Annotated, get_args, get_origin

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


# ============================================================
# Tests for _get_env_var_key
# ============================================================


def test_get_env_var_key_case_insensitive():
    assert _get_env_var_key('MY_VAR') == 'my_var'


def test_get_env_var_key_case_sensitive():
    assert _get_env_var_key('MY_VAR', case_sensitive=True) == 'MY_VAR'


def test_get_env_var_key_already_lowercase():
    assert _get_env_var_key('my_var') == 'my_var'


def test_get_env_var_key_mixed_case_sensitive():
    assert _get_env_var_key('MixedCase', case_sensitive=True) == 'MixedCase'


# ============================================================
# Tests for _parse_env_none_str
# ============================================================


def test_parse_env_none_str_no_none_str():
    assert _parse_env_none_str('hello') == 'hello'


def test_parse_env_none_str_none_value():
    assert _parse_env_none_str(None) is None


def test_parse_env_none_str_matching_none_str():
    result = _parse_env_none_str('null', 'null')
    assert isinstance(result, EnvNoneType)
    assert result == 'null'


def test_parse_env_none_str_non_matching():
    result = _parse_env_none_str('hello', 'null')
    assert result == 'hello'
    assert not isinstance(result, EnvNoneType)


def test_parse_env_none_str_parse_none_str_is_none():
    # parse_none_str is None, so no conversion happens
    result = _parse_env_none_str('null', None)
    assert result == 'null'


# ============================================================
# Tests for parse_env_vars
# ============================================================


def test_parse_env_vars_basic():
    result = parse_env_vars({'MY_VAR': 'hello'})
    assert result == {'my_var': 'hello'}


def test_parse_env_vars_case_sensitive():
    result = parse_env_vars({'MY_VAR': 'hello'}, case_sensitive=True)
    assert result == {'MY_VAR': 'hello'}


def test_parse_env_vars_ignore_empty():
    result = parse_env_vars({'MY_VAR': '', 'OTHER': 'value'}, ignore_empty=True)
    assert result == {'other': 'value'}
    assert 'my_var' not in result


def test_parse_env_vars_keep_empty_by_default():
    result = parse_env_vars({'MY_VAR': ''})
    assert result == {'my_var': ''}


def test_parse_env_vars_none_value():
    result = parse_env_vars({'MY_VAR': None})
    assert result == {'my_var': None}


def test_parse_env_vars_parse_none_str():
    result = parse_env_vars({'MY_VAR': 'null'}, parse_none_str='null')
    assert isinstance(result['my_var'], EnvNoneType)


def test_parse_env_vars_multiple_keys():
    env = {'FOO': 'bar', 'BAZ': 'qux'}
    result = parse_env_vars(env)
    assert result == {'foo': 'bar', 'baz': 'qux'}


# ============================================================
# Tests for _substitute_typevars
# ============================================================


def test_substitute_typevars_simple_typevar():
    T = TypeVar('T')
    result = _substitute_typevars(T, {T: int})
    assert result is int


def test_substitute_typevars_not_in_map():
    T = TypeVar('T')
    result = _substitute_typevars(T, {})
    assert result is T


def test_substitute_typevars_no_args():
    result = _substitute_typevars(int, {})
    assert result is int


def test_substitute_typevars_list_with_typevar():
    T = TypeVar('T')
    result = _substitute_typevars(List[T], {T: str})
    # Result may be list[str] or List[str] depending on Python version
    assert get_args(result) == (str,)


def test_substitute_typevars_union_with_typevar():
    T = TypeVar('T')
    result = _substitute_typevars(Union[T, None], {T: int})
    # Check that the args contain int and NoneType
    args = get_args(result)
    assert int in args
    assert type(None) in args


def test_substitute_typevars_no_substitution_needed():
    result = _substitute_typevars(List[int], {})
    assert result == List[int]


# ============================================================
# Tests for _resolve_type_alias (Python 3.12+)
# ============================================================


@pytest.mark.skipif(sys.version_info < (3, 12), reason='TypeAliasType requires Python 3.12+')
def test_resolve_type_alias_simple():
    import typing

    MyAlias = typing.TypeAliasType('MyAlias', int)
    result = _resolve_type_alias(MyAlias)
    assert result is int


@pytest.mark.skipif(sys.version_info < (3, 12), reason='TypeAliasType requires Python 3.12+')
def test_resolve_type_alias_parameterized():
    import typing

    T = TypeVar('T')
    MyAlias = typing.TypeAliasType('MyAlias', List[T], type_params=(T,))
    result = _resolve_type_alias(MyAlias[int])
    # Result should be a generic list with int arg
    assert get_args(result) == (int,)


def test_resolve_type_alias_non_alias():
    result = _resolve_type_alias(int)
    assert result is int


def test_resolve_type_alias_list():
    result = _resolve_type_alias(List[int])
    assert result == List[int]


# ============================================================
# Tests for _annotation_is_complex_inner
# ============================================================


def test_annotation_is_complex_inner_str():
    assert _annotation_is_complex_inner(str) is False


def test_annotation_is_complex_inner_bytes():
    assert _annotation_is_complex_inner(bytes) is False


def test_annotation_is_complex_inner_basemodel():
    class MyModel(BaseModel):
        x: int

    assert _annotation_is_complex_inner(MyModel) is True


def test_annotation_is_complex_inner_dict():
    assert _annotation_is_complex_inner(dict) is True


def test_annotation_is_complex_inner_list():
    assert _annotation_is_complex_inner(list) is True


def test_annotation_is_complex_inner_set():
    assert _annotation_is_complex_inner(set) is True


def test_annotation_is_complex_inner_frozenset():
    assert _annotation_is_complex_inner(frozenset) is True


def test_annotation_is_complex_inner_tuple():
    assert _annotation_is_complex_inner(tuple) is True


def test_annotation_is_complex_inner_deque():
    assert _annotation_is_complex_inner(deque) is True


def test_annotation_is_complex_inner_int():
    assert _annotation_is_complex_inner(int) is False


def test_annotation_is_complex_inner_none():
    assert _annotation_is_complex_inner(None) is False


# ============================================================
# Tests for _annotation_is_complex
# ============================================================


def test_annotation_is_complex_str():
    assert _annotation_is_complex(str, []) is False


def test_annotation_is_complex_int():
    assert _annotation_is_complex(int, []) is False


def test_annotation_is_complex_basemodel():
    class MyModel(BaseModel):
        x: int

    assert _annotation_is_complex(MyModel, []) is True


def test_annotation_is_complex_list():
    assert _annotation_is_complex(list, []) is True


def test_annotation_is_complex_dict():
    assert _annotation_is_complex(dict, []) is True


def test_annotation_is_complex_json_metadata():
    # Json in metadata makes it non-complex - needs a Json instance, not the class
    json_instance = Json()
    assert _annotation_is_complex(dict, [json_instance]) is False


def test_annotation_is_complex_annotated():
    # Annotated[list, ...] should be complex
    assert _annotation_is_complex(Annotated[list, 'meta'], []) is True


def test_annotation_is_complex_secret():
    assert _annotation_is_complex(Secret, []) is False


def test_annotation_is_complex_root_model():
    class MyRoot(RootModel[List[int]]):
        pass

    assert _annotation_is_complex(MyRoot, []) is True


# ============================================================
# Tests for _get_field_metadata
# ============================================================


def test_get_field_metadata_basic():
    field = FieldInfo(annotation=int)
    result = _get_field_metadata(field)
    assert result == []


def test_get_field_metadata_with_metadata():
    class MyModel(BaseModel):
        x: Annotated[int, Strict(strict=True)]

    field = MyModel.model_fields['x']
    result = _get_field_metadata(field)
    assert any(isinstance(m, Strict) for m in result)


def test_get_field_metadata_annotated():
    # Use a model where the annotation is Annotated with metadata
    class MyModel(BaseModel):
        x: Annotated[int, Strict(strict=True)]

    field = MyModel.model_fields['x']
    result = _get_field_metadata(field)
    assert any(isinstance(m, Strict) for m in result)


# ============================================================
# Tests for _union_is_complex
# ============================================================


def test_union_is_complex_with_complex_type():
    assert _union_is_complex(Union[int, List[str]], []) is True


def test_union_is_complex_no_complex_types():
    assert _union_is_complex(Union[int, str], []) is False


def test_union_is_complex_with_dict():
    assert _union_is_complex(Union[int, Dict[str, Any]], []) is True


def test_union_is_complex_optional_int():
    assert _union_is_complex(Optional[int], []) is False


def test_union_is_complex_optional_list():
    assert _union_is_complex(Optional[List[int]], []) is True


def test_union_is_complex_annotated_union_with_json_suppresses():
    # Annotated[Union[int, List[str]], Json()] - Json in inner_meta triggers `continue` (lines 146-148)
    # so the nested complex Union is skipped; no other complex args -> False
    json_instance = Json()
    inner = Annotated[Union[int, List[str]], json_instance]
    annotation = Union[inner, str]
    assert _union_is_complex(annotation, []) is False


def test_union_is_complex_annotated_union_non_json_complex():
    # Annotated[Union[int, List[str]], Strict()] - non-Json metadata, recurse into inner Union (lines 146-147, 149-151)
    # inner Union contains List[str] which is complex -> True
    inner = Annotated[Union[int, List[str]], Strict()]
    annotation = Union[inner, bool]
    assert _union_is_complex(annotation, []) is True


def test_union_is_complex_annotated_union_non_json_not_complex():
    # Annotated[Union[int, str], Strict()] - non-Json metadata, recurse into inner Union (lines 146-147, 149-150)
    # inner Union contains only simple types -> False
    inner = Annotated[Union[int, str], Strict()]
    annotation = Union[inner, bool]
    assert _union_is_complex(annotation, []) is False


# ============================================================
# Tests for _union_has_strict_types
# ============================================================


def test_union_has_strict_types_with_strict():
    annotation = Union[Annotated[int, Strict()], str]
    assert _union_has_strict_types(annotation) is True


def test_union_has_strict_types_no_strict():
    assert _union_has_strict_types(Union[int, str]) is False


def test_union_has_strict_types_optional_strict():
    annotation = Optional[Annotated[int, Strict()]]
    assert _union_has_strict_types(annotation) is True


# ============================================================
# Tests for _strip_annotated
# ============================================================


def test_strip_annotated_with_annotated():
    result = _strip_annotated(Annotated[int, 'meta'])
    assert result is int


def test_strip_annotated_non_annotated():
    result = _strip_annotated(int)
    assert result is int


def test_strip_annotated_list():
    result = _strip_annotated(List[int])
    assert result == List[int]


# ============================================================
# Tests for _annotation_enum_val_to_name
# ============================================================


class Color(Enum):
    RED = 'red'
    GREEN = 'green'
    BLUE = 'blue'


class Status(IntEnum):
    ACTIVE = 1
    INACTIVE = 2


def test_annotation_enum_val_to_name_direct():
    result = _annotation_enum_val_to_name(Color, Color.RED)
    assert result == 'RED'


def test_annotation_enum_val_to_name_not_found():
    result = _annotation_enum_val_to_name(Color, 'yellow')
    assert result is None


def test_annotation_enum_val_to_name_from_union():
    result = _annotation_enum_val_to_name(Union[Color, int], Color.GREEN)
    assert result == 'GREEN'


def test_annotation_enum_val_to_name_int_enum():
    result = _annotation_enum_val_to_name(Status, Status.ACTIVE)
    assert result == 'ACTIVE'


def test_annotation_enum_val_to_name_non_enum():
    result = _annotation_enum_val_to_name(int, 1)
    assert result is None


def test_annotation_enum_val_to_name_none():
    result = _annotation_enum_val_to_name(None, 'red')
    assert result is None


# ============================================================
# Tests for _annotation_enum_name_to_val
# ============================================================


def test_annotation_enum_name_to_val_direct():
    result = _annotation_enum_name_to_val(Color, 'RED')
    assert result == Color.RED


def test_annotation_enum_name_to_val_not_found():
    result = _annotation_enum_name_to_val(Color, 'YELLOW')
    assert result is None


def test_annotation_enum_name_to_val_from_union():
    result = _annotation_enum_name_to_val(Union[Color, int], 'GREEN')
    assert result == Color.GREEN


def test_annotation_enum_name_to_val_int_enum():
    result = _annotation_enum_name_to_val(Status, 'INACTIVE')
    assert result == Status.INACTIVE


def test_annotation_enum_name_to_val_non_enum():
    result = _annotation_enum_name_to_val(int, 'RED')
    assert result is None


# ============================================================
# Tests for _literal_has_numeric_enum
# ============================================================


class NumericStatus(IntEnum):
    ACTIVE = 1
    INACTIVE = 2


def test_literal_has_numeric_enum_true():
    annotation = Literal[NumericStatus.ACTIVE]
    assert _literal_has_numeric_enum(annotation) is True


def test_literal_has_numeric_enum_false_string_literal():
    annotation = Literal['a', 'b']
    assert _literal_has_numeric_enum(annotation) is False


def test_literal_has_numeric_enum_false_int_literal():
    # Plain int Literal (not Enum) should be False
    annotation = Literal[1, 2, 3]
    assert _literal_has_numeric_enum(annotation) is False


def test_literal_has_numeric_enum_non_literal():
    assert _literal_has_numeric_enum(int) is False


def test_literal_has_numeric_enum_annotated_wrapping():
    annotation = Annotated[Literal[NumericStatus.ACTIVE], 'meta']
    assert _literal_has_numeric_enum(annotation) is True


def test_literal_has_numeric_enum_optional():
    annotation = Optional[Literal[NumericStatus.ACTIVE]]
    assert _literal_has_numeric_enum(annotation) is True


def test_literal_has_numeric_enum_optional_no_numeric():
    annotation = Optional[Literal['a']]
    assert _literal_has_numeric_enum(annotation) is False


# ============================================================
# Tests for _annotation_contains_types
# ============================================================


def test_annotation_contains_types_direct_match():
    assert _annotation_contains_types(int, (int,)) is True


def test_annotation_contains_types_no_match():
    assert _annotation_contains_types(str, (int,)) is False


def test_annotation_contains_types_in_generic():
    assert _annotation_contains_types(List[int], (int,)) is True


def test_annotation_contains_types_origin_match():
    assert _annotation_contains_types(List[int], (list,)) is True


def test_annotation_contains_types_with_collect():
    collected: set[Any] = set()
    _annotation_contains_types(List[int], (list,), collect=collected)
    assert List[int] in collected


def test_annotation_contains_types_strip_annotated():
    assert _annotation_contains_types(Annotated[int, 'meta'], (int,), is_strip_annotated=True) is True


def test_annotation_contains_types_instance_check():
    # TypeVar is instance of TypeVar
    T = TypeVar('T')
    assert _annotation_contains_types(T, (TypeVar,), is_instance=True) is True


def test_annotation_contains_types_no_include_origin():
    # Without including origin, list[int] should not match (list,)
    result = _annotation_contains_types(List[int], (list,), is_include_origin=False)
    assert result is False


def test_annotation_contains_types_union():
    assert _annotation_contains_types(Union[int, str], (int,)) is True


def test_annotation_contains_types_instance_check_origin_returns_true():
    # Lines 183-184: is_instance=True, origin is instance of a type in types, collect=None
    # list is an instance of type, so List[int] with types=(type,) should return True
    result = _annotation_contains_types(List[int], (type,), is_instance=True)
    assert result is True


def test_annotation_contains_types_instance_check_origin_with_collect():
    # Line 185: is_instance=True, origin is instance of a type in types, collect not None
    collected: set[Any] = set()
    _annotation_contains_types(List[int], (type,), is_instance=True, collect=collected)
    assert List[int] in collected


def test_annotation_contains_types_instance_annotation_with_collect():
    # Line 202: is_instance=True, annotation itself is an instance of type in types, collect not None
    T = TypeVar('T')
    collected: set[Any] = set()
    _annotation_contains_types(T, (TypeVar,), is_instance=True, collect=collected)
    assert T in collected


def test_annotation_contains_types_direct_match_with_collect():
    # Line 205: annotation directly in types and collect is not None
    collected: set[Any] = set()
    result = _annotation_contains_types(int, (int,), collect=collected)
    assert result is True
    assert int in collected


# ============================================================
# Tests for _get_model_fields
# ============================================================


def test_get_model_fields_basemodel():
    class MyModel(BaseModel):
        x: int
        y: str

    fields = _get_model_fields(MyModel)
    assert 'x' in fields
    assert 'y' in fields


def test_get_model_fields_pydantic_dataclass():
    @pydantic_dataclass
    class MyDC:
        x: int
        y: str

    fields = _get_model_fields(MyDC)
    assert 'x' in fields
    assert 'y' in fields


def test_get_model_fields_non_model_raises():
    class PlainClass:
        pass

    with pytest.raises(SettingsError, match='not subclass of BaseModel'):
        _get_model_fields(PlainClass)


# ============================================================
# Tests for _get_alias_names
# ============================================================


def test_get_alias_names_no_alias():
    field = FieldInfo()
    names, is_alias_path_only = _get_alias_names('my_field', field)
    assert names == ('my_field',)
    assert is_alias_path_only is False


def test_get_alias_names_string_alias():
    field = FieldInfo(alias='my_alias')
    names, is_alias_path_only = _get_alias_names('my_field', field)
    assert 'my_alias' in names
    assert is_alias_path_only is False


def test_get_alias_names_validation_alias_str():
    field = FieldInfo(validation_alias='val_alias')
    names, is_alias_path_only = _get_alias_names('my_field', field)
    assert 'val_alias' in names
    assert is_alias_path_only is False


def test_get_alias_names_alias_choices():
    field = FieldInfo(validation_alias=AliasChoices('alias1', 'alias2'))
    names, is_alias_path_only = _get_alias_names('my_field', field)
    assert 'alias1' in names
    assert 'alias2' in names
    assert is_alias_path_only is False


def test_get_alias_names_alias_path():
    field = FieldInfo(validation_alias=AliasPath('nested', 'field'))
    names, is_alias_path_only = _get_alias_names('my_field', field)
    assert 'nested' in names
    assert is_alias_path_only is True


def test_get_alias_names_populate_by_name():
    field = FieldInfo(alias='my_alias')
    names, is_alias_path_only = _get_alias_names('my_field', field, populate_by_name=True)
    assert 'my_alias' in names
    assert 'my_field' in names
    assert is_alias_path_only is False


def test_get_alias_names_case_insensitive():
    field = FieldInfo(alias='MyAlias')
    names, _ = _get_alias_names('my_field', field, case_sensitive=False)
    assert 'myalias' in names


def test_get_alias_names_alias_path_with_int():
    field = FieldInfo(validation_alias=AliasPath('nested', 0))
    alias_path_args: dict[str, Any] = {}
    names, is_alias_path_only = _get_alias_names('my_field', field, alias_path_args=alias_path_args)
    assert 'nested' in names
    assert alias_path_args.get('nested') == 0


def test_get_alias_names_alias_choices_with_path():
    # When AliasChoices has both strings and paths, strings take priority
    alias = AliasChoices('alias1', AliasPath('nested', 'field'))
    field = FieldInfo(validation_alias=alias)
    names, is_alias_path_only = _get_alias_names('my_field', field)
    # 'alias1' is in names, is_alias_path_only is False because there's a string alias
    assert 'alias1' in names
    assert is_alias_path_only is False


def test_get_alias_names_alias_choices_only_paths():
    # When AliasChoices has only paths, the first path component is used
    alias = AliasChoices(AliasPath('nested', 'field'))
    field = FieldInfo(validation_alias=alias)
    names, is_alias_path_only = _get_alias_names('my_field', field)
    assert 'nested' in names
    assert is_alias_path_only is True


# ============================================================
# Tests for _is_function
# ============================================================


def test_is_function_regular_function():
    def my_func():
        pass

    assert _is_function(my_func) is True


def test_is_function_builtin():
    assert _is_function(len) is True


def test_is_function_lambda():
    f = lambda x: x
    assert _is_function(f) is True


def test_is_function_class():
    assert _is_function(int) is False


def test_is_function_instance():
    assert _is_function(42) is False


def test_is_function_none():
    assert _is_function(None) is False


def test_is_function_class_with_call():
    class Callable:
        def __call__(self):
            pass

    assert _is_function(Callable()) is False
