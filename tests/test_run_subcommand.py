"""Tests for CliApp.run_subcommand method - targeting uncovered lines."""
from typing import Union

import pytest
from pydantic import BaseModel

from pydantic_settings import BaseSettings, CliApp
from pydantic_settings.exceptions import SettingsError
from pydantic_settings.sources import CliSubCommand


class TestRunSubcommandWithSubcommandStack:
    """Tests for run_subcommand when model id is in _subcommand_stack (line 773)."""

    def test_run_subcommand_from_subcommand_stack(self):
        """Test run_subcommand retrieves from _subcommand_stack when model id exists."""

        class SubCmd(BaseModel):
            name: str = 'default'

            def cli_cmd(self):
                pass

        class MainSettings(BaseSettings):
            sub: CliSubCommand[SubCmd]

            def cli_cmd(self):
                CliApp.run_subcommand(self)

        result = CliApp.run(MainSettings, cli_args=['sub', '--name', 'test'])
        assert result.sub is not None
        assert result.sub.name == 'test'


class TestRunSubcommandWithErrorContext:
    """Tests for run_subcommand when error has cause/context (line 791)."""

    def test_run_subcommand_error_with_context(self):
        """Test run_subcommand re-raises error when it has context."""

        class MySettings(BaseSettings):
            name: str = 'default'

        settings = MySettings()

        with pytest.raises((SystemExit, SettingsError)):
            CliApp.run_subcommand(settings, cli_exit_on_error=False)


class TestRunSubcommandSuccessPath:
    """Tests for run_subcommand success path (lines 793-802)."""

    def test_run_subcommand_executes_subcommand_cli_cmd(self):
        """Test run_subcommand successfully executes subcommand's cli_cmd."""
        execution_log = []

        class SubCmd(BaseModel):
            value: int = 42

            def cli_cmd(self):
                execution_log.append(f'executed with value={self.value}')

        class MainSettings(BaseSettings):
            sub: CliSubCommand[SubCmd]

            def cli_cmd(self):
                return CliApp.run_subcommand(self)

        result = CliApp.run(MainSettings, cli_args=['sub', '--value', '100'])
        assert result.sub is not None
        assert result.sub.value == 100
        assert execution_log == ['executed with value=100']

    def test_run_subcommand_nested_subcommands(self):
        """Test run_subcommand works with nested subcommands."""
        execution_log = []

        class NestedCmd(BaseModel):
            nested_val: str = 'nested'

            def cli_cmd(self):
                execution_log.append(f'nested: {self.nested_val}')

        class SubCmd(BaseModel):
            nested: CliSubCommand[NestedCmd]

            def cli_cmd(self):
                execution_log.append('sub executed')
                if self.nested is not None:
                    CliApp.run_subcommand(self)

        class MainSettings(BaseSettings):
            sub: CliSubCommand[SubCmd]

            def cli_cmd(self):
                if self.sub is not None:
                    CliApp.run_subcommand(self)

        result = CliApp.run(
            MainSettings,
            cli_args=['sub', 'nested', '--nested_val', 'deep']
        )
        assert result.sub is not None
        assert result.sub.nested is not None
        assert result.sub.nested.nested_val == 'deep'
        assert 'sub executed' in execution_log
        assert 'nested: deep' in execution_log

    def test_run_subcommand_with_union_subcommand(self):
        """Test run_subcommand with union of subcommand types."""
        execution_log = []

        class CmdA(BaseModel):
            a_val: str = 'a'

            def cli_cmd(self):
                execution_log.append(f'cmd_a: {self.a_val}')

        class CmdB(BaseModel):
            b_val: str = 'b'

            def cli_cmd(self):
                execution_log.append(f'cmd_b: {self.b_val}')

        class MainSettings(BaseSettings):
            cmd: CliSubCommand[Union[CmdA, CmdB]]

            def cli_cmd(self):
                if self.cmd is not None:
                    CliApp.run_subcommand(self)

        # Use snake_case for CLI arguments (matching CliApp defaults)
        result = CliApp.run(MainSettings, cli_args=['CmdA', '--a_val', 'test_a'])
        assert result.cmd is not None
        assert result.cmd.a_val == 'test_a'
        assert 'cmd_a: test_a' in execution_log

        execution_log.clear()
        result = CliApp.run(MainSettings, cli_args=['CmdB', '--b_val', 'test_b'])
        assert result.cmd is not None
        assert result.cmd.b_val == 'test_b'
        assert 'cmd_b: test_b' in execution_log

    def test_run_subcommand_cleans_up_stack_on_success(self):
        """Test that _subcommand_stack is cleaned up after successful execution."""

        class SubCmd(BaseModel):
            val: str = 'test'

            def cli_cmd(self):
                pass

        class MainSettings(BaseSettings):
            sub: CliSubCommand[SubCmd]

            def cli_cmd(self):
                CliApp.run_subcommand(self)

        initial_stack_size = len(CliApp._subcommand_stack)
        CliApp.run(MainSettings, cli_args=['sub'])
        assert len(CliApp._subcommand_stack) == initial_stack_size

    def test_run_subcommand_cleans_up_stack_on_exception(self):
        """Test that _subcommand_stack is cleaned up even if cli_cmd raises."""

        class SubCmd(BaseModel):
            val: str = 'test'

            def cli_cmd(self):
                raise ValueError('intentional error')

        class MainSettings(BaseSettings):
            sub: CliSubCommand[SubCmd]

            def cli_cmd(self):
                CliApp.run_subcommand(self)

        initial_stack_size = len(CliApp._subcommand_stack)
        with pytest.raises(ValueError, match='intentional error'):
            CliApp.run(MainSettings, cli_args=['sub'])
        assert len(CliApp._subcommand_stack) == initial_stack_size

    def test_run_subcommand_returns_subcommand_model(self):
        """Test run_subcommand returns the subcommand model."""
        returned_model = []

        class SubCmd(BaseModel):
            val: int = 123

            def cli_cmd(self):
                pass

        class MainSettings(BaseSettings):
            sub: CliSubCommand[SubCmd]

            def cli_cmd(self):
                result = CliApp.run_subcommand(self)
                returned_model.append(result)

        CliApp.run(MainSettings, cli_args=['sub', '--val', '456'])
        assert len(returned_model) == 1
        assert returned_model[0].val == 456


class TestRunSubcommandDirectCall:
    """Tests for calling run_subcommand directly on an instance."""

    def test_run_subcommand_direct_call_without_stack(self):
        """Test run_subcommand called directly on a model instance not in stack."""

        class SubCmd(BaseModel):
            name: str = 'test'

            def cli_cmd(self):
                pass

        class MainSettings(BaseSettings):
            sub: CliSubCommand[SubCmd]

        settings = MainSettings(_cli_parse_args=['sub', '--name', 'direct'])
        result = CliApp.run_subcommand(settings)
        assert result.name == 'direct'
