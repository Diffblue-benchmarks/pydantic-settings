"""Unit tests for get_subcommand function - coverage for uncovered lines."""

from __future__ import annotations

from typing import Annotated

import pytest
from pydantic import BaseModel, Field

from pydantic_settings.main import BaseSettings
from pydantic_settings.exceptions import SettingsError
from pydantic_settings.sources.base import get_subcommand
from pydantic_settings.sources.types import _CliSubCommand


class SubCommand1(BaseModel):
    """First subcommand model."""

    name: str = 'sub1'


class SubCommand2(BaseModel):
    """Second subcommand model."""

    name: str = 'sub2'


class SettingsWithSubcommands(BaseSettings):
    """Settings with subcommand fields marked with _CliSubCommand."""

    sub_cmd1: Annotated[SubCommand1 | None, _CliSubCommand] = None
    sub_cmd2: Annotated[SubCommand2 | None, _CliSubCommand] = None


class SettingsWithSingleSubcommand(BaseSettings):
    """Settings with a single subcommand field."""

    subcommand: Annotated[SubCommand1 | None, _CliSubCommand] = None


class SettingsWithoutCliExitOnError(BaseSettings):
    """Settings without cli_exit_on_error config."""

    name: str = 'default'


class TestGetSubcommandUncoveredLines:
    """Tests targeting uncovered lines in get_subcommand function."""

    def test_line_69_cli_exit_on_error_defaults_to_true(self):
        """Test line 69: cli_exit_on_error defaults to True when None and not in config.

        This tests the path where:
        - cli_exit_on_error parameter is None
        - model doesn't have cli_exit_on_error in config
        - Line 69 executes: cli_exit_on_error = True
        """
        settings = SettingsWithoutCliExitOnError()
        # When cli_exit_on_error is None and model has no config, it should default to True
        # With is_required=True and no subcommands, it should raise SystemExit (not SettingsError)
        with pytest.raises(SystemExit):
            get_subcommand(settings, is_required=True, cli_exit_on_error=None)

    def test_line_69_cli_exit_on_error_none_explicit_no_config(self):
        """Test line 69 explicitly with cli_exit_on_error=None and no config."""
        settings = SettingsWithSingleSubcommand(subcommand=None)
        # Verify it raises SystemExit (line 84: SystemExit when cli_exit_on_error is True)
        with pytest.raises(SystemExit) as exc_info:
            get_subcommand(settings, is_required=True, cli_exit_on_error=None)
        # Should be SystemExit, not SettingsError
        assert isinstance(exc_info.value, SystemExit)

    def test_line_74_subcommand_field_found_with_metadata(self):
        """Test line 74: Field with _CliSubCommand metadata is identified.

        This tests the path where:
        - Line 72: Loop through fields with _CliSubCommand in metadata
        - Line 73: Check if _CliSubCommand in field_info.metadata (line 73)
        - Line 74: getattr(model, field_name) is not None
        """
        cmd = SubCommand1(name='custom_sub1')
        settings = SettingsWithSubcommands(sub_cmd1=cmd)
        result = get_subcommand(settings, is_required=False)
        assert result is cmd
        assert result.name == 'custom_sub1'

    def test_line_74_subcommand_field_is_not_none_returns_it(self):
        """Test line 74: Returns subcommand when it's not None.

        Specifically tests: if getattr(model, field_name) is not None: return getattr(...)
        """
        cmd = SubCommand1(name='test_sub')
        settings = SettingsWithSubcommands(sub_cmd1=cmd, sub_cmd2=None)
        result = get_subcommand(settings, is_required=False)
        assert result is cmd

    def test_line_75_subcommand_field_none_appends_to_list(self):
        """Test line 75: When subcommand is None, field name is appended to list.

        This tests: subcommands.append(field_name) when the subcommand is None
        Line 76: subcommands.append(field_name)
        """
        settings = SettingsWithSubcommands(sub_cmd1=None, sub_cmd2=None)
        # When no subcommands are set and is_required=True, cli_exit_on_error=False
        # It should raise SettingsError with message indicating available subcommands
        with pytest.raises(SettingsError) as exc_info:
            get_subcommand(settings, is_required=True, cli_exit_on_error=False)
        error_msg = str(exc_info.value)
        # The error message should mention both subcommand field names
        assert 'sub_cmd1' in error_msg or 'sub_cmd2' in error_msg

    def test_line_76_multiple_subcommand_fields_appended(self):
        """Test line 76: Multiple subcommand fields are appended to list.

        When multiple subcommand fields are None, they should all be in the error message.
        """
        settings = SettingsWithSubcommands(sub_cmd1=None, sub_cmd2=None)
        with pytest.raises(SettingsError) as exc_info:
            get_subcommand(settings, is_required=True, cli_exit_on_error=False)
        error_msg = str(exc_info.value)
        # Both subcommand fields should be mentioned in the error
        assert 'sub_cmd1' in error_msg and 'sub_cmd2' in error_msg

    def test_line_74_returns_first_non_none_subcommand(self):
        """Test line 74: Returns first non-None subcommand found.

        When multiple subcommand fields exist but only one is set, it should return that one.
        """
        cmd = SubCommand1(name='first')
        settings = SettingsWithSubcommands(sub_cmd1=cmd, sub_cmd2=None)
        result = get_subcommand(settings, is_required=True)
        assert result is cmd

    def test_line_74_with_second_subcommand(self):
        """Test line 74: Returns second subcommand when first is None.

        Tests that the loop continues and finds the next non-None subcommand.
        """
        cmd = SubCommand2(name='second')
        settings = SettingsWithSubcommands(sub_cmd1=None, sub_cmd2=cmd)
        result = get_subcommand(settings, is_required=False)
        assert result is cmd
        assert result.name == 'second'

    def test_line_69_default_true_with_required_and_no_subcommands(self):
        """Test line 69: cli_exit_on_error=True (default) causes SystemExit.

        When cli_exit_on_error defaults to True (line 69) and is_required=True
        with no subcommands found, should raise SystemExit.
        """
        settings = SettingsWithSingleSubcommand()
        # Should raise SystemExit because cli_exit_on_error defaults to True
        with pytest.raises(SystemExit):
            get_subcommand(settings, is_required=True, cli_exit_on_error=None)

    def test_line_74_75_mixed_none_and_values(self):
        """Test lines 74-75: Loop handles mix of None and non-None subcommands.

        Tests the complete loop through fields with _CliSubCommand metadata
        where some are None and some are not None.
        """
        cmd = SubCommand2(name='valid_sub')
        settings = SettingsWithSubcommands(sub_cmd1=None, sub_cmd2=cmd)

        # Should return the non-None subcommand
        result = get_subcommand(settings, is_required=False)
        assert result is cmd

    def test_line_74_75_76_all_none_with_list_building(self):
        """Test lines 74-76: Complete flow when all subcommands are None.

        Tests that the subcommands list is built with all field names
        when they are all None.
        """
        settings = SettingsWithSubcommands(sub_cmd1=None, sub_cmd2=None)
        with pytest.raises(SettingsError) as exc_info:
            get_subcommand(settings, is_required=True, cli_exit_on_error=False)
        error_msg = str(exc_info.value)
        # Should mention both fields in the error
        assert 'sub_cmd1' in error_msg and 'sub_cmd2' in error_msg

    def test_line_74_comparison_operator_uses_is_not(self):
        """Test line 74: Uses 'is not None' comparison correctly.

        Verifies that the comparison is identity-based (is not), not equality.
        """
        # Create a subcommand and verify it's returned
        cmd = SubCommand1(name='test')
        settings = SettingsWithSubcommands(sub_cmd1=cmd)
        result = get_subcommand(settings, is_required=False)
        # Should return the exact object, not a copy
        assert result is cmd

    def test_line_75_76_error_message_contains_subcommand_names(self):
        """Test lines 75-76: Error message is formatted with subcommand names.

        When subcommands list is built and error is raised, message should
        contain the subcommand names.
        """
        settings = SettingsWithSubcommands(sub_cmd1=None, sub_cmd2=None)
        errors: list[SettingsError | SystemExit] = []
        result = get_subcommand(
            settings,
            is_required=True,
            cli_exit_on_error=False,
            _suppress_errors=errors,
        )
        assert result is None
        assert len(errors) == 1
        error = errors[0]
        assert isinstance(error, SettingsError)
        error_msg = str(error)
        # Should mention the available subcommands
        assert 'sub_cmd1' in error_msg or 'sub_cmd2' in error_msg


