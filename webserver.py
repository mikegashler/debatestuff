from typing import Mapping, Any, Dict, Callable, cast, Optional
from http.server import BaseHTTPRequestHandler, HTTPServer
import webbrowser
import os
import json
import urllib.parse as urlparse
import urllib.request, urllib.parse, urllib.error
import random
import string
from http.cookies import SimpleCookie
import re
import posixpath
import datetime

COOKIE_LEN = 12

reserved_session: Optional[str] = None

def new_session_id() -> str:
    global reserved_session
    if reserved_session is not None:
        sess_id, reserved_session = reserved_session, None
        return sess_id
    return ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.ascii_lowercase + string.digits) for _ in range(COOKIE_LEN))

sws: 'SimpleWebServer'
simpleWebServerPages: Mapping[str, Any] = {}
class SimpleWebServer(BaseHTTPRequestHandler):
    def __init__(self, *args: Any) -> None:
        BaseHTTPRequestHandler.__init__(self, *args)

    def send_file(self, filename: str, content: str, session_id: str) -> None:
        self.send_response(200)
        name, ext = os.path.splitext(filename)
        if ext == '.svg':
            self.send_header('Content-type', 'image/svg+xml')
        elif ext == '.jpeg' or ext == '.jpg':
            self.send_header('Content-type', 'image/jpeg')
        else:
            self.send_header('Content-type', 'text/html')

        expires = datetime.datetime.utcnow() + datetime.timedelta(days=720)
        s_expires = expires.strftime("%a, %d %b %Y %H:%M:%S GMT")
        self.send_header('Set-Cookie', f'sid={session_id}; samesite=strict; Expires={s_expires}')
        self.end_headers()
        if isinstance(content, str):
            self.wfile.write(bytes(content, 'utf8'))
        else:
            self.wfile.write(content)

    def do_HEAD(self) -> None:
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

    def do_GET(self) -> None:
        global sws
        sws = self

        # Parse url
        url_parts = urlparse.urlparse(self.path)
        filename = url_parts.path
        if filename[0] == '/':
            filename = filename[1:]

        # Parse query
        q = urlparse.parse_qs(url_parts.query)
        q = { k:(q[k][0] if len(q[k]) == 1 else q[k]) for k in q } # type: ignore

        # Parse cookies
        cookie = SimpleCookie(self.headers.get('Cookie')) # type: ignore
        if 'sid' in cookie:
            session_id = cookie['sid'].value
            if len(session_id) != COOKIE_LEN:
                print(f'Bad session id {session_id}. Making new one.')
                session_id = new_session_id()
        else:
            session_id = new_session_id()
            print(f'No session id. Making new one.')

        # Get content
        if filename in simpleWebServerPages:
            content = simpleWebServerPages[filename](q, session_id)
        else:
            try:
                with open(filename, 'rb') as f:
                    content = f.read()
            except:
                content = f'404 {filename} not found.\n'
        self.send_file(filename, content, session_id)

    def do_POST(self) -> None:
        global sws
        sws = self

        # Parse url
        url_parts = urlparse.urlparse(self.path)
        filename = url_parts.path
        if filename[0] == '/':
            filename = filename[1:]

        if filename == 'receive_image.html':
            # Parse cookies
            session_id = ''
            cookie = SimpleCookie(self.headers.get('Cookie')) # type: ignore
            if 'sid' in cookie:
                session_id = cookie['sid'].value
            else:
                raise ValueError('No cookie in POST with uploaded file.')

            response = simpleWebServerPages[filename]({}, session_id)
            ajax_params = {}
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(bytes(response, 'utf8'))
        else:
            # Parse content
            content_len = int(self.headers.get('Content-Length'))
            post_body = self.rfile.read(content_len)
            ajax_params = json.loads(post_body)

            # Parse cookies
            session_id = ''
            if 'session_id' in ajax_params:
                session_id = ajax_params['session_id']
            if len(session_id) != COOKIE_LEN:
                cookie = SimpleCookie(self.headers.get('Cookie'))
                if 'sid' in cookie:
                    session_id = cookie['sid'].value
                else:
                    raise ValueError('No cookie with POST. This is probably an error')
                    session_id = new_session_id()

            # Generate a response
            response = simpleWebServerPages[filename](ajax_params, session_id)
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(bytes(json.dumps(response), 'utf8'))

    # Returns the filename specified for the file
    def receive_file(self, save_as_name: str, max_size: int) -> str:
        content_type = self.headers['content-type']
        if not content_type:
            assert False, "No content-type header"
        boundary = content_type.split("=")[1].encode()
        remainbytes = int(self.headers['content-length'])
        assert remainbytes <= max_size, 'File too big'
        line = self.rfile.readline()
        remainbytes -= len(line)
        if not boundary in line:
            assert False, "expected content to begin with boundary"
        line = self.rfile.readline()
        remainbytes -= len(line)
        fn = re.findall(r'Content-Disposition.*name="file"; filename="(.*)"', line.decode()) or ['']
        line = self.rfile.readline()
        remainbytes -= len(line)
        line = self.rfile.readline()
        remainbytes -= len(line)
        with open(save_as_name, 'wb') as out:
            preline = self.rfile.readline()
            remainbytes -= len(preline)
            while remainbytes > 0:
                line = self.rfile.readline()
                remainbytes -= len(line)
                if boundary in line:
                    preline = preline[0:-1]
                    if preline.endswith(b'\r'):
                        preline = preline[0:-1]
                    out.write(preline)
                    out.close()
                    break
                else:
                    out.write(preline)
                    preline = line
        return str(fn[0])

    @staticmethod
    def render(pages: Mapping[str, Callable[[Mapping[str,Any], str],Any]]) -> None:
        global simpleWebServerPages
        simpleWebServerPages = pages
        port = 8986
        httpd = HTTPServer(('', port), SimpleWebServer)
        webbrowser.open(f'http://localhost:{port}/index.html', new=2)
        print('Press Ctrl-C to shut down again')
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
        httpd.server_close()



if __name__ == "__main__":
    def do_index(params: Mapping[str, Any], session_id:str) -> str:
        s = [
            """<html><body>
<h1>Here is the number 4:</h1>""",
            str(4),
            '</body></html>'
        ]
        return ''.join(s)

    SimpleWebServer.render({
        'index.html': do_index
    })
