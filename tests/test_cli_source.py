"""Tests for CLI settings source provider."""
from __future__ import annotations

from argparse import ArgumentParser, Namespace
from collections import defaultdict
from enum import Enum
from types import SimpleNamespace
from typing import Any, List, Optional, Union

import pytest
from pydantic import AliasChoices, AliasPath, BaseModel, Field
from pydantic.fields import FieldInfo

from pydantic_settings import BaseSettings, CliSettingsSource
from pydantic_settings.exceptions import SettingsError
from pydantic_settings.sources.providers.cli import (
    CliMutuallyExclusiveGroup,
    CliPositionalArg,
    CliSubCommand,
    _CliArg,
    _CliInternalArgParser,
    _collect_sub_models,
)


# --- Simple settings for tests ---


class SimpleSettings(BaseSettings):
    name: str = 'default'
    value: int = 0


class NestedModel(BaseModel):
    x: int = 1
    y: int = 2


class SettingsWithNested(BaseSettings):
    nested: NestedModel = NestedModel()
    flag: bool = False


class SettingsWithRequired(BaseSettings):
    required_field: str


# --- _CliInternalArgParser tests ---


def test_internal_arg_parser_init_stores_exit_on_error():
    parser = _CliInternalArgParser(cli_exit_on_error=False, prog='test')
    assert parser._cli_exit_on_error is False


def test_internal_arg_parser_init_default_exit_on_error():
    parser = _CliInternalArgParser(prog='test')
    assert parser._cli_exit_on_error is True


def test_internal_arg_parser_error_raises_settings_error_when_no_exit():
    parser = _CliInternalArgParser(cli_exit_on_error=False, prog='test')
    with pytest.raises(SettingsError, match='error parsing CLI: bad argument'):
        parser.error('bad argument')


def test_internal_arg_parser_error_calls_super_when_exit_on_error():
    parser = _CliInternalArgParser(cli_exit_on_error=True, prog='test')
    with pytest.raises(SystemExit):
        parser.error('bad argument')


# --- _collect_sub_models tests ---


def test_collect_sub_models_with_base_model():
    sub_models: list[type[BaseModel]] = []
    _collect_sub_models(NestedModel, sub_models)
    assert NestedModel in sub_models


def test_collect_sub_models_with_union():
    sub_models: list[type[BaseModel]] = []
    _collect_sub_models(Optional[NestedModel], sub_models)
    assert NestedModel in sub_models


def test_collect_sub_models_with_non_model():
    sub_models: list[type[BaseModel]] = []
    _collect_sub_models(int, sub_models)
    assert sub_models == []


def test_collect_sub_models_with_nested_union():
    class SubA(BaseModel):
        pass

    class SubB(BaseModel):
        pass

    sub_models: list[type[BaseModel]] = []
    _collect_sub_models(Union[SubA, SubB], sub_models)
    assert SubA in sub_models
    assert SubB in sub_models


# --- CliSettingsSource.__init__ tests ---


def test_cli_settings_source_init_basic():
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    assert source.cli_parse_none_str == 'null'


def test_cli_settings_source_init_avoid_json():
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[], cli_avoid_json=True)
    assert source.cli_parse_none_str == 'None'


def test_cli_settings_source_init_custom_none_str():
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[], cli_parse_none_str='void')
    assert source.cli_parse_none_str == 'void'


def test_cli_settings_source_init_invalid_prefix():
    with pytest.raises(SettingsError, match='CLI settings source prefix is invalid'):
        CliSettingsSource(SimpleSettings, cli_parse_args=[], cli_prefix='.invalid')


def test_cli_settings_source_init_with_valid_prefix():
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[], cli_prefix='myprefix')
    assert source.cli_prefix == 'myprefix.'


def test_cli_settings_source_init_case_insensitive_with_external_parser_raises():
    external_parser = ArgumentParser()
    with pytest.raises(SettingsError, match='Case-insensitive matching is only supported on the internal root parser'):
        CliSettingsSource(SimpleSettings, root_parser=external_parser, case_sensitive=False)


def test_cli_settings_source_init_parse_args_invalid_type():
    with pytest.raises(SettingsError, match='cli_parse_args must be a list or tuple'):
        CliSettingsSource(SimpleSettings, cli_parse_args='invalid')  # type: ignore


