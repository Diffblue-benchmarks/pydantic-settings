"""Tests for CliSettingsSource.add_group_method (lines 875-879, 883 in cli.py)."""
from __future__ import annotations

from argparse import ArgumentParser
from typing import Any

import pytest
from pydantic import BaseModel

from pydantic_settings import BaseSettings, CliSettingsSource
from pydantic_settings.exceptions import SettingsError
from pydantic_settings.sources.providers.cli import CliMutuallyExclusiveGroup


class MyMEGroup(CliMutuallyExclusiveGroup):
    option_a: str = ''
    option_b: str = ''


class SettingsWithMEGroup(BaseSettings):
    group: MyMEGroup = MyMEGroup()


def test_add_group_method_mutually_exclusive_creates_group():
    """Lines 875-877, 883: else branch sets title with '(mutually exclusive)' and returns ME group."""
    parser = ArgumentParser()
    source = CliSettingsSource(SettingsWithMEGroup, root_parser=parser, cli_parse_args=[])

    # After init, parser should have a mutually exclusive group added (line 883 path was taken)
    # We verify by checking if the source parsed correctly (no exceptions) and that the
    # argument group with the mutually exclusive suffix exists in the parser
    help_text = parser.format_help()
    assert 'mutually exclusive' in help_text


def test_add_group_method_mutually_exclusive_group_missing_method():
    """Lines 878-882: raise SettingsError when group object lacks add_mutually_exclusive_group."""

    def custom_add_argument_group(parser: Any, **kwargs: Any) -> Any:
        # Return an object without add_mutually_exclusive_group to trigger the error
        class GroupWithoutMEMethod:
            def add_argument(self, *args: Any, **kwargs: Any) -> None:
                pass

        return GroupWithoutMEMethod()

    parser = ArgumentParser()
    with pytest.raises(
        SettingsError,
        match='group object is missing add_mutually_exclusive_group but is needed for connecting',
    ):
        CliSettingsSource(
            SettingsWithMEGroup,
            root_parser=parser,
            cli_parse_args=[],
            add_argument_group_method=custom_add_argument_group,
        )


def test_add_group_method_regular_group_not_mutually_exclusive():
    """Lines 870-873: if branch (not mutually exclusive) pops required and calls add_argument_group."""

    class RegularModel(BaseModel):
        x: int = 1

    class SettingsWithRegular(BaseSettings):
        model: RegularModel = RegularModel()

    parser = ArgumentParser()
    # Should not raise; regular (non-ME) group path
    source = CliSettingsSource(SettingsWithRegular, root_parser=parser, cli_parse_args=[])
    help_text = parser.format_help()
    assert 'mutually exclusive' not in help_text
