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
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix, precision_recall_curve
from sklearn.preprocessing import StandardScaler
from sklearn.utils.class_weight import compute_class_weight
from xgboost import XGBClassifier
from imblearn.over_sampling import SMOTE
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from collections import OrderedDict
import socket
import time
import warnings
from scipy import stats

warnings.filterwarnings('ignore', message='Unverified HTTPS request')

# ==================== CONFIGURACIÓN ====================
app = Flask(__name__)
app.config['PREFERRED_URL_SCHEME'] = 'https'
app.config['TRUST_REMOTE_ADDR'] = True

# Rutas y variables globales
ruta_archivo = "resultados_loterias.json"
carpeta_static = "static"
archivo_json_static = os.path.join(carpeta_static, ruta_archivo)
analisis_texto = ""
datos_ultimo_sorteo = {}
predicciones_diarias = {}
analisis_numeros_especiales = {}
lock = threading.Lock()
modelo_ia = None
progreso_analisis = {"estado": "inactivo", "mensaje": "", "porcentaje": 0}

# Configuración para requests
SESSION = requests.Session()
SESSION.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
})

# 📅 CALENDARIO ACTUALIZADO DE LOTERÍAS
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

# ⭐ CALENDARIO ORDENADO PARA FRONTEND
calendario = OrderedDict([
    ('Domingo', []),
    ('Lunes', ['Cundinamarca', 'Tolima']),
    ('Martes', ['Cruz Roja', 'Huila']),
    ('Miércoles', ['Manizales', 'Valle', 'Meta']),
    ('Jueves', ['Bogotá', 'Quindío']),
    ('Viernes', ['Medellín', 'Risaralda', 'Santander']),
    ('Sábado', ['Boyacá', 'Cauca'])
])

NUMEROS_ESPECIALES = ["0419", "0116", "2710", "1012", "6888"]


# ==================== FUNCIONES UTILITARIAS ====================

def validar_fecha(fecha_str):
    """Valida y convierte string de fecha a objeto datetime"""
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
        shutil.copy(ruta_archivo, archivo_json_static)

def cargar_historial(ruta):
    """Carga historial con manejo de excepciones específicas"""
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError as e:
        print(f"⚠️ Archivo no encontrado: {e}")
        return {}
    except json.JSONDecodeError as e:
        print(f"⚠️ Error al decodificar JSON: {e}")
        return {}
    except Exception as e:
        print(f"⚠️ Error inesperado: {e}")
        return {}

def actualizar_progreso(estado, mensaje, porcentaje):
    """Actualiza el progreso del análisis"""
    global progreso_analisis
    with lock:
        progreso_analisis = {
            "estado": estado,
            "mensaje": mensaje,
            "porcentaje": min(100, max(0, porcentaje))
        }
    print(f"📊 [{porcentaje}%] {mensaje}")

# ==================== SCRAPING OPTIMIZADO ====================

def obtener_solo_ultimo_resultado(nombre, url, fecha_limite):
    """
    ⚡ OPTIMIZADO: Obtiene SOLO el último resultado si es posterior a fecha_limite.
    """
    try:
        response = SESSION.get(url, timeout=10, verify=True)
        
        if response.status_code != 200:
            print(f"⚠️ {nombre}: Error HTTP {response.status_code}")
            return None

        soup = BeautifulSoup(response.text, "html.parser")
        tablas = soup.find_all("table")
        
        for tabla in tablas:
            encabezados = [th.text.strip() for th in tabla.find_all("th")]
            if "# Sorteo" in encabezados and "Fecha" in encabezados and "Resultado" in encabezados:
                filas = tabla.find_all("tr")[1:2]
                
                if filas:
                    celdas = filas[0].find_all("td")
                    if len(celdas) >= 3:
                        fecha_texto = celdas[1].text.strip()
                        fecha = validar_fecha(fecha_texto)
                        
                        if fecha and fecha > fecha_limite:
                            numero = celdas[2].text.strip()
                            serie = "No disponible"
                            
                            if "serie" in numero.lower():
                                partes = numero.lower().split("serie")
                                numero = partes[0].strip()
                                serie = partes[1].strip()
                            
                            numero_limpio = str(int(numero.lstrip('0') or '0')).zfill(4)
                            
                            print(f"✅ {nombre}: Nuevo {numero_limpio} ({fecha.strftime('%Y-%m-%d')})")
                            return {
                                "numero": numero_limpio,
                                "serie": serie,
                                "fecha": fecha.strftime("%Y-%m-%d")
                            }
                        else:
                            print(f"ℹ️ {nombre}: Sin actualizaciones")
                            return None
                
        print(f"⚠️ {nombre}: Tabla no encontrada")
        return None
        
    except Exception as e:
        print(f"❌ {nombre}: Error - {str(e)}")
        return None


