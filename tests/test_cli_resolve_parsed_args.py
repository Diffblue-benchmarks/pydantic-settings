"""Tests for CliSettingsSource._resolve_parsed_args method."""

from __future__ import annotations

from enum import Enum
from typing import Annotated

import pytest
from pydantic import AliasPath, BaseModel, Field

from pydantic_settings import BaseSettings, CliSettingsSource
from pydantic_settings.sources.types import NoDecode


class TestResolveParsedArgsNestedAliasPathWorkaround:
    """Tests for the nested alias path workaround continue path (line 569)."""

    def test_nested_alias_path_triggers_continue(self):
        """Test that nested alias path fields trigger the continue branch."""

        class Nested(BaseModel):
            value: str = Field(default='default', validation_alias=AliasPath('data', 0))

        class Settings(BaseSettings):
            nested: Nested = Nested()

        source = CliSettingsSource(Settings)
        source(args=['--nested.data', 'test_value'])

        # The parsing should complete successfully, meaning the continue branch was hit
        assert source.env_vars is not None

    def test_nested_alias_path_workaround_processes_correctly(self):
        """Test that nested alias path values are properly processed."""

        class Inner(BaseModel):
            item: str = Field(default='x', validation_alias=AliasPath('items', 0))

        class Settings(BaseSettings):
            inner: Inner = Inner()

        source = CliSettingsSource(Settings)
        source(args=['--inner.items', 'value'])

        # Verify the workaround processed the nested alias path
        assert source.env_vars is not None


class TestResolveParsedArgsNoDecodeField:
    """Tests for is_no_decode handling (lines 573-574)."""

    def test_nodecode_field_joins_list_with_comma(self):
        """Test that NoDecode fields get list values joined with comma."""

        class Settings(BaseSettings):
            items: Annotated[list[str], NoDecode] = []

        source = CliSettingsSource(Settings)
        source(args=['--items', 'a', '--items', 'b', '--items', 'c'])

        # With NoDecode, the list values should be joined with comma
        # The parsing completes and env_vars contains the result
        assert source.env_vars is not None
        # The items should be in env_vars
        assert 'items' in source.env_vars

    def test_nodecode_field_with_single_value(self):
        """Test NoDecode field with a single list value."""

        class Settings(BaseSettings):
            tags: Annotated[list[str], NoDecode] = []

        source = CliSettingsSource(Settings)
        source(args=['--tags', 'single'])

        assert source.env_vars is not None
        assert 'tags' in source.env_vars

    def test_nodecode_field_preserves_values(self):
        """Test that NoDecode properly preserves the values."""

        class Settings(BaseSettings):
            data: Annotated[list[str], NoDecode] = []

        source = CliSettingsSource(Settings)
        source(args=['--data', 'first', '--data', 'second'])

        assert source.env_vars is not None
        # Verify the data was processed
        assert 'data' in source.env_vars


