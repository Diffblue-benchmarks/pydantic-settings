"""Unit tests for pydantic_settings.sources.utils module."""

from __future__ import annotations

from collections import deque
from enum import Enum, IntEnum
from typing import Any, Annotated, Dict, FrozenSet, List, Literal, Optional, Set, Tuple, TypeVar, Union

import pytest
from pydantic import AliasChoices, AliasPath, BaseModel, Json, RootModel
from pydantic.dataclasses import dataclass as pydantic_dataclass
from pydantic.fields import FieldInfo
from pydantic.types import Strict

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


# ---------------------------------------------------------------------------
# _get_env_var_key
# ---------------------------------------------------------------------------

def test_get_env_var_key_case_insensitive():
    assert _get_env_var_key("MY_VAR") == "my_var"


def test_get_env_var_key_case_sensitive():
    assert _get_env_var_key("MY_VAR", case_sensitive=True) == "MY_VAR"


def test_get_env_var_key_already_lower():
    assert _get_env_var_key("my_var") == "my_var"


# ---------------------------------------------------------------------------
# _parse_env_none_str
# ---------------------------------------------------------------------------

def test_parse_env_none_str_returns_value_when_no_match():
    assert _parse_env_none_str("hello", "none") == "hello"


def test_parse_env_none_str_returns_env_none_type_when_match():
    result = _parse_env_none_str("none", "none")
    assert isinstance(result, EnvNoneType)
    assert result == "none"


def test_parse_env_none_str_none_value():
    assert _parse_env_none_str(None, "none") is None


def test_parse_env_none_str_parse_none_str_is_none():
    # When parse_none_str is None, should return value as-is
    assert _parse_env_none_str("none", None) == "none"


# ---------------------------------------------------------------------------
# parse_env_vars
# ---------------------------------------------------------------------------

def test_parse_env_vars_basic():
    result = parse_env_vars({"KEY": "value"})
    assert result == {"key": "value"}


def test_parse_env_vars_case_sensitive():
    result = parse_env_vars({"KEY": "value"}, case_sensitive=True)
    assert result == {"KEY": "value"}


def test_parse_env_vars_ignore_empty():
    result = parse_env_vars({"KEY": "", "OTHER": "val"}, ignore_empty=True)
    assert "key" not in result
    assert result == {"other": "val"}


def test_parse_env_vars_keep_empty_when_not_ignoring():
    result = parse_env_vars({"KEY": ""})
    assert result == {"key": ""}


def test_parse_env_vars_parse_none_str():
    result = parse_env_vars({"A": "null", "B": "val"}, parse_none_str="null")
    assert isinstance(result["a"], EnvNoneType)
    assert result["b"] == "val"


def test_parse_env_vars_none_value_preserved():
    result = parse_env_vars({"A": None})
    assert result == {"a": None}


# ---------------------------------------------------------------------------
# _substitute_typevars
# ---------------------------------------------------------------------------

def test_substitute_typevars_replaces_typevar():
    T = TypeVar("T")
    result = _substitute_typevars(T, {T: int})
    assert result is int


def test_substitute_typevars_no_match_returns_tp():
    T = TypeVar("T")
    result = _substitute_typevars(T, {})
    assert result is T


def test_substitute_typevars_no_args_returns_tp():
    result = _substitute_typevars(int, {})
    assert result is int


def test_substitute_typevars_list_with_typevar():
    T = TypeVar("T")
    result = _substitute_typevars(List[T], {T: int})
    from typing import get_args, get_origin
    assert get_origin(result) is list
    assert get_args(result) == (int,)


def test_substitute_typevars_same_args_returns_tp():
    T = TypeVar("T")
    result = _substitute_typevars(List[int], {T: str})
    assert result == List[int]


def test_substitute_typevars_union_type():
    T = TypeVar("T")
    result = _substitute_typevars(Optional[T], {T: int})
    # Should be Optional[int] (Union[int, None])
    assert int in result.__args__


def test_substitute_typevars_types_union_type_uses_or_operator():
    """Test lines 59-65: TypeError path when types.UnionType cannot be subscripted."""
    import sys
    import types
    from typing import get_args as typing_get_args
    if sys.version_info < (3, 10):
        pytest.skip("requires Python 3.10+ types.UnionType")
    T = TypeVar("T")
    # list[T] | None creates types.UnionType in Python 3.10+
    tp = list[T] | None
    result = _substitute_typevars(tp, {T: int})
    assert isinstance(result, types.UnionType)
    result_args = typing_get_args(result)
    assert list[int] in result_args
    assert type(None) in result_args


