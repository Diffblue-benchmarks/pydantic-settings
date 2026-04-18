"""Tests for CLI settings source."""

import enum
from typing import Annotated, List, Literal, Optional, Union

import pytest

from pydantic import AliasChoices, AliasPath, BaseModel, Field
from pydantic.fields import FieldInfo

from pydantic_settings import BaseSettings, CliSettingsSource, CliSubCommand
from pydantic_settings.exceptions import SettingsError
from pydantic_settings.sources.providers.cli import (
    CliSettingsSource as _CliSettingsSourceDirect,
    _CliArg,
    _CliInternalArgParser,
    _collect_sub_models,
)
from pydantic_settings.sources.types import (
    NoDecode,
    ForceDecode,
    _CliDualFlag,
    _CliExplicitFlag,
    _CliImplicitFlag,
    _CliPositionalArg,
    _CliSubCommand,
    _CliToggleFlag,
)


# ---- Models used in tests ----

class SimpleSettings(BaseSettings):
    name: str = 'default'
    count: int = 0

    model_config = {'env_file': None}


class NestedModel(BaseModel):
    host: str = 'localhost'
    port: int = 8080


class SettingsWithNested(BaseSettings):
    db: NestedModel = NestedModel()
    name: str = 'app'

    model_config = {'env_file': None}


class SubCommandA(BaseModel):
    alpha: str = 'a'

    def cli_cmd(self) -> None:
        pass


class SubCommandB(BaseModel):
    beta: str = 'b'

    def cli_cmd(self) -> None:
        pass


class SettingsWithSubcommand(BaseSettings):
    sub: CliSubCommand[Union[SubCommandA, SubCommandB]]

    model_config = {'env_file': None}


class Color(enum.Enum):
    RED = 'red'
    GREEN = 'green'
    BLUE = 'blue'


class SettingsWithEnum(BaseSettings):
    color: Color = Color.RED

    model_config = {'env_file': None}


class SettingsWithBool(BaseSettings):
    flag: bool = False

    model_config = {'env_file': None}


class SettingsWithList(BaseSettings):
    items: list[str] = []

    model_config = {'env_file': None}


class SettingsWithDict(BaseSettings):
    config: dict[str, str] = {}

    model_config = {'env_file': None}


class SettingsWithOptional(BaseSettings):
    maybe: Optional[str] = None

    model_config = {'env_file': None}


class SettingsWithKebab(BaseSettings):
    my_field_name: str = 'test'

    model_config = {'env_file': None, 'cli_kebab_case': True}


class SettingsWithPrefix(BaseSettings):
    name: str = 'default'

    model_config = {'env_file': None, 'cli_prefix': 'app'}


class SettingsWithAvoidJson(BaseSettings):
    name: str = 'default'

    model_config = {'env_file': None, 'cli_avoid_json': True}


class SettingsWithClassDocs(BaseSettings):
    """App settings help text."""
    name: str = 'default'

    model_config = {'env_file': None}


# ---- _CliInternalArgParser tests ----

class TestCliInternalArgParser:
    def test_init_default(self):
        parser = _CliInternalArgParser()
        assert parser._cli_exit_on_error is True

    def test_init_exit_on_error_false(self):
        parser = _CliInternalArgParser(cli_exit_on_error=False)
        assert parser._cli_exit_on_error is False

    def test_init_exit_on_error_true(self):
        parser = _CliInternalArgParser(cli_exit_on_error=True)
        assert parser._cli_exit_on_error is True

    def test_error_raises_settings_error_when_exit_disabled(self):
        parser = _CliInternalArgParser(cli_exit_on_error=False)
        with pytest.raises(SettingsError, match='error parsing CLI'):
            parser.error('some error message')

    def test_error_exits_when_exit_enabled(self):
        parser = _CliInternalArgParser(cli_exit_on_error=True, prog='test')
        with pytest.raises(SystemExit):
            parser.error('some error message')


# ---- _collect_sub_models tests ----

class TestCollectSubModels:
    def test_collect_single_model(self):
        sub_models: list[type[BaseModel]] = []
        _collect_sub_models(SubCommandA, sub_models)
        assert sub_models == [SubCommandA]

    def test_collect_union_models(self):
        sub_models: list[type[BaseModel]] = []
        _collect_sub_models(Union[SubCommandA, SubCommandB], sub_models)
        assert SubCommandA in sub_models
        assert SubCommandB in sub_models

    def test_collect_non_model(self):
        sub_models: list[type[BaseModel]] = []
        _collect_sub_models(str, sub_models)
        assert sub_models == []

    def test_collect_optional_model(self):
        sub_models: list[type[BaseModel]] = []
        _collect_sub_models(Optional[SubCommandA], sub_models)
        assert SubCommandA in sub_models


