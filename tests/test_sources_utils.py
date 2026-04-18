"""Tests for pydantic_settings.sources.utils module."""

from __future__ import annotations

from collections import deque
from enum import Enum, IntEnum
from typing import Annotated, Any, Dict, List, Optional, TypeVar, Union

import pytest
from pydantic import BaseModel, Field, Json, RootModel, Secret
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


class TestGetEnvVarKey:
    """Tests for _get_env_var_key function."""

    def test_case_sensitive_true(self):
        assert _get_env_var_key("MY_VAR", case_sensitive=True) == "MY_VAR"

    def test_case_sensitive_false(self):
        assert _get_env_var_key("MY_VAR", case_sensitive=False) == "my_var"

    def test_default_case_sensitive(self):
        # Default is False
        assert _get_env_var_key("MY_VAR") == "my_var"


class TestParseEnvNoneStr:
    """Tests for _parse_env_none_str function."""

    def test_value_not_matching_parse_none_str(self):
        assert _parse_env_none_str("hello", "null") == "hello"

    def test_value_matching_parse_none_str(self):
        result = _parse_env_none_str("null", "null")
        assert isinstance(result, EnvNoneType)
        assert result == "null"

    def test_parse_none_str_is_none(self):
        assert _parse_env_none_str("null", None) == "null"

    def test_value_is_none(self):
        assert _parse_env_none_str(None, "null") is None


class TestParseEnvVars:
    """Tests for parse_env_vars function."""

    def test_basic_parsing(self):
        env_vars = {"MY_VAR": "value", "OTHER_VAR": "other"}
        result = parse_env_vars(env_vars)
        assert result == {"my_var": "value", "other_var": "other"}

    def test_case_sensitive(self):
        env_vars = {"MY_VAR": "value"}
        result = parse_env_vars(env_vars, case_sensitive=True)
        assert result == {"MY_VAR": "value"}

    def test_ignore_empty_true(self):
        env_vars = {"MY_VAR": "value", "EMPTY_VAR": ""}
        result = parse_env_vars(env_vars, ignore_empty=True)
        assert "empty_var" not in result
        assert result == {"my_var": "value"}

    def test_ignore_empty_false(self):
        env_vars = {"MY_VAR": "value", "EMPTY_VAR": ""}
        result = parse_env_vars(env_vars, ignore_empty=False)
        assert result == {"my_var": "value", "empty_var": ""}

    def test_parse_none_str(self):
        env_vars = {"MY_VAR": "null"}
        result = parse_env_vars(env_vars, parse_none_str="null")
        assert isinstance(result["my_var"], EnvNoneType)


class TestSubstituteTypevars:
    """Tests for _substitute_typevars function."""

    def test_substitute_typevar(self):
        T = TypeVar("T")
        param_map = {T: int}
        result = _substitute_typevars(T, param_map)
        assert result is int

    def test_no_args(self):
        result = _substitute_typevars(int, {})
        assert result is int

    def test_substitute_generic(self):
        T = TypeVar("T")
        param_map = {T: int}
        annotation = List[T]
        result = _substitute_typevars(annotation, param_map)
        # Result can be list[int] or List[int] depending on Python version
        from typing import get_args, get_origin

        assert get_origin(result) is list
        assert get_args(result) == (int,)

    def test_unchanged_args(self):
        annotation = List[int]
        result = _substitute_typevars(annotation, {})
        assert result == List[int]

    def test_union_type_substitution(self):
        T = TypeVar("T")
        param_map = {T: int}
        annotation = Union[T, str]
        result = _substitute_typevars(annotation, param_map)
        # Should handle Union properly
        assert int in result.__args__
        assert str in result.__args__


class TestResolveTypeAlias:
    """Tests for _resolve_type_alias function."""

    def test_non_type_alias(self):
        result = _resolve_type_alias(int)
        assert result is int

    def test_none_annotation(self):
        result = _resolve_type_alias(None)
        assert result is None


class TestAnnotationIsComplex:
    """Tests for _annotation_is_complex function."""

    def test_simple_types_not_complex(self):
        assert _annotation_is_complex(str, []) is False
        assert _annotation_is_complex(int, []) is False
        assert _annotation_is_complex(bytes, []) is False

    def test_list_is_complex(self):
        assert _annotation_is_complex(List[int], []) is True

    def test_dict_is_complex(self):
        assert _annotation_is_complex(Dict[str, int], []) is True

    def test_json_annotation_not_complex(self):
        assert _annotation_is_complex(str, [Json()]) is False

    def test_basemodel_is_complex(self):
        class MyModel(BaseModel):
            name: str

        assert _annotation_is_complex(MyModel, []) is True

    def test_annotated_type(self):
        annotation = Annotated[List[int], Field()]
        assert _annotation_is_complex(annotation, []) is True

    def test_secret_not_complex(self):
        assert _annotation_is_complex(Secret[str], []) is False

    def test_root_model(self):
        class MyRootModel(RootModel[List[int]]):
            pass

        assert _annotation_is_complex(MyRootModel, []) is True