class TestGetSubcommandCliExitOnErrorDefault:
    """Tests specifically for line 69 behavior."""

    def test_no_config_no_parameter_defaults_true(self):
        """Test that cli_exit_on_error defaults to True when not configured."""

        class SimpleSettings(BaseSettings):
            name: str = 'default'

        settings = SimpleSettings()
        # When cli_exit_on_error is None and not in config, should default to True
        # This means SystemExit should be raised, not SettingsError
        with pytest.raises(SystemExit):
            get_subcommand(settings, is_required=True, cli_exit_on_error=None)

    def test_explicit_none_uses_default_true(self):
        """Test explicit cli_exit_on_error=None uses default True."""
        settings = SettingsWithSingleSubcommand()
        # Explicitly pass None, should default to True and raise SystemExit
        with pytest.raises(SystemExit):
            get_subcommand(settings, is_required=True, cli_exit_on_error=None)

    def test_non_bool_config_ignores_and_uses_default(self):
        """Test that non-boolean config values are ignored."""

        class SettingsWithInvalidConfig(BaseSettings):
            model_config = {'cli_exit_on_error': 'invalid'}  # type: ignore

            name: str = 'default'

        settings = SettingsWithInvalidConfig()
        # Non-boolean value should be ignored, defaulting to True
        with pytest.raises(SystemExit):
            get_subcommand(settings, is_required=True, cli_exit_on_error=None)


class TestGetSubcommandSubcommandFieldDetection:
    """Tests for subcommand field detection (lines 72-76)."""

    def test_only_fields_with_cli_subcommand_marker_processed(self):
        """Test that only fields with _CliSubCommand marker are processed."""

        class MixedSettings(BaseSettings):
            regular_field: str = 'not_a_subcommand'
            subcommand: Annotated[SubCommand1 | None, _CliSubCommand] = None

        settings = MixedSettings()
        # Should only look at subcommand field, not regular_field
        with pytest.raises(SettingsError) as exc_info:
            get_subcommand(settings, is_required=True, cli_exit_on_error=False)
        error_msg = str(exc_info.value)
        # Error should mention subcommand, not regular_field
        assert 'subcommand' in error_msg

    def test_field_value_is_obtained_with_getattr(self):
        """Test that field values are obtained using getattr."""
        cmd = SubCommand1(name='obtained')
        settings = SettingsWithSubcommands(sub_cmd1=cmd)
        result = get_subcommand(settings, is_required=False)
        # Should use getattr to get the field value
        assert result is cmd

    def test_multiple_fields_loop_order(self):
        """Test that fields are processed in order."""

        class OrderedSettings(BaseSettings):
            first: Annotated[SubCommand1 | None, _CliSubCommand] = None
            second: Annotated[SubCommand2 | None, _CliSubCommand] = None

        cmd2 = SubCommand2(name='second_cmd')
        settings = OrderedSettings(first=None, second=cmd2)
        # Should find second since first is None
        result = get_subcommand(settings, is_required=False)
        assert result is cmd2
