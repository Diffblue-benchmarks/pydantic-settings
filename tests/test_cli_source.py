"""Tests for CliSettingsSource."""

import sys
from argparse import ArgumentParser, Namespace
from enum import Enum
from typing import Annotated, Union

import pytest
from pydantic import BaseModel, Field

from pydantic_settings import BaseSettings
from pydantic_settings.exceptions import SettingsError
from pydantic_settings.sources.providers.cli import (
    CliSettingsSource,
    CliSubCommand,
    CliPositionalArg,
    CliImplicitFlag,
    CliExplicitFlag,
    CliToggleFlag,
    CliDualFlag,
    _CliInternalArgParser,
    _collect_sub_models,
    _CliArg,
)
from pydantic_settings.sources.types import NoDecode, ForceDecode, _CliSubCommand


class TestCliInternalArgParser:
    """Tests for _CliInternalArgParser class."""

    def test_init_with_exit_on_error_true(self):
        """Test __init__ when cli_exit_on_error is True."""
        parser = _CliInternalArgParser(cli_exit_on_error=True, prog="test")
        assert parser._cli_exit_on_error is True

    def test_init_with_exit_on_error_false(self):
        """Test __init__ when cli_exit_on_error is False."""
        parser = _CliInternalArgParser(cli_exit_on_error=False, prog="test")
        assert parser._cli_exit_on_error is False

    def test_error_with_exit_on_error_false(self):
        """Test error method when cli_exit_on_error is False raises SettingsError."""
        parser = _CliInternalArgParser(cli_exit_on_error=False, prog="test")
        with pytest.raises(SettingsError, match="error parsing CLI:"):
            parser.error("test error message")

    def test_error_with_exit_on_error_true(self):
        """Test error method when cli_exit_on_error is True exits."""
        parser = _CliInternalArgParser(cli_exit_on_error=True, prog="test")
        with pytest.raises(SystemExit):
            parser.error("test error message")


class TestCollectSubModels:
    """Tests for _collect_sub_models function."""

    def test_collect_sub_models_with_base_model(self):
        """Test _collect_sub_models with a BaseModel type."""
        class SubModel(BaseModel):
            value: str

        sub_models = []
        _collect_sub_models(SubModel, sub_models)
        assert len(sub_models) == 1
        assert sub_models[0] is SubModel

    def test_collect_sub_models_with_union(self):
        """Test _collect_sub_models with a Union type."""
        class SubModel1(BaseModel):
            value1: str

        class SubModel2(BaseModel):
            value2: int

        sub_models = []
        _collect_sub_models(Union[SubModel1, SubModel2], sub_models)
        assert len(sub_models) == 2
        assert SubModel1 in sub_models
        assert SubModel2 in sub_models

    def test_collect_sub_models_with_annotated(self):
        """Test _collect_sub_models with Annotated type."""
        class SubModel(BaseModel):
            value: str

        sub_models = []
        _collect_sub_models(Annotated[SubModel, "metadata"], sub_models)
        assert len(sub_models) == 1
        assert sub_models[0] is SubModel

    def test_collect_sub_models_with_non_model(self):
        """Test _collect_sub_models with non-BaseModel type."""
        sub_models = []
        _collect_sub_models(str, sub_models)
        assert len(sub_models) == 0


class TestCliArg:
    """Tests for _CliArg class."""

    def test_get_kebab_case_with_true(self):
        """Test get_kebab_case with kebab_case=True."""
        result = _CliArg.get_kebab_case("test_name", True)
        assert result == "test-name"

    def test_get_kebab_case_with_false(self):
        """Test get_kebab_case with kebab_case=False."""
        result = _CliArg.get_kebab_case("test_name", False)
        assert result == "test_name"

    def test_get_kebab_case_with_none(self):
        """Test get_kebab_case with kebab_case=None."""
        result = _CliArg.get_kebab_case("test_name", None)
        assert result == "test_name"

    def test_get_kebab_case_with_all(self):
        """Test get_kebab_case with kebab_case='all'."""
        result = _CliArg.get_kebab_case("test_name", "all")
        assert result == "test-name"

    def test_get_enum_names_with_enum(self):
        """Test get_enum_names with an Enum type."""
        class Color(Enum):
            RED = "red"
            BLUE = "blue"
            GREEN_YELLOW = "green_yellow"

        result = _CliArg.get_enum_names(Color, False)
        assert "RED" in result
        assert "BLUE" in result
        assert "GREEN_YELLOW" in result

    def test_get_enum_names_with_kebab_case_all(self):
        """Test get_enum_names with kebab_case='all'."""
        class Color(Enum):
            RED = "red"
            GREEN_YELLOW = "green_yellow"

        result = _CliArg.get_enum_names(Color, "all")
        assert "RED" in result
        assert "GREEN-YELLOW" in result

    def test_get_enum_names_with_union(self):
        """Test get_enum_names with Union of Enums."""
        class Color(Enum):
            RED = "red"

        class Size(Enum):
            LARGE = "large"

        result = _CliArg.get_enum_names(Union[Color, Size], False)
        assert "RED" in result
        assert "LARGE" in result