def obtener_actualizaciones_recientes():
    """⚡ OPTIMIZADO: Obtiene SOLO los resultados nuevos"""
    loterias_urls = {
        "Boyacá": "https://resultadodelaloteria.com/colombia/loteria-de-boyaca",
        "Cruz Roja": "https://resultadodelaloteria.com/colombia/loteria-de-la-cruz-roja",
        "Manizales": "https://resultadodelaloteria.com/colombia/loteria-de-manizales",
        "Cundinamarca": "https://resultadodelaloteria.com/colombia/loteria-de-cundinamarca",
        "Tolima": "https://resultadodelaloteria.com/colombia/loteria-del-tolima",
        "Medellín": "https://resultadodelaloteria.com/colombia/loteria-de-medellin",
        "Santander": "https://resultadodelaloteria.com/colombia/loteria-de-santander",
        "Huila": "https://resultadodelaloteria.com/colombia/loteria-del-huila",
        "Risaralda": "https://resultadodelaloteria.com/colombia/loteria-de-risaralda",
        "Bogotá": "https://resultadodelaloteria.com/colombia/loteria-de-bogota",
        "Meta": "https://resultadodelaloteria.com/colombia/loteria-del-meta",
        "Quindío": "https://resultadodelaloteria.com/colombia/loteria-del-quindio",
        "Valle": "https://resultadodelaloteria.com/colombia/loteria-del-valle",
        "Cauca": "https://resultadodelaloteria.com/colombia/loteria-del-cauca"
    }
    
    print("\n📅 Verificando actualizaciones...")
    actualizar_progreso("procesando", "Verificando actualizaciones...", 10)
    
    historico = cargar_historial(ruta_archivo)
    fechas_limite = {}
    
    for loteria, sorteos in historico.items():
        if sorteos and len(sorteos) > 0:
            fecha_str = sorteos[0].get("fecha", "")
            fecha_obj = validar_fecha(fecha_str)
            if fecha_obj:
                fechas_limite[loteria] = fecha_obj
            else:
                fechas_limite[loteria] = datetime.now() - timedelta(days=30)
        else:
            fechas_limite[loteria] = datetime.now() - timedelta(days=30)
    
    actualizaciones = {}
    tiempo_inicio = time.time()
    contador = 0
    total_loterias = len(loterias_urls)
    
    try:
        with ThreadPoolExecutor(max_workers=5) as executor:
            futuros = {
                executor.submit(
                    obtener_solo_ultimo_resultado, 
                    nombre, 
                    url, 
                    fechas_limite.get(nombre, datetime.now() - timedelta(days=7))
                ): nombre 
                for nombre, url in loterias_urls.items()
            }
            
            for futuro in as_completed(futuros, timeout=60):
                nombre = futuros[futuro]
                contador += 1
                try:
                    resultado = futuro.result(timeout=3)
                    if resultado:
                        actualizaciones[nombre] = [resultado]
                    else:
                        actualizaciones[nombre] = []
                    
                    porcentaje = 10 + int((contador / total_loterias) * 40)
                    actualizar_progreso("procesando", f"Verificado {contador}/{total_loterias}", porcentaje)
                    
                except Exception as e:
                    print(f"⚠️ {nombre}: Error - {str(e)}")
                    actualizaciones[nombre] = []
                    
    except TimeoutError:
        print("⚠️ Timeout en algunas loterías")
    
    tiempo_total = time.time() - tiempo_inicio
    total_nuevos = sum(len(v) for v in actualizaciones.values())
    
    print(f"\n⏱️ Completado en {tiempo_total:.2f}s - {total_nuevos} nuevos")
    return actualizaciones

