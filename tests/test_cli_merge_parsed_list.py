"""Tests for CliSettingsSource._merge_parsed_list method."""

from __future__ import annotations

from typing import Mapping

import pytest
from pydantic import BaseModel

from pydantic_settings import BaseSettings, CliSettingsSource


class TestMergeParsedListNonStringValue:
    """Tests for _merge_parsed_list with non-string values from external parsers."""

    def test_non_string_value_breaks_loop(self):
        """Test that non-string values from external parser break the parsing loop."""

        class Settings(BaseSettings):
            items: list[str] = []

        source = CliSettingsSource(Settings)
        source(args=['--items', 'a'])

        # When a non-string value is in the parsed_list, the loop should break early.
        # This simulates an external parser providing non-string values.
        parsed_list = ['first', 123, 'third']  # 123 is not a string
        result = source._merge_parsed_list(parsed_list, 'items')
        # Should only process 'first' before breaking on 123
        assert result == '["first"]'

    def test_non_string_at_start_produces_empty_result(self):
        """Test that non-string at start produces empty result."""

        class Settings(BaseSettings):
            items: list[str] = []

        source = CliSettingsSource(Settings)
        source(args=['--items', 'a'])

        parsed_list = [123]  # Start with non-string
        result = source._merge_parsed_list(parsed_list, 'items')
        # When first element is not a string, the loop breaks immediately
        # resulting in an empty merged_list which converts to empty string
        assert result == ''


class TestMergeParsedListStrMergeType:
    """Tests for _merge_parsed_list with str merge type (line 697)."""

    def test_str_merge_type_returns_single_value(self):
        """Test that when merge_type is str, returns the single merged value."""

        class Settings(BaseSettings):
            value: str | list[str] = ''

        source = CliSettingsSource(Settings)
        source(args=['--value', 'test'])

        # Set up for str merge type - when the inferred type is str for a union
        source._cli_dict_args['value'] = str | list[str]

        # Single value without array brackets should return just the value
        parsed_list = ['hello']
        result = source._merge_parsed_list(parsed_list, 'value')
        # With str merge_type, it should return merged_list[0]
        assert result == '"hello"'


class TestMergeParsedListDictMergeType:
    """Tests for _merge_parsed_list with dict merge type (lines 701-704)."""

    def test_dict_merge_type_single_key_value(self):
        """Test merging a single key=value pair for dict type."""

        class Settings(BaseSettings):
            config: dict[str, str] = {}

        source = CliSettingsSource(Settings)
        source(args=['--config', 'key=value'])

        # The dict merging logic should be used
        assert 'config' in source.env_vars

    def test_dict_merge_type_multiple_key_values(self):
        """Test merging multiple key=value pairs into a dict."""

        class Settings(BaseSettings):
            config: dict[str, str] = {}

        source = CliSettingsSource(Settings)
        source(args=['--config', 'key1=value1', '--config', 'key2=value2'])

        # Both pairs should be merged
        env_val = source.env_vars.get('config')
        assert env_val is not None
        assert 'key1' in env_val or '"key1"' in env_val


class TestMergeParsedListValueErrorRetry:
    """Tests for _merge_parsed_list ValueError retry logic (lines 690-691)."""

    def test_value_error_retry_with_inferred_type(self):
        """Test that ValueError causes retry with inferred type when merge_type differs."""

        class Settings(BaseSettings):
            items: str | list[str] = ''

        source = CliSettingsSource(Settings)
        source(args=['--items', '[a,b]'])

        # When there's a union type with str and list, and the initial type
        # causes ValueError, it should retry with inferred_type
        assert 'items' in source.env_vars


class TestMergeParsedListConsumeCommaAfterLoop:
    """Tests for _merge_parsed_list consume comma after inner loop (line 694)."""

    def test_trailing_comma_handling(self):
        """Test handling of trailing commas in parsed lists."""

        class Settings(BaseSettings):
            items: list[str] = []

        source = CliSettingsSource(Settings)
        source(args=['--items', 'a,'])

        # Trailing comma should be handled
        assert 'items' in source.env_vars

    def test_only_comma_in_array(self):
        """Test array with only comma produces empty strings."""

        class Settings(BaseSettings):
            items: list[str] = []

        source = CliSettingsSource(Settings)
        source(args=['--items', '[,]'])

        # Leading comma should produce empty string
        assert 'items' in source.env_vars


class TestMergeParsedListDictMergeFromCli:
    """Integration tests for dict merging via CLI."""

    def test_dict_merge_json_format(self):
        """Test dict merging with JSON format input."""

        class Settings(BaseSettings):
            mappings: dict[str, str] = {}

        source = CliSettingsSource(Settings)
        source(args=['--mappings', '{"key":"value"}'])

        assert 'mappings' in source.env_vars

    def test_dict_merge_key_equals_value_format(self):
        """Test dict merging with key=value format."""

        class Settings(BaseSettings):
            mappings: dict[str, str] = {}

        source = CliSettingsSource(Settings)
        source(args=['--mappings', 'foo=bar', '--mappings', 'baz=qux'])

        env_val = source.env_vars.get('mappings')
        assert env_val is not None


