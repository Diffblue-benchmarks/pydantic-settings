"""Tests for CliSettingsSource._sort_arg_fields method."""

from typing import Annotated, Union

import pytest

from pydantic import AliasChoices, BaseModel, Field
from pydantic.fields import FieldInfo

from pydantic_settings import BaseSettings, CliPositionalArg, CliSettingsSource, CliSubCommand
from pydantic_settings.exceptions import SettingsError
from pydantic_settings.sources.types import _CliPositionalArg, _CliSubCommand


# ---- Helper to call _sort_arg_fields without triggering full parse ----

def _sort_fields(settings_cls: type[BaseSettings]) -> list[tuple[str, FieldInfo]]:
    source = CliSettingsSource(settings_cls, cli_parse_args=None)
    return source._sort_arg_fields(settings_cls)


# ---- Models ----

class SubA(BaseModel):
    val: str = 'a'


class SubB(BaseModel):
    val: str = 'b'


# ---- Tests: subcommand with multiple aliases raises error (line 789) ----

class TestSubcommandMultipleAliases:
    def test_subcommand_with_multiple_aliases_raises(self):
        class BadSettings(BaseSettings):
            sub: CliSubCommand[Union[SubA, SubB]] = Field(
                validation_alias=AliasChoices('sub', 'subcmd')
            )
            model_config = {'env_file': None}

        with pytest.raises(SettingsError, match='has multiple aliases'):
            CliSettingsSource(BadSettings, cli_parse_args=None)


# ---- Tests: subcommand with non-BaseModel type raises error (lines 793-794) ----

class TestSubcommandNonModelType:
    def test_subcommand_with_str_type_raises(self):
        class BadSettings(BaseSettings):
            sub: Annotated[Union[str, None], _CliSubCommand]
            model_config = {'env_file': None}

        with pytest.raises(SettingsError, match='has type not derived from BaseModel'):
            CliSettingsSource(BadSettings, cli_parse_args=None)

    def test_subcommand_with_int_type_raises(self):
        class BadSettings(BaseSettings):
            sub: Annotated[Union[int, None], _CliSubCommand]
            model_config = {'env_file': None}

        with pytest.raises(SettingsError, match='has type not derived from BaseModel'):
            CliSettingsSource(BadSettings, cli_parse_args=None)


# ---- Tests: positional arg with multiple aliases raises error (lines 798-800) ----

class TestPositionalMultipleAliases:
    def test_positional_arg_with_multiple_aliases_raises(self):
        class BadSettings(BaseSettings):
            pos: CliPositionalArg[str] = Field(
                validation_alias=AliasChoices('pos', 'position')
            )
            model_config = {'env_file': None}

        with pytest.raises(SettingsError, match='positional argument.*has multiple aliases'):
            CliSettingsSource(BadSettings, cli_parse_args=None)


# ---- Tests: positional variadic arg (list type) goes to variadic list (lines 801-807) ----

class TestPositionalVariadicArg:
    def test_positional_list_arg_is_variadic(self):
        class Settings(BaseSettings):
            files: CliPositionalArg[list[str]]
            name: str = 'default'
            model_config = {'env_file': None}

        result = _sort_fields(Settings)
        field_names = [name for name, _ in result]
        # files is variadic positional, name is optional
        # Order: positional_args + positional_variadic_arg + subcommand_args + optional_args
        assert field_names == ['files', 'name']

    def test_positional_non_list_arg_is_not_variadic(self):
        class Settings(BaseSettings):
            pos: CliPositionalArg[str]
            name: str = 'default'
            model_config = {'env_file': None}

        result = _sort_fields(Settings)
        field_names = [name for name, _ in result]
        assert field_names == ['pos', 'name']

    def test_positional_set_arg_is_variadic(self):
        class Settings(BaseSettings):
            items: CliPositionalArg[set[str]]
            name: str = 'default'
            model_config = {'env_file': None}

        result = _sort_fields(Settings)
        field_names = [name for name, _ in result]
        assert field_names == ['items', 'name']

    def test_positional_dict_arg_is_variadic(self):
        class Settings(BaseSettings):
            mapping: CliPositionalArg[dict[str, str]]
            name: str = 'default'
            model_config = {'env_file': None}

        result = _sort_fields(Settings)
        field_names = [name for name, _ in result]
        assert field_names == ['mapping', 'name']


# ---- Tests: multiple variadic positional args raises error (lines 813-815) ----

class TestMultipleVariadicPositional:
    def test_multiple_variadic_positional_args_raises(self):
        class BadSettings(BaseSettings):
            files: CliPositionalArg[list[str]]
            dirs: CliPositionalArg[list[str]]
            model_config = {'env_file': None}

        with pytest.raises(SettingsError, match='has multiple variadic positional arguments'):
            CliSettingsSource(BadSettings, cli_parse_args=None)


# ---- Tests: variadic positional + subcommand conflict raises error (lines 816-818) ----

class TestVariadicPositionalAndSubcommandConflict:
    def test_variadic_positional_with_subcommand_raises(self):
        class BadSettings(BaseSettings):
            files: CliPositionalArg[list[str]]
            sub: CliSubCommand[Union[SubA, SubB]]
            model_config = {'env_file': None}

        with pytest.raises(SettingsError, match='has variadic positional arguments and subcommand arguments'):
            CliSettingsSource(BadSettings, cli_parse_args=None)


# ---- Tests: basic sorting order ----

class TestSortOrder:
    def test_positional_before_subcommand_before_optional(self):
        class Settings(BaseSettings):
            opt: str = 'default'
            sub: CliSubCommand[Union[SubA, SubB]]
            pos: CliPositionalArg[str]
            model_config = {'env_file': None}

        result = _sort_fields(Settings)
        field_names = [name for name, _ in result]
        # positional_args first, then subcommand_args, then optional_args
        assert field_names == ['pos', 'sub', 'opt']

    def test_variadic_positional_after_regular_positional(self):
        class Settings(BaseSettings):
            files: CliPositionalArg[list[str]]
            pos: CliPositionalArg[str]
            opt: str = 'default'
            model_config = {'env_file': None}

        result = _sort_fields(Settings)
        field_names = [name for name, _ in result]
        # positional_args + positional_variadic_arg + optional_args
        assert field_names == ['pos', 'files', 'opt']
