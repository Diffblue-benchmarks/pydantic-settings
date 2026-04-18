"""Tests for pydantic_settings.sources.base module."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from unittest.mock import patch

import pytest
from pydantic import AliasChoices, AliasPath, BaseModel, Field

from pydantic_settings import BaseSettings, SettingsConfigDict, SettingsError
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
# Helper models
# ---------------------------------------------------------------------------

class SimpleSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix='', extra='ignore')
    name: str = 'default'
    count: int = 0


class NestedSubModel(BaseModel):
    val: str = 'inner'


class NestedSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix='', extra='ignore')
    name: str = 'default'
    nested: NestedSubModel = NestedSubModel()


class DefaultPartialSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix='',
        extra='ignore',
        nested_model_default_partial_update=True,
    )
    nested: NestedSubModel = NestedSubModel()


@dataclass
class DCDefault:
    x: int = 1
    y: int = 2


class DataclassDefaultSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix='',
        extra='ignore',
        nested_model_default_partial_update=True,
    )
    dc: DCDefault = DCDefault()


class AliasSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix='',
        extra='ignore',
        populate_by_name=True,
    )
    my_field: str = Field(default='test', alias='myField')


class SubCommandModel(BaseSettings):
    model_config = SettingsConfigDict(env_prefix='', extra='ignore')
    value: str = 'sub'


# ---------------------------------------------------------------------------
# Concrete subclass of PydanticBaseSettingsSource for testing
# ---------------------------------------------------------------------------

class ConcreteSettingsSource(PydanticBaseSettingsSource):
    """Minimal concrete implementation for testing the ABC."""

    def __init__(self, settings_cls: type[BaseSettings], values: dict[str, Any] | None = None):
        super().__init__(settings_cls)
        self._values = values or {}

    def get_field_value(self, field: Any, field_name: str) -> tuple[Any, str, bool]:
        val = self._values.get(field_name)
        return val, field_name, False

    def __call__(self) -> dict[str, Any]:
        return self._values


# ---------------------------------------------------------------------------
# Concrete subclass of PydanticBaseEnvSettingsSource for testing
# ---------------------------------------------------------------------------

class ConcreteEnvSource(PydanticBaseEnvSettingsSource):
    """Minimal concrete implementation for testing the env base class."""

    def __init__(
        self,
        settings_cls: type[BaseSettings],
        env_values: dict[str, Any] | None = None,
        **kwargs: Any,
    ):
        super().__init__(settings_cls, **kwargs)
        self._env_values = env_values or {}

    def get_field_value(self, field: Any, field_name: str) -> tuple[Any, str, bool]:
        val = self._env_values.get(field_name)
        return val, field_name, False

    def __call__(self) -> dict[str, Any]:
        return super().__call__()


# ---------------------------------------------------------------------------
# Tests for get_subcommand
# ---------------------------------------------------------------------------

class TestGetSubcommand:
    def test_no_subcommand_fields_required_raises_settings_error(self):
        """When model has no _CliSubCommand fields and is_required, raise error."""
        settings = SimpleSettings()
        with pytest.raises(SettingsError, match='CLI subcommand is required but no subcommands were found'):
            get_subcommand(settings, is_required=True, cli_exit_on_error=False)

    def test_no_subcommand_fields_required_exit_on_error(self):
        """When model has no _CliSubCommand fields and cli_exit_on_error=True, raise SystemExit."""
        settings = SimpleSettings()
        with pytest.raises(SystemExit, match='CLI subcommand is required but no subcommands were found'):
            get_subcommand(settings, is_required=True, cli_exit_on_error=True)

    def test_not_required_returns_none(self):
        """When is_required=False and no subcommand, return None."""
        settings = SimpleSettings()
        result = get_subcommand(settings, is_required=False)
        assert result is None

    def test_suppress_errors_collects_error(self):
        """When _suppress_errors is provided, errors are appended instead of raised."""
        settings = SimpleSettings()
        errors: list[SettingsError | SystemExit] = []
        result = get_subcommand(settings, is_required=True, cli_exit_on_error=False, _suppress_errors=errors)
        assert result is None
        assert len(errors) == 1
        assert isinstance(errors[0], SettingsError)

    def test_suppress_errors_collects_system_exit(self):
        """When _suppress_errors is provided with cli_exit_on_error=True."""
        settings = SimpleSettings()
        errors: list[SettingsError | SystemExit] = []
        result = get_subcommand(settings, is_required=True, cli_exit_on_error=True, _suppress_errors=errors)
        assert result is None
        assert len(errors) == 1
        assert isinstance(errors[0], SystemExit)

    def test_cli_exit_on_error_defaults_from_config(self):
        """cli_exit_on_error defaults from model_config when not explicitly set."""

        class MySettings(BaseSettings):
            model_config = SettingsConfigDict(cli_exit_on_error=False, extra='ignore')
            name: str = 'test'

        settings = MySettings()
        # cli_exit_on_error=None should pick up False from config
        with pytest.raises(SettingsError):
            get_subcommand(settings, is_required=True, cli_exit_on_error=None)

    def test_cli_exit_on_error_defaults_true_when_not_in_config(self):
        """cli_exit_on_error defaults to True when not set in config and not passed."""
        settings = SimpleSettings()
        with pytest.raises(SystemExit):
            get_subcommand(settings, is_required=True, cli_exit_on_error=None)


# ---------------------------------------------------------------------------
# Tests for PydanticBaseSettingsSource
# ---------------------------------------------------------------------------

class TestPydanticBaseSettingsSource:
    def test_init(self):
        source = ConcreteSettingsSource(SimpleSettings)
        assert source.settings_cls is SimpleSettings
        assert source.config == SimpleSettings.model_config

    def test_current_state_default(self):
        source = ConcreteSettingsSource(SimpleSettings)
        assert source.current_state == {}

    def test_set_current_state(self):
        source = ConcreteSettingsSource(SimpleSettings)
        source._set_current_state({'name': 'hello'})
        assert source.current_state == {'name': 'hello'}

    def test_settings_sources_data_default(self):
        source = ConcreteSettingsSource(SimpleSettings)
        assert source.settings_sources_data == {}

    def test_set_settings_sources_data(self):
        source = ConcreteSettingsSource(SimpleSettings)
        data = {'EnvSettingsSource': {'name': 'env_val'}}
        source._set_settings_sources_data(data)
        assert source.settings_sources_data == data

    def test_field_is_complex_simple(self):
        source = ConcreteSettingsSource(SimpleSettings)
        field = SimpleSettings.model_fields['name']
        assert source.field_is_complex(field) is False

    def test_field_is_complex_for_model(self):
        source = ConcreteSettingsSource(NestedSettings)
        field = NestedSettings.model_fields['nested']
        assert source.field_is_complex(field) is True

    def test_prepare_field_value_none(self):
        source = ConcreteSettingsSource(SimpleSettings)
        field = SimpleSettings.model_fields['name']
        result = source.prepare_field_value('name', field, None, False)
        assert result is None

    def test_prepare_field_value_simple(self):
        source = ConcreteSettingsSource(SimpleSettings)
        field = SimpleSettings.model_fields['name']
        result = source.prepare_field_value('name', field, 'hello', False)
        assert result == 'hello'

    def test_prepare_field_value_complex_json(self):
        source = ConcreteSettingsSource(NestedSettings)
        field = NestedSettings.model_fields['nested']
        json_val = json.dumps({'val': 'parsed'})
        result = source.prepare_field_value('nested', field, json_val, False)
        assert result == {'val': 'parsed'}

    def test_prepare_field_value_with_value_is_complex_flag(self):
        source = ConcreteSettingsSource(SimpleSettings)
        field = SimpleSettings.model_fields['name']
        json_val = json.dumps({'key': 'val'})
        result = source.prepare_field_value('name', field, json_val, True)
        assert result == {'key': 'val'}

    def test_decode_complex_value_json(self):
        source = ConcreteSettingsSource(SimpleSettings)
        field = SimpleSettings.model_fields['name']
        result = source.decode_complex_value('name', field, '{"a": 1}')
        assert result == {'a': 1}

    def test_decode_complex_value_no_decode_metadata(self):
        """Field with NoDecode metadata should return value as-is."""
        from typing import Annotated

        class NoDecSettings(BaseSettings):
            model_config = SettingsConfigDict(env_prefix='', extra='ignore')
            data: Annotated[str, NoDecode] = 'x'

        source = ConcreteSettingsSource(NoDecSettings)
        field = NoDecSettings.model_fields['data']
        result = source.decode_complex_value('data', field, '{"a": 1}')
        assert result == '{"a": 1}'

    def test_decode_complex_value_enable_decoding_false(self):
        """When enable_decoding is False and no ForceDecode, return value as-is."""

        class NoDecodeSettings(BaseSettings):
            model_config = SettingsConfigDict(env_prefix='', extra='ignore', enable_decoding=False)
            name: str = 'test'

        source = ConcreteSettingsSource(NoDecodeSettings)
        field = NoDecodeSettings.model_fields['name']
        result = source.decode_complex_value('name', field, '{"a": 1}')
        assert result == '{"a": 1}'

    def test_call_returns_values(self):
        vals = {'name': 'test_val'}
        source = ConcreteSettingsSource(SimpleSettings, values=vals)
        assert source() == vals


# ---------------------------------------------------------------------------
# Tests for DefaultSettingsSource
# ---------------------------------------------------------------------------

class TestDefaultSettingsSource:
    def test_init_basic(self):
        source = DefaultSettingsSource(SimpleSettings)
        assert source.nested_model_default_partial_update is False
        assert source.defaults == {}

    def test_get_field_value(self):
        source = DefaultSettingsSource(SimpleSettings)
        field = SimpleSettings.model_fields['name']
        val, key, is_complex = source.get_field_value(field, 'name')
        assert val is None
        assert key == ''
        assert is_complex is False

    def test_call_empty(self):
        source = DefaultSettingsSource(SimpleSettings)
        assert source() == {}

    def test_repr(self):
        source = DefaultSettingsSource(SimpleSettings)
        r = repr(source)
        assert 'DefaultSettingsSource' in r
        assert 'nested_model_default_partial_update=False' in r

    def test_nested_model_default_partial_update_true(self):
        source = DefaultSettingsSource(DefaultPartialSettings)
        assert source.nested_model_default_partial_update is True
        assert 'nested' in source.defaults
        assert source.defaults['nested'] == {'val': 'inner'}

    def test_nested_model_default_partial_update_explicit(self):
        source = DefaultSettingsSource(SimpleSettings, nested_model_default_partial_update=True)
        assert source.nested_model_default_partial_update is True

    def test_dataclass_default_partial_update(self):
        source = DefaultSettingsSource(DataclassDefaultSettings)
        assert source.nested_model_default_partial_update is True
        assert 'dc' in source.defaults
        assert source.defaults['dc'] == {'x': 1, 'y': 2}


# ---------------------------------------------------------------------------
# Tests for InitSettingsSource
# ---------------------------------------------------------------------------

class TestInitSettingsSource:
    def test_init_basic(self):
        source = InitSettingsSource(SimpleSettings, init_kwargs={'name': 'init_val'})
        assert source.init_kwargs == {'name': 'init_val'}
        assert source.nested_model_default_partial_update is False

    def test_call_returns_init_kwargs(self):
        source = InitSettingsSource(SimpleSettings, init_kwargs={'name': 'test'})
        result = source()
        assert result == {'name': 'test'}

    def test_call_with_partial_update(self):
        source = InitSettingsSource(
            DefaultPartialSettings,
            init_kwargs={'nested': NestedSubModel(val='custom')},
            nested_model_default_partial_update=True,
        )
        result = source()
        assert isinstance(result, dict)

    def test_get_field_value(self):
        source = InitSettingsSource(SimpleSettings, init_kwargs={})
        field = SimpleSettings.model_fields['name']
        val, key, is_complex = source.get_field_value(field, 'name')
        assert val is None
        assert key == ''
        assert is_complex is False

    def test_repr(self):
        source = InitSettingsSource(SimpleSettings, init_kwargs={'name': 'r'})
        r = repr(source)
        assert 'InitSettingsSource' in r
        assert 'init_kwargs' in r

    def test_alias_field_normalization(self):
        source = InitSettingsSource(AliasSettings, init_kwargs={'myField': 'alias_val'})
        assert source.init_kwargs == {'myField': 'alias_val'}

    def test_populate_by_name_field(self):
        source = InitSettingsSource(AliasSettings, init_kwargs={'my_field': 'by_name'})
        # With populate_by_name=True, the field name should be accepted and normalized
        assert 'myField' in source.init_kwargs
        assert source.init_kwargs['myField'] == 'by_name'

    def test_extra_kwargs_preserved(self):
        class ExtraSettings(BaseSettings):
            model_config = SettingsConfigDict(env_prefix='', extra='allow')
            name: str = 'test'

        source = InitSettingsSource(ExtraSettings, init_kwargs={'name': 'val', 'extra_key': 'extra_val'})
        assert 'extra_key' in source.init_kwargs
        assert source.init_kwargs['extra_key'] == 'extra_val'


# ---------------------------------------------------------------------------
# Tests for PydanticBaseEnvSettingsSource
# ---------------------------------------------------------------------------

class TestPydanticBaseEnvSettingsSource:
    def test_init_defaults(self):
        source = ConcreteEnvSource(SimpleSettings)
        assert source.case_sensitive is False
        assert source.env_prefix == ''
        assert source.env_prefix_target == 'variable'
        assert source.env_ignore_empty is False
        assert source.env_parse_none_str is None
        assert source.env_parse_enums is None

    def test_init_custom_values(self):
        source = ConcreteEnvSource(
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

    def test_apply_case_sensitive_lower(self):
        source = ConcreteEnvSource(SimpleSettings, case_sensitive=False)
        assert source._apply_case_sensitive('MY_VAR') == 'my_var'

    def test_apply_case_sensitive_preserve(self):
        source = ConcreteEnvSource(SimpleSettings, case_sensitive=True)
        assert source._apply_case_sensitive('MY_VAR') == 'MY_VAR'

    def test_extract_field_info_simple(self):
        source = ConcreteEnvSource(SimpleSettings)
        field = SimpleSettings.model_fields['name']
        info = source._extract_field_info(field, 'name')
        assert len(info) >= 1
        field_key, env_name, is_complex = info[0]
        assert field_key == 'name'
        assert is_complex is False

    def test_extract_field_info_with_prefix(self):
        source = ConcreteEnvSource(SimpleSettings, env_prefix='APP_')
        field = SimpleSettings.model_fields['name']
        info = source._extract_field_info(field, 'name')
        assert any('app_name' == env_name for _, env_name, _ in info)

    def test_extract_field_info_validation_alias_string(self):
        class AliasEnvSettings(BaseSettings):
            model_config = SettingsConfigDict(env_prefix='', extra='ignore')
            my_field: str = Field(default='test', validation_alias='my_alias')

        source = ConcreteEnvSource(AliasEnvSettings)
        field = AliasEnvSettings.model_fields['my_field']
        info = source._extract_field_info(field, 'my_field')
        env_names = [env_name for _, env_name, _ in info]
        assert 'my_alias' in env_names

    def test_extract_field_info_alias_choices(self):
        class ChoicesSettings(BaseSettings):
            model_config = SettingsConfigDict(env_prefix='', extra='ignore')
            my_field: str = Field(default='test', validation_alias=AliasChoices('alias1', 'alias2'))

        source = ConcreteEnvSource(ChoicesSettings)
        field = ChoicesSettings.model_fields['my_field']
        info = source._extract_field_info(field, 'my_field')
        env_names = [env_name for _, env_name, _ in info]
        assert 'alias1' in env_names
        assert 'alias2' in env_names

    def test_extract_field_info_alias_path(self):
        class PathSettings(BaseSettings):
            model_config = SettingsConfigDict(env_prefix='', extra='ignore')
            my_field: str = Field(default='test', validation_alias=AliasPath('root', 'nested'))

        source = ConcreteEnvSource(PathSettings)
        field = PathSettings.model_fields['my_field']
        info = source._extract_field_info(field, 'my_field')
        # AliasPath should produce a complex field info entry
        assert any(is_complex for _, _, is_complex in info)

    def test_extract_field_info_with_alias_prefix_target(self):
        class APSettings(BaseSettings):
            model_config = SettingsConfigDict(env_prefix='APP_', extra='ignore')
            my_field: str = Field(default='test', validation_alias='my_alias')

        source = ConcreteEnvSource(APSettings, env_prefix='APP_', env_prefix_target='alias')
        field = APSettings.model_fields['my_field']
        info = source._extract_field_info(field, 'my_field')
        env_names = [env_name for _, env_name, _ in info]
        # With env_prefix_target='alias', prefix applies to alias
        assert any('app_my_alias' == n for n in env_names)

    def test_replace_env_none_type_values(self):
        source = ConcreteEnvSource(SimpleSettings)
        values = {'a': EnvNoneType('null'), 'b': 'keep', 'c': {'d': EnvNoneType('null'), 'e': 'nested'}}
        result = source._replace_env_none_type_values(values)
        assert result['a'] is None
        assert result['b'] == 'keep'
        assert result['c']['d'] is None
        assert result['c']['e'] == 'nested'

    def test_replace_field_names_case_insensitively(self):
        class InnerModel(BaseModel):
            MyField: str = 'default'

        class CaseSettings(BaseSettings):
            model_config = SettingsConfigDict(env_prefix='', extra='ignore')
            nested: InnerModel = InnerModel()

        source = ConcreteEnvSource(CaseSettings, case_sensitive=False)
        field = CaseSettings.model_fields['nested']
        result = source._replace_field_names_case_insensitively(field, {'myfield': 'val'})
        assert 'MyField' in result
        assert result['MyField'] == 'val'

    def test_replace_field_names_non_model_annotation(self):
        """When field annotation is not a BaseModel, values pass through unchanged."""
        source = ConcreteEnvSource(SimpleSettings, case_sensitive=False)
        field = SimpleSettings.model_fields['name']
        result = source._replace_field_names_case_insensitively(field, {'x': 'val'})
        assert result == {'x': 'val'}

    def test_replace_field_names_no_matching_alias(self):
        """When no alias matches in model fields, key passes through."""
        class InnerModel(BaseModel):
            MyField: str = 'default'

        class CaseSettings(BaseSettings):
            model_config = SettingsConfigDict(env_prefix='', extra='ignore')
            nested: InnerModel = InnerModel()

        source = ConcreteEnvSource(CaseSettings, case_sensitive=False)
        field = CaseSettings.model_fields['nested']
        result = source._replace_field_names_case_insensitively(field, {'nonexistent': 'val'})
        assert result == {'nonexistent': 'val'}

    def test_replace_field_names_with_optional_annotation(self):
        """Test case insensitive replace with Optional[Model] annotation."""
        class InnerModel(BaseModel):
            FieldA: str = 'default'

        class OptSettings(BaseSettings):
            model_config = SettingsConfigDict(env_prefix='', extra='ignore')
            nested: Optional[InnerModel] = None

        source = ConcreteEnvSource(OptSettings, case_sensitive=False)
        field = OptSettings.model_fields['nested']
        result = source._replace_field_names_case_insensitively(field, {'fielda': 'val'})
        assert 'FieldA' in result

    def test_replace_field_names_recursive(self):
        """Test recursive replacement for nested BaseModel fields."""
        class Inner(BaseModel):
            Val: str = 'default'

        class Outer(BaseModel):
            Sub: Inner = Inner()

        class RecSettings(BaseSettings):
            model_config = SettingsConfigDict(env_prefix='', extra='ignore')
            nested: Outer = Outer()

        source = ConcreteEnvSource(RecSettings, case_sensitive=False)
        field = RecSettings.model_fields['nested']
        result = source._replace_field_names_case_insensitively(field, {'sub': {'val': 'deep'}})
        assert 'Sub' in result
        assert 'Val' in result['Sub']

    def test_call_basic(self):
        source = ConcreteEnvSource(SimpleSettings, env_values={'name': 'from_env'})
        result = source()
        assert result['name'] == 'from_env'

    def test_call_with_none_value(self):
        source = ConcreteEnvSource(SimpleSettings, env_values={'name': None})
        result = source()
        # None values are not included
        assert 'name' not in result

    def test_call_with_env_parse_none_str(self):
        source = ConcreteEnvSource(
            SimpleSettings,
            env_values={'name': EnvNoneType('null')},
            env_parse_none_str='null',
        )
        result = source()
        # EnvNoneType should be replaced with None
        assert result.get('name') is None

    def test_call_with_dict_value_case_insensitive(self):
        class InnerModel(BaseModel):
            FieldA: str = 'default'

        class DictSettings(BaseSettings):
            model_config = SettingsConfigDict(env_prefix='', extra='ignore')
            nested: InnerModel = InnerModel()

        # Pass a JSON string since nested model field is complex and will be decoded
        env_vals = {'nested': json.dumps({'fielda': 'val'})}
        source = ConcreteEnvSource(DictSettings, env_values=env_vals, case_sensitive=False)
        result = source()
        assert 'nested' in result
        assert 'FieldA' in result['nested']

    def test_get_resolved_field_value(self):
        source = ConcreteEnvSource(SimpleSettings, env_values={'name': 'val'})
        field = SimpleSettings.model_fields['name']
        value, key, is_complex = source._get_resolved_field_value(field, 'name')
        assert value == 'val'


# ---------------------------------------------------------------------------
# Tests for ConfigFileSourceMixin
# ---------------------------------------------------------------------------

class ConcreteConfigFileSource(ConfigFileSourceMixin):
    """Concrete implementation for testing."""

    def __init__(self, file_data: dict[str, Any] | None = None):
        self._file_data = file_data or {}

    def _read_file(self, path: Path) -> dict[str, Any]:
        return self._file_data


class TestConfigFileSourceMixin:
    def test_read_files_none(self):
        source = ConcreteConfigFileSource()
        assert source._read_files(None) == {}

    def test_read_files_single_string(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{}')
            tmp_path = f.name
        try:
            source = ConcreteConfigFileSource(file_data={'key': 'val'})
            result = source._read_files(tmp_path)
            assert result == {'key': 'val'}
        finally:
            os.unlink(tmp_path)

    def test_read_files_single_path(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{}')
            tmp_path = Path(f.name)
        try:
            source = ConcreteConfigFileSource(file_data={'k': 'v'})
            result = source._read_files(tmp_path)
            assert result == {'k': 'v'}
        finally:
            os.unlink(str(tmp_path))

    def test_read_files_nonexistent_skipped(self):
        source = ConcreteConfigFileSource(file_data={'k': 'v'})
        result = source._read_files('/nonexistent/file.json')
        assert result == {}

    def test_read_files_multiple(self):
        files = []
        for i in range(2):
            f = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
            f.write('{}')
            f.close()
            files.append(f.name)
        try:
            call_count = 0
            data_list = [{'a': '1'}, {'b': '2'}]

            class MultiSource(ConfigFileSourceMixin):
                def _read_file(self, path: Path) -> dict[str, Any]:
                    nonlocal call_count
                    result = data_list[call_count]
                    call_count += 1
                    return result

            source = MultiSource()
            result = source._read_files(files)
            assert result == {'a': '1', 'b': '2'}
        finally:
            for f_path in files:
                os.unlink(f_path)

    def test_read_files_deep_merge(self):
        files = []
        for i in range(2):
            f = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
            f.write('{}')
            f.close()
            files.append(f.name)
        try:
            call_count = 0
            data_list = [{'a': {'x': 1}}, {'a': {'y': 2}}]

            class MergeSource(ConfigFileSourceMixin):
                def _read_file(self, path: Path) -> dict[str, Any]:
                    nonlocal call_count
                    result = data_list[call_count]
                    call_count += 1
                    return result

            source = MergeSource()
            result = source._read_files(files, deep_merge=True)
            assert result == {'a': {'x': 1, 'y': 2}}
        finally:
            for f_path in files:
                os.unlink(f_path)

    def test_read_files_expanduser(self):
        """Verifies that Path.expanduser() is called on file paths."""
        source = ConcreteConfigFileSource(file_data={'k': 'v'})
        # A path with ~ that doesn't exist should be skipped (after expanduser)
        result = source._read_files('~/nonexistent_test_file_12345.json')
        assert result == {}


# ---------------------------------------------------------------------------
# Integration-style tests using BaseSettings directly
# ---------------------------------------------------------------------------

class TestIntegration:
    def test_simple_settings_from_env(self):
        with patch.dict(os.environ, {'NAME': 'env_value'}):
            settings = SimpleSettings()
            assert settings.name == 'env_value'

    def test_init_settings_priority(self):
        settings = SimpleSettings(name='init_val')
        assert settings.name == 'init_val'

    def test_default_settings_source_call(self):
        source = DefaultSettingsSource(SimpleSettings)
        result = source()
        assert result == {}

    def test_init_settings_source_empty(self):
        source = InitSettingsSource(SimpleSettings, init_kwargs={})
        result = source()
        assert result == {}


# ---------------------------------------------------------------------------
# Tests for PydanticBaseEnvSettingsSource.__call__ error paths and
# env_parse_none_str dict handling
# ---------------------------------------------------------------------------

class TestBaseEnvSettingsSourceCallErrors:
    def test_call_raises_settings_error_when_get_resolved_field_value_fails(self):
        """Lines 545-546: exception in _get_resolved_field_value wraps in SettingsError."""

        class FailingGetFieldSource(PydanticBaseEnvSettingsSource):
            def get_field_value(self, field, field_name):
                raise RuntimeError('boom')

        source = FailingGetFieldSource(SimpleSettings)
        with pytest.raises(SettingsError, match='error getting value for field "name"'):
            source()

    def test_call_raises_settings_error_preserves_cause(self):
        """The original exception is chained via __cause__."""

        class FailingGetFieldSource(PydanticBaseEnvSettingsSource):
            def get_field_value(self, field, field_name):
                raise RuntimeError('original cause')

        source = FailingGetFieldSource(SimpleSettings)
        with pytest.raises(SettingsError) as exc_info:
            source()
        assert isinstance(exc_info.value.__cause__, RuntimeError)
        assert str(exc_info.value.__cause__) == 'original cause'

    def test_call_raises_settings_error_when_prepare_field_value_raises_value_error(self):
        """Lines 552-553: ValueError in prepare_field_value wraps in SettingsError."""

        class FailingPrepareSource(PydanticBaseEnvSettingsSource):
            def get_field_value(self, field, field_name):
                return 'some_val', field_name, False

            def prepare_field_value(self, field_name, field, value, value_is_complex):
                if value is not None:
                    raise ValueError('bad value')
                return value

        source = FailingPrepareSource(SimpleSettings)
        with pytest.raises(SettingsError, match='error parsing value for field "name"'):
            source()

    def test_call_raises_settings_error_from_prepare_preserves_cause(self):
        """The original ValueError is chained via __cause__."""

        class FailingPrepareSource(PydanticBaseEnvSettingsSource):
            def get_field_value(self, field, field_name):
                return 'some_val', field_name, False

            def prepare_field_value(self, field_name, field, value, value_is_complex):
                if value is not None:
                    raise ValueError('parse failure')
                return value

        source = FailingPrepareSource(SimpleSettings)
        with pytest.raises(SettingsError) as exc_info:
            source()
        assert isinstance(exc_info.value.__cause__, ValueError)

    def test_call_replaces_env_none_type_in_dict_values(self):
        """Line 560: dict field_value with env_parse_none_str triggers _replace_env_none_type_values."""

        class DictReturnSource(PydanticBaseEnvSettingsSource):
            def get_field_value(self, field, field_name):
                if field_name == 'name':
                    return {'key': EnvNoneType('null'), 'other': 'keep'}, field_name, False
                return None, field_name, False

        source = DictReturnSource(SimpleSettings, env_parse_none_str='null')
        result = source()
        assert 'name' in result
        assert result['name']['key'] is None
        assert result['name']['other'] == 'keep'
