import socket  # noqa: F401
import threading


def handle_client(conn):
    request = conn.recv(4096).decode()
    request = HTTPRequest(request)

    if request.path == "/":
        response = http_200_ok("")
    elif request.path.startswith("/echo/"):
        target = request.path.split("/")[2]
        response = http_200_ok(target)
    elif request.path == "/user-agent":
        response = http_200_ok(request.headers["User-Agent"])
    else:
        response = http_404_not_found()

    conn.sendall(bytes(response))
    conn.close()


def http_200_ok(message):
    headers = {"Content-Length": f"{len(message)}"} if message else {}
    return HTTPResponse("HTTP/1.1", 200, "OK", headers, message)


def http_404_not_found():
    return HTTPResponse("HTTP/1.1", 404, "Not Found", {}, "")


def main():
    # You can use print statements as follows for debugging, they'll be visible when running tests.
    print("Logs from your program will appear here!")

    # Uncomment this to pass the first stage
    #
    server_socket = socket.create_server(("localhost", 4221), reuse_port=True)
    print("Server is running at port 4221")

    try:
        while True:
            conn, address = server_socket.accept()  # wait for client
            thread = threading.Thread(target=handle_client, args=(conn,))
            thread.start()
    except Exception as e:
        print(f"Error: {e}")
    finally:
        print("Closing connection")
        server_socket.close()


class HTTPRequest:
    def __init__(self, request):
        head, self.body = request.split("\r\n\r\n")

        head = head.split("\r\n")
        self.method, self.path, self.version = head[0].split()
        self.headers = {
            k.strip(): v.strip()
            for k, v in map(lambda line: line.split(":", 1), head[1:])
        }

    def __str__(self):
        headers = "\r\n".join(f"{k}: {v}" for k, v in self.headers.items())
        return (
            f"{self.method} {self.path} {self.version}\r\n{headers}\r\n\r\n{self.body}"
        )

    def __bytes__(self):
        return self.__str__().encode()


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

    def __str__(self):
        headers = "\r\n".join(f"{k}: {v}" for k, v in self.headers.items())
        return f"{self.version} {self.status_code} {self.status_message}\r\n{headers}\r\n\r\n{self.body}"

    def __bytes__(self):
        return self.__str__().encode()


if __name__ == "__main__":
    main()
