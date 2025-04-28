import socket  # noqa: F401


def main():
    # You can use print statements as follows for debugging, they'll be visible when running tests.
    print("Logs from your program will appear here!")

    # Uncomment this to pass the first stage
    #
    server_socket = socket.create_server(("localhost", 4221), reuse_port=True)
    conn, address = server_socket.accept()  # wait for client
    request = conn.recv(4096).decode()
    lines = request.splitlines()
    path = lines[0].split()[1]
    if path == "/":
        conn.sendall(b"HTTP/1.1 200 OK\r\n\r\n")
    elif path.startswith("/echo/"):
        target = path.split("/")[2]
        conn.sendall(
            f"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: {len(target)}\r\n\r\n{target}".encode()
        )
    else:
        conn.sendall(b"HTTP/1.1 404 Not Found\r\n\r\n")


if __name__ == "__main__":
    main()
