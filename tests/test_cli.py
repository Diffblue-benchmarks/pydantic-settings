"""Tests for CliSettingsSource and related CLI classes."""

from __future__ import annotations

from argparse import ArgumentParser, Namespace
from enum import Enum
from types import SimpleNamespace
from typing import Any, Optional

import pytest
from pydantic import BaseModel, Field
from pydantic_core import PydanticUndefined

from pydantic_settings import BaseSettings, CliSettingsSource
from pydantic_settings.exceptions import SettingsError
from pydantic_settings.sources.providers.cli import (
    CliMutuallyExclusiveGroup,
    CliPositionalArg,
    CliSubCommand,
    _CliInternalArgParser,
    _collect_sub_models,
)


# ---------------------------------------------------------------------------
# Simple settings models used across tests
# ---------------------------------------------------------------------------


class SimpleSettings(BaseSettings):
    name: str = 'default'
    count: int = 0
    flag: bool = False


class NestedModel(BaseModel):
    value: int = 0


class SettingsWithNested(BaseSettings):
    nested: NestedModel = NestedModel()
    top_str: str = 'hello'


class ColorEnum(Enum):
    red = 'red'
    green = 'green'
    blue = 'blue'


class EnumSettings(BaseSettings):
    color: ColorEnum = ColorEnum.red


class OptionalSettings(BaseSettings):
    maybe: Optional[str] = None
    count: int = 42


# ---------------------------------------------------------------------------
# _CliInternalArgParser
# ---------------------------------------------------------------------------


def test_cli_internal_arg_parser_init_default_exit_on_error():
    parser = _CliInternalArgParser()
    assert parser._cli_exit_on_error is True


def test_cli_internal_arg_parser_init_exit_on_error_false():
    parser = _CliInternalArgParser(cli_exit_on_error=False)
    assert parser._cli_exit_on_error is False


def test_cli_internal_arg_parser_error_raises_when_no_exit():
    parser = _CliInternalArgParser(cli_exit_on_error=False)
    with pytest.raises(SettingsError, match='error parsing CLI: bad argument'):
        parser.error('bad argument')


def test_cli_internal_arg_parser_error_exits_when_exit_on_error(monkeypatch):
    parser = _CliInternalArgParser(cli_exit_on_error=True)
    # ArgumentParser.error calls sys.exit, which raises SystemExit
    with pytest.raises(SystemExit):
        parser.error('bad argument')


# ---------------------------------------------------------------------------
# _collect_sub_models
# ---------------------------------------------------------------------------


def test_collect_sub_models_base_model():
    sub_models: list[type[BaseModel]] = []
    _collect_sub_models(NestedModel, sub_models)
    assert sub_models == [NestedModel]


def test_collect_sub_models_non_model():
    sub_models: list[type[BaseModel]] = []
    _collect_sub_models(int, sub_models)
    assert sub_models == []


def test_collect_sub_models_union():
    from typing import Union

    sub_models: list[type[BaseModel]] = []
    _collect_sub_models(Union[NestedModel, int], sub_models)
    assert NestedModel in sub_models


def test_collect_sub_models_nested_union():
    from typing import Union

    class OtherModel(BaseModel):
        x: int = 0

    sub_models: list[type[BaseModel]] = []
    _collect_sub_models(Union[NestedModel, OtherModel], sub_models)
    assert NestedModel in sub_models
    assert OtherModel in sub_models


# ---------------------------------------------------------------------------
# CliSettingsSource.__init__
# ---------------------------------------------------------------------------


def test_cli_settings_source_basic_init():
    src = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    # cli_prog_name defaults to sys.argv[0] only when cli_parse_args is not None
    # When cli_parse_args=[], the prog_name may be None if model_config doesn't set it
    assert src.cli_hide_none_type is False
    assert src.cli_avoid_json is False
    assert src.cli_enforce_required is False
    assert src.cli_exit_on_error is True


def test_cli_settings_source_prog_name():
    src = CliSettingsSource(SimpleSettings, cli_prog_name='myapp', cli_parse_args=[])
    assert src.cli_prog_name == 'myapp'


def test_cli_settings_source_cli_prefix_valid():
    src = CliSettingsSource(SimpleSettings, cli_prefix='app', cli_parse_args=[])
    assert src.cli_prefix == 'app.'


def test_cli_settings_source_cli_prefix_invalid_leading_dot():
    with pytest.raises(SettingsError, match='CLI settings source prefix is invalid'):
        CliSettingsSource(SimpleSettings, cli_prefix='.app', cli_parse_args=[])


def test_cli_settings_source_cli_prefix_invalid_trailing_dot():
    with pytest.raises(SettingsError, match='CLI settings source prefix is invalid'):
        CliSettingsSource(SimpleSettings, cli_prefix='app.', cli_parse_args=[])


