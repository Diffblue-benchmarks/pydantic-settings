"""Tests targeting uncovered lines in CliSettingsSource._add_parser_args."""

from typing import Literal, Union

import pytest
from pydantic import BaseModel, Field

from pydantic_settings import (
    BaseSettings,
    CliPositionalArg,
    CliSettingsSource,
    CliSubCommand,
    CliUnknownArgs,
)
from pydantic_settings.sources.providers.cli import _CliInternalArgParser


# ---- Models ----


class SubCmdWithDocs(BaseModel):
    """This subcommand has documentation."""

    value: str = 'doc_val'


class SubCmdNoDocs(BaseModel):
    other: str = 'no_doc'


class SettingsSubcmdClassDocs(BaseSettings):
    sub: CliSubCommand[Union[SubCmdWithDocs, SubCmdNoDocs]]

    model_config = {'env_file': None, 'cli_use_class_docs_for_groups': True}


class CatModel(BaseModel):
    pet_type: Literal['cat']
    meow: str = 'loud'


class DogModel(BaseModel):
    pet_type: Literal['dog']
    bark: str = 'woof'


class SettingsDiscriminator(BaseSettings):
    pet: Union[CatModel, DogModel] = Field(
        default=CatModel(pet_type='cat'),
        discriminator='pet_type',
    )

    model_config = {'env_file': None}


class SettingsPositional(BaseSettings):
    name: CliPositionalArg[str]

    model_config = {'env_file': None}


class SettingsUnknownArgs(BaseSettings):
    known_field: str = 'default'
    extra: CliUnknownArgs

    model_config = {'env_file': None, 'cli_ignore_unknown_args': True}


class SettingsToggleTrue(BaseSettings):
    verbose: bool = True

    model_config = {'env_file': None, 'cli_implicit_flags': 'toggle'}


class EmptyModel(BaseModel):
    pass


class SimpleFieldModel(BaseModel):
    field_a: str = 'default'


class SimpleSettings(BaseSettings):
    name: str = 'default'

    model_config = {'env_file': None}


# ---- Tests ----


class TestSubcommandClassDocsForGroups:
    """Cover line 1009: cli_use_class_docs_for_groups sets subcommand help from docstring."""

    def test_subcommand_with_docs_uses_docstring(self):
        settings = SettingsSubcmdClassDocs(_cli_parse_args=['SubCmdWithDocs', '--value', 'test'])
        assert isinstance(settings.sub, SubCmdWithDocs)
        assert settings.sub.value == 'test'

    def test_subcommand_without_docs_uses_none(self):
        settings = SettingsSubcmdClassDocs(_cli_parse_args=['SubCmdNoDocs', '--other', 'val'])
        assert isinstance(settings.sub, SubCmdNoDocs)
        assert settings.sub.other == 'val'


class TestDiscriminatorUnionSkip:
    """Cover line 1060: continue when discriminator arg names are empty for non-last model."""

    def test_discriminator_union_default(self):
        settings = SettingsDiscriminator(_cli_parse_args=[])
        assert settings.pet.pet_type == 'cat'

    def test_discriminator_union_override_json(self):
        settings = SettingsDiscriminator(
            _cli_parse_args=['--pet', '{"pet_type": "dog", "bark": "ruff"}'],
        )
        assert settings.pet.pet_type == 'dog'
        assert settings.pet.bark == 'ruff'


class TestPositionalArg:
    """Cover line 1065: _CliPositionalArg triggers positional arg conversion."""

    def test_positional_arg_parsed(self):
        settings = SettingsPositional(_cli_parse_args=['hello'])
        assert settings.name == 'hello'


class TestUnknownArgsField:
    """Cover line 1095: _CliUnknownArgs registers dest in _cli_unknown_args."""

    def test_unknown_args_collected(self):
        settings = SettingsUnknownArgs(
            _cli_parse_args=['--known_field', 'val', '--surprise', 'hi'],
        )
        assert settings.known_field == 'val'

    def test_unknown_args_empty_when_none_extra(self):
        settings = SettingsUnknownArgs(_cli_parse_args=['--known_field', 'test'])
        assert settings.known_field == 'test'
        assert settings.extra == []


class TestToggleFlagStoreFalse:
    """Cover line 1101: store_false action prepends 'no-' to flag prefix."""

    def test_toggle_flag_default_true_negated(self):
        settings = SettingsToggleTrue(_cli_parse_args=['--no-verbose'])
        assert settings.verbose is False

    def test_toggle_flag_default_true_no_arg(self):
        settings = SettingsToggleTrue(_cli_parse_args=[])
        assert settings.verbose is True


class TestModelPathNone:
    """Cover line 966: model_path initialized from None to empty set."""

    def test_model_path_none_initializes_set(self):
        source = CliSettingsSource(SimpleSettings, cli_parse_args=False)
        fresh_parser = _CliInternalArgParser(add_help=False)
        result = source._add_parser_args(
            parser=fresh_parser,
            model=EmptyModel,
            added_args=[],
            arg_prefix='',
            subcommand_prefix='',
            group=None,
            alias_prefixes=[],
            model_default=None,
            model_path=None,
        )
        assert result is fresh_parser


class TestGroupDictConversion:
    """Cover line 1098: group passed as dict is converted to argparse group."""

    def test_group_dict_creates_group(self):
        source = CliSettingsSource(SimpleSettings, cli_parse_args=False)
        fresh_parser = _CliInternalArgParser(add_help=False)
        group_dict = {
            'title': 'test group',
            'description': None,
            'required': False,
            '_is_cli_mutually_exclusive_group': False,
        }
        result = source._add_parser_args(
            parser=fresh_parser,
            model=SimpleFieldModel,
            added_args=[],
            arg_prefix='',
            subcommand_prefix='',
            group=group_dict,
            alias_prefixes=[],
            model_default=None,
        )
        assert result is fresh_parser
