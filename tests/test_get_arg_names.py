"""Tests for CliSettingsSource._get_arg_names covering previously uncovered lines."""
from __future__ import annotations

from typing import Annotated, Literal, Union

import pytest
from pydantic import BaseModel, Field
from pydantic.fields import FieldInfo

from pydantic_settings import BaseSettings, CliSettingsSource


# --- Settings with cli_shortcuts ---


class SettingsWithShortcuts(BaseSettings):
    option: str = Field(default='foo')
    list_option: str = Field(default='fizz')

    model_config = {'cli_shortcuts': {'option': 'opt', 'list_option': ['lo', 'list_opt']}}


class SettingsWithShortcutString(BaseSettings):
    my_field: str = Field(default='bar')

    model_config = {'cli_shortcuts': {'my_field': 'mf'}}


# --- Settings with discriminated unions ---


class CatModel(BaseModel):
    pet_type: Literal['cat']
    name: str = 'Whiskers'


class DogModel(BaseModel):
    pet_type: Literal['dog']
    name: str = 'Rex'


class SettingsWithDiscriminator(BaseSettings):
    pet: Annotated[Union[CatModel, DogModel], Field(discriminator='pet_type')]


# --- Tests for cli_shortcuts (lines 1182-1185) ---


def test_cli_shortcuts_string_alias_is_added():
    """Test that a string shortcut alias is added to arg_names (lines 1182-1185)."""
    source = CliSettingsSource(SettingsWithShortcutString, cli_parse_args=['--mf', 'hello'])
    # Verify source was constructed with cli_shortcuts set
    assert source.cli_shortcuts == {'my_field': 'mf'}
    # Verify we can parse using the shortcut
    result = source()
    assert result.get('my_field') == 'hello'


def test_cli_shortcuts_list_alias_is_added():
    """Test that list shortcut aliases are all added to arg_names (lines 1182-1185)."""
    source = CliSettingsSource(SettingsWithShortcuts, cli_parse_args=['--lo', 'buzz'])
    result = source()
    assert result.get('list_option') == 'buzz'


def test_cli_shortcuts_second_list_alias():
    """Test that second alias in list shortcut also works (lines 1184-1185)."""
    source = CliSettingsSource(SettingsWithShortcuts, cli_parse_args=['--list_opt', 'baz'])
    result = source()
    assert result.get('list_option') == 'baz'


def test_cli_shortcuts_original_arg_name_still_works():
    """Test that original arg name still works when shortcuts are defined."""
    source = CliSettingsSource(SettingsWithShortcuts, cli_parse_args=['--option', 'bar'])
    result = source()
    assert result.get('option') == 'bar'


def test_cli_shortcuts_shortcut_string_single():
    """Test shortcut where alias is a string (not list) from cli_shortcuts (line 1184)."""
    source = CliSettingsSource(SettingsWithShortcuts, cli_parse_args=['--opt', 'newval'])
    result = source()
    assert result.get('option') == 'newval'


# --- Tests for discriminated unions (lines 1190, 1196-1199) ---


def test_discriminated_union_parses_cat():
    """Test that discriminated union with Literal type processes discriminators (lines 1190, 1196-1199)."""
    source = CliSettingsSource(
        SettingsWithDiscriminator,
        cli_parse_args=['--pet.pet_type', 'cat', '--pet.name', 'Felix'],
    )
    result = source()
    assert result.get('pet') is not None


def test_discriminated_union_parses_dog():
    """Test that discriminated union parses last discriminator (line 1199 metavar set)."""
    source = CliSettingsSource(
        SettingsWithDiscriminator,
        cli_parse_args=['--pet.pet_type', 'dog', '--pet.name', 'Buddy'],
    )
    result = source()
    assert result.get('pet') is not None


def test_discriminated_union_source_constructs():
    """Test CliSettingsSource is successfully constructed with a discriminated union model.

    This exercises _get_arg_names for the discriminator field, covering:
    - line 1190: _annotation_contains_types call
    - line 1196: discriminators.update(...)
    - lines 1197-1199: is_last_discriminator check and metavar assignment
    """
    source = CliSettingsSource(SettingsWithDiscriminator, cli_parse_args=[])
    assert source is not None
    # Format help to verify discriminator metavar is set
    help_text = source._root_parser.format_help()
    assert 'pet_type' in help_text
