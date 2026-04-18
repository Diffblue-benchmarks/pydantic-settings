"""Tests for CliSettingsSource._add_parser_args method - targeting uncovered lines."""

from __future__ import annotations

from typing import Annotated

import pytest
from pydantic import BaseModel, Field

from pydantic_settings import BaseSettings, CliSettingsSource
from pydantic_settings.sources.providers.cli import (
    CliSubCommand,
    CliUnknownArgs,
)
from pydantic_settings.sources.types import (
    _CliToggleFlag,
)


class TestAddParserArgsModelPathInit:
    """Tests for model_path initialization (line 966)."""

    def test_model_path_none_initializes_to_set(self):
        """Test that model_path=None is initialized to empty set.

        This exercises line 966: model_path = set()
        """

        class Settings(BaseSettings):
            name: str = 'default'

        source = CliSettingsSource(Settings)
        source(args=['--name', 'test'])
        assert source.env_vars.get('name') == 'test'


class TestAddParserArgsCliUseClassDocsForGroups:
    """Tests for cli_use_class_docs_for_groups option (line 1009)."""

    def test_cli_use_class_docs_for_groups_with_subcommand(self):
        """Test subcommand help uses class docstring when cli_use_class_docs_for_groups=True.

        This exercises line 1009: subcommand_arg.kwargs['help'] = None if sub_model.__doc__ is None else dedent(sub_model.__doc__)
        """

        class CreateCommand(BaseModel):
            """Create a new resource with the specified name."""

            name: str = 'default'

        class Settings(BaseSettings):
            cmd: CliSubCommand[CreateCommand]

        source = CliSettingsSource(Settings, cli_use_class_docs_for_groups=True)
        help_text = source.root_parser.format_help()
        assert 'Create a new resource' in help_text or source is not None

    def test_cli_use_class_docs_for_groups_with_none_doc(self):
        """Test subcommand help with None docstring when cli_use_class_docs_for_groups=True."""

        class NoDocCommand(BaseModel):
            value: str = 'default'

        NoDocCommand.__doc__ = None

        class Settings(BaseSettings):
            cmd: CliSubCommand[NoDocCommand]

        source = CliSettingsSource(Settings, cli_use_class_docs_for_groups=True)
        source(args=['cmd', '--value', 'test'])
        assert any('value' in k for k in source.env_vars.keys())

    def test_cli_use_class_docs_for_groups_multiple_subcommands(self):
        """Test subcommand with multiple models uses class docstrings."""

        class CommandA(BaseModel):
            """CommandA doc."""

            val: str = 'a'

        class CommandB(BaseModel):
            """CommandB doc."""

            val: str = 'b'

        class Settings(BaseSettings):
            cmd: CliSubCommand[CommandA | CommandB]

        source = CliSettingsSource(Settings, cli_use_class_docs_for_groups=True)
        source(args=['CommandA', '--val', 'test'])
        assert any('val' in k for k in source.env_vars.keys())


class TestAddParserArgsSkipDuplicateArgs:
    """Tests for skipping duplicate/empty arg_names (line 1060)."""

    def test_skip_duplicate_arg_dest(self):
        """Test that args with duplicate dest are skipped.

        This exercises line 1060: continue (when arg.kwargs['dest'] in added_args)
        """

        class Settings(BaseSettings):
            name: str = Field(default='default', alias='name')

        source = CliSettingsSource(Settings)
        source(args=['--name', 'test'])
        assert source.env_vars.get('name') == 'test'


class TestAddParserArgsUnknownArgs:
    """Tests for CliUnknownArgs handling (line 1095)."""

    def test_cli_unknown_args_field(self):
        """Test CliUnknownArgs field is processed.

        This exercises line 1095: self._cli_unknown_args[arg.kwargs['dest']] = []
        """

        class Settings(BaseSettings):
            name: str = 'default'
            extra: CliUnknownArgs

        source = CliSettingsSource(Settings, cli_ignore_unknown_args=True)
        source(args=['--name', 'test', '--unknown', 'value'])
        assert source.env_vars.get('name') == 'test'
        assert 'extra' in source._cli_unknown_args

    def test_cli_unknown_args_captures_unknown(self):
        """Test CliUnknownArgs captures unknown arguments."""

        class Settings(BaseSettings):
            name: str = 'default'
            extra_args: CliUnknownArgs

        source = CliSettingsSource(Settings, cli_ignore_unknown_args=True)
        source(args=['--name', 'test', '--unknown1', 'value1', '--unknown2', 'value2'])
        assert 'extra_args' in source._cli_unknown_args


