"""Tests for CliSettingsSource."""

import sys
from argparse import ArgumentParser, Namespace
from collections import defaultdict
from enum import Enum
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import BaseModel, Field
from pydantic.dataclasses import dataclass
from pydantic.fields import FieldInfo

from pydantic_settings import BaseSettings
from pydantic_settings.sources.providers.cli import (
    CliSettingsSource,
    _CliArg,
    _CliInternalArgParser,
    _collect_sub_models,
)


class SimpleSettings(BaseSettings):
    """Simple settings model for testing."""

    name: str = 'default'
    value: int = 0
    verbose: bool = False


class SubModel(BaseModel):
    """Sub model for testing."""

    sub_value: str = 'default'


class TestCliInternalArgParser:
    """Tests for _CliInternalArgParser."""

    def test_init_default(self):
        """Test initialization with default values."""
        parser = _CliInternalArgParser(prog='test')
        assert parser.prog == 'test'
        assert parser._cli_exit_on_error is True

    def test_init_with_cli_exit_on_error_false(self):
        """Test initialization with cli_exit_on_error=False."""
        parser = _CliInternalArgParser(cli_exit_on_error=False, prog='test')
        assert parser._cli_exit_on_error is False

    def test_init_with_cli_exit_on_error_true(self):
        """Test initialization with cli_exit_on_error=True."""
        parser = _CliInternalArgParser(cli_exit_on_error=True, prog='test')
        assert parser._cli_exit_on_error is True

    def test_error_with_exit_on_error_false(self):
        """Test error method raises SettingsError when cli_exit_on_error is False."""
        from pydantic_settings.exceptions import SettingsError

        parser = _CliInternalArgParser(cli_exit_on_error=False, prog='test')
        with pytest.raises(SettingsError, match='error parsing CLI:'):
            parser.error('test error')

    def test_error_with_exit_on_error_true(self):
        """Test error method calls parent error when cli_exit_on_error is True."""
        parser = _CliInternalArgParser(cli_exit_on_error=True, prog='test')
        with pytest.raises(SystemExit):
            parser.error('test error')


class TestCollectSubModels:
    """Tests for _collect_sub_models function."""

    def test_collect_single_model(self):
        """Test collecting a single BaseModel."""
        sub_models: list[type[BaseModel]] = []
        _collect_sub_models(SubModel, sub_models)
        assert len(sub_models) == 1
        assert sub_models[0] is SubModel

    def test_collect_union_models(self):
        """Test collecting models from a union type."""
        from typing import Union

        sub_models: list[type[BaseModel]] = []
        _collect_sub_models(Union[SubModel, SimpleSettings], sub_models)
        assert len(sub_models) == 2
        assert SubModel in sub_models
        assert SimpleSettings in sub_models

    def test_collect_non_model_type(self):
        """Test collecting with non-model type."""
        sub_models: list[type[BaseModel]] = []
        _collect_sub_models(str, sub_models)
        assert len(sub_models) == 0

    def test_collect_pydantic_dataclass(self):
        """Test collecting pydantic dataclass."""

        @dataclass
        class DataClassModel:
            value: str = 'test'

        sub_models: list[type[BaseModel]] = []
        _collect_sub_models(DataClassModel, sub_models)
        assert len(sub_models) == 1