def test_substitute_typevars_origin_none_returns_tp(mocker):
    """Test line 66: return tp when origin is None but new_args differ from args."""
    T = TypeVar("T")
    mocker.patch("pydantic_settings.sources.utils.get_origin", return_value=None)
    result = _substitute_typevars(List[T], {T: int})
    assert result is List[T]


# ---------------------------------------------------------------------------
# _resolve_type_alias
# ---------------------------------------------------------------------------

def test_resolve_type_alias_non_alias_returns_self():
    assert _resolve_type_alias(int) is int


def test_resolve_type_alias_with_typealiastype():
    from typing import TypeAliasType
    MyAlias = TypeAliasType("MyAlias", int)
    result = _resolve_type_alias(MyAlias)
    assert result is int


def test_resolve_type_alias_parameterized_typealiastype():
    from typing import TypeAliasType, get_args, get_origin
    T = TypeVar("T")
    MyList = TypeAliasType("MyList", List[T], type_params=(T,))
    result = _resolve_type_alias(MyList[int])
    assert get_origin(result) is list
    assert get_args(result) == (int,)


# ---------------------------------------------------------------------------
# _annotation_is_complex
# ---------------------------------------------------------------------------

def test_annotation_is_complex_str_not_complex():
    assert not _annotation_is_complex(str, [])


def test_annotation_is_complex_bytes_not_complex():
    assert not _annotation_is_complex(bytes, [])


def test_annotation_is_complex_int_not_complex():
    assert not _annotation_is_complex(int, [])


def test_annotation_is_complex_list_is_complex():
    assert _annotation_is_complex(List[str], [])


def test_annotation_is_complex_dict_is_complex():
    assert _annotation_is_complex(Dict[str, str], [])


def test_annotation_is_complex_basemodel_is_complex():
    class MyModel(BaseModel):
        x: int

    assert _annotation_is_complex(MyModel, [])


def test_annotation_is_complex_json_not_complex():
    assert not _annotation_is_complex(str, [Json()])


def test_annotation_is_complex_root_model():
    class MyRoot(RootModel[List[int]]):
        pass

    assert _annotation_is_complex(MyRoot, [])


def test_annotation_is_complex_annotated():
    assert _annotation_is_complex(Annotated[List[str], "meta"], [])


def test_annotation_is_complex_tuple():
    assert _annotation_is_complex(Tuple[int, str], [])


def test_annotation_is_complex_frozenset():
    assert _annotation_is_complex(FrozenSet[int], [])


def test_annotation_is_complex_set():
    assert _annotation_is_complex(Set[int], [])


# ---------------------------------------------------------------------------
# _get_field_metadata
# ---------------------------------------------------------------------------

def test_get_field_metadata_basic_field():
    class M(BaseModel):
        x: int

    field = M.model_fields["x"]
    meta = _get_field_metadata(field)
    assert isinstance(meta, list)


def test_get_field_metadata_annotated_field():
    class M(BaseModel):
        x: Annotated[int, Strict(True)]

    field = M.model_fields["x"]
    meta = _get_field_metadata(field)
    assert any(isinstance(m, Strict) for m in meta)


# ---------------------------------------------------------------------------
# _annotation_is_complex_inner
# ---------------------------------------------------------------------------

def test_annotation_is_complex_inner_str_false():
    assert not _annotation_is_complex_inner(str)


def test_annotation_is_complex_inner_bytes_false():
    assert not _annotation_is_complex_inner(bytes)


def test_annotation_is_complex_inner_none_false():
    assert not _annotation_is_complex_inner(None)


def test_annotation_is_complex_inner_list_true():
    assert _annotation_is_complex_inner(list)


def test_annotation_is_complex_inner_dict_true():
    assert _annotation_is_complex_inner(dict)


def test_annotation_is_complex_inner_basemodel_true():
    class M(BaseModel):
        pass

    assert _annotation_is_complex_inner(M)


def test_annotation_is_complex_inner_tuple_true():
    assert _annotation_is_complex_inner(tuple)


def test_annotation_is_complex_inner_set_true():
    assert _annotation_is_complex_inner(set)


def test_annotation_is_complex_inner_frozenset_true():
    assert _annotation_is_complex_inner(frozenset)


def test_annotation_is_complex_inner_deque_true():
    assert _annotation_is_complex_inner(deque)


# ---------------------------------------------------------------------------
# _union_is_complex
# ---------------------------------------------------------------------------

def test_union_is_complex_with_list():
    assert _union_is_complex(Union[List[int], None], [])


def test_union_is_complex_simple_types():
    assert not _union_is_complex(Union[int, str], [])


def test_union_is_complex_none():
    assert not _union_is_complex(None, [])


def test_union_is_complex_with_basemodel():
    class M(BaseModel):
        x: int

    assert _union_is_complex(Optional[M], [])


