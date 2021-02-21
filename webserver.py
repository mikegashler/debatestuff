from typing import Mapping, Any, Dict, Callable, cast, Optional
from http.server import BaseHTTPRequestHandler, HTTPServer
import webbrowser
import os
import json
import urllib.parse as urlparse
import urllib.request, urllib.parse, urllib.error
from http.cookies import SimpleCookie
import re
import posixpath
from datetime import datetime, timedelta
import sessions


sws: 'SimpleWebServer'
simpleWebServerPages: Mapping[str, Any] = {}
class SimpleWebServer(BaseHTTPRequestHandler):
    def __init__(self, *args: Any) -> None:
        self.mime_types: Dict[str, str] = {}
        self.mime_types['.svg'] = 'image/svg+xml'
        self.mime_types['.jpeg'] = 'image/jpeg'
        self.mime_types['.jpg'] = 'image/jpeg'
        self.mime_types['.png'] = 'image/png'
        self.mime_types['.js'] = 'text/javascript'
        BaseHTTPRequestHandler.__init__(self, *args)

    def send_file(self, filename: str, content: str, session_id: str) -> None:
        self.send_response(200)
        name, ext = os.path.splitext(filename)
        if ext in self.mime_types:
            self.send_header('Content-type', self.mime_types[ext])
        else:
            self.send_header('Content-type', 'text/html')
        expires = datetime.utcnow() + timedelta(days=720)
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

        ip_address = self.client_address[0]

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
            if len(session_id) != sessions.COOKIE_LEN:
                print(f'Bad session id {session_id}. Making new one.')
                session_id = sessions.new_session_id()
        else:
            session_id = sessions.new_session_id()
            print(f'No session id. Making new one.')
        session = sessions.get_or_make_session(session_id, ip_address)

        # Get content
        if filename in simpleWebServerPages:
            content = simpleWebServerPages[filename](q, session)
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

        ip_address = self.client_address[0]

        # Parse url
        url_parts = urlparse.urlparse(self.path)
        filename = url_parts.path
        if filename[0] == '/':
            filename = filename[1:]

        # Parse cookies
        session_id = ''
        cookie = SimpleCookie(self.headers.get('Cookie')) # type: ignore
        if 'sid' in cookie:
            session_id = cookie['sid'].value
        else:
            # The XHR specification forbids clients from setting 'Cookie',
            # so we work around that with 'Brownie' instead.
            brownie = SimpleCookie(self.headers.get('Brownie')) # type: ignore
            if 'sid' in brownie:
                session_id = cookie['sid'].value
            else:
                raise ValueError('No cookie in POST with uploaded file.')
        session = sessions.get_or_make_session(session_id, ip_address)

        upload_file_type = 'multipart/form-data'
        if filename == 'receive_image.html':
            response = simpleWebServerPages[filename]({}, session)
            ajax_params = {}
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(bytes(response, 'utf8'))
        elif self.headers.get('Content-Type')[:len(upload_file_type)] == upload_file_type:
            act = self.headers.get('Act') # An action specifying what to do with this image
            t = datetime.now()
            fn = f'{session_id}_{t.year:04}-{t.month:02}-{t.day:02}_{t.hour:02}-{t.minute:02}-{t.second:02}-{t.microsecond:06}.jpeg'
            self.receive_file(f'/tmp/{fn}', 16000000)
            response = simpleWebServerPages[filename]({
                'act': act,
                'file': fn,
            }, session)
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(bytes(json.dumps(response), 'utf8'))
        else:
            # Parse content
            content_len = int(self.headers.get('Content-Length'))
            post_body = self.rfile.read(content_len)
            ajax_params = json.loads(post_body)

            # Generate a response
            response = simpleWebServerPages[filename](ajax_params, session)
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
        # print(f'boundary={boundary}')
        remainbytes = int(self.headers['content-length'])
        # print(f'packet size={remainbytes}')
        assert remainbytes <= max_size, 'File too big'
        assert remainbytes > 0, 'Empty file packet'
        line = self.rfile.readline()
        remainbytes -= len(line)
        if not boundary in line:
            assert False, "expected content to begin with boundary"
        line = self.rfile.readline()
        remainbytes -= len(line)
        fn = re.findall(r'Content-Disposition.*name="file"; filename="(.*)"', line.decode()) or ['']

        # Skip b'Content-Type: image/jpeg\r\n'
        line = self.rfile.readline()
        remainbytes -= len(line)
        # print(f'discard_line_1={line}') # type: ignore

        # Skip b'\r\n'
        line = self.rfile.readline()
        remainbytes -= len(line)
        print(f'discard_line_2={line}') # type: ignore

        # Read the file
        assert remainbytes > 0, 'Empty file'
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
    def render(pages: Mapping[str, Callable[[Mapping[str,Any], sessions.Session],Any]]) -> None:
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
    def do_index(params: Mapping[str, Any], session: sessions.Session) -> str:
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
