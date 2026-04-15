"""Tests for CliSettingsSource._update_alias_path_only_default."""
from __future__ import annotations

import pytest
from pydantic import AliasChoices, AliasPath, BaseModel, Field

from pydantic_settings import BaseSettings, CliSettingsSource


class SimpleSettings(BaseSettings):
    name: str = "default"
    value: int = 0


@pytest.fixture
def cli_source():
    return CliSettingsSource(SimpleSettings, cli_parse_args=[])


def test_update_alias_path_only_default_no_nested_paths(cli_source):
    """AliasPath with 2-element path (no nested paths) creates a list."""
    field_info = Field(alias=AliasPath("root", 0))
    alias_path_only_defaults: dict = {}

    result = cli_source._update_alias_path_only_default("myarg", "myvalue", field_info, alias_path_only_defaults)

    assert result == ["myvalue"]
    assert alias_path_only_defaults["myarg"] == ["myvalue"]


def test_update_alias_path_only_default_no_nested_paths_nonzero_index(cli_source):
    """AliasPath with index > 0 extends the list with empty strings before setting value."""
    field_info = Field(alias=AliasPath("root", 2))
    alias_path_only_defaults: dict = {}

    result = cli_source._update_alias_path_only_default("myarg", "myvalue", field_info, alias_path_only_defaults)

    assert result == ["", "", "myvalue"]


def test_update_alias_path_only_default_existing_list_entry(cli_source):
    """Calling with existing list entry preserves previous values."""
    field_info = Field(alias=AliasPath("root", 0))
    alias_path_only_defaults: dict = {}

    cli_source._update_alias_path_only_default("myarg", "first", field_info, alias_path_only_defaults)

    field_info2 = Field(alias=AliasPath("root", 1))
    result = cli_source._update_alias_path_only_default("myarg", "second", field_info2, alias_path_only_defaults)

    assert result == ["first", "second"]


def test_update_alias_path_only_default_one_nested_path(cli_source):
    """AliasPath with 3-element path creates a dict with a list value."""
    field_info = Field(alias=AliasPath("root", "nested", 0))
    alias_path_only_defaults: dict = {}

    result = cli_source._update_alias_path_only_default("myarg", "myvalue", field_info, alias_path_only_defaults)

    assert result == {"nested": ["myvalue"]}
    assert alias_path_only_defaults["myarg"] == {"nested": ["myvalue"]}


def test_update_alias_path_only_default_multiple_nested_paths(cli_source):
    """AliasPath with 4-element path creates nested dicts with a list at the leaf."""
    field_info = Field(alias=AliasPath("root", "a", "b", 0))
    alias_path_only_defaults: dict = {}

    result = cli_source._update_alias_path_only_default("myarg", "myvalue", field_info, alias_path_only_defaults)

    assert result == {"a": {"b": ["myvalue"]}}


def test_update_alias_path_only_default_validation_alias(cli_source):
    """Works when alias is on validation_alias instead of alias."""
    field_info = Field(validation_alias=AliasPath("root", 0))
    alias_path_only_defaults: dict = {}

    result = cli_source._update_alias_path_only_default("myarg", "val", field_info, alias_path_only_defaults)

    assert result == ["val"]


def test_update_alias_path_only_default_alias_choices(cli_source):
    """Works when validation_alias is an AliasChoices containing an AliasPath."""
    field_info = Field(validation_alias=AliasChoices(AliasPath("root", 0)))
    alias_path_only_defaults: dict = {}

    result = cli_source._update_alias_path_only_default("myarg", "val", field_info, alias_path_only_defaults)

    assert result == ["val"]


def test_update_alias_path_only_default_nested_nonzero_index(cli_source):
    """Nested path with non-zero index extends list properly."""
    field_info = Field(alias=AliasPath("root", "nested", 1))
    alias_path_only_defaults: dict = {}

    result = cli_source._update_alias_path_only_default("myarg", "myvalue", field_info, alias_path_only_defaults)

    assert result == {"nested": ["", "myvalue"]}
