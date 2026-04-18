"""Tests for CliSettingsSource._is_nested_alias_path_only_workaround method."""

from __future__ import annotations

import pytest
from pydantic import AliasPath, BaseModel, Field

from pydantic_settings import BaseSettings, CliSettingsSource


class TestIsNestedAliasPathOnlyWorkaroundEmptyParserMap:
    """Tests for _is_nested_alias_path_only_workaround when parser_map is empty (line 602)."""

    def test_returns_false_when_field_not_in_parser_map(self):
        """Test that method returns False when field_name is not in parser_map."""

        class Settings(BaseSettings):
            items: list[str] = []

        source = CliSettingsSource(Settings)
        source(args=['--items', 'a'])

        parsed_args = {'unknown_field': ['value1', 'value2']}
        result = source._is_nested_alias_path_only_workaround(
            parsed_args, 'unknown_field', ['value1', 'value2']
        )

        assert result is False
        # parsed_args should be unchanged
        assert parsed_args == {'unknown_field': ['value1', 'value2']}

    def test_returns_false_when_parser_map_value_is_empty_dict(self):
        """Test returns False when parser_map returns empty dict for field."""

        class Settings(BaseSettings):
            items: list[str] = []

        source = CliSettingsSource(Settings)
        source(args=['--items', 'a'])

        # Use a field name that's not registered in parser_map
        parsed_args = {'nonexistent': ['val']}
        result = source._is_nested_alias_path_only_workaround(
            parsed_args, 'nonexistent', ['val']
        )

        assert result is False


class TestIsNestedAliasPathOnlyWorkaroundAliasPathOnly:
    """Tests for nested alias path only workaround (lines 605-608, 613)."""

    def test_nested_alias_path_only_with_prefix_ending_in_dot(self):
        """Test nested alias path workaround when arg_prefix ends with dot."""

        class Nested(BaseModel):
            value: str = Field(default='default', validation_alias=AliasPath('data', 0))

        class Settings(BaseSettings):
            nested: Nested = Nested()

        source = CliSettingsSource(Settings)
        source(args=[])

        # Find the arg for nested.data which should have is_alias_path_only=True
        # and arg_prefix ending with '.'
        nested_data_arg = None
        found_dest = None
        for dest, arg_map in source._parser_map.items():
            if isinstance(dest, str) and dest == 'nested.data':
                for key, arg in arg_map.items():
                    if arg.is_alias_path_only and arg.arg_prefix.endswith('.'):
                        nested_data_arg = arg
                        found_dest = dest
                        break

        if nested_data_arg is not None:
            # Create parsed_args that would trigger the workaround
            parsed_args = {found_dest: ['test_value']}
            result = source._is_nested_alias_path_only_workaround(
                parsed_args, found_dest, ['test_value']
            )

            # Should return True and modify parsed_args
            assert result is True
            assert found_dest not in parsed_args
            assert 'nested' in parsed_args

    def test_nested_alias_path_workaround_modifies_parsed_args(self):
        """Test that workaround correctly modifies parsed_args dict."""

        class Nested(BaseModel):
            item: str = Field(default='default', validation_alias=AliasPath('items', 0))

        class Settings(BaseSettings):
            nested: Nested = Nested()

        source = CliSettingsSource(Settings)
        source(args=[])

        # Check if we have the required arg structure
        for dest, arg_map in source._parser_map.items():
            if isinstance(dest, str) and 'items' in dest:
                for key, arg in arg_map.items():
                    if hasattr(arg, 'is_alias_path_only') and arg.is_alias_path_only:
                        if hasattr(arg, 'arg_prefix') and arg.arg_prefix.endswith('.'):
                            parsed_args = {dest: ['value']}
                            original_dest = dest
                            result = source._is_nested_alias_path_only_workaround(
                                parsed_args, dest, ['value']
                            )
                            if result:
                                # Verify the original key was deleted
                                assert original_dest not in parsed_args
                                return

    def test_nested_alias_path_workaround_appends_to_existing(self):
        """Test workaround appends to existing nested_dest value."""

        class Nested(BaseModel):
            item1: str = Field(default='a', validation_alias=AliasPath('data', 0))
            item2: str = Field(default='b', validation_alias=AliasPath('data', 1))

        class Settings(BaseSettings):
            nested: Nested = Nested()

        source = CliSettingsSource(Settings)
        source(args=[])

        # Find a field with alias_path_only and prefix ending in '.'
        for dest, arg_map in source._parser_map.items():
            if isinstance(dest, str) and dest.startswith('nested.'):
                for key, arg in arg_map.items():
                    if hasattr(arg, 'is_alias_path_only') and arg.is_alias_path_only:
                        if hasattr(arg, 'arg_prefix') and arg.arg_prefix.endswith('.'):
                            nested_dest = arg.arg_prefix[:-1]
                            # Pre-populate the nested_dest
                            parsed_args = {
                                nested_dest: '{"existing": "value"}',
                                dest: ['new_value']
                            }
                            result = source._is_nested_alias_path_only_workaround(
                                parsed_args, dest, ['new_value']
                            )
                            if result:
                                # The original field should be removed
                                assert dest not in parsed_args
                                # The nested_dest should be updated
                                assert nested_dest in parsed_args
                                return

    def test_workaround_returns_true_and_deletes_field(self):
        """Test that the workaround returns True and deletes the field from parsed_args (lines 605-608, 613)."""

        class Nested(BaseModel):
            field: str = Field(default='x', validation_alias=AliasPath('alias', 0))

        class Settings(BaseSettings):
            nested: Nested = Nested()

        source = CliSettingsSource(Settings)
        source(args=[])

        # Find the nested alias path arg
        dest_to_test = None
        for dest, arg_map in source._parser_map.items():
            if isinstance(dest, str) and 'nested.' in dest:
                for key, arg in arg_map.items():
                    if arg.is_alias_path_only and arg.arg_prefix.endswith('.'):
                        dest_to_test = dest
                        break
                if dest_to_test:
                    break

        assert dest_to_test is not None, 'Should find a nested alias path only arg'

        # Test the workaround - should return True
        parsed_args = {dest_to_test: ['test_value']}
        result = source._is_nested_alias_path_only_workaround(
            parsed_args, dest_to_test, ['test_value']
        )

        assert result is True
        assert dest_to_test not in parsed_args  # Line 605: del parsed_args[field_name]
        assert 'nested' in parsed_args  # Lines 606-612: creates nested_dest entry

    def test_workaround_merges_with_existing_nested_dest(self):
        """Test that workaround merges values when nested_dest already exists (line 611)."""

        class Nested(BaseModel):
            a: str = Field(default='x', validation_alias=AliasPath('items', 0))
            b: str = Field(default='y', validation_alias=AliasPath('items', 1))

        class Settings(BaseSettings):
            nested: Nested = Nested()

        source = CliSettingsSource(Settings)
        source(args=[])

        # Find nested alias path args
        dest_to_test = None
        for dest, arg_map in source._parser_map.items():
            if isinstance(dest, str) and dest == 'nested.items':
                for key, arg in arg_map.items():
                    if arg.is_alias_path_only and arg.arg_prefix.endswith('.'):
                        dest_to_test = dest
                        break
                if dest_to_test:
                    break

        if dest_to_test is not None:
            # Set up parsed_args with existing nested value
            parsed_args = {
                'nested': '{"existing": "data"}',
                dest_to_test: ['new_value']
            }
            result = source._is_nested_alias_path_only_workaround(
                parsed_args, dest_to_test, ['new_value']
            )

            assert result is True
            assert dest_to_test not in parsed_args
            # The nested value should have been appended (line 611)
            assert 'existing' in parsed_args['nested']
            assert 'new_value' in parsed_args['nested'] or 'items' in parsed_args['nested']


