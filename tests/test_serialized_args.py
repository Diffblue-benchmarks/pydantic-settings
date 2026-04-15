"""Tests for CliSettingsSource._serialized_args method."""
from __future__ import annotations

import json
from typing import Optional

import pytest
from pydantic import AliasPath, BaseModel, Field
from pydantic.dataclasses import dataclass as pydantic_dataclass

from pydantic_settings import BaseSettings, CliApp, CliPositionalArg, CliSettingsSource, CliSubCommand
from pydantic_settings.main import SettingsConfigDict


# --- Shared models ---


class SimpleSettings(BaseSettings):
    name: str = 'default'
    value: int = 0


class NestedModel(BaseModel):
    x: int = 1
    y: int = 2


class SettingsWithNested(BaseSettings):
    nested: NestedModel = Field(default_factory=NestedModel)
    top: str = 'top'


class ListSettings(BaseSettings):
    items: list[str] = Field(default_factory=list)


class DictSettings(BaseSettings):
    config: dict[str, str] = Field(default_factory=dict)


# --- Tests for _serialized_args initialization and loop (lines 1480-1493) ---


def test_serialized_args_returns_expected_structure():
    """Calling _serialized_args returns a dict with optional/positional/subcommand keys."""
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    model = SimpleSettings.model_construct(name='hello', value=0)
    result = source._serialized_args(model)
    assert 'optional' in result
    assert 'positional' in result
    assert 'subcommand' in result
    assert isinstance(result['optional'], list)
    assert isinstance(result['positional'], list)
    assert isinstance(result['subcommand'], list)


def test_serialized_args_skips_default_values():
    """Fields whose value equals the field default should not appear in output."""
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    model = SimpleSettings.model_construct(name='default', value=0)
    result = source._serialized_args(model)
    assert result['optional'] == []
    assert result['positional'] == []
    assert result['subcommand'] == []


def test_serialized_args_basic_optional_field():
    """Non-default string field produces the flag name and value in optional args."""
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    model = SimpleSettings.model_construct(name='hello', value=0)
    result = source._serialized_args(model)
    assert '--name' in result['optional']
    assert 'hello' in result['optional']


def test_serialized_args_integer_optional_field():
    """Non-default integer field is serialized as a string in optional args."""
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    model = SimpleSettings.model_construct(name='default', value=42)
    result = source._serialized_args(model)
    assert '--value' in result['optional']
    assert '42' in result['optional']


def test_serialized_args_multiple_non_default_fields():
    """Multiple non-default fields all appear in the optional output."""
    source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
    model = SimpleSettings.model_construct(name='test', value=99)
    result = source._serialized_args(model)
    assert '--name' in result['optional']
    assert 'test' in result['optional']
    assert '--value' in result['optional']
    assert '99' in result['optional']


# --- Tests for value assignment and optional args loop (lines 1515-1542) ---


def test_serialized_args_dict_value_is_json_encoded():
    """dict model_default is json-encoded in optional args (line 1518 branch)."""
    source = CliSettingsSource(DictSettings, cli_parse_args=[])
    model = DictSettings.model_construct(config={'key': 'val'})
    result = source._serialized_args(model)
    assert '--config' in result['optional']
    idx = result['optional'].index('--config')
    parsed = json.loads(result['optional'][idx + 1])
    assert parsed == {'key': 'val'}


def test_serialized_args_list_value_is_json_encoded():
    """list model_default is json-encoded in optional args (line 1518 branch)."""
    source = CliSettingsSource(ListSettings, cli_parse_args=[])
    model = ListSettings.model_construct(items=['a', 'b'])
    result = source._serialized_args(model)
    assert '--items' in result['optional']
    idx = result['optional'].index('--items')
    parsed = json.loads(result['optional'][idx + 1])
    assert parsed == ['a', 'b']


# --- Tests for list_style / dict_style coercion (lines 1537-1538, 1541-1542) ---


