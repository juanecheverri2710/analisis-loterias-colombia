from flask import Flask, render_template

app = Flask(__name__, template_folder='templates', static_folder='static')

@app.route('/')
def home():
    """Ruta raíz - DEBE EXISTIR"""
    try:
        return render_template('index.html')
    except Exception as e:
        return f"<h1>Error cargando la página</h1><p>{str(e)}</p>", 500

@app.errorhandler(404)
def not_found(error):
    return f"<h1>404 - Página no encontrada</h1><p>{error}</p>", 404

# Para desarrollo local SOLAMENTE
if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
