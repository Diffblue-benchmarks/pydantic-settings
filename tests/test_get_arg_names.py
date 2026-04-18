"""Tests for CliSettingsSource._get_arg_names discriminator handling."""

from typing import Literal, Union
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel, Field
from pydantic.fields import FieldInfo

from pydantic_settings import BaseSettings, CliSettingsSource
from pydantic_settings.sources.providers.cli import _CliArg


class SimpleSettings(BaseSettings):
    name: str = 'default'

    model_config = {'env_file': None}


def _make_source(**kwargs):
    return CliSettingsSource(SimpleSettings, **kwargs)


def _make_mock_arg(dest='field', annotation=str, alias_names=('field',), arg_prefix=''):
    mock_arg = MagicMock()
    mock_arg.arg_prefix = arg_prefix
    mock_arg.alias_names = alias_names
    mock_arg.dest = dest
    mock_arg.field_info = MagicMock()
    mock_arg.field_info.annotation = annotation
    mock_arg.kwargs = {}
    return mock_arg


def test_discriminator_not_last_returns_empty():
    """When discriminator_vals contains arg.dest and is_last_discriminator is False, return []."""
    source = _make_source()
    mock_arg = _make_mock_arg(
        dest='pet_type',
        annotation=Literal['cat'],
        alias_names=('pet_type',),
    )
    discriminator_vals = {'pet_type': set()}

    result = source._get_arg_names(
        arg=mock_arg,
        subcommand_prefix='',
        alias_prefixes=[],
        added_args=[],
        discriminator_vals=discriminator_vals,
        is_last_discriminator=False,
    )

    assert result == []
    assert 'cat' in discriminator_vals['pet_type']


def test_discriminator_last_returns_arg_names_and_sets_metavar():
    """When is_last_discriminator is True, set metavar and return arg_names."""
    source = _make_source()
    mock_arg = _make_mock_arg(
        dest='pet_type',
        annotation=Literal['cat', 'dog'],
        alias_names=('pet_type',),
    )
    discriminator_vals = {'pet_type': set()}

    result = source._get_arg_names(
        arg=mock_arg,
        subcommand_prefix='',
        alias_prefixes=[],
        added_args=[],
        discriminator_vals=discriminator_vals,
        is_last_discriminator=True,
    )

    assert 'pet_type' in result
    assert 'metavar' in mock_arg.kwargs
    assert 'cat' in discriminator_vals['pet_type']
    assert 'dog' in discriminator_vals['pet_type']


def test_discriminator_collects_literal_values():
    """Discriminator values are collected from Literal annotations."""
    source = _make_source()
    mock_arg = _make_mock_arg(
        dest='kind',
        annotation=Literal['a', 'b', 'c'],
        alias_names=('kind',),
    )
    discriminator_vals = {'kind': set()}

    source._get_arg_names(
        arg=mock_arg,
        subcommand_prefix='',
        alias_prefixes=[],
        added_args=[],
        discriminator_vals=discriminator_vals,
        is_last_discriminator=False,
    )

    assert discriminator_vals['kind'] == {'a', 'b', 'c'}


def test_discriminator_accumulates_existing_values():
    """Discriminator values are added to existing set values."""
    source = _make_source()
    mock_arg = _make_mock_arg(
        dest='kind',
        annotation=Literal['new'],
        alias_names=('kind',),
    )
    discriminator_vals = {'kind': {'existing'}}

    source._get_arg_names(
        arg=mock_arg,
        subcommand_prefix='',
        alias_prefixes=[],
        added_args=[],
        discriminator_vals=discriminator_vals,
        is_last_discriminator=False,
    )

    assert discriminator_vals['kind'] == {'existing', 'new'}


def test_discriminator_last_metavar_contains_sorted_values():
    """Metavar should contain sorted discriminator values."""
    source = _make_source()
    mock_arg = _make_mock_arg(
        dest='kind',
        annotation=Literal['z_val', 'a_val'],
        alias_names=('kind',),
    )
    discriminator_vals = {'kind': set()}

    source._get_arg_names(
        arg=mock_arg,
        subcommand_prefix='',
        alias_prefixes=[],
        added_args=[],
        discriminator_vals=discriminator_vals,
        is_last_discriminator=True,
    )

    metavar = mock_arg.kwargs['metavar']
    # Values should appear sorted in the metavar
    a_pos = metavar.find('a_val')
    z_pos = metavar.find('z_val')
    assert a_pos < z_pos


def test_discriminator_with_union_literal_annotation():
    """Discriminator handles Union containing Literal types."""
    source = _make_source()
    mock_arg = _make_mock_arg(
        dest='pet_type',
        annotation=Union[Literal['cat'], Literal['dog']],
        alias_names=('pet_type',),
    )
    discriminator_vals = {'pet_type': set()}

    source._get_arg_names(
        arg=mock_arg,
        subcommand_prefix='',
        alias_prefixes=[],
        added_args=[],
        discriminator_vals=discriminator_vals,
        is_last_discriminator=False,
    )

    assert 'cat' in discriminator_vals['pet_type']
    assert 'dog' in discriminator_vals['pet_type']
