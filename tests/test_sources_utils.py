"""Tests for pydantic_settings/sources/utils.py functions."""

from collections import deque
from enum import Enum, IntEnum
from types import BuiltinFunctionType, FunctionType
from typing import Annotated, Any, Literal, Optional, TypeVar, Union

import pytest
from pydantic import AliasChoices, AliasPath, BaseModel, Field, Json, RootModel, Secret
from pydantic.dataclasses import dataclass as pydantic_dataclass
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


class TestGetEnvVarKey:
    def test_case_insensitive_default(self):
        assert _get_env_var_key("MY_VAR") == "my_var"
        assert _get_env_var_key("MyVar") == "myvar"

    def test_case_sensitive(self):
        assert _get_env_var_key("MY_VAR", case_sensitive=True) == "MY_VAR"
        assert _get_env_var_key("MyVar", case_sensitive=True) == "MyVar"


class TestParseEnvNoneStr:
    def test_value_not_matching_parse_none_str(self):
        assert _parse_env_none_str("value", "null") == "value"
        assert _parse_env_none_str("null", "none") == "null"

    def test_value_matching_parse_none_str(self):
        result = _parse_env_none_str("null", "null")
        assert isinstance(result, EnvNoneType)
        assert str(result) == "null"

    def test_none_parse_none_str(self):
        assert _parse_env_none_str("null", None) == "null"


class TestParseEnvVars:
    def test_basic_parsing(self):
        env_vars = {"VAR1": "value1", "VAR2": "value2"}
        result = parse_env_vars(env_vars)
        assert result == {"var1": "value1", "var2": "value2"}

    def test_case_sensitive(self):
        env_vars = {"VAR1": "value1", "Var2": "value2"}
        result = parse_env_vars(env_vars, case_sensitive=True)
        assert result == {"VAR1": "value1", "Var2": "value2"}

    def test_ignore_empty(self):
        env_vars = {"VAR1": "value1", "VAR2": "", "VAR3": "value3"}
        result = parse_env_vars(env_vars, ignore_empty=True)
        assert result == {"var1": "value1", "var3": "value3"}
        assert "var2" not in result

    def test_parse_none_str(self):
        env_vars = {"VAR1": "value1", "VAR2": "null"}
        result = parse_env_vars(env_vars, parse_none_str="null")
        assert result["var1"] == "value1"
        assert isinstance(result["var2"], EnvNoneType)


class TestSubstituteTypevars:
    def test_typevar_substitution(self):
        T = TypeVar("T")
        param_map = {T: int}
        assert _substitute_typevars(T, param_map) == int

    def test_no_args_type(self):
        assert _substitute_typevars(int, {}) == int
        assert _substitute_typevars(str, {}) == str

    def test_generic_with_typevar(self):
        T = TypeVar("T")
        param_map = {T: int}
        result = _substitute_typevars(list[T], param_map)
        assert result == list[int]

    def test_nested_generic(self):
        T = TypeVar("T")
        param_map = {T: str}
        result = _substitute_typevars(list[dict[T, T]], param_map)
        assert result == list[dict[str, str]]

    def test_union_type_reconstruction(self):
        T = TypeVar("T")
        param_map = {T: int}
        result = _substitute_typevars(T | str, param_map)
        assert result == int | str

    def test_no_substitution_needed(self):
        result = _substitute_typevars(list[int], {})
        assert result == list[int]


class TestResolveTypeAlias:
    def test_non_type_alias(self):
        assert _resolve_type_alias(int) == int
        assert _resolve_type_alias(str) == str
        assert _resolve_type_alias(list[int]) == list[int]


class TestAnnotationIsComplex:
    def test_json_metadata(self):
        assert _annotation_is_complex(str, [Json]) is False

    def test_secret_type(self):
        assert _annotation_is_complex(Secret[str], []) is False

    def test_annotated_json(self):
        annotation = Annotated[str, Json]
        assert _annotation_is_complex(annotation, []) is False

    def test_pydantic_model(self):
        class MyModel(BaseModel):
            field: str

        assert _annotation_is_complex(MyModel, []) is True

    def test_simple_type(self):
        assert _annotation_is_complex(int, []) is False
        assert _annotation_is_complex(str, []) is False

    def test_root_model(self):
        class MyRootModel(RootModel[list[str]]):
            pass

        assert _annotation_is_complex(MyRootModel, []) is True


class TestGetFieldMetadata:
    def test_simple_field(self):
        field = FieldInfo(annotation=int, default=0)
        metadata = _get_field_metadata(field)
        assert isinstance(metadata, list)

    def test_annotated_field(self):
        field = FieldInfo(annotation=Annotated[int, "meta"], default=0)
        metadata = _get_field_metadata(field)
        assert "meta" in metadata

    def test_annotated_field_with_multiple_metadata(self):
        field = FieldInfo(annotation=Annotated[int, "meta1", "meta2"], default=0)
        metadata = _get_field_metadata(field)
        assert "meta1" in metadata
        assert "meta2" in metadata


