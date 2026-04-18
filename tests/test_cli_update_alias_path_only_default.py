"""Tests for CliSettingsSource._update_alias_path_only_default method."""

from argparse import ArgumentParser
from collections import defaultdict
from typing import Any

import pytest
from pydantic import AliasChoices, AliasPath, BaseModel, Field
from pydantic.fields import FieldInfo

from pydantic_settings import BaseSettings
from pydantic_settings.sources.providers.cli import CliSettingsSource


class SimpleSettings(BaseSettings):
    """Simple settings model for testing."""

    name: str = 'default'
    value: int = 0
    verbose: bool = False


class TestUpdateAliasPathOnlyDefault:
    """Tests for CliSettingsSource._update_alias_path_only_default method."""

    def test_update_alias_path_no_nested_paths(self):
        """Test updating alias path with no nested paths (flat list)."""
        source = CliSettingsSource(
            settings_cls=SimpleSettings,
            cli_parse_args=None,
        )

        # Create a FieldInfo with AliasPath that has no nested paths
        # AliasPath('a', 0) means root level, index 0
        field_info = FieldInfo(annotation=str, alias=AliasPath('a', 0), default='default')

        arg_name = 'test_arg'
        value = 'test_value'
        alias_path_only_defaults: dict[str, Any] = {}

        result = source._update_alias_path_only_default(
            arg_name, value, field_info, alias_path_only_defaults
        )

        assert isinstance(result, list)
        assert result[0] == 'test_value'
        assert alias_path_only_defaults[arg_name] is result

    def test_update_alias_path_no_nested_paths_multiple_indices(self):
        """Test updating alias path with no nested paths at higher index."""
        source = CliSettingsSource(
            settings_cls=SimpleSettings,
            cli_parse_args=None,
        )

        # AliasPath('a', 2) means root level, index 2
        field_info = FieldInfo(annotation=str, alias=AliasPath('a', 2), default='default')

        arg_name = 'test_arg'
        value = 'test_value'
        alias_path_only_defaults: dict[str, Any] = {}

        result = source._update_alias_path_only_default(
            arg_name, value, field_info, alias_path_only_defaults
        )

        assert isinstance(result, list)
        assert len(result) == 3
        assert result[0] == ''
        assert result[1] == ''
        assert result[2] == 'test_value'

    def test_update_alias_path_with_single_nested_path(self):
        """Test updating alias path with one level of nesting."""
        source = CliSettingsSource(
            settings_cls=SimpleSettings,
            cli_parse_args=None,
        )

        # AliasPath('root', 'nested', 0) means nested['nested'] is a list at index 0
        field_info = FieldInfo(annotation=str, alias=AliasPath('root', 'nested', 0), default='default')

        arg_name = 'test_arg'
        value = 'test_value'
        alias_path_only_defaults: dict[str, Any] = {}

        result = source._update_alias_path_only_default(
            arg_name, value, field_info, alias_path_only_defaults
        )

        assert isinstance(result, dict)
        assert 'nested' in result
        assert isinstance(result['nested'], list)
        assert result['nested'][0] == 'test_value'

    def test_update_alias_path_with_multiple_nested_paths(self):
        """Test updating alias path with multiple levels of nesting."""
        source = CliSettingsSource(
            settings_cls=SimpleSettings,
            cli_parse_args=None,
        )

        # AliasPath('root', 'level1', 'level2', 1)
        field_info = FieldInfo(
            annotation=str, alias=AliasPath('root', 'level1', 'level2', 1), default='default'
        )

        arg_name = 'test_arg'
        value = 'test_value'
        alias_path_only_defaults: dict[str, Any] = {}

        result = source._update_alias_path_only_default(
            arg_name, value, field_info, alias_path_only_defaults
        )

        assert isinstance(result, dict)
        assert 'level1' in result
        assert isinstance(result['level1'], dict)
        assert 'level2' in result['level1']
        assert isinstance(result['level1']['level2'], list)
        assert result['level1']['level2'][1] == 'test_value'

    def test_update_alias_path_appends_to_existing_list(self):
        """Test updating alias path appends to existing list entry."""
        source = CliSettingsSource(
            settings_cls=SimpleSettings,
            cli_parse_args=None,
        )

        field_info = FieldInfo(annotation=str, alias=AliasPath('a', 0), default='default')

        arg_name = 'test_arg'
        alias_path_only_defaults: dict[str, Any] = {arg_name: ['existing']}

        result = source._update_alias_path_only_default(
            arg_name, 'new_value', field_info, alias_path_only_defaults
        )

        assert result[0] == 'new_value'

    def test_update_alias_path_preserves_existing_nested_structure(self):
        """Test updating alias path preserves existing nested structure."""
        source = CliSettingsSource(
            settings_cls=SimpleSettings,
            cli_parse_args=None,
        )

        field_info = FieldInfo(
            annotation=str, alias=AliasPath('root', 'level1', 'level2', 1), default='default'
        )

        arg_name = 'test_arg'
        # Pre-populate with existing structure
        alias_path_only_defaults: dict[str, Any] = {arg_name: {'level1': {'level2': ['', 'existing']}}}

        result = source._update_alias_path_only_default(
            arg_name, 'new_value', field_info, alias_path_only_defaults
        )

        assert result['level1']['level2'][1] == 'new_value'
        assert result['level1']['level2'][0] == ''

    def test_update_alias_path_with_validation_alias(self):
        """Test updating alias path when using validation_alias instead of alias."""
        source = CliSettingsSource(
            settings_cls=SimpleSettings,
            cli_parse_args=None,
        )

        field_info = FieldInfo(
            annotation=str, validation_alias=AliasPath('a', 0), default='default'
        )

        arg_name = 'test_arg'
        value = 'test_value'
        alias_path_only_defaults: dict[str, Any] = {}

        result = source._update_alias_path_only_default(
            arg_name, value, field_info, alias_path_only_defaults
        )

        assert isinstance(result, list)
        assert result[0] == 'test_value'

    def test_update_alias_path_with_alias_choices_containing_aliaspath(self):
        """Test updating alias path when using AliasChoices with AliasPath."""
        source = CliSettingsSource(
            settings_cls=SimpleSettings,
            cli_parse_args=None,
        )

        # AliasChoices selects the first AliasPath as the default
        field_info = FieldInfo(
            annotation=str,
            alias=AliasChoices(AliasPath('root', 'nested', 0), 'fallback'),
            default='default',
        )

        arg_name = 'test_arg'
        value = 'test_value'
        alias_path_only_defaults: dict[str, Any] = {}

        result = source._update_alias_path_only_default(
            arg_name, value, field_info, alias_path_only_defaults
        )

        assert isinstance(result, dict)
        assert 'nested' in result
        assert result['nested'][0] == 'test_value'

    def test_update_alias_path_fills_gaps_with_empty_strings(self):
        """Test that gaps in indices are filled with empty strings."""
        source = CliSettingsSource(
            settings_cls=SimpleSettings,
            cli_parse_args=None,
        )

        field_info = FieldInfo(annotation=str, alias=AliasPath('a', 5), default='default')

        arg_name = 'test_arg'
        value = 'test_value'
        alias_path_only_defaults: dict[str, Any] = {}

        result = source._update_alias_path_only_default(
            arg_name, value, field_info, alias_path_only_defaults
        )

        assert len(result) == 6
        assert all(item == '' for item in result[:5])
        assert result[5] == 'test_value'

    def test_update_alias_path_returns_correct_part_of_defaults(self):
        """Test that method returns the correct part of alias_path_only_defaults."""
        source = CliSettingsSource(
            settings_cls=SimpleSettings,
            cli_parse_args=None,
        )

        field_info = FieldInfo(
            annotation=str, alias=AliasPath('root', 'nested', 0), default='default'
        )

        arg_name = 'test_arg'
        value = 'test_value'
        alias_path_only_defaults: dict[str, Any] = {}

        result = source._update_alias_path_only_default(
            arg_name, value, field_info, alias_path_only_defaults
        )

        # Return value should be the item stored at arg_name
        assert result is alias_path_only_defaults[arg_name]

    def test_update_alias_path_deep_nesting(self):
        """Test updating alias path with deep nesting (3+ levels)."""
        source = CliSettingsSource(
            settings_cls=SimpleSettings,
            cli_parse_args=None,
        )

        field_info = FieldInfo(
            annotation=str,
            alias=AliasPath('root', 'l1', 'l2', 'l3', 'l4', 2),
            default='default',
        )

        arg_name = 'test_arg'
        value = 'test_value'
        alias_path_only_defaults: dict[str, Any] = {}

        result = source._update_alias_path_only_default(
            arg_name, value, field_info, alias_path_only_defaults
        )

        assert isinstance(result, dict)
        assert result['l1']['l2']['l3']['l4'][2] == 'test_value'
