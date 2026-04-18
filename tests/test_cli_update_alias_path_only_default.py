"""Tests for CliSettingsSource._update_alias_path_only_default method."""

from __future__ import annotations

import pytest
from pydantic import AliasChoices, AliasPath, Field
from pydantic.fields import FieldInfo

from pydantic_settings import BaseSettings, CliSettingsSource


class TestUpdateAliasPathOnlyDefault:
    """Tests for _update_alias_path_only_default method."""

    def test_simple_alias_path_with_index(self):
        """Test with simple AliasPath with direct index (no nested paths)."""

        class Settings(BaseSettings):
            item: str = Field(validation_alias=AliasPath('items', 0))

        source = CliSettingsSource(Settings)
        field_info = Settings.model_fields['item']
        alias_path_only_defaults: dict[str, any] = {}

        result = source._update_alias_path_only_default(
            'items', 'value0', field_info, alias_path_only_defaults
        )

        assert alias_path_only_defaults == {'items': ['value0']}
        assert result == ['value0']

    def test_alias_path_with_higher_index(self):
        """Test with AliasPath where index > 0 to verify padding."""

        class Settings(BaseSettings):
            item: str = Field(validation_alias=AliasPath('items', 2))

        source = CliSettingsSource(Settings)
        field_info = Settings.model_fields['item']
        alias_path_only_defaults: dict[str, any] = {}

        result = source._update_alias_path_only_default(
            'items', 'value2', field_info, alias_path_only_defaults
        )

        assert alias_path_only_defaults == {'items': ['', '', 'value2']}
        assert result == ['', '', 'value2']

    def test_alias_path_update_existing_list(self):
        """Test updating an existing list with new value."""

        class Settings(BaseSettings):
            item: str = Field(validation_alias=AliasPath('items', 1))

        source = CliSettingsSource(Settings)
        field_info = Settings.model_fields['item']
        alias_path_only_defaults: dict[str, any] = {'items': ['existing']}

        result = source._update_alias_path_only_default(
            'items', 'new_value', field_info, alias_path_only_defaults
        )

        assert alias_path_only_defaults == {'items': ['existing', 'new_value']}
        assert result == ['existing', 'new_value']

    def test_nested_alias_path_single_level(self):
        """Test with AliasPath with single nested level before index."""

        class Settings(BaseSettings):
            item: str = Field(validation_alias=AliasPath('data', 'items', 0))

        source = CliSettingsSource(Settings)
        field_info = Settings.model_fields['item']
        alias_path_only_defaults: dict[str, any] = {}

        result = source._update_alias_path_only_default(
            'data', 'value0', field_info, alias_path_only_defaults
        )

        assert alias_path_only_defaults == {'data': {'items': ['value0']}}
        assert result == {'items': ['value0']}

    def test_nested_alias_path_multi_level(self):
        """Test with AliasPath with multiple nested levels before index."""

        class Settings(BaseSettings):
            item: str = Field(validation_alias=AliasPath('root', 'nested', 'items', 0))

        source = CliSettingsSource(Settings)
        field_info = Settings.model_fields['item']
        alias_path_only_defaults: dict[str, any] = {}

        result = source._update_alias_path_only_default(
            'root', 'value0', field_info, alias_path_only_defaults
        )

        assert alias_path_only_defaults == {'root': {'nested': {'items': ['value0']}}}
        assert result == {'nested': {'items': ['value0']}}

    def test_nested_alias_path_update_existing(self):
        """Test updating existing nested dict structure."""

        class Settings(BaseSettings):
            item: str = Field(validation_alias=AliasPath('data', 'items', 1))

        source = CliSettingsSource(Settings)
        field_info = Settings.model_fields['item']
        alias_path_only_defaults: dict[str, any] = {'data': {'items': ['existing']}}

        result = source._update_alias_path_only_default(
            'data', 'new_value', field_info, alias_path_only_defaults
        )

        assert alias_path_only_defaults == {'data': {'items': ['existing', 'new_value']}}
        assert result == {'items': ['existing', 'new_value']}

    def test_alias_choices_with_alias_path(self):
        """Test with AliasChoices containing AliasPath as first choice."""

        class Settings(BaseSettings):
            item: str = Field(
                validation_alias=AliasChoices(AliasPath('items', 0), 'fallback')
            )

        source = CliSettingsSource(Settings)
        field_info = Settings.model_fields['item']
        alias_path_only_defaults: dict[str, any] = {}

        result = source._update_alias_path_only_default(
            'items', 'value0', field_info, alias_path_only_defaults
        )

        assert alias_path_only_defaults == {'items': ['value0']}
        assert result == ['value0']

    def test_nested_path_with_higher_index(self):
        """Test nested path structure with index > 0."""

        class Settings(BaseSettings):
            item: str = Field(validation_alias=AliasPath('data', 'items', 3))

        source = CliSettingsSource(Settings)
        field_info = Settings.model_fields['item']
        alias_path_only_defaults: dict[str, any] = {}

        result = source._update_alias_path_only_default(
            'data', 'value3', field_info, alias_path_only_defaults
        )

        assert alias_path_only_defaults == {'data': {'items': ['', '', '', 'value3']}}
        assert result == {'items': ['', '', '', 'value3']}

    def test_deeply_nested_alias_path(self):
        """Test with deeply nested alias path (3+ levels)."""

        class Settings(BaseSettings):
            item: str = Field(
                validation_alias=AliasPath('level1', 'level2', 'level3', 'items', 0)
            )

        source = CliSettingsSource(Settings)
        field_info = Settings.model_fields['item']
        alias_path_only_defaults: dict[str, any] = {}

        result = source._update_alias_path_only_default(
            'level1', 'value0', field_info, alias_path_only_defaults
        )

        expected = {'level2': {'level3': {'items': ['value0']}}}
        assert alias_path_only_defaults == {'level1': expected}
        assert result == expected

    def test_existing_nested_dict_preserves_other_keys(self):
        """Test that existing dict structure preserves other keys."""

        class Settings(BaseSettings):
            item: str = Field(validation_alias=AliasPath('data', 'items', 0))

        source = CliSettingsSource(Settings)
        field_info = Settings.model_fields['item']
        alias_path_only_defaults: dict[str, any] = {
            'data': {'other_key': 'preserved', 'items': []}
        }

        result = source._update_alias_path_only_default(
            'data', 'value0', field_info, alias_path_only_defaults
        )

        assert alias_path_only_defaults == {
            'data': {'other_key': 'preserved', 'items': ['value0']}
        }
        assert result == {'other_key': 'preserved', 'items': ['value0']}