class TestAnnotationIsComplexInner:
    def test_string_types_not_complex(self):
        assert _annotation_is_complex_inner(str) is False
        assert _annotation_is_complex_inner(bytes) is False

    def test_complex_types(self):
        assert _annotation_is_complex_inner(list) is True
        assert _annotation_is_complex_inner(dict) is True
        assert _annotation_is_complex_inner(set) is True
        assert _annotation_is_complex_inner(frozenset) is True
        assert _annotation_is_complex_inner(tuple) is True
        assert _annotation_is_complex_inner(deque) is True

    def test_basemodel(self):
        class MyModel(BaseModel):
            field: str

        assert _annotation_is_complex_inner(MyModel) is True

    def test_dataclass(self):
        @pydantic_dataclass
        class MyDataclass:
            field: str

        assert _annotation_is_complex_inner(MyDataclass) is True


class TestUnionIsComplex:
    def test_simple_union(self):
        assert _union_is_complex(Union[int, str], []) is False

    def test_union_with_complex_type(self):
        class MyModel(BaseModel):
            field: str

        assert _union_is_complex(Union[int, MyModel], []) is True

    def test_nested_union(self):
        class MyModel(BaseModel):
            field: str

        assert _union_is_complex(Union[int, Union[str, MyModel]], []) is True

    def test_annotated_union_with_json(self):
        class MyModel(BaseModel):
            field: str

        annotation = Union[int, Annotated[MyModel, Json]]
        assert _union_is_complex(annotation, []) is True


class TestUnionHasStrictTypes:
    def test_no_strict_types(self):
        assert _union_has_strict_types(Union[int, str]) is False

    def test_with_strict_types(self):
        annotation = Union[Annotated[int, Strict()], str]
        assert _union_has_strict_types(annotation) is True

    def test_multiple_strict_types(self):
        annotation = Union[Annotated[int, Strict()], Annotated[str, Strict()]]
        assert _union_has_strict_types(annotation) is True


class TestAnnotationContainsTypes:
    def test_origin_match(self):
        assert _annotation_contains_types(list[int], (list,)) is True

    def test_origin_no_match(self):
        assert _annotation_contains_types(list[int], (dict,)) is False

    def test_nested_types(self):
        assert _annotation_contains_types(list[dict[str, int]], (dict,)) is True

    def test_with_collect(self):
        collected = set()
        _annotation_contains_types(list[int], (list,), collect=collected)
        assert len(collected) > 0

    def test_strip_annotated(self):
        annotation = Annotated[list[int], "meta"]
        assert _annotation_contains_types(annotation, (list,), is_strip_annotated=True) is True

    def test_direct_type_match(self):
        assert _annotation_contains_types(int, (int,), is_include_origin=False) is True

    def test_is_instance_check(self):
        class MyType:
            pass

        assert _annotation_contains_types(MyType(), (MyType,), is_instance=True) is True


class TestStripAnnotated:
    def test_annotated_type(self):
        annotation = Annotated[int, "metadata"]
        assert _strip_annotated(annotation) == int

    def test_non_annotated_type(self):
        assert _strip_annotated(int) == int
        assert _strip_annotated(str) == str
        assert _strip_annotated(list[int]) == list[int]

    def test_nested_annotated(self):
        annotation = Annotated[list[int], "meta"]
        assert _strip_annotated(annotation) == list[int]


class TestAnnotationEnumValToName:
    class Color(Enum):
        RED = 1
        GREEN = 2
        BLUE = 3

    def test_enum_value_to_name(self):
        assert _annotation_enum_val_to_name(self.Color, self.Color.RED) == "RED"
        assert _annotation_enum_val_to_name(self.Color, self.Color.GREEN) == "GREEN"

    def test_non_enum_value(self):
        assert _annotation_enum_val_to_name(self.Color, 99) is None

    def test_non_enum_type(self):
        assert _annotation_enum_val_to_name(int, 1) is None

    def test_union_with_enum(self):
        annotation = Union[self.Color, str]
        assert _annotation_enum_val_to_name(annotation, self.Color.RED) == "RED"


class TestAnnotationEnumNameToVal:
    class Color(Enum):
        RED = 1
        GREEN = 2
        BLUE = 3

    def test_enum_name_to_value(self):
        result = _annotation_enum_name_to_val(self.Color, "RED")
        assert result == self.Color.RED

    def test_invalid_name(self):
        assert _annotation_enum_name_to_val(self.Color, "YELLOW") is None

    def test_non_enum_type(self):
        assert _annotation_enum_name_to_val(int, "RED") is None

    def test_union_with_enum(self):
        annotation = Union[self.Color, str]
        result = _annotation_enum_name_to_val(annotation, "GREEN")
        assert result == self.Color.GREEN


