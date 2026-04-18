"""Tests for CLI settings source."""

from __future__ import annotations

import argparse
import json
from argparse import ArgumentParser, Namespace
from enum import Enum
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import BaseModel, Field

from pydantic_settings import BaseSettings
from pydantic_settings.exceptions import SettingsError
from pydantic_settings.sources.providers.cli import (
    CliMutuallyExclusiveGroup,
    CliPositionalArg,
    CliSettingsSource,
    CliSubCommand,
    _CliArg,
    _CliInternalArgParser,
    _collect_sub_models,
)


class SimpleSettings(BaseSettings):
    """Simple settings for testing."""

    field1: str = 'default1'
    field2: int = 42
    field3: str | None = None


def test_cli_internal_arg_parser_init() -> None:
    """Test _CliInternalArgParser initialization."""
    parser = _CliInternalArgParser(cli_exit_on_error=True, prog='test')
    assert parser._cli_exit_on_error is True


def test_cli_internal_arg_parser_init_default() -> None:
    """Test _CliInternalArgParser initialization with default."""
    parser = _CliInternalArgParser(prog='test')
    assert parser._cli_exit_on_error is True


def test_cli_internal_arg_parser_error_raises() -> None:
    """Test _CliInternalArgParser error raises SettingsError."""
    parser = _CliInternalArgParser(cli_exit_on_error=False, prog='test')
    with pytest.raises(SettingsError, match='error parsing CLI'):
        parser.error('test error')


def test_cli_internal_arg_parser_error_exits() -> None:
    """Test _CliInternalArgParser error exits normally."""
    parser = _CliInternalArgParser(cli_exit_on_error=True, prog='test')
    with pytest.raises(SystemExit):
        parser.error('test error')


class SubModel(BaseModel):
    """Sub model for testing."""

    field: str = 'sub'


def test_collect_sub_models() -> None:
    """Test _collect_sub_models function."""
    sub_models: list[type[BaseModel]] = []
    _collect_sub_models(SubModel, sub_models)
    assert SubModel in sub_models


def test_collect_sub_models_union() -> None:
    """Test _collect_sub_models with union types."""
    sub_models: list[type[BaseModel]] = []
    _collect_sub_models(SubModel | None, sub_models)
    assert SubModel in sub_models


def test_cli_arg_get_kebab_case() -> None:
    """Test _CliArg.get_kebab_case method."""
    assert _CliArg.get_kebab_case('test_name', True) == 'test-name'
    assert _CliArg.get_kebab_case('test_name', False) == 'test_name'


class SampleEnum(Enum):
    """Enum for testing."""

    VALUE_ONE = 1
    VALUE_TWO = 2


def test_cli_arg_get_enum_names() -> None:
    """Test _CliArg.get_enum_names method."""
    names = _CliArg.get_enum_names(SampleEnum, False)
    assert 'VALUE_ONE' in names
    assert 'VALUE_TWO' in names


def test_cli_arg_get_enum_names_kebab() -> None:
    """Test _CliArg.get_enum_names with kebab case."""
    names = _CliArg.get_enum_names(SampleEnum, 'all')
    assert 'VALUE-ONE' in names
    assert 'VALUE-TWO' in names


class SettingsWithSubCommand(BaseSettings):
    """Settings with sub command."""

    cmd: CliSubCommand[SubModel]


@pytest.mark.skip(reason="SubCommand requires complex setup")
def test_cli_arg_subcommand_alias() -> None:
    """Test _CliArg.subcommand_alias method."""
    source = CliSettingsSource(SettingsWithSubCommand)
    for arg_map in source._parser_map.values():
        for arg in arg_map.values():
            if hasattr(arg, 'subcommand_alias'):
                alias = arg.subcommand_alias(SubModel)
                assert isinstance(alias, str)
                break


def test_cli_arg_field_info() -> None:
    """Test _CliArg.field_info property."""
    source = CliSettingsSource(SimpleSettings)
    for arg_map in source._parser_map.values():
        for arg in arg_map.values():
            if hasattr(arg, 'field_info'):
                assert arg.field_info is not None
                break


