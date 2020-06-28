# http.py

import uos as os
import ujson as json
import usocket as socket

_handlers = {}

def route(path, method='GET', minetype='application/json'):
    def decorator(func):
        _handlers[(method.upper(), path)] = (func, minetype)
        return func
    return decorator


class Request:
    def __init__(self, socket):
        socket.settimeout(2)
        self._socket = socket
        self.method = None
        self.version = None
        self.path = "/"
        self.params = {}
        self.headers = {}
        self.ct_type = None
        self.length = 0
        if self._parse_first():
            self._parse_header()

    def _parse_first(self):
        line = self._socket.readline().decode().upper().strip().split()
        if len(line) == 3:
            self.method, url, self.version = line
            urls = url.lower().split('?', 1)
            self.path = self._unquote(urls[0].replace('+', ' '))
            if len(urls) > 1:
                for s in urls[1].split('&'):
                    p = s.split('=', 1)
                    self.params[self._unquote(p[0])] = self._unquote(p[1]) if len(p) > 1 else ''
            return True
        return False

    def _parse_header(self):
        while True:
            line = self._socket.readline().decode().strip().split(':', 1)
            if len(line) == 2:
                self.headers[line[0].strip().lower()] = line[1].strip()
            elif len(line) == 1 and not line[0]:
                if self.method == 'POST' or self.method == 'PUT':
                    self.ct_type = self.headers.get("content-type", None)
                    self.length = int(self.headers.get("content-length", 0))
                return True
            else:
                return False

    def _read(self, size=None):
        self._socket.setblocking(False)
        b = self._socket.read(size or self.length)
        self._socket.setblocking(True)
        return b if b else b''

    def read(self):
        try:
            return json.loads(self._read())
        except:
            return None

    @staticmethod
    def _unquote(s):
        r = s.split('%')
        for i in range(1, len(r)):
            s = r[i]
            try:
                r[i] = chr(int(s[:2], 16)) + s[2:]
            except:
                r[i] = '%' + s
        return ''.join(r)


class Response:
    def __init__(self, socket):
        self._socket = socket

    def _write(self, data):
        if data:
            if type(data) == str:
                data = data.encode()
            return self._socket.write(data)
        return 0

    def _write_header(self, key, value):
        self._write("%s: %s\r\n" % (key, value))

    def _write_before(self, code, headers, ct_type, charset, length):
        self._write("HTTP/1.1 %s MSG\r\n" % code)
        if isinstance(headers, dict):
            for header in headers:
                self._write_header(header, headers[header])
        if ct_type:
            ct = ct_type + (("; charset=%s" % charset) if charset else "")
        else:
            ct = "application/octet-stream"
        self._write_header("Content-Type", ct)
        if length > 0:
            self._write_header("Content-Length", length)
        self._write_header("Server", "mprest")
        self._write_header("Connection", "close")
        self._write("\r\n")

    def write(self, code, headers, ct_type, charset, content):
        if type(content) == str:
            content = content.encode()
        length = len(content) if content else 0
        self._write_before(code, headers, ct_type, charset, length)
        if content:
            self._write(content)

    def write_file(self, filepath, ct_type=None, headers=None):
        size = os.stat(filepath)[6]
        if size <= 0:
            self.error(403)
        with open(filepath, 'rb') as fp:
            self._write_before(200, headers, ct_type, None, size)
            try:
                buf = bytearray(1024)
                while size > 0:
                    x = fp.readinto(buf)
                    if x < len(buf):
                        buf = memoryview(buf)[:x]
                    self._write(buf)
                    size -= x
            except:
                self.error(500)
        self.error(404)

    def error(self, code):
        body = "<html><head><title>Error</title></head><body><h1>%d</h1></body></html>" % code
        return self.write( code, None, "text/html", "utf-8", body )


class Client:
    _mine = {
        ".txt"   : "text/plain",
        ".htm"   : "text/html",
        ".html"  : "text/html",
        ".css"   : "text/css",
        ".js"    : "application/javascript",
        ".json"  : "application/json",
        ".woff"  : "font/woff",
        ".woff2" : "font/woff2",
        ".ttf"   : "font/ttf",
        ".otf"   : "font/otf",
        ".jpg"   : "image/jpeg",
        ".jpeg"  : "image/jpeg",
        ".png"   : "image/png",
        ".gif"   : "image/gif",
        ".svg"   : "image/svg+xml",
        ".ico"   : "image/x-icon"
    }

    def __init__(self, server, socket):
        socket.settimeout(2)
        self._server = server
        self._socket = socket
        self._req = Request(self._socket)
        self._resp = Response(self._socket)

    def run(self):
        try:
            if self._req.headers:
                if (self._req.method.upper(), self._req.path) in _handlers:
                    fn, minetype = _handlers[(self._req.method, self._req.path)]
                    result = fn(self._req)
                    if type(result) in (list, tuple, dict):
                        result = json.dumps(result)
                    self._resp.write(200, None, minetype, "utf-8", result)
                elif self._req.method.upper() == "GET":
                    self._static(self._req.path)
                else:
                    self._resp.error(405)
            else:
                self._resp.error(400)
        except:
            self._resp.error(500)
        finally:
            self._socket.close()

    def _static(self, path):
        if path.endswith('/'):
            path += 'index.html'
        filepath = (self._server.root + path).replace('//', '/')
        print(filepath)
        try:
            os.stat(filepath)
        except:
            self._resp.error(404)
        ct_type = self._get_mine_type(filepath) or 'application/octet-stream'
        self._resp.write_file(filepath, ct_type)

    @classmethod
    def _get_mine_type(cls, name):
        name = name.lower()
        for ext in cls._mine:
            if name.endswith(ext):
                return cls._mine[ext]
        return None


class Server:
    def __init__( self, host='127.0.0.1', port=1000, root='/'):
        self.host = host
        self.port = port
        self.root = root
        self._running = False

    def _process(self):
        client, addr = self._server.accept()
        Client(self, client).run()

    def start(self):
        if not self._running:
            info = socket.getaddrinfo(self.host, self.port, 0, socket.SOCK_STREAM)[0]
            self._server = socket.socket(info[0], info[1], info[2])
            self._server.setblocking(False)
            self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server.bind(info[-1])
            self._server.listen(16)
            self._server.setsockopt(socket.SOL_SOCKET, 20, lambda x: self._process())
        self._running = True

    def stop(self):
        if self._running:
            self._server.close()
        self._running = False