# ==================== PROCESAMIENTO DE DATOS ====================

def combinar_resultados_acumulativo(historico, nuevos):
    """Combina datos históricos con nuevos resultados sin duplicados"""
    actualizar_progreso("procesando", "Combinando datos...", 65)

    dfs = []

    for lot, res in historico.items():
        if res:
            df_temp = pd.DataFrame(res)
            df_temp["loteria"] = lot
            dfs.append(df_temp)

    for lot, res in nuevos.items():
        if res:
            df_temp = pd.DataFrame(res)
            df_temp["loteria"] = lot
            dfs.append(df_temp)

    if dfs:
        df_combinado = pd.concat(dfs, ignore_index=True)
    else:
        df_combinado = pd.DataFrame(columns=["numero", "serie", "fecha", "loteria"])

    df_combinado["fecha"] = pd.to_datetime(df_combinado["fecha"])
    df_combinado = df_combinado.sort_values('fecha', ascending=False)
    df_combinado.drop_duplicates(subset=["loteria", "fecha", "numero"], inplace=True, keep='first')

    resultado_final = {}
    for lot in df_combinado["loteria"].unique():
        df_loteria = df_combinado[df_combinado["loteria"] == lot].copy()
        df_loteria["fecha"] = df_loteria["fecha"].dt.strftime("%Y-%m-%d")
        resultado_final[lot] = df_loteria[["numero", "serie", "fecha"]].to_dict(orient="records")

    return resultado_final

def generar_datos_ultimo_sorteo():
    """Genera datos del último sorteo de cada lotería"""
    global datos_ultimo_sorteo
    try:
        actualizar_progreso("analizando", "Generando datos...", 85)
        with open(ruta_archivo, 'r', encoding='utf-8') as f:
            datos = json.load(f)

        datos_ultimo_sorteo = {}
        for loteria, sorteos in datos.items():
            if sorteos and len(sorteos) > 0:
                ultimo = sorteos[0]
                datos_ultimo_sorteo[loteria] = {
                    "numero": str(ultimo.get("numero", "N/A")).zfill(4),
                    "signo": str(ultimo.get("serie", "N/A")),
                    "fecha": str(ultimo.get("fecha", "N/A"))
                }

        print(f"✅ Últimos sorteos: {len(datos_ultimo_sorteo)} loterías")
        return True
    except Exception as e:
        print(f"⚠️ Error: {str(e)}")
        return False

def generar_predicciones_diarias():
    """Genera predicciones según el día de hoy"""
    global predicciones_diarias
    try:
        with open(ruta_archivo, 'r', encoding='utf-8') as f:
            datos = json.load(f)

        hoy = datetime.now()
        hoy_dia = hoy.weekday()

        predicciones_diarias = {}

        for loteria, sorteos in datos.items():
            if loteria in DIAS_LOTERIA and hoy_dia in DIAS_LOTERIA[loteria]:
                if sorteos and len(sorteos) > 0:
                    sorteos_recientes = sorteos[:10]
                    numeros_freq = {}

                    for sorteo in sorteos_recientes:
                        num = str(sorteo.get("numero", "0")).strip().zfill(4)
                        numeros_freq[num] = numeros_freq.get(num, 0) + 1

                    if numeros_freq:
                        top_numeros = sorted(numeros_freq.items(), key=lambda x: x[1], reverse=True)
                        predicciones_diarias[loteria] = {
                            "numero": top_numeros[0][0],
                            "frecuencia": top_numeros[0][1]
                        }

        print(f"✅ Predicciones: {len(predicciones_diarias)} loterías")
    except Exception as e:
        print(f"⚠️ Error: {str(e)}")