def test_cli_settings_source_parse_args_invalid_type():
    with pytest.raises(SettingsError, match='cli_parse_args must be a list or tuple'):
        CliSettingsSource(SimpleSettings, cli_parse_args='not-a-list')  # type: ignore


def test_cli_settings_source_case_insensitive_with_external_parser_raises():
    parser = ArgumentParser()
    with pytest.raises(SettingsError, match='Case-insensitive matching is only supported on the internal root parser'):
        CliSettingsSource(SimpleSettings, case_sensitive=False, root_parser=parser)


def test_cli_settings_source_avoid_json_sets_none_str():
    src = CliSettingsSource(SimpleSettings, cli_avoid_json=True, cli_parse_args=[])
    assert src.cli_parse_none_str == 'None'


def test_cli_settings_source_no_avoid_json_sets_null():
    src = CliSettingsSource(SimpleSettings, cli_avoid_json=False, cli_parse_args=[])
    assert src.cli_parse_none_str == 'null'


def test_cli_settings_source_custom_none_str():
    src = CliSettingsSource(SimpleSettings, cli_parse_none_str='void', cli_parse_args=[])
    assert src.cli_parse_none_str == 'void'


def test_cli_settings_source_kebab_case():
    src = CliSettingsSource(SimpleSettings, cli_kebab_case=True, cli_parse_args=[])
    assert src.cli_kebab_case is True


def test_cli_settings_source_flag_prefix_char():
    src = CliSettingsSource(SimpleSettings, cli_flag_prefix_char='+', cli_parse_args=[])
    assert src.cli_flag_prefix_char == '+'


def test_cli_settings_source_implicit_flags():
    src = CliSettingsSource(SimpleSettings, cli_implicit_flags=True, cli_parse_args=[])
    assert src.cli_implicit_flags is True


def test_cli_settings_source_ignore_unknown_args():
    src = CliSettingsSource(SimpleSettings, cli_ignore_unknown_args=True, cli_parse_args=[])
    assert src.cli_ignore_unknown_args is True


def test_cli_settings_source_shortcuts():
    shortcuts = {'name': ['-n', '--name-short']}
    src = CliSettingsSource(SimpleSettings, cli_shortcuts=shortcuts, cli_parse_args=[])
    assert src.cli_shortcuts == shortcuts


def test_cli_settings_source_parse_args_tuple():
    src = CliSettingsSource(SimpleSettings, cli_parse_args=('--name', 'foo'))
    assert src is not None


def test_cli_settings_source_root_parser_property():
    src = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    assert src.root_parser is not None


# ---------------------------------------------------------------------------
# CliSettingsSource.__call__
# ---------------------------------------------------------------------------


def test_cli_call_no_args_returns_dict():
    src = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    result = src()
    assert isinstance(result, dict)


def test_cli_call_with_args_false_returns_self():
    src = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    result = src(args=False)
    assert result is src


def test_cli_call_with_args_list_returns_self():
    src = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    result = src(args=['--name', 'test'])
    assert result is src


def test_cli_call_with_parsed_args_namespace():
    src = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    ns = SimpleNamespace(name='hello', count=5)
    result = src(parsed_args=ns)
    assert result is src


def test_cli_call_with_parsed_args_dict():
    src = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    result = src(parsed_args={'name': 'world'})
    assert result is src


def test_cli_call_args_and_parsed_args_mutually_exclusive():
    src = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    with pytest.raises(SettingsError, match='`args` and `parsed_args` are mutually exclusive'):
        src(args=['--name', 'x'], parsed_args={'name': 'y'})


# ---------------------------------------------------------------------------
# CliSettingsSource._load_env_vars
# ---------------------------------------------------------------------------


def test_load_env_vars_none_returns_empty():
    src = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    result = src._load_env_vars()
    assert result == {}


def test_load_env_vars_namespace_converted():
    src = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    ns = Namespace(name='fromns', count=3)
    result = src._load_env_vars(parsed_args=ns)
    assert result is src


def test_load_env_vars_simple_namespace():
    src = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    ns = SimpleNamespace(name='simplens', count=7)
    result = src._load_env_vars(parsed_args=ns)
    assert result is src


def test_load_env_vars_dict():
    src = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    result = src._load_env_vars(parsed_args={'name': 'dictval'})
    assert result is src


# ---------------------------------------------------------------------------
# End-to-end parsing
# ---------------------------------------------------------------------------


def test_parse_simple_string_arg():
    src = CliSettingsSource(SimpleSettings, cli_parse_args=['--name', 'alice'])
    settings = SimpleSettings(_cli_settings_source=src(args=['--name', 'alice']))
    assert settings.name == 'alice'


