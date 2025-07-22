#!/usr/bin/env python3
"""
Minimal Flask test app for Railway deployment testing
"""

from flask import Flask, jsonify
import os

app = Flask(__name__)

@app.route('/')
def hello():
    return jsonify({
        'status': 'ok',
        'message': 'Hello from Railway!',
        'port': os.environ.get('PORT', '8000'),
        'python_version': os.sys.version
    })

@app.route('/health')
def health():
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port) 