def test_union_is_complex_annotated_arg_with_json_suppresses_complexity():
    # Covers lines 146-148: Annotated arg whose metadata contains Json → continue
    annotation = Union[Annotated[Union[List[int], str], Json()], None]
    assert not _union_is_complex(annotation, [])


def test_union_is_complex_annotated_arg_without_json_recurses_into_inner_union():
    # Covers lines 146-147 (no Json), 150-151: Annotated wrapping a complex union → recurse
    annotation = Union[Annotated[Union[List[int], str], "meta"], None]
    assert _union_is_complex(annotation, [])


# ---------------------------------------------------------------------------
# _union_has_strict_types
# ---------------------------------------------------------------------------

def test_union_has_strict_types_true():
    annotation = Union[Annotated[int, Strict(True)], str]
    assert _union_has_strict_types(annotation)


def test_union_has_strict_types_false():
    annotation = Union[int, str]
    assert not _union_has_strict_types(annotation)


def test_union_has_strict_types_none():
    assert not _union_has_strict_types(None)


# ---------------------------------------------------------------------------
# _annotation_contains_types
# ---------------------------------------------------------------------------

def test_annotation_contains_types_direct_match():
    assert _annotation_contains_types(int, (int,))


def test_annotation_contains_types_no_match():
    assert not _annotation_contains_types(str, (int,))


def test_annotation_contains_types_in_args():
    assert _annotation_contains_types(List[int], (int,))


def test_annotation_contains_types_origin_match():
    assert _annotation_contains_types(List[str], (list,))


def test_annotation_contains_types_no_origin_check():
    assert not _annotation_contains_types(List[str], (list,), is_include_origin=False)


def test_annotation_contains_types_strip_annotated():
    result = _annotation_contains_types(Annotated[int, "meta"], (int,), is_strip_annotated=True)
    assert result


def test_annotation_contains_types_collect():
    found: set[Any] = set()
    _annotation_contains_types(Union[int, str], (int,), collect=found)
    assert int in found


def test_annotation_contains_types_is_instance():
    T = TypeVar("T")
    assert _annotation_contains_types(T, (TypeVar,), is_instance=True)


def test_annotation_contains_types_collect_origin_match():
    # Line 181: origin in types and collect is not None -> collect.add(annotation)
    found: set[Any] = set()
    _annotation_contains_types(List[int], (list,), collect=found)
    assert List[int] in found


def test_annotation_contains_types_is_instance_origin_returns_true():
    # Lines 183-184: is_instance=True, isinstance(origin, type_) is True, collect is None -> return True
    assert _annotation_contains_types(List[int], (type,), is_instance=True)


def test_annotation_contains_types_is_instance_origin_collect():
    # Line 185: is_instance=True, isinstance(origin, type_) is True, collect is not None -> collect.add
    found: set[Any] = set()
    _annotation_contains_types(List[int], (type,), is_instance=True, collect=found)
    assert List[int] in found


def test_annotation_contains_types_is_instance_annotation_collect():
    # Line 202: is_instance=True, isinstance(annotation, type_) is True, collect is not None -> collect.add
    T = TypeVar("T")
    found: set[Any] = set()
    _annotation_contains_types(T, (TypeVar,), is_instance=True, collect=found)
    assert T in found


# ---------------------------------------------------------------------------
# _strip_annotated
# ---------------------------------------------------------------------------

def test_strip_annotated_removes_annotated():
    result = _strip_annotated(Annotated[int, "meta"])
    assert result is int


def test_strip_annotated_non_annotated_unchanged():
    result = _strip_annotated(int)
    assert result is int


def test_strip_annotated_list_unchanged():
    result = _strip_annotated(List[int])
    assert result == List[int]


# ---------------------------------------------------------------------------
# _annotation_enum_val_to_name
# ---------------------------------------------------------------------------

class Color(Enum):
    RED = "red"
    GREEN = "green"


def test_annotation_enum_val_to_name_direct_match():
    result = _annotation_enum_val_to_name(Color, Color.RED)
    assert result == "RED"


def test_annotation_enum_val_to_name_no_match():
    result = _annotation_enum_val_to_name(Color, "blue")
    assert result is None


def test_annotation_enum_val_to_name_none_annotation():
    result = _annotation_enum_val_to_name(None, "red")
    assert result is None


def test_annotation_enum_val_to_name_in_union():
    result = _annotation_enum_val_to_name(Optional[Color], Color.GREEN)
    assert result == "GREEN"


# ---------------------------------------------------------------------------
# _annotation_enum_name_to_val
# ---------------------------------------------------------------------------

def test_annotation_enum_name_to_val_direct_match():
    result = _annotation_enum_name_to_val(Color, "RED")
    assert result == Color.RED