def test_serialized_args_list_style_argparse():
    """list_style='argparse' produces one flag per element in optional args."""
    source = CliSettingsSource(ListSettings, cli_parse_args=[])
    model = ListSettings.model_construct(items=['x', 'y', 'z'])
    result = source._serialized_args(model, list_style='argparse')
    assert result['optional'].count('--items') == 3
    assert 'x' in result['optional']
    assert 'y' in result['optional']
    assert 'z' in result['optional']


def test_serialized_args_list_style_lazy():
    """list_style='lazy' produces comma-separated values."""
    source = CliSettingsSource(ListSettings, cli_parse_args=[])
    model = ListSettings.model_construct(items=['a', 'b', 'c'])
    result = source._serialized_args(model, list_style='lazy')
    assert '--items' in result['optional']
    idx = result['optional'].index('--items')
    assert result['optional'][idx + 1] == 'a,b,c'


def test_serialized_args_dict_style_env():
    """dict_style='env' produces key=value pairs in optional args."""
    source = CliSettingsSource(DictSettings, cli_parse_args=[])
    model = DictSettings.model_construct(config={'host': 'localhost', 'port': '5432'})
    result = source._serialized_args(model, dict_style='env')
    assert 'host=localhost' in result['optional']
    assert 'port=5432' in result['optional']


# --- Tests for BooleanOptionalAction with False (lines 1534-1535) ---


def test_serialized_args_bool_optional_action_false_prepends_no():
    """BooleanOptionalAction field with False value prepends 'no-' to flag name."""
    class BoolOptSettings(BaseSettings):
        model_config = SettingsConfigDict(cli_implicit_flags=True)
        flag: bool = True

    source = CliSettingsSource(BoolOptSettings, cli_parse_args=[])
    model = BoolOptSettings.model_construct(flag=False)
    result = source._serialized_args(model)
    assert '--no-flag' in result['optional']


def test_serialized_args_bool_optional_action_true_no_prepend():
    """BooleanOptionalAction field with True value (default False) uses normal flag."""
    class BoolOptSettings(BaseSettings):
        model_config = SettingsConfigDict(cli_implicit_flags=True)
        flag: bool = False

    source = CliSettingsSource(BoolOptSettings, cli_parse_args=[])
    model = BoolOptSettings.model_construct(flag=True)
    result = source._serialized_args(model)
    assert '--flag' in result['optional']
    assert '--no-flag' not in result['optional']


# --- Tests for store_true / store_false (line 1541 branch) ---


def test_serialized_args_store_true_does_not_append_value():
    """store_true action flag does not add a value, only the flag name."""
    class ToggleSettings(BaseSettings):
        model_config = SettingsConfigDict(cli_implicit_flags='toggle')
        verbose: bool = False  # store_true

    source = CliSettingsSource(ToggleSettings, cli_parse_args=[])
    model = ToggleSettings.model_construct(verbose=True)
    result = source._serialized_args(model)
    assert '--verbose' in result['optional']
    # Only the flag name, no 'True' value
    assert 'True' not in result['optional']


def test_serialized_args_store_false_does_not_append_value():
    """store_false action flag does not add a value, only the flag name."""
    class ToggleSettings(BaseSettings):
        model_config = SettingsConfigDict(cli_implicit_flags='toggle')
        debug: bool = True  # store_false → --no-debug

    source = CliSettingsSource(ToggleSettings, cli_parse_args=[])
    model = ToggleSettings.model_construct(debug=False)
    result = source._serialized_args(model)
    assert '--no-debug' in result['optional']
    assert 'False' not in result['optional']


# --- Tests for CliPositionalArg (lines 1527-1531) ---


def test_serialized_args_positional_str_arg():
    """CliPositionalArg[str] field ends up in positional args list."""
    class PosSettings(BaseSettings):
        filename: CliPositionalArg[str]

    source = CliSettingsSource(PosSettings, cli_parse_args=['myfile.txt'])
    model = PosSettings.model_construct(filename='myfile.txt')
    result = source._serialized_args(model)
    assert 'myfile.txt' in result['positional']
    assert result['optional'] == []


