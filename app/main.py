import argparse
import gzip
import os
import socket  # noqa: F401
import threading
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--directory", action="store")
args = parser.parse_args()
target_path = args.directory if args.directory else os.getcwd()
target_dir = Path(target_path)

valid_compression = ["gzip"]


class HTTPRequest:
    def __init__(self, request: str):
        head, self.body = request.split("\r\n\r\n")

        head = head.split("\r\n")
        self.method, self.path, self.version = head[0].split()
        self.headers = {
            k.strip(): v.strip()
            for k, v in map(lambda line: line.split(":", 1), head[1:])
        }

        self.headers.setdefault("Content-Type", "text/plain")
        self.headers.setdefault("Content-Length", str(len(self.body)))

    def __bytes__(self):
        request_line = f"{self.method} {self.path} {self.version}".encode()
        headers = "\r\n".join(f"{k}: {v}" for k, v in self.headers.items()).encode()
        body = self.body.encode()
        return request_line + b"\r\n" + headers + b"\r\n\r\n" + body


class HTTPResponse:
    def __init__(
        self,
        version: str,
        status_code: int,
        status_message: str,
        headers: dict[str, str],
        body: str,
    ):
        self.version = version
        self.status_code = status_code
        self.status_message = status_message
        self.headers = headers
        self.body = body

        self.headers.setdefault("Content-Type", "text/plain")
        self.headers.setdefault("Content-Length", str(len(self.body)))

    def encode(self, encoding):
        if not isinstance(self.body, str):
            return

        if encoding == "gzip":
            self.body = gzip.compress(self.body.encode())
            self.headers["Content-Length"] = str(len(self.body))
            self.headers["Content-Encoding"] = encoding

    def __bytes__(self):
        status_line = (
            f"{self.version} {self.status_code} {self.status_message}".encode()
        )
        headers = "\r\n".join(f"{k}: {v}" for k, v in self.headers.items()).encode()
        body = self.body.encode() if isinstance(self.body, str) else self.body
        return status_line + b"\r\n" + headers + b"\r\n\r\n" + body


def handle_client(conn: socket.socket):
    with conn:
        while True:
            raw_request = b""
            while b"\r\n\r\n" not in raw_request:
                raw_request += conn.recv(1024)

            request = HTTPRequest(raw_request.decode())
            while len(request.body) < int(request.headers["Content-Length"]):
                request.body += conn.recv(1024).decode()

            response = handle_request(request)
            conn.sendall(bytes(response))


def handle_request(request: HTTPRequest) -> HTTPResponse:
    if request.path == "/":
        response = http_200_ok("")
    elif "echo" in request.path:
        target = request.path.removeprefix("/echo/")
        response = http_200_ok(target)
    elif request.path == "/user-agent":
        response = http_200_ok(request.headers["User-Agent"])
    elif "files" in request.path:
        path = request.path.removeprefix("/files/")
        if request.method == "POST":
            response = post_file(path, request.body)
        else:
            response = read_file(path)
    else:
        response = http_404_not_found()

    if "Accept-Encoding" in request.headers:
        for encoding in request.headers["Accept-Encoding"].split(","):
            if encoding.strip() in valid_compression:
                response.encode(encoding.strip())
                break

    return response


def post_file(path: str, content: str):
    full_path = target_dir / path
    with open(full_path, "w") as f:
        f.write(content)

    return http_201_created()


def read_file(path: str):
    full_path = target_dir / path

    if not full_path.exists():
        return http_404_not_found()

    size = os.path.getsize(full_path)
    with open(full_path, "r") as f:
        content = f.read()

    return http_200_ok(
        content,
        {"Content-Length": str(size), "Content-Type": "application/octet-stream"},
    )


def http_200_ok(message: str, headers=None):
    if headers is None:
        headers = {}
    return HTTPResponse("HTTP/1.1", 200, "OK", headers, message)


def http_201_created():
    return HTTPResponse("HTTP/1.1", 201, "Created", {}, "")


def http_404_not_found():
    return HTTPResponse("HTTP/1.1", 404, "Not Found", {}, "")


def main():
    # You can use print statements as follows for debugging, they'll be visible when running tests.
    print("Logs from your program will appear here!")

    server_socket = socket.create_server(("localhost", 4221), reuse_port=True)
    print("Server is running at port 4221")

    with server_socket:
        while True:
            conn, address = server_socket.accept()  # wait for client
            thread = threading.Thread(target=handle_client, args=(conn,))
            thread.start()


if __name__ == "__main__":
    main()
