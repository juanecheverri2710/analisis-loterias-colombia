import sys
import os

# Agrega el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Importa tu aplicación Flask
from app import app

# Exporta para Vercel
application = app
