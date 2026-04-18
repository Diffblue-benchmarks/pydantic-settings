import tempfile
from pathlib import Path
from typing import List

import pytest

from pydantic_settings.utils import _lenient_issubclass, path_type_label


class TestPathTypeLabel:
    """Tests for path_type_label function."""

    def test_path_type_label_file(self):
        """Test that a regular file is identified correctly."""
        with tempfile.NamedTemporaryFile() as tmp_file:
            result = path_type_label(Path(tmp_file.name))
            assert result == 'file'

    def test_path_type_label_directory(self):
        """Test that a directory is identified correctly."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = path_type_label(Path(tmp_dir))
            assert result == 'directory'

    def test_path_type_label_symlink(self):
        """Test that a symlink is identified correctly.

        Note: Due to the ordering in _PATH_TYPE_LABELS, a symlink to a file
        will be identified as 'file' first, since is_file() returns True for
        symlinks pointing to files.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            target = Path(tmp_dir) / "target.txt"
            target.write_text("test")
            symlink = Path(tmp_dir) / "link.txt"
            symlink.symlink_to(target)
            result = path_type_label(symlink)
            # is_file() is checked before is_symlink() in the dictionary
            assert result == 'file'

    def test_path_type_label_nonexistent_path(self):
        """Test that nonexistent path raises assertion error."""
        nonexistent = Path("/nonexistent/path/that/does/not/exist")
        with pytest.raises(AssertionError, match="path does not exist"):
            path_type_label(nonexistent)


class TestLenientIssubclass:
    """Tests for _lenient_issubclass function."""

    def test_lenient_issubclass_basic_type(self):
        """Test with basic type subclass check."""
        result = _lenient_issubclass(int, object)
        assert result is True

    def test_lenient_issubclass_string_subclass(self):
        """Test with str as subclass of object."""
        result = _lenient_issubclass(str, object)
        assert result is True

    def test_lenient_issubclass_not_subclass(self):
        """Test with non-subclass relationship."""
        result = _lenient_issubclass(int, str)
        assert result is False

    def test_lenient_issubclass_non_type(self):
        """Test with non-type argument."""
        result = _lenient_issubclass("not a type", str)
        assert result is False

    def test_lenient_issubclass_with_generic_alias(self):
        """Test with generic alias like list[int]."""
        result = _lenient_issubclass(List[int], list)
        assert result is False

    def test_lenient_issubclass_tuple_of_types(self):
        """Test with tuple of types."""
        result = _lenient_issubclass(int, (str, int, float))
        assert result is True

    def test_lenient_issubclass_invalid_class_or_tuple(self):
        """Test that invalid class_or_tuple raises TypeError."""
        with pytest.raises(TypeError):
            _lenient_issubclass(int, "not a class")