class TestGetFieldMetadata:
    """Tests for _get_field_metadata function."""

    def test_simple_field(self):
        field = FieldInfo(annotation=str)
        result = _get_field_metadata(field)
        assert isinstance(result, list)

    def test_annotated_field(self):
        marker = object()
        field = FieldInfo(annotation=Annotated[str, marker])
        result = _get_field_metadata(field)
        assert marker in result


class TestAnnotationIsComplexInner:
    """Tests for _annotation_is_complex_inner function."""

    def test_str_not_complex(self):
        assert _annotation_is_complex_inner(str) is False

    def test_bytes_not_complex(self):
        assert _annotation_is_complex_inner(bytes) is False

    def test_basemodel_complex(self):
        class MyModel(BaseModel):
            name: str

        assert _annotation_is_complex_inner(MyModel) is True

    def test_dict_complex(self):
        assert _annotation_is_complex_inner(dict) is True

    def test_list_complex(self):
        assert _annotation_is_complex_inner(list) is True

    def test_tuple_complex(self):
        assert _annotation_is_complex_inner(tuple) is True

    def test_set_complex(self):
        assert _annotation_is_complex_inner(set) is True

    def test_frozenset_complex(self):
        assert _annotation_is_complex_inner(frozenset) is True

    def test_deque_complex(self):
        assert _annotation_is_complex_inner(deque) is True


class TestUnionIsComplex:
    """Tests for _union_is_complex function."""

    def test_union_with_simple_types(self):
        annotation = Union[str, int]
        assert _union_is_complex(annotation, []) is False

    def test_union_with_complex_type(self):
        annotation = Union[str, List[int]]
        assert _union_is_complex(annotation, []) is True

    def test_union_with_none(self):
        annotation = Optional[str]
        assert _union_is_complex(annotation, []) is False

    def test_nested_union_with_complex(self):
        annotation = Union[str, Union[int, List[str]]]
        assert _union_is_complex(annotation, []) is True

    def test_annotated_union_with_json(self):
        annotation = Union[str, Annotated[List[int], Json()]]
        # Json suppresses complexity
        assert _union_is_complex(annotation, []) is False


class TestUnionHasStrictTypes:
    """Tests for _union_has_strict_types function."""

    def test_union_without_strict(self):
        annotation = Union[str, int]
        assert _union_has_strict_types(annotation) is False

    def test_union_with_strict(self):
        annotation = Union[str, Annotated[int, Strict()]]
        assert _union_has_strict_types(annotation) is True

    def test_optional_without_strict(self):
        annotation = Optional[str]
        assert _union_has_strict_types(annotation) is False


class TestAnnotationContainsTypes:
    """Tests for _annotation_contains_types function."""

    def test_contains_direct_type(self):
        assert _annotation_contains_types(int, (int,)) is True

    def test_not_contains_type(self):
        assert _annotation_contains_types(str, (int,)) is False

    def test_contains_origin_type(self):
        assert _annotation_contains_types(List[int], (list,)) is True

    def test_contains_nested_type(self):
        assert _annotation_contains_types(List[Dict[str, int]], (dict,)) is True

    def test_strip_annotated(self):
        annotation = Annotated[List[int], Field()]
        assert _annotation_contains_types(annotation, (list,), is_strip_annotated=True) is True

    def test_with_collect(self):
        collected: set[Any] = set()
        _annotation_contains_types(List[int], (list,), collect=collected)
        assert List[int] in collected

    def test_is_instance_check(self):
        # Test with is_instance=True
        assert _annotation_contains_types(List[int], (type,), is_instance=True) is True


class TestStripAnnotated:
    """Tests for _strip_annotated function."""

    def test_annotated_stripped(self):
        annotation = Annotated[str, Field()]
        result = _strip_annotated(annotation)
        assert result is str

    def test_non_annotated_unchanged(self):
        result = _strip_annotated(int)
        assert result is int


class Color(Enum):
    RED = 1
    GREEN = 2
    BLUE = 3