def test_cli_settings_source_init_parse_args_list():
    source = CliSettingsSource(SimpleSettings, cli_parse_args=['--name', 'test'])
    assert source is not None


def test_cli_settings_source_init_from_config():
    class ConfiguredSettings(BaseSettings):
        model_config = {'cli_avoid_json': True, 'cli_hide_none_type': True, 'cli_enforce_required': True}
        name: str = 'default'

    source = CliSettingsSource(ConfiguredSettings, cli_parse_args=[])
    assert source.cli_avoid_json is True
    assert source.cli_hide_none_type is True
    assert source.cli_enforce_required is True


# --- CliSettingsSource.__call__ tests ---


def test_cli_settings_source_call_no_args_returns_dict():
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    result = source()
    assert isinstance(result, dict)


def test_cli_settings_source_call_with_args_returns_self():
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    result = source(args=['--name', 'hello'])
    assert result is source


def test_cli_settings_source_call_with_false_args():
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    result = source(args=False)
    assert result is source


def test_cli_settings_source_call_mutual_exclusion_error():
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    with pytest.raises(SettingsError, match='`args` and `parsed_args` are mutually exclusive'):
        source(args=['--name', 'test'], parsed_args={'name': 'test'})


def test_cli_settings_source_call_with_parsed_args_namespace():
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    ns = Namespace(name='from_namespace', value=42)
    result = source(parsed_args=ns)
    assert result is source


def test_cli_settings_source_call_with_parsed_args_dict():
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    result = source(parsed_args={'name': 'from_dict', 'value': '5'})
    assert result is source


def test_cli_settings_source_call_with_simple_namespace():
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    sns = SimpleNamespace(name='simple', value=10)
    result = source(parsed_args=sns)
    assert result is source


# --- root_parser property ---


def test_root_parser_property():
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    parser = source.root_parser
    assert parser is not None


# --- _load_env_vars tests ---


def test_load_env_vars_empty_dict():
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    result = source._load_env_vars()
    assert result == {}


def test_load_env_vars_with_namespace():
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    ns = Namespace(name='from_ns')
    result = source._load_env_vars(parsed_args=ns)
    assert result is source


def test_load_env_vars_with_dict():
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    result = source._load_env_vars(parsed_args={'name': 'test_val'})
    assert result is source


# --- _metavar_format and _metavar_format_recurse ---


def test_metavar_format_simple_type():
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    assert source._metavar_format(str) == 'str'


def test_metavar_format_int():
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    assert source._metavar_format(int) == 'int'


def test_metavar_format_optional():
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    result = source._metavar_format(Optional[str])
    assert 'str' in result


def test_metavar_format_none_type():
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    result = source._metavar_format(type(None))
    assert result == 'null'


def test_metavar_format_with_ellipsis():
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    result = source._metavar_format_recurse(...)
    assert result == '...'


def test_metavar_format_enum():
    class Color(Enum):
        RED = 'red'
        BLUE = 'blue'

    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    result = source._metavar_format(Color)
    assert 'RED' in result or 'BLUE' in result


def test_metavar_format_choices_with_json():
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    result = source._metavar_format_choices(['JSON', 'str', 'JSON'])
    assert result.count('JSON') == 1


def test_metavar_format_choices_single():
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    result = source._metavar_format_choices(['str'])
    assert result == 'str'


def test_metavar_format_choices_multiple():
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    result = source._metavar_format_choices(['str', 'int'])
    assert result == '{str,int}'


# --- _help_format tests ---


def test_help_format_required_field():
    source = CliSettingsSource(SettingsWithRequired, cli_parse_args=[])
    from pydantic_core import PydanticUndefined
    fi = SettingsWithRequired.model_fields['required_field']
    result = source._help_format('required_field', fi, PydanticUndefined, False)
    assert 'required' in result


def test_help_format_suppressed_field():
    from pydantic_settings.sources.providers.cli import CLI_SUPPRESS

    class SuppressedSettings(BaseSettings):
        secret: str = Field(default='x', description=CLI_SUPPRESS)

    source = CliSettingsSource(SuppressedSettings, cli_parse_args=[])
    fi = SuppressedSettings.model_fields['secret']
    from pydantic_core import PydanticUndefined
    result = source._help_format('secret', fi, PydanticUndefined, False)
    assert result == CLI_SUPPRESS


