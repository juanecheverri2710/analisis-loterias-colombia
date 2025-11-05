from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/')
def home():
    return "✅ APP IS RUNNING!"

@app.route('/api/health')
def health():
    return jsonify({"status": "ok", "message": "App is healthy"})

if __name__ == '__main__':
    app.run(debug=True)