class TestAnnotationEnumValToName:
    """Tests for _annotation_enum_val_to_name function."""

    def test_valid_enum_value(self):
        # The function checks if `value in type_.__members__.values()` which checks
        # for the enum member object, not the raw value.
        assert _annotation_enum_val_to_name(Color, Color.RED) == "RED"
        assert _annotation_enum_val_to_name(Color, Color.GREEN) == "GREEN"

    def test_invalid_value(self):
        assert _annotation_enum_val_to_name(Color, 999) is None

    def test_non_enum_type(self):
        assert _annotation_enum_val_to_name(str, "test") is None


class TestAnnotationEnumNameToVal:
    """Tests for _annotation_enum_name_to_val function."""

    def test_valid_enum_name(self):
        result = _annotation_enum_name_to_val(Color, "RED")
        assert result == Color.RED

    def test_invalid_name(self):
        assert _annotation_enum_name_to_val(Color, "INVALID") is None

    def test_non_enum_type(self):
        assert _annotation_enum_name_to_val(str, "test") is None


class Priority(IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3


class TestLiteralHasNumericEnum:
    """Tests for _literal_has_numeric_enum function."""

    def test_literal_with_int_enum(self):
        from typing import Literal

        annotation = Literal[Priority.LOW, Priority.MEDIUM]
        assert _literal_has_numeric_enum(annotation) is True

    def test_literal_without_enum(self):
        from typing import Literal

        annotation = Literal["a", "b"]
        assert _literal_has_numeric_enum(annotation) is False

    def test_non_literal(self):
        assert _literal_has_numeric_enum(str) is False

    def test_annotated_literal_with_int_enum(self):
        from typing import Literal

        annotation = Annotated[Literal[Priority.LOW], Field()]
        assert _literal_has_numeric_enum(annotation) is True

    def test_optional_literal_with_int_enum(self):
        from typing import Literal

        annotation = Optional[Literal[Priority.LOW]]
        assert _literal_has_numeric_enum(annotation) is True


class SimpleModel(BaseModel):
    name: str
    age: int


class TestGetModelFields:
    """Tests for _get_model_fields function."""

    def test_basemodel(self):
        fields = _get_model_fields(SimpleModel)
        assert "name" in fields
        assert "age" in fields

    def test_invalid_model(self):
        with pytest.raises(Exception):
            _get_model_fields(str)  # type: ignore[arg-type]


class TestGetAliasNames:
    """Tests for _get_alias_names function."""

    def test_field_without_alias(self):
        field = FieldInfo()
        result, is_alias_path_only = _get_alias_names("my_field", field)
        assert "my_field" in result
        assert is_alias_path_only is False

    def test_field_with_string_alias(self):
        field = FieldInfo(alias="myAlias")
        result, is_alias_path_only = _get_alias_names("my_field", field)
        assert "myAlias" in result
        assert is_alias_path_only is False

    def test_field_with_validation_alias(self):
        field = FieldInfo(validation_alias="valAlias")
        result, is_alias_path_only = _get_alias_names("my_field", field)
        assert "valAlias" in result
        assert is_alias_path_only is False

    def test_case_insensitive(self):
        field = FieldInfo(alias="MyAlias")
        result, _ = _get_alias_names("my_field", field, case_sensitive=False)
        assert "myalias" in result

    def test_populate_by_name(self):
        field = FieldInfo(alias="myAlias")
        result, is_alias_path_only = _get_alias_names(
            "my_field", field, populate_by_name=True
        )
        assert "myAlias" in result
        assert "my_field" in result
        assert is_alias_path_only is False


class TestIsFunction:
    """Tests for _is_function function."""

    def test_regular_function(self):
        def my_func():
            pass

        assert _is_function(my_func) is True

    def test_lambda(self):
        assert _is_function(lambda x: x) is True

    def test_builtin_function(self):
        assert _is_function(len) is True

    def test_class(self):
        class MyClass:
            pass

        assert _is_function(MyClass) is False

    def test_instance(self):
        assert _is_function("string") is False

    def test_none(self):
        assert _is_function(None) is False


class TestGetAliasNamesAdvanced:
    """Advanced tests for _get_alias_names with AliasChoices and AliasPath."""

    def test_alias_choices_with_strings(self):
        from pydantic import AliasChoices

        field = FieldInfo(validation_alias=AliasChoices("alias1", "alias2"))
        result, is_alias_path_only = _get_alias_names("my_field", field)
        assert "alias1" in result
        assert "alias2" in result
        assert is_alias_path_only is False

    def test_alias_path(self):
        from pydantic import AliasPath

        field = FieldInfo(validation_alias=AliasPath("nested", "field"))
        alias_path_args: dict[str, int | None] = {}
        result, is_alias_path_only = _get_alias_names(
            "my_field", field, alias_path_args=alias_path_args
        )
        assert "nested" in result
        assert is_alias_path_only is True

    def test_alias_path_with_index(self):
        from pydantic import AliasPath

        field = FieldInfo(validation_alias=AliasPath("items", 0))
        alias_path_args: dict[str, int | None] = {}
        result, is_alias_path_only = _get_alias_names(
            "my_field", field, alias_path_args=alias_path_args
        )
        assert "items" in result
        assert alias_path_args.get("items") == 0
        assert is_alias_path_only is True

    def test_alias_choices_with_alias_path(self):
        from pydantic import AliasChoices, AliasPath

        field = FieldInfo(
            validation_alias=AliasChoices("str_alias", AliasPath("nested", "path"))
        )
        alias_path_args: dict[str, int | None] = {}
        result, is_alias_path_only = _get_alias_names(
            "my_field", field, alias_path_args=alias_path_args
        )
        assert "str_alias" in result
        # nested is recorded in alias_path_args but not in result when string alias exists
        assert "nested" in alias_path_args
        assert is_alias_path_only is False


class TestAnnotationIsComplexDataclass:
    """Tests for _annotation_is_complex with dataclasses."""

    def test_dataclass_is_complex(self):
        from dataclasses import dataclass

        @dataclass
        class MyDataclass:
            name: str

        assert _annotation_is_complex(MyDataclass, []) is True


class TestGetModelFieldsPydanticDataclass:
    """Tests for _get_model_fields with pydantic dataclasses."""

    def test_pydantic_dataclass(self):
        from pydantic.dataclasses import dataclass

        @dataclass
        class MyPydanticDataclass:
            name: str
            age: int

        fields = _get_model_fields(MyPydanticDataclass)
        assert "name" in fields
        assert "age" in fields


class TestAnnotationContainsTypesAdvanced:
    """Advanced tests for _annotation_contains_types."""

    def test_no_include_origin(self):
        result = _annotation_contains_types(
            List[int], (list,), is_include_origin=False
        )
        assert result is False

    def test_collect_multiple_types(self):
        collected: set[Any] = set()
        _annotation_contains_types(
            Dict[str, List[int]], (list, dict), collect=collected
        )
        assert len(collected) == 2

    def test_is_instance_origin_with_collect(self):
        """Test that when is_instance=True, origin is instance of types, and collect is provided, it adds to collect."""
        collected: set[Any] = set()
        # List[int] has origin=list, and list is an instance of type
        result = _annotation_contains_types(
            List[int], (type,), is_instance=True, collect=collected
        )
        # Should return True at the end because of annotation in types or other conditions
        # List[int] origin is list which is an instance of type, so it should be added to collect
        assert List[int] in collected

    def test_is_instance_annotation_itself_with_collect(self):
        """Test is_instance check on annotation itself (not origin) with collect (line 200-202)."""
        collected: set[Any] = set()
        # Use int as annotation and check if it's an instance of 'type' class
        # This will hit line 199-202 since int is an instance of type
        # Also include int in types so the function returns True at the end
        result = _annotation_contains_types(
            int, (type, int), is_instance=True, is_include_origin=False, collect=collected
        )
        # The function should return True because int is in (type, int)
        # and should add int to collected via line 202 (is_instance check on annotation)
        # and also via line 205 (direct match)
        assert result is True
        assert int in collected

    def test_is_instance_annotation_itself_returns_true(self):
        """Test is_instance check on annotation itself returns True without collect."""
        T = TypeVar('T')
        result = _annotation_contains_types(
            T, (TypeVar,), is_instance=True, is_include_origin=False
        )
        assert result is True

    def test_direct_type_match_with_collect(self):
        """Test that when annotation is directly in types and collect is provided, it adds to collect."""
        collected: set[Any] = set()
        result = _annotation_contains_types(int, (int, str), collect=collected)
        assert result is True
        assert int in collected

    def test_direct_type_match_with_collect_no_origin_match(self):
        """Test direct type match with collect when origin doesn't match."""
        collected: set[Any] = set()
        # Use a simple type that won't match origin checks but will match direct type check
        result = _annotation_contains_types(str, (str,), collect=collected)
        assert result is True
        assert str in collected


class TestUnionIsComplexWithAnnotated:
    """Tests for _union_is_complex with Annotated types."""

    def test_deeply_nested_annotated_union(self):
        annotation = Union[str, Annotated[Union[int, List[str]], Field()]]
        assert _union_is_complex(annotation, []) is True
