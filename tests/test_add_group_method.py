"""Tests for CliSettingsSource.add_group_method (mutually exclusive group branch)."""

from unittest.mock import MagicMock

import pytest

from pydantic_settings import BaseSettings, CliSettingsSource
from pydantic_settings.exceptions import SettingsError


class SimpleSettings(BaseSettings):
    name: str = 'default'

    model_config = {'env_file': None}


class TestAddGroupMethodMutuallyExclusive:
    """Tests covering the mutually exclusive group path in add_group_method (lines 875-883)."""

    def _get_add_group(self, cli_source):
        """Helper to access the _connect_group_method result via _add_group."""
        return cli_source._add_group

    def test_mutually_exclusive_group_calls_add_mutually_exclusive_group(self):
        """Test that when _is_cli_mutually_exclusive_group is True, the method creates
        a mutually exclusive group from the argument group."""
        cli_source = CliSettingsSource(SimpleSettings, cli_parse_args=[])

        mock_parser = MagicMock()
        mock_group = MagicMock()
        mock_exclusive_group = MagicMock()
        mock_group.add_mutually_exclusive_group.return_value = mock_exclusive_group

        # Mock _add_group's internal add_argument_group to return mock_group
        # We need to call _connect_group_method directly with a custom callable
        def fake_add_argument_group(parser, **kwargs):
            return mock_group

        add_group = cli_source._connect_group_method(fake_add_argument_group)

        result = add_group(
            mock_parser,
            _is_cli_mutually_exclusive_group=True,
            title='Options',
            description='Some options',
            required=True,
        )

        assert result is mock_exclusive_group
        mock_group.add_mutually_exclusive_group.assert_called_once_with(required=True)

    def test_mutually_exclusive_group_appends_title_suffix(self):
        """Test that ' (mutually exclusive)' is appended to the title."""
        cli_source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
        captured_kwargs = {}

        def fake_add_argument_group(parser, **kwargs):
            captured_kwargs.update(kwargs)
            group = MagicMock()
            group.add_mutually_exclusive_group.return_value = MagicMock()
            return group

        add_group = cli_source._connect_group_method(fake_add_argument_group)

        add_group(
            MagicMock(),
            _is_cli_mutually_exclusive_group=True,
            title='MyGroup',
            description='A description',
            required=False,
        )

        assert captured_kwargs['title'] == 'MyGroup (mutually exclusive)'
        assert captured_kwargs['description'] == 'A description'

    def test_mutually_exclusive_group_extracts_only_title_and_description(self):
        """Test that only title and description go to the main group; remaining kwargs
        go to add_mutually_exclusive_group."""
        cli_source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
        main_kwargs = {}
        exclusive_kwargs = {}

        def fake_add_argument_group(parser, **kwargs):
            main_kwargs.update(kwargs)
            group = MagicMock()

            def capture_exclusive(**kw):
                exclusive_kwargs.update(kw)
                return MagicMock()

            group.add_mutually_exclusive_group = capture_exclusive
            return group

        add_group = cli_source._connect_group_method(fake_add_argument_group)

        add_group(
            MagicMock(),
            _is_cli_mutually_exclusive_group=True,
            title='Flags',
            required=True,
        )

        assert 'title' in main_kwargs
        assert 'required' not in main_kwargs
        assert exclusive_kwargs == {'required': True}

    def test_mutually_exclusive_group_missing_method_raises_error(self):
        """Test that a SettingsError is raised when the group object lacks
        add_mutually_exclusive_group."""
        cli_source = CliSettingsSource(SimpleSettings, cli_parse_args=[])

        class FakeGroup:
            """A group object without add_mutually_exclusive_group."""
            pass

        def fake_add_argument_group(parser, **kwargs):
            return FakeGroup()

        add_group = cli_source._connect_group_method(fake_add_argument_group)

        with pytest.raises(
            SettingsError,
            match='group object is missing add_mutually_exclusive_group',
        ):
            add_group(
                MagicMock(),
                _is_cli_mutually_exclusive_group=True,
                title='Broken',
                required=False,
            )

    def test_non_mutually_exclusive_still_works(self):
        """Test that the non-mutually-exclusive path still works (already covered lines,
        but ensures no regression)."""
        cli_source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
        mock_result = MagicMock()

        def fake_add_argument_group(parser, **kwargs):
            return mock_result

        add_group = cli_source._connect_group_method(fake_add_argument_group)

        result = add_group(
            MagicMock(),
            _is_cli_mutually_exclusive_group=False,
            required=True,
            title='Group',
        )

        assert result is mock_result

    def test_mutually_exclusive_group_without_description(self):
        """Test mutually exclusive group when only title is provided (no description)."""
        cli_source = CliSettingsSource(SimpleSettings, cli_parse_args=[])
        captured_kwargs = {}

        def fake_add_argument_group(parser, **kwargs):
            captured_kwargs.update(kwargs)
            group = MagicMock()
            group.add_mutually_exclusive_group.return_value = MagicMock()
            return group

        add_group = cli_source._connect_group_method(fake_add_argument_group)

        add_group(
            MagicMock(),
            _is_cli_mutually_exclusive_group=True,
            title='OnlyTitle',
            required=False,
        )

        assert captured_kwargs == {'title': 'OnlyTitle (mutually exclusive)'}
        assert 'description' not in captured_kwargs
