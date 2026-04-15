"""Tests for CliSettingsSource._add_parser_submodels covering previously uncovered branches."""
from __future__ import annotations

from typing import Optional, Union

import pytest
from pydantic import BaseModel, Field

from pydantic_settings import BaseSettings, CliSettingsSource
from pydantic_settings.exceptions import SettingsError
from pydantic_settings.sources.providers.cli import CLI_SUPPRESS, CliMutuallyExclusiveGroup


# --- Model definitions ---


class InnerModel(BaseModel):
    val: int = 0


class InnerModelWithDoc(BaseModel):
    """Class-level documentation for InnerModelWithDoc."""

    val: int = 0


class InnerModelNoDoc(BaseModel):
    val: int = 0


# Remove auto-generated docstring to ensure __doc__ is None
InnerModelNoDoc.__doc__ = None  # type: ignore[assignment]


# --- Line 1226: raise when model (parent) is CliMutuallyExclusiveGroup with nested model field ---


def test_add_parser_submodels_nested_in_mutually_exclusive_group_raises():
    class GroupWithNested(CliMutuallyExclusiveGroup):
        sub: InnerModel = Field(default=InnerModel())

    class SettingsWithGroup(BaseSettings):
        group: GroupWithNested = Field(default=GroupWithNested())

    with pytest.raises(SettingsError, match='cannot have nested models in a CliMutuallyExclusiveGroup'):
        CliSettingsSource(SettingsWithGroup, cli_parse_args=[])


# --- Line 1236: raise when union includes CliMutuallyExclusiveGroup with multiple sub_models ---


def test_add_parser_submodels_union_with_mutually_exclusive_group_raises():
    class MyMEGroup(CliMutuallyExclusiveGroup):
        a: str = 'x'

    class OtherModel(BaseModel):
        b: str = 'y'

    class SettingsWithUnion(BaseSettings):
        choice: Union[MyMEGroup, OtherModel] = Field(default=MyMEGroup())

    with pytest.raises(SettingsError, match='cannot use union with CliMutuallyExclusiveGroup'):
        CliSettingsSource(SettingsWithUnion, cli_parse_args=[])


# --- Line 1238: cli_use_class_docs_for_groups with a single sub_model (doc present) ---


def test_add_parser_submodels_cli_use_class_docs_for_groups_with_doc():
    class SettingsWithDoc(BaseSettings):
        inner: InnerModelWithDoc = Field(default=InnerModelWithDoc())

    source = CliSettingsSource(SettingsWithDoc, cli_parse_args=[], cli_use_class_docs_for_groups=True)
    assert source is not None


# --- Line 1238: cli_use_class_docs_for_groups with a single sub_model (no doc) ---


def test_add_parser_submodels_cli_use_class_docs_for_groups_no_doc():
    class SettingsNoDoc(BaseSettings):
        inner: InnerModelNoDoc = Field(default=InnerModelNoDoc())

    source = CliSettingsSource(SettingsNoDoc, cli_parse_args=[], cli_use_class_docs_for_groups=True)
    assert source is not None


# --- Lines 1241-1242: model_default is a pydantic model instance ---


def test_add_parser_submodels_model_default_is_model_instance():
    class OuterModel(BaseModel):
        inner: InnerModel = InnerModel()

    class SettingsWithDefault(BaseSettings):
        outer: OuterModel = OuterModel(inner=InnerModel(val=5))

    source = CliSettingsSource(SettingsWithDefault, cli_parse_args=[])
    assert source is not None


# --- Lines 1246-1247: field_info.default_factory is set ---


def test_add_parser_submodels_default_factory():
    class SettingsWithFactory(BaseSettings):
        inner: InnerModel = Field(default_factory=InnerModel)

    source = CliSettingsSource(SettingsWithFactory, cli_parse_args=[])
    assert source is not None


# --- Lines 1249-1253: model_default is None, with description ---


def test_add_parser_submodels_model_default_none_with_description():
    class SettingsNoneWithDesc(BaseSettings):
        inner: Optional[InnerModel] = Field(default=None, description='Some field description')

    source = CliSettingsSource(SettingsNoneWithDesc, cli_parse_args=[])
    assert source is not None


# --- Lines 1249-1253: model_default is None, without description ---


def test_add_parser_submodels_model_default_none_no_description():
    class SettingsNoneNoDesc(BaseSettings):
        inner: Optional[InnerModel] = Field(default=None)

    source = CliSettingsSource(SettingsNoneNoDesc, cli_parse_args=[])
    assert source is not None


# --- Line 1258: is_model_suppressed branch ---


def test_add_parser_submodels_suppressed_model():
    class SettingsSuppressed(BaseSettings):
        inner: InnerModel = Field(default=InnerModel(), description=CLI_SUPPRESS)

    source = CliSettingsSource(SettingsSuppressed, cli_parse_args=[])
    assert source is not None
