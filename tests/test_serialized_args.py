"""Tests for CliSettingsSource._serialized_args method."""

from typing import Annotated, Optional, Union

import pytest

from pydantic import AliasChoices, AliasPath, BaseModel, Field

from pydantic_settings import BaseSettings, CliApp, CliPositionalArg, CliSettingsSource, CliSubCommand
from pydantic_settings.sources.providers.cli import CliSettingsSource as _CliSettingsSourceDirect


# ---- Models used in tests ----


class SimpleModel(BaseSettings):
    name: str = 'default'
    count: int = 0

    model_config = {'env_file': None}


class NestedChild(BaseModel):
    host: str = 'localhost'
    port: int = 8080


class SettingsWithNestedModel(BaseSettings):
    db: NestedChild = NestedChild()
    label: str = 'app'

    model_config = {'env_file': None}


class SubCmdAlpha(BaseModel):
    alpha_val: str = 'a_default'

    def cli_cmd(self) -> None:
        pass


class SubCmdBeta(BaseModel):
    beta_val: str = 'b_default'

    def cli_cmd(self) -> None:
        pass


class SettingsWithSubCmd(BaseSettings):
    sub: CliSubCommand[Union[SubCmdAlpha, SubCmdBeta]]

    model_config = {'env_file': None}


class SettingsWithPositional(BaseSettings):
    pos_arg: CliPositionalArg[str]
    name: str = 'default'

    model_config = {'env_file': None}


class SettingsWithBoolFlag(BaseSettings):
    flag: bool = False

    model_config = {'env_file': None, 'cli_implicit_flags': True}


class SettingsWithListField(BaseSettings):
    items: list[str] = []

    model_config = {'env_file': None}


class SettingsWithDictField(BaseSettings):
    config: dict[str, str] = {}

    model_config = {'env_file': None}


class SettingsWithMultipleFields(BaseSettings):
    name: str = 'default'
    count: int = 0
    active: bool = True

    model_config = {'env_file': None}


class SettingsWithPositionalList(BaseSettings):
    files: CliPositionalArg[list[str]]
    name: str = 'default'

    model_config = {'env_file': None}


class SettingsWithBoolDefaultTrue(BaseSettings):
    flag: bool = True

    model_config = {'env_file': None, 'cli_implicit_flags': True}


class SettingsWithAliasPathOnly(BaseSettings):
    value: str = Field(default='default', validation_alias=AliasPath('data', 0))

    model_config = {'env_file': None}


class SettingsWithSubCmdAndName(BaseSettings):
    name: str = 'default'
    sub: CliSubCommand[SubCmdAlpha]

    model_config = {'env_file': None}


# ---- Tests for _serialized_args via CliApp.serialize ----


class TestSerializedArgsSimple:
    def test_simple_string_field_non_default(self):
        """Covers basic loop iteration, regex matching, value coercion, optional arg append."""
        settings = SimpleModel(_cli_parse_args=['--name', 'hello'])
        result = CliApp.serialize(settings)
        assert '--name' in result
        assert 'hello' in result

    def test_simple_int_field_non_default(self):
        settings = SimpleModel(_cli_parse_args=['--count', '42'])
        result = CliApp.serialize(settings)
        assert '--count' in result
        assert '42' in result

    def test_multiple_fields_non_default(self):
        settings = SimpleModel(_cli_parse_args=['--name', 'test', '--count', '5'])
        result = CliApp.serialize(settings)
        assert '--name' in result
        assert 'test' in result
        assert '--count' in result
        assert '5' in result

    def test_default_field_skipped(self):
        """Fields at their default values should not appear in serialized args."""
        settings = SimpleModel(_cli_parse_args=['--name', 'hello'])
        result = CliApp.serialize(settings)
        assert '--name' in result
        assert 'hello' in result
        # count is still at default 0, should not appear
        assert '--count' not in result

    def test_all_defaults_empty_result(self):
        settings = SimpleModel(_cli_parse_args=[])
        result = CliApp.serialize(settings)
        assert result == []


