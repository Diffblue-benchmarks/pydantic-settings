"""Tests for CliApp._run_cli_cmd with async commands and a running event loop (run_coro path)."""

import asyncio
import threading

import pytest
from pydantic import BaseModel

from pydantic_settings import BaseSettings, CliApp, SettingsConfigDict


class AsyncCliModel(BaseModel):
    value: str = 'initial'
    executed: bool = False

    async def cli_cmd(self) -> None:
        self.executed = True
        self.value = 'async_done'


class AsyncCliSettings(BaseSettings):
    model_config = SettingsConfigDict(cli_parse_args=[])
    value: str = 'initial'
    executed: bool = False

    async def cli_cmd(self) -> None:
        self.executed = True
        self.value = 'async_done'


class AsyncCliRaisingModel(BaseModel):
    value: str = 'initial'

    async def cli_cmd(self) -> None:
        raise ValueError('async error from cli_cmd')


def test_run_cli_cmd_async_with_running_loop() -> None:
    """Test the run_coro path: async command executed from within a running event loop."""
    model = AsyncCliModel(value='initial', executed=False)
    result_holder: list[AsyncCliModel] = []
    exception_holder: list[Exception] = []

    def run_in_thread() -> None:
        loop = asyncio.new_event_loop()
        try:

            async def inner() -> None:
                result = CliApp._run_cli_cmd(model, 'cli_cmd', is_required=True)
                result_holder.append(result)

            loop.run_until_complete(inner())
        except Exception as e:
            exception_holder.append(e)
        finally:
            loop.close()

    thread = threading.Thread(target=run_in_thread)
    thread.start()
    thread.join()

    assert not exception_holder, f'Unexpected exception: {exception_holder}'
    assert len(result_holder) == 1
    result = result_holder[0]
    assert result.executed is True
    assert result.value == 'async_done'


def test_run_cli_cmd_async_with_running_loop_exception_propagation() -> None:
    """Test that exceptions from async commands in the run_coro path are propagated."""
    model = AsyncCliRaisingModel(value='initial')
    exception_holder: list[Exception] = []

    def run_in_thread() -> None:
        loop = asyncio.new_event_loop()
        try:

            async def inner() -> None:
                CliApp._run_cli_cmd(model, 'cli_cmd', is_required=True)

            loop.run_until_complete(inner())
        except ValueError as e:
            exception_holder.append(e)
        finally:
            loop.close()

    thread = threading.Thread(target=run_in_thread)
    thread.start()
    thread.join()

    assert len(exception_holder) == 1
    assert str(exception_holder[0]) == 'async error from cli_cmd'


def test_run_cli_cmd_async_with_running_loop_via_settings() -> None:
    """Test the run_coro path through CliApp.run with BaseSettings and a running loop."""
    result_holder: list[AsyncCliSettings] = []
    exception_holder: list[Exception] = []

    def run_in_thread() -> None:
        loop = asyncio.new_event_loop()
        try:

            async def inner() -> None:
                result = CliApp.run(AsyncCliSettings, cli_args=[])
                result_holder.append(result)

            loop.run_until_complete(inner())
        except Exception as e:
            exception_holder.append(e)
        finally:
            loop.close()

    thread = threading.Thread(target=run_in_thread)
    thread.start()
    thread.join()

    assert not exception_holder, f'Unexpected exception: {exception_holder}'
    assert len(result_holder) == 1
    result = result_holder[0]
    assert result.executed is True
    assert result.value == 'async_done'
