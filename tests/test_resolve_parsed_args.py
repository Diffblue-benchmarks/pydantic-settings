"""Tests for CliSettingsSource._resolve_parsed_args method."""

import enum
from typing import Annotated, Union
from unittest.mock import MagicMock, patch

import pytest

from pydantic import AliasPath, BaseModel, Field

from pydantic_settings import BaseSettings, CliSettingsSource
from pydantic_settings.sources.types import NoDecode


# ---- Models ----

class SimpleSettings(BaseSettings):
    name: str = 'default'
    count: int = 0

    model_config = {'env_file': None}


class MyColor(enum.Enum):
    red = 'red'
    green = 'green'
    dark_blue = 'dark_blue'
    light_green = 'light_green'


class KebabAllEnumSettings(BaseSettings):
    color: MyColor = MyColor.red

    model_config = {'env_file': None, 'cli_kebab_case': 'all'}


class SettingsWithNoDecode(BaseSettings):
    tags: Annotated[list[str], NoDecode] = []

    model_config = {'env_file': None}


class NestedModel(BaseModel):
    value: str = 'x'


class SettingsWithAliasPath(BaseSettings):
    item: str = Field(default='default', validation_alias=AliasPath('nested', 'item'))

    model_config = {'env_file': None}


# ---- Fixtures ----

@pytest.fixture
def simple_source():
    return CliSettingsSource(SimpleSettings, cli_parse_args=[])


@pytest.fixture
def kebab_all_source():
    return CliSettingsSource(KebabAllEnumSettings, cli_parse_args=[], cli_kebab_case='all')


@pytest.fixture
def no_decode_source():
    return CliSettingsSource(SettingsWithNoDecode, cli_parse_args=[])


@pytest.fixture
def alias_path_source():
    return CliSettingsSource(SettingsWithAliasPath, cli_parse_args=[])


# ---- Tests for line 569: _is_nested_alias_path_only_workaround returns True ----

def test_resolve_skips_nested_alias_path_only(simple_source):
    """When _is_nested_alias_path_only_workaround returns True,
    the list value is skipped via continue (line 569)."""
    parsed_args = {'field_a': ['val1', 'val2'], 'other': 'kept'}
    with patch.object(
        simple_source, '_is_nested_alias_path_only_workaround', return_value=True
    ) as mock_workaround:
        result = simple_source._resolve_parsed_args(parsed_args)
    mock_workaround.assert_called_once_with(parsed_args, 'field_a', ['val1', 'val2'])
    assert result == []


# ---- Tests for lines 573-574: is_no_decode list join ----

def test_resolve_joins_no_decode_list(no_decode_source):
    """When a list field has is_no_decode, values are joined with comma (lines 572-574)."""
    parsed_args = {'tags': ['a', 'b', 'c']}

    with patch.object(
        no_decode_source, '_is_nested_alias_path_only_workaround', return_value=False
    ):
        no_decode_source._resolve_parsed_args(parsed_args)

    assert parsed_args['tags'] == 'a,b,c'


def test_resolve_joins_no_decode_single_item(no_decode_source):
    """is_no_decode join works with a single-element list."""
    parsed_args = {'tags': ['only']}

    with patch.object(
        no_decode_source, '_is_nested_alias_path_only_workaround', return_value=False
    ):
        no_decode_source._resolve_parsed_args(parsed_args)

    assert parsed_args['tags'] == 'only'


# ---- Tests for lines 580-589: cli_kebab_case == 'all' enum handling ----

def test_resolve_kebab_all_converts_kebab_enum_to_snake(kebab_all_source):
    """When cli_kebab_case='all' and value matches an enum name after
    kebab-to-snake conversion, the value is replaced (lines 580-586, 589)."""
    parsed_args = {'color': 'dark-blue'}

    kebab_all_source._resolve_parsed_args(parsed_args)

    assert parsed_args['color'] == 'dark_blue'


def test_resolve_kebab_all_raises_on_underscore_in_value(kebab_all_source):
    """When cli_kebab_case='all' and the value contains underscores that match
    an enum name, a ValueError is raised (lines 587-588)."""
    parsed_args = {'color': 'dark_blue'}

    with pytest.raises(ValueError, match='Input should be kebab-case "dark-blue", not "dark_blue"'):
        kebab_all_source._resolve_parsed_args(parsed_args)


def test_resolve_kebab_all_no_match_leaves_value(kebab_all_source):
    """When cli_kebab_case='all' but value doesn't match any enum name,
    the value is left unchanged."""
    parsed_args = {'color': 'purple'}

    kebab_all_source._resolve_parsed_args(parsed_args)

    assert parsed_args['color'] == 'purple'


def test_resolve_kebab_all_no_cli_arg_in_parser_map():
    """When cli_kebab_case='all' but field_name not in _parser_map,
    the value is left unchanged (line 581 returns None)."""
    source = CliSettingsSource(KebabAllEnumSettings, cli_parse_args=[], cli_kebab_case='all')
    parsed_args = {'unknown_field': 'some-value'}

    source._resolve_parsed_args(parsed_args)

    assert parsed_args['unknown_field'] == 'some-value'


# ---- Tests for subcommand selection (line 578) ----

def test_resolve_returns_selected_subcommands(simple_source):
    """When a field ends with ':subcommand' and val is not None,
    the subcommand dest is appended to selected_subcommands (line 578)."""
    mock_arg = MagicMock()
    mock_arg.dest = 'cmd_dest'

    simple_source._parser_map[':subcommand'] = {'my_cmd': mock_arg}
    parsed_args = {':subcommand': 'my_cmd'}

    result = simple_source._resolve_parsed_args(parsed_args)

    assert result == ['cmd_dest']


# ---- Tests for normal list merge (line 576) ----

def test_resolve_merges_normal_list(simple_source):
    """When a list value is not alias_path_only and not no_decode,
    _merge_parsed_list is called (line 576)."""
    parsed_args = {'field_a': ['x', 'y']}

    with patch.object(
        simple_source, '_is_nested_alias_path_only_workaround', return_value=False
    ), patch.object(
        simple_source, '_merge_parsed_list', return_value='merged_result'
    ) as mock_merge:
        simple_source._resolve_parsed_args(parsed_args)

    mock_merge.assert_called_once_with(['x', 'y'], 'field_a')
    assert parsed_args['field_a'] == 'merged_result'


def test_resolve_mixed_args(simple_source):
    """_resolve_parsed_args handles a mix of string and list args."""
    parsed_args = {'name': 'hello', 'items': ['a', 'b']}

    with patch.object(
        simple_source, '_is_nested_alias_path_only_workaround', return_value=False
    ), patch.object(
        simple_source, '_merge_parsed_list', return_value='"merged"'
    ):
        result = simple_source._resolve_parsed_args(parsed_args)

    assert result == []
    assert parsed_args['name'] == 'hello'
    assert parsed_args['items'] == '"merged"'