class TestSerializedArgsNestedModel:
    def test_nested_model_non_default(self):
        """Covers is_model_class branch, recursive _serialized_args call for submodels."""
        settings = SettingsWithNestedModel(
            _cli_parse_args=['--db.host', 'remotehost', '--db.port', '3306']
        )
        result = CliApp.serialize(settings)
        assert '--db.host' in result
        assert 'remotehost' in result
        assert '--db.port' in result
        assert '3306' in result

    def test_nested_model_partial_non_default(self):
        settings = SettingsWithNestedModel(_cli_parse_args=['--db.host', 'newhost'])
        result = CliApp.serialize(settings)
        assert '--db.host' in result
        assert 'newhost' in result


class TestSerializedArgsSubcommand:
    def test_subcommand_serialization(self):
        """Covers subcommand_dest branch, subcommand_alias, recursive call, flattening."""
        settings = SettingsWithSubCmd(_cli_parse_args=['SubCmdAlpha', '--alpha_val', 'test'])
        result = CliApp.serialize(settings)
        assert any('SubCmdAlpha' in arg or 'sub' in arg.lower() for arg in result)

    def test_subcommand_with_non_default_value(self):
        settings = SettingsWithSubCmd(_cli_parse_args=['SubCmdBeta', '--beta_val', 'custom'])
        result = CliApp.serialize(settings)
        assert any('custom' in arg for arg in result)


class TestSerializedArgsPositional:
    def test_positional_arg(self):
        """Covers _CliPositionalArg branch for positional args."""
        settings = SettingsWithPositional(_cli_parse_args=['myfile'])
        result = CliApp.serialize(settings)
        assert 'myfile' in result

    def test_positional_list_arg(self):
        """Covers the list iteration inside positional args."""
        settings = SettingsWithPositionalList(_cli_parse_args=['file1', 'file2', 'file3'])
        result = CliApp.serialize(settings)
        assert 'file1' in result
        assert 'file2' in result
        assert 'file3' in result


class TestSerializedArgsBoolFlag:
    def test_bool_flag_true(self):
        """Covers BooleanOptionalAction with True value (no 'no-' prefix)."""
        settings = SettingsWithBoolFlag(_cli_parse_args=['--flag'])
        result = CliApp.serialize(settings)
        assert any('flag' in arg for arg in result)

    def test_bool_flag_false_no_prefix(self):
        """Covers BooleanOptionalAction with False value adding 'no-' prefix."""
        settings = SettingsWithBoolFlag(_cli_parse_args=['--no-flag'])
        result = CliApp.serialize(settings)
        # Should remain empty since default is False and model_default after parsing --no-flag is also False
        # which equals field_info.default, so it's skipped
        # Actually, default is False and --no-flag sets it to False, so no change
        assert result == []


class TestSerializedArgsListField:
    def test_list_field_json_style(self):
        """Covers json.dumps path for list values."""
        settings = SettingsWithListField(_cli_parse_args=['--items', '["a","b","c"]'])
        result = CliApp.serialize(settings)
        assert '--items' in result

    def test_list_field_argparse_style(self):
        settings = SettingsWithListField(_cli_parse_args=['--items', '["x","y"]'])
        result = CliApp.serialize(settings, list_style='argparse')
        assert result.count('--items') == 2
        assert 'x' in result
        assert 'y' in result

    def test_list_field_lazy_style(self):
        settings = SettingsWithListField(_cli_parse_args=['--items', '["x","y"]'])
        result = CliApp.serialize(settings, list_style='lazy')
        assert '--items' in result
        assert 'x,y' in result