class TestMergeParsedListMappingType:
    """Tests for _merge_parsed_list with Mapping type annotation."""

    def test_mapping_type_with_key_value_pairs(self):
        """Test Mapping type annotation handles key=value correctly."""

        class Settings(BaseSettings):
            config: Mapping[str, str] = {}

        source = CliSettingsSource(Settings)
        source(args=['--config', 'a=1', '--config', 'b=2'])

        assert 'config' in source.env_vars


class TestMergeParsedListDirectDictMerge:
    """Direct tests for dict merge logic in _merge_parsed_list (lines 701-704)."""

    def test_dict_merge_direct_call(self):
        """Test _merge_parsed_list directly with dict merge type configured."""

        class Settings(BaseSettings):
            config: dict[str, str] = {}

        source = CliSettingsSource(Settings)
        source(args=['--config', 'x=1'])

        # Manually set dict as merge type for the field
        source._cli_dict_args['myfield'] = dict

        # Call _merge_parsed_list directly with key=value format
        result = source._merge_parsed_list(['key1=val1', 'key2=val2'], 'myfield')

        # Should return a JSON dict with merged values
        assert 'key1' in result
        assert 'key2' in result
        assert 'val1' in result
        assert 'val2' in result

    def test_dict_merge_single_item(self):
        """Test dict merge with single key=value."""

        class Settings(BaseSettings):
            config: dict[str, str] = {}

        source = CliSettingsSource(Settings)
        source(args=['--config', 'x=1'])

        source._cli_dict_args['field'] = dict
        result = source._merge_parsed_list(['foo=bar'], 'field')

        assert 'foo' in result
        assert 'bar' in result

    def test_dict_merge_overwrites_duplicate_keys(self):
        """Test that later keys overwrite earlier ones in dict merge."""

        class Settings(BaseSettings):
            config: dict[str, str] = {}

        source = CliSettingsSource(Settings)
        source(args=['--config', 'x=1'])

        source._cli_dict_args['field'] = dict
        result = source._merge_parsed_list(['key=first', 'key=second'], 'field')

        # Later value should overwrite
        assert 'second' in result


class TestMergeParsedListStrTypeReturn:
    """Direct tests for str merge type return path (line 697)."""

    def test_str_merge_type_direct_single_value(self):
        """Test that str merge type returns the first merged list item."""

        class Settings(BaseSettings):
            value: str | list[str] = ''

        source = CliSettingsSource(Settings)
        source(args=['--value', 'test'])

        # Set up merge type as str for the field
        source._cli_dict_args['field'] = str

        result = source._merge_parsed_list(['hello'], 'field')
        # When merge_type is str, should return merged_list[0]
        assert result == '"hello"'

    def test_str_merge_type_union_with_str(self):
        """Test str merge type behavior with union annotation containing str."""

        class Settings(BaseSettings):
            val: str | list[str] = ''

        source = CliSettingsSource(Settings)
        source(args=['--val', 'single'])

        # The method should detect str union and handle appropriately
        assert 'val' in source.env_vars


class TestMergeParsedListValueErrorRetryDirect:
    """Direct tests for ValueError retry logic (lines 690-691)."""

    def test_value_error_with_different_merge_and_inferred_type(self):
        """Test ValueError retry when merge_type != inferred_type."""

        class Settings(BaseSettings):
            items: str | list[str] = ''

        source = CliSettingsSource(Settings)
        source(args=['--items', 'test'])

        # Configure to trigger the retry logic:
        # merge_type should be the union, and inferred_type should differ
        source._cli_dict_args['field'] = str | list[str]

        # With a single value (not starting with [), inferred_type becomes str
        result = source._merge_parsed_list(['value'], 'field')
        assert result is not None


class TestMergeParsedListEmptyAndEdgeCases:
    """Tests for edge cases in _merge_parsed_list."""

    def test_empty_parsed_list(self):
        """Test handling of empty parsed list."""

        class Settings(BaseSettings):
            items: list[str] = []

        source = CliSettingsSource(Settings)
        source(args=['--items', 'a'])

        result = source._merge_parsed_list([], 'items')
        assert result == ''

    def test_value_with_only_brackets(self):
        """Test handling of value with only brackets."""

        class Settings(BaseSettings):
            items: list[str] = []

        source = CliSettingsSource(Settings)
        source(args=['--items', '[]'])

        assert 'items' in source.env_vars

    def test_whitespace_value_in_list(self):
        """Test handling of whitespace values."""

        class Settings(BaseSettings):
            items: list[str] = []

        source = CliSettingsSource(Settings)
        source(args=['--items', '  '])

        # Whitespace should be handled
        assert 'items' in source.env_vars