class TestCliSettingsSource:
    """Tests for CliSettingsSource class."""

    def test_init_basic(self):
        """Test basic __init__ with minimal configuration."""
        class Settings(BaseSettings):
            value: str = "default"

        source = CliSettingsSource(settings_cls=Settings)
        assert source.cli_prefix == ""
        assert source.cli_exit_on_error is True
        assert source.cli_avoid_json is False

    def test_init_with_cli_prefix(self):
        """Test __init__ with cli_prefix."""
        class Settings(BaseSettings):
            value: str = "default"

        source = CliSettingsSource(settings_cls=Settings, cli_prefix="app")
        assert source.cli_prefix == "app."

    def test_init_with_invalid_cli_prefix_start_dot(self):
        """Test __init__ with invalid cli_prefix starting with dot."""
        class Settings(BaseSettings):
            value: str = "default"

        with pytest.raises(SettingsError, match="CLI settings source prefix is invalid"):
            CliSettingsSource(settings_cls=Settings, cli_prefix=".invalid")

    def test_init_with_invalid_cli_prefix_end_dot(self):
        """Test __init__ with invalid cli_prefix ending with dot."""
        class Settings(BaseSettings):
            value: str = "default"

        with pytest.raises(SettingsError, match="CLI settings source prefix is invalid"):
            CliSettingsSource(settings_cls=Settings, cli_prefix="invalid.")

    def test_init_with_invalid_cli_prefix_non_identifier(self):
        """Test __init__ with invalid cli_prefix that's not an identifier."""
        class Settings(BaseSettings):
            value: str = "default"

        with pytest.raises(SettingsError, match="CLI settings source prefix is invalid"):
            CliSettingsSource(settings_cls=Settings, cli_prefix="invalid-name")

    def test_init_with_case_sensitive_and_root_parser(self):
        """Test __init__ with case_sensitive=False and custom root_parser raises error."""
        class Settings(BaseSettings):
            value: str = "default"

        custom_parser = ArgumentParser()
        with pytest.raises(SettingsError, match="Case-insensitive matching is only supported"):
            CliSettingsSource(settings_cls=Settings, case_sensitive=False, root_parser=custom_parser)

    def test_init_with_cli_parse_args_list(self):
        """Test __init__ with cli_parse_args as list."""
        class Settings(BaseSettings):
            value: str = "default"

        source = CliSettingsSource(settings_cls=Settings, cli_parse_args=["--value", "test"])
        data = source()
        assert data.get("value") == "test"

    def test_init_with_cli_parse_args_tuple(self):
        """Test __init__ with cli_parse_args as tuple."""
        class Settings(BaseSettings):
            value: str = "default"

        source = CliSettingsSource(settings_cls=Settings, cli_parse_args=("--value", "test"))
        data = source()
        assert data.get("value") == "test"

    def test_init_with_cli_parse_args_true(self):
        """Test __init__ with cli_parse_args=True uses sys.argv."""
        class Settings(BaseSettings):
            value: str = "default"

        original_argv = sys.argv
        try:
            sys.argv = ["prog", "--value", "from_argv"]
            source = CliSettingsSource(settings_cls=Settings, cli_parse_args=True)
            data = source()
            assert data.get("value") == "from_argv"
        finally:
            sys.argv = original_argv

    def test_init_with_invalid_cli_parse_args_type(self):
        """Test __init__ with invalid cli_parse_args type."""
        class Settings(BaseSettings):
            value: str = "default"

        with pytest.raises(SettingsError, match="cli_parse_args must be a list or tuple"):
            CliSettingsSource(settings_cls=Settings, cli_parse_args="invalid")

    def test_init_with_cli_hide_none_type(self):
        """Test __init__ with cli_hide_none_type."""
        class Settings(BaseSettings):
            value: str = "default"

        source = CliSettingsSource(settings_cls=Settings, cli_hide_none_type=True)
        assert source.cli_hide_none_type is True

    def test_init_with_cli_avoid_json(self):
        """Test __init__ with cli_avoid_json."""
        class Settings(BaseSettings):
            value: str = "default"

        source = CliSettingsSource(settings_cls=Settings, cli_avoid_json=True)
        assert source.cli_avoid_json is True
        assert source.cli_parse_none_str == "None"

    def test_init_with_cli_parse_none_str(self):
        """Test __init__ with custom cli_parse_none_str."""
        class Settings(BaseSettings):
            value: str = "default"

        source = CliSettingsSource(settings_cls=Settings, cli_parse_none_str="nil")
        assert source.cli_parse_none_str == "nil"

    def test_init_with_cli_enforce_required(self):
        """Test __init__ with cli_enforce_required."""
        class Settings(BaseSettings):
            value: str

        source = CliSettingsSource(settings_cls=Settings, cli_enforce_required=True)
        assert source.cli_enforce_required is True

    def test_init_with_cli_use_class_docs_for_groups(self):
        """Test __init__ with cli_use_class_docs_for_groups."""
        class Settings(BaseSettings):
            value: str = "default"

        source = CliSettingsSource(settings_cls=Settings, cli_use_class_docs_for_groups=True)
        assert source.cli_use_class_docs_for_groups is True

    def test_init_with_cli_exit_on_error_false(self):
        """Test __init__ with cli_exit_on_error=False."""
        class Settings(BaseSettings):
            value: str = "default"

        source = CliSettingsSource(settings_cls=Settings, cli_exit_on_error=False)
        assert source.cli_exit_on_error is False

    def test_init_with_cli_flag_prefix_char(self):
        """Test __init__ with custom cli_flag_prefix_char."""
        class Settings(BaseSettings):
            value: str = "default"

        source = CliSettingsSource(settings_cls=Settings, cli_flag_prefix_char="+")
        assert source.cli_flag_prefix_char == "+"
        assert source._cli_flag_prefix == "++"

    def test_init_with_cli_implicit_flags(self):
        """Test __init__ with cli_implicit_flags."""
        class Settings(BaseSettings):
            value: bool = False

        source = CliSettingsSource(settings_cls=Settings, cli_implicit_flags=True)
        assert source.cli_implicit_flags is True

    def test_init_with_cli_implicit_flags_dual(self):
        """Test __init__ with cli_implicit_flags='dual'."""
        class Settings(BaseSettings):
            value: bool = False

        source = CliSettingsSource(settings_cls=Settings, cli_implicit_flags="dual")
        assert source.cli_implicit_flags == "dual"

    def test_init_with_cli_implicit_flags_toggle(self):
        """Test __init__ with cli_implicit_flags='toggle'."""
        class Settings(BaseSettings):
            value: bool = False

        source = CliSettingsSource(settings_cls=Settings, cli_implicit_flags="toggle")
        assert source.cli_implicit_flags == "toggle"

    def test_init_with_cli_ignore_unknown_args(self):
        """Test __init__ with cli_ignore_unknown_args."""
        class Settings(BaseSettings):
            value: str = "default"

        source = CliSettingsSource(settings_cls=Settings, cli_ignore_unknown_args=True)
        assert source.cli_ignore_unknown_args is True

    def test_init_with_cli_kebab_case(self):
        """Test __init__ with cli_kebab_case."""
        class Settings(BaseSettings):
            test_value: str = "default"

        source = CliSettingsSource(settings_cls=Settings, cli_kebab_case=True)
        assert source.cli_kebab_case is True

    def test_init_with_cli_kebab_case_all(self):
        """Test __init__ with cli_kebab_case='all'."""
        class Settings(BaseSettings):
            test_value: str = "default"

        source = CliSettingsSource(settings_cls=Settings, cli_kebab_case="all")
        assert source.cli_kebab_case == "all"

    def test_init_with_cli_kebab_case_no_enums(self):
        """Test __init__ with cli_kebab_case='no_enums'."""
        class Settings(BaseSettings):
            test_value: str = "default"

        source = CliSettingsSource(settings_cls=Settings, cli_kebab_case="no_enums")
        assert source.cli_kebab_case == "no_enums"

    def test_init_with_cli_shortcuts(self):
        """Test __init__ with cli_shortcuts."""
        class Settings(BaseSettings):
            value: str = "default"

        shortcuts = {"value": ["v", "val"]}
        source = CliSettingsSource(settings_cls=Settings, cli_shortcuts=shortcuts)
        assert source.cli_shortcuts == shortcuts

    def test_init_with_model_config_values(self):
        """Test __init__ with values from model_config."""
        class Settings(BaseSettings):
            value: str = "default"
            model_config = {
                "cli_prog_name": "myapp",
                "cli_hide_none_type": True,
                "cli_avoid_json": True,
                "cli_enforce_required": True,
                "cli_use_class_docs_for_groups": True,
                "cli_exit_on_error": False,
                "cli_flag_prefix_char": "+",
                "cli_implicit_flags": True,
                "cli_ignore_unknown_args": True,
                "cli_kebab_case": True,
            }

        source = CliSettingsSource(settings_cls=Settings)
        assert source.cli_prog_name == "myapp"
        assert source.cli_hide_none_type is True
        assert source.cli_avoid_json is True
        assert source.cli_enforce_required is True
        assert source.cli_use_class_docs_for_groups is True
        assert source.cli_exit_on_error is False
        assert source.cli_flag_prefix_char == "+"
        assert source.cli_implicit_flags is True
        assert source.cli_ignore_unknown_args is True
        assert source.cli_kebab_case is True

    def test_call_with_no_args(self):
        """Test __call__ with no arguments returns dict."""
        class Settings(BaseSettings):
            value: str = "default"

        source = CliSettingsSource(settings_cls=Settings)
        result = source()
        assert isinstance(result, dict)

    def test_call_with_args_and_parsed_args_raises_error(self):
        """Test __call__ with both args and parsed_args raises error."""
        class Settings(BaseSettings):
            value: str = "default"

        source = CliSettingsSource(settings_cls=Settings)
        with pytest.raises(SettingsError, match="mutually exclusive"):
            source(args=["--value", "test"], parsed_args=Namespace(value="test"))

    def test_call_with_args_false(self):
        """Test __call__ with args=False."""
        class Settings(BaseSettings):
            value: str = "default"

        source = CliSettingsSource(settings_cls=Settings)
        result = source(args=False)
        assert isinstance(result, CliSettingsSource)

    def test_call_with_args_true(self):
        """Test __call__ with args=True uses sys.argv."""
        class Settings(BaseSettings):
            value: str = "default"

        original_argv = sys.argv
        try:
            sys.argv = ["prog", "--value", "from_argv"]
            source = CliSettingsSource(settings_cls=Settings)
            result = source(args=True)
            assert isinstance(result, CliSettingsSource)
        finally:
            sys.argv = original_argv

    def test_call_with_args_list(self):
        """Test __call__ with args as list."""
        class Settings(BaseSettings):
            value: str = "default"

        source = CliSettingsSource(settings_cls=Settings)
        result = source(args=["--value", "test"])
        assert isinstance(result, CliSettingsSource)

    def test_call_with_parsed_args_namespace(self):
        """Test __call__ with parsed_args as Namespace."""
        class Settings(BaseSettings):
            value: str = "default"

        source = CliSettingsSource(settings_cls=Settings)
        result = source(parsed_args=Namespace(value="test"))
        assert isinstance(result, CliSettingsSource)

    def test_root_parser_property(self):
        """Test root_parser property access."""
        class Settings(BaseSettings):
            value: str = "default"

        source = CliSettingsSource(settings_cls=Settings)
        assert source.root_parser is not None
        assert hasattr(source.root_parser, "parse_args")

    def test_init_with_case_sensitive_default(self):
        """Test __init__ with default case_sensitive value."""
        class Settings(BaseSettings):
            Value: str = "default"

        source = CliSettingsSource(settings_cls=Settings, case_sensitive=True)
        assert source.case_sensitive is True

    def test_init_with_docstring(self):
        """Test __init__ with Settings class that has a docstring."""
        class Settings(BaseSettings):
            """
            This is a test settings class.
            It has multiple lines.
            """
            value: str = "default"

        source = CliSettingsSource(settings_cls=Settings)
        assert source.root_parser is not None

    def test_init_with_no_docstring(self):
        """Test __init__ with Settings class that has no docstring."""
        class Settings(BaseSettings):
            value: str = "default"

        source = CliSettingsSource(settings_cls=Settings)
        assert source.root_parser is not None