class TestSerializedArgsDictField:
    def test_dict_field_json_style(self):
        """Covers json.dumps path for dict values."""
        settings = SettingsWithDictField(_cli_parse_args=['--config', '{"key": "val"}'])
        result = CliApp.serialize(settings)
        assert '--config' in result

    def test_dict_field_env_style(self):
        settings = SettingsWithDictField(_cli_parse_args=['--config', '{"k": "v"}'])
        result = CliApp.serialize(settings, dict_style='env')
        assert '--config' in result
        assert 'k=v' in result


class TestSerializedArgsBoolNoPrefix:
    def test_bool_false_when_default_true(self):
        """Covers BooleanOptionalAction with False value when default is True, adding 'no-' prefix."""
        settings = SettingsWithBoolDefaultTrue(_cli_parse_args=['--no-flag'])
        result = CliApp.serialize(settings)
        assert any('no-flag' in arg for arg in result)


class TestSerializedArgsPositionalsFirst:
    def test_positionals_first_true(self):
        settings = SettingsWithPositional(_cli_parse_args=['myarg', '--name', 'val'])
        result = CliApp.serialize(settings, positionals_first=True)
        if '--name' in result and 'myarg' in result:
            name_idx = result.index('--name')
            myarg_idx = result.index('myarg')
            assert myarg_idx < name_idx

    def test_positionals_first_false(self):
        settings = SettingsWithPositional(_cli_parse_args=['myarg', '--name', 'val'])
        result = CliApp.serialize(settings, positionals_first=False)
        if '--name' in result and 'myarg' in result:
            name_idx = result.index('--name')
            myarg_idx = result.index('myarg')
            assert name_idx < myarg_idx


class TestSerializedArgsDirectCall:
    def test_direct_serialized_args_returns_dict(self):
        """Directly call _serialized_args and verify return structure."""
        source = CliSettingsSource(SimpleModel, cli_parse_args=['--name', 'direct'])
        settings = SimpleModel(_cli_parse_args=['--name', 'direct'])
        result = source._serialized_args(settings)
        assert 'optional' in result
        assert 'positional' in result
        assert 'subcommand' in result
        assert isinstance(result['optional'], list)
        assert isinstance(result['positional'], list)
        assert isinstance(result['subcommand'], list)

    def test_direct_serialized_args_optional_values(self):
        source = CliSettingsSource(SimpleModel, cli_parse_args=['--name', 'test_val'])
        settings = SimpleModel(_cli_parse_args=['--name', 'test_val'])
        result = source._serialized_args(settings)
        assert '--name' in result['optional']
        assert 'test_val' in result['optional']

    def test_direct_serialized_args_empty_when_defaults(self):
        source = CliSettingsSource(SimpleModel, cli_parse_args=[])
        settings = SimpleModel(_cli_parse_args=[])
        result = source._serialized_args(settings)
        assert result['optional'] == []
        assert result['positional'] == []
        assert result['subcommand'] == []


class TestSerializedArgsBoolNonDefault:
    def test_bool_true_when_default_false(self):
        """When default is False and value is True, should serialize the flag."""
        settings = SettingsWithBoolFlag(_cli_parse_args=['--flag'])
        result = CliApp.serialize(settings)
        assert any('flag' in arg for arg in result)
        # For BooleanOptionalAction with True value, no value is appended (implicit flag)
        # The flag name should appear but not a separate 'True' value


class TestSerializedArgsSubcommandNone:
    def test_subcommand_none_skipped(self):
        """Covers line 1489: subcommand field with None value is skipped."""
        settings = SettingsWithSubCmdAndName.model_construct(name='changed', sub=None)
        result = CliApp.serialize(settings)
        assert '--name' in result
        assert 'changed' in result


class TestSerializedArgsAliasPathOnly:
    def test_alias_path_only_field(self):
        """Covers line 1525: alias_path_only fields use _update_alias_path_only_default."""
        settings = SettingsWithAliasPathOnly.model_construct(value='custom')
        result = CliApp.serialize(settings)
        # The field should be serialized, even though it uses an alias path
        assert len(result) > 0