@pytest.mark.skip(reason="SubCommand requires complex setup")
def test_cli_arg_subcommand_dest() -> None:
    """Test _CliArg.subcommand_dest property."""
    source = CliSettingsSource(SettingsWithSubCommand)
    for arg_map in source._parser_map.values():
        for arg in arg_map.values():
            dest = arg.subcommand_dest
            break


def test_cli_arg_dest() -> None:
    """Test _CliArg.dest property."""
    source = CliSettingsSource(SimpleSettings)
    for arg_map in source._parser_map.values():
        for arg in arg_map.values():
            dest = arg.dest
            assert isinstance(dest, str)
            break


def test_cli_arg_preferred_arg_name() -> None:
    """Test _CliArg.preferred_arg_name property."""
    source = CliSettingsSource(SimpleSettings, cli_kebab_case=True)
    for arg_map in source._parser_map.values():
        for arg in arg_map.values():
            name = arg.preferred_arg_name
            assert isinstance(name, str)
            break


class SettingsWithNestedAnnotation(BaseSettings):
    """Settings with nested annotation."""

    field: list[str] = []


def test_cli_arg_sub_models() -> None:
    """Test _CliArg.sub_models property."""
    source = CliSettingsSource(SettingsWithNestedAnnotation)
    for arg_map in source._parser_map.values():
        for arg in arg_map.values():
            models = arg.sub_models
            assert isinstance(models, list)
            break


def test_cli_arg_alias_names() -> None:
    """Test _CliArg.alias_names property."""
    source = CliSettingsSource(SimpleSettings)
    for arg_map in source._parser_map.values():
        for arg in arg_map.values():
            names = arg.alias_names
            assert isinstance(names, tuple)
            break


def test_cli_arg_alias_paths() -> None:
    """Test _CliArg.alias_paths property."""
    source = CliSettingsSource(SimpleSettings)
    for arg_map in source._parser_map.values():
        for arg in arg_map.values():
            paths = arg.alias_paths
            assert isinstance(paths, dict)
            break


def test_cli_arg_preferred_alias() -> None:
    """Test _CliArg.preferred_alias property."""
    source = CliSettingsSource(SimpleSettings)
    for arg_map in source._parser_map.values():
        for arg in arg_map.values():
            alias = arg.preferred_alias
            assert isinstance(alias, str)
            break


def test_cli_arg_is_alias_path_only() -> None:
    """Test _CliArg.is_alias_path_only property."""
    source = CliSettingsSource(SimpleSettings)
    for arg_map in source._parser_map.values():
        for arg in arg_map.values():
            result = arg.is_alias_path_only
            assert isinstance(result, bool)
            break


def test_cli_arg_is_append_action() -> None:
    """Test _CliArg.is_append_action property."""
    source = CliSettingsSource(SettingsWithNestedAnnotation)
    for arg_map in source._parser_map.values():
        for arg in arg_map.values():
            result = arg.is_append_action
            assert isinstance(result, bool)
            break


def test_cli_arg_is_parser_submodel() -> None:
    """Test _CliArg.is_parser_submodel property."""
    source = CliSettingsSource(SimpleSettings)
    for arg_map in source._parser_map.values():
        for arg in arg_map.values():
            result = arg.is_parser_submodel
            assert isinstance(result, bool)
            break


def test_cli_arg_is_no_decode() -> None:
    """Test _CliArg.is_no_decode property."""
    source = CliSettingsSource(SimpleSettings)
    for arg_map in source._parser_map.values():
        for arg in arg_map.values():
            result = arg.is_no_decode
            assert isinstance(result, bool)
            break


def test_cli_settings_source_init() -> None:
    """Test CliSettingsSource initialization."""
    source = CliSettingsSource(SimpleSettings)
    assert source is not None


def test_cli_settings_source_init_with_prog_name() -> None:
    """Test CliSettingsSource initialization with cli_prog_name."""
    source = CliSettingsSource(SimpleSettings, cli_prog_name='test_prog')
    assert source.cli_prog_name == 'test_prog'


def test_cli_settings_source_init_with_parse_none_str() -> None:
    """Test CliSettingsSource initialization with cli_parse_none_str."""
    source = CliSettingsSource(SimpleSettings, cli_parse_none_str='NULL')
    assert source.cli_parse_none_str == 'NULL'