def test_annotation_enum_name_to_val_no_match():
    result = _annotation_enum_name_to_val(Color, "BLUE")
    assert result is None


def test_annotation_enum_name_to_val_none_annotation():
    result = _annotation_enum_name_to_val(None, "RED")
    assert result is None


def test_annotation_enum_name_to_val_in_union():
    result = _annotation_enum_name_to_val(Optional[Color], "GREEN")
    assert result == Color.GREEN


# ---------------------------------------------------------------------------
# _literal_has_numeric_enum
# ---------------------------------------------------------------------------

class Status(IntEnum):
    ACTIVE = 1
    INACTIVE = 2


def test_literal_has_numeric_enum_with_int_enum():
    assert _literal_has_numeric_enum(Literal[Status.ACTIVE])


def test_literal_has_numeric_enum_without_enum():
    assert not _literal_has_numeric_enum(Literal[1, 2, 3])


def test_literal_has_numeric_enum_string_literal():
    assert not _literal_has_numeric_enum(Literal["a", "b"])


def test_literal_has_numeric_enum_none_annotation():
    assert not _literal_has_numeric_enum(None)


def test_literal_has_numeric_enum_annotated_wrapping():
    from pydantic import Field
    assert _literal_has_numeric_enum(Annotated[Literal[Status.ACTIVE], Field()])


def test_literal_has_numeric_enum_optional_wrapping():
    assert _literal_has_numeric_enum(Optional[Literal[Status.ACTIVE]])


def test_literal_has_numeric_enum_non_literal():
    assert not _literal_has_numeric_enum(int)


# ---------------------------------------------------------------------------
# _get_model_fields
# ---------------------------------------------------------------------------

def test_get_model_fields_basemodel():
    class M(BaseModel):
        x: int
        y: str

    fields = _get_model_fields(M)
    assert "x" in fields
    assert "y" in fields


def test_get_model_fields_pydantic_dataclass():
    @pydantic_dataclass
    class DC:
        x: int
        y: str

    fields = _get_model_fields(DC)
    assert "x" in fields
    assert "y" in fields


def test_get_model_fields_invalid_raises():
    from pydantic_settings.exceptions import SettingsError

    class NotAModel:
        pass

    with pytest.raises(SettingsError):
        _get_model_fields(NotAModel)


# ---------------------------------------------------------------------------
# _get_alias_names
# ---------------------------------------------------------------------------

def test_get_alias_names_no_alias():
    class M(BaseModel):
        field_x: int

    field_info = M.model_fields["field_x"]
    names, is_path_only = _get_alias_names("field_x", field_info)
    assert names == ("field_x",)
    assert not is_path_only


def test_get_alias_names_string_alias():
    class M(BaseModel):
        field_x: int = FieldInfo(alias="x")

    field_info = M.model_fields["field_x"]
    names, is_path_only = _get_alias_names("field_x", field_info)
    assert "x" in names
    assert not is_path_only


def test_get_alias_names_alias_path():
    field_info = FieldInfo(validation_alias=AliasPath("nested", "x"))
    alias_path_args: dict = {}
    names, is_path_only = _get_alias_names("field_x", field_info, alias_path_args=alias_path_args)
    assert "nested" in names
    assert is_path_only


def test_get_alias_names_alias_choices():
    field_info = FieldInfo(validation_alias=AliasChoices("alias_a", "alias_b"))
    names, is_path_only = _get_alias_names("field_x", field_info)
    assert "alias_a" in names
    assert "alias_b" in names
    assert not is_path_only


def test_get_alias_names_case_insensitive():
    class M(BaseModel):
        field_x: int = FieldInfo(alias="MyAlias")

    field_info = M.model_fields["field_x"]
    names, _ = _get_alias_names("field_x", field_info, case_sensitive=False)
    assert "myalias" in names


def test_get_alias_names_populate_by_name():
    class M(BaseModel):
        field_x: int = FieldInfo(alias="x")

    field_info = M.model_fields["field_x"]
    names, _ = _get_alias_names("field_x", field_info, populate_by_name=True)
    assert "field_x" in names
    assert "x" in names


# ---------------------------------------------------------------------------
# _is_function
# ---------------------------------------------------------------------------

def test_is_function_with_function():
    def my_func():
        pass

    assert _is_function(my_func)


def test_is_function_with_builtin():
    assert _is_function(len)


def test_is_function_with_non_function():
    assert not _is_function(42)
    assert not _is_function("string")
    assert not _is_function(None)


def test_is_function_with_lambda():
    assert _is_function(lambda: None)


def test_is_function_with_class():
    class MyClass:
        pass

    assert not _is_function(MyClass)