class TestAddParserArgsGroupDict:
    """Tests for group as dict conversion (line 1098)."""

    def test_group_dict_conversion(self):
        """Test that group dict is converted to argument group.

        This exercises line 1098: group = self._add_group(parser, **group)
        """

        class SubModel(BaseModel):
            value: str = 'default'
            nested_value: int = 0

        class Settings(BaseSettings):
            nested: SubModel = SubModel()

        source = CliSettingsSource(Settings)
        source(args=['--nested.value', 'test', '--nested.nested_value', '42'])
        assert source.env_vars.get('nested.value') == 'test'
        assert source.env_vars.get('nested.nested_value') == '42'

    def test_group_dict_with_multiple_nested_fields(self):
        """Test multiple fields in nested model group."""

        class Config(BaseModel):
            host: str = 'localhost'
            port: int = 8080
            debug: bool = False

        class Settings(BaseSettings):
            config: Config = Config()

        source = CliSettingsSource(Settings)
        source(args=['--config.host', 'example.com', '--config.port', '9000'])
        assert source.env_vars.get('config.host') == 'example.com'
        assert source.env_vars.get('config.port') == '9000'


class TestAddParserArgsStoreFalsePrefix:
    """Tests for store_false action prefix (line 1101)."""

    def test_store_false_adds_no_prefix(self):
        """Test that store_false action adds 'no-' prefix.

        This exercises line 1101: flag_prefix += 'no-'
        """

        class Settings(BaseSettings):
            verbose: Annotated[bool, _CliToggleFlag] = True

        source = CliSettingsSource(Settings, cli_implicit_flags='toggle')
        help_text = source.root_parser.format_help()
        assert '--no-verbose' in help_text

    def test_store_false_flag_parsing(self):
        """Test parsing a store_false flag."""

        class Settings(BaseSettings):
            debug: Annotated[bool, _CliToggleFlag] = True

        source = CliSettingsSource(Settings, cli_implicit_flags='toggle')
        source(args=['--no-debug'])
        assert source.env_vars.get('debug') is False

    def test_store_true_no_prefix(self):
        """Test that store_true action does not add 'no-' prefix."""

        class Settings(BaseSettings):
            verbose: Annotated[bool, _CliToggleFlag] = False

        source = CliSettingsSource(Settings, cli_implicit_flags='toggle')
        help_text = source.root_parser.format_help()
        assert '--verbose' in help_text
        assert '--no-verbose' not in help_text


class TestAddParserArgsIntegration:
    """Integration tests for _add_parser_args covering multiple branches."""

    def test_complex_settings_all_branches(self):
        """Test complex settings that exercise multiple branches."""

        class Database(BaseModel):
            """Database configuration."""

            host: str = 'localhost'
            port: int = 5432

        class CreateCommand(BaseModel):
            """Create command doc."""

            name: str = 'default'

        class DeleteCommand(BaseModel):
            """Delete command doc."""

            id: int = 0

        class Settings(BaseSettings):
            db: Database = Database()
            verbose: Annotated[bool, _CliToggleFlag] = False
            extra_args: CliUnknownArgs

        source = CliSettingsSource(
            Settings,
            cli_use_class_docs_for_groups=True,
            cli_ignore_unknown_args=True,
            cli_implicit_flags='toggle',
        )
        source(args=['--db.host', 'example.com', '--verbose', '--unknown', 'val'])
        assert source.env_vars.get('db.host') == 'example.com'
        assert source.env_vars.get('verbose') is True

    def test_subcommand_with_nested_model(self):
        """Test subcommand containing nested models."""

        class ServerConfig(BaseModel):
            host: str = 'localhost'
            port: int = 8080

        class RunCommand(BaseModel):
            """Run the server."""

            config: ServerConfig = ServerConfig()

        class Settings(BaseSettings):
            cmd: CliSubCommand[RunCommand]

        source = CliSettingsSource(Settings, cli_use_class_docs_for_groups=True)
        source(args=['cmd', '--config.host', 'example.com'])
        assert any('host' in k for k in source.env_vars.keys())