def test_cli_settings_source_init_with_hide_none_type() -> None:
    """Test CliSettingsSource initialization with cli_hide_none_type."""
    source = CliSettingsSource(SimpleSettings, cli_hide_none_type=True)
    assert source.cli_hide_none_type is True


def test_cli_settings_source_init_with_avoid_json() -> None:
    """Test CliSettingsSource initialization with cli_avoid_json."""
    source = CliSettingsSource(SimpleSettings, cli_avoid_json=True)
    assert source.cli_avoid_json is True


def test_cli_settings_source_init_with_enforce_required() -> None:
    """Test CliSettingsSource initialization with cli_enforce_required."""
    source = CliSettingsSource(SimpleSettings, cli_enforce_required=True)
    assert source.cli_enforce_required is True


def test_cli_settings_source_init_with_use_class_docs_for_groups() -> None:
    """Test CliSettingsSource initialization with cli_use_class_docs_for_groups."""
    source = CliSettingsSource(SimpleSettings, cli_use_class_docs_for_groups=True)
    assert source.cli_use_class_docs_for_groups is True


def test_cli_settings_source_init_with_exit_on_error() -> None:
    """Test CliSettingsSource initialization with cli_exit_on_error."""
    source = CliSettingsSource(SimpleSettings, cli_exit_on_error=False)
    assert source.cli_exit_on_error is False


def test_cli_settings_source_init_with_prefix() -> None:
    """Test CliSettingsSource initialization with cli_prefix."""
    source = CliSettingsSource(SimpleSettings, cli_prefix='test')
    assert source.cli_prefix == 'test.'


def test_cli_settings_source_init_with_invalid_prefix() -> None:
    """Test CliSettingsSource initialization with invalid cli_prefix."""
    with pytest.raises(SettingsError, match='CLI settings source prefix is invalid'):
        CliSettingsSource(SimpleSettings, cli_prefix='.invalid')


def test_cli_settings_source_init_with_flag_prefix_char() -> None:
    """Test CliSettingsSource initialization with cli_flag_prefix_char."""
    source = CliSettingsSource(SimpleSettings, cli_flag_prefix_char='+')
    assert source.cli_flag_prefix_char == '+'


def test_cli_settings_source_init_with_implicit_flags() -> None:
    """Test CliSettingsSource initialization with cli_implicit_flags."""
    source = CliSettingsSource(SimpleSettings, cli_implicit_flags=True)
    assert source.cli_implicit_flags is True


def test_cli_settings_source_init_with_ignore_unknown_args() -> None:
    """Test CliSettingsSource initialization with cli_ignore_unknown_args."""
    source = CliSettingsSource(SimpleSettings, cli_ignore_unknown_args=True)
    assert source.cli_ignore_unknown_args is True


def test_cli_settings_source_init_with_kebab_case() -> None:
    """Test CliSettingsSource initialization with cli_kebab_case."""
    source = CliSettingsSource(SimpleSettings, cli_kebab_case=True)
    assert source.cli_kebab_case is True


def test_cli_settings_source_init_with_shortcuts() -> None:
    """Test CliSettingsSource initialization with cli_shortcuts."""
    shortcuts = {'field1': 'f1'}
    source = CliSettingsSource(SimpleSettings, cli_shortcuts=shortcuts)
    assert source.cli_shortcuts == shortcuts


def test_cli_settings_source_init_case_insensitive_custom_parser() -> None:
    """Test CliSettingsSource initialization with case_sensitive=False and custom parser."""
    custom_parser = ArgumentParser()
    with pytest.raises(SettingsError, match='Case-insensitive matching is only supported'):
        CliSettingsSource(SimpleSettings, case_sensitive=False, root_parser=custom_parser)


def test_cli_settings_source_init_with_parse_args_true() -> None:
    """Test CliSettingsSource initialization with cli_parse_args=True."""
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    assert source.env_vars is not None


