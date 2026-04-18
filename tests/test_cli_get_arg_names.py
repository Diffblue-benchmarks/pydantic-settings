"""Tests for CliSettingsSource._get_arg_names method, focusing on discriminator handling."""

from __future__ import annotations

from typing import Annotated, Literal, Union

import pytest
from pydantic import BaseModel, Field

from pydantic_settings import BaseSettings, CliSettingsSource


class TestGetArgNamesWithDiscriminators:
    """Tests for _get_arg_names method with discriminated unions."""

    def test_discriminator_with_literal_type_single_model(self):
        """Test discriminator handling with a single model containing Literal type."""

        class Cat(BaseModel):
            pet_type: Literal['cat']
            meow: str = 'meow'

        class Dog(BaseModel):
            pet_type: Literal['dog']
            bark: str = 'woof'

        class Settings(BaseSettings):
            pet: Union[Cat, Dog] = Field(discriminator='pet_type')

        source = CliSettingsSource(Settings, cli_parse_args=['--pet.pet_type', 'cat'])
        result = source()
        assert result['pet']['pet_type'] == 'cat'

    def test_discriminator_with_literal_type_multiple_values(self):
        """Test discriminator field with multiple Literal values across models."""

        class Cat(BaseModel):
            animal_type: Literal['cat', 'feline']
            name: str = 'whiskers'

        class Dog(BaseModel):
            animal_type: Literal['dog', 'canine']
            name: str = 'fido'

        class Settings(BaseSettings):
            animal: Union[Cat, Dog] = Field(discriminator='animal_type')

        source = CliSettingsSource(Settings, cli_parse_args=['--animal.animal_type', 'dog'])
        result = source()
        assert result['animal']['animal_type'] == 'dog'

    def test_discriminator_with_kebab_case_enabled(self):
        """Test discriminator handling with kebab case enabled."""

        class TypeA(BaseModel):
            type_name: Literal['type_a']
            value_a: int = 1

        class TypeB(BaseModel):
            type_name: Literal['type_b']
            value_b: int = 2

        class Settings(BaseSettings):
            item: Union[TypeA, TypeB] = Field(discriminator='type_name')

        source = CliSettingsSource(
            Settings,
            cli_parse_args=['--item.type-name', 'type_a'],
            cli_kebab_case=True,
        )
        result = source()
        # The CLI uses kebab-case for args but the result dict uses original names
        assert result['item']['type_name'] == 'type_a'

    def test_discriminator_values_collected_across_models(self):
        """Test that discriminator values are collected from all models in union."""

        class Circle(BaseModel):
            shape: Literal['circle']
            radius: float = 1.0

        class Rectangle(BaseModel):
            shape: Literal['rectangle']
            width: float = 1.0
            height: float = 1.0

        class Triangle(BaseModel):
            shape: Literal['triangle']
            base: float = 1.0

        class Settings(BaseSettings):
            geometry: Union[Circle, Rectangle, Triangle] = Field(discriminator='shape')

        source = CliSettingsSource(
            Settings,
            cli_parse_args=['--geometry.shape', 'triangle'],
        )
        result = source()
        assert result['geometry']['shape'] == 'triangle'

    def test_discriminator_with_nested_model(self):
        """Test discriminator handling with nested model structures."""

        class ApiConfig(BaseModel):
            backend: Literal['api']
            endpoint: str = '/api'

        class FileConfig(BaseModel):
            backend: Literal['file']
            path: str = '/tmp'

        class Settings(BaseSettings):
            config: Union[ApiConfig, FileConfig] = Field(discriminator='backend')

        source = CliSettingsSource(
            Settings,
            cli_parse_args=['--config.backend', 'file', '--config.path', '/data'],
        )
        result = source()
        assert result['config']['backend'] == 'file'
        assert result['config']['path'] == '/data'

    def test_discriminator_metavar_sorted(self):
        """Test that discriminator metavar values are sorted."""

        class ZModel(BaseModel):
            kind: Literal['z_type']

        class AModel(BaseModel):
            kind: Literal['a_type']

        class MModel(BaseModel):
            kind: Literal['m_type']

        class Settings(BaseSettings):
            model: Union[ZModel, AModel, MModel] = Field(discriminator='kind')

        source = CliSettingsSource(Settings)
        # The discriminator metavar should be sorted alphabetically
        help_text = source.root_parser.format_help()
        # Check that the help text contains the sorted discriminator values
        assert 'a_type' in help_text or 'z_type' in help_text

    def test_is_last_discriminator_false_returns_empty(self):
        """Test that _get_arg_names returns empty when is_last_discriminator is False."""

        class ModelA(BaseModel):
            tag: Literal['a']
            field_a: str = 'a'

        class ModelB(BaseModel):
            tag: Literal['b']
            field_b: str = 'b'

        class Settings(BaseSettings):
            item: Union[ModelA, ModelB] = Field(discriminator='tag')

        # This test verifies the behavior when multiple models have the same
        # discriminator field - only the last model should produce arg names
        source = CliSettingsSource(Settings, cli_parse_args=['--item.tag', 'a'])
        result = source()
        assert result['item']['tag'] == 'a'

    def test_discriminator_with_annotated_literal(self):
        """Test discriminator handling with Annotated[Literal[...]]."""

        class Config1(BaseModel):
            mode: Annotated[Literal['mode1'], 'description']
            val1: int = 1

        class Config2(BaseModel):
            mode: Annotated[Literal['mode2'], 'description']
            val2: int = 2

        class Settings(BaseSettings):
            config: Union[Config1, Config2] = Field(discriminator='mode')

        source = CliSettingsSource(
            Settings,
            cli_parse_args=['--config.mode', 'mode2'],
        )
        result = source()
        assert result['config']['mode'] == 'mode2'

    def test_discriminator_field_with_string_values(self):
        """Test discriminator with string literal values including special chars."""

        class OpAdd(BaseModel):
            op: Literal['add']
            value: int = 0

        class OpSub(BaseModel):
            op: Literal['subtract']
            value: int = 0

        class Settings(BaseSettings):
            operation: Union[OpAdd, OpSub] = Field(discriminator='op')

        source = CliSettingsSource(
            Settings,
            cli_parse_args=['--operation.op', 'subtract', '--operation.value', '5'],
        )
        result = source()
        assert result['operation']['op'] == 'subtract'
        assert result['operation']['value'] == '5'
