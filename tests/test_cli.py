"""Tests for CLI settings source."""

from __future__ import annotations

from collections import defaultdict
from enum import Enum
from typing import Annotated, Any, Literal

import pytest
from pydantic import AliasChoices, AliasPath, BaseModel, Field

from pydantic_settings import BaseSettings, CliSettingsSource, SettingsError
from pydantic_settings.sources.providers.cli import (
    _CliArg,
    _CliInternalArgParser,
    _collect_sub_models,
    CliMutuallyExclusiveGroup,
    CliPositionalArg,
    CliSubCommand,
)
from pydantic_settings.sources.types import (
    _CliDualFlag,
    _CliExplicitFlag,
    _CliImplicitFlag,
    _CliPositionalArg,
    _CliSubCommand,
    _CliToggleFlag,
    ForceDecode,
    NoDecode,
)


class TestCliInternalArgParser:
    """Tests for _CliInternalArgParser class."""

    def test_init_default_exit_on_error(self):
        """Test initialization with default cli_exit_on_error."""
        parser = _CliInternalArgParser()
        assert parser._cli_exit_on_error is True

    def test_init_custom_exit_on_error(self):
        """Test initialization with custom cli_exit_on_error."""
        parser = _CliInternalArgParser(cli_exit_on_error=False)
        assert parser._cli_exit_on_error is False

    def test_error_with_exit_disabled_raises_settings_error(self):
        """Test that error() raises SettingsError when cli_exit_on_error is False."""
        parser = _CliInternalArgParser(cli_exit_on_error=False)
        with pytest.raises(SettingsError, match='error parsing CLI: test error'):
            parser.error('test error')

    def test_error_with_exit_enabled_calls_super(self):
        """Test that error() calls super() when cli_exit_on_error is True."""
        parser = _CliInternalArgParser(cli_exit_on_error=True, prog='test')
        with pytest.raises(SystemExit):
            parser.error('test error')


class TestCollectSubModels:
    """Tests for _collect_sub_models function."""

    def test_collect_base_model(self):
        """Test collecting a simple BaseModel."""

        class SubModel(BaseModel):
            field: str

        sub_models: list[type[BaseModel]] = []
        _collect_sub_models(SubModel, sub_models)
        assert SubModel in sub_models

    def test_collect_from_union(self):
        """Test collecting models from union types."""

        class ModelA(BaseModel):
            a: str

        class ModelB(BaseModel):
            b: str

        sub_models: list[type[BaseModel]] = []
        _collect_sub_models(ModelA | ModelB, sub_models)
        assert ModelA in sub_models
        assert ModelB in sub_models

    def test_collect_from_union_with_none(self):
        """Test collecting models from optional union types."""

        class SubModel(BaseModel):
            field: str

        sub_models: list[type[BaseModel]] = []
        _collect_sub_models(SubModel | None, sub_models)
        assert SubModel in sub_models
        assert len(sub_models) == 1

    def test_collect_non_model_returns_empty(self):
        """Test that non-model types don't get collected."""
        sub_models: list[type[BaseModel]] = []
        _collect_sub_models(str, sub_models)
        assert len(sub_models) == 0


class TestCliArg:
    """Tests for _CliArg class."""

    def test_get_kebab_case_enabled(self):
        """Test get_kebab_case with kebab_case enabled."""
        assert _CliArg.get_kebab_case('my_field_name', True) == 'my-field-name'
        assert _CliArg.get_kebab_case('my_field_name', 'all') == 'my-field-name'

    def test_get_kebab_case_disabled(self):
        """Test get_kebab_case with kebab_case disabled."""
        assert _CliArg.get_kebab_case('my_field_name', False) == 'my_field_name'
        assert _CliArg.get_kebab_case('my_field_name', None) == 'my_field_name'

    def test_get_kebab_case_no_enums(self):
        """Test get_kebab_case with 'no_enums' setting."""
        assert _CliArg.get_kebab_case('my_field_name', 'no_enums') == 'my-field-name'

    def test_get_enum_names_basic(self):
        """Test get_enum_names for simple enum."""

        class Color(Enum):
            RED = 'red'
            GREEN = 'green'
            BLUE = 'blue'

        names = _CliArg.get_enum_names(Color, False)
        assert 'RED' in names
        assert 'GREEN' in names
        assert 'BLUE' in names

    def test_get_enum_names_with_kebab_case(self):
        """Test get_enum_names with kebab case conversion."""

        class Status(Enum):
            IN_PROGRESS = 'in_progress'
            NOT_STARTED = 'not_started'

        names = _CliArg.get_enum_names(Status, 'all')
        assert 'IN-PROGRESS' in names
        assert 'NOT-STARTED' in names

    def test_get_enum_names_without_kebab_case(self):
        """Test get_enum_names without kebab case."""

        class Status(Enum):
            IN_PROGRESS = 'in_progress'

        names = _CliArg.get_enum_names(Status, False)
        assert 'IN_PROGRESS' in names


