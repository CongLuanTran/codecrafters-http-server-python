import typer
import os
import re
import gzip
import socket  # noqa: F401
import threading
from pathlib import Path
from typing import Annotated, Callable, final

target_dir = Path(os.getcwd())

ENCODER = ["gzip"]

STASTUS = {
    200: "OK",
    201: "Created",
    404: "Not Found",
}


@final
class HTTPRequest:
    """Represents an HTTP request.

    Attributes:
        method (str): The HTTP method (e.g., "GET", "POST").
        path (str): The request path (e.g., "/echo/hello").
        version (str): The HTTP version (e.g., "HTTP/1.1").
        headers (dict[str, str]): The request headers (e.g., {"Host": "localhost"}).
        body (str): The request body (e.g., "Hello, world!").
    """

    def __init__(
        self, method: str, path: str, version: str, headers: dict[str, str], body: str
    ):
        self.method = method
        self.path = path
        self.version = version
        self.headers = headers
        self.body = body

    @classmethod
    def from_raw(cls, raw_request: str):
        """Parse a raw HTTP request string into an HTTPRequest object.

        Args:
            raw_request (str): The raw HTTP request string, including headers and body.

        Returns:
            HTTPRequest: The parsed HTTPRequest object.
        """
        headers_lines, body = raw_request.split("\r\n\r\n", 1)
        request_line, *header_lines = headers_lines.split("\r\n")
        method, path, version = request_line.split(" ")
        headers: dict[str, str] = {}
        for line in header_lines:
            if not line:
                break
            header, value = line.split(":", 1)
            headers[header.strip()] = value.strip()
        return cls(method, path, version, headers, body)


@final
class HTTPResponse:
    """Represents an HTTP response.

    Attributes:
        version (str): The HTTP version (e.g., "HTTP/1.1").
        status (str): The HTTP status code (e.g., 200, 404).
        headers (dict[str, str] | None): The response headers (e.g., {"Content-Type": "text/plain"}).
        body (str): The response body (e.g., "Hello, world!").
    """

    def __init__(
        self,
        version: str,
        status: int,
        headers: dict[str, str] | None = None,
        body: str = "",
    ):
        self.version = version
        self.status = status
        self.headers = headers or {}
        self.body = body

    @classmethod
    def ok(cls, headers: dict[str, str] | None = None, body: str = ""):
        """Returns a 200 OK HTTP response.

        The headers is None by default, but can be provided to include additional headers.

        Args:
            headers (dict[str, str] | None): The response headers (optional).
            body (str): The response body.

        Returns:
            HTTPResponse: An HTTPResponse object with status 200 OK.
        """
        if headers is None:
            headers = {}
        return cls("HTTP/1.1", 200, headers, body)

    @classmethod
    def not_found(cls):
        """Returns a 404 Not Found HTTP response.

        Returns:
            HTTPResponse: An HTTPResponse object with status 404 Not Found.
        """
        return cls("HTTP/1.1", 404, {}, "")

    @classmethod
    def created(cls):
        """Returns a 201 Created HTTP response.

        Returns:
            HTTPResponse: An HTTPResponse object with status 201 Created.
        """
        return cls("HTTP/1.1", 201, {}, "")

    def __bytes__(self):
        if self.headers.get("Content-Encoding", ""):
            body = gzip.compress(self.body.encode())
            self.headers["Content-Length"] = str(len(body))
        else:
            body = self.body.encode()
        response_line = f"{self.version} {self.status} {STASTUS[self.status]}\r\n"
        headers_lines = "".join(
            header + ": " + value + "\r\n" for header, value in self.headers.items()
        )
        head = (response_line + headers_lines + "\r\n").encode()
        return head + body


Route = tuple[str, re.Pattern[str], Callable[..., HTTPResponse]]

routes: list[Route] = []


