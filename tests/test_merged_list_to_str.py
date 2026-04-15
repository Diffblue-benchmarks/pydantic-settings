"""Tests for CliSettingsSource._merged_list_to_str covering uncovered lines."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from pydantic_settings import BaseSettings, CliSettingsSource
from pydantic_settings.exceptions import SettingsError


class SimpleSettings(BaseSettings):
    name: str = 'default'
    value: int = 0


def _make_decode_arg(annotation=None):
    """Create a fake CLI arg with is_no_decode=False."""
    if annotation is not None:
        return SimpleNamespace(is_no_decode=False, field_info=SimpleNamespace(annotation=annotation))
    return SimpleNamespace(is_no_decode=False)


def _make_nodecode_arg():
    """Create a fake CLI arg with is_no_decode=True."""
    return SimpleNamespace(is_no_decode=True)


def test_merged_list_to_str_numeric_item_str_annotation_covers_line_639_and_654():
    # Lines 639, 654: _parser_map has an entry with list[str] annotation so
    # TypeAdapter succeeds, is_num_type_str=True, and float() succeeds → item quoted.
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    source._parser_map['my_field'][None] = _make_decode_arg(annotation=list[str])
    result = source._merged_list_to_str(['1.5'], 'my_field')
    assert '"1.5"' in result


def test_merged_list_to_str_numeric_item_int_annotation_covers_line_654_false_branch():
    # Line 654 (false branch): annotation=list[int] → is_num_type_str=False →
    # numeric item unquoted.
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    source._parser_map['my_field'][None] = _make_decode_arg(annotation=list[int])
    result = source._merged_list_to_str(['1'], 'my_field')
    assert '"1"' not in result
    assert '1' in result


def test_merged_list_to_str_mixing_decode_and_nodecode_raises_line_648():
    # Line 648: first item decode, second item no_decode → SettingsError.
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    source._parser_map['my_field'][0] = _make_decode_arg()
    source._parser_map['my_field'][1] = _make_nodecode_arg()
    with pytest.raises(SettingsError, match='Mixing Decode and NoDecode'):
        source._merged_list_to_str(['a', 'b'], 'my_field')


def test_merged_list_to_str_nodecode_quoted_item_strips_quotes_lines_657_658():
    # Lines 657-658: no_decode mode and item is quoted → quotes are stripped.
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    source._parser_map['my_field'][0] = _make_nodecode_arg()
    result = source._merged_list_to_str(['"hello"'], 'my_field')
    assert result == 'hello'


def test_merged_list_to_str_nodecode_unquoted_item_unchanged():
    # Line 657 branch not taken: no_decode mode but item has no quotes → unchanged.
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    source._parser_map['my_field'][0] = _make_nodecode_arg()
    result = source._merged_list_to_str(['hello'], 'my_field')
    assert result == 'hello'