def test_serialized_args_positional_list_arg():
    """CliPositionalArg[list[str]] produces one positional entry per element."""
    class PosListSettings(BaseSettings):
        files: CliPositionalArg[list[str]]

    source = CliSettingsSource(PosListSettings, cli_parse_args=['a.txt', 'b.txt'])
    model = PosListSettings.model_construct(files=['a.txt', 'b.txt'])
    result = source._serialized_args(model)
    assert 'a.txt' in result['positional']
    assert 'b.txt' in result['positional']
    assert result['optional'] == []


def test_serialized_args_positional_dict_arg_json_encoded():
    """CliPositionalArg with dict value is JSON-encoded in positional args."""
    class PosDictSettings(BaseSettings):
        config: CliPositionalArg[dict]

    source = CliSettingsSource(PosDictSettings, cli_parse_args=['{"key": "value"}'])
    model = PosDictSettings.model_construct(config={'key': 'value'})
    result = source._serialized_args(model)
    assert len(result['positional']) == 1
    parsed = json.loads(result['positional'][0])
    assert parsed == {'key': 'value'}


# --- Tests for nested BaseModel path (lines 1502-1513) ---


def test_serialized_args_nested_base_model_non_default():
    """Nested BaseModel with non-default field values merges into optional args."""
    source = CliSettingsSource(SettingsWithNested, cli_parse_args=[])
    model = SettingsWithNested.model_construct(nested=NestedModel(x=10, y=2), top='top')
    result = source._serialized_args(model)
    assert '--nested.x' in result['optional']
    assert '10' in result['optional']


def test_serialized_args_nested_base_model_multiple_non_default_fields():
    """Both non-default fields from a nested model appear in the output."""
    source = CliSettingsSource(SettingsWithNested, cli_parse_args=[])
    model = SettingsWithNested.model_construct(nested=NestedModel(x=5, y=99), top='top')
    result = source._serialized_args(model)
    assert '--nested.x' in result['optional']
    assert '5' in result['optional']
    assert '--nested.y' in result['optional']
    assert '99' in result['optional']


def test_serialized_args_nested_pydantic_dataclass():
    """Nested pydantic dataclass with non-default values merges into optional args."""
    @pydantic_dataclass
    class SubData:
        x: int = 1
        y: int = 2

    class DataclassSettings(BaseSettings):
        data: SubData = Field(default_factory=SubData)

    source = CliSettingsSource(DataclassSettings, cli_parse_args=[])
    model = DataclassSettings.model_construct(data=SubData(x=10, y=2))
    result = source._serialized_args(model)
    assert '--data.x' in result['optional']
    assert '10' in result['optional']


# --- Tests for subcommand path (lines 1488-1501) ---


def test_serialized_args_subcommand_none_is_skipped():
    """CliSubCommand field with None value is skipped (continue at line 1489)."""
    class SubModel(BaseModel):
        x: int = 1

    class SubSettings(BaseSettings):
        cmd: CliSubCommand[SubModel]

    source = CliSettingsSource(SubSettings, cli_parse_args=['cmd'])
    model = SubSettings.model_construct(cmd=None)
    result = source._serialized_args(model)
    assert result['subcommand'] == []
    assert result['optional'] == []


def test_serialized_args_subcommand_selected_adds_alias():
    """Active CliSubCommand produces the subcommand alias in subcommand args."""
    class SubModel(BaseModel):
        x: int = 1

    class SubSettings(BaseSettings):
        cmd: CliSubCommand[SubModel]

    source = CliSettingsSource(SubSettings, cli_parse_args=['cmd'])
    model = SubSettings.model_construct(cmd=SubModel(x=1))
    result = source._serialized_args(model)
    assert 'cmd' in result['subcommand']


def test_serialized_args_subcommand_with_non_default_field():
    """Active subcommand with non-default sub-field serializes the sub-field."""
    class SubModel(BaseModel):
        x: int = 1

    class SubSettings(BaseSettings):
        cmd: CliSubCommand[SubModel]

    source = CliSettingsSource(SubSettings, cli_parse_args=['cmd'])
    model = SubSettings.model_construct(cmd=SubModel(x=5))
    result = source._serialized_args(model)
    assert 'cmd' in result['subcommand']
    # Sub-model fields with non-default values are serialized after the subcommand alias
    assert '-x' in result['subcommand'] or '--x' in result['subcommand']
    assert '5' in result['subcommand']