def analizar_numeros_especiales_probabilidad():
    """Análisis de números especiales"""
    global analisis_numeros_especiales
    try:
        actualizar_progreso("analizando", "Analizando números...", 90)
        with open(ruta_archivo, 'r', encoding='utf-8') as f:
            datos = json.load(f)

        hoy = datetime.now()
        fecha_limite_1ano = hoy - timedelta(days=365)

        analisis_numeros_especiales = {}

        for numero_especial in NUMEROS_ESPECIALES:
            numero_info = {
                "numero": numero_especial,
                "apariciones_total": 0,
                "apariciones_1ano": 0,
                "loterrias_donde_cayo": {},
                "probabilidad": 0,
                "ultimas_fechas": [],
                "proxima_prediccion": ""
            }

            for loteria, sorteos in datos.items():
                for sorteo in sorteos:
                    numero_sorteo = str(sorteo.get("numero", "0")).strip().zfill(4)
                    numero_check = str(int(numero_especial.lstrip('0') or '0')).zfill(4)

                    if numero_sorteo == numero_check:
                        fecha_str = sorteo.get("fecha", "")
                        fecha_obj = validar_fecha(fecha_str)

                        if fecha_obj:
                            numero_info["apariciones_total"] += 1
                            if fecha_obj >= fecha_limite_1ano:
                                numero_info["apariciones_1ano"] += 1
                            
                            numero_info["loterrias_donde_cayo"][loteria] = \
                                numero_info["loterrias_donde_cayo"].get(loteria, 0) + 1

            if numero_info["apariciones_total"] > 0:
                numero_info["probabilidad"] = min(100, (numero_info["apariciones_total"] / 5 / 16) * 100)

            analisis_numeros_especiales[numero_especial] = numero_info

        print("✅ Análisis completado")
    except Exception as e:
        print(f"❌ Error: {str(e)}")

def ejecutar_scraping_y_analisis():
    """⚡ VERSIÓN OPTIMIZADA"""
    global analisis_texto
    try:
        print("\n🔄 Iniciando...")
        crear_o_validar_archivo_json()
        asegurar_carpeta_static()

        actualizar_progreso("procesando", "Cargando...", 5)

        with lock:
            historico = cargar_historial(ruta_archivo)
            
            if historico:
                total = sum(len(v) for v in historico.values())
                print(f"✅ Histórico: {total} registros")

            actualizaciones = obtener_actualizaciones_recientes()
            total_nuevos = sum(len(v) for v in actualizaciones.values())
            
            if total_nuevos > 0:
                print(f"✅ {total_nuevos} nuevos")
                actualizar_progreso("procesando", f"{total_nuevos} nuevos...", 60)
                combinado = combinar_resultados_acumulativo(historico, actualizaciones)
            else:
                print("✅ Sin actualizaciones")
                actualizar_progreso("procesando", "Sin actualizaciones", 60)
                combinado = historico

            actualizar_progreso("guardando", "Guardando...", 70)
            with open(ruta_archivo, "w", encoding="utf-8") as f:
                json.dump(combinado, f, indent=2, ensure_ascii=False)
            copiar_json_a_static()

            generar_datos_ultimo_sorteo()
            generar_predicciones_diarias()
            analizar_numeros_especiales_probabilidad()

        analisis_texto = f"✅ Completado. {total_nuevos} actualizaciones."
        actualizar_progreso("completado", "✅ ¡Completado!", 100)
        print(f"✅ [100%] COMPLETO - {total_nuevos} nuevos")
        
    except Exception as e:
        analisis_texto = f"Error: {str(e)}"
        actualizar_progreso("error", str(e), 0)
        print(f"❌ Error: {str(e)}")

