import socket  # noqa: F401


def ok_response(message):
    return f"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: {len(message)}\r\n\r\n{message}".encode()


def main():
    # You can use print statements as follows for debugging, they'll be visible when running tests.
    print("Logs from your program will appear here!")

    # Uncomment this to pass the first stage
    #
    server_socket = socket.create_server(("localhost", 4221), reuse_port=True)
    conn, address = server_socket.accept()  # wait for client
    request = conn.recv(4096).decode()
    lines = request.splitlines()
    get_line = lines[0]
    path = get_line.split()[1]
    if path == "/":
        conn.sendall(b"HTTP/1.1 200 OK\r\n\r\n")
    elif path.startswith("/echo/"):
        target = path.split("/")[2]
        conn.sendall(ok_response(target))
    elif path.startswith("/user-agent"):
        agent_line = next(filter(lambda line: line.startswith("User-Agent"), lines))
        agent = agent_line.split(":")[1].strip()
        conn.sendall(ok_response(agent))
    else:
        conn.sendall(b"HTTP/1.1 404 Not Found\r\n\r\n")


if __name__ == "__main__":
    main()
