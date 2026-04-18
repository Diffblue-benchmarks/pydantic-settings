"""Tests for CliSettingsSource._update_alias_path_only_default."""

from typing import Annotated

import pytest

from pydantic import AliasChoices, AliasPath, Field
from pydantic.fields import FieldInfo

from pydantic_settings import BaseSettings, CliSettingsSource


class AliasSettings(BaseSettings):
    value: str = 'default'

    model_config = {'env_file': None}


@pytest.fixture
def cli_source():
    return CliSettingsSource(AliasSettings, cli_parse_args=[])


class TestUpdateAliasPathOnlyDefaultNoNesting:
    """Tests for alias paths without nested paths (path[1:-1] is empty)."""

    def test_simple_alias_path_index_zero(self, cli_source):
        """AliasPath('root', 0) -> no nested paths, inserts at index 0."""
        field_info = FieldInfo(annotation=str, default='x')
        field_info.validation_alias = AliasPath('root', 0)
        defaults: dict = {}

        result = cli_source._update_alias_path_only_default('my_arg', 'hello', field_info, defaults)

        assert defaults['my_arg'] == ['hello']
        assert result == ['hello']

    def test_simple_alias_path_index_two(self, cli_source):
        """AliasPath('root', 2) -> extends list to accommodate index 2."""
        field_info = FieldInfo(annotation=str, default='x')
        field_info.validation_alias = AliasPath('root', 2)
        defaults: dict = {}

        result = cli_source._update_alias_path_only_default('arg2', 'val', field_info, defaults)

        assert defaults['arg2'] == ['', '', 'val']
        assert result == ['', '', 'val']

    def test_multiple_calls_same_arg(self, cli_source):
        """Multiple calls with different indices build up the same list."""
        field_info_0 = FieldInfo(annotation=str, default='x')
        field_info_0.validation_alias = AliasPath('root', 0)
        field_info_1 = FieldInfo(annotation=str, default='x')
        field_info_1.validation_alias = AliasPath('root', 1)
        defaults: dict = {}

        cli_source._update_alias_path_only_default('arg', 'first', field_info_0, defaults)
        result = cli_source._update_alias_path_only_default('arg', 'second', field_info_1, defaults)

        assert defaults['arg'] == ['first', 'second']
        assert result == ['first', 'second']

    def test_alias_on_field_alias_not_validation_alias(self, cli_source):
        """When alias (not validation_alias) is an AliasPath, it should still work."""
        field_info = FieldInfo(annotation=str, default='x')
        field_info.alias = AliasPath('root', 1)
        field_info.validation_alias = None
        defaults: dict = {}

        result = cli_source._update_alias_path_only_default('arg', 'value', field_info, defaults)

        assert defaults['arg'] == ['', 'value']
        assert result == ['', 'value']

    def test_alias_choices_extracts_first_choice(self, cli_source):
        """When validation_alias is AliasChoices, first choice is used."""
        field_info = FieldInfo(annotation=str, default='x')
        field_info.validation_alias = AliasChoices(AliasPath('root', 0), AliasPath('other', 1))
        defaults: dict = {}

        result = cli_source._update_alias_path_only_default('arg', 'picked', field_info, defaults)

        assert defaults['arg'] == ['picked']
        assert result == ['picked']


class TestUpdateAliasPathOnlyDefaultWithNesting:
    """Tests for alias paths with nested paths (path[1:-1] is non-empty)."""

    def test_single_nested_path(self, cli_source):
        """AliasPath('root', 'nested', 0) -> one level of nesting."""
        field_info = FieldInfo(annotation=str, default='x')
        field_info.validation_alias = AliasPath('root', 'nested', 0)
        defaults: dict = {}

        result = cli_source._update_alias_path_only_default('arg', 'val', field_info, defaults)

        assert defaults['arg'] == {'nested': ['val']}
        assert result == {'nested': ['val']}

    def test_deeply_nested_path(self, cli_source):
        """AliasPath('root', 'a', 'b', 0) -> two levels of nesting."""
        field_info = FieldInfo(annotation=str, default='x')
        field_info.validation_alias = AliasPath('root', 'a', 'b', 0)
        defaults: dict = {}

        result = cli_source._update_alias_path_only_default('arg', 'deep', field_info, defaults)

        assert defaults['arg'] == {'a': {'b': ['deep']}}
        assert result == {'a': {'b': ['deep']}}

    def test_nested_path_index_greater_than_zero(self, cli_source):
        """AliasPath('root', 'nest', 2) -> extends list for index 2."""
        field_info = FieldInfo(annotation=str, default='x')
        field_info.validation_alias = AliasPath('root', 'nest', 2)
        defaults: dict = {}

        result = cli_source._update_alias_path_only_default('arg', 'v', field_info, defaults)

        assert defaults['arg'] == {'nest': ['', '', 'v']}
        assert result == {'nest': ['', '', 'v']}

    def test_multiple_calls_nested_same_arg(self, cli_source):
        """Multiple calls accumulate into the same nested structure."""
        field_info_0 = FieldInfo(annotation=str, default='x')
        field_info_0.validation_alias = AliasPath('root', 'nest', 0)
        field_info_1 = FieldInfo(annotation=str, default='x')
        field_info_1.validation_alias = AliasPath('root', 'nest', 1)
        defaults: dict = {}

        cli_source._update_alias_path_only_default('arg', 'a', field_info_0, defaults)
        result = cli_source._update_alias_path_only_default('arg', 'b', field_info_1, defaults)

        assert defaults['arg'] == {'nest': ['a', 'b']}
        assert result == {'nest': ['a', 'b']}

    def test_three_level_nesting(self, cli_source):
        """AliasPath('root', 'x', 'y', 'z', 0) -> three levels of nested dicts."""
        field_info = FieldInfo(annotation=str, default='x')
        field_info.validation_alias = AliasPath('root', 'x', 'y', 'z', 0)
        defaults: dict = {}

        result = cli_source._update_alias_path_only_default('arg', 'leaf', field_info, defaults)

        assert defaults['arg'] == {'x': {'y': {'z': ['leaf']}}}
        assert result == {'x': {'y': {'z': ['leaf']}}}
