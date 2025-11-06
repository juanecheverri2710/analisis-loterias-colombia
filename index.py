from flask import Flask, render_template, request, jsonify
import os
import sys

# Agregar ruta del proyecto
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Crear app
app = Flask(__name__, template_folder='templates', static_folder='static')

# ===== RUTA RAÍZ (CRÍTICA PARA VERCEL) =====
@app.route('/')
def home():
    """Ruta raíz - DEBE existir"""
    try:
        return render_template('index.html')
    except Exception as e:
        return f"<h1>Error cargando página:</h1><pre>{str(e)}</pre>", 500

# ===== OTRAS RUTAS =====
@app.route('/api/health')
def health():
    """Health check para Vercel"""
    return {'status': 'ok', 'message': 'App en línea'}

# Agregar aquí TODAS tus otras rutas (@app.route)
# por ejemplo: /predicciones, /estadisticas, etc.

# ===== MANEJO DE ERRORES =====
@app.errorhandler(404)
def not_found(e):
    return {'error': 'Ruta no encontrada'}, 404

@app.errorhandler(500)
def server_error(e):
    return {'error': 'Error del servidor'}, 500

# ===== SOLO PARA DESARROLLO LOCAL =====
if __name__ == '__main__':
    # SOLO se ejecuta en desarrollo local, NO en Vercel
    app.run(host='0.0.0.0', port=5000, debug=False)

# Vercel exporta automáticamente 'app'
