import os
import tempfile
from pathlib import Path
from typing import List

import pytest

from pydantic_settings.utils import _lenient_issubclass, path_type_label


class TestPathTypeLabel:
    def test_path_type_label_file(self):
        """Test that a file is correctly identified."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            assert path_type_label(tmp_path) == 'file'
        finally:
            tmp_path.unlink()

    def test_path_type_label_directory(self):
        """Test that a directory is correctly identified."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            assert path_type_label(tmp_path) == 'directory'

    def test_path_type_label_symlink_to_file(self):
        """Test that a symlink to a file is identified as a file (not symlink)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_dir = Path(tmpdir)
            target = tmp_dir / 'target.txt'
            target.write_text('content')
            symlink = tmp_dir / 'link.txt'
            symlink.symlink_to(target)
            # Note: is_file() is checked before is_symlink(), so symlinks to files are labeled as 'file'
            assert path_type_label(symlink) == 'file'

    def test_path_type_label_nonexistent_path(self):
        """Test that an assertion is raised for nonexistent paths."""
        nonexistent = Path('/tmp/this_path_does_not_exist_12345')
        with pytest.raises(AssertionError, match='path does not exist'):
            path_type_label(nonexistent)

    @pytest.mark.skip(reason="Requires special permissions or OS-specific setup")
    def test_path_type_label_fifo(self):
        """Test that a FIFO is correctly identified."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fifo_path = Path(tmpdir) / 'test.fifo'
            os.mkfifo(fifo_path)
            assert path_type_label(fifo_path) == 'FIFO'


class TestLenientIssubclass:
    def test_lenient_issubclass_with_regular_class(self):
        """Test with regular class inheritance."""
        class Parent:
            pass

        class Child(Parent):
            pass

        assert _lenient_issubclass(Child, Parent) is True

    def test_lenient_issubclass_with_builtin_types(self):
        """Test with builtin types."""
        assert _lenient_issubclass(int, object) is True
        assert _lenient_issubclass(str, int) is False

    def test_lenient_issubclass_with_generic_alias(self):
        """Test with generic aliases like list[int]."""
        result = _lenient_issubclass(List[int], list)
        assert result is False

    def test_lenient_issubclass_with_non_type(self):
        """Test with non-type argument."""
        assert _lenient_issubclass('not a type', str) is False

    def test_lenient_issubclass_with_instance(self):
        """Test with an instance instead of a class."""
        assert _lenient_issubclass(42, int) is False

    def test_lenient_issubclass_with_none(self):
        """Test with None."""
        assert _lenient_issubclass(None, type(None)) is False
