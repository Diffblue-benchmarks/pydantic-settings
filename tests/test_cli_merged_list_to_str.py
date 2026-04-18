"""Tests for CliSettingsSource._merged_list_to_str method."""

from __future__ import annotations

from collections import defaultdict
from typing import Annotated, Any

import pytest
from pydantic import BaseModel

from pydantic_settings import BaseSettings, CliSettingsSource, SettingsError
from pydantic_settings.sources.providers.cli import _CliArg
from pydantic_settings.sources.types import NoDecode


class TestMergedListToStrExceptionHandling:
    """Tests for exception handling in _merged_list_to_str (lines 640-641)."""

    def test_exception_in_type_adapter_sets_is_num_type_str_none(self):
        """Test that exception during TypeAdapter validation sets is_num_type_str to None."""

        class Settings(BaseSettings):
            items: list[str] = []

        source = CliSettingsSource(Settings)
        source(args=['--items', 'a', '--items', 'b'])

        # Call _merged_list_to_str with an unknown field name that's not in _parser_map
        # This will cause the TypeAdapter creation to fail
        result = source._merged_list_to_str(['value1', 'value2'], 'unknown_field')

        # Should still produce valid output even when is_num_type_str is None
        assert result == '[value1,value2]'

    def test_exception_with_quoted_numeric_value(self):
        """Test exception handling when value looks like quoted number."""

        class Settings(BaseSettings):
            items: list[str] = []

        source = CliSettingsSource(Settings)
        source(args=['--items', 'a'])

        # With unknown field, quoted numeric should have inner quotes unquoted
        result = source._merged_list_to_str(['"123"'], 'unknown_field')
        # When is_num_type_str is None, the numeric value is still detected as float
        # and unquoted (since unquoted_item passes float() test)
        assert result == '[123]'


class TestMergedListToStrMixingDecodeError:
    """Tests for mixing Decode and NoDecode error (line 648)."""

    def test_mixing_decode_and_nodecode_raises_error(self):
        """Test that mixing Decode and NoDecode across AliasPath fields raises SettingsError."""

        class DecodeModel(BaseModel):
            field: str = ''

        class NoDecodeModel(BaseModel):
            field: Annotated[str, NoDecode] = ''

        class Settings(BaseSettings):
            items: list[str] = []

        source = CliSettingsSource(Settings)
        source(args=['--items', 'a'])

        # Manually set up _parser_map to simulate mixing Decode and NoDecode
        mock_field_info_decode = DecodeModel.model_fields['field']
        mock_field_info_nodecode = NoDecodeModel.model_fields['field']

        parser_map: defaultdict[str | Any, dict[int | None | str | type[BaseModel], _CliArg]] = defaultdict(dict)

        # Create _CliArg for decode (index 0) - is_no_decode will be False
        arg_decode = _CliArg(
            field_info=mock_field_info_decode,
            parser_map=parser_map,
            model=DecodeModel,
            parser=None,
            field_name='field',
            arg_prefix='',
            case_sensitive=True,
            populate_by_name=False,
            hide_none_type=False,
            kebab_case=False,
            enable_decoding=True,
            env_prefix_len=0,
        )

        # Create _CliArg for nodecode (index 1) - is_no_decode will be True
        arg_nodecode = _CliArg(
            field_info=mock_field_info_nodecode,
            parser_map=parser_map,
            model=NoDecodeModel,
            parser=None,
            field_name='field',
            arg_prefix='',
            case_sensitive=True,
            populate_by_name=False,
            hide_none_type=False,
            kebab_case=False,
            enable_decoding=True,
            env_prefix_len=0,
        )

        # Verify the is_no_decode values are different
        assert arg_decode.is_no_decode is False
        assert arg_nodecode.is_no_decode is True

        # Manually set up parser map with mixed decode settings
        source._parser_map['mixed_field'] = {
            0: arg_decode,  # First item: Decode (is_no_decode=False)
            1: arg_nodecode,  # Second item: NoDecode (is_no_decode=True)
        }

        with pytest.raises(SettingsError, match='Mixing Decode and NoDecode across different AliasPath fields'):
            source._merged_list_to_str(['value1', 'value2'], 'mixed_field')


class TestMergedListToStrNumericStringType:
    """Tests for is_num_type_str=True case (line 654)."""

    def test_numeric_value_quoted_when_type_is_str(self):
        """Test that numeric values are quoted when the list element type is str."""

        class Settings(BaseSettings):
            numbers: list[str] = []

        source = CliSettingsSource(Settings)
        source(args=['--numbers', '123', '--numbers', '456'])

        # For list[str], numeric strings should be wrapped in quotes
        result = source._merged_list_to_str(['123', '456'], 'numbers')

        # When is_num_type_str is True (list[str]), numeric values should be quoted
        assert result == '["123","456"]'

    def test_already_quoted_numeric_preserved(self):
        """Test that already quoted numeric values are handled correctly."""

        class Settings(BaseSettings):
            numbers: list[str] = []

        source = CliSettingsSource(Settings)
        source(args=['--numbers', '"123"'])

        # Already quoted numeric values
        result = source._merged_list_to_str(['"123"'], 'numbers')

        # Should still have quotes for str type
        assert result == '["123"]'

    def test_float_value_quoted_when_type_is_str(self):
        """Test that float values are quoted when the list element type is str."""

        class Settings(BaseSettings):
            numbers: list[str] = []

        source = CliSettingsSource(Settings)
        source(args=['--numbers', '3.14'])

        result = source._merged_list_to_str(['3.14'], 'numbers')

        # Float values should also be quoted for str type
        assert result == '["3.14"]'

    def test_negative_number_quoted_when_type_is_str(self):
        """Test that negative numbers are quoted when list element type is str."""

        class Settings(BaseSettings):
            numbers: list[str] = []

        source = CliSettingsSource(Settings)
        source(args=['--numbers', '-42'])

        result = source._merged_list_to_str(['-42'], 'numbers')

        assert result == '["-42"]'


