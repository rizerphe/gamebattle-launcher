"""A simple FastAPI server that launches a subprocess and allows you to
interact with it through websockets."""
import os
import pty
from select import POLLIN, poll

from websocket_server import WebsocketServer


class Launcher:
    """Launches a subprocess and allows you to interact with it through
    websockets."""

    def __init__(self, command: list[str]) -> None:
        """Initializes the Launcher.

        Args:
            command (list[str]): The child command to run.
        """
        self.accumulated_output = b""
        self.unsent_bytes = b""
        self.server: WebsocketServer | None = None
        self.launch(command)
        self.done = False

    def __call__(self) -> None:
        """Initialize the WebsocketServer."""
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
            import subprocess
            import sys

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
                if poller.poll(10):
                    out = os.read(fd, 1024)
                    self.accumulated_output += out
                    for i in range(0, len(out)):
                        try:
                            result = (
                                self.unsent_bytes + (out[:-i] if i else out)
                            ).decode()
                            self.unsent_bytes = out[-i:] if i else b""
                            self.send_message(result)
                            break
                        except UnicodeDecodeError:
                            pass
        except OSError:
            self.done = True


def main():
    command = os.environ.get("COMMAND")
    if command is None:
        raise ValueError("Environment variable COMMAND not set.")
    Launcher(command.split(" "))()


if __name__ == "__main__":
    main()