# ---- _CliArg class method tests ----

class TestCliArgClassMethods:
    def test_get_kebab_case_enabled(self):
        assert _CliArg.get_kebab_case('my_field', True) == 'my-field'

    def test_get_kebab_case_disabled(self):
        assert _CliArg.get_kebab_case('my_field', False) == 'my_field'

    def test_get_kebab_case_none(self):
        assert _CliArg.get_kebab_case('my_field', None) == 'my_field'

    def test_get_kebab_case_all(self):
        assert _CliArg.get_kebab_case('my_field', 'all') == 'my-field'

    def test_get_kebab_case_no_enums(self):
        assert _CliArg.get_kebab_case('my_field', 'no_enums') == 'my-field'

    def test_get_enum_names_basic(self):
        names = _CliArg.get_enum_names(Color, None)
        assert 'RED' in names
        assert 'GREEN' in names
        assert 'BLUE' in names

    def test_get_enum_names_kebab(self):
        class SnakeEnum(enum.Enum):
            my_val = 'x'
            other_val = 'y'

        names = _CliArg.get_enum_names(SnakeEnum, 'all')
        assert 'my-val' in names
        assert 'other-val' in names

    def test_get_enum_names_non_enum(self):
        names = _CliArg.get_enum_names(str, None)
        assert names == ()


# ---- CliSettingsSource basic init tests ----

class TestCliSettingsSourceInit:
    def test_init_basic(self):
        source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
        assert source.cli_exit_on_error is True
        assert source.cli_hide_none_type is False
        assert source.cli_avoid_json is False
        assert source.cli_enforce_required is False
        assert source.cli_use_class_docs_for_groups is False
        assert source.cli_kebab_case is False
        assert source.cli_implicit_flags is False
        assert source.cli_ignore_unknown_args is False

    def test_init_with_custom_options(self):
        source = CliSettingsSource(
            SimpleSettings,
            cli_parse_args=[],
            cli_hide_none_type=True,
            cli_avoid_json=True,
            cli_enforce_required=True,
            cli_use_class_docs_for_groups=True,
            cli_exit_on_error=False,
            cli_kebab_case=True,
            cli_implicit_flags=True,
            cli_ignore_unknown_args=True,
        )
        assert source.cli_hide_none_type is True
        assert source.cli_avoid_json is True
        assert source.cli_enforce_required is True
        assert source.cli_use_class_docs_for_groups is True
        assert source.cli_exit_on_error is False
        assert source.cli_kebab_case is True
        assert source.cli_implicit_flags is True
        assert source.cli_ignore_unknown_args is True

    def test_init_parse_none_str_default(self):
        source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
        assert source.cli_parse_none_str == 'null'

    def test_init_parse_none_str_avoid_json(self):
        source = CliSettingsSource(SimpleSettings, cli_parse_args=[], cli_avoid_json=True)
        assert source.cli_parse_none_str == 'None'

    def test_init_parse_none_str_custom(self):
        source = CliSettingsSource(SimpleSettings, cli_parse_args=[], cli_parse_none_str='nil')
        assert source.cli_parse_none_str == 'nil'

    def test_init_invalid_prefix(self):
        with pytest.raises(SettingsError, match='CLI settings source prefix is invalid'):
            CliSettingsSource(SimpleSettings, cli_parse_args=[], cli_prefix='.bad')

    def test_init_invalid_prefix_trailing_dot(self):
        with pytest.raises(SettingsError, match='CLI settings source prefix is invalid'):
            CliSettingsSource(SimpleSettings, cli_parse_args=[], cli_prefix='bad.')

    def test_init_valid_prefix(self):
        source = CliSettingsSource(SimpleSettings, cli_parse_args=[], cli_prefix='myapp')
        assert source.cli_prefix == 'myapp.'

    def test_init_case_insensitive_with_external_parser_raises(self):
        from argparse import ArgumentParser

        external_parser = ArgumentParser()
        with pytest.raises(SettingsError, match='Case-insensitive matching is only supported'):
            CliSettingsSource(SimpleSettings, case_sensitive=False, root_parser=external_parser)

    def test_init_prog_name(self):
        source = CliSettingsSource(SimpleSettings, cli_parse_args=[], cli_prog_name='myapp')
        assert source.cli_prog_name == 'myapp'

    def test_init_flag_prefix_char(self):
        source = CliSettingsSource(SimpleSettings, cli_parse_args=[], cli_flag_prefix_char='+')
        assert source.cli_flag_prefix_char == '+'

    def test_root_parser_property(self):
        source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
        assert source.root_parser is not None


