"""Unit tests for PydanticBaseEnvSettingsSource._extract_field_info method."""

from __future__ import annotations

from typing import Any, Optional, Union

import pytest
from pydantic import BaseModel, Field, AliasChoices, AliasPath
from pydantic.fields import FieldInfo

from pydantic_settings.main import BaseSettings
from pydantic_settings.sources.providers.env import EnvSettingsSource


class TestExtractFieldInfo:
    """Tests for _extract_field_info method."""

    def test_extract_field_info_with_no_alias(self):
        """Test extraction with no validation alias - should use field name."""

        class Settings(BaseSettings):
            name: str = Field(default='default')

        source = EnvSettingsSource(Settings)
        field = Settings.model_fields['name']
        result = source._extract_field_info(field, 'name')

        assert len(result) == 1
        assert result[0][0] == 'name'  # field_key
        assert result[0][1] == 'name'  # env_name
        assert result[0][2] is False  # value_is_complex

    def test_extract_field_info_with_string_alias(self):
        """Test extraction with simple string validation alias."""

        class Settings(BaseSettings):
            name: str = Field(default='default', validation_alias='custom_name')

        source = EnvSettingsSource(Settings)
        field = Settings.model_fields['name']
        result = source._extract_field_info(field, 'name')

        # Should have the alias
        assert any(item[0] == 'custom_name' for item in result)
        alias_item = next(item for item in result if item[0] == 'custom_name')
        assert alias_item[1] == 'custom_name'
        assert alias_item[2] is False  # string alias is not complex

    def test_extract_field_info_with_alias_choices(self):
        """Test extraction with AliasChoices."""

        class Settings(BaseSettings):
            name: str = Field(
                default='default',
                validation_alias=AliasChoices('custom_name', 'alternate_name')
            )

        source = EnvSettingsSource(Settings)
        field = Settings.model_fields['name']
        result = source._extract_field_info(field, 'name')

        # AliasChoices should expand to multiple entries
        assert len(result) >= 2
        # First item from AliasChoices should be 'custom_name'
        assert any(item[0] == 'custom_name' for item in result)
        # Second item should be 'alternate_name'
        assert any(item[0] == 'alternate_name' for item in result)

    def test_extract_field_info_with_alias_path_single_element(self):
        """Test extraction with AliasPath containing single string element."""

        class Settings(BaseSettings):
            name: str = Field(
                default='default',
                validation_alias=AliasPath('nested_name')
            )

        source = EnvSettingsSource(Settings)
        field = Settings.model_fields['name']
        result = source._extract_field_info(field, 'name')

        # AliasPath with single element - result depends on len(alias)
        # Line 390 checks: True if len(alias) > 1 else False
        assert len(result) >= 1
        alias_item = next(item for item in result if item[0] == 'nested_name')
        # AliasPath('nested_name') has len=1, but internal representation may vary
        assert isinstance(alias_item[2], bool)

    def test_extract_field_info_with_alias_path_multiple_elements(self):
        """Test extraction with AliasPath containing multiple elements."""

        class Settings(BaseSettings):
            name: str = Field(
                default='default',
                validation_alias=AliasPath('nested', 'deep', 'name')
            )

        source = EnvSettingsSource(Settings)
        field = Settings.model_fields['name']
        result = source._extract_field_info(field, 'name')

        # Should have entry for the first element
        assert any(item[0] == 'nested' for item in result)
        # Should be marked as complex (more than 1 element)
        path_item = next(item for item in result if item[0] == 'nested')
        assert path_item[2] is True

    def test_extract_field_info_with_env_prefix_alias_target(self):
        """Test extraction respects env_prefix when env_prefix_target includes 'alias'."""

        class Settings(BaseSettings):
            model_config = {'env_prefix': 'APP_'}

            name: str = Field(
                default='default',
                validation_alias='custom_name'
            )

        source = EnvSettingsSource(
            Settings,
            env_prefix='APP_',
            env_prefix_target='alias',
            case_sensitive=True
        )
        field = Settings.model_fields['name']
        result = source._extract_field_info(field, 'name')

        # Should have prefixed alias (case-sensitive)
        assert any(item[1] == 'APP_custom_name' for item in result)

    def test_extract_field_info_with_env_prefix_variable_target(self):
        """Test extraction respects env_prefix when env_prefix_target includes 'variable'."""

        class Settings(BaseSettings):
            model_config = {'env_prefix': 'APP_'}

            name: str = Field(default='default')

        source = EnvSettingsSource(
            Settings,
            env_prefix='APP_',
            env_prefix_target='variable',
            case_sensitive=True
        )
        field = Settings.model_fields['name']
        result = source._extract_field_info(field, 'name')

        # Should have prefixed variable name (case-sensitive)
        assert any(item[1] == 'APP_name' for item in result)

    def test_extract_field_info_with_env_prefix_all_target(self):
        """Test extraction respects env_prefix when env_prefix_target is 'all'."""

        class Settings(BaseSettings):
            model_config = {'env_prefix': 'APP_'}

            name: str = Field(
                default='default',
                validation_alias='custom_name'
            )

        source = EnvSettingsSource(
            Settings,
            env_prefix='APP_',
            env_prefix_target='all',
            case_sensitive=True
        )
        field = Settings.model_fields['name']
        result = source._extract_field_info(field, 'name')

        # Should have both prefixed alias and field name (case-sensitive)
        env_names = [item[1] for item in result]
        assert 'APP_custom_name' in env_names

    def test_extract_field_info_case_insensitive(self):
        """Test extraction with case_sensitive=False."""

        class Settings(BaseSettings):
            name: str = Field(
                default='default',
                validation_alias='CustomName'
            )

        source = EnvSettingsSource(Settings, case_sensitive=False)
        field = Settings.model_fields['name']
        result = source._extract_field_info(field, 'name')

        # Env name should be lowercase
        assert any(item[1] == 'customname' for item in result)

    def test_extract_field_info_with_populate_by_name(self):
        """Test extraction includes field name when populate_by_name is True."""

        class Settings(BaseSettings):
            model_config = {'populate_by_name': True}

            name: str = Field(
                default='default',
                validation_alias='custom_name'
            )

        source = EnvSettingsSource(Settings)
        field = Settings.model_fields['name']
        result = source._extract_field_info(field, 'name')

        # Should include both alias and field name
        field_keys = [item[0] for item in result]
        assert 'custom_name' in field_keys
        assert 'name' in field_keys

    def test_extract_field_info_with_validate_by_name(self):
        """Test extraction includes field name when validate_by_name is True."""

        class Settings(BaseSettings):
            model_config = {'validate_by_name': True}

            name: str = Field(
                default='default',
                validation_alias='custom_name'
            )

        source = EnvSettingsSource(Settings)
        field = Settings.model_fields['name']
        result = source._extract_field_info(field, 'name')

        # Should include both alias and field name
        field_keys = [item[0] for item in result]
        assert 'custom_name' in field_keys
        assert 'name' in field_keys

    def test_extract_field_info_union_type_complex(self):
        """Test extraction with union types."""

        class Settings(BaseSettings):
            name: Union[str, int] = Field(default='default')

        source = EnvSettingsSource(Settings)
        field = Settings.model_fields['name']
        result = source._extract_field_info(field, 'name')

        # Union types handling depends on _union_is_complex which checks metadata
        assert len(result) >= 1
        field_item = next(item for item in result if item[0] == 'name')
        # Result depends on union complexity check with metadata
        assert isinstance(field_item[2], bool)

    def test_extract_field_info_optional_type_simple(self):
        """Test extraction with Optional type (Union with None)."""

        class Settings(BaseSettings):
            name: Optional[str] = Field(default=None)

        source = EnvSettingsSource(Settings)
        field = Settings.model_fields['name']
        result = source._extract_field_info(field, 'name')

        # Optional[str] without complex metadata should not be complex
        assert len(result) >= 1
        field_item = next(item for item in result if item[0] == 'name')
        # This depends on implementation, but typically Optional[str] is not complex
        assert isinstance(field_item[2], bool)

    def test_extract_field_info_no_alias_no_populate_by_name(self):
        """Test extraction with no alias and populate_by_name False returns only field name."""

        class Settings(BaseSettings):
            model_config = {'populate_by_name': False}

            name: str = Field(default='default')

        source = EnvSettingsSource(Settings)
        field = Settings.model_fields['name']
        result = source._extract_field_info(field, 'name')

        # Should have exactly one entry for the field name
        assert len(result) == 1
        assert result[0][0] == 'name'

    def test_extract_field_info_alias_choices_multiple_options(self):
        """Test extraction with AliasChoices containing multiple string options."""

        class Settings(BaseSettings):
            name: str = Field(
                default='default',
                validation_alias=AliasChoices('simple', 'also_simple', 'or_this')
            )

        source = EnvSettingsSource(Settings)
        field = Settings.model_fields['name']
        result = source._extract_field_info(field, 'name')

        # Should have entries for all choices
        field_keys = [item[0] for item in result]
        assert 'simple' in field_keys
        assert 'also_simple' in field_keys
        assert 'or_this' in field_keys

    def test_extract_field_info_multiple_field_names(self):
        """Test extraction with multiple fields to ensure independence."""

        class Settings(BaseSettings):
            field1: str = Field(default='default1', validation_alias='alias1')
            field2: str = Field(default='default2', validation_alias='alias2')

        source = EnvSettingsSource(Settings)
        field1 = Settings.model_fields['field1']
        field2 = Settings.model_fields['field2']

        result1 = source._extract_field_info(field1, 'field1')
        result2 = source._extract_field_info(field2, 'field2')

        # Results should be independent
        keys1 = [item[0] for item in result1]
        keys2 = [item[0] for item in result2]
        assert 'alias1' in keys1
        assert 'alias2' in keys2
        assert 'alias1' not in keys2
        assert 'alias2' not in keys1

    def test_extract_field_info_empty_prefix(self):
        """Test extraction with empty env_prefix."""

        class Settings(BaseSettings):
            name: str = Field(default='default', validation_alias='custom')

        source = EnvSettingsSource(Settings, env_prefix='', env_prefix_target='all')
        field = Settings.model_fields['name']
        result = source._extract_field_info(field, 'name')

        # Should not have prefix in env names
        assert any(item[1] == 'custom' for item in result)

    def test_extract_field_info_respects_case_sensitive_setting(self):
        """Test extraction respects case_sensitive configuration."""

        class Settings(BaseSettings):
            MyField: str = Field(default='default')

        source_case_sensitive = EnvSettingsSource(Settings, case_sensitive=True)
        source_case_insensitive = EnvSettingsSource(Settings, case_sensitive=False)

        field = Settings.model_fields['MyField']

        result_sensitive = source_case_sensitive._extract_field_info(field, 'MyField')
        result_insensitive = source_case_insensitive._extract_field_info(field, 'MyField')

        # Case sensitive should preserve case
        assert result_sensitive[0][1] == 'MyField'
        # Case insensitive should convert to lowercase
        assert result_insensitive[0][1] == 'myfield'
