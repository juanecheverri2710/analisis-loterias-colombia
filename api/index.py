from flask import Flask, render_template, jsonify, request
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

app = Flask(__name__, template_folder='../templates', static_folder='../static')

@app.route('/')
def home():
    return "<h1>✅ Flask Lottery App Online!</h1>", 200

@app.route('/api/health')
def health():
    return jsonify({"status": "ok", "app": "analisis_loterias"}), 200

if __name__ == '__main__':
    app.run(debug=False)