def test_help_format_with_default():
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    fi = SimpleSettings.model_fields['name']
    from pydantic_core import PydanticUndefined
    result = source._help_format('name', fi, PydanticUndefined, False)
    assert 'default' in result


# --- _is_field_suppressed tests ---


def test_is_field_suppressed_false():
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    fi = SimpleSettings.model_fields['name']
    assert source._is_field_suppressed(fi) is False


def test_is_field_suppressed_true():
    from pydantic_settings.sources.providers.cli import CLI_SUPPRESS

    class SuppressedSettings(BaseSettings):
        secret: str = Field(default='x', description=CLI_SUPPRESS)

    source = CliSettingsSource(SuppressedSettings, cli_parse_args=[])
    fi = SuppressedSettings.model_fields['secret']
    assert source._is_field_suppressed(fi) is True


# --- _get_modified_args tests ---


def test_get_modified_args_no_none_hiding():
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    result = source._get_modified_args(Optional[str])
    assert type(None) in result


def test_get_modified_args_with_none_hiding():
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[], cli_hide_none_type=True)
    result = source._get_modified_args(Optional[str])
    assert type(None) not in result


# --- _consume_comma tests ---


def test_consume_comma_with_last_value():
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    merged_list: list[str] = ['a']
    result = source._consume_comma(',b', merged_list, True)
    assert result == 'b'
    assert merged_list == ['a']


def test_consume_comma_without_last_value():
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    merged_list: list[str] = []
    result = source._consume_comma(',b', merged_list, False)
    assert result == 'b'
    assert '""' in merged_list


# --- _consume_object_or_array tests ---


def test_consume_object():
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    merged_list: list[str] = []
    remainder = source._consume_object_or_array('{"key": "val"},rest', merged_list)
    assert merged_list == ['{"key": "val"}']
    assert remainder == ',rest'


def test_consume_array():
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    merged_list: list[str] = []
    remainder = source._consume_object_or_array('[1,2,3]extra', merged_list)
    assert merged_list == ['[1,2,3]']
    assert remainder == 'extra'


def test_consume_object_missing_end_delimiter():
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    with pytest.raises(SettingsError, match='Missing end delimiter'):
        source._consume_object_or_array('{"key": "val"', [])


# --- _consume_string_or_number tests ---


def test_consume_string_simple():
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    merged_list: list[str] = []
    remainder = source._consume_string_or_number('hello,world', merged_list, list)
    assert '"hello"' in merged_list
    assert remainder == ',world'


def test_consume_string_with_str_type():
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    merged_list: list[str] = []
    remainder = source._consume_string_or_number('hello,world', merged_list, str)
    assert remainder == ''
    assert merged_list[0] == '"hello,world"'


def test_consume_string_mismatched_quotes():
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    with pytest.raises(SettingsError, match='Mismatched quotes'):
        source._consume_string_or_number('"unmatched', [], list)


def test_consume_number():
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    merged_list: list[str] = []
    source._consume_string_or_number('42,rest', merged_list, list)
    assert '42' in merged_list


# --- _flatten_serialized_args tests ---


def test_flatten_serialized_args_optional_first():
    result = CliSettingsSource._flatten_serialized_args(
        {'optional': ['--a', '1'], 'positional': ['pos'], 'subcommand': ['sub']},
        positionals_first=False,
    )
    assert result == ['--a', '1', 'pos', 'sub']


def test_flatten_serialized_args_positionals_first():
    result = CliSettingsSource._flatten_serialized_args(
        {'optional': ['--a', '1'], 'positional': ['pos'], 'subcommand': ['sub']},
        positionals_first=True,
    )
    assert result == ['pos', '--a', '1', 'sub']


# --- _coerce_value_styles tests ---


def test_coerce_value_styles_string_no_conversion():
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    result = source._coerce_value_styles('default', 'hello')
    assert result == ['hello']


def test_coerce_value_styles_list_json():
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    result = source._coerce_value_styles([1, 2], '[1, 2]', list_style='json')
    assert result == ['[1, 2]']


def test_coerce_value_styles_list_argparse():
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    result = source._coerce_value_styles([1, 2, 3], '[1, 2, 3]', list_style='argparse')
    assert result == ['1', '2', '3']


def test_coerce_value_styles_list_lazy():
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    result = source._coerce_value_styles([1, 2], '[1, 2]', list_style='lazy')
    assert result == ['1,2']