class TestCliArgProperties:
    """Tests for _CliArg property methods."""

    def test_subcommand_alias_single_model(self):
        """Test subcommand_alias with single sub_model."""
        from collections import defaultdict

        class SubModel(BaseModel):
            value: str

        class Settings(BaseSettings):
            sub: Annotated[SubModel, CliSubCommand] = None

        field_info = Settings.model_fields["sub"]
        parser_map = defaultdict(dict)

        cli_arg = _CliArg(
            field_info=field_info,
            parser_map=parser_map,
            model=Settings,
            parser=None,
            field_name="sub",
            arg_prefix="",
            case_sensitive=True,
            populate_by_name=False,
            hide_none_type=False,
            kebab_case=False,
            enable_decoding=None,
            env_prefix_len=0,
        )

        # Access sub_models to populate them
        sub_models = cli_arg.sub_models
        if sub_models:
            alias = cli_arg.subcommand_alias(sub_models[0])
            assert isinstance(alias, str)

    def test_field_info_property(self):
        """Test field_info property."""
        from collections import defaultdict

        class Settings(BaseSettings):
            value: str = "default"

        field_info = Settings.model_fields["value"]
        parser_map = defaultdict(dict)

        cli_arg = _CliArg(
            field_info=field_info,
            parser_map=parser_map,
            model=Settings,
            parser=None,
            field_name="value",
            arg_prefix="",
            case_sensitive=True,
            populate_by_name=False,
            hide_none_type=False,
            kebab_case=False,
            enable_decoding=None,
            env_prefix_len=0,
        )

        assert cli_arg.field_info is field_info

    def test_subcommand_dest_with_subcommand(self):
        """Test subcommand_dest property with CliSubCommand metadata."""
        from collections import defaultdict

        class SubModel(BaseModel):
            value: str

        class Settings(BaseSettings):
            sub: Annotated[SubModel | None, _CliSubCommand] = None

        field_info = Settings.model_fields["sub"]
        parser_map = defaultdict(dict)

        cli_arg = _CliArg(
            field_info=field_info,
            parser_map=parser_map,
            model=Settings,
            parser=None,
            field_name="sub",
            arg_prefix="",
            case_sensitive=True,
            populate_by_name=False,
            hide_none_type=False,
            kebab_case=False,
            enable_decoding=None,
            env_prefix_len=0,
        )

        assert cli_arg.subcommand_dest == ":subcommand"

    def test_subcommand_dest_without_subcommand(self):
        """Test subcommand_dest property without CliSubCommand metadata."""
        from collections import defaultdict

        class Settings(BaseSettings):
            value: str = "default"

        field_info = Settings.model_fields["value"]
        parser_map = defaultdict(dict)

        cli_arg = _CliArg(
            field_info=field_info,
            parser_map=parser_map,
            model=Settings,
            parser=None,
            field_name="value",
            arg_prefix="",
            case_sensitive=True,
            populate_by_name=False,
            hide_none_type=False,
            kebab_case=False,
            enable_decoding=None,
            env_prefix_len=0,
        )

        assert cli_arg.subcommand_dest is None

    def test_dest_property_basic(self):
        """Test dest property for basic field."""
        from collections import defaultdict

        class Settings(BaseSettings):
            value: str = "default"

        field_info = Settings.model_fields["value"]
        parser_map = defaultdict(dict)

        cli_arg = _CliArg(
            field_info=field_info,
            parser_map=parser_map,
            model=Settings,
            parser=None,
            field_name="value",
            arg_prefix="",
            case_sensitive=True,
            populate_by_name=False,
            hide_none_type=False,
            kebab_case=False,
            enable_decoding=None,
            env_prefix_len=0,
        )

        assert cli_arg.dest == "value"

    def test_preferred_arg_name_without_kebab_case(self):
        """Test preferred_arg_name without kebab_case."""
        from collections import defaultdict

        class Settings(BaseSettings):
            test_value: str = "default"

        field_info = Settings.model_fields["test_value"]
        parser_map = defaultdict(dict)

        cli_arg = _CliArg(
            field_info=field_info,
            parser_map=parser_map,
            model=Settings,
            parser=None,
            field_name="test_value",
            arg_prefix="",
            case_sensitive=True,
            populate_by_name=False,
            hide_none_type=False,
            kebab_case=False,
            enable_decoding=None,
            env_prefix_len=0,
        )

        # Set args for preferred_arg_name
        cli_arg.args = ["test_value"]
        assert cli_arg.preferred_arg_name == "test_value"

    def test_preferred_arg_name_with_kebab_case(self):
        """Test preferred_arg_name with kebab_case."""
        from collections import defaultdict

        class Settings(BaseSettings):
            test_value: str = "default"

        field_info = Settings.model_fields["test_value"]
        parser_map = defaultdict(dict)

        cli_arg = _CliArg(
            field_info=field_info,
            parser_map=parser_map,
            model=Settings,
            parser=None,
            field_name="test_value",
            arg_prefix="",
            case_sensitive=True,
            populate_by_name=False,
            hide_none_type=False,
            kebab_case=True,
            enable_decoding=None,
            env_prefix_len=0,
        )

        cli_arg.args = ["test_value"]
        assert cli_arg.preferred_arg_name == "test-value"

    def test_alias_names_property(self):
        """Test alias_names property."""
        from collections import defaultdict

        class Settings(BaseSettings):
            value: str = Field(default="default", validation_alias="val")

        field_info = Settings.model_fields["value"]
        parser_map = defaultdict(dict)

        cli_arg = _CliArg(
            field_info=field_info,
            parser_map=parser_map,
            model=Settings,
            parser=None,
            field_name="value",
            arg_prefix="",
            case_sensitive=True,
            populate_by_name=False,
            hide_none_type=False,
            kebab_case=False,
            enable_decoding=None,
            env_prefix_len=0,
        )

        assert isinstance(cli_arg.alias_names, tuple)

    def test_alias_paths_property(self):
        """Test alias_paths property."""
        from collections import defaultdict

        class Settings(BaseSettings):
            value: str = "default"

        field_info = Settings.model_fields["value"]
        parser_map = defaultdict(dict)

        cli_arg = _CliArg(
            field_info=field_info,
            parser_map=parser_map,
            model=Settings,
            parser=None,
            field_name="value",
            arg_prefix="",
            case_sensitive=True,
            populate_by_name=False,
            hide_none_type=False,
            kebab_case=False,
            enable_decoding=None,
            env_prefix_len=0,
        )

        assert isinstance(cli_arg.alias_paths, dict)

    def test_preferred_alias_property(self):
        """Test preferred_alias property."""
        from collections import defaultdict

        class Settings(BaseSettings):
            value: str = "default"

        field_info = Settings.model_fields["value"]
        parser_map = defaultdict(dict)

        cli_arg = _CliArg(
            field_info=field_info,
            parser_map=parser_map,
            model=Settings,
            parser=None,
            field_name="value",
            arg_prefix="",
            case_sensitive=True,
            populate_by_name=False,
            hide_none_type=False,
            kebab_case=False,
            enable_decoding=None,
            env_prefix_len=0,
        )

        assert cli_arg.preferred_alias == "value"

    def test_is_alias_path_only_property(self):
        """Test is_alias_path_only property."""
        from collections import defaultdict

        class Settings(BaseSettings):
            value: str = "default"

        field_info = Settings.model_fields["value"]
        parser_map = defaultdict(dict)

        cli_arg = _CliArg(
            field_info=field_info,
            parser_map=parser_map,
            model=Settings,
            parser=None,
            field_name="value",
            arg_prefix="",
            case_sensitive=True,
            populate_by_name=False,
            hide_none_type=False,
            kebab_case=False,
            enable_decoding=None,
            env_prefix_len=0,
        )

        assert isinstance(cli_arg.is_alias_path_only, bool)

    def test_is_append_action_with_list(self):
        """Test is_append_action property with list type."""
        from collections import defaultdict

        class Settings(BaseSettings):
            values: list[str] = []

        field_info = Settings.model_fields["values"]
        parser_map = defaultdict(dict)

        cli_arg = _CliArg(
            field_info=field_info,
            parser_map=parser_map,
            model=Settings,
            parser=None,
            field_name="values",
            arg_prefix="",
            case_sensitive=True,
            populate_by_name=False,
            hide_none_type=False,
            kebab_case=False,
            enable_decoding=None,
            env_prefix_len=0,
        )

        assert cli_arg.is_append_action is True

    def test_is_append_action_without_list(self):
        """Test is_append_action property without list type."""
        from collections import defaultdict

        class Settings(BaseSettings):
            value: str = "default"

        field_info = Settings.model_fields["value"]
        parser_map = defaultdict(dict)

        cli_arg = _CliArg(
            field_info=field_info,
            parser_map=parser_map,
            model=Settings,
            parser=None,
            field_name="value",
            arg_prefix="",
            case_sensitive=True,
            populate_by_name=False,
            hide_none_type=False,
            kebab_case=False,
            enable_decoding=None,
            env_prefix_len=0,
        )

        assert cli_arg.is_append_action is False

    def test_is_parser_submodel_with_submodel(self):
        """Test is_parser_submodel property with submodel."""
        from collections import defaultdict

        class SubModel(BaseModel):
            value: str

        class Settings(BaseSettings):
            sub: SubModel

        field_info = Settings.model_fields["sub"]
        parser_map = defaultdict(dict)

        cli_arg = _CliArg(
            field_info=field_info,
            parser_map=parser_map,
            model=Settings,
            parser=None,
            field_name="sub",
            arg_prefix="",
            case_sensitive=True,
            populate_by_name=False,
            hide_none_type=False,
            kebab_case=False,
            enable_decoding=None,
            env_prefix_len=0,
        )

        assert cli_arg.is_parser_submodel is True

    def test_is_parser_submodel_without_submodel(self):
        """Test is_parser_submodel property without submodel."""
        from collections import defaultdict

        class Settings(BaseSettings):
            value: str = "default"

        field_info = Settings.model_fields["value"]
        parser_map = defaultdict(dict)

        cli_arg = _CliArg(
            field_info=field_info,
            parser_map=parser_map,
            model=Settings,
            parser=None,
            field_name="value",
            arg_prefix="",
            case_sensitive=True,
            populate_by_name=False,
            hide_none_type=False,
            kebab_case=False,
            enable_decoding=None,
            env_prefix_len=0,
        )

        assert cli_arg.is_parser_submodel is False

    def test_is_no_decode_with_nodecode_metadata(self):
        """Test is_no_decode property with NoDecode metadata."""
        from collections import defaultdict

        class Settings(BaseSettings):
            value: Annotated[str, NoDecode] = "default"

        field_info = Settings.model_fields["value"]
        parser_map = defaultdict(dict)

        cli_arg = _CliArg(
            field_info=field_info,
            parser_map=parser_map,
            model=Settings,
            parser=None,
            field_name="value",
            arg_prefix="",
            case_sensitive=True,
            populate_by_name=False,
            hide_none_type=False,
            kebab_case=False,
            enable_decoding=None,
            env_prefix_len=0,
        )

        assert cli_arg.is_no_decode is True

    def test_is_no_decode_with_enable_decoding_false(self):
        """Test is_no_decode property with enable_decoding=False."""
        from collections import defaultdict

        class Settings(BaseSettings):
            value: str = "default"

        field_info = Settings.model_fields["value"]
        parser_map = defaultdict(dict)

        cli_arg = _CliArg(
            field_info=field_info,
            parser_map=parser_map,
            model=Settings,
            parser=None,
            field_name="value",
            arg_prefix="",
            case_sensitive=True,
            populate_by_name=False,
            hide_none_type=False,
            kebab_case=False,
            enable_decoding=False,
            env_prefix_len=0,
        )

        assert cli_arg.is_no_decode is True

    def test_is_no_decode_with_force_decode(self):
        """Test is_no_decode property with ForceDecode metadata."""
        from collections import defaultdict

        class Settings(BaseSettings):
            value: Annotated[str, ForceDecode] = "default"

        field_info = Settings.model_fields["value"]
        parser_map = defaultdict(dict)

        cli_arg = _CliArg(
            field_info=field_info,
            parser_map=parser_map,
            model=Settings,
            parser=None,
            field_name="value",
            arg_prefix="",
            case_sensitive=True,
            populate_by_name=False,
            hide_none_type=False,
            kebab_case=False,
            enable_decoding=False,
            env_prefix_len=0,
        )

        assert cli_arg.is_no_decode is False