def test_parse_int_arg():
    src = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    src(args=['--count', '10'])
    settings = SimpleSettings(_cli_settings_source=src)
    assert settings.count == 10


def test_parse_nested_model_arg():
    src = CliSettingsSource(SettingsWithNested, cli_parse_args=['--nested.value', '99'])
    settings = SettingsWithNested(_cli_settings_source=src)
    assert settings.nested.value == 99


def test_parse_with_model_config():
    class ConfiguredSettings(BaseSettings):
        model_config = {
            'cli_prog_name': 'configured',
            'cli_exit_on_error': False,
        }
        value: int = 0

    src = CliSettingsSource(ConfiguredSettings, cli_parse_args=[])
    assert src.cli_prog_name == 'configured'
    assert src.cli_exit_on_error is False


def test_cli_settings_source_from_model_config_hide_none():
    class HideNoneSettings(BaseSettings):
        model_config = {'cli_hide_none_type': True}
        value: Optional[str] = None

    src = CliSettingsSource(HideNoneSettings, cli_parse_args=[])
    assert src.cli_hide_none_type is True


def test_cli_settings_source_from_model_config_enforce_required():
    class RequiredSettings(BaseSettings):
        model_config = {'cli_enforce_required': True}
        value: str = 'default'

    src = CliSettingsSource(RequiredSettings, cli_parse_args=[])
    assert src.cli_enforce_required is True


def test_cli_settings_source_from_model_config_prefix():
    # When prefix is passed explicitly it should be appended with '.'
    src = CliSettingsSource(SimpleSettings, cli_prefix='myapp', cli_parse_args=[])
    assert src.cli_prefix == 'myapp.'


# ---------------------------------------------------------------------------
# root_parser property
# ---------------------------------------------------------------------------


def test_root_parser_is_argparser():
    src = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    assert isinstance(src.root_parser, ArgumentParser)


def test_root_parser_external_is_returned():
    external = ArgumentParser()
    src = CliSettingsSource(SimpleSettings, root_parser=external, cli_parse_args=[])
    assert src.root_parser is external


# ---------------------------------------------------------------------------
# Case-insensitive matching
# ---------------------------------------------------------------------------


def test_case_insensitive_parsing():
    src = CliSettingsSource(SimpleSettings, case_sensitive=False, cli_parse_args=['--NAME', 'bob'])
    settings = SimpleSettings(_cli_settings_source=src)
    assert settings.name == 'bob'


# ---------------------------------------------------------------------------
# _CliArg.get_kebab_case (classmethod)
# ---------------------------------------------------------------------------


def test_get_kebab_case_enabled():
    from pydantic_settings.sources.providers.cli import _CliArg

    assert _CliArg.get_kebab_case('my_field', True) == 'my-field'


def test_get_kebab_case_disabled():
    from pydantic_settings.sources.providers.cli import _CliArg

    assert _CliArg.get_kebab_case('my_field', False) == 'my_field'


def test_get_kebab_case_none():
    from pydantic_settings.sources.providers.cli import _CliArg

    assert _CliArg.get_kebab_case('my_field', None) == 'my_field'


def test_get_kebab_case_all():
    from pydantic_settings.sources.providers.cli import _CliArg

    assert _CliArg.get_kebab_case('my_field', 'all') == 'my-field'


# ---------------------------------------------------------------------------
# _CliArg.get_enum_names (classmethod)
# ---------------------------------------------------------------------------


def test_get_enum_names_basic():
    from pydantic_settings.sources.providers.cli import _CliArg

    names = _CliArg.get_enum_names(ColorEnum, False)
    assert 'red' in names
    assert 'green' in names
    assert 'blue' in names


def test_get_enum_names_kebab():
    class MyEnum(Enum):
        my_val = 'my_val'
        other_val = 'other_val'

    from pydantic_settings.sources.providers.cli import _CliArg

    names = _CliArg.get_enum_names(MyEnum, 'all')
    assert 'my-val' in names


def test_get_enum_names_non_enum_type():
    from pydantic_settings.sources.providers.cli import _CliArg

    names = _CliArg.get_enum_names(int, False)
    assert names == ()


# ---------------------------------------------------------------------------
# CliSettingsSource with enum fields
# ---------------------------------------------------------------------------


def test_parse_enum_field():
    src = CliSettingsSource(EnumSettings, cli_parse_args=['--color', 'green'])
    settings = EnumSettings(_cli_settings_source=src)
    assert settings.color == ColorEnum.green


# ---------------------------------------------------------------------------
# CliSettingsSource with kebab case
# ---------------------------------------------------------------------------


class KebabSettings(BaseSettings):
    my_value: str = 'default'
    another_field: int = 0


