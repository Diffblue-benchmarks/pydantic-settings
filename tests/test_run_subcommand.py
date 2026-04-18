"""Tests for CliApp.run_subcommand covering lines 775-777, 786-789, 791."""

from __future__ import annotations

from typing import Annotated, Any
from unittest.mock import patch

import pytest
from pydantic import BaseModel

from pydantic_settings import BaseSettings, CliApp, CliSettingsSource, SettingsError
from pydantic_settings.main import SettingsConfigDict
from pydantic_settings.sources.types import _CliSubCommand


class SubCmd(BaseModel):
    val: str = 'sub_default'

    def cli_cmd(self) -> None:
        pass


class MySettings(BaseSettings):
    model_config = SettingsConfigDict(cli_exit_on_error=False)
    sub: Annotated[SubCmd | None, _CliSubCommand]


class MySettingsExitOnError(BaseSettings):
    model_config = SettingsConfigDict(cli_exit_on_error=True)
    sub: Annotated[SubCmd | None, _CliSubCommand]


class TestRunSubcommandNotInStack:
    """Tests for when model is NOT in _subcommand_stack (lines 775-777)
    combined with error handling (lines 786-789)."""

    def test_raises_settings_error_with_help_text(self) -> None:
        """When model not in stack, no subcommand set, cli_exit_on_error=False:
        hits lines 775-777 (else branch) and 786-789 (error with help text)."""
        model = MySettings.model_construct(sub=None)
        with pytest.raises(SettingsError, match='CLI subcommand is required'):
            CliApp.run_subcommand(model, cli_exit_on_error=False)

    def test_raises_system_exit_with_help_text(self) -> None:
        """When model not in stack, no subcommand set, cli_exit_on_error=True:
        hits lines 775-777 (else branch) and 786-789 (SystemExit with help text)."""
        model = MySettingsExitOnError.model_construct(sub=None)
        with pytest.raises(SystemExit):
            CliApp.run_subcommand(model, cli_exit_on_error=True)

    def test_error_message_includes_help(self) -> None:
        """Verify the enriched error message contains both the error and help text."""
        model = MySettings.model_construct(sub=None)
        with pytest.raises(SettingsError) as exc_info:
            CliApp.run_subcommand(model, cli_exit_on_error=False)
        error_msg = str(exc_info.value)
        assert 'CLI subcommand is required' in error_msg

    def test_uses_cli_exit_on_error_from_source_when_none(self) -> None:
        """When cli_exit_on_error is None, uses value from cli_settings_source.
        MySettings has cli_exit_on_error=False, so SettingsError is raised."""
        model = MySettings.model_construct(sub=None)
        with pytest.raises(SettingsError, match='CLI subcommand is required'):
            CliApp.run_subcommand(model, cli_exit_on_error=None)


class TestRunSubcommandErrorReraise:
    """Tests for error re-raise path (line 791)."""

    def test_reraises_error_when_format_help_is_none(self) -> None:
        """When _format_help is None, the error is re-raised directly (line 791)."""
        model = MySettings.model_construct(sub=None)
        cli_settings_source = CliSettingsSource[Any](
            CliApp._get_base_settings_cls(type(model)),
        )
        cli_settings_source._format_help = None
        parser = cli_settings_source.root_parser
        CliApp._subcommand_stack[id(model)] = (cli_settings_source, parser, ':subcommand')
        try:
            with pytest.raises(SettingsError, match='CLI subcommand is required'):
                CliApp.run_subcommand(model, cli_exit_on_error=False)
        finally:
            CliApp._subcommand_stack.pop(id(model), None)

    def test_reraises_system_exit_when_format_help_is_none(self) -> None:
        """When _format_help is None, SystemExit is re-raised directly (line 791)."""
        model = MySettingsExitOnError.model_construct(sub=None)
        cli_settings_source = CliSettingsSource[Any](
            CliApp._get_base_settings_cls(type(model)),
        )
        cli_settings_source._format_help = None
        parser = cli_settings_source.root_parser
        CliApp._subcommand_stack[id(model)] = (cli_settings_source, parser, ':subcommand')
        try:
            with pytest.raises(SystemExit):
                CliApp.run_subcommand(model, cli_exit_on_error=True)
        finally:
            CliApp._subcommand_stack.pop(id(model), None)

    def test_reraises_error_with_cause(self) -> None:
        """When error has __cause__ set, re-raises directly (line 791)."""
        model = MySettings.model_construct(sub=None)
        cli_settings_source = CliSettingsSource[Any](
            CliApp._get_base_settings_cls(type(model)),
        )
        parser = cli_settings_source.root_parser
        CliApp._subcommand_stack[id(model)] = (cli_settings_source, parser, ':subcommand')

        def mock_get_subcommand(
            model: Any,
            is_required: bool = True,
            cli_exit_on_error: bool | None = None,
            _suppress_errors: list | None = None,
        ) -> None:
            err = SettingsError('subcommand required')
            err.__cause__ = ValueError('original cause')
            if _suppress_errors is not None:
                _suppress_errors.append(err)
            return None

        try:
            with patch('pydantic_settings.main.get_subcommand', side_effect=mock_get_subcommand):
                with pytest.raises(SettingsError, match='subcommand required'):
                    CliApp.run_subcommand(model, cli_exit_on_error=False)
        finally:
            CliApp._subcommand_stack.pop(id(model), None)
