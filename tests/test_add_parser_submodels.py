"""Tests for CliSettingsSource._add_parser_submodels uncovered lines."""

from typing import Annotated, Optional, Union

import pytest

from pydantic import BaseModel, Field
from pydantic.fields import FieldInfo

from pydantic_settings import BaseSettings, CLI_SUPPRESS, CliMutuallyExclusiveGroup, CliSettingsSource, CliSuppress
from pydantic_settings.exceptions import SettingsError


# ---- Models for testing ----

class InnerModel(BaseModel):
    x: int = 1


class MutexGroupWithNested(CliMutuallyExclusiveGroup):
    inner: InnerModel = InnerModel()


class SettingsNestedInMutex(BaseSettings):
    group: MutexGroupWithNested = MutexGroupWithNested()

    model_config = {'env_file': None}


class SimpleMutex(CliMutuallyExclusiveGroup):
    a: str = 'x'


class OtherModel(BaseModel):
    b: str = 'y'


class SettingsUnionMutex(BaseSettings):
    item: Union[SimpleMutex, OtherModel] = SimpleMutex()

    model_config = {'env_file': None}


class DocModel(BaseModel):
    """This model has a docstring."""
    host: str = 'localhost'


class NoDocModel(BaseModel):
    host: str = 'localhost'


class SettingsClassDocsWithDoc(BaseSettings):
    server: DocModel = DocModel()

    model_config = {'env_file': None}


class SettingsClassDocsNoDoc(BaseSettings):
    server: NoDocModel = NoDocModel()

    model_config = {'env_file': None}


class Level2(BaseModel):
    value: str = 'deep'


class Level1(BaseModel):
    level2: Level2 = Level2()


class SettingsDeepNested(BaseSettings):
    level1: Level1 = Level1()

    model_config = {'env_file': None}


class FactoryModel(BaseModel):
    value: str = 'created'


class SettingsFactory(BaseSettings):
    item: FactoryModel = Field(default_factory=FactoryModel)

    model_config = {'env_file': None}


class OptModel(BaseModel):
    value: str = 'opt'


class SettingsOptionalNoneWithDesc(BaseSettings):
    item: Optional[OptModel] = Field(None, description='an optional model')

    model_config = {'env_file': None}


class SettingsOptionalNoneNoDesc(BaseSettings):
    item: Optional[OptModel] = None

    model_config = {'env_file': None}


class SuppressedInnerModel(BaseModel):
    val: str = 'hidden'


class SettingsSuppressed(BaseSettings):
    item: CliSuppress[SuppressedInnerModel] = SuppressedInnerModel()

    model_config = {'env_file': None}


# ---- Tests ----

class TestAddParserSubmodels:
    def test_nested_model_in_mutually_exclusive_group_raises(self):
        """Line 1226: nested models in CliMutuallyExclusiveGroup raise SettingsError."""
        with pytest.raises(SettingsError, match='cannot have nested models in a CliMutuallyExclusiveGroup'):
            CliSettingsSource(SettingsNestedInMutex, cli_parse_args=[])

    def test_union_with_mutually_exclusive_group_raises(self):
        """Line 1236: Union containing CliMutuallyExclusiveGroup with other models raises."""
        with pytest.raises(SettingsError, match='cannot use union with CliMutuallyExclusiveGroup'):
            CliSettingsSource(SettingsUnionMutex, cli_parse_args=[])

    def test_class_docs_for_groups_with_docstring(self):
        """Line 1238: cli_use_class_docs_for_groups uses class docstring when available."""
        source = CliSettingsSource(
            SettingsClassDocsWithDoc,
            cli_parse_args=[],
            cli_use_class_docs_for_groups=True,
        )
        # Should not raise and should use DocModel's docstring
        result = source()
        assert isinstance(result, dict)

    def test_class_docs_for_groups_no_docstring(self):
        """Line 1238: cli_use_class_docs_for_groups sets None when no docstring."""
        source = CliSettingsSource(
            SettingsClassDocsNoDoc,
            cli_parse_args=[],
            cli_use_class_docs_for_groups=True,
        )
        result = source()
        assert isinstance(result, dict)

    def test_deep_nested_model_default_extraction(self):
        """Lines 1241-1242: model_default is a model instance, extract field value."""
        source = CliSettingsSource(SettingsDeepNested, cli_parse_args=[])
        result = source()
        assert isinstance(result, dict)

    def test_default_factory_model(self):
        """Lines 1246-1247: field with default_factory."""
        source = CliSettingsSource(SettingsFactory, cli_parse_args=[])
        result = source()
        assert isinstance(result, dict)

    def test_optional_model_none_with_description(self):
        """Lines 1249-1251: model_default is None with field description set."""
        source = CliSettingsSource(SettingsOptionalNoneWithDesc, cli_parse_args=[])
        result = source()
        assert isinstance(result, dict)

    def test_optional_model_none_no_description(self):
        """Lines 1252-1253: model_default is None without field description."""
        source = CliSettingsSource(SettingsOptionalNoneNoDesc, cli_parse_args=[])
        result = source()
        assert isinstance(result, dict)

    def test_suppressed_model_field(self):
        """Line 1258: suppressed field sets description to CLI_SUPPRESS."""
        source = CliSettingsSource(SettingsSuppressed, cli_parse_args=[])
        result = source()
        assert isinstance(result, dict)

    def test_deep_nested_with_cli_args(self):
        """Lines 1241-1242: verify deep nested model works with actual CLI args."""
        source = CliSettingsSource(
            SettingsDeepNested,
            cli_parse_args=['--level1.level2.value', 'override'],
        )
        result = source()
        assert result.get('level1', {}).get('level2', {}).get('value') == 'override'

    def test_optional_model_none_with_json_arg(self):
        """Lines 1249-1253: optional None model can be set via JSON."""
        source = CliSettingsSource(
            SettingsOptionalNoneWithDesc,
            cli_parse_args=['--item', '{"value": "from_json"}'],
        )
        result = source()
        assert result.get('item', {}).get('value') == 'from_json'

    def test_factory_model_with_cli_override(self):
        """Lines 1246-1247: default_factory model can be overridden via CLI."""
        source = CliSettingsSource(
            SettingsFactory,
            cli_parse_args=['--item.value', 'overridden'],
        )
        result = source()
        assert result.get('item', {}).get('value') == 'overridden'
