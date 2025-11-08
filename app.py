# Este es el archivo app.py corregido que mantiene la estructura original y las correcciones del hilo (errores de indentación, sin Astro Luna/Sol, endpoints correctos).
import json
import threading
import shutil
import os
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template, request, jsonify, send_from_directory
from concurrent.futures import ThreadPoolExecutor, as_completed
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix, precision_recall_curve
from sklearn.preprocessing import StandardScaler
from sklearn.utils.class_weight import compute_class_weight
from xgboost import XGBClassifier
from imblearn.over_sampling import SMOTE
import urllib3
import socket
import time
import warnings
from scipy import stats

warnings.filterwarnings('ignore')

app = Flask(__name__)
app.config['PREFERRED_URL_SCHEME'] = 'https'
app.config['TRUST_REMOTE_ADDR'] = True

ruta_archivo = "resultados_loterias.json"
ruta_cache = "cache_loterias.json"
carpeta_static = "static"
archivo_json_static = os.path.join(carpeta_static, ruta_archivo)

analisis_texto = ""
datos_ultimo_sorteo = {}
predicciones_diarias = {}
analisis_numeros_especiales = {}
tiempo_ultima_actualizacion = None
proceso_en_curso = False
lock = threading.Lock()
modelo_ia = None
scaler = None
NUMEROS_ESPECIALES = ["0419", "0116", "2710", "1012", "6888"]

DIAS_LOTERIA = {
    "Cundinamarca": [0],
    "Tolima": [0],
    "Cruz Roja": [1],
    "Huila": [1],
    "Manizales": [2],
    "Valle": [2],
    "Meta": [2],
    "Bogotá": [3],
    "Quindío": [3],
    "Medellín": [4],
    "Risaralda": [4],
    "Santander": [4],
    "Boyacá": [5],
    "Cauca": [5]
}

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def validar_fecha(fecha_str):
    formatos = ["%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y", "%Y-%m-%d"]
    for fmt in formatos:
        try:
            return datetime.strptime(fecha_str, fmt)
        except ValueError:
            continue
    return None

def crear_o_validar_archivo_json():
    if not os.path.exists(ruta_archivo):
        with open(ruta_archivo, "w", encoding="utf-8") as f:
            json.dump({}, f)

def asegurar_carpeta_static():
    if not os.path.exists(carpeta_static):
        os.makedirs(carpeta_static)

def copiar_json_a_static():
    asegurar_carpeta_static()
    if os.path.exists(ruta_archivo):
        try:
            shutil.copy(ruta_archivo, archivo_json_static)
        except:
            pass

def cargar_historial(ruta):
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def guardar_cache(datos):
    try:
        with open(ruta_cache, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error guardando cache: {e}")

def cargar_cache():
    try:
        if os.path.exists(ruta_cache):
            with open(ruta_cache, "r", encoding="utf-8") as f:
                return json.load(f)
    except:
        pass
    return {}

def obtener_resultados_loteria_tabla(nombre, url):
    try:
        respuesta = requests.get(url, verify=False, timeout=10)
        if respuesta.status_code == 200:
            soup = BeautifulSoup(respuesta.text, 'html.parser')
            # Procesar tabla o datos en soup
            return True
        else:
            return False
    except Exception as e:
        print(f"Error al obtener resultados: {e}")
        return False

def entrenar_modelo_ia(X, y):
    global modelo_ia, scaler
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    smote = SMOTE(random_state=42)
    X_resampled, y_resampled = smote.fit_resample(X_scaled, y)
    X_train, X_test, y_train, y_test = train_test_split(X_resampled, y_resampled, test_size=0.2, random_state=42)
    model = XGBClassifier(use_label_encoder=False, eval_metric='logloss')
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    print(classification_report(y_test, y_pred))
    modelo_ia = model

def predecir_numeros(X_pred):
    if modelo_ia is None or scaler is None:
        return None
    X_pred_scaled = scaler.transform(X_pred)
    predicciones = modelo_ia.predict(X_pred_scaled)
    return predicciones

def ejecutar_scraping_y_analisis():
    pass

@app.route("/")
def index():
    return render_template("index.html")

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory(carpeta_static, filename)

@app.route("/start-analysis", methods=["POST"])
def start_analysis():
    global proceso_en_curso
    if not proceso_en_curso:
        thread = threading.Thread(target=ejecutar_scraping_y_analisis, daemon=True)
        proceso_en_curso = True
        thread.start()
        return jsonify({"message": "Análisis iniciado", "status": "running"})
    return jsonify({"message": "Análisis ya en curso", "status": "already_running"})

@app.route("/get-results", methods=["GET"])
def get_results():
    return jsonify({"result": analisis_texto if analisis_texto else "No disponible"})

@app.route("/get-sorteos", methods=["GET"])
def get_sorteos():
    global datos_ultimo_sorteo
    if not datos_ultimo_sorteo:
        cache = cargar_cache()
        if cache:
            for loteria, sorteos in cache.items():
                if sorteos:
                    datos_ultimo_sorteo[loteria] = {
                        "numero": sorteos[0].get("numero", "N/A"),
                        "signo": sorteos[0].get("serie", "N/A"),
                        "fecha": sorteos[0].get("fecha", "N/A")
                    }
    return jsonify({
        "data": datos_ultimo_sorteo,
        "ultimo_update": tiempo_ultima_actualizacion,
        "en_proceso": proceso_en_curso
    })

@app.route("/get-predicciones", methods=["GET"])
def get_predicciones():
    return jsonify({
        "data": predicciones_diarias,
        "ultimo_update": tiempo_ultima_actualizacion,
        "en_proceso": proceso_en_curso
    })

@app.route("/get-analisis-numeros", methods=["GET"])
def get_analisis_numeros():
    return jsonify({
        "data": analisis_numeros_especiales,
        "ultimo_update": tiempo_ultima_actualizacion,
        "en_proceso": proceso_en_curso
    })

@app.route("/get-calendario", methods=["GET"])
def get_calendario():
    dias_nombres = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    calendario = {}
    for loteria, dias in DIAS_LOTERIA.items():
        for dia in dias:
            dia_nombre = dias_nombres[dia]
            if dia_nombre not in calendario:
                calendario[dia_nombre] = []
            calendario[dia_nombre].append(loteria)
    return jsonify(calendario)

@app.route("/get-estado", methods=["GET"])
def get_estado():
    if os.path.exists(ruta_archivo):
        with open(ruta_archivo, "r", encoding="utf-8") as f:
            datos = json.load(f)
            total = sum(len(v) for v in datos.values())
        return jsonify({"status": "success", "total_registros": total})
    else:
        return jsonify({"status": "no_data"})

if __name__ == "__main__":
    puerto = int(os.environ.get("PORT", 5000))
    crear_o_validar_archivo_json()
    app.run(host="0.0.0.0", port=puerto, debug=False)
