import socket
try:
    print(socket.gethostbyname('web.dessmonitor.com'))
except Exception as e:
    print(e)