def test_coerce_value_styles_dict_env():
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    result = source._coerce_value_styles({'a': '1'}, '{"a": "1"}', dict_style='env')
    assert result == ['a=1']


# --- _CliArg.get_kebab_case ---


def test_get_kebab_case_with_kebab():
    result = _CliArg.get_kebab_case('my_field', True)
    assert result == 'my-field'


def test_get_kebab_case_without_kebab():
    result = _CliArg.get_kebab_case('my_field', None)
    assert result == 'my_field'


def test_get_kebab_case_false():
    result = _CliArg.get_kebab_case('my_field', False)
    assert result == 'my_field'


# --- _CliArg.get_enum_names ---


def test_get_enum_names_basic():
    class Color(Enum):
        RED = 'red'
        BLUE = 'blue'

    names = _CliArg.get_enum_names(Color, False)
    assert 'RED' in names
    assert 'BLUE' in names


def test_get_enum_names_kebab():
    class MyEnum(Enum):
        MY_VALUE = 'my_value'

    names = _CliArg.get_enum_names(MyEnum, 'all')
    assert 'MY-VALUE' in names


def test_get_enum_names_non_enum():
    names = _CliArg.get_enum_names(str, False)
    assert names == ()


# --- Integration tests ---


def test_cli_settings_parse_simple_args():
    source = CliSettingsSource(SimpleSettings, cli_parse_args=['--name', 'hello', '--value', '42'])
    result = source()
    assert result.get('name') == 'hello'


def test_cli_settings_source_parse_nested():
    source = CliSettingsSource(SettingsWithNested, cli_parse_args=['--nested.x', '10'])
    result = source()
    assert result is not None


def test_cli_settings_exit_on_error_false():
    source = CliSettingsSource(SimpleSettings, cli_exit_on_error=False)
    with pytest.raises(SettingsError, match='error parsing CLI'):
        source(args=['--nonexistent-arg', 'value'])


def test_cli_settings_source_case_insensitive():
    source = CliSettingsSource(SimpleSettings, cli_parse_args=['--NAME', 'hello'], case_sensitive=False)
    result = source()
    assert result.get('name') == 'hello'


def test_cli_settings_source_parse_none_str():
    source = CliSettingsSource(SimpleSettings, cli_parse_args=['--name', 'null'])
    result = source()
    assert 'name' in result or result is not None


def test_cli_settings_source_with_bool_flag():
    source = CliSettingsSource(SettingsWithNested, cli_parse_args=['--flag', 'true'])
    result = source()
    assert result is not None


def test_cli_settings_source_prefix_with_period_raises():
    with pytest.raises(SettingsError, match='CLI settings source prefix is invalid'):
        CliSettingsSource(SimpleSettings, cli_parse_args=[], cli_prefix='invalid.')


def test_cli_settings_source_prefix_with_leading_period_raises():
    with pytest.raises(SettingsError, match='CLI settings source prefix is invalid'):
        CliSettingsSource(SimpleSettings, cli_parse_args=[], cli_prefix='.invalid')


def test_cli_settings_with_ignore_unknown_args():
    source = CliSettingsSource(SimpleSettings, cli_parse_args=['--name', 'hello', '--unknown', 'val'],
                               cli_ignore_unknown_args=True)
    result = source()
    assert result.get('name') == 'hello'


def test_cli_settings_with_implicit_flags():
    class FlagSettings(BaseSettings):
        verbose: bool = False

    source = CliSettingsSource(FlagSettings, cli_parse_args=['--verbose'], cli_implicit_flags=True)
    result = source()
    assert result is not None


def test_cli_settings_source_kebab_case():
    class KebabSettings(BaseSettings):
        my_option: str = 'default'

    source = CliSettingsSource(KebabSettings, cli_parse_args=['--my-option', 'test'], cli_kebab_case=True)
    result = source()
    assert result.get('my_option') == 'test'


def test_cli_settings_with_subcommand():
    class SubCmdA(BaseModel):
        x: int = 1

    class SubCmdSettings(BaseSettings):
        cmd: CliSubCommand[SubCmdA]

    source = CliSettingsSource(SubCmdSettings, cli_parse_args=['cmd'])
    result = source()
    assert result is not None


