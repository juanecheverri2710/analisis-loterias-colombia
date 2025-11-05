import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from app import app
    application = app
except Exception as e:
    # Fallback if import fails
    from flask import Flask, jsonify
    application = Flask(__name__)
    
    @application.route('/')
    def health():
        return "✅ Fallback OK"
    
    @application.route('/api/health')
    def api_health():
        return jsonify({"status": "ok"})
