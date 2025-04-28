import socket  # noqa: F401


def http_200_ok(message):
    return f"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: {len(message)}\r\n\r\n{message}".encode()


def http_404_not_found():
    return b"HTTP/1.1 404 Not Found"


def main():
    # You can use print statements as follows for debugging, they'll be visible when running tests.
    print("Logs from your program will appear here!")

    # Uncomment this to pass the first stage
    #
    server_socket = socket.create_server(("localhost", 4221), reuse_port=True)
    conn, address = server_socket.accept()  # wait for client
    request = conn.recv(4096).decode()
    header, body = request.split("\r\n\r\n")
    header = header.split("\r\n")
    method, path, version = header[0].split()
    header_fields = {
        k.strip(): v.strip()
        for k, v in map(lambda line: line.split(":", 1), header[1:])
    }

    if path == "/":
        conn.sendall(http_200_ok(""))
    elif path.startswith("/echo/"):
        target = path.split("/")[2]
        conn.sendall(http_200_ok(target))
    elif path == "/user-agent":
        conn.sendall(http_200_ok(header_fields["User-Agent"]))
    else:
        conn.sendall(http_404_not_found())


if __name__ == "__main__":
    main()
