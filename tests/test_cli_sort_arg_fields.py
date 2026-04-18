"""Tests for CliSettingsSource._sort_arg_fields method covering edge cases."""

from __future__ import annotations

from typing import Annotated

import pytest
from pydantic import AliasChoices, BaseModel, Field

from pydantic_settings import BaseSettings, CliSettingsSource, SettingsError
from pydantic_settings.sources.providers.cli import CliPositionalArg, CliSubCommand
from pydantic_settings.sources.types import _CliPositionalArg, _CliSubCommand


class TestSortArgFieldsSubcommandErrors:
    """Tests for subcommand argument validation errors in _sort_arg_fields."""

    def test_subcommand_with_multiple_aliases_raises_error(self):
        """Test that subcommand with multiple aliases raises SettingsError."""

        class SubCmd(BaseModel):
            name: str = 'default'

        class Settings(BaseSettings):
            cmd: Annotated[SubCmd | None, _CliSubCommand] = Field(
                validation_alias=AliasChoices('cmd', 'command')
            )

        with pytest.raises(SettingsError, match='subcommand argument Settings.cmd has multiple aliases'):
            CliSettingsSource(Settings)

    def test_subcommand_with_non_basemodel_type_raises_error(self):
        """Test that subcommand with non-BaseModel type raises SettingsError."""

        class Settings(BaseSettings):
            cmd: Annotated[str | None, _CliSubCommand]

        with pytest.raises(SettingsError, match='subcommand argument Settings.cmd has type not derived from BaseModel'):
            CliSettingsSource(Settings)

    def test_subcommand_with_int_type_raises_error(self):
        """Test that subcommand with int type raises SettingsError."""

        class Settings(BaseSettings):
            cmd: Annotated[int | None, _CliSubCommand]

        with pytest.raises(SettingsError, match='has type not derived from BaseModel'):
            CliSettingsSource(Settings)


class TestSortArgFieldsPositionalErrors:
    """Tests for positional argument validation errors in _sort_arg_fields."""

    def test_positional_with_multiple_aliases_raises_error(self):
        """Test that positional arg with multiple aliases raises SettingsError."""

        class Settings(BaseSettings):
            pos: Annotated[str, _CliPositionalArg] = Field(
                validation_alias=AliasChoices('pos', 'position')
            )

        with pytest.raises(SettingsError, match='positional argument Settings.pos has multiple aliases'):
            CliSettingsSource(Settings)


class TestSortArgFieldsVariadicPositional:
    """Tests for variadic positional argument handling in _sort_arg_fields."""

    def test_variadic_positional_arg_list(self):
        """Test that list positional args are treated as variadic."""

        class Settings(BaseSettings):
            files: CliPositionalArg[list[str]]
            output: str = 'default'

        source = CliSettingsSource(Settings)
        sorted_fields = source._sort_arg_fields(Settings)

        field_names = [name for name, _ in sorted_fields]
        # variadic positional (list) should come before optional args
        files_idx = field_names.index('files')
        output_idx = field_names.index('output')
        assert files_idx < output_idx

    def test_variadic_positional_arg_set(self):
        """Test that set positional args are treated as variadic."""

        class Settings(BaseSettings):
            tags: CliPositionalArg[set[str]]

        source = CliSettingsSource(Settings)
        sorted_fields = source._sort_arg_fields(Settings)

        field_names = [name for name, _ in sorted_fields]
        assert 'tags' in field_names

    def test_multiple_variadic_positional_args_raises_error(self):
        """Test that multiple variadic positional args raise SettingsError."""

        class Settings(BaseSettings):
            files: CliPositionalArg[list[str]]
            items: CliPositionalArg[list[int]]

        with pytest.raises(SettingsError, match='has multiple variadic positional arguments'):
            CliSettingsSource(Settings)

    def test_multiple_variadic_positional_lists_all_names_in_error(self):
        """Test that error message contains all variadic field names."""

        class Settings(BaseSettings):
            files: CliPositionalArg[list[str]]
            items: CliPositionalArg[list[int]]

        with pytest.raises(SettingsError, match='files') as exc_info:
            CliSettingsSource(Settings)
        assert 'items' in str(exc_info.value)

    def test_variadic_positional_with_subcommand_raises_error(self):
        """Test that variadic positional with subcommand raises SettingsError."""

        class SubCmd(BaseModel):
            name: str = 'default'

        class Settings(BaseSettings):
            files: CliPositionalArg[list[str]]
            cmd: CliSubCommand[SubCmd]

        with pytest.raises(SettingsError, match='has variadic positional arguments and subcommand arguments'):
            CliSettingsSource(Settings)

    def test_variadic_positional_with_subcommand_error_contains_names(self):
        """Test that error message contains both variadic and subcommand names."""

        class SubCmd(BaseModel):
            name: str = 'default'

        class Settings(BaseSettings):
            items: CliPositionalArg[list[str]]
            cmd: CliSubCommand[SubCmd]

        with pytest.raises(SettingsError) as exc_info:
            CliSettingsSource(Settings)
        error_msg = str(exc_info.value)
        assert 'items' in error_msg
        assert 'cmd' in error_msg

    def test_variadic_positional_dict_type(self):
        """Test that dict positional args are treated as variadic."""

        class Settings(BaseSettings):
            mapping: CliPositionalArg[dict[str, str]]

        source = CliSettingsSource(Settings)
        sorted_fields = source._sort_arg_fields(Settings)

        field_names = [name for name, _ in sorted_fields]
        assert 'mapping' in field_names


class TestSortArgFieldsSortingOrder:
    """Tests for correct field sorting order in _sort_arg_fields."""

    def test_non_variadic_positional_before_variadic(self):
        """Test that non-variadic positional args come before variadic ones."""

        class Settings(BaseSettings):
            # Non-variadic (single value) positional
            name: CliPositionalArg[str]
            # Variadic (list) positional - should come after
            files: CliPositionalArg[list[str]]
            optional: str = 'default'

        source = CliSettingsSource(Settings)
        sorted_fields = source._sort_arg_fields(Settings)

        field_names = [name for name, _ in sorted_fields]
        name_idx = field_names.index('name')
        files_idx = field_names.index('files')
        optional_idx = field_names.index('optional')

        assert name_idx < files_idx < optional_idx

    def test_ordering_with_subcommand(self):
        """Test correct ordering with subcommand field."""

        class SubCmd(BaseModel):
            value: str = 'test'

        class Settings(BaseSettings):
            pos: CliPositionalArg[str]
            cmd: CliSubCommand[SubCmd]
            opt: str = 'default'

        source = CliSettingsSource(Settings)
        sorted_fields = source._sort_arg_fields(Settings)

        field_names = [name for name, _ in sorted_fields]
        pos_idx = field_names.index('pos')
        cmd_idx = field_names.index('cmd')
        opt_idx = field_names.index('opt')

        # Order: positional, subcommand, optional
        assert pos_idx < cmd_idx < opt_idx
