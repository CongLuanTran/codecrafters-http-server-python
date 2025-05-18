import argparse
import os
import re
import gzip
import socket  # noqa: F401
import threading
from pathlib import Path
from typing import Callable

parser = argparse.ArgumentParser()
parser.add_argument("--directory", action="store")
args = parser.parse_args()
target_path = args.directory if args.directory else os.getcwd()
target_dir = Path(target_path)

ENCODER = ["gzip"]

STASTUS = {
    200: "OK",
    201: "Created",
    404: "Not Found",
}

Route = tuple[str, re.Pattern, Callable]

routes: list[Route] = []


def add_route(method: str, path: str, handler: Callable):
    pattern = re.compile(path)
    routes.append((method, pattern, handler))


def find_handler(method: str, path: str):
    for route_method, pattern, handler in routes:
        if method == route_method and pattern.match(path):
            return handler
    return None


class HTTPRequest:
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
        headers_lines, body = raw_request.split("\r\n\r\n", 1)
        request_line, *header_lines = headers_lines.split("\r\n")
        method, path, version = request_line.split(" ")
        headers = {}
        for line in header_lines:
            if not line:
                break
            header, value = line.split(":", 1)
            headers[header.strip()] = value.strip()
        return cls(method, path, version, headers, body)


class HTTPResponse:
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
        if headers is None:
            headers = {}
        return cls("HTTP/1.1", 200, headers, body)

    @classmethod
    def not_found(cls):
        return cls("HTTP/1.1", 404, {}, "")

    @classmethod
    def created(cls):
        return cls("HTTP/1.1", 201, {}, "")

    def __bytes__(self):
        encoding = self.headers.get("Content-Encoding", "")
        if encoding:
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
    handler = find_handler(request.method, request.path)
    if handler:
        response = handler(request)
    else:
        response = HTTPResponse.not_found()
    return encode_response(request, response)


def home(_request: HTTPRequest):
    return HTTPResponse.ok()


def echo(request):
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
        f.write(content)
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


def encode_response(request: HTTPRequest, response: HTTPResponse):
    encoding = request.headers.get("Accept-Encoding", "")
    for enc in ENCODER:
        if enc in encoding:
            response.headers["Content-Encoding"] = enc
            break
    return response


add_route("GET", r"^/$", home)
add_route("GET", r"^/echo/(?P<message>.*)$", echo)
add_route("GET", r"/user-agent", user_agent)
add_route("GET", r"^/files/(?P<file>.*)", read_file)
add_route("POST", r"^/files/(?P<file>.*)", post_file)


def main():
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
    main()
