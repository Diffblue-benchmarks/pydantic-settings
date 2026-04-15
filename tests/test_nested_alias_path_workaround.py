"""Tests for CliSettingsSource._is_nested_alias_path_only_workaround."""
from __future__ import annotations

import pytest
from pydantic import AliasPath, BaseModel, Field

from pydantic_settings import BaseSettings, CliSettingsSource


class InnerWithAlias(BaseModel):
    value: str = Field(default='', validation_alias=AliasPath('data', 'key'))


class OuterWithNested(BaseSettings):
    nested: InnerWithAlias = Field(default_factory=InnerWithAlias)


class TopLevelAliasSettings(BaseSettings):
    value: str = Field(default='', validation_alias=AliasPath('root', 'key'))


class SimpleSettings(BaseSettings):
    name: str = 'default'


@pytest.fixture
def nested_source():
    return CliSettingsSource(OuterWithNested, cli_parse_args=[])


@pytest.fixture
def simple_source():
    return CliSettingsSource(SimpleSettings, cli_parse_args=[])


def test_workaround_field_not_in_parser_map_returns_false(nested_source):
    """When field_name is not in _parser_map, returns False."""
    parsed_args = {'nonexistent': ['val']}
    result = nested_source._is_nested_alias_path_only_workaround(parsed_args, 'nonexistent', ['val'])
    assert result is False


def test_workaround_field_not_alias_path_only_returns_false(simple_source):
    """When field has no alias (is_alias_path_only=False), returns False."""
    parsed_args = {'name': ['hello']}
    result = simple_source._is_nested_alias_path_only_workaround(parsed_args, 'name', ['hello'])
    assert result is False


def test_workaround_top_level_alias_path_returns_false():
    """When arg_prefix does not end with '.', returns False (top-level AliasPath field)."""
    source = CliSettingsSource(TopLevelAliasSettings, cli_parse_args=[])
    parsed_args = {'root': ['{"key": "hello"}']}
    result = source._is_nested_alias_path_only_workaround(parsed_args, 'root', ['{"key": "hello"}'])
    assert result is False


def test_workaround_nested_alias_path_returns_true_and_updates_parsed_args(nested_source):
    """When is_alias_path_only=True and arg_prefix ends with '.', returns True and updates parsed_args."""
    parsed_args = {'nested.data': ['{"key": "hello"}']}
    result = nested_source._is_nested_alias_path_only_workaround(
        parsed_args, 'nested.data', ['{"key": "hello"}']
    )
    assert result is True
    assert 'nested.data' not in parsed_args
    assert 'nested' in parsed_args
    assert '"data"' in parsed_args['nested']


def test_workaround_nested_alias_path_nested_dest_not_in_parsed_args(nested_source):
    """When nested_dest is not in parsed_args, creates new entry with curly braces."""
    parsed_args = {'nested.data': ['{"key": "hello"}']}
    nested_source._is_nested_alias_path_only_workaround(
        parsed_args, 'nested.data', ['{"key": "hello"}']
    )
    assert parsed_args['nested'].startswith('{')
    assert parsed_args['nested'].endswith('}')


def test_workaround_nested_alias_path_nested_dest_already_in_parsed_args(nested_source):
    """When nested_dest is already in parsed_args, merges the new value into existing entry."""
    existing = '{"other": "existing"}'
    parsed_args = {'nested.data': ['{"key": "hello"}'], 'nested': existing}
    result = nested_source._is_nested_alias_path_only_workaround(
        parsed_args, 'nested.data', ['{"key": "hello"}']
    )
    assert result is True
    assert 'nested.data' not in parsed_args
    assert '"other"' in parsed_args['nested']
    assert '"data"' in parsed_args['nested']


def test_workaround_deletes_original_field_from_parsed_args(nested_source):
    """The original field_name entry is removed from parsed_args on success."""
    parsed_args = {'nested.data': ['{"key": "val"}']}
    nested_source._is_nested_alias_path_only_workaround(
        parsed_args, 'nested.data', ['{"key": "val"}']
    )
    assert 'nested.data' not in parsed_args