# ---- CliSettingsSource.__call__ tests ----

class TestCliSettingsSourceCall:
    def test_call_without_args_returns_dict(self):
        source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
        result = source()
        assert isinstance(result, dict)

    def test_call_with_args_returns_source(self):
        source = CliSettingsSource(SimpleSettings)
        result = source(args=['--name', 'test'])
        assert isinstance(result, CliSettingsSource)

    def test_call_with_args_false_returns_source(self):
        source = CliSettingsSource(SimpleSettings)
        result = source(args=False)
        assert isinstance(result, CliSettingsSource)

    def test_call_with_parsed_args_returns_source(self):
        source = CliSettingsSource(SimpleSettings)
        result = source(parsed_args={'name': 'test'})
        assert isinstance(result, CliSettingsSource)

    def test_call_with_both_args_and_parsed_raises(self):
        source = CliSettingsSource(SimpleSettings)
        with pytest.raises(SettingsError, match='`args` and `parsed_args` are mutually exclusive'):
            source(args=['--name', 'test'], parsed_args={'name': 'test'})


# ---- Parsing args tests ----

class TestCliSettingsSourceParsing:
    def test_parse_simple_args(self):
        source = CliSettingsSource(SimpleSettings, cli_parse_args=['--name', 'hello', '--count', '42'])
        result = source()
        assert result['name'] == 'hello'
        assert result['count'] == '42'

    def test_parse_no_args(self):
        source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
        result = source()
        assert result == {}

    def test_parse_with_nested_model(self):
        source = CliSettingsSource(SettingsWithNested, cli_parse_args=['--db.host', 'remotehost', '--db.port', '5432'])
        result = source()
        assert result.get('db.host') == 'remotehost' or result.get('db', {}).get('host') == 'remotehost'

    def test_parse_bool_value(self):
        source = CliSettingsSource(SettingsWithBool, cli_parse_args=['--flag', 'true'])
        result = source()
        assert result['flag'] == 'true'

    def test_parse_list_value(self):
        source = CliSettingsSource(SettingsWithList, cli_parse_args=['--items', '["a","b","c"]'])
        result = source()
        assert 'items' in result

    def test_parse_dict_value(self):
        source = CliSettingsSource(SettingsWithDict, cli_parse_args=['--config', '{"key": "val"}'])
        result = source()
        assert 'config' in result

    def test_parse_optional_null(self):
        source = CliSettingsSource(SettingsWithOptional, cli_parse_args=['--maybe', 'null'])
        result = source()
        assert result['maybe'] is None


# ---- Kebab case tests ----

class TestCliKebabCase:
    def test_kebab_case_arg_name(self):
        source = CliSettingsSource(SettingsWithKebab, cli_parse_args=['--my-field-name', 'value'])
        result = source()
        assert result['my_field_name'] == 'value'


# ---- Integration: BaseSettings with CLI ----

class TestBaseSettingsCliIntegration:
    def test_simple_cli_parse(self):
        settings = SimpleSettings(_cli_parse_args=['--name', 'world', '--count', '10'])
        assert settings.name == 'world'
        assert settings.count == 10

    def test_defaults_when_no_args(self):
        settings = SimpleSettings(_cli_parse_args=[])
        assert settings.name == 'default'
        assert settings.count == 0

    def test_nested_model_cli(self):
        settings = SettingsWithNested(_cli_parse_args=['--db.host', 'myhost', '--db.port', '3306'])
        assert settings.db.host == 'myhost'
        assert settings.db.port == 3306

    def test_enum_cli(self):
        settings = SettingsWithEnum(_cli_parse_args=['--color', 'GREEN'])
        assert settings.color == Color.GREEN

    def test_bool_cli(self):
        settings = SettingsWithBool(_cli_parse_args=['--flag', 'true'])
        assert settings.flag is True

    def test_list_cli(self):
        settings = SettingsWithList(_cli_parse_args=['--items', '["x","y"]'])
        assert settings.items == ['x', 'y']

    def test_dict_cli(self):
        settings = SettingsWithDict(_cli_parse_args=['--config', '{"k": "v"}'])
        assert settings.config == {'k': 'v'}

    def test_optional_null_cli(self):
        settings = SettingsWithOptional(_cli_parse_args=['--maybe', 'null'])
        assert settings.maybe is None


