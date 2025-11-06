from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return '''<html>
    <head><title>Análisis Loterías</title></head>
    <body>
        <h1>✅ App funcionando</h1>
        <p>API lista para usar.</p>
    </body>
    </html>'''

if __name__ == '__main__':
    app.run(debug=False)
