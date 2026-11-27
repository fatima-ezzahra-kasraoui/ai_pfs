from http.server import BaseHTTPRequestHandler, HTTPServer
import http.client
import socket
import ssl
import ipaddress
from html.parser import HTMLParser

class Text(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]; self.hidden=0
    def handle_starttag(self, tag, attrs):
        if tag in ('script','style'): self.hidden += 1
    def handle_endtag(self, tag):
        if tag in ('script','style'): self.hidden=max(0,self.hidden-1)
    def handle_data(self, data):
        if not self.hidden: self.parts.append(data)

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != '/': self.send_error(404); return
        try:
            host='example.com'
            ip=socket.getaddrinfo(host,443,socket.AF_INET,socket.SOCK_STREAM)[0][4][0]
            if not ipaddress.ip_address(ip).is_global: raise ValueError('IP denied')
            conn=http.client.HTTPSConnection(host,timeout=8,context=ssl.create_default_context())
            conn._create_connection=lambda address, timeout, source_address: socket.create_connection((ip,443),timeout,source_address)
            try:
                conn.request('GET','/',headers={'Accept-Encoding':'identity'})
                r=conn.getresponse()
                if r.status != 200 or 'text/html' not in r.getheader('Content-Type',''): raise ValueError('Response denied')
                data=r.read(256001)
                if len(data)>256000: raise ValueError('Size limit')
            finally: conn.close()
            parser=Text(); parser.feed(data.decode('utf-8','replace'))
            result=('https://example.com/\n'+' '.join(parser.parts)).encode()
            self.send_response(200); self.send_header('Content-Type','text/plain; charset=utf-8'); self.end_headers(); self.wfile.write(result)
        except Exception: self.send_error(502,'Fetch failed')
HTTPServer(('0.0.0.0',8090),Handler).serve_forever()