# --- Tests for alias_path_only field (lines 1521, 1525) ---


def test_serialized_args_alias_path_only_field():
    """Field with AliasPath-only alias is serialized through alias path logic."""
    class AliasSettings(BaseSettings):
        my_field: int = Field(default=0, validation_alias=AliasPath('data', 0))

    source = CliSettingsSource(AliasSettings, cli_parse_args=[])
    model = AliasSettings.model_construct(my_field=42)
    result = source._serialized_args(model)
    assert '--data' in result['optional']
    idx = result['optional'].index('--data')
    # Value should be a JSON-encoded list due to alias path indexing
    assert result['optional'][idx + 1] is not None


# --- Tests for positionals_first parameter ---


def test_serialized_args_positionals_first_false():
    """positionals_first=False puts optional args before positional args."""
    source = CliSettingsSource(SettingsWithNested, cli_parse_args=[])
    model = SettingsWithNested.model_construct(nested=NestedModel(x=5, y=2), top='top')
    result = source._serialized_args(model, positionals_first=False)
    assert '--nested.x' in result['optional']


def test_serialized_args_positionals_first_true():
    """positionals_first=True keeps same internal structure, flatten determines order."""
    source = CliSettingsSource(SettingsWithNested, cli_parse_args=[])
    model = SettingsWithNested.model_construct(nested=NestedModel(x=5, y=2), top='top')
    result = source._serialized_args(model, positionals_first=True)
    assert '--nested.x' in result['optional']


# --- Integration tests via CliApp.serialize ---


def test_cli_app_serialize_basic():
    """CliApp.serialize produces CLI args for non-default field values."""
    model = SimpleSettings(name='hello', value=0)
    result = CliApp.serialize(model)
    assert '--name' in result
    assert 'hello' in result


def test_cli_app_serialize_empty_when_all_defaults():
    """CliApp.serialize returns empty list when all fields are at defaults."""
    model = SimpleSettings(name='default', value=0)
    result = CliApp.serialize(model)
    assert result == []


def test_cli_app_serialize_list_json():
    """CliApp.serialize with list_style='json' encodes list as JSON array."""
    model = ListSettings(items=['a', 'b', 'c'])
    result = CliApp.serialize(model, list_style='json')
    assert '--items' in result
    idx = result.index('--items')
    parsed = json.loads(result[idx + 1])
    assert parsed == ['a', 'b', 'c']


def test_cli_app_serialize_list_argparse():
    """CliApp.serialize with list_style='argparse' repeats the flag per element."""
    model = ListSettings(items=['a', 'b', 'c'])
    result = CliApp.serialize(model, list_style='argparse')
    assert result.count('--items') == 3


def test_cli_app_serialize_list_lazy():
    """CliApp.serialize with list_style='lazy' produces comma-separated string."""
    model = ListSettings(items=['x', 'y'])
    result = CliApp.serialize(model, list_style='lazy')
    assert '--items' in result
    idx = result.index('--items')
    assert result[idx + 1] == 'x,y'


def test_cli_app_serialize_dict_json():
    """CliApp.serialize with dict_style='json' encodes dict as JSON object."""
    model = DictSettings(config={'host': 'localhost'})
    result = CliApp.serialize(model, dict_style='json')
    assert '--config' in result
    idx = result.index('--config')
    parsed = json.loads(result[idx + 1])
    assert parsed == {'host': 'localhost'}


def test_cli_app_serialize_dict_env():
    """CliApp.serialize with dict_style='env' produces key=value pairs."""
    model = DictSettings(config={'host': 'localhost', 'port': '5432'})
    result = CliApp.serialize(model, dict_style='env')
    assert '--config' in result
    assert 'host=localhost' in result


def test_cli_app_serialize_nested_model():
    """CliApp.serialize serializes nested BaseModel non-default fields."""
    model = SettingsWithNested(nested=NestedModel(x=10, y=2), top='top')
    result = CliApp.serialize(model)
    assert '--nested.x' in result
    assert '10' in result