def add_route(method: str, path: str, handler: Callable[..., HTTPResponse]):
    """Add a route to the server.

    A route is defined by an HTTP method, a path pattern, and a handler function.

    Args:
        method (str): The HTTP method (e.g., "GET", "POST").
        path (str): The path pattern to match (e.g., "^/echo/.*$").
        handler (Callable): The function to handle requests to this route.
    """
    pattern = re.compile(path)
    routes.append((method, pattern, handler))


def find_handler(method: str, path: str):
    """Find the handler for a given method and path.

    Returns the handler function if a matching route is found, otherwise returns None.

    Args:
        method (str): The HTTP method (e.g., "GET", "POST").
        path (str): The request path to match against the route patterns.

    Returns:
        Callable | None: The handler function if a match is found, otherwise None.
    """
    for route_method, pattern, handler in routes:
        if method == route_method and pattern.match(path):
            return handler
    return None


def handle_client(conn: socket.socket):
    with conn:
        while True:
            raw_request = b""
            while b"\r\n\r\n" not in raw_request:
                raw_request += conn.recv(1024)

            request = HTTPRequest.from_raw(raw_request.decode())
            while len(request.body) < int(request.headers.get("Content-Length", 0)):
                request.body += conn.recv(1024).decode()

            response = handle_request(request)
            if request.headers.get("Connection") == "close":
                response.headers["Connection"] = "close"
                conn.sendall(bytes(response))
                return
            conn.sendall(bytes(response))


def handle_request(request: HTTPRequest) -> HTTPResponse:
    if handler := find_handler(request.method, request.path):
        response = handler(request)
    else:
        response = HTTPResponse.not_found()
    encoding = request.headers.get("Accept-Encoding", "")
    for enc in ENCODER:
        if enc in encoding:
            response.headers["Content-Encoding"] = enc
            break
    return response


def home(_request: HTTPRequest):
    return HTTPResponse.ok()


def echo(request: HTTPRequest):
    message = re.sub(r"^/echo/", "", request.path)
    headers = {
        "Content-Type": "text/plain",
        "Content-Length": str(len(message)),
    }
    return HTTPResponse.ok(headers, message)


def user_agent(request: HTTPRequest):
    user_agent = request.headers.get("User-Agent", "")
    headers = {
        "Content-Type": "text/plain",
        "Content-Length": str(len(user_agent)),
    }
    return HTTPResponse.ok(headers, user_agent)


def post_file(request: HTTPRequest):
    path = re.sub(r"^/files/", "", request.path)
    content = request.body
    full_path = target_dir / path
    with open(full_path, "w") as f:
        _ = f.write(content)
    return HTTPResponse.created()


def read_file(request: HTTPRequest):
    path = re.sub(r"^/files/", "", request.path)
    full_path = target_dir / path
    if not full_path.exists():
        return HTTPResponse.not_found()
    size = os.path.getsize(full_path)
    with open(full_path, "r") as f:
        content = f.read()
    headers = {
        "Content-Type": "application/octet-stream",
        "Content-Length": str(size),
    }
    return HTTPResponse.ok(headers, content)


add_route("GET", r"^/$", home)
add_route("GET", r"^/echo/(?P<message>.*)$", echo)
add_route("GET", r"/user-agent", user_agent)
add_route("GET", r"^/files/(?P<file>.*)", read_file)
add_route("POST", r"^/files/(?P<file>.*)", post_file)


def main(directory: Annotated[str | None, typer.Option()] = None):
    if directory:
        global target_dir
        target_dir = Path(directory).resolve()
    # You can use print statements as follows for debugging, they'll be visible when running tests.
    print("Logs from your program will appear here!")

    server_socket = socket.create_server(("localhost", 4221), reuse_port=True)
    print("Server is running at port 4221")

    with server_socket:
        while True:
            conn, _addr = server_socket.accept()  # wait for client
            thread = threading.Thread(target=handle_client, args=(conn,))
            thread.start()


if __name__ == "__main__":
    typer.run(main)
