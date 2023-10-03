"""A simple FastAPI server that launches a subprocess and allows you to
interact with it RESTfully."""
import os
import pty
from select import POLLIN, poll
import subprocess
import sys
from typing import Literal
from typing_extensions import TypedDict

from websocket_server import WebsocketServer


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
        self.server: WebsocketServer | None = None
        self.launch(command)
        self.done = False

    def __call__(self) -> None:
        """Return the FastAPI app."""
        server = WebsocketServer(port=8080, host="0.0.0.0")
        server.set_fn_new_client(self.new_client)
        server.set_fn_message_received(self.message_received)
        server.run_forever(threaded=True)
        self.server = server
        self._handle_stdout(self.fd)

    def launch(self, command: list[str]) -> None:
        """Launch the subprocess.

        Args:
            command (list[str]): The child command to run.
        """
        self.pid, self.fd = pty.fork()
        if self.pid == 0:
            subprocess.call(command)
            sys.exit(0)

    def new_client(self, client, server: WebsocketServer) -> None:
        """Websocket handler."""
        server.send_message(client, self.accumulated_output)

    def send_message(self, message: str) -> None:
        """Send a message to all clients."""
        if self.server is not None:
            self.server.send_message_to_all(message)

    def message_received(self, client, server: WebsocketServer, message: str) -> None:
        """Websocket handler."""
        os.write(self.fd, message.encode())

    def _handle_stdout(self, fd: int) -> None:
        """Read from stdout."""
        try:
            poller = poll()
            poller.register(fd, POLLIN)
            while True:
                if poller.poll(0):
                    out = os.read(fd, 1024)
                    self.current_output += out.decode()
                    self.accumulated_output += out.decode()
                    self.send_message(out.decode())
        except OSError:
            self.done = True


def main():
    command = os.environ.get("COMMAND")
    if command is None:
        raise ValueError("Environment variable COMMAND not set.")
    Launcher(command.split(" "))()


if __name__ == "__main__":
    main()