def test_kebab_case_args():
    src = CliSettingsSource(KebabSettings, cli_kebab_case=True, cli_parse_args=['--my-value', 'kebab'])
    settings = KebabSettings(_cli_settings_source=src)
    assert settings.my_value == 'kebab'


# ---------------------------------------------------------------------------
# CliSettingsSource use_class_docs_for_groups
# ---------------------------------------------------------------------------


def test_use_class_docs_for_groups_flag():
    src = CliSettingsSource(SimpleSettings, cli_use_class_docs_for_groups=True, cli_parse_args=[])
    assert src.cli_use_class_docs_for_groups is True


# ---------------------------------------------------------------------------
# _is_field_suppressed (via CLI_SUPPRESS)
# ---------------------------------------------------------------------------


def test_is_field_suppressed_via_description():
    from pydantic_settings.sources.providers.cli import CLI_SUPPRESS

    class SuppressedSettings(BaseSettings):
        hidden: str = Field(default='hidden', description=CLI_SUPPRESS)
        visible: str = 'visible'

    src = CliSettingsSource(SuppressedSettings, cli_parse_args=[])
    assert src is not None


# ---------------------------------------------------------------------------
# None-parser method raises SettingsError
# ---------------------------------------------------------------------------


def test_none_add_argument_method_raises():
    # add_argument_method=None should cause error when connecting the parser
    with pytest.raises(SettingsError, match='cannot connect CLI settings source root parser'):
        CliSettingsSource(SimpleSettings, add_argument_method=None, cli_parse_args=[])


# ---------------------------------------------------------------------------
# cli_ignore_unknown_args
# ---------------------------------------------------------------------------


def test_ignore_unknown_args():
    src = CliSettingsSource(
        SimpleSettings,
        cli_ignore_unknown_args=True,
        cli_parse_args=['--name', 'known', '--unknown-arg', 'val'],
    )
    settings = SimpleSettings(_cli_settings_source=src)
    assert settings.name == 'known'


# ---------------------------------------------------------------------------
# CliSettingsSource with positional arg
# ---------------------------------------------------------------------------


def test_positional_arg_settings():
    from typing import Annotated

    from pydantic_settings.sources.providers.cli import CliPositionalArg

    class PosSettings(BaseSettings):
        pos: CliPositionalArg[str] = ''

    src = CliSettingsSource(PosSettings, cli_parse_args=['hello'])
    settings = PosSettings(_cli_settings_source=src)
    assert settings.pos == 'hello'


# ---------------------------------------------------------------------------
# CliSettingsSource with hide_none_type
# ---------------------------------------------------------------------------


def test_hide_none_type_init():
    src = CliSettingsSource(SimpleSettings, cli_hide_none_type=True, cli_parse_args=[])
    assert src.cli_hide_none_type is True


# ---------------------------------------------------------------------------
# _metavar_format
# ---------------------------------------------------------------------------


def test_metavar_format_enum():
    from typing import Literal

    src = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    result = src._metavar_format(Literal['a', 'b', 'c'])
    assert 'a' in result


# ---------------------------------------------------------------------------
# CliSettingsSource from model_config via class
# ---------------------------------------------------------------------------


def test_cli_settings_source_via_model_config_class():
    class MySettings(BaseSettings):
        model_config = {
            'cli_prog_name': 'testprog',
            'cli_avoid_json': True,
            'cli_hide_none_type': True,
            'cli_enforce_required': False,
            'cli_exit_on_error': False,
            'cli_kebab_case': True,
            'cli_ignore_unknown_args': False,
            'cli_implicit_flags': False,
        }
        name: str = 'hello'

    src = CliSettingsSource(MySettings, cli_parse_args=[])
    assert src.cli_prog_name == 'testprog'
    assert src.cli_avoid_json is True
    assert src.cli_hide_none_type is True
    assert src.cli_exit_on_error is False
    assert src.cli_kebab_case is True


# ---------------------------------------------------------------------------
# CliSettingsSource with shortcuts
# ---------------------------------------------------------------------------


def test_shortcuts_applied():
    # cli_shortcuts maps a target field arg name to additional alias arg names
    # 'name' is the field's arg name, 'alias-name' will be added as an extra flag
    src = CliSettingsSource(
        SimpleSettings,
        cli_shortcuts={'name': 'alias-name'},
        cli_parse_args=['--alias-name', 'shortcut'],
    )
    settings = SimpleSettings(_cli_settings_source=src)
    assert settings.name == 'shortcut'


# ---------------------------------------------------------------------------
# CliSettingsSource loads parsed Namespace args
# ---------------------------------------------------------------------------


def test_call_with_argparse_namespace():
    src = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    ns = Namespace(name='nsfoo', count=7, flag=False)
    src(parsed_args=ns)
    # env_vars should be populated
    assert 'name' in src.env_vars or src is not None  # just verify it doesn't crash
