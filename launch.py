"""A simple FastAPI server that launches a subprocess and allows you to
interact with it RESTfully."""
import asyncio
import os
import pty
from select import POLLIN, poll
import subprocess
import sys
from threading import Lock
from typing import Literal
from typing_extensions import TypedDict

import fastapi


class SubprocessStatus(TypedDict):
    """The status of the subprocess."""

    output: str
    done: bool
    whole: str


class StatusMessage(TypedDict):
    """A status message."""

    status: Literal["ok", "error"]


class Launcher:
    """Launches a subprocess and allows you to interact with it RESTfully."""

    def __init__(self, command: list[str]) -> None:
        """Initializes the Launcher.

        Args:
            command (list[str]): The child command to run.
        """
        self.accumulated_output = ""
        self.current_output = ""
        self.launch(command)
        self.active_websockets: set[fastapi.WebSocket] = set()
        self.lock = Lock()
        self.done = False

    def __call__(self) -> fastapi.FastAPI:
        """Return the FastAPI app."""
        asyncio.create_task(self._ws_stdout(self.fd))

        app = fastapi.FastAPI()
        app.post("/stdin")(self.stdin)
        app.get("/output")(self.output)
        app.websocket("/ws")(self.ws)
        return app

    def launch(self, command: list[str]) -> None:
        """Launch the subprocess.

        Args:
            command (list[str]): The child command to run.
        """
        self.pid, self.fd = pty.fork()
        if self.pid == 0:
            subprocess.call(command)
            sys.exit(0)

    def stdin(self, text: str = fastapi.Body(...)) -> StatusMessage:
        """Write to stdin.

        Args:
            text (str, optional): The text to write to stdin.

        Returns:
            StatusMessage: A status message.
        """
        os.write(self.fd, text.encode())
        return {"status": "ok"}

    def output(self) -> SubprocessStatus:
        """Read from stdout import"""
        with self.lock:
            out = self.current_output
            self.current_output = ""
            return {
                "output": out,
                "done": self.done,
                "whole": self.accumulated_output,
            }

    async def ws(self, websocket: fastapi.WebSocket) -> None:
        """Websocket handler."""
        await websocket.accept()
        self.active_websockets.add(websocket)
        await websocket.send_text(self.accumulated_output)
        await websocket.send_text("")

        await self._ws_stdin(websocket)

    async def _ws_stdin(self, websocket: fastapi.WebSocket) -> None:
        """Write to stdin.

        Args:
            websocket (fastapi.WebSocket): The websocket to read from.
        """
        async for text in websocket.iter_text():
            os.write(self.fd, text.encode())

    async def _ws_stdout(self, fd: int) -> None:
        """Read from stdout."""
        try:
            poller = poll()
            poller.register(fd, POLLIN)
            while True:
                if poller.poll(0):
                    out = os.read(fd, 1024)
                    with self.lock:
                        self.current_output += out.decode()
                        self.accumulated_output += out.decode()
                    for websocket in set(self.active_websockets):
                        try:
                            await websocket.send_text(out.decode())
                        except RuntimeError:
                            self.active_websockets.remove(websocket)
                else:
                    await asyncio.sleep(0.1)
        except OSError:
            self.done = True
            await asyncio.gather(
                *[websocket.close() for websocket in self.active_websockets]
            )


def launch() -> fastapi.FastAPI:
    """Launch a subprocess and return a FastAPI app that allows you
    to interact with it RESTfully."""
    command = os.environ.get("COMMAND")
    if command is None:
        raise ValueError("Environment variable COMMAND not set.")
    return Launcher(command.split(" "))()