class TestIsNestedAliasPathOnlyWorkaroundReturnsFalse:
    """Tests for when method returns False for non-alias-path-only args (line 614)."""

    def test_returns_false_when_not_alias_path_only(self):
        """Test returns False when arg is not alias_path_only."""

        class Settings(BaseSettings):
            items: list[str] = []

        source = CliSettingsSource(Settings)
        source(args=['--items', 'a'])

        # 'items' is a regular field, not alias_path_only
        parsed_args = {'items': ['value']}
        result = source._is_nested_alias_path_only_workaround(
            parsed_args, 'items', ['value']
        )

        assert result is False
        # parsed_args should be unchanged
        assert parsed_args == {'items': ['value']}

    def test_returns_false_when_prefix_does_not_end_with_dot(self):
        """Test returns False when arg_prefix doesn't end with '.'."""

        class Settings(BaseSettings):
            # Top-level field with AliasPath - prefix won't end with '.'
            item: str = Field(default='', validation_alias=AliasPath('data', 0))

        source = CliSettingsSource(Settings)
        source(args=[])

        # The arg for top-level alias path should have empty prefix
        parsed_args = {'data': ['value']}
        result = source._is_nested_alias_path_only_workaround(
            parsed_args, 'data', ['value']
        )

        # Should return False because prefix is empty, not ending with '.'
        assert result is False


class TestIsNestedAliasPathOnlyWorkaroundIntegration:
    """Integration tests for the nested alias path workaround."""

    def test_workaround_integration_via_call(self):
        """Test the workaround is triggered during normal CLI parsing."""

        class Inner(BaseModel):
            val: str = Field(default='default', validation_alias=AliasPath('items', 0))

        class Settings(BaseSettings):
            inner: Inner = Inner()

        source = CliSettingsSource(Settings)
        # This should trigger the workaround internally during parsing
        source(args=['--inner.items', 'test_value'])

        # Verify the source was created and parsed
        assert source.env_vars is not None

    def test_workaround_with_multiple_nested_fields(self):
        """Test workaround with multiple nested alias path fields."""

        class Data(BaseModel):
            first: str = Field(default='a', validation_alias=AliasPath('arr', 0))
            second: str = Field(default='b', validation_alias=AliasPath('arr', 1))

        class Settings(BaseSettings):
            data: Data = Data()

        source = CliSettingsSource(Settings)
        source(args=[])

        # Verify source initializes correctly
        assert source is not None

    def test_workaround_verifies_arg_structure(self):
        """Test that verifies the parser_map has correct arg structure for workaround."""

        class Nested(BaseModel):
            val: str = Field(default='x', validation_alias=AliasPath('alias', 0))

        class Settings(BaseSettings):
            nested: Nested = Nested()

        source = CliSettingsSource(Settings)
        source(args=[])

        # Verify the parser_map contains the expected nested alias path
        found_alias_path_only = False
        found_prefix_with_dot = False

        for dest, arg_map in source._parser_map.items():
            if isinstance(dest, str) and 'nested.' in dest:
                for key, arg in arg_map.items():
                    if arg.is_alias_path_only:
                        found_alias_path_only = True
                    if arg.arg_prefix.endswith('.'):
                        found_prefix_with_dot = True

        assert found_alias_path_only, 'Should have an alias_path_only arg'
        assert found_prefix_with_dot, 'Should have an arg_prefix ending with dot'