def test_verify_cli_flag_annotations_non_bool_raises():
    from pydantic_settings import CliImplicitFlag

    class BadFlagSettings(BaseSettings):
        flag: CliImplicitFlag[str] = 'no'  # type: ignore

    with pytest.raises(Exception):
        CliSettingsSource(BadFlagSettings, cli_parse_args=[], cli_implicit_flags=True)


def test_verify_cli_flag_annotations_explicit_flag_non_bool_raises():
    from pydantic_settings import CliExplicitFlag

    class BadExplicitFlagSettings(BaseSettings):
        flag: CliExplicitFlag[str] = 'no'  # type: ignore

    with pytest.raises(SettingsError, match='CliExplicitFlag'):
        CliSettingsSource(BadExplicitFlagSettings, cli_parse_args=[])


def test_verify_cli_flag_annotations_toggle_flag_non_bool_default_raises():
    from pydantic_settings import CliToggleFlag

    class BadToggleFlagSettings(BaseSettings):
        flag: CliToggleFlag = 'not_a_bool'  # type: ignore

    with pytest.raises(SettingsError, match='must have a default bool value'):
        CliSettingsSource(BadToggleFlagSettings, cli_parse_args=[])


def test_verify_cli_flag_annotations_toggle_flag_bool_default_valid():
    from pydantic_settings import CliToggleFlag

    class ValidToggleFlagSettings(BaseSettings):
        flag: CliToggleFlag[bool] = True

    source = CliSettingsSource(ValidToggleFlagSettings, cli_parse_args=[])
    assert source is not None


def test_verify_cli_flag_annotations_dual_flag_non_bool_raises():
    from pydantic_settings import CliDualFlag

    class BadDualFlagSettings(BaseSettings):
        flag: CliDualFlag[str] = 'no'  # type: ignore

    with pytest.raises(SettingsError, match='CliDualFlag'):
        CliSettingsSource(BadDualFlagSettings, cli_parse_args=[])


def test_sort_arg_fields_subcommand_with_default_raises():
    class SubModel(BaseModel):
        x: int = 1

    class BadSubSettings(BaseSettings):
        cmd: CliSubCommand[SubModel] = None  # type: ignore

    with pytest.raises(Exception):
        CliSettingsSource(BadSubSettings, cli_parse_args=[])


def test_positional_arg_settings():
    class PosSettings(BaseSettings):
        filename: CliPositionalArg[str]

    source = CliSettingsSource(PosSettings, cli_parse_args=['myfile.txt'])
    result = source()
    assert result is not None


def test_merge_parsed_list_simple():
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    result = source._merge_parsed_list(['a', 'b', 'c'], 'some_field')
    assert result is not None


def test_connect_parser_method_none_raises_on_call():
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    none_method = source._connect_parser_method(None, 'some_method')
    with pytest.raises(SettingsError, match='cannot connect CLI settings source root parser'):
        none_method()


def test_connect_parser_method_returns_method():
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    parser = ArgumentParser()
    method = source._connect_parser_method(ArgumentParser.parse_args, 'parse_args_method')
    assert callable(method)


def test_metavar_format_model():
    source = CliSettingsSource(SettingsWithNested, cli_parse_args=[])
    result = source._metavar_format(NestedModel)
    assert result == 'JSON'


def test_convert_append_action_with_list():
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    from pydantic.fields import FieldInfo
    fi = FieldInfo(annotation=List[str])
    kwargs: dict[str, Any] = {'dest': 'items'}
    source._convert_append_action(kwargs, fi, True)
    assert kwargs.get('action') == 'append'


def test_convert_append_action_false():
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    from pydantic.fields import FieldInfo
    fi = FieldInfo(annotation=str)
    kwargs: dict[str, Any] = {'dest': 'name'}
    source._convert_append_action(kwargs, fi, False)
    assert 'action' not in kwargs


# --- _metavar_format_recurse uncovered branch tests ---


def test_metavar_format_recurse_function_without_locals_uses_qualname():
    # Line 1342 else branch: function whose __qualname__ does NOT contain '<locals>'
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])

    def _top_level_like():
        pass

    # Simulate a function with no '<locals>' in qualname by using a module-level function
    result = source._metavar_format_recurse(len)
    # len is a built-in function; its __qualname__ == 'len', no '<locals>'
    assert result == 'len'


