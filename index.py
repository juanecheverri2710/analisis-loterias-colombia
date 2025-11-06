from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def home():
    return '''
    <html>
    <head><title>Análisis Loterías Colombia</title></head>
    <body>
        <h1>¡Hola! App funcionando ✅</h1>
        <p>La API está lista.</p>
    </body>
    </html>
    '''

@app.errorhandler(404)
def not_found(error):
    return "<h1>404 - No encontrado</h1>", 404

if __name__ == '__main__':
    app.run(debug=False)