# ---- Bool flag tests ----

class TestCliBoolFlags:
    def test_implicit_flags_dual(self):
        source = CliSettingsSource(SettingsWithBool, cli_parse_args=['--flag'], cli_implicit_flags=True)
        result = source()
        assert result['flag'] is True

    def test_implicit_flags_no_flag(self):
        source = CliSettingsSource(SettingsWithBool, cli_parse_args=['--no-flag'], cli_implicit_flags=True)
        result = source()
        assert result['flag'] is False


# ---- Enforce required tests ----

class TestCliEnforceRequired:
    def test_enforce_required_missing_field(self):
        class RequiredSettings(BaseSettings):
            name: str

            model_config = {'env_file': None}

        with pytest.raises(SettingsError, match='error parsing CLI'):
            CliSettingsSource(RequiredSettings, cli_parse_args=[], cli_enforce_required=True, cli_exit_on_error=False)


# ---- Case insensitivity tests ----

class TestCliCaseInsensitive:
    def test_case_insensitive_parsing(self):
        source = CliSettingsSource(SimpleSettings, cli_parse_args=['--NAME', 'upper'], case_sensitive=False)
        result = source()
        assert result['name'] == 'upper'


# ---- Ignore unknown args ----

class TestCliIgnoreUnknownArgs:
    def test_ignore_unknown_args(self):
        source = CliSettingsSource(
            SimpleSettings, cli_parse_args=['--name', 'test', '--unknown', 'val'], cli_ignore_unknown_args=True
        )
        result = source()
        assert result['name'] == 'test'


# ---- _consume_comma tests ----

class TestConsumeHelpers:
    def test_consume_comma_empty_value(self):
        source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
        merged = []
        result = source._consume_comma(',rest', merged, False)
        assert result == 'rest'
        assert merged == ['""']

    def test_consume_comma_after_value(self):
        source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
        merged = ['existing']
        result = source._consume_comma(',rest', merged, True)
        assert result == 'rest'
        assert merged == ['existing']


# ---- _consume_object_or_array tests ----

class TestConsumeObjectOrArray:
    def test_consume_simple_object(self):
        source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
        merged = []
        result = source._consume_object_or_array('{"key": "val"}rest', merged)
        assert merged == ['{"key": "val"}']
        assert result == 'rest'

    def test_consume_simple_array(self):
        source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
        merged = []
        result = source._consume_object_or_array('["a","b"]rest', merged)
        assert merged == ['["a","b"]']
        assert result == 'rest'

    def test_consume_nested_object(self):
        source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
        merged = []
        result = source._consume_object_or_array('{"a": {"b": 1}}', merged)
        assert merged == ['{"a": {"b": 1}}']
        assert result == ''

    def test_consume_missing_end_delimiter(self):
        source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
        merged = []
        with pytest.raises(SettingsError, match='Missing end delimiter'):
            source._consume_object_or_array('{"key": "val"', merged)


# ---- _flatten_serialized_args tests ----

class TestFlattenSerializedArgs:
    def test_optional_first(self):
        args = {'optional': ['--name', 'a'], 'positional': ['pos'], 'subcommand': ['sub']}
        result = CliSettingsSource._flatten_serialized_args(args, positionals_first=False)
        assert result == ['--name', 'a', 'pos', 'sub']

    def test_positionals_first(self):
        args = {'optional': ['--name', 'a'], 'positional': ['pos'], 'subcommand': ['sub']}
        result = CliSettingsSource._flatten_serialized_args(args, positionals_first=True)
        assert result == ['pos', '--name', 'a', 'sub']


# ---- _is_field_suppressed tests ----

class TestIsFieldSuppressed:
    def test_not_suppressed(self):
        source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
        field_info = FieldInfo(annotation=str, default='test')
        assert source._is_field_suppressed(field_info) is False

    def test_suppressed_via_description(self):
        from argparse import SUPPRESS
        source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
        field_info = FieldInfo(annotation=str, default='test', description=SUPPRESS)
        assert source._is_field_suppressed(field_info) is True


