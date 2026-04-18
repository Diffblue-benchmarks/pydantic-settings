"""Tests for CliSettingsSource._merge_parsed_list method."""

from typing import Dict, Union

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


# ---- Line 672: non-string value in parsed_list triggers break ----

def test_non_string_val_breaks_early(cli_source):
    """When parsed_list contains a non-string (from external parser), loop breaks."""
    result = cli_source._merge_parsed_list([123], 'name')
    # merge_type defaults to list, empty merged_list => _merged_list_to_str returns empty
    assert isinstance(result, str)


def test_non_string_val_after_string_breaks(cli_source):
    """Non-string element after valid strings causes early break."""
    result = cli_source._merge_parsed_list(['"hello"', 456], 'name')
    assert isinstance(result, str)
    assert 'hello' in result


# ---- Lines 687-689, 705-706: ValueError re-raised when merge_type is inferred_type ----

def test_dict_merge_type_bad_value_raises_settings_error(cli_source):
    """When merge_type==inferred_type==dict and value has no '=', SettingsError is raised."""
    cli_source._cli_dict_args['test_field'] = dict
    with pytest.raises(SettingsError, match='Parsing error encountered for test_field'):
        cli_source._merge_parsed_list(['badvalue'], 'test_field')


# ---- Lines 690-691: ValueError retry with inferred_type ----

def test_union_dict_str_retries_with_inferred_str(cli_source):
    """When merge_type is a Union with dict and non-dict, retry with inferred_type=str."""
    cli_source._cli_dict_args['test_field'] = Union[Dict[str, str], str]
    result = cli_source._merge_parsed_list(['hello'], 'test_field')
    # inferred_type=str for single element not starting with '[', so returns merged_list[0]
    assert result == '"hello"'


def test_union_dict_list_retries_with_inferred_list(cli_source):
    """When merge_type is a Union with dict and list, retry with inferred_type=list for multi-element."""
    cli_source._cli_dict_args['test_field'] = Union[Dict[str, str], str]
    result = cli_source._merge_parsed_list(['[hello,world]'], 'test_field')
    # inferred_type=list for element starting with '['
    assert isinstance(result, str)
    assert 'hello' in result
    assert 'world' in result


# ---- Line 694: consume comma when is_last_consumed_a_value is False ----

def test_empty_bracket_content_consumes_comma(cli_source):
    """Empty brackets '[]' cause is_last_consumed_a_value=False path after while loop."""
    result = cli_source._merge_parsed_list(['[]'], 'name')
    assert isinstance(result, str)


# ---- Line 697: merge_type is str returns merged_list[0] ----

def test_merge_type_str_returns_first_element(cli_source):
    """When merge_type is str, returns merged_list[0] directly."""
    cli_source._cli_dict_args['test_field'] = Union[Dict[str, str], str]
    result = cli_source._merge_parsed_list(['somevalue'], 'test_field')
    # inferred_type=str (single element, not starting with '[')
    # After retry, merge_type becomes str, so returns merged_list[0]
    assert result == '"somevalue"'


# ---- Lines 705-706: general exception wrapping ----

def test_general_exception_wrapped_in_settings_error(cli_source):
    """Any exception in _merge_parsed_list is wrapped in SettingsError."""
    cli_source._cli_dict_args['test_field'] = dict
    with pytest.raises(SettingsError, match='Parsing error encountered for test_field'):
        cli_source._merge_parsed_list(['no_equals_sign'], 'test_field')


def test_multiple_bad_dict_values_raises_settings_error(cli_source):
    """Dict merge with invalid value format raises SettingsError."""
    cli_source._cli_dict_args['test_field'] = dict
    with pytest.raises(SettingsError, match='Parsing error encountered for test_field'):
        cli_source._merge_parsed_list(['value_without_equals'], 'test_field')
