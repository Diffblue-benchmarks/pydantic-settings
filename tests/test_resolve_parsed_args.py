"""Tests for CliSettingsSource._resolve_parsed_args."""
from __future__ import annotations

from enum import Enum
from typing import Annotated, List

import pytest
from pydantic import AliasPath, BaseModel, Field

from pydantic_settings import BaseSettings, CliSettingsSource, NoDecode


# --- Models used in tests ---


class InnerWithAlias(BaseModel):
    value: str = Field(default='', validation_alias=AliasPath('data', 'key'))


class OuterWithNested(BaseSettings):
    nested: InnerWithAlias = Field(default_factory=InnerWithAlias)


class ListSettings(BaseSettings):
    items: List[str] = []


class NoDecodeListSettings(BaseSettings):
    numbers: Annotated[List[str], NoDecode] = []


class Color(Enum):
    dark_blue = 'dark_blue'
    red = 'red'


class KebabEnumSettings(BaseSettings):
    color: Color = Color.red


# --- _resolve_parsed_args tests ---


def test_resolve_parsed_args_nested_alias_path_workaround_fires():
    """Lines 566-569: When _is_nested_alias_path_only_workaround returns True, continue is executed."""
    source = CliSettingsSource(OuterWithNested, cli_parse_args=[])
    parsed_args: dict = {'nested.data': ['{"key": "hello"}']}
    result = source._resolve_parsed_args(parsed_args)
    assert result == []
    assert 'nested.data' not in parsed_args
    assert 'nested' in parsed_args


def test_resolve_parsed_args_nested_alias_path_skips_further_list_processing():
    """Lines 566-569: After workaround fires, val is NOT processed by merge or no_decode logic."""
    source = CliSettingsSource(OuterWithNested, cli_parse_args=[])
    parsed_args: dict = {'nested.data': ['{"key": "hello"}']}
    source._resolve_parsed_args(parsed_args)
    # The original key is gone and nested key was set as a string, not merged via _merge_parsed_list
    assert isinstance(parsed_args.get('nested'), str)


def test_resolve_parsed_args_list_merge_regular_field():
    """Line 576: For a regular list field (no NoDecode), _merge_parsed_list is called."""
    source = CliSettingsSource(ListSettings, cli_parse_args=[])
    parsed_args: dict = {'items': ['"a"']}
    source._resolve_parsed_args(parsed_args)
    # After merge, the list is replaced by a string representation
    assert isinstance(parsed_args['items'], str)


def test_resolve_parsed_args_no_decode_list_joins_with_comma():
    """Lines 571-574: When is_no_decode is True for a list field, values are joined with commas."""
    source = CliSettingsSource(NoDecodeListSettings, cli_parse_args=[])
    parsed_args: dict = {'numbers': ['1', '2', '3']}
    source._resolve_parsed_args(parsed_args)
    assert parsed_args['numbers'] == '1,2,3'


def test_resolve_parsed_args_no_decode_list_single_value():
    """Lines 571-574: NoDecode with a single list item produces joined string."""
    source = CliSettingsSource(NoDecodeListSettings, cli_parse_args=[])
    parsed_args: dict = {'numbers': ['42']}
    source._resolve_parsed_args(parsed_args)
    assert parsed_args['numbers'] == '42'


def test_resolve_parsed_args_kebab_case_all_converts_kebab_to_snake():
    """Line 589: When cli_kebab_case='all' and val is valid kebab-case enum, converted to snake_case."""
    source = CliSettingsSource(KebabEnumSettings, cli_parse_args=[], cli_kebab_case='all')
    parsed_args: dict = {'color': 'dark-blue'}
    source._resolve_parsed_args(parsed_args)
    assert parsed_args['color'] == 'dark_blue'


def test_resolve_parsed_args_kebab_case_all_raises_on_underscore_input():
    """Lines 587-588: When cli_kebab_case='all' and val contains underscore matching an enum, raises ValueError."""
    source = CliSettingsSource(KebabEnumSettings, cli_parse_args=[], cli_kebab_case='all')
    parsed_args: dict = {'color': 'dark_blue'}
    with pytest.raises(ValueError, match='Input should be kebab-case'):
        source._resolve_parsed_args(parsed_args)


def test_resolve_parsed_args_kebab_case_all_no_match_leaves_unchanged():
    """Lines 580-582: When cli_kebab_case='all' but snake_val not in enum names, no change."""
    source = CliSettingsSource(KebabEnumSettings, cli_parse_args=[], cli_kebab_case='all')
    parsed_args: dict = {'color': 'blue'}
    source._resolve_parsed_args(parsed_args)
    assert parsed_args['color'] == 'blue'


def test_resolve_parsed_args_kebab_case_all_simple_str_no_enum():
    """Lines 580-582: cli_kebab_case='all' on a non-enum field does not raise."""
    source = CliSettingsSource(ListSettings, cli_parse_args=[], cli_kebab_case='all')
    # items is a list field; if val is somehow a str it should pass through without error
    parsed_args: dict = {'other': 'some-value'}
    source._resolve_parsed_args(parsed_args)
    assert parsed_args['other'] == 'some-value'


def test_resolve_parsed_args_returns_empty_list_when_no_subcommands():
    """Line 591: Method returns empty list when no subcommands present."""
    source = CliSettingsSource(ListSettings, cli_parse_args=[])
    result = source._resolve_parsed_args({'items': ['"a"']})
    assert result == []