# ---- _metavar_format tests ----

class TestMetavarFormat:
    def test_metavar_str(self):
        source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
        result = source._metavar_format(str)
        assert result == 'str'

    def test_metavar_int(self):
        source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
        result = source._metavar_format(int)
        assert result == 'int'

    def test_metavar_bool(self):
        source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
        result = source._metavar_format(bool)
        assert result == 'bool'

    def test_metavar_enum(self):
        source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
        result = source._metavar_format(Color)
        assert 'RED' in result
        assert 'GREEN' in result
        assert 'BLUE' in result

    def test_metavar_list(self):
        source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
        result = source._metavar_format(list[str])
        assert 'str' in result

    def test_metavar_optional(self):
        source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
        result = source._metavar_format(Optional[str])
        assert 'str' in result
        assert 'null' in result

    def test_metavar_literal(self):
        source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
        result = source._metavar_format(Literal['a', 'b'])
        assert 'a' in result
        assert 'b' in result


# ---- _get_modified_args tests ----

class TestGetModifiedArgs:
    def test_no_hide_none(self):
        source = CliSettingsSource(SimpleSettings, cli_parse_args=[], cli_hide_none_type=False)
        result = source._get_modified_args(Optional[str])
        assert type(None) in result

    def test_hide_none(self):
        source = CliSettingsSource(SimpleSettings, cli_parse_args=[], cli_hide_none_type=True)
        result = source._get_modified_args(Optional[str])
        assert type(None) not in result


# ---- _metavar_format_choices tests ----

class TestMetavarFormatChoices:
    def test_single_choice(self):
        source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
        result = source._metavar_format_choices(['str'])
        assert result == 'str'

    def test_multiple_choices(self):
        source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
        result = source._metavar_format_choices(['str', 'int'])
        assert result == '{str,int}'

    def test_choices_with_qualname(self):
        source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
        result = source._metavar_format_choices(['str', 'int'], obj_qualname='list')
        assert result == 'list[str,int]'

    def test_choices_dedup_json(self):
        source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
        result = source._metavar_format_choices(['str', 'JSON', 'int', 'JSON'])
        assert result == '{str,JSON,int}'


# ---- Subcommand tests ----

class TestCliSubcommand:
    def test_subcommand_parsing(self):
        settings = SettingsWithSubcommand(_cli_parse_args=['SubCommandA', '--alpha', 'test'])
        assert settings.sub is not None
        assert isinstance(settings.sub, SubCommandA)
        assert settings.sub.alpha == 'test'

    def test_subcommand_second_option(self):
        settings = SettingsWithSubcommand(_cli_parse_args=['SubCommandB', '--beta', 'hello'])
        assert isinstance(settings.sub, SubCommandB)
        assert settings.sub.beta == 'hello'


# ---- Avoid json tests ----

class TestCliAvoidJson:
    def test_avoid_json_parse_none_str(self):
        source = CliSettingsSource(SimpleSettings, cli_parse_args=[], cli_avoid_json=True)
        assert source.cli_parse_none_str == 'None'


# ---- Help format tests ----

class TestCliHelpFormat:
    def test_help_format_with_default(self):
        source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
        from pydantic_core import PydanticUndefined

        field_info = SimpleSettings.model_fields['name']
        result = source._help_format('name', field_info, PydanticUndefined, False)
        assert 'default' in result

    def test_help_format_required(self):
        class ReqSettings(BaseSettings):
            name: str
            model_config = {'env_file': None}

        source = CliSettingsSource(ReqSettings, cli_parse_args=[])
        from pydantic_core import PydanticUndefined

        field_info = ReqSettings.model_fields['name']
        result = source._help_format('name', field_info, PydanticUndefined, False)
        assert 'required' in result


# ---- Sort arg fields validation tests ----

class TestSortArgFields:
    def test_subcommand_with_default_raises(self):
        class BadSettings(BaseSettings):
            sub: Annotated[Optional[SubCommandA], _CliSubCommand] = None
            model_config = {'env_file': None}

        source = CliSettingsSource.__new__(CliSettingsSource)
        with pytest.raises(SettingsError, match='has a default value'):
            source._sort_arg_fields(BadSettings)


# ---- Verify CLI flag annotations tests ----