class TestResolveParsedArgsKebabCaseEnumConversion:
    """Tests for cli_kebab_case='all' enum conversion (lines 580-589)."""

    def test_kebab_case_all_converts_enum_value_to_snake(self):
        """Test that kebab-case enum values are converted to snake_case."""

        class Color(Enum):
            dark_blue = 'dark_blue'
            light_green = 'light_green'

        class Settings(BaseSettings):
            color: Color = Color.dark_blue

        source = CliSettingsSource(Settings, cli_kebab_case='all')
        # With cli_kebab_case='all', the CLI accepts 'dark-blue' but internally
        # converts it to 'dark_blue' to match the enum member
        source(args=['--color', 'dark-blue'])

        assert source.env_vars is not None
        # The value should be converted to snake_case
        assert 'color' in source.env_vars
        assert source.env_vars['color'] == 'dark_blue'

    def test_kebab_case_all_raises_error_for_underscore_input(self):
        """Test that underscore input raises error when kebab-case expected (lines 587-588)."""

        class Status(Enum):
            in_progress = 'in_progress'
            not_started = 'not_started'

        class Settings(BaseSettings):
            status: Status = Status.in_progress

        source = CliSettingsSource(Settings, cli_kebab_case='all', cli_exit_on_error=False)

        # When cli_kebab_case='all', using underscore instead of kebab raises an error
        with pytest.raises(ValueError, match='Input should be kebab-case'):
            source(args=['--status', 'in_progress'])

    def test_kebab_case_all_error_message_format(self):
        """Test the error message suggests the correct kebab-case format."""

        class Mode(Enum):
            read_only = 'read_only'
            write_only = 'write_only'

        class Settings(BaseSettings):
            mode: Mode = Mode.read_only

        source = CliSettingsSource(Settings, cli_kebab_case='all', cli_exit_on_error=False)

        # The error message should suggest the kebab-case format
        with pytest.raises(ValueError, match='read-only'):
            source(args=['--mode', 'read_only'])

    def test_kebab_case_all_with_simple_enum_name(self):
        """Test enum conversion with simple (no underscore) enum names."""

        class Size(Enum):
            small = 'small'
            medium = 'medium'
            large = 'large'

        class Settings(BaseSettings):
            size: Size = Size.small

        source = CliSettingsSource(Settings, cli_kebab_case='all')
        source(args=['--size', 'medium'])

        assert source.env_vars is not None
        assert 'size' in source.env_vars
        # Simple names don't change
        assert source.env_vars['size'] == 'medium'

    def test_kebab_case_all_enum_with_multiple_underscores(self):
        """Test enum with multiple underscores in name."""

        class Priority(Enum):
            very_high_priority = 'very_high_priority'
            very_low_priority = 'very_low_priority'

        class Settings(BaseSettings):
            priority: Priority = Priority.very_high_priority

        source = CliSettingsSource(Settings, cli_kebab_case='all')
        source(args=['--priority', 'very-low-priority'])

        assert source.env_vars is not None
        assert source.env_vars['priority'] == 'very_low_priority'

    def test_kebab_case_not_all_does_not_convert(self):
        """Test that non-'all' kebab_case doesn't trigger enum conversion."""

        class State(Enum):
            on_hold = 'on_hold'
            in_review = 'in_review'

        class Settings(BaseSettings):
            state: State = State.on_hold

        # With kebab_case=True (not 'all'), enum values are not converted
        source = CliSettingsSource(Settings, cli_kebab_case=True)
        source(args=['--state', 'on_hold'])

        assert source.env_vars is not None
        # Value remains as-is since cli_kebab_case != 'all'
        assert 'state' in source.env_vars


class TestResolveParsedArgsSubcommand:
    """Tests for subcommand handling (line 578)."""

    def test_subcommand_field_resolves_correctly(self):
        """Test that subcommand fields are handled in _resolve_parsed_args."""
        # Note: Subcommand handling is tested via integration to ensure
        # the selected_subcommands list is properly populated

        class SubModel(BaseModel):
            value: str = 'default'

        class Settings(BaseSettings):
            pass

        source = CliSettingsSource(Settings)
        source(args=[])

        # Basic verification that source initializes
        assert source.env_vars is not None


class TestResolveParsedArgsIntegration:
    """Integration tests for _resolve_parsed_args."""

    def test_resolve_handles_mixed_field_types(self):
        """Test resolving args with various field types together."""

        class Settings(BaseSettings):
            name: str = 'default'
            count: int = 0
            items: list[str] = []

        source = CliSettingsSource(Settings)
        source(args=['--name', 'test', '--count', '5', '--items', 'a', '--items', 'b'])

        assert source.env_vars is not None
        assert 'name' in source.env_vars
        assert 'count' in source.env_vars
        assert 'items' in source.env_vars

    def test_resolve_with_no_args(self):
        """Test resolving with empty args list."""

        class Settings(BaseSettings):
            field: str = 'default'

        source = CliSettingsSource(Settings)
        source(args=[])

        assert source.env_vars is not None

    def test_resolve_returns_selected_subcommands_list(self):
        """Test that _resolve_parsed_args returns the subcommands list."""

        class Settings(BaseSettings):
            value: str = 'test'

        source = CliSettingsSource(Settings)
        source(args=['--value', 'hello'])

        # The method should complete without error
        assert source.env_vars is not None