def test_metavar_format_recurse_representation_object():
    # Line 1346: isinstance(obj, Representation) branch
    from pydantic._internal._repr import Representation

    class MyRepr(Representation):
        __slots__ = ('value',)

        def __init__(self, value: int) -> None:
            self.value = value

    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    obj = MyRepr(42)
    result = source._metavar_format_recurse(obj)
    assert result == repr(obj)


def test_metavar_format_recurse_forward_ref():
    # Line 1348: isinstance(obj, typing.ForwardRef) branch
    import typing

    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    ref = typing.ForwardRef('MyModel')
    result = source._metavar_format_recurse(ref)
    assert result == str(ref)


def test_metavar_format_recurse_non_type_instance_uses_class():
    # Line 1351: obj is not (_typing_base, _WithArgsTypes, type), so obj = obj.__class__
    # A plain integer instance is not a type; it gets replaced by int, then returns qualname 'int'
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    result = source._metavar_format_recurse(42)
    assert result == 'int'


def test_metavar_format_recurse_literal_type():
    # Line 1357: is_literal(origin) branch
    from typing import Literal

    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    result = source._metavar_format_recurse(Literal['a', 'b'])
    assert 'a' in result and 'b' in result


def test_metavar_format_recurse_generic_alias():
    # Line 1363: isinstance(obj, _WithArgsTypes) branch (e.g. List[str])
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    result = source._metavar_format_recurse(List[str])
    assert 'str' in result


def test_metavar_format_recurse_typing_any_fallback():
    # Line 1378: final else branch — typing.Any is a _Final instance, not a plain type
    import typing

    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    result = source._metavar_format_recurse(typing.Any)
    assert isinstance(result, str)


# --- _sort_arg_fields uncovered branch tests ---


def test_sort_arg_fields_subcommand_multiple_aliases_raises():
    # Line 789: subcommand with multiple aliases raises SettingsError
    class SubModel(BaseModel):
        x: int = 1

    class BadSubSettings(BaseSettings):
        cmd: CliSubCommand[SubModel] = Field(  # type: ignore
            default=..., validation_alias=AliasChoices('cmd_a', 'cmd_b')
        )

    with pytest.raises(SettingsError, match='has multiple aliases'):
        CliSettingsSource(BadSubSettings, cli_parse_args=[])


def test_sort_arg_fields_subcommand_non_model_type_raises():
    # Lines 793-795: subcommand type not derived from BaseModel raises SettingsError
    class BadSubSettings(BaseSettings):
        cmd: CliSubCommand[str]  # type: ignore

    with pytest.raises(SettingsError, match='has type not derived from BaseModel'):
        CliSettingsSource(BadSubSettings, cli_parse_args=[])


def test_sort_arg_fields_positional_multiple_aliases_raises():
    # Line 800: positional arg with multiple aliases raises SettingsError
    class BadPosSettings(BaseSettings):
        filename: CliPositionalArg[str] = Field(  # type: ignore
            default=..., validation_alias=AliasChoices('file_a', 'file_b')
        )

    with pytest.raises(SettingsError, match='has multiple aliases'):
        CliSettingsSource(BadPosSettings, cli_parse_args=[])


def test_sort_arg_fields_variadic_positional_arg():
    # Line 807: positional arg with list annotation goes to positional_variadic_arg
    class VarPosSettings(BaseSettings):
        files: CliPositionalArg[List[str]]

    source = CliSettingsSource(VarPosSettings, cli_parse_args=['a', 'b'])
    result = source()
    assert result is not None


def test_sort_arg_fields_multiple_variadic_positional_raises():
    # Lines 813-815: multiple variadic positional args raises SettingsError
    class MultiVarSettings(BaseSettings):
        files: CliPositionalArg[List[str]]
        names: CliPositionalArg[List[str]]

    with pytest.raises(SettingsError, match='has multiple variadic positional arguments'):
        CliSettingsSource(MultiVarSettings, cli_parse_args=[])


def test_sort_arg_fields_variadic_and_subcommand_raises():
    # Lines 816-820: variadic positional arg combined with subcommand raises SettingsError
    class SubModel(BaseModel):
        x: int = 1

    class MixedSettings(BaseSettings):
        files: CliPositionalArg[List[str]]
        cmd: CliSubCommand[SubModel]

    with pytest.raises(SettingsError, match='has variadic positional arguments and subcommand arguments'):
        CliSettingsSource(MixedSettings, cli_parse_args=[])
