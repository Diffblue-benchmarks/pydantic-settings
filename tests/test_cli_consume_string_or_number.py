"""Tests for CliSettingsSource._consume_string_or_number method."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from pydantic_settings import BaseSettings, CliSettingsSource, SettingsError


class TestConsumeStringOrNumberNoneString:
    """Tests for _consume_string_or_number handling of cli_parse_none_str."""

    def test_parse_none_str_converted_to_null_in_list(self):
        """Test that cli_parse_none_str value is converted to 'null' in list context."""

        class Settings(BaseSettings):
            items: list[str | None] = []

        source = CliSettingsSource(Settings, cli_parse_none_str='null')
        merged_list: list[str] = []
        result = source._consume_string_or_number('null', merged_list, list)
        assert 'null' in merged_list
        assert result == ''

    def test_parse_none_str_with_custom_value_converted_to_null(self):
        """Test that custom cli_parse_none_str value is converted to 'null' in JSON."""

        class Settings(BaseSettings):
            items: list[str | None] = []

        source = CliSettingsSource(Settings, cli_parse_none_str='None')
        merged_list: list[str] = []
        result = source._consume_string_or_number('None', merged_list, list)
        assert 'null' in merged_list
        assert result == ''

    def test_parse_none_str_void_converted_to_null(self):
        """Test that 'void' cli_parse_none_str value is converted to 'null' in JSON."""

        class Settings(BaseSettings):
            items: list[str | None] = []

        source = CliSettingsSource(Settings, cli_parse_none_str='void')
        merged_list: list[str] = []
        result = source._consume_string_or_number('void', merged_list, list)
        assert 'null' in merged_list
        assert result == ''

    def test_parse_none_str_converted_in_str_context(self):
        """Test that cli_parse_none_str value is converted to 'null' in str context."""

        class Settings(BaseSettings):
            value: str | None = None

        source = CliSettingsSource(Settings, cli_parse_none_str='NONE')
        merged_list: list[str] = []
        result = source._consume_string_or_number('NONE', merged_list, str)
        assert 'null' in merged_list


class TestConsumeStringOrNumberDictBranch:
    """Tests for _consume_string_or_number handling dict key=value parsing."""

    def test_dict_keyval_parsing_basic(self):
        """Test basic key=value parsing for dict fields."""

        class Settings(BaseSettings):
            data: dict[str, str] = {}

        source = CliSettingsSource(Settings)
        merged_list: list[str] = []
        result = source._consume_string_or_number('foo=bar', merged_list, dict)
        assert '{"foo": "bar"}' in merged_list
        assert result == ''

    def test_dict_keyval_parsing_with_comma(self):
        """Test key=value parsing stops at comma."""

        class Settings(BaseSettings):
            data: dict[str, str] = {}

        source = CliSettingsSource(Settings)
        merged_list: list[str] = []
        result = source._consume_string_or_number('foo=bar,baz=qux', merged_list, dict)
        assert '{"foo": "bar"}' in merged_list
        assert result == ',baz=qux'

    def test_dict_keyval_parsing_with_equals_in_value(self):
        """Test key=value parsing when value contains equals sign."""

        class Settings(BaseSettings):
            data: dict[str, str] = {}

        source = CliSettingsSource(Settings)
        merged_list: list[str] = []
        result = source._consume_string_or_number('key=value=with=equals', merged_list, dict)
        assert '{"key": "value=with=equals"}' in merged_list
        assert result == ''

    def test_dict_keyval_quoted_string_raises_error(self):
        """Test that quoted string spanning key=val raises ValueError."""

        class Settings(BaseSettings):
            data: dict[str, str] = {}

        source = CliSettingsSource(Settings)
        merged_list: list[str] = []
        with pytest.raises(ValueError, match='quoted string'):
            source._consume_string_or_number('"key=value"', merged_list, dict)

    def test_dict_keyval_numeric_value(self):
        """Test key=value parsing with numeric value."""

        class Settings(BaseSettings):
            data: dict[str, str] = {}

        source = CliSettingsSource(Settings)
        merged_list: list[str] = []
        result = source._consume_string_or_number('count=42', merged_list, dict)
        assert '{"count": "42"}' in merged_list
        assert result == ''

    def test_dict_keyval_empty_value(self):
        """Test key=value parsing with empty value."""

        class Settings(BaseSettings):
            data: dict[str, str] = {}

        source = CliSettingsSource(Settings)
        merged_list: list[str] = []
        result = source._consume_string_or_number('empty=', merged_list, dict)
        assert '{"empty": ""}' in merged_list
        assert result == ''

    def test_dict_keyval_special_chars_in_value(self):
        """Test key=value parsing with special characters in value."""

        class Settings(BaseSettings):
            data: dict[str, str] = {}

        source = CliSettingsSource(Settings)
        merged_list: list[str] = []
        result = source._consume_string_or_number('path=/usr/local/bin', merged_list, dict)
        assert '{"path": "/usr/local/bin"}' in merged_list
        assert result == ''