class TestCliArg:
    """Tests for _CliArg class."""

    def test_init_with_basic_field(self):
        """Test initialization with basic field."""
        field_info = FieldInfo(annotation=str, default='default')
        parser_map: defaultdict[str | FieldInfo, dict[int | None | str | type[BaseModel], _CliArg]] = defaultdict(dict)

        cli_arg = _CliArg(
            field_info=field_info,
            parser_map=parser_map,
            model=SimpleSettings,
            parser=ArgumentParser(),
            field_name='name',
            arg_prefix='',
            case_sensitive=True,
            populate_by_name=True,
            hide_none_type=False,
            kebab_case=False,
            enable_decoding=True,
            env_prefix_len=0,
        )

        assert cli_arg.field_name == 'name'
        assert cli_arg._field_info is field_info

    def test_get_kebab_case_with_kebab_case_true(self):
        """Test get_kebab_case with kebab_case=True."""
        result = _CliArg.get_kebab_case('field_name', True)
        assert result == 'field-name'

    def test_get_kebab_case_with_kebab_case_false(self):
        """Test get_kebab_case with kebab_case=False."""
        result = _CliArg.get_kebab_case('field_name', False)
        assert result == 'field_name'

    def test_get_kebab_case_with_kebab_case_none(self):
        """Test get_kebab_case with kebab_case=None."""
        result = _CliArg.get_kebab_case('field_name', None)
        assert result == 'field_name'

    def test_get_kebab_case_with_kebab_case_all(self):
        """Test get_kebab_case with kebab_case='all'."""
        result = _CliArg.get_kebab_case('field_name', 'all')
        assert result == 'field-name'

    def test_get_kebab_case_with_kebab_case_no_enums(self):
        """Test get_kebab_case with kebab_case='no_enums'."""
        result = _CliArg.get_kebab_case('field_name', 'no_enums')
        assert result == 'field-name'

    def test_get_enum_names_with_enum(self):
        """Test get_enum_names with an Enum."""

        class Color(Enum):
            RED = 1
            GREEN = 2
            BLUE = 3

        result = _CliArg.get_enum_names(Color, False)
        assert 'RED' in result
        assert 'GREEN' in result
        assert 'BLUE' in result

    def test_get_enum_names_with_enum_kebab_case(self):
        """Test get_enum_names with an Enum and kebab_case."""

        class StatusEnum(Enum):
            ACTIVE_STATE = 1
            INACTIVE_STATE = 2

        result = _CliArg.get_enum_names(StatusEnum, 'all')
        assert 'ACTIVE-STATE' in result
        assert 'INACTIVE-STATE' in result

    def test_get_enum_names_non_enum(self):
        """Test get_enum_names with non-enum type."""
        result = _CliArg.get_enum_names(str, False)
        assert len(result) == 0

    def test_field_info_property(self):
        """Test field_info property."""
        field_info = FieldInfo(annotation=str, default='default')
        parser_map: defaultdict[str | FieldInfo, dict[int | None | str | type[BaseModel], _CliArg]] = defaultdict(dict)

        cli_arg = _CliArg(
            field_info=field_info,
            parser_map=parser_map,
            model=SimpleSettings,
            parser=ArgumentParser(),
            field_name='name',
            arg_prefix='',
            case_sensitive=True,
            populate_by_name=True,
            hide_none_type=False,
            kebab_case=False,
            enable_decoding=True,
            env_prefix_len=0,
        )

        assert cli_arg.field_info is field_info

    def test_alias_names_property(self):
        """Test alias_names property."""
        field_info = FieldInfo(annotation=str, default='default')
        parser_map: defaultdict[str | FieldInfo, dict[int | None | str | type[BaseModel], _CliArg]] = defaultdict(dict)

        cli_arg = _CliArg(
            field_info=field_info,
            parser_map=parser_map,
            model=SimpleSettings,
            parser=ArgumentParser(),
            field_name='name',
            arg_prefix='',
            case_sensitive=True,
            populate_by_name=True,
            hide_none_type=False,
            kebab_case=False,
            enable_decoding=True,
            env_prefix_len=0,
        )

        assert isinstance(cli_arg.alias_names, tuple)

    def test_is_append_action_with_list(self):
        """Test is_append_action with list field."""
        field_info = FieldInfo(annotation=list[str], default_factory=list)
        parser_map: defaultdict[str | FieldInfo, dict[int | None | str | type[BaseModel], _CliArg]] = defaultdict(dict)

        cli_arg = _CliArg(
            field_info=field_info,
            parser_map=parser_map,
            model=SimpleSettings,
            parser=ArgumentParser(),
            field_name='items',
            arg_prefix='',
            case_sensitive=True,
            populate_by_name=True,
            hide_none_type=False,
            kebab_case=False,
            enable_decoding=True,
            env_prefix_len=0,
        )

        assert cli_arg.is_append_action is True

    def test_is_append_action_with_string(self):
        """Test is_append_action with string field."""
        field_info = FieldInfo(annotation=str, default='default')
        parser_map: defaultdict[str | FieldInfo, dict[int | None | str | type[BaseModel], _CliArg]] = defaultdict(dict)

        cli_arg = _CliArg(
            field_info=field_info,
            parser_map=parser_map,
            model=SimpleSettings,
            parser=ArgumentParser(),
            field_name='name',
            arg_prefix='',
            case_sensitive=True,
            populate_by_name=True,
            hide_none_type=False,
            kebab_case=False,
            enable_decoding=True,
            env_prefix_len=0,
        )

        assert cli_arg.is_append_action is False


