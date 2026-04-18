"""Tests for CliSettingsSource._metavar_format_recurse method."""

from __future__ import annotations

import typing
from typing import ForwardRef

import pytest
from pydantic import BaseModel
from pydantic._internal._repr import Representation

from pydantic_settings import BaseSettings, CliSettingsSource


def _module_level_test_func():
    """A module-level function for testing."""
    pass


class TestMetavarFormatRecurseFunction:
    """Tests for _metavar_format_recurse with function objects."""

    def test_function_with_locals_in_qualname(self):
        """Test _metavar_format_recurse returns __name__ for locally defined function."""

        def outer():
            def inner_local_func():
                pass
            return inner_local_func

        local_func = outer()

        class Settings(BaseSettings):
            name: str = 'default'

        source = CliSettingsSource(Settings, cli_prog_name='test')
        result = source._metavar_format_recurse(local_func)

        assert result == 'inner_local_func'
        assert '<locals>' in local_func.__qualname__

    def test_function_without_locals_in_qualname(self):
        """Test _metavar_format_recurse returns __qualname__ for top-level function."""

        class Settings(BaseSettings):
            name: str = 'default'

        source = CliSettingsSource(Settings, cli_prog_name='test')
        result = source._metavar_format_recurse(_module_level_test_func)

        # Module-level function should not have '<locals>' in qualname
        assert '<locals>' not in _module_level_test_func.__qualname__
        assert result == _module_level_test_func.__qualname__


class TestMetavarFormatRecurseEllipsis:
    """Tests for _metavar_format_recurse with ellipsis."""

    def test_ellipsis_returns_dots(self):
        """Test _metavar_format_recurse returns '...' for Ellipsis."""

        class Settings(BaseSettings):
            name: str = 'default'

        source = CliSettingsSource(Settings, cli_prog_name='test')
        result = source._metavar_format_recurse(...)

        assert result == '...'


class TestMetavarFormatRecurseRepresentation:
    """Tests for _metavar_format_recurse with Representation objects."""

    def test_representation_returns_repr(self):
        """Test _metavar_format_recurse returns repr for Representation instance."""

        class MyRepr(Representation):
            def __repr__(self):
                return 'MyRepr(custom)'

        obj = MyRepr()

        class Settings(BaseSettings):
            name: str = 'default'

        source = CliSettingsSource(Settings, cli_prog_name='test')
        result = source._metavar_format_recurse(obj)

        assert result == 'MyRepr(custom)'


class TestMetavarFormatRecurseForwardRef:
    """Tests for _metavar_format_recurse with ForwardRef."""

    def test_forward_ref_returns_str(self):
        """Test _metavar_format_recurse returns str for ForwardRef."""
        ref = ForwardRef('SomeType')

        class Settings(BaseSettings):
            name: str = 'default'

        source = CliSettingsSource(Settings, cli_prog_name='test')
        result = source._metavar_format_recurse(ref)

        assert result == str(ref)


class TestMetavarFormatRecurseTypeAliasType:
    """Tests for _metavar_format_recurse with TypeAliasType."""

    def test_type_alias_type_returns_str(self):
        """Test _metavar_format_recurse returns str for TypeAliasType."""
        # TypeAliasType was added in Python 3.12, but typing_objects.is_typealiastype
        # should handle it. We can use a TypeAlias if available.
        try:
            # Python 3.12+ has TypeAliasType
            from typing import TypeAliasType  # type: ignore[attr-defined]
            MyAlias = TypeAliasType('MyAlias', str)

            class Settings(BaseSettings):
                name: str = 'default'

            source = CliSettingsSource(Settings, cli_prog_name='test')
            result = source._metavar_format_recurse(MyAlias)

            assert result == str(MyAlias)
        except ImportError:
            pytest.skip('TypeAliasType not available in this Python version')


class TestMetavarFormatRecurseNonTypingObject:
    """Tests for _metavar_format_recurse with non-typing objects (line 1351)."""

    def test_instance_uses_class(self):
        """Test that non-type instances get converted to their class type."""

        class Settings(BaseSettings):
            name: str = 'default'

        source = CliSettingsSource(Settings, cli_prog_name='test')

        # Pass an instance (not a type) that isn't a special typing construct
        # This should fall through to line 1350-1351 where obj = obj.__class__
        # Then line 1375-1376 (isinstance(obj, type)) returns the class qualname
        instance = 'some string instance'
        result = source._metavar_format_recurse(instance)

        # The string instance becomes str class, which returns 'str'
        assert result == 'str'


class TestMetavarFormatRecurseFallback:
    """Tests for _metavar_format_recurse fallback case (line 1378)."""

    def test_typing_special_form_fallback(self):
        """Test fallback repr for typing constructs that don't match other cases."""

        class Settings(BaseSettings):
            name: str = 'default'

        source = CliSettingsSource(Settings, cli_prog_name='test')

        # typing.Any is a special form that should trigger the fallback
        # It's not a type, not a _WithArgsTypes, but also not a normal instance
        result = source._metavar_format_recurse(typing.Any)

        # Should return repr without 'typing.' prefix
        assert 'typing.' not in result
        assert 'Any' in result