class TestCliSettingsSourceBasic:
    """Basic tests for CliSettingsSource class."""

    def test_init_basic(self):
        """Test basic initialization."""

        class Settings(BaseSettings):
            name: str = 'default'

        source = CliSettingsSource(Settings, cli_prog_name='test')
        assert source.cli_prog_name == 'test'
        assert source.cli_exit_on_error is True

    def test_init_with_custom_options(self):
        """Test initialization with custom options."""

        class Settings(BaseSettings):
            name: str = 'default'

        source = CliSettingsSource(
            Settings,
            cli_prog_name='myapp',
            cli_hide_none_type=True,
            cli_avoid_json=True,
            cli_enforce_required=True,
            cli_exit_on_error=False,
            cli_kebab_case=True,
        )
        assert source.cli_prog_name == 'myapp'
        assert source.cli_hide_none_type is True
        assert source.cli_avoid_json is True
        assert source.cli_enforce_required is True
        assert source.cli_exit_on_error is False
        assert source.cli_kebab_case is True

    def test_init_invalid_prefix_raises_error(self):
        """Test that invalid cli_prefix raises SettingsError."""

        class Settings(BaseSettings):
            name: str = 'default'

        with pytest.raises(SettingsError, match='CLI settings source prefix is invalid'):
            CliSettingsSource(Settings, cli_prefix='.invalid')

        with pytest.raises(SettingsError, match='CLI settings source prefix is invalid'):
            CliSettingsSource(Settings, cli_prefix='invalid.')

    def test_case_insensitive_with_external_parser_raises_error(self):
        """Test case insensitive with external parser raises error."""
        from argparse import ArgumentParser

        class Settings(BaseSettings):
            name: str = 'default'

        external_parser = ArgumentParser()
        with pytest.raises(SettingsError, match='Case-insensitive matching is only supported'):
            CliSettingsSource(Settings, root_parser=external_parser, case_sensitive=False)

    def test_root_parser_property(self):
        """Test root_parser property returns the parser."""

        class Settings(BaseSettings):
            name: str = 'default'

        source = CliSettingsSource(Settings)
        parser = source.root_parser
        assert isinstance(parser, _CliInternalArgParser)


class TestCliSettingsSourceCall:
    """Tests for CliSettingsSource __call__ method."""

    def test_call_with_no_args_returns_dict(self):
        """Test __call__ with no arguments returns dict."""

        class Settings(BaseSettings):
            name: str = 'default'

        source = CliSettingsSource(Settings)
        source._load_env_vars(parsed_args={})
        result = source()
        assert isinstance(result, dict)

    def test_call_with_args_list(self):
        """Test __call__ with args list."""

        class Settings(BaseSettings):
            name: str = 'default'

        source = CliSettingsSource(Settings)
        result = source(args=['--name', 'test'])
        assert isinstance(result, CliSettingsSource)

    def test_call_with_args_false(self):
        """Test __call__ with args=False."""

        class Settings(BaseSettings):
            name: str = 'default'

        source = CliSettingsSource(Settings)
        result = source(args=False)
        assert isinstance(result, CliSettingsSource)

    def test_call_with_parsed_args(self):
        """Test __call__ with parsed_args dict."""

        class Settings(BaseSettings):
            name: str = 'default'

        source = CliSettingsSource(Settings)
        result = source(parsed_args={'name': 'test'})
        assert isinstance(result, CliSettingsSource)

    def test_call_with_args_and_parsed_args_raises_error(self):
        """Test __call__ with both args and parsed_args raises error."""

        class Settings(BaseSettings):
            name: str = 'default'

        source = CliSettingsSource(Settings)
        with pytest.raises(SettingsError, match='mutually exclusive'):
            source(args=['--name', 'test'], parsed_args={'name': 'test'})


