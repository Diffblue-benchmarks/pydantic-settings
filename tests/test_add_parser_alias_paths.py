"""Tests for CliSettingsSource._add_parser_alias_paths method."""

from typing import Optional

import pytest

from pydantic import AliasChoices, AliasPath, BaseModel, Field

from pydantic_settings import BaseSettings, CliSettingsSource


# ---- Models with AliasPath fields ----


class SettingsWithAliasPathInt(BaseSettings):
    """Model with AliasPath using integer index (list-type alias path)."""

    my_field: str = Field(default='default', validation_alias=AliasPath('data', 0))

    model_config = {'env_file': None}


class SettingsWithAliasPathStr(BaseSettings):
    """Model with AliasPath using string key (dict-type alias path, index=None)."""

    my_field: str = Field(default='default', validation_alias=AliasPath('data', 'key'))

    model_config = {'env_file': None}


class SettingsWithAliasPathSingle(BaseSettings):
    """Model with AliasPath with only one path element (dict-type, index=None)."""

    my_field: str = Field(default='default', validation_alias=AliasPath('info'))

    model_config = {'env_file': None}


class SettingsWithMultipleAliasPaths(BaseSettings):
    """Model with multiple AliasPath fields via AliasChoices."""

    my_field: str = Field(
        default='default',
        validation_alias=AliasChoices(AliasPath('data', 0), AliasPath('backup', 'key')),
    )

    model_config = {'env_file': None}


class NestedModelWithAlias(BaseModel):
    value: str = Field(default='nested_default', validation_alias=AliasPath('nested_data', 0))


class SettingsWithNestedAliasPath(BaseSettings):
    """Model with nested model that has AliasPath fields."""

    sub: NestedModelWithAlias = NestedModelWithAlias()

    model_config = {'env_file': None}


# ---- Tests ----


class TestAddParserAliasPathsIntIndex:
    """Tests for alias paths with integer index (list-type alias paths)."""

    def test_alias_path_int_index_source_init(self):
        """Creating a source with AliasPath(int index) should succeed and register the arg."""
        source = CliSettingsSource(SettingsWithAliasPathInt, cli_parse_args=[])
        # The data arg should NOT be in _cli_dict_args since index is an int (not None)
        assert 'data' not in source._cli_dict_args

    def test_alias_path_int_index_in_parser_map(self):
        """AliasPath with int index should be registered in the parser map."""
        source = CliSettingsSource(SettingsWithAliasPathInt, cli_parse_args=[])
        assert 'data' in source._parser_map

    def test_alias_path_int_index_parse_value(self):
        """Parsing a value through an alias path with int index should work."""
        source = CliSettingsSource(SettingsWithAliasPathInt, cli_parse_args=['--data', 'hello'])
        result = source()
        assert 'data' in result

    def test_alias_path_int_index_creates_settings(self):
        """AliasPath with int index should allow creating settings from CLI."""
        settings = SettingsWithAliasPathInt(_cli_parse_args=['--data', 'hello'])
        assert settings.my_field == 'hello'

    def test_alias_path_int_index_multiple_values(self):
        """Alias path with int index can receive multiple appended values."""
        settings = SettingsWithAliasPathInt(_cli_parse_args=['--data', 'first', '--data', 'second'])
        assert settings.my_field == 'first'


class TestAddParserAliasPathsDictIndex:
    """Tests for alias paths with None index (dict-type alias paths)."""

    def test_alias_path_str_key_registers_dict_arg(self):
        """AliasPath with string key should register in _cli_dict_args."""
        source = CliSettingsSource(SettingsWithAliasPathStr, cli_parse_args=[])
        assert 'data' in source._cli_dict_args
        assert source._cli_dict_args['data'] is dict

    def test_alias_path_str_key_in_parser_map(self):
        """AliasPath with string key should be in parser map."""
        source = CliSettingsSource(SettingsWithAliasPathStr, cli_parse_args=[])
        assert 'data' in source._parser_map

    def test_alias_path_str_key_parse_value(self):
        """Parsing a value through dict-type alias path should work."""
        source = CliSettingsSource(SettingsWithAliasPathStr, cli_parse_args=['--data', 'key=hello'])
        result = source()
        assert 'data' in result

    def test_alias_path_str_key_creates_settings(self):
        """AliasPath with string key should allow creating settings from CLI."""
        settings = SettingsWithAliasPathStr(_cli_parse_args=['--data', 'key=hello'])
        assert settings.my_field == 'hello'

    def test_alias_path_single_element_registers_dict_arg(self):
        """AliasPath with single element should register in _cli_dict_args (index=None)."""
        source = CliSettingsSource(SettingsWithAliasPathSingle, cli_parse_args=[])
        # Single-element AliasPath: the field name IS the first path element
        # When AliasPath has only one element, _get_alias_names returns it as alias_path_only=True
        # but alias_path_args gets name with index=None
        assert 'info' in source._parser_map


