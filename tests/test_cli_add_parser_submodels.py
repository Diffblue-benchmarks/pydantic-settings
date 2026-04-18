"""Tests for CliSettingsSource._add_parser_submodels method."""

from __future__ import annotations

from typing import Annotated

import pytest
from pydantic import BaseModel, Field
from pydantic.dataclasses import dataclass as pydantic_dataclass

from pydantic_settings import BaseSettings, CliSettingsSource, SettingsError
from pydantic_settings.sources.providers.cli import (
    CLI_SUPPRESS,
    CliMutuallyExclusiveGroup,
)


class TestAddParserSubmodelsUnionWithMutuallyExclusiveGroup:
    """Tests for error when union with CliMutuallyExclusiveGroup."""

    def test_union_with_mutually_exclusive_group_raises_error(self):
        """Test that union with CliMutuallyExclusiveGroup raises SettingsError."""

        class ExclusiveGroup(CliMutuallyExclusiveGroup):
            option_a: str | None = None
            option_b: str | None = None

        class OtherModel(BaseModel):
            value: str = 'default'

        class Settings(BaseSettings):
            group: ExclusiveGroup | OtherModel

        with pytest.raises(SettingsError, match='cannot use union with CliMutuallyExclusiveGroup'):
            CliSettingsSource(Settings)


class TestAddParserSubmodelsClassDocsForGroups:
    """Tests for cli_use_class_docs_for_groups with nested models."""

    def test_use_class_docs_for_groups_with_docstring(self):
        """Test cli_use_class_docs_for_groups uses class docstring."""

        class SubModel(BaseModel):
            """This is the submodel documentation."""

            value: str = 'default'

        class Settings(BaseSettings):
            nested: SubModel = SubModel()

        source = CliSettingsSource(Settings, cli_use_class_docs_for_groups=True)
        source(args=[])
        help_text = source.root_parser.format_help()
        assert 'This is the submodel documentation.' in help_text

    def test_use_class_docs_for_groups_with_none_docstring(self):
        """Test cli_use_class_docs_for_groups handles None docstring."""

        class SubModelNoDoc(BaseModel):
            value: str = 'default'

        # Clear the docstring if there is one
        SubModelNoDoc.__doc__ = None

        class Settings(BaseSettings):
            nested: SubModelNoDoc = SubModelNoDoc()

        source = CliSettingsSource(Settings, cli_use_class_docs_for_groups=True)
        source(args=[])
        # Should not raise, description should be None
        assert source.root_parser is not None


class TestAddParserSubmodelsModelDefault:
    """Tests for model_default handling in _add_parser_submodels."""

    def test_model_default_from_parent_model_class(self):
        """Test model_default extracted from parent model instance (covers line 1241-1242)."""

        class InnerSubModel(BaseModel):
            inner_value: str = 'inner_default'

        class OuterSubModel(BaseModel):
            inner: InnerSubModel = InnerSubModel(inner_value='from_outer')

        class Settings(BaseSettings):
            outer: OuterSubModel = OuterSubModel()

        source = CliSettingsSource(Settings)
        source(args=[])
        # The nested model's default should be extracted from parent
        assert source.root_parser is not None
        help_text = source.root_parser.format_help()
        assert 'outer' in help_text.lower()

    def test_model_default_from_pydantic_dataclass(self):
        """Test model_default extracted from pydantic dataclass instance (covers line 1241)."""
        from dataclasses import field as dataclass_field

        class InnerModel(BaseModel):
            value: str = 'inner'

        @pydantic_dataclass
        class DataclassOuter:
            nested: InnerModel = dataclass_field(default_factory=lambda: InnerModel(value='from_dataclass'))

        class Settings(BaseSettings):
            outer: DataclassOuter = Field(default_factory=DataclassOuter)

        source = CliSettingsSource(Settings)
        source(args=[])
        assert source.root_parser is not None

    def test_model_default_with_default_factory(self):
        """Test model_default using default_factory."""

        class SubModel(BaseModel):
            value: str = 'default'

        def make_submodel():
            return SubModel(value='from_factory')

        class Settings(BaseSettings):
            nested: SubModel = Field(default_factory=make_submodel)

        source = CliSettingsSource(Settings)
        source(args=[])
        # Verify the source was created and parser works
        assert source.root_parser is not None

    def test_model_default_none_adds_description_header(self):
        """Test model_default=None appends header to existing description (covers line 1250-1251)."""

        class SubModelWithDesc(BaseModel):
            """This is the model description."""

            value: str = 'default'

        class Settings(BaseSettings):
            nested: SubModelWithDesc | None = Field(default=None, description='Field description')

        source = CliSettingsSource(Settings)
        source(args=[])
        help_text = source.root_parser.format_help()
        # Should include the default: null (undefined) text prepended to description
        assert 'null' in help_text.lower() or 'undefined' in help_text.lower()
        assert 'description' in help_text.lower()

    def test_model_default_none_without_description(self):
        """Test model_default=None sets description to just header (covers line 1253)."""

        class SubModelNoDesc(BaseModel):
            value: str = 'default'

        SubModelNoDesc.__doc__ = None

        class Settings(BaseSettings):
            nested: SubModelNoDesc | None = Field(default=None, description=None)

        source = CliSettingsSource(Settings)
        source(args=[])
        help_text = source.root_parser.format_help()
        # Should set description to just the default header
        assert 'null' in help_text.lower() or 'undefined' in help_text.lower()


class TestAddParserSubmodelsSuppressed:
    """Tests for suppressed field handling in _add_parser_submodels."""

    def test_suppressed_model_field(self):
        """Test suppressed model field sets description to CLI_SUPPRESS."""

        class SubModel(BaseModel):
            value: str = 'default'

        class Settings(BaseSettings):
            nested: Annotated[SubModel, CLI_SUPPRESS] = SubModel()

        source = CliSettingsSource(Settings)
        source(args=[])
        help_text = source.root_parser.format_help()
        # Suppressed fields should not appear in help
        assert 'nested' not in help_text

    def test_suppressed_via_description(self):
        """Test model field suppressed via description=SUPPRESS."""

        class SubModel(BaseModel):
            value: str = 'default'

        class Settings(BaseSettings):
            nested: SubModel = Field(default=SubModel(), description=CLI_SUPPRESS)

        source = CliSettingsSource(Settings)
        source(args=[])
        help_text = source.root_parser.format_help()
        # Suppressed fields should not appear in help
        assert 'nested options' not in help_text


class TestAddParserSubmodelsInheritSuppressed:
    """Tests for inherited suppression in _add_parser_submodels."""

    def test_nested_model_inherits_parent_suppression(self):
        """Test that nested models inherit parent's suppressed state."""

        class InnerModel(BaseModel):
            inner_value: str = 'inner'

        class OuterModel(BaseModel):
            inner: InnerModel = InnerModel()

        class Settings(BaseSettings):
            outer: Annotated[OuterModel, CLI_SUPPRESS] = OuterModel()

        source = CliSettingsSource(Settings)
        source(args=[])
        help_text = source.root_parser.format_help()
        # Both outer and inner should be suppressed
        assert 'outer' not in help_text
        assert 'inner' not in help_text