class TestCliSettingsSourceParseNoneStr:
    """Tests for CLI parse_none_str handling."""

    def test_parse_none_str_default_json(self):
        """Test default parse_none_str is 'null' when not avoiding JSON."""

        class Settings(BaseSettings):
            name: str | None = None

        source = CliSettingsSource(Settings, cli_avoid_json=False)
        assert source.cli_parse_none_str == 'null'

    def test_parse_none_str_default_no_json(self):
        """Test default parse_none_str is 'None' when avoiding JSON."""

        class Settings(BaseSettings):
            name: str | None = None

        source = CliSettingsSource(Settings, cli_avoid_json=True)
        assert source.cli_parse_none_str == 'None'


class TestCliSettingsSourceKebabCase:
    """Tests for kebab case handling."""

    def test_kebab_case_arg_parsing(self):
        """Test parsing with kebab case enabled."""

        class Settings(BaseSettings):
            my_field: str = 'default'

        source = CliSettingsSource(Settings, cli_kebab_case=True)
        source(args=['--my-field', 'value'])
        assert source.env_vars.get('my_field') == 'value' or source.env_vars.get('my-field') == 'value'


class TestCliSettingsSourceShortcuts:
    """Tests for CLI shortcuts handling."""

    def test_shortcuts_mapping(self):
        """Test CLI shortcuts mapping."""

        class Settings(BaseSettings):
            verbose: bool = False

        source = CliSettingsSource(
            Settings, cli_shortcuts={'verbose': ['v']}, cli_implicit_flags=True
        )
        source(args=['--verbose'])
        assert 'verbose' in source.env_vars


class TestCliSettingsSourceListMerging:
    """Tests for list merging behavior."""

    def test_merge_simple_list(self):
        """Test merging simple list values."""

        class Settings(BaseSettings):
            items: list[str] = []

        source = CliSettingsSource(Settings)
        source(args=['--items', 'a', '--items', 'b'])
        assert 'items' in source.env_vars

    def test_merge_json_array(self):
        """Test merging JSON array syntax."""

        class Settings(BaseSettings):
            items: list[str] = []

        source = CliSettingsSource(Settings)
        source(args=['--items', '["a", "b"]'])
        assert 'items' in source.env_vars


class TestCliSettingsSourceBoolFlags:
    """Tests for boolean flag handling."""

    def test_dual_flag_true(self):
        """Test dual flag with true value."""

        class Settings(BaseSettings):
            flag: bool = False

        source = CliSettingsSource(Settings, cli_implicit_flags='dual')
        source(args=['--flag'])
        assert source.env_vars.get('flag') is True

    def test_dual_flag_false(self):
        """Test dual flag with false value."""

        class Settings(BaseSettings):
            flag: bool = True

        source = CliSettingsSource(Settings, cli_implicit_flags='dual')
        source(args=['--no-flag'])
        assert source.env_vars.get('flag') is False


class TestCliSettingsSourceNestedModels:
    """Tests for nested model handling."""

    def test_nested_model_basic(self):
        """Test basic nested model parsing."""

        class SubModel(BaseModel):
            value: str = 'default'

        class Settings(BaseSettings):
            nested: SubModel = SubModel()

        source = CliSettingsSource(Settings)
        source(args=['--nested.value', 'test'])
        assert 'nested.value' in source.env_vars


class TestCliSettingsSourceSubcommands:
    """Tests for subcommand handling."""

    def test_subcommand_basic(self):
        """Test basic subcommand parsing."""

        class SubCmd(BaseModel):
            name: str = 'default'

        class Settings(BaseSettings):
            cmd: CliSubCommand[SubCmd]

        source = CliSettingsSource(Settings)
        # Subcommand name is 'cmd' since there's only one subcommand option
        source(args=['cmd', '--name', 'test'])
        assert any('name' in k for k in source.env_vars.keys())


class TestCliSettingsSourcePositionalArgs:
    """Tests for positional argument handling."""

    def test_positional_arg_basic(self):
        """Test basic positional argument."""

        class Settings(BaseSettings):
            file: CliPositionalArg[str]

        source = CliSettingsSource(Settings)
        source(args=['myfile.txt'])
        # Check that the value was parsed
        assert any('file' in k.lower() for k in source.env_vars.keys()) or 'file' in source.env_vars.values()


class TestCliSettingsSourceErrorHandling:
    """Tests for error handling."""

    def test_consume_object_missing_close(self):
        """Test error when JSON object is missing closing brace."""

        class Settings(BaseSettings):
            data: dict[str, str] = {}

        source = CliSettingsSource(Settings)
        with pytest.raises(SettingsError, match='Parsing error'):
            source(args=['--data', '{"key": "value"'])

    def test_consume_string_mismatched_quotes(self):
        """Test error when string has mismatched quotes."""

        class Settings(BaseSettings):
            items: list[str] = []

        source = CliSettingsSource(Settings)
        with pytest.raises(SettingsError, match='Parsing error'):
            source(args=['--items', '"unclosed'])


class TestCliArgProperties:
    """Tests for _CliArg cached properties."""

    def test_cli_arg_initialization(self):
        """Test _CliArg full initialization."""

        class MyModel(BaseModel):
            field: str = 'default'

        field_info = MyModel.model_fields['field']
        parser_map: defaultdict[str | Any, dict[int | None | str | type[BaseModel], _CliArg]] = defaultdict(dict)

        arg = _CliArg(
            field_info=field_info,
            parser_map=parser_map,
            model=MyModel,
            parser=None,
            field_name='field',
            arg_prefix='',
            case_sensitive=True,
            populate_by_name=False,
            hide_none_type=False,
            kebab_case=False,
            enable_decoding=True,
            env_prefix_len=0,
        )

        assert arg.field_info == field_info
        assert arg.field_name == 'field'
        assert arg.preferred_alias == 'field'
        assert arg.dest == 'field'

    def test_cli_arg_with_alias(self):
        """Test _CliArg with field alias."""

        class MyModel(BaseModel):
            field: str = Field(default='default', alias='my_alias')

        field_info = MyModel.model_fields['field']
        parser_map: defaultdict[str | Any, dict[int | None | str | type[BaseModel], _CliArg]] = defaultdict(dict)

        arg = _CliArg(
            field_info=field_info,
            parser_map=parser_map,
            model=MyModel,
            parser=None,
            field_name='field',
            arg_prefix='',
            case_sensitive=True,
            populate_by_name=False,
            hide_none_type=False,
            kebab_case=False,
            enable_decoding=True,
            env_prefix_len=0,
        )

        assert arg.preferred_alias == 'my_alias'

    def test_cli_arg_is_append_action_list(self):
        """Test is_append_action for list type."""

        class MyModel(BaseModel):
            items: list[str] = []

        field_info = MyModel.model_fields['items']
        parser_map: defaultdict[str | Any, dict[int | None | str | type[BaseModel], _CliArg]] = defaultdict(dict)

        arg = _CliArg(
            field_info=field_info,
            parser_map=parser_map,
            model=MyModel,
            parser=None,
            field_name='items',
            arg_prefix='',
            case_sensitive=True,
            populate_by_name=False,
            hide_none_type=False,
            kebab_case=False,
            enable_decoding=True,
            env_prefix_len=0,
        )

        assert arg.is_append_action is True

    def test_cli_arg_is_no_decode(self):
        """Test is_no_decode with NoDecode annotation."""

        class MyModel(BaseModel):
            raw_field: Annotated[str, NoDecode] = 'default'

        field_info = MyModel.model_fields['raw_field']
        parser_map: defaultdict[str | Any, dict[int | None | str | type[BaseModel], _CliArg]] = defaultdict(dict)

        arg = _CliArg(
            field_info=field_info,
            parser_map=parser_map,
            model=MyModel,
            parser=None,
            field_name='raw_field',
            arg_prefix='',
            case_sensitive=True,
            populate_by_name=False,
            hide_none_type=False,
            kebab_case=False,
            enable_decoding=True,
            env_prefix_len=0,
        )

        assert arg.is_no_decode is True

    def test_cli_arg_is_no_decode_with_enable_decoding_false(self):
        """Test is_no_decode when enable_decoding is False."""

        class MyModel(BaseModel):
            field: str = 'default'

        field_info = MyModel.model_fields['field']
        parser_map: defaultdict[str | Any, dict[int | None | str | type[BaseModel], _CliArg]] = defaultdict(dict)

        arg = _CliArg(
            field_info=field_info,
            parser_map=parser_map,
            model=MyModel,
            parser=None,
            field_name='field',
            arg_prefix='',
            case_sensitive=True,
            populate_by_name=False,
            hide_none_type=False,
            kebab_case=False,
            enable_decoding=False,
            env_prefix_len=0,
        )

        assert arg.is_no_decode is True

    def test_cli_arg_force_decode_overrides_enable_decoding_false(self):
        """Test ForceDecode overrides enable_decoding=False."""

        class MyModel(BaseModel):
            field: Annotated[str, ForceDecode] = 'default'

        field_info = MyModel.model_fields['field']
        parser_map: defaultdict[str | Any, dict[int | None | str | type[BaseModel], _CliArg]] = defaultdict(dict)

        arg = _CliArg(
            field_info=field_info,
            parser_map=parser_map,
            model=MyModel,
            parser=None,
            field_name='field',
            arg_prefix='',
            case_sensitive=True,
            populate_by_name=False,
            hide_none_type=False,
            kebab_case=False,
            enable_decoding=False,
            env_prefix_len=0,
        )

        assert arg.is_no_decode is False


