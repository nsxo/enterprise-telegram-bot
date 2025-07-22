#!/usr/bin/env python3
"""
Railway-specific test app following their documentation
"""

import os
import sys
from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/')
def root():
    """Root endpoint for Railway health checks"""
    return jsonify({
        'status': 'ok',
        'service': 'Railway Test',
        'port': os.environ.get('PORT', '8000'),
        'railway_env': os.environ.get('RAILWAY_ENVIRONMENT', 'unknown'),
        'railway_service': os.environ.get('RAILWAY_SERVICE_NAME', 'unknown')
    })

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy'})

@app.route('/railway')
def railway_info():
    """Railway-specific info endpoint"""
    return jsonify({
        'railway_environment': os.environ.get('RAILWAY_ENVIRONMENT'),
        'railway_service_name': os.environ.get('RAILWAY_SERVICE_NAME'),
        'railway_project_name': os.environ.get('RAILWAY_PROJECT_NAME'),
        'port': os.environ.get('PORT'),
        'python_version': sys.version
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    print(f"🚀 Railway test app starting on port {port}")
    print(f"Environment: {os.environ.get('RAILWAY_ENVIRONMENT')}")
    print(f"Service: {os.environ.get('RAILWAY_SERVICE_NAME')}")
    app.run(host='0.0.0.0', port=port, debug=False) 