class TestCliSettingsSourceInit:
    """Tests for CliSettingsSource.__init__."""

    def test_init_basic(self):
        """Test basic initialization."""
        source = CliSettingsSource(
            settings_cls=SimpleSettings,
            cli_parse_args=None,
        )

        assert source.cli_hide_none_type is False
        assert source.cli_avoid_json is False
        assert source.cli_enforce_required is False

    def test_init_with_cli_prog_name(self):
        """Test initialization with custom cli_prog_name."""
        source = CliSettingsSource(
            settings_cls=SimpleSettings,
            cli_prog_name='my-program',
            cli_parse_args=None,
        )

        assert source.cli_prog_name == 'my-program'

    def test_init_with_cli_prefix(self):
        """Test initialization with cli_prefix."""
        source = CliSettingsSource(
            settings_cls=SimpleSettings,
            cli_prefix='app',
            cli_parse_args=None,
        )

        assert source.cli_prefix == 'app.'

    def test_init_with_invalid_cli_prefix_starts_with_dot(self):
        """Test initialization with invalid cli_prefix starting with dot."""
        from pydantic_settings.exceptions import SettingsError

        with pytest.raises(SettingsError, match='CLI settings source prefix is invalid'):
            CliSettingsSource(
                settings_cls=SimpleSettings,
                cli_prefix='.invalid',
                cli_parse_args=None,
            )

    def test_init_with_invalid_cli_prefix_ends_with_dot(self):
        """Test initialization with invalid cli_prefix ending with dot."""
        from pydantic_settings.exceptions import SettingsError

        with pytest.raises(SettingsError, match='CLI settings source prefix is invalid'):
            CliSettingsSource(
                settings_cls=SimpleSettings,
                cli_prefix='invalid.',
                cli_parse_args=None,
            )

    def test_init_with_invalid_cli_prefix_with_spaces(self):
        """Test initialization with invalid cli_prefix containing spaces."""
        from pydantic_settings.exceptions import SettingsError

        with pytest.raises(SettingsError, match='CLI settings source prefix is invalid'):
            CliSettingsSource(
                settings_cls=SimpleSettings,
                cli_prefix='in valid',
                cli_parse_args=None,
            )

    def test_init_with_cli_parse_none_str(self):
        """Test initialization with custom cli_parse_none_str."""
        source = CliSettingsSource(
            settings_cls=SimpleSettings,
            cli_parse_none_str='NONE',
            cli_parse_args=None,
        )

        assert source.cli_parse_none_str == 'NONE'

    def test_init_with_cli_parse_none_str_default_json(self):
        """Test default cli_parse_none_str with json (not avoid_json)."""
        source = CliSettingsSource(
            settings_cls=SimpleSettings,
            cli_avoid_json=False,
            cli_parse_args=None,
        )

        assert source.cli_parse_none_str == 'null'

    def test_init_with_cli_parse_none_str_default_avoid_json(self):
        """Test default cli_parse_none_str with avoid_json=True."""
        source = CliSettingsSource(
            settings_cls=SimpleSettings,
            cli_avoid_json=True,
            cli_parse_args=None,
        )

        assert source.cli_parse_none_str == 'None'

    def test_init_case_insensitive_with_custom_parser_error(self):
        """Test case-insensitive matching with custom parser raises error."""
        from pydantic_settings.exceptions import SettingsError

        parser = ArgumentParser()
        with pytest.raises(SettingsError, match='Case-insensitive matching is only supported'):
            CliSettingsSource(
                settings_cls=SimpleSettings,
                case_sensitive=False,
                root_parser=parser,
                cli_parse_args=None,
            )

    def test_init_with_cli_parse_args_invalid_type(self):
        """Test initialization with invalid cli_parse_args type."""
        from pydantic_settings.exceptions import SettingsError

        with pytest.raises(SettingsError, match='cli_parse_args must be a list or tuple'):
            CliSettingsSource(
                settings_cls=SimpleSettings,
                cli_parse_args={'invalid': 'type'},
            )

    def test_init_with_kebab_case(self):
        """Test initialization with kebab_case=True."""
        source = CliSettingsSource(
            settings_cls=SimpleSettings,
            cli_kebab_case=True,
            cli_parse_args=None,
        )

        assert source.cli_kebab_case is True

    def test_init_with_cli_implicit_flags(self):
        """Test initialization with cli_implicit_flags."""
        source = CliSettingsSource(
            settings_cls=SimpleSettings,
            cli_implicit_flags=True,
            cli_parse_args=None,
        )

        assert source.cli_implicit_flags is True


class TestCliSettingsSourceCall:
    """Tests for CliSettingsSource.__call__."""

    def test_call_with_args_false(self):
        """Test __call__ with args=False."""
        source = CliSettingsSource(
            settings_cls=SimpleSettings,
            cli_parse_args=None,
        )

        result = source(args=False)
        assert isinstance(result, CliSettingsSource)

    def test_call_with_args_true(self):
        """Test __call__ with args=True."""
        source = CliSettingsSource(
            settings_cls=SimpleSettings,
            cli_parse_args=None,
        )

        result = source(args=[])
        assert isinstance(result, CliSettingsSource)

    def test_call_with_parsed_args_namespace(self):
        """Test __call__ with parsed_args as Namespace."""
        source = CliSettingsSource(
            settings_cls=SimpleSettings,
            cli_parse_args=None,
        )

        result = source(parsed_args=Namespace(name='test'))
        assert isinstance(result, CliSettingsSource)

    def test_call_with_parsed_args_simple_namespace(self):
        """Test __call__ with parsed_args as SimpleNamespace."""
        source = CliSettingsSource(
            settings_cls=SimpleSettings,
            cli_parse_args=None,
        )

        result = source(parsed_args=SimpleNamespace(name='test'))
        assert isinstance(result, CliSettingsSource)

    def test_call_with_parsed_args_dict(self):
        """Test __call__ with parsed_args as dict."""
        source = CliSettingsSource(
            settings_cls=SimpleSettings,
            cli_parse_args=None,
        )

        result = source(parsed_args={'name': 'test'})
        assert isinstance(result, CliSettingsSource)

    def test_call_with_args_and_parsed_args_raises_error(self):
        """Test __call__ with both args and parsed_args raises error."""
        from pydantic_settings.exceptions import SettingsError

        source = CliSettingsSource(
            settings_cls=SimpleSettings,
            cli_parse_args=None,
        )

        with pytest.raises(SettingsError, match='`args` and `parsed_args` are mutually exclusive'):
            source(args=[], parsed_args={})

    def test_call_with_no_args(self):
        """Test __call__ with no arguments."""
        source = CliSettingsSource(
            settings_cls=SimpleSettings,
            cli_parse_args=None,
        )

        result = source()
        assert isinstance(result, dict)


class TestCliSettingsSourceLoadEnvVars:
    """Tests for CliSettingsSource._load_env_vars."""

    def test_load_env_vars_with_empty_dict(self):
        """Test _load_env_vars with empty parsed_args."""
        source = CliSettingsSource(
            settings_cls=SimpleSettings,
            cli_parse_args=None,
        )

        result = source._load_env_vars(parsed_args={})
        assert isinstance(result, CliSettingsSource)

    def test_load_env_vars_with_namespace(self):
        """Test _load_env_vars with Namespace object."""
        source = CliSettingsSource(
            settings_cls=SimpleSettings,
            cli_parse_args=None,
        )

        result = source._load_env_vars(parsed_args=Namespace(name='test'))
        assert isinstance(result, CliSettingsSource)

    def test_load_env_vars_with_none(self):
        """Test _load_env_vars with None."""
        source = CliSettingsSource(
            settings_cls=SimpleSettings,
            cli_parse_args=None,
        )

        result = source._load_env_vars(parsed_args=None)
        assert result == {}
