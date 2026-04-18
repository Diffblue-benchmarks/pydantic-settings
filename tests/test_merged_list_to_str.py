"""Tests for CliSettingsSource._merged_list_to_str method."""

from unittest.mock import MagicMock

import pytest

from pydantic_settings import BaseSettings, CliSettingsSource
from pydantic_settings.exceptions import SettingsError


class SimpleSettings(BaseSettings):
    name: str = 'default'
    count: int = 0

    model_config = {'env_file': None}


@pytest.fixture
def cli_source():
    return CliSettingsSource(SimpleSettings, cli_parse_args=[])


def _make_cli_arg_mock(*, is_no_decode=False, annotation=str):
    mock = MagicMock()
    mock.is_no_decode = is_no_decode
    mock.field_info.annotation = annotation
    return mock


def test_merged_list_to_str_exception_in_type_adapter(cli_source):
    """Lines 640-641: When field_name is not in _parser_map, exception is caught."""
    result = cli_source._merged_list_to_str(['hello', 'world'], 'nonexistent_field')
    assert result == '[hello,world]'


def test_merged_list_to_str_numeric_string_quoted_for_str_list(cli_source):
    """Line 654: Numeric string gets quoted when annotation is list[str]."""
    mock_arg = _make_cli_arg_mock(is_no_decode=False, annotation=list[str])
    cli_source._parser_map['test_field'] = {0: mock_arg}

    result = cli_source._merged_list_to_str(['42'], 'test_field')
    assert result == '["42"]'


def test_merged_list_to_str_numeric_string_unquoted_for_int_list(cli_source):
    """Line 654: Numeric string stays unquoted when annotation is list[int]."""
    mock_arg = _make_cli_arg_mock(is_no_decode=False, annotation=list[int])
    cli_source._parser_map['test_field'] = {0: mock_arg}

    result = cli_source._merged_list_to_str(['42'], 'test_field')
    assert result == '[42]'


def test_merged_list_to_str_mixing_decode_and_no_decode_raises(cli_source):
    """Line 648: Mixing Decode and NoDecode across fields raises SettingsError."""
    decode_arg = _make_cli_arg_mock(is_no_decode=False, annotation=str)
    no_decode_arg = _make_cli_arg_mock(is_no_decode=True, annotation=str)
    cli_source._parser_map['mixed_field'] = {0: decode_arg, 1: no_decode_arg}

    with pytest.raises(SettingsError, match='Mixing Decode and NoDecode'):
        cli_source._merged_list_to_str(['a', 'b'], 'mixed_field')


def test_merged_list_to_str_no_decode_strips_quotes(cli_source):
    """Lines 657-658: NoDecode path strips surrounding quotes."""
    no_decode_arg = _make_cli_arg_mock(is_no_decode=True, annotation=str)
    cli_source._parser_map['nodecode_field'] = {0: no_decode_arg}

    result = cli_source._merged_list_to_str(['"hello"'], 'nodecode_field')
    assert result == 'hello'


def test_merged_list_to_str_no_decode_unquoted_passthrough(cli_source):
    """NoDecode path with unquoted string passes through unchanged."""
    no_decode_arg = _make_cli_arg_mock(is_no_decode=True, annotation=str)
    cli_source._parser_map['nodecode_field'] = {0: no_decode_arg}

    result = cli_source._merged_list_to_str(['plain'], 'nodecode_field')
    assert result == 'plain'
