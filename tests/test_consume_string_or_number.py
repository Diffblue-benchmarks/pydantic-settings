"""Tests for CliSettingsSource._consume_string_or_number method."""

import json

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


# ---- Line 741: Mismatched quotes ----

def test_mismatched_quotes_raises_error(cli_source):
    merged = []
    with pytest.raises(SettingsError, match='Mismatched quotes'):
        cli_source._consume_string_or_number('"hello', merged, list)


def test_mismatched_quotes_single_quote_char(cli_source):
    merged = []
    with pytest.raises(SettingsError, match='Mismatched quotes'):
        cli_source._consume_string_or_number('"unclosed string value', merged, list)


# ---- Line 748: val_string == cli_parse_none_str => 'null' ----

def test_none_str_converted_to_null_for_list(cli_source):
    merged = []
    assert cli_source.cli_parse_none_str == 'null'
    cli_source._consume_string_or_number('null,rest', merged, list)
    assert merged == ['null']


def test_none_str_converted_to_null_for_str(cli_source):
    merged = []
    cli_source._consume_string_or_number('null', merged, str)
    assert merged == ['null']


def test_custom_none_str_converted_to_null(cli_source):
    cli_source.cli_parse_none_str = 'None'
    merged = []
    cli_source._consume_string_or_number('None,rest', merged, list)
    assert merged == ['null']


# ---- Line 750: non-keyword string gets quoted ----

def test_plain_string_gets_quoted_for_list(cli_source):
    merged = []
    cli_source._consume_string_or_number('hello,rest', merged, list)
    assert merged == ['"hello"']


def test_plain_string_gets_quoted_for_str(cli_source):
    merged = []
    cli_source._consume_string_or_number('hello', merged, str)
    assert merged == ['"hello"']


def test_true_not_quoted(cli_source):
    merged = []
    cli_source._consume_string_or_number('true,rest', merged, list)
    assert merged == ['true']


def test_false_not_quoted(cli_source):
    merged = []
    cli_source._consume_string_or_number('false,rest', merged, list)
    assert merged == ['false']


def test_null_not_quoted(cli_source):
    merged = []
    cli_source._consume_string_or_number('null,rest', merged, list)
    assert merged == ['null']


def test_already_quoted_not_double_quoted(cli_source):
    merged = []
    cli_source._consume_string_or_number('"already quoted",rest', merged, list)
    assert merged == ['"already quoted"']


def test_number_not_quoted(cli_source):
    merged = []
    cli_source._consume_string_or_number('42,rest', merged, list)
    assert merged == ['42']


def test_float_not_quoted(cli_source):
    merged = []
    cli_source._consume_string_or_number('3.14,rest', merged, list)
    assert merged == ['3.14']


# ---- Lines 753-757: dict merge_type (else branch) ----

def test_dict_key_val_parsed(cli_source):
    merged = []
    cli_source._consume_string_or_number('key=value,rest', merged, None)
    assert merged == [json.dumps({'key': 'value'})]


def test_dict_key_val_no_remaining(cli_source):
    merged = []
    remainder = cli_source._consume_string_or_number('mykey=myval', merged, None)
    assert merged == [json.dumps({'mykey': 'myval'})]
    assert remainder == ''


def test_dict_key_val_with_remainder(cli_source):
    merged = []
    remainder = cli_source._consume_string_or_number('a=b,c=d', merged, None)
    assert merged == [json.dumps({'a': 'b'})]
    assert remainder == ',c=d'


def test_dict_quoted_key_val(cli_source):
    merged = []
    cli_source._consume_string_or_number('"key"="value",rest', merged, None)
    assert merged == [json.dumps({'key': 'value'})]


def test_dict_quoted_string_raises_error(cli_source):
    merged = []
    with pytest.raises(ValueError, match='Dictionary key=val parameter is a quoted string'):
        cli_source._consume_string_or_number('"key=value",rest', merged, None)


# ---- Return value tests ----

def test_returns_remaining_string_after_comma(cli_source):
    merged = []
    remainder = cli_source._consume_string_or_number('hello,world', merged, list)
    assert remainder == ',world'


def test_returns_empty_for_str_merge_type(cli_source):
    merged = []
    remainder = cli_source._consume_string_or_number('hello', merged, str)
    assert remainder == ''
