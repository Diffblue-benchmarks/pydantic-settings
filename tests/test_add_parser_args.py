"""Tests for CliSettingsSource._add_parser_args covering previously uncovered branches."""
from __future__ import annotations

from argparse import ArgumentParser
from typing import Annotated, List

import pytest
from pydantic import BaseModel, Field
from pydantic_core import PydanticUndefined

from pydantic_settings import BaseSettings, CliSettingsSource, CliUnknownArgs
from pydantic_settings.sources.providers.cli import CliSubCommand


# --- Model definitions ---


class SimpleModel(BaseSettings):
    name: str = 'default'


class SubCmdWithDoc(BaseModel):
    """Sub command documentation string."""

    x: int = 1


class SubCmdNoDoc(BaseModel):
    x: int = 1


class SubCmdSettings(BaseSettings):
    cmd: CliSubCommand[SubCmdWithDoc]


class SubCmdNoDocSettings(BaseSettings):
    cmd: CliSubCommand[SubCmdNoDoc]


class SettingsWithUnknownArgs(BaseSettings):
    extra: CliUnknownArgs


class SettingsWithToggleFlag(BaseSettings):
    verbose: bool = True


# --- Tests for model_path=None branch (line 966) ---


def test_add_parser_args_model_path_none_initializes_set():
    source = CliSettingsSource(SimpleModel, cli_parse_args=[])
    parser = ArgumentParser()
    result = source._add_parser_args(
        parser=parser,
        model=SimpleModel,
        added_args=[],
        arg_prefix='',
        subcommand_prefix='',
        group=None,
        alias_prefixes=[],
        model_default=PydanticUndefined,
        model_path=None,
    )
    assert result is parser


# --- Tests for cli_use_class_docs_for_groups with subcommand (line 1009) ---


def test_add_parser_args_cli_use_class_docs_for_groups_with_doc():
    source = CliSettingsSource(
        SubCmdSettings,
        cli_parse_args=['cmd'],
        cli_use_class_docs_for_groups=True,
    )
    result = source()
    assert result is not None


def test_add_parser_args_cli_use_class_docs_for_groups_no_doc():
    source = CliSettingsSource(
        SubCmdNoDocSettings,
        cli_parse_args=['cmd'],
        cli_use_class_docs_for_groups=True,
    )
    result = source()
    assert result is not None


# --- Tests for continue branch (line 1060) ---


def test_add_parser_args_skips_dest_already_in_added_args():
    source = CliSettingsSource(SimpleModel, cli_parse_args=[])
    parser = ArgumentParser()
    result = source._add_parser_args(
        parser=parser,
        model=SimpleModel,
        added_args=['name'],
        arg_prefix='',
        subcommand_prefix='',
        group=None,
        alias_prefixes=[],
        model_default=PydanticUndefined,
        model_path=set(),
    )
    assert result is parser


# --- Tests for CliUnknownArgs branch (line 1095) ---


def test_add_parser_args_cli_unknown_args_field():
    source = CliSettingsSource(
        SettingsWithUnknownArgs,
        cli_parse_args=[],
        cli_ignore_unknown_args=True,
    )
    result = source()
    assert result is not None


def test_add_parser_args_cli_unknown_args_populates_dict():
    source = CliSettingsSource(
        SettingsWithUnknownArgs,
        cli_parse_args=[],
        cli_ignore_unknown_args=True,
    )
    assert 'extra' in source._cli_unknown_args


# --- Tests for group as dict branch (line 1098) ---


def test_add_parser_args_group_as_dict_creates_group():
    source = CliSettingsSource(SimpleModel, cli_parse_args=[])
    parser = ArgumentParser()
    group_dict = {
        'title': 'test group',
        'description': None,
        'required': False,
        '_is_cli_mutually_exclusive_group': False,
    }
    result = source._add_parser_args(
        parser=parser,
        model=SimpleModel,
        added_args=[],
        arg_prefix='',
        subcommand_prefix='',
        group=group_dict,
        alias_prefixes=[],
        model_default=PydanticUndefined,
        model_path=set(),
    )
    assert result is parser


# --- Tests for store_false flag prefix (line 1101) ---


def test_add_parser_args_store_false_adds_no_prefix():
    source = CliSettingsSource(
        SettingsWithToggleFlag,
        cli_parse_args=['--no-verbose'],
        cli_implicit_flags='toggle',
    )
    result = source()
    assert result.get('verbose') is False


def test_add_parser_args_store_false_default_true_toggle():
    source = CliSettingsSource(
        SettingsWithToggleFlag,
        cli_parse_args=[],
        cli_implicit_flags='toggle',
    )
    result = source()
    assert isinstance(result, dict)