class TestCliSettingsSourceSortArgFields:
    """Tests for _sort_arg_fields method."""

    def test_sort_positional_first(self):
        """Test that positional args come first."""

        class Settings(BaseSettings):
            optional: str = 'default'
            positional: CliPositionalArg[str]

        source = CliSettingsSource(Settings)
        sorted_fields = source._sort_arg_fields(Settings)

        field_names = [name for name, _ in sorted_fields]
        pos_idx = field_names.index('positional')
        opt_idx = field_names.index('optional')
        assert pos_idx < opt_idx

    def test_subcommand_requires_no_default(self):
        """Test that subcommand cannot have default value."""

        class SubCmd(BaseModel):
            name: str = 'default'

        # Subcommand fields must be required (no default)
        # This test verifies the validation happens at source initialization
        class Settings(BaseSettings):
            cmd: Annotated[SubCmd | None, _CliSubCommand] = Field(default=None)

        with pytest.raises(SettingsError, match='has a default value'):
            CliSettingsSource(Settings)


class TestCliSettingsSourceImplicitFlags:
    """Tests for implicit flag settings."""

    def test_toggle_flag(self):
        """Test toggle flag behavior."""

        class Settings(BaseSettings):
            verbose: Annotated[bool, _CliToggleFlag] = False

        source = CliSettingsSource(Settings, cli_implicit_flags='toggle')
        source(args=['--verbose'])
        assert source.env_vars.get('verbose') is True

    def test_explicit_flag_requires_bool_type(self):
        """Test that explicit flag requires bool annotation."""

        class Settings(BaseSettings):
            flag: Annotated[str, _CliExplicitFlag] = 'default'

        with pytest.raises(SettingsError, match='is not of type bool'):
            CliSettingsSource(Settings)

    def test_toggle_flag_requires_default_bool(self):
        """Test that toggle flag requires default bool value."""

        class Settings(BaseSettings):
            flag: Annotated[bool, _CliToggleFlag]

        with pytest.raises(SettingsError, match='must have a default bool value'):
            CliSettingsSource(Settings)


class TestCliSettingsSourceHelp:
    """Tests for help formatting."""

    def test_help_format_required(self):
        """Test help format for required field."""

        class Settings(BaseSettings):
            required_field: str

        source = CliSettingsSource(Settings)
        field_info = Settings.model_fields['required_field']
        help_text = source._help_format('required_field', field_info, None, False)
        assert 'required' in help_text.lower()

    def test_help_format_with_default(self):
        """Test help format with default value."""

        class Settings(BaseSettings):
            field: str = 'default_value'

        source = CliSettingsSource(Settings)
        field_info = Settings.model_fields['field']
        help_text = source._help_format('field', field_info, None, False)
        assert 'default' in help_text.lower()


class TestCliSettingsSourceMetavarFormat:
    """Tests for metavar formatting."""

    def test_metavar_format_basic_types(self):
        """Test metavar format for basic types."""

        class Settings(BaseSettings):
            name: str = 'default'
            count: int = 0
            flag: bool = False

        source = CliSettingsSource(Settings)

        str_metavar = source._metavar_format(str)
        assert str_metavar == 'str'

        int_metavar = source._metavar_format(int)
        assert int_metavar == 'int'

        bool_metavar = source._metavar_format(bool)
        assert bool_metavar == 'bool'

    def test_metavar_format_union(self):
        """Test metavar format for union types."""

        class Settings(BaseSettings):
            value: str | int | None = None

        source = CliSettingsSource(Settings)
        metavar = source._metavar_format(str | int | None)
        assert 'str' in metavar
        assert 'int' in metavar

    def test_metavar_format_enum(self):
        """Test metavar format for enum types."""

        class Color(Enum):
            RED = 'red'
            GREEN = 'green'

        class Settings(BaseSettings):
            color: Color = Color.RED

        source = CliSettingsSource(Settings)
        metavar = source._metavar_format(Color)
        assert 'RED' in metavar
        assert 'GREEN' in metavar

    def test_metavar_format_literal(self):
        """Test metavar format for Literal types."""

        class Settings(BaseSettings):
            mode: Literal['fast', 'slow'] = 'fast'

        source = CliSettingsSource(Settings)
        metavar = source._metavar_format(Literal['fast', 'slow'])
        assert 'fast' in metavar
        assert 'slow' in metavar


