"""Tests for pydantic_settings/sources/base.py"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Annotated, Any, Optional
from unittest.mock import MagicMock

import pytest
from pydantic import AliasChoices, AliasPath, BaseModel, Field
from pydantic.fields import FieldInfo

from pydantic_settings import BaseSettings, CliSubCommand
from pydantic_settings.exceptions import SettingsError
from pydantic_settings.sources.base import (
    ConfigFileSourceMixin,
    DefaultSettingsSource,
    InitSettingsSource,
    PydanticBaseEnvSettingsSource,
    PydanticBaseSettingsSource,
    get_subcommand,
)
from pydantic_settings.sources.types import EnvNoneType, ForceDecode, NoDecode, _CliSubCommand


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class SimpleSettings(BaseSettings):
    model_config = {'env_prefix': '', 'extra': 'forbid'}
    my_var: str = 'default'


class SettingsWithNested(BaseSettings):
    model_config = {'env_prefix': '', 'extra': 'forbid'}
    name: str = 'test'
    count: int = 0


class SubModel(BaseModel):
    val: str = 'sub_default'


class NestedSettings(BaseSettings):
    model_config = {'env_prefix': '', 'extra': 'forbid', 'nested_model_default_partial_update': True}
    sub: SubModel = SubModel()


class ConcreteSettingsSource(PydanticBaseSettingsSource):
    """Concrete implementation for testing abstract base class."""

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        return {}


class ConcreteEnvSettingsSource(PydanticBaseEnvSettingsSource):
    """Concrete implementation for testing PydanticBaseEnvSettingsSource."""

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        return super().__call__()


# ---------------------------------------------------------------------------
# get_subcommand tests
# ---------------------------------------------------------------------------


class SubCommandModel(BaseModel):
    pass


class ModelWithSubcommand(BaseSettings):
    model_config = {'extra': 'forbid', 'cli_exit_on_error': False}
    sub: CliSubCommand[SubCommandModel] = None


class ModelWithSubcommandExitTrue(BaseSettings):
    model_config = {'extra': 'forbid', 'cli_exit_on_error': True}
    sub: CliSubCommand[SubCommandModel] = None


class ModelNoSubcommand(BaseSettings):
    model_config = {'extra': 'forbid'}
    name: str = 'hello'


def test_get_subcommand_returns_subcommand_when_set():
    child = SubCommandModel()
    model = ModelWithSubcommand.model_construct(sub=child)
    result = get_subcommand(model)
    assert result is child


def test_get_subcommand_raises_settings_error_when_required_and_not_set():
    model = ModelWithSubcommand.model_construct(sub=None)
    with pytest.raises(SettingsError, match='CLI subcommand is required'):
        get_subcommand(model, is_required=True, cli_exit_on_error=False)


def test_get_subcommand_raises_system_exit_when_cli_exit_on_error():
    model = ModelWithSubcommand.model_construct(sub=None)
    with pytest.raises(SystemExit, match='CLI subcommand is required'):
        get_subcommand(model, is_required=True, cli_exit_on_error=True)


def test_get_subcommand_returns_none_when_not_required():
    model = ModelWithSubcommand.model_construct(sub=None)
    result = get_subcommand(model, is_required=False)
    assert result is None


def test_get_subcommand_suppress_errors():
    model = ModelWithSubcommand.model_construct(sub=None)
    errors: list[SettingsError | SystemExit] = []
    result = get_subcommand(model, is_required=True, cli_exit_on_error=False, _suppress_errors=errors)
    assert result is None
    assert len(errors) == 1
    assert isinstance(errors[0], SettingsError)


def test_get_subcommand_suppress_errors_system_exit():
    model = ModelWithSubcommand.model_construct(sub=None)
    errors: list[SettingsError | SystemExit] = []
    result = get_subcommand(model, is_required=True, cli_exit_on_error=True, _suppress_errors=errors)
    assert result is None
    assert len(errors) == 1
    assert isinstance(errors[0], SystemExit)


def test_get_subcommand_uses_model_config_cli_exit_on_error_false():
    model = ModelWithSubcommand.model_construct(sub=None)
    # cli_exit_on_error=None => falls back to model_config which is False
    with pytest.raises(SettingsError, match='CLI subcommand is required'):
        get_subcommand(model, is_required=True, cli_exit_on_error=None)


def test_get_subcommand_uses_model_config_cli_exit_on_error_true():
    model = ModelWithSubcommandExitTrue.model_construct(sub=None)
    with pytest.raises(SystemExit, match='CLI subcommand is required'):
        get_subcommand(model, is_required=True, cli_exit_on_error=None)


def test_get_subcommand_no_subcommands_defined():
    model = ModelNoSubcommand.model_construct(name='hello')
    with pytest.raises(SettingsError, match='no subcommands were found'):
        get_subcommand(model, is_required=True, cli_exit_on_error=False)


def test_get_subcommand_no_subcommands_system_exit():
    model = ModelNoSubcommand.model_construct(name='hello')
    with pytest.raises(SystemExit, match='no subcommands were found'):
        get_subcommand(model, is_required=True, cli_exit_on_error=True)


# ---------------------------------------------------------------------------
# PydanticBaseSettingsSource tests
# ---------------------------------------------------------------------------


def test_base_settings_source_init():
    source = ConcreteSettingsSource(SimpleSettings)
    assert source.settings_cls is SimpleSettings
    assert source.config == SimpleSettings.model_config
    assert source.current_state == {}
    assert source.settings_sources_data == {}


def test_set_current_state():
    source = ConcreteSettingsSource(SimpleSettings)
    state = {'my_var': 'value'}
    source._set_current_state(state)
    assert source.current_state == {'my_var': 'value'}


def test_set_settings_sources_data():
    source = ConcreteSettingsSource(SimpleSettings)
    data = {'EnvSource': {'my_var': 'val'}}
    source._set_settings_sources_data(data)
    assert source.settings_sources_data == {'EnvSource': {'my_var': 'val'}}


def test_field_is_complex_simple():
    source = ConcreteSettingsSource(SimpleSettings)
    field = SimpleSettings.model_fields['my_var']
    assert source.field_is_complex(field) is False


def test_field_is_complex_with_model():
    source = ConcreteSettingsSource(NestedSettings)
    field = NestedSettings.model_fields['sub']
    assert source.field_is_complex(field) is True


def test_prepare_field_value_none():
    source = ConcreteSettingsSource(SimpleSettings)
    field = SimpleSettings.model_fields['my_var']
    result = source.prepare_field_value('my_var', field, None, False)
    assert result is None


def test_prepare_field_value_simple():
    source = ConcreteSettingsSource(SimpleSettings)
    field = SimpleSettings.model_fields['my_var']
    result = source.prepare_field_value('my_var', field, 'hello', False)
    assert result == 'hello'


def test_prepare_field_value_complex_json():
    source = ConcreteSettingsSource(NestedSettings)
    field = NestedSettings.model_fields['sub']
    json_val = '{"val": "from_json"}'
    result = source.prepare_field_value('sub', field, json_val, True)
    assert result == {'val': 'from_json'}


def test_decode_complex_value_json():
    source = ConcreteSettingsSource(SimpleSettings)
    field = SimpleSettings.model_fields['my_var']
    result = source.decode_complex_value('my_var', field, '"hello"')
    assert result == 'hello'


def test_decode_complex_value_no_decode():
    class SettingsWithNoDecode(BaseSettings):
        model_config = {'extra': 'forbid'}
        data: Annotated[str, NoDecode] = 'x'

    source = ConcreteSettingsSource(SettingsWithNoDecode)
    field = SettingsWithNoDecode.model_fields['data']
    result = source.decode_complex_value('data', field, '{"key": "val"}')
    assert result == '{"key": "val"}'


def test_decode_complex_value_enable_decoding_false():
    class SettingsDecodingDisabled(BaseSettings):
        model_config = {'extra': 'forbid', 'enable_decoding': False}
        data: str = 'default'

    source = ConcreteSettingsSource(SettingsDecodingDisabled)
    field = SettingsDecodingDisabled.model_fields['data']
    result = source.decode_complex_value('data', field, '{"key": "val"}')
    assert result == '{"key": "val"}'


def test_decode_complex_value_force_decode_overrides_disabled():
    class SettingsForceDecoding(BaseSettings):
        model_config = {'extra': 'forbid', 'enable_decoding': False}
        data: Annotated[str, ForceDecode] = 'default'

    source = ConcreteSettingsSource(SettingsForceDecoding)
    field = SettingsForceDecoding.model_fields['data']
    result = source.decode_complex_value('data', field, '"forced"')
    assert result == 'forced'


def test_concrete_source_call():
    source = ConcreteSettingsSource(SimpleSettings)
    assert source() == {}


# ---------------------------------------------------------------------------
# ConfigFileSourceMixin tests
# ---------------------------------------------------------------------------


class ConcreteConfigFileSource(ConfigFileSourceMixin):
    def _read_file(self, path: Path) -> dict[str, Any]:
        return json.loads(path.read_text())


def test_read_files_none():
    source = ConcreteConfigFileSource()
    assert source._read_files(None) == {}


def test_read_files_single_string(tmp_path):
    f = tmp_path / 'config.json'
    f.write_text('{"key": "value"}')
    source = ConcreteConfigFileSource()
    result = source._read_files(str(f))
    assert result == {'key': 'value'}


def test_read_files_single_path(tmp_path):
    f = tmp_path / 'config.json'
    f.write_text('{"key": "value2"}')
    source = ConcreteConfigFileSource()
    result = source._read_files(f)
    assert result == {'key': 'value2'}


def test_read_files_multiple(tmp_path):
    f1 = tmp_path / 'a.json'
    f1.write_text('{"a": 1}')
    f2 = tmp_path / 'b.json'
    f2.write_text('{"b": 2}')
    source = ConcreteConfigFileSource()
    result = source._read_files([f1, f2])
    assert result == {'a': 1, 'b': 2}


def test_read_files_skips_missing(tmp_path):
    f = tmp_path / 'exists.json'
    f.write_text('{"x": 1}')
    missing = tmp_path / 'nope.json'
    source = ConcreteConfigFileSource()
    result = source._read_files([f, missing])
    assert result == {'x': 1}


def test_read_files_deep_merge(tmp_path):
    f1 = tmp_path / 'a.json'
    f1.write_text('{"nested": {"a": 1, "b": 2}}')
    f2 = tmp_path / 'b.json'
    f2.write_text('{"nested": {"b": 3, "c": 4}}')
    source = ConcreteConfigFileSource()
    result = source._read_files([f1, f2], deep_merge=True)
    assert result == {'nested': {'a': 1, 'b': 3, 'c': 4}}


# ---------------------------------------------------------------------------
# DefaultSettingsSource tests
# ---------------------------------------------------------------------------


def test_default_settings_source_init():
    source = DefaultSettingsSource(SimpleSettings)
    assert source.defaults == {}
    assert source.nested_model_default_partial_update is False


def test_default_settings_source_with_partial_update():
    source = DefaultSettingsSource(NestedSettings, nested_model_default_partial_update=True)
    assert source.nested_model_default_partial_update is True
    assert 'sub' in source.defaults
    assert source.defaults['sub'] == {'val': 'sub_default'}


def test_default_settings_source_get_field_value():
    source = DefaultSettingsSource(SimpleSettings)
    field = SimpleSettings.model_fields['my_var']
    val, key, is_complex = source.get_field_value(field, 'my_var')
    assert val is None
    assert key == ''
    assert is_complex is False


def test_default_settings_source_call():
    source = DefaultSettingsSource(SimpleSettings)
    assert source() == {}


def test_default_settings_source_call_with_defaults():
    source = DefaultSettingsSource(NestedSettings, nested_model_default_partial_update=True)
    result = source()
    assert 'sub' in result


def test_default_settings_source_repr():
    source = DefaultSettingsSource(SimpleSettings)
    r = repr(source)
    assert 'DefaultSettingsSource' in r
    assert 'nested_model_default_partial_update=False' in r


def test_default_settings_source_repr_partial_update():
    source = DefaultSettingsSource(NestedSettings, nested_model_default_partial_update=True)
    r = repr(source)
    assert 'nested_model_default_partial_update=True' in r


def test_default_settings_source_uses_config_partial_update():
    source = DefaultSettingsSource(NestedSettings)
    # NestedSettings has nested_model_default_partial_update=True in model_config
    assert source.nested_model_default_partial_update is True


# ---------------------------------------------------------------------------
# InitSettingsSource tests
# ---------------------------------------------------------------------------


def test_init_settings_source_basic():
    source = InitSettingsSource(SimpleSettings, init_kwargs={'my_var': 'init_val'})
    assert source.init_kwargs == {'my_var': 'init_val'}


def test_init_settings_source_empty_kwargs():
    source = InitSettingsSource(SimpleSettings, init_kwargs={})
    assert source.init_kwargs == {}


def test_init_settings_source_get_field_value():
    source = InitSettingsSource(SimpleSettings, init_kwargs={})
    field = SimpleSettings.model_fields['my_var']
    val, key, is_complex = source.get_field_value(field, 'my_var')
    assert val is None
    assert key == ''
    assert is_complex is False


def test_init_settings_source_call():
    source = InitSettingsSource(SimpleSettings, init_kwargs={'my_var': 'test'})
    result = source()
    assert result == {'my_var': 'test'}


def test_init_settings_source_call_with_nested_model_partial():
    source = InitSettingsSource(
        NestedSettings,
        init_kwargs={'sub': SubModel(val='init')},
        nested_model_default_partial_update=True,
    )
    result = source()
    assert result == {'sub': {'val': 'init'}}


def test_init_settings_source_repr():
    source = InitSettingsSource(SimpleSettings, init_kwargs={'my_var': 'x'})
    r = repr(source)
    assert 'InitSettingsSource' in r
    assert 'my_var' in r


def test_init_settings_source_nested_model_default_from_config():
    source = InitSettingsSource(NestedSettings, init_kwargs={})
    assert source.nested_model_default_partial_update is True


def test_init_settings_source_nested_model_default_override():
    source = InitSettingsSource(NestedSettings, init_kwargs={}, nested_model_default_partial_update=False)
    assert source.nested_model_default_partial_update is False


class AliasSettings(BaseSettings):
    model_config = {'extra': 'forbid', 'populate_by_name': True}
    my_field: str = Field(default='x', validation_alias='my_alias')


def test_init_settings_source_with_alias():
    source = InitSettingsSource(AliasSettings, init_kwargs={'my_alias': 'aliased'})
    assert source.init_kwargs == {'my_alias': 'aliased'}


def test_init_settings_source_with_field_name_populate_by_name():
    source = InitSettingsSource(AliasSettings, init_kwargs={'my_field': 'by_name'})
    # When populate_by_name is True, field_name is also matchable,
    # and preferred_alias is 'my_alias'
    assert source.init_kwargs == {'my_alias': 'by_name'}


def test_init_settings_source_extras_pass_through():
    class ExtraSettings(BaseSettings):
        model_config = {'extra': 'allow'}
        name: str = 'default'

    source = InitSettingsSource(ExtraSettings, init_kwargs={'name': 'val', 'extra_key': 'extra_val'})
    assert source.init_kwargs['name'] == 'val'
    assert source.init_kwargs['extra_key'] == 'extra_val'


# ---------------------------------------------------------------------------
# PydanticBaseEnvSettingsSource tests
# ---------------------------------------------------------------------------


def test_env_settings_source_init_defaults():
    source = ConcreteEnvSettingsSource(SimpleSettings)
    assert source.case_sensitive is False
    assert source.env_prefix == ''
    assert source.env_prefix_target == 'variable'
    assert source.env_ignore_empty is False
    assert source.env_parse_none_str is None
    assert source.env_parse_enums is None


def test_env_settings_source_init_overrides():
    source = ConcreteEnvSettingsSource(
        SimpleSettings,
        case_sensitive=True,
        env_prefix='APP_',
        env_prefix_target='alias',
        env_ignore_empty=True,
        env_parse_none_str='null',
        env_parse_enums=True,
    )
    assert source.case_sensitive is True
    assert source.env_prefix == 'APP_'
    assert source.env_prefix_target == 'alias'
    assert source.env_ignore_empty is True
    assert source.env_parse_none_str == 'null'
    assert source.env_parse_enums is True


def test_apply_case_sensitive():
    source = ConcreteEnvSettingsSource(SimpleSettings, case_sensitive=False)
    assert source._apply_case_sensitive('MY_VAR') == 'my_var'

    source_cs = ConcreteEnvSettingsSource(SimpleSettings, case_sensitive=True)
    assert source_cs._apply_case_sensitive('MY_VAR') == 'MY_VAR'


def test_extract_field_info_simple():
    source = ConcreteEnvSettingsSource(SimpleSettings)
    field = SimpleSettings.model_fields['my_var']
    info = source._extract_field_info(field, 'my_var')
    assert len(info) >= 1
    field_key, env_name, is_complex = info[0]
    assert field_key == 'my_var'
    assert env_name == 'my_var'
    assert is_complex is False


def test_extract_field_info_with_string_alias():
    class AliasedEnvSettings(BaseSettings):
        model_config = {'extra': 'forbid'}
        my_field: str = Field(default='x', validation_alias='MY_ALIAS')

    source = ConcreteEnvSettingsSource(AliasedEnvSettings)
    field = AliasedEnvSettings.model_fields['my_field']
    info = source._extract_field_info(field, 'my_field')
    # Should have the alias entry
    assert any(fk == 'MY_ALIAS' for fk, _, _ in info)


def test_extract_field_info_with_alias_choices():
    class ChoicesSettings(BaseSettings):
        model_config = {'extra': 'forbid'}
        my_field: str = Field(default='x', validation_alias=AliasChoices('alias1', 'alias2'))

    source = ConcreteEnvSettingsSource(ChoicesSettings)
    field = ChoicesSettings.model_fields['my_field']
    info = source._extract_field_info(field, 'my_field')
    keys = [fk for fk, _, _ in info]
    assert 'alias1' in keys
    assert 'alias2' in keys


def test_extract_field_info_with_alias_path():
    class PathSettings(BaseSettings):
        model_config = {'extra': 'forbid'}
        my_field: str = Field(default='x', validation_alias=AliasPath('nested', 'value'))

    source = ConcreteEnvSettingsSource(PathSettings)
    field = PathSettings.model_fields['my_field']
    info = source._extract_field_info(field, 'my_field')
    # AliasPath -> complex=True for multi-element paths
    assert any(is_complex for _, _, is_complex in info)


def test_extract_field_info_with_env_prefix():
    source = ConcreteEnvSettingsSource(SimpleSettings, env_prefix='APP_')
    field = SimpleSettings.model_fields['my_var']
    info = source._extract_field_info(field, 'my_var')
    env_names = [en for _, en, _ in info]
    assert any('app_my_var' in en for en in env_names)


def test_replace_env_none_type_values():
    source = ConcreteEnvSettingsSource(SimpleSettings)
    values = {
        'key1': EnvNoneType('null'),
        'key2': 'normal',
        'key3': {'nested_key': EnvNoneType('null'), 'other': 'ok'},
    }
    result = source._replace_env_none_type_values(values)
    assert result['key1'] is None
    assert result['key2'] == 'normal'
    assert result['key3']['nested_key'] is None
    assert result['key3']['other'] == 'ok'


def test_replace_field_names_case_insensitively():
    class Inner(BaseModel):
        Val1: str = 'default'

    class OuterSettings(BaseSettings):
        model_config = {'extra': 'forbid'}
        nested: Inner = Inner()

    source = ConcreteEnvSettingsSource(OuterSettings)
    field = OuterSettings.model_fields['nested']
    result = source._replace_field_names_case_insensitively(field, {'val1': 'test_value'})
    assert 'Val1' in result
    assert result['Val1'] == 'test_value'


def test_replace_field_names_case_insensitively_no_annotation():
    source = ConcreteEnvSettingsSource(SimpleSettings)
    field = SimpleSettings.model_fields['my_var']
    result = source._replace_field_names_case_insensitively(field, {'key': 'val'})
    assert result == {'key': 'val'}


def test_replace_field_names_case_insensitively_no_match():
    class Inner(BaseModel):
        Val1: str = 'default'

    class OuterSettings(BaseSettings):
        model_config = {'extra': 'forbid'}
        nested: Inner = Inner()

    source = ConcreteEnvSettingsSource(OuterSettings)
    field = OuterSettings.model_fields['nested']
    result = source._replace_field_names_case_insensitively(field, {'unknown_key': 'val'})
    assert result == {'unknown_key': 'val'}


def test_replace_field_names_case_insensitively_nested_model():
    class DeepInner(BaseModel):
        DeepVal: str = 'deep'

    class Inner(BaseModel):
        Val1: str = 'default'
        Sub: DeepInner = DeepInner()

    class OuterSettings(BaseSettings):
        model_config = {'extra': 'forbid'}
        nested: Inner = Inner()

    source = ConcreteEnvSettingsSource(OuterSettings)
    field = OuterSettings.model_fields['nested']
    result = source._replace_field_names_case_insensitively(
        field, {'val1': 'v1', 'sub': {'deepval': 'dv'}}
    )
    assert 'Val1' in result
    assert 'Sub' in result
    assert result['Sub']['DeepVal'] == 'dv'


def test_replace_field_names_case_insensitively_optional():
    class Inner(BaseModel):
        Val1: str = 'default'

    class OuterSettings(BaseSettings):
        model_config = {'extra': 'forbid'}
        nested: Optional[Inner] = None

    source = ConcreteEnvSettingsSource(OuterSettings)
    field = OuterSettings.model_fields['nested']
    result = source._replace_field_names_case_insensitively(field, {'val1': 'test'})
    assert 'Val1' in result


def test_env_settings_source_call_empty():
    source = ConcreteEnvSettingsSource(SimpleSettings)
    result = source()
    assert result == {}


def test_env_settings_source_call_with_env_parse_none_str():
    class NoneStrSettings(BaseSettings):
        model_config = {'extra': 'forbid', 'env_parse_none_str': 'null'}
        my_var: Optional[str] = None

    source = ConcreteEnvSettingsSource(NoneStrSettings, env_parse_none_str='null')
    result = source()
    assert isinstance(result, dict)


def test_get_resolved_field_value():
    source = ConcreteEnvSettingsSource(SimpleSettings)
    field = SimpleSettings.model_fields['my_var']
    val, key, is_complex = source._get_resolved_field_value(field, 'my_var')
    assert val is None
    assert key == 'my_var'
    assert is_complex is False


# ---------------------------------------------------------------------------
# Integration: DefaultSettingsSource with dataclass defaults
# ---------------------------------------------------------------------------


def test_default_settings_source_with_dataclass_default():
    from dataclasses import dataclass

    @dataclass
    class DCModel:
        x: int = 10
        y: str = 'hello'

    class DCSettings(BaseSettings):
        model_config = {'extra': 'forbid', 'nested_model_default_partial_update': True}
        dc: DCModel = DCModel()

    source = DefaultSettingsSource(DCSettings, nested_model_default_partial_update=True)
    assert 'dc' in source.defaults
    assert source.defaults['dc'] == {'x': 10, 'y': 'hello'}


# ---------------------------------------------------------------------------
# ConfigFileSourceMixin: edge cases
# ---------------------------------------------------------------------------


def test_read_files_with_string_list(tmp_path):
    f = tmp_path / 'config.json'
    f.write_text('{"k": "v"}')
    source = ConcreteConfigFileSource()
    result = source._read_files([str(f)])
    assert result == {'k': 'v'}


def test_read_files_expanduser(tmp_path):
    f = tmp_path / 'config.json'
    f.write_text('{"expand": true}')
    source = ConcreteConfigFileSource()
    result = source._read_files(f)
    assert result == {'expand': True}