def test_cli_settings_source_init_with_invalid_parse_args() -> None:
    """Test CliSettingsSource initialization with invalid cli_parse_args."""
    with pytest.raises(SettingsError, match='cli_parse_args must be a list or tuple'):
        CliSettingsSource(SimpleSettings, cli_parse_args='invalid')


def test_cli_settings_source_call() -> None:
    """Test CliSettingsSource __call__ method."""
    source = CliSettingsSource(SimpleSettings)
    result = source()
    assert isinstance(result, dict)


def test_cli_settings_source_call_with_args_and_parsed_args() -> None:
    """Test CliSettingsSource __call__ with both args and parsed_args."""
    source = CliSettingsSource(SimpleSettings)
    with pytest.raises(SettingsError, match='are mutually exclusive'):
        source(args=[], parsed_args=Namespace())


def test_cli_settings_source_call_with_args_false() -> None:
    """Test CliSettingsSource __call__ with args=False."""
    source = CliSettingsSource(SimpleSettings)
    result = source(args=False)
    assert source.env_vars is not None


def test_cli_settings_source_call_with_args_true() -> None:
    """Test CliSettingsSource __call__ with args=True."""
    source = CliSettingsSource(SimpleSettings)
    result = source(args=[])
    assert source.env_vars is not None


def test_cli_settings_source_call_with_args_list() -> None:
    """Test CliSettingsSource __call__ with args as list."""
    source = CliSettingsSource(SimpleSettings)
    result = source(args=['--field1', 'test'])
    assert source.env_vars is not None


def test_cli_settings_source_call_with_parsed_args() -> None:
    """Test CliSettingsSource __call__ with parsed_args."""
    source = CliSettingsSource(SimpleSettings)
    result = source(parsed_args=Namespace(field1='test'))
    assert source.env_vars is not None


def test_cli_settings_source_call_with_parsed_dict() -> None:
    """Test CliSettingsSource __call__ with parsed_args as dict."""
    source = CliSettingsSource(SimpleSettings)
    result = source(parsed_args={'field1': 'test'})
    assert source.env_vars is not None


def test_cli_settings_source_load_env_vars() -> None:
    """Test CliSettingsSource _load_env_vars method."""
    source = CliSettingsSource(SimpleSettings)
    result = source._load_env_vars()
    assert result == {}


def test_cli_settings_source_load_env_vars_with_parsed_args() -> None:
    """Test CliSettingsSource _load_env_vars with parsed_args."""
    source = CliSettingsSource(SimpleSettings)
    result = source._load_env_vars(parsed_args=Namespace(field1='test'))
    assert source.env_vars is not None


def test_cli_settings_source_load_env_vars_with_simple_namespace() -> None:
    """Test CliSettingsSource _load_env_vars with SimpleNamespace."""
    source = CliSettingsSource(SimpleSettings)
    result = source._load_env_vars(parsed_args=SimpleNamespace(field1='test'))
    assert source.env_vars is not None


def test_cli_settings_source_resolve_parsed_args() -> None:
    """Test CliSettingsSource _resolve_parsed_args method."""
    source = CliSettingsSource(SettingsWithNestedAnnotation)
    parsed_args = {'field': ['value1', 'value2']}
    result = source._resolve_parsed_args(parsed_args)
    assert isinstance(result, list)


def test_cli_settings_source_consume_comma() -> None:
    """Test CliSettingsSource _consume_comma method."""
    source = CliSettingsSource(SimpleSettings)
    merged_list: list[str] = []
    result = source._consume_comma(',test', merged_list, False)
    assert result == 'test'
    assert merged_list == ['""']


def test_cli_settings_source_consume_object_or_array() -> None:
    """Test CliSettingsSource _consume_object_or_array method."""
    source = CliSettingsSource(SimpleSettings)
    merged_list: list[str] = []
    result = source._consume_object_or_array('{"key": "value"} rest', merged_list)
    assert result == ' rest'
    assert '{"key": "value"}' in merged_list


def test_cli_settings_source_consume_object_or_array_array() -> None:
    """Test CliSettingsSource _consume_object_or_array with array."""
    source = CliSettingsSource(SimpleSettings)
    merged_list: list[str] = []
    result = source._consume_object_or_array('[1, 2, 3] rest', merged_list)
    assert result == ' rest'
    assert '[1, 2, 3]' in merged_list


