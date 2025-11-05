from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return "<h1>✅ Flask Lottery App Online!</h1>", 200

@app.route('/<path:path>')
def catch_all(path):
    return "<h1>✅ Flask Lottery App Online!</h1>", 200

@app.route('/api/health')
def health():
    return {"status": "ok"}, 200

if __name__ == '__main__':
    app.run()