class TestMergedListToStrNoDecodeQuotedItem:
    """Tests for NoDecode with quoted items (lines 657-658)."""

    def test_nodecode_removes_surrounding_quotes(self):
        """Test that NoDecode removes surrounding quotes from items."""

        class Settings(BaseSettings):
            raw_items: Annotated[list[str], NoDecode] = []

        source = CliSettingsSource(Settings)
        source(args=['--raw_items', '"value"'])

        # Set up parser_map with NoDecode argument
        mock_field_info = Settings.model_fields['raw_items']
        parser_map: defaultdict[str | Any, dict[int | None | str | type[BaseModel], _CliArg]] = defaultdict(dict)

        arg = _CliArg(
            field_info=mock_field_info,
            parser_map=parser_map,
            model=Settings,
            parser=None,
            field_name='raw_items',
            arg_prefix='',
            case_sensitive=True,
            populate_by_name=False,
            hide_none_type=False,
            kebab_case=False,
            enable_decoding=True,
            env_prefix_len=0,
        )

        # Add to parser_map for each index
        source._parser_map['nodecode_field'] = {0: arg}

        # When is_use_decode is False, quotes should be stripped
        result = source._merged_list_to_str(['"value"'], 'nodecode_field')

        # Quotes should be removed for NoDecode
        assert result == 'value'

    def test_nodecode_multiple_quoted_items(self):
        """Test NoDecode with multiple quoted items removes all quotes."""

        class Settings(BaseSettings):
            raw_items: Annotated[list[str], NoDecode] = []

        source = CliSettingsSource(Settings)
        source(args=['--raw_items', '"a"', '--raw_items', '"b"'])

        mock_field_info = Settings.model_fields['raw_items']
        parser_map: defaultdict[str | Any, dict[int | None | str | type[BaseModel], _CliArg]] = defaultdict(dict)

        arg = _CliArg(
            field_info=mock_field_info,
            parser_map=parser_map,
            model=Settings,
            parser=None,
            field_name='raw_items',
            arg_prefix='',
            case_sensitive=True,
            populate_by_name=False,
            hide_none_type=False,
            kebab_case=False,
            enable_decoding=True,
            env_prefix_len=0,
        )

        source._parser_map['nodecode_multi'] = {0: arg, 1: arg}

        result = source._merged_list_to_str(['"first"', '"second"'], 'nodecode_multi')

        # Both quoted items should have quotes stripped
        assert result == 'first,second'

    def test_nodecode_unquoted_item_unchanged(self):
        """Test that NoDecode leaves unquoted items unchanged."""

        class Settings(BaseSettings):
            raw_items: Annotated[list[str], NoDecode] = []

        source = CliSettingsSource(Settings)
        source(args=['--raw_items', 'unquoted'])

        mock_field_info = Settings.model_fields['raw_items']
        parser_map: defaultdict[str | Any, dict[int | None | str | type[BaseModel], _CliArg]] = defaultdict(dict)

        arg = _CliArg(
            field_info=mock_field_info,
            parser_map=parser_map,
            model=Settings,
            parser=None,
            field_name='raw_items',
            arg_prefix='',
            case_sensitive=True,
            populate_by_name=False,
            hide_none_type=False,
            kebab_case=False,
            enable_decoding=True,
            env_prefix_len=0,
        )

        source._parser_map['nodecode_unquoted'] = {0: arg}

        result = source._merged_list_to_str(['unquoted'], 'nodecode_unquoted')

        # Unquoted items should stay unchanged
        assert result == 'unquoted'

    def test_nodecode_partial_quotes_unchanged(self):
        """Test that NoDecode only strips when both start and end have quotes."""

        class Settings(BaseSettings):
            raw_items: Annotated[list[str], NoDecode] = []

        source = CliSettingsSource(Settings)
        source(args=['--raw_items', '"partial'])

        mock_field_info = Settings.model_fields['raw_items']
        parser_map: defaultdict[str | Any, dict[int | None | str | type[BaseModel], _CliArg]] = defaultdict(dict)

        arg = _CliArg(
            field_info=mock_field_info,
            parser_map=parser_map,
            model=Settings,
            parser=None,
            field_name='raw_items',
            arg_prefix='',
            case_sensitive=True,
            populate_by_name=False,
            hide_none_type=False,
            kebab_case=False,
            enable_decoding=True,
            env_prefix_len=0,
        )

        source._parser_map['nodecode_partial'] = {0: arg}

        result = source._merged_list_to_str(['"partial'], 'nodecode_partial')

        # Only starting quote - should not be stripped
        assert result == '"partial'
