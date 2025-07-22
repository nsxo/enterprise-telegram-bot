#!/usr/bin/env python3
"""
Ultra-minimal HTTP server for Railway deployment testing
"""

import http.server
import socketserver
import os

PORT = int(os.environ.get('PORT', 8000))

class SimpleHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        response = '{"status": "ok", "message": "Simple server works!", "port": "' + str(PORT) + '"}'
        self.wfile.write(response.encode())

if __name__ == "__main__":
    with socketserver.TCPServer(("0.0.0.0", PORT), SimpleHandler) as httpd:
        print(f"🚀 Simple server starting on port {PORT}")
        httpd.serve_forever() 