class TestLiteralHasNumericEnum:
    def test_literal_with_numeric_enum(self):
        class Priority(IntEnum):
            LOW = 1
            MEDIUM = 2
            HIGH = 3

        annotation = Literal[Priority.LOW, Priority.HIGH]
        assert _literal_has_numeric_enum(annotation) is True

    def test_literal_without_enum(self):
        annotation = Literal[1, 2, 3]
        assert _literal_has_numeric_enum(annotation) is False

    def test_non_literal_type(self):
        assert _literal_has_numeric_enum(int) is False

    def test_annotated_literal_with_numeric_enum(self):
        class Priority(IntEnum):
            LOW = 1

        annotation = Annotated[Literal[Priority.LOW], Field()]
        assert _literal_has_numeric_enum(annotation) is True

    def test_optional_literal_with_numeric_enum(self):
        class Priority(IntEnum):
            MEDIUM = 2

        annotation = Optional[Literal[Priority.MEDIUM]]
        assert _literal_has_numeric_enum(annotation) is True

    def test_union_literal_with_numeric_enum(self):
        class Priority(IntEnum):
            HIGH = 3

        annotation = Union[Literal[Priority.HIGH], str]
        assert _literal_has_numeric_enum(annotation) is True


class TestGetModelFields:
    def test_basemodel(self):
        class MyModel(BaseModel):
            field1: int
            field2: str

        fields = _get_model_fields(MyModel)
        assert "field1" in fields
        assert "field2" in fields

    def test_pydantic_dataclass(self):
        @pydantic_dataclass
        class MyDataclass:
            field1: int
            field2: str

        fields = _get_model_fields(MyDataclass)
        assert "field1" in fields
        assert "field2" in fields

    def test_non_model_raises_error(self):
        class RegularClass:
            pass

        with pytest.raises(SettingsError):
            _get_model_fields(RegularClass)


class TestGetAliasNames:
    def test_no_alias(self):
        field_info = FieldInfo(annotation=int, default=0)
        names, is_alias_path_only = _get_alias_names("field_name", field_info)
        assert "field_name" in names
        assert is_alias_path_only is False

    def test_string_alias(self):
        field_info = FieldInfo(annotation=int, default=0, alias="my_alias")
        names, is_alias_path_only = _get_alias_names("field_name", field_info)
        assert "my_alias" in names
        assert is_alias_path_only is False

    def test_alias_choices(self):
        field_info = FieldInfo(
            annotation=int, default=0, validation_alias=AliasChoices("alias1", "alias2")
        )
        names, is_alias_path_only = _get_alias_names("field_name", field_info)
        assert "alias1" in names
        assert "alias2" in names

    def test_alias_path(self):
        field_info = FieldInfo(annotation=int, default=0, validation_alias=AliasPath("path_name"))
        alias_path_args = {}
        names, is_alias_path_only = _get_alias_names(
            "field_name", field_info, alias_path_args=alias_path_args
        )
        assert "path_name" in names
        assert is_alias_path_only is True
        assert "path_name" in alias_path_args

    def test_alias_path_with_index(self):
        field_info = FieldInfo(annotation=int, default=0, validation_alias=AliasPath("path_name", 0))
        alias_path_args = {}
        names, is_alias_path_only = _get_alias_names(
            "field_name", field_info, alias_path_args=alias_path_args
        )
        assert "path_name" in alias_path_args
        assert alias_path_args["path_name"] == 0

    def test_case_insensitive(self):
        field_info = FieldInfo(annotation=int, default=0, alias="MyAlias")
        names, is_alias_path_only = _get_alias_names(
            "field_name", field_info, case_sensitive=False
        )
        assert "myalias" in names

    def test_populate_by_name(self):
        field_info = FieldInfo(annotation=int, default=0, alias="my_alias")
        names, is_alias_path_only = _get_alias_names(
            "field_name", field_info, populate_by_name=True
        )
        assert "field_name" in names
        assert "my_alias" in names

    def test_alias_choices_with_path(self):
        field_info = FieldInfo(
            annotation=int,
            default=0,
            validation_alias=AliasChoices("alias1", AliasPath("path_name")),
        )
        alias_path_args = {}
        names, is_alias_path_only = _get_alias_names("field_name", field_info, alias_path_args=alias_path_args)
        assert "alias1" in names
        assert is_alias_path_only is False
        assert "path_name" in alias_path_args


class TestIsFunction:
    def test_function(self):
        def my_func():
            pass

        assert _is_function(my_func) is True

    def test_builtin_function(self):
        assert _is_function(len) is True
        assert _is_function(print) is True

    def test_lambda(self):
        my_lambda = lambda x: x + 1
        assert _is_function(my_lambda) is True

    def test_non_function(self):
        assert _is_function(42) is False
        assert _is_function("string") is False
        assert _is_function([1, 2, 3]) is False

    def test_class(self):
        class MyClass:
            pass

        assert _is_function(MyClass) is False