class TestAddParserAliasPathsMultiple:
    """Tests for multiple alias paths via AliasChoices."""

    def test_multiple_alias_paths_both_registered(self):
        """Multiple AliasPath entries via AliasChoices should all be registered."""
        source = CliSettingsSource(SettingsWithMultipleAliasPaths, cli_parse_args=[])
        assert 'data' in source._parser_map
        assert 'backup' in source._parser_map

    def test_multiple_alias_paths_dict_types(self):
        """AliasPath with string key should be dict arg, int index should not."""
        source = CliSettingsSource(SettingsWithMultipleAliasPaths, cli_parse_args=[])
        # 'data' has int index 0 -> not in _cli_dict_args
        assert 'data' not in source._cli_dict_args
        # 'backup' has string key 'key' -> index is None -> in _cli_dict_args
        assert 'backup' in source._cli_dict_args

    def test_multiple_alias_paths_parse_first(self):
        """Parsing through first alias path should work."""
        settings = SettingsWithMultipleAliasPaths(_cli_parse_args=['--data', 'hello'])
        assert settings.my_field == 'hello'

    def test_multiple_alias_paths_parse_second(self):
        """Parsing through second alias path (dict-type) should work."""
        settings = SettingsWithMultipleAliasPaths(_cli_parse_args=['--backup', 'key=hello'])
        assert settings.my_field == 'hello'


class TestAddParserAliasPathsNested:
    """Tests for alias paths in nested models."""

    def test_nested_alias_path_source_init(self):
        """Creating a source with nested model having AliasPath should succeed."""
        source = CliSettingsSource(SettingsWithNestedAliasPath, cli_parse_args=[])
        assert 'sub.nested_data' in source._parser_map

    def test_nested_alias_path_parse(self):
        """Parsing values for nested alias paths should work."""
        settings = SettingsWithNestedAliasPath(
            _cli_parse_args=['--sub.nested_data', 'nested_hello']
        )
        assert settings.sub.value == 'nested_hello'


class TestAddParserAliasPathsWithPrefix:
    """Tests for alias paths with CLI prefix."""

    def test_alias_path_with_prefix(self):
        """AliasPath args should work with CLI prefix."""

        class PrefixedSettings(BaseSettings):
            my_field: str = Field(default='default', validation_alias=AliasPath('data', 0))

            model_config = {'env_file': None}

        source = CliSettingsSource(PrefixedSettings, cli_parse_args=[], cli_prefix='app')
        assert 'app.data' in source._parser_map

    def test_alias_path_with_prefix_not_in_dict_args(self):
        """AliasPath with int index and prefix should not be in _cli_dict_args."""

        class PrefixedSettings(BaseSettings):
            my_field: str = Field(default='default', validation_alias=AliasPath('data', 0))

            model_config = {'env_file': None}

        source = CliSettingsSource(PrefixedSettings, cli_parse_args=[], cli_prefix='app')
        assert 'app.data' not in source._cli_dict_args


class TestAddParserAliasPathsAddedArgs:
    """Tests verifying alias path args are tracked in added_args."""

    def test_alias_path_arg_not_duplicated(self):
        """Alias path arg should not cause duplicate arg registration errors."""
        # If added_args tracking is broken, argparse would raise on duplicate args
        source = CliSettingsSource(SettingsWithAliasPathInt, cli_parse_args=[])
        # Re-initializing should not raise
        assert source is not None

    def test_alias_path_with_choices_no_duplicate(self):
        """AliasChoices with multiple paths referencing same root should not duplicate."""

        class Settings(BaseSettings):
            field1: str = Field(default='d1', validation_alias=AliasPath('shared', 0))
            field2: str = Field(default='d2', validation_alias=AliasPath('shared', 1))

            model_config = {'env_file': None}

        source = CliSettingsSource(Settings, cli_parse_args=[])
        assert 'shared' in source._parser_map
