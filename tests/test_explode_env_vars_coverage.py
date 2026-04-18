"""Tests for EnvSettingsSource.explode_env_vars targeting uncovered branches."""

from __future__ import annotations

import os
from enum import Enum
from typing import Any, Dict, List, Optional
from unittest.mock import patch

import pytest
from pydantic import BaseModel
from pydantic.fields import FieldInfo

from pydantic_settings import BaseSettings
from pydantic_settings.sources.providers.env import EnvSettingsSource


# --- Models for enum parsing in nested env vars ---


class MyStatus(str, Enum):
    active = 'active_value'
    inactive = 'inactive_value'


class SubModelWithEnum(BaseModel):
    status: MyStatus = MyStatus.active
    name: str = 'default'


class EnumNestedSettings(BaseSettings):
    model_config = {'env_nested_delimiter': '__'}

    sub: SubModelWithEnum = SubModelWithEnum()


# --- Models for complex nested fields ---


class SubModelWithList(BaseModel):
    items: List[str] = []


class NestedComplexSettings(BaseSettings):
    model_config = {'env_nested_delimiter': '__'}

    sub: SubModelWithList = SubModelWithList()


# --- Models for dict deep nesting ---


class DeepDictSettings(BaseSettings):
    model_config = {'env_nested_delimiter': '__'}

    data: Dict[str, Any] = {}


# --- Tests for env_parse_enums in explode_env_vars (lines 263-264) ---


class TestExplodeEnvVarsEnumParsing:
    def test_explode_env_parse_enums_matching_name(self):
        """When env_parse_enums=True and env_val matches an enum member name,
        the value should be replaced with the enum member."""
        with patch.dict(os.environ, {'SUB__STATUS': 'active'}, clear=True):
            source = EnvSettingsSource(EnumNestedSettings, env_parse_enums=True)
            field = EnumNestedSettings.model_fields['sub']
            result = source.explode_env_vars('sub', field, source.env_vars)
            assert result['status'] == MyStatus.active

    def test_explode_env_parse_enums_no_match(self):
        """When env_parse_enums=True but env_val doesn't match any enum member name,
        the original string value should be kept."""
        with patch.dict(os.environ, {'SUB__STATUS': 'active_value'}, clear=True):
            source = EnvSettingsSource(EnumNestedSettings, env_parse_enums=True)
            field = EnumNestedSettings.model_fields['sub']
            result = source.explode_env_vars('sub', field, source.env_vars)
            # 'active_value' is the enum value, not the name, so no match
            assert result['status'] == 'active_value'

    def test_explode_env_parse_enums_non_enum_field(self):
        """When env_parse_enums=True but the target field is not an enum,
        _annotation_enum_name_to_val returns None and value is unchanged."""
        with patch.dict(os.environ, {'SUB__NAME': 'hello'}, clear=True):
            source = EnvSettingsSource(EnumNestedSettings, env_parse_enums=True)
            field = EnumNestedSettings.model_fields['sub']
            result = source.explode_env_vars('sub', field, source.env_vars)
            assert result['name'] == 'hello'


# --- Tests for dict deep nesting where target_field is None (line 271) ---


class TestExplodeEnvVarsDictDeepNesting:
    def test_explode_dict_deep_nesting_valid_json(self):
        """Dict field with deep nesting (>1 level) and valid JSON value.
        target_field becomes None, is_dict=True, is_complex=True."""
        with patch.dict(os.environ, {'DATA__KEY1__SUBKEY': '{"nested": true}'}, clear=True):
            source = EnvSettingsSource(DeepDictSettings)
            field = DeepDictSettings.model_fields['data']
            result = source.explode_env_vars('data', field, source.env_vars)
            assert 'key1' in result
            assert result['key1']['subkey'] == {'nested': True}

    def test_explode_dict_deep_nesting_invalid_json(self):
        """Dict field with deep nesting and invalid JSON value.
        ValueError from decode_complex_value is caught since allow_json_failure=True."""
        with patch.dict(os.environ, {'DATA__KEY1__SUBKEY': 'plain_text'}, clear=True):
            source = EnvSettingsSource(DeepDictSettings)
            field = DeepDictSettings.model_fields['data']
            result = source.explode_env_vars('data', field, source.env_vars)
            assert result['key1']['subkey'] == 'plain_text'

    def test_explode_dict_deep_nesting_json_list(self):
        """Dict field with deep nesting and valid JSON list value."""
        with patch.dict(os.environ, {'DATA__KEY1__SUBKEY': '[1, 2, 3]'}, clear=True):
            source = EnvSettingsSource(DeepDictSettings)
            field = DeepDictSettings.model_fields['data']
            result = source.explode_env_vars('data', field, source.env_vars)
            assert result['key1']['subkey'] == [1, 2, 3]


# --- Tests for complex field decode in explode_env_vars (lines 273-278) ---


class TestExplodeEnvVarsComplexDecode:
    def test_explode_nested_complex_field_valid_json(self):
        """Nested model with complex field (List[str]) and valid JSON.
        decode_complex_value succeeds."""
        with patch.dict(os.environ, {'SUB__ITEMS': '["a", "b"]'}, clear=True):
            source = EnvSettingsSource(NestedComplexSettings)
            field = NestedComplexSettings.model_fields['sub']
            result = source.explode_env_vars('sub', field, source.env_vars)
            assert result['items'] == ['a', 'b']

    def test_explode_nested_complex_field_invalid_json_raises(self):
        """Nested model with complex field (List[str]) and invalid JSON.
        allow_json_failure=False so ValueError is raised."""
        with patch.dict(os.environ, {'SUB__ITEMS': 'not_json'}, clear=True):
            source = EnvSettingsSource(NestedComplexSettings)
            field = NestedComplexSettings.model_fields['sub']
            with pytest.raises(ValueError):
                source.explode_env_vars('sub', field, source.env_vars)