# ==================== RUTAS FLASK ====================

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/start-analysis", methods=["POST"])
def start_analysis():
    thread = threading.Thread(target=ejecutar_scraping_y_analisis, daemon=True)
    thread.start()
    return jsonify({"message": "Análisis iniciado."})

@app.route("/get-results", methods=["GET"])
def get_results():
    global analisis_texto
    if analisis_texto:
        return jsonify({"result": analisis_texto})
    else:
        return jsonify({"result": "Resultados aún no disponibles."})

@app.route("/get-progreso", methods=["GET"])
def get_progreso():
    with lock:
        return jsonify(progreso_analisis)

@app.route("/get-sorteos", methods=["GET"])
def get_sorteos():
    return jsonify(datos_ultimo_sorteo)

@app.route("/get-predicciones", methods=["GET"])
def get_predicciones():
    return jsonify(predicciones_diarias)

@app.route("/get-analisis-numeros", methods=["GET"])
def get_analisis_numeros():
    return jsonify(analisis_numeros_especiales)

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory(carpeta_static, filename)

@app.route('/get-calendario', methods=['GET'])
def get_calendario():
    return jsonify(calendario)

@app.route("/get-estado-historico", methods=["GET"])
def get_estado_historico():
    try:
        if os.path.exists(ruta_archivo):
            with open(ruta_archivo, 'r', encoding='utf-8') as f:
                datos = json.load(f)

            total_registros = sum(len(registros) for registros in datos.values())

            todas_fechas = []
            for sorteos in datos.values():
                for sorteo in sorteos:
                    fecha_str = sorteo.get("fecha", "")
                    if fecha_str:
                        fecha_obj = validar_fecha(fecha_str)
                        if fecha_obj:
                            todas_fechas.append(fecha_obj)

            fecha_mas_antigua = min(todas_fechas).strftime("%Y-%m-%d") if todas_fechas else "N/A"
            fecha_mas_reciente = max(todas_fechas).strftime("%Y-%m-%d") if todas_fechas else "N/A"

            return jsonify({
                "status": "success",
                "tiene_datos": True,
                "total_loterias": len(datos),
                "total_registros": total_registros,
                "fecha_mas_antigua": fecha_mas_antigua,
                "fecha_mas_reciente": fecha_mas_reciente,
                "loterias": {k: len(v) for k, v in datos.items()}
            })
        else:
            return jsonify({"status": "success", "tiene_datos": False, "message": "No hay datos aún"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/descargar-json", methods=["GET"])
def descargar_json():
    """Permite descargar el archivo JSON con todo el histórico"""
    try:
        if os.path.exists(ruta_archivo):
            return send_from_directory(
                directory=os.getcwd(),
                path=ruta_archivo,
                as_attachment=True,
                download_name=f"resultados_loterias_{datetime.now().strftime('%Y%m%d')}.json"
            )
        else:
            return jsonify({"error": "Archivo no encontrado"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==================== INICIO DEL SERVIDOR ====================

if __name__ == "__main__":
    puerto = int(os.environ.get("PORT", 5000))
    hostname = socket.gethostname()

    try:
        local_ip = socket.gethostbyname(hostname)
    except:
        local_ip = "127.0.0.1"

    print("\n" + "="*70)
    print("🚀 ANÁLISIS DE LOTERÍAS COLOMBIA - OPTIMIZADO")
    print("="*70)
    print("\n⚡ OPTIMIZACIONES:")
    print("  ✅ Solo busca actualizaciones nuevas")
    print("  ✅ Timeout 60s")
    print("  ✅ Calendario ordenado")
    print(f"\n📍 Puerto: {puerto}")
    print("="*70 + "\n")

    app.run(host='0.0.0.0', port=puerto, debug=False, use_reloader=False, threaded=True)