class TestCliSettingsSourceMutuallyExclusiveGroup:
    """Tests for mutually exclusive group handling."""

    def test_mutually_exclusive_group_nested_error(self):
        """Test that nested models in mutually exclusive group raise error."""

        class SubModel(BaseModel):
            field: str = 'default'

        class ExclusiveGroup(CliMutuallyExclusiveGroup):
            nested: SubModel = SubModel()

        class Settings(BaseSettings):
            group: ExclusiveGroup = ExclusiveGroup()

        with pytest.raises(SettingsError, match='cannot have nested models'):
            CliSettingsSource(Settings)


class TestCliSettingsSourceAliasPath:
    """Tests for alias path handling."""

    def test_alias_path_basic(self):
        """Test basic alias path handling."""

        class Settings(BaseSettings):
            field: str = Field(default='default', validation_alias=AliasPath('nested', 0))

        source = CliSettingsSource(Settings)
        # Just verify the source initializes without error
        assert source is not None


class TestCliSettingsSourceConsumeHelpers:
    """Tests for consume helper methods."""

    def test_consume_comma(self):
        """Test _consume_comma method."""

        class Settings(BaseSettings):
            items: list[str] = []

        source = CliSettingsSource(Settings)
        merged_list: list[str] = []
        result = source._consume_comma(',rest', merged_list, False)
        assert result == 'rest'
        assert '""' in merged_list

    def test_consume_object_json(self):
        """Test _consume_object_or_array with JSON object."""

        class Settings(BaseSettings):
            data: dict[str, str] = {}

        source = CliSettingsSource(Settings)
        merged_list: list[str] = []
        result = source._consume_object_or_array('{"key": "value"}rest', merged_list)
        assert '{"key": "value"}' in merged_list
        assert result == 'rest'

    def test_consume_object_array(self):
        """Test _consume_object_or_array with JSON array."""

        class Settings(BaseSettings):
            items: list[str] = []

        source = CliSettingsSource(Settings)
        merged_list: list[str] = []
        result = source._consume_object_or_array('["a", "b"]rest', merged_list)
        assert '["a", "b"]' in merged_list
        assert result == 'rest'


class TestCliSettingsSourceCaseInsensitive:
    """Tests for case insensitive parsing."""

    def test_case_insensitive_parsing(self):
        """Test case insensitive argument parsing."""

        class Settings(BaseSettings):
            myfield: str = 'default'

        source = CliSettingsSource(Settings, case_sensitive=False)
        source(args=['--MYFIELD', 'test'])
        # Check that the value was parsed (case insensitive lookup)
        assert any(v == 'test' for v in source.env_vars.values())


class TestCliSettingsSourceIgnoreUnknownArgs:
    """Tests for ignoring unknown arguments."""

    def test_ignore_unknown_args(self):
        """Test that unknown args are ignored when configured."""

        class Settings(BaseSettings):
            name: str = 'default'

        source = CliSettingsSource(Settings, cli_ignore_unknown_args=True)
        source(args=['--name', 'test', '--unknown', 'value'])
        assert source.env_vars.get('name') == 'test'


class TestCliSettingsSourceModifiedArgs:
    """Tests for _get_modified_args method."""

    def test_get_modified_args_no_hide_none(self):
        """Test _get_modified_args without hiding None type."""

        class Settings(BaseSettings):
            value: str | None = None

        source = CliSettingsSource(Settings, cli_hide_none_type=False)
        args = source._get_modified_args(str | None)
        assert type(None) in args

    def test_get_modified_args_hide_none(self):
        """Test _get_modified_args with hiding None type."""

        class Settings(BaseSettings):
            value: str | None = None

        source = CliSettingsSource(Settings, cli_hide_none_type=True)
        args = source._get_modified_args(str | None)
        assert type(None) not in args