class TestVerifyCliFlagAnnotations:
    def test_non_bool_implicit_flag_raises(self):
        """CliImplicitFlag on a non-bool field should raise when building the model."""

        with pytest.raises(SettingsError, match='is not of type bool'):
            class BadImplicitSettings(BaseSettings):
                field: Annotated[str, _CliImplicitFlag] = 'test'
                model_config = {'env_file': None}

            CliSettingsSource(BadImplicitSettings, cli_parse_args=[])

    def test_non_bool_explicit_flag_raises(self):
        with pytest.raises(SettingsError, match='is not of type bool'):
            class BadExplicitSettings(BaseSettings):
                field: Annotated[str, _CliExplicitFlag] = 'test'
                model_config = {'env_file': None}

            CliSettingsSource(BadExplicitSettings, cli_parse_args=[])

    def test_non_bool_dual_flag_raises(self):
        with pytest.raises(SettingsError, match='is not of type bool'):
            class BadDualSettings(BaseSettings):
                field: Annotated[str, _CliDualFlag] = 'test'
                model_config = {'env_file': None}

            CliSettingsSource(BadDualSettings, cli_parse_args=[])

    def test_toggle_flag_without_bool_default_raises(self):
        with pytest.raises(SettingsError, match='must have a default bool value'):
            class BadToggleSettings(BaseSettings):
                field: Annotated[bool, _CliToggleFlag] = Field(default='not_bool')  # type: ignore
                model_config = {'env_file': None}

            CliSettingsSource(BadToggleSettings, cli_parse_args=[])

    def test_bool_implicit_flag_passes(self):
        class GoodImplicitSettings(BaseSettings):
            field: Annotated[bool, _CliImplicitFlag] = False
            model_config = {'env_file': None}

        # Should not raise
        source = CliSettingsSource(GoodImplicitSettings, cli_parse_args=[])
        assert source is not None


# ---- Convert append action tests ----

class TestConvertAppendAction:
    def test_convert_append_action_list(self):
        source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
        kwargs = {'dest': 'items'}
        field_info = FieldInfo(annotation=list[str], default=[])
        source._convert_append_action(kwargs, field_info, True)
        assert kwargs['action'] == 'append'

    def test_convert_append_action_false(self):
        source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
        kwargs = {'dest': 'items'}
        field_info = FieldInfo(annotation=str, default='test')
        source._convert_append_action(kwargs, field_info, False)
        assert 'action' not in kwargs


# ---- _coerce_value_styles tests ----

class TestCoerceValueStyles:
    def test_json_list_style(self):
        source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
        result = source._coerce_value_styles(['a', 'b'], '["a", "b"]', list_style='json')
        assert result == ['["a", "b"]']

    def test_argparse_list_style(self):
        source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
        result = source._coerce_value_styles(['a', 'b'], '["a", "b"]', list_style='argparse')
        assert result == ['a', 'b']

    def test_lazy_list_style(self):
        source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
        result = source._coerce_value_styles(['a', 'b'], '["a", "b"]', list_style='lazy')
        assert result == ['a,b']

    def test_env_dict_style(self):
        source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
        result = source._coerce_value_styles({'k': 'v'}, '{"k": "v"}', dict_style='env')
        assert result == ['k=v']

    def test_json_dict_style(self):
        source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
        result = source._coerce_value_styles({'k': 'v'}, '{"k": "v"}', dict_style='json')
        assert result == ['{"k": "v"}']


# ---- Shortcuts tests ----

class TestCliShortcuts:
    def test_shortcut_mapping(self):
        source = CliSettingsSource(
            SimpleSettings,
            cli_parse_args=['-n', 'shortcut_val'],
            cli_shortcuts={'name': 'n'},
        )
        result = source()
        assert result['name'] == 'shortcut_val'


# ---- connect_parser_method tests ----

class TestConnectParserMethod:
    def test_none_parser_method_raises(self):
        source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
        method = source._connect_parser_method(None, 'test_method')
        with pytest.raises(SettingsError, match='cannot connect CLI settings source root parser'):
            method()


# ---- Prefix tests ----

class TestCliPrefix:
    def test_prefix_parsing(self):
        source = CliSettingsSource(SettingsWithPrefix, cli_parse_args=['--app.name', 'prefixed'], cli_prefix='app')
        result = source()
        assert result['name'] == 'prefixed'