def test_cli_settings_source_consume_object_or_array_missing_delimiter() -> None:
    """Test CliSettingsSource _consume_object_or_array with missing delimiter."""
    source = CliSettingsSource(SimpleSettings)
    merged_list: list[str] = []
    with pytest.raises(SettingsError, match='Missing end delimiter'):
        source._consume_object_or_array('{"key": "value"', merged_list)


def test_cli_settings_source_consume_string_or_number_string() -> None:
    """Test CliSettingsSource _consume_string_or_number with string."""
    source = CliSettingsSource(SimpleSettings)
    merged_list: list[str] = []
    result = source._consume_string_or_number('test,rest', merged_list, list)
    assert result == ',rest'
    assert '"test"' in merged_list


def test_cli_settings_source_consume_string_or_number_number() -> None:
    """Test CliSettingsSource _consume_string_or_number with number."""
    source = CliSettingsSource(SimpleSettings)
    merged_list: list[str] = []
    result = source._consume_string_or_number('123,rest', merged_list, list)
    assert result == ',rest'
    assert '123' in merged_list


def test_cli_settings_source_consume_string_or_number_mismatched_quotes() -> None:
    """Test CliSettingsSource _consume_string_or_number with mismatched quotes."""
    source = CliSettingsSource(SimpleSettings)
    merged_list: list[str] = []
    with pytest.raises(SettingsError, match='Mismatched quotes'):
        source._consume_string_or_number('"test', merged_list, list)


def test_cli_settings_source_root_parser() -> None:
    """Test CliSettingsSource root_parser property."""
    source = CliSettingsSource(SimpleSettings)
    assert source.root_parser is not None


def test_cli_settings_source_metavar_format_choices() -> None:
    """Test CliSettingsSource _metavar_format_choices method."""
    source = CliSettingsSource(SimpleSettings)
    result = source._metavar_format_choices(['str', 'int'])
    assert result == '{str,int}'


def test_cli_settings_source_metavar_format_choices_with_json() -> None:
    """Test CliSettingsSource _metavar_format_choices with JSON."""
    source = CliSettingsSource(SimpleSettings)
    result = source._metavar_format_choices(['JSON', 'str', 'JSON'])
    assert 'JSON' in result


def test_cli_settings_source_metavar_format_recurse() -> None:
    """Test CliSettingsSource _metavar_format_recurse method."""
    source = CliSettingsSource(SimpleSettings)
    result = source._metavar_format_recurse(str)
    assert result == 'str'


def test_cli_settings_source_metavar_format() -> None:
    """Test CliSettingsSource _metavar_format method."""
    source = CliSettingsSource(SimpleSettings)
    result = source._metavar_format(str)
    assert isinstance(result, str)


def test_cli_settings_source_help_format() -> None:
    """Test CliSettingsSource _help_format method."""
    source = CliSettingsSource(SimpleSettings)
    from pydantic_settings.sources.utils import _get_model_fields

    fields = _get_model_fields(SimpleSettings)
    field_info = fields['field1']
    result = source._help_format('field1', field_info, None, False)
    assert isinstance(result, str)


def test_cli_settings_source_is_field_suppressed() -> None:
    """Test CliSettingsSource _is_field_suppressed method."""
    source = CliSettingsSource(SimpleSettings)
    from pydantic_settings.sources.utils import _get_model_fields

    fields = _get_model_fields(SimpleSettings)
    field_info = fields['field1']
    result = source._is_field_suppressed(field_info)
    assert isinstance(result, bool)


def test_cli_settings_source_get_modified_args() -> None:
    """Test CliSettingsSource _get_modified_args method."""
    source = CliSettingsSource(SimpleSettings)
    result = source._get_modified_args(str | int)
    assert str in result
    assert int in result


def test_cli_settings_source_get_modified_args_hide_none() -> None:
    """Test CliSettingsSource _get_modified_args with hide_none_type."""
    source = CliSettingsSource(SimpleSettings, cli_hide_none_type=True)
    result = source._get_modified_args(str | None)
    assert str in result
    assert type(None) not in result
