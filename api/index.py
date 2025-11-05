from flask import Flask

app = Flask(__name__)

@app.route('/')
@app.route('/<path:path>')
def catch_all(path=''):
    return "<h1>✅ Flask Lottery App Online!</h1>", 200

@app.route('/api/health')
def health():
    return {"status": "ok", "app": "analisis_loterias"}, 200

# Vercel needs this
def handler(request):
    return app(request.environ, request.start_response)
