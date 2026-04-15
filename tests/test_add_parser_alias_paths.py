"""Tests for CliSettingsSource._add_parser_alias_paths."""
from __future__ import annotations

import pytest
from pydantic import AliasChoices, AliasPath, BaseModel, Field

from pydantic_settings import BaseSettings, CliSettingsSource


class SettingsWithDictAliasPath(BaseSettings):
    """Settings with AliasPath where path[1] is a string (index=None, dict case)."""

    my_field: str = Field(default='', validation_alias=AliasPath('data', 'key'))


class SettingsWithListAliasPath(BaseSettings):
    """Settings with AliasPath where path[1] is an int (index=0, list case)."""

    my_field: str = Field(default='', validation_alias=AliasPath('data', 0))


class SettingsWithMultipleAliasPaths(BaseSettings):
    """Settings with multiple AliasPath fields."""

    field_a: str = Field(default='', validation_alias=AliasPath('root_a', 'key'))
    field_b: int = Field(default=0, validation_alias=AliasPath('root_b', 1))


class InnerModelWithAliasPath(BaseModel):
    """Nested model whose field uses AliasPath (alias_path_only)."""

    inner_field: str = Field(default='', validation_alias=AliasPath('inner_data', 'key'))


class SettingsWithNestedAliasPath(BaseSettings):
    """Settings with a nested model that has an AliasPath field."""

    nested: InnerModelWithAliasPath = Field(default_factory=InnerModelWithAliasPath)


class InnerModelWithListAliasPath(BaseModel):
    """Nested model whose field uses AliasPath with int index."""

    inner_field: int = Field(default=0, validation_alias=AliasPath('inner_list', 0))


class SettingsWithNestedListAliasPath(BaseSettings):
    """Settings with nested model having AliasPath with int index."""

    nested: InnerModelWithListAliasPath = Field(default_factory=InnerModelWithListAliasPath)


class SettingsWithChoicesAliasPath(BaseSettings):
    """Settings with AliasChoices containing an AliasPath."""

    my_field: str = Field(default='', validation_alias=AliasChoices(AliasPath('choice_data', 'key')))


def test_add_parser_alias_paths_dict_case_group_none():
    """AliasPath with string path element (index=None) registers as dict arg, group=None."""
    source = CliSettingsSource(SettingsWithDictAliasPath, cli_parse_args=[])

    assert 'data' in source._cli_dict_args
    assert source._cli_dict_args['data'] is dict


def test_add_parser_alias_paths_list_case_group_none():
    """AliasPath with int index (index=0) does not register as dict arg, group=None."""
    source = CliSettingsSource(SettingsWithListAliasPath, cli_parse_args=[])

    assert 'data' not in source._cli_dict_args


def test_add_parser_alias_paths_arg_registered_in_parser_map_dict():
    """Dict-case alias path arg is registered in the parser map."""
    source = CliSettingsSource(SettingsWithDictAliasPath, cli_parse_args=[])

    assert 'data' in source._parser_map


def test_add_parser_alias_paths_arg_registered_in_parser_map_list():
    """List-case alias path arg is registered in the parser map."""
    source = CliSettingsSource(SettingsWithListAliasPath, cli_parse_args=[])

    assert 'data' in source._parser_map


def test_add_parser_alias_paths_multiple_fields():
    """Multiple AliasPath fields each get their alias paths registered."""
    source = CliSettingsSource(SettingsWithMultipleAliasPaths, cli_parse_args=[])

    assert 'root_a' in source._cli_dict_args
    assert source._cli_dict_args['root_a'] is dict
    assert 'root_b' not in source._cli_dict_args


def test_add_parser_alias_paths_nested_model_group_not_none():
    """AliasPath inside nested model triggers _add_parser_alias_paths with non-None group."""
    source = CliSettingsSource(SettingsWithNestedAliasPath, cli_parse_args=[])

    assert 'nested.inner_data' in source._cli_dict_args
    assert source._cli_dict_args['nested.inner_data'] is dict


def test_add_parser_alias_paths_nested_model_list_index_group_not_none():
    """AliasPath with int index inside nested model (list case, group not None)."""
    source = CliSettingsSource(SettingsWithNestedListAliasPath, cli_parse_args=[])

    assert 'nested.inner_list' not in source._cli_dict_args
    assert 'nested.inner_list' in source._parser_map


def test_add_parser_alias_paths_alias_choices():
    """AliasChoices containing AliasPath registers the alias path."""
    source = CliSettingsSource(SettingsWithChoicesAliasPath, cli_parse_args=[])

    assert 'choice_data' in source._cli_dict_args


def test_add_parser_alias_paths_args_parseable_dict():
    """Dict-case alias path args can be parsed via CLI with JSON dict input."""
    source = CliSettingsSource(SettingsWithDictAliasPath, cli_parse_args=['--data', '{"key": "hello"}'])
    result = source()

    assert result.get('data') == {'key': 'hello'}


def test_add_parser_alias_paths_args_parseable_list():
    """List-case alias path args can be parsed via CLI with JSON list input."""
    source = CliSettingsSource(SettingsWithListAliasPath, cli_parse_args=['--data', '["world"]'])
    result = source()

    assert result.get('data') == ['world']


def test_add_parser_alias_paths_parser_map_kwargs_set():
    """_add_parser_alias_paths sets correct kwargs on the parser map arg entries."""
    source = CliSettingsSource(SettingsWithDictAliasPath, cli_parse_args=[])

    arg_entry = next(iter(source._parser_map['data'].values()))

    assert arg_entry.kwargs.get('action') == 'append'
    assert arg_entry.kwargs.get('metavar') == 'dict'
