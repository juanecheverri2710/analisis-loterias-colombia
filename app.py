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
import socket
import time
import warnings
from scipy import stats

# ⚠️ NO DESACTIVES WARNINGS DE SSL - RESUELVE EL PROBLEMA
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

# Configuración para requests (SIN verify=False)
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

# ==================== SCRAPING DE LOTERÍAS ====================

def obtener_resultados_loteria_tabla(nombre, url, reintentos=3):
    """Obtiene resultados con reintentos y manejo robusto de errores"""
    resultados = []
    
    for intento in range(reintentos):
        try:
            # ✅ Usar verify=True (verificación SSL activa)
            response = SESSION.get(
                url, 
                timeout=15,
                verify=True  # ✅ VERIFICACIÓN SSL ACTIVADA
            )
            
            if response.status_code != 200:
                print(f"⚠️ {nombre}: Error HTTP {response.status_code}")
                if intento < reintentos - 1:
                    print(f"   Reintentando ({intento + 1}/{reintentos})...")
                    time.sleep(2 ** intento)  # Exponential backoff
                    continue
                return resultados
            
            soup = BeautifulSoup(response.text, "html.parser")
            tablas = soup.find_all("table")
            tabla_deseada = None
            
            for tabla in tablas:
                encabezados = [th.text.strip() for th in tabla.find_all("th")]
                if "# Sorteo" in encabezados and "Fecha" in encabezados and "Resultado" in encabezados:
                    tabla_deseada = tabla
                    break
            
            if tabla_deseada is None:
                print(f"⚠️ {nombre}: Tabla no encontrada")
                return resultados
            
            filas = tabla_deseada.find_all("tr")[1:]
            fecha_limite = datetime.now() - timedelta(days=1825)
            
            for fila in filas:
                try:
                    celdas = fila.find_all("td")
                    if len(celdas) >= 3:
                        fecha_texto = celdas[1].text.strip()
                        fecha = validar_fecha(fecha_texto)
                        
                        if fecha is None or fecha < fecha_limite:
                            continue
                        
                        numero = celdas[2].text.strip()
                        serie = "No disponible"
                        
                        if "serie" in numero.lower():
                            partes = numero.lower().split("serie")
                            numero = partes[0].strip()
                            serie = partes[1].strip()
                        
                        # ✅ Normalizar números a enteros
                        numero_limpio = str(int(numero.lstrip('0') or '0')).zfill(4)
                        
                        resultados.append({
                            "numero": numero_limpio,
                            "serie": serie,
                            "fecha": fecha.strftime("%Y-%m-%d")
                        })
                except Exception as e:
                    continue
            
            print(f"✅ {nombre}: {len(resultados)} resultados")
            return resultados
            
        except requests.exceptions.Timeout as e:
            print(f"⚠️ {nombre}: Timeout ({intento + 1}/{reintentos})")
            if intento < reintentos - 1:
                time.sleep(2 ** intento)
        except requests.exceptions.SSLError as e:
            print(f"⚠️ {nombre}: Error SSL - {str(e)}")
            return resultados
        except requests.exceptions.RequestException as e:
            print(f"⚠️ {nombre}: Error de conexión - {str(e)}")
            if intento < reintentos - 1:
                time.sleep(2 ** intento)
        except Exception as e:
            print(f"❌ {nombre}: Error inesperado - {str(e)}")
            return resultados
    
    return resultados

def obtener_todas_loterias():
    """Obtiene resultados de todas las loterías"""
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
    
    resultados_totales = {}
    for nombre, url in loterias_urls.items():
        print(f"🔄 Consultando {nombre}...")
        resultados = obtener_resultados_loteria_tabla(nombre, url)
        resultados_totales[nombre] = resultados
    
    return resultados_totales

def obtener_historico_completo_5anos():
    """Obtiene el histórico completo de los últimos 5 años de todas las loterías"""
    print("\n" + "="*100)
    print("📅 CONSULTANDO HISTÓRICO COMPLETO - ÚLTIMOS 5 AÑOS")
    print("="*100)
    
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
    
    historico_completo = {}
    total_loterias = len(loterias_urls)
    contador = 0
    
    for nombre, url in loterias_urls.items():
        contador += 1
        print(f"\n[{contador}/{total_loterias}] 📥 Consultando {nombre}...")
        
        try:
            # ✅ VERIFY=TRUE
            response = SESSION.get(url, timeout=15, verify=True)
            
            if response.status_code != 200:
                print(f" ⚠️ Error HTTP {response.status_code}")
                historico_completo[nombre] = []
                continue
            
            soup = BeautifulSoup(response.text, "html.parser")
            tablas = soup.find_all("table")
            tabla_deseada = None
            
            for tabla in tablas:
                encabezados = [th.text.strip() for th in tabla.find_all("th")]
                if "# Sorteo" in encabezados and "Fecha" in encabezados and "Resultado" in encabezados:
                    tabla_deseada = tabla
                    break
            
            if tabla_deseada is None:
                print(f" ⚠️ Tabla no encontrada")
                historico_completo[nombre] = []
                continue
            
            filas = tabla_deseada.find_all("tr")[1:]
            fecha_limite = datetime.now() - timedelta(days=1825)
            resultados_loteria = []
            
            for fila in filas:
                try:
                    celdas = fila.find_all("td")
                    if len(celdas) >= 3:
                        fecha_texto = celdas[1].text.strip()
                        fecha = validar_fecha(fecha_texto)
                        
                        if fecha is None or fecha < fecha_limite:
                            continue
                        
                        numero = celdas[2].text.strip()
                        serie = "No disponible"
                        
                        if "serie" in numero.lower():
                            partes = numero.lower().split("serie")
                            numero = partes[0].strip()
                            serie = partes[1].strip()
                        
                        numero_limpio = str(int(numero.lstrip('0') or '0')).zfill(4)
                        
                        resultados_loteria.append({
                            "numero": numero_limpio,
                            "serie": serie,
                            "fecha": fecha.strftime("%Y-%m-%d")
                        })
                except Exception as e:
                    continue
            
            resultados_loteria.sort(key=lambda x: x["fecha"], reverse=True)
            historico_completo[nombre] = resultados_loteria
            print(f" ✅ {len(resultados_loteria)} registros obtenidos")
            time.sleep(1)
            
        except requests.exceptions.SSLError as e:
            print(f" ❌ Error SSL: {str(e)}")
            historico_completo[nombre] = []
        except Exception as e:
            print(f" ❌ Error: {str(e)}")
            historico_completo[nombre] = []
    
    print("\n" + "="*100)
    print("✅ CONSULTA HISTÓRICA COMPLETADA")
    print("="*100)
    
    total_registros = 0
    for loteria, registros in historico_completo.items():
        cantidad = len(registros)
        total_registros += cantidad
        print(f" {loteria:20s}: {cantidad:6d} registros")
    
    return historico_completo

def guardar_historico_json(historico):
    """Guarda el histórico en el archivo JSON"""
    try:
        print("\n💾 Guardando histórico en archivo JSON...")
        with open(ruta_archivo, "w", encoding="utf-8") as f:
            json.dump(historico, f, indent=2, ensure_ascii=False)
        copiar_json_a_static()
        print("✅ Histórico guardado exitosamente")
        return True
    except Exception as e:
        print(f"❌ Error guardando histórico: {str(e)}")
        return False

# ==================== PROCESAMIENTO DE DATOS ====================

def combinar_resultados_acumulativo(historico, nuevos):
    """Combina datos históricos con nuevos resultados sin duplicados"""
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
        
        print(f"✅ Datos del último sorteo cargados: {len(datos_ultimo_sorteo)} loterías")
        return True
    except Exception as e:
        print(f"⚠️ Error cargando datos: {str(e)}")
        return False

def generar_predicciones_diarias():
    """Genera predicciones de números ganadores según el día de hoy"""
    global predicciones_diarias
    try:
        with open(ruta_archivo, 'r', encoding='utf-8') as f:
            datos = json.load(f)
        
        hoy = datetime.now()
        hoy_dia = hoy.weekday()
        dias_nombres = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
        
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
                        numero_predicho = top_numeros[0][0]
                        
                        predicciones_diarias[loteria] = {
                            "numero": numero_predicho,
                            "frecuencia": top_numeros[0][1]
                        }
                        print(f"🎯 {loteria}: {numero_predicho} - {top_numeros[0][1]} apariciones")
        
        print(f"✅ Predicciones generadas para HOY ({dias_nombres[hoy_dia]})")
        print(f" Loterías que juegan hoy: {len(predicciones_diarias)}")
    except Exception as e:
        print(f"⚠️ Error generando predicciones: {str(e)}")

def analizar_numeros_especiales_probabilidad():
    """Análisis detallado de probabilidad para números especiales"""
    global analisis_numeros_especiales
    try:
        with open(ruta_archivo, 'r', encoding='utf-8') as f:
            datos = json.load(f)
        
        hoy = datetime.now()
        fecha_limite_1ano = hoy - timedelta(days=365)
        fecha_limite_2anos = hoy - timedelta(days=730)
        fecha_limite_3anos = hoy - timedelta(days=1095)
        
        analisis_numeros_especiales = {}
        
        print("\n" + "="*100)
        print("🎯 ANÁLISIS DE PROBABILIDAD - NÚMEROS ESPECIALES")
        print("="*100)
        
        for numero_especial in NUMEROS_ESPECIALES:
            print(f"\n{'='*100}")
            print(f"📊 NÚMERO: {numero_especial}")
            print(f"{'='*100}")
            
            numero_info = {
                "numero": numero_especial,
                "apariciones_total": 0,
                "apariciones_1ano": 0,
                "apariciones_2anos": 0,
                "apariciones_3anos": 0,
                "loterrias_donde_cayo": {},
                "frecuencia_por_loteria": {},
                "probabilidad": 0,
                "ultimas_fechas": [],
                "dias_entre_apariciones": [],
                "proxima_prediccion": ""
            }
            
            for loteria, sorteos in datos.items():
                apariciones_loteria = []
                fechas_loteria = []
                
                for sorteo in sorteos:
                    numero_sorteo = str(sorteo.get("numero", "0")).strip().zfill(4)
                    numero_check = str(int(numero_especial.lstrip('0') or '0')).zfill(4)
                    
                    if numero_sorteo == numero_check:
                        fecha_str = sorteo.get("fecha", "")
                        fecha_obj = validar_fecha(fecha_str)
                        
                        if fecha_obj:
                            numero_info["apariciones_total"] += 1
                            apariciones_loteria.append(fecha_obj)
                            fechas_loteria.append(fecha_str)
                            
                            if fecha_obj >= fecha_limite_1ano:
                                numero_info["apariciones_1ano"] += 1
                            if fecha_obj >= fecha_limite_2anos:
                                numero_info["apariciones_2anos"] += 1
                            if fecha_obj >= fecha_limite_3anos:
                                numero_info["apariciones_3anos"] += 1
                
                if apariciones_loteria:
                    numero_info["loterrias_donde_cayo"][loteria] = len(apariciones_loteria)
                    numero_info["frecuencia_por_loteria"][loteria] = {
                        "veces": len(apariciones_loteria),
                        "ultimas_fechas": sorted(fechas_loteria, reverse=True)[:3]
                    }
            
            apariciones_total = numero_info["apariciones_total"]
            
            if apariciones_total > 0:
                frecuencia_anual = (apariciones_total / 5)
                numero_info["probabilidad"] = min(100, (frecuencia_anual / 16) * 100)
            
            todas_fechas = []
            for loteria, sorteos in datos.items():
                for sorteo in sorteos:
                    numero_sorteo = str(sorteo.get("numero", "0")).strip().zfill(4)
                    numero_check = str(int(numero_especial.lstrip('0') or '0')).zfill(4)
                    
                    if numero_sorteo == numero_check:
                        fecha_str = sorteo.get("fecha", "")
                        fecha_obj = validar_fecha(fecha_str)
                        if fecha_obj:
                            todas_fechas.append((fecha_obj, loteria))
            
            todas_fechas.sort(reverse=True)
            numero_info["ultimas_fechas"] = [(f.strftime("%Y-%m-%d"), l) for f, l in todas_fechas[:5]]
            
            if len(todas_fechas) > 1:
                dias_lista = []
                for i in range(len(todas_fechas) - 1):
                    dias = (todas_fechas[i][0] - todas_fechas[i+1][0]).days
                    if dias > 0:
                        dias_lista.append(dias)
                
                if dias_lista:
                    promedio_dias = int(np.mean(dias_lista))
                    numero_info["dias_entre_apariciones"] = {
                        "promedio": promedio_dias,
                        "minimo": int(np.min(dias_lista)),
                        "maximo": int(np.max(dias_lista))
                    }
                    
                    ultima_fecha = todas_fechas[0][0]
                    proxima_fecha_estimada = ultima_fecha + timedelta(days=promedio_dias)
                    numero_info["proxima_prediccion"] = proxima_fecha_estimada.strftime("%Y-%m-%d")
            
            print(f"\n✅ APARICIONES TOTALES: {apariciones_total}")
            print(f"\n🎰 LOTERÍAS DONDE MÁS HA CAÍDO:")
            print("─" * 100)
            
            sorted_loterias = sorted(numero_info["loterrias_donde_cayo"].items(), key=lambda x: x[1], reverse=True)
            for loteria, veces in sorted_loterias[:5]:
                porcentaje = (veces / apariciones_total) * 100 if apariciones_total > 0 else 0
                barra = "█" * int(porcentaje / 3)
                print(f" {loteria:20s}: {veces:3d}x ({porcentaje:5.1f}%) {barra}")
            
            analisis_numeros_especiales[numero_especial] = numero_info
        
        print("\n" + "="*100)
        print("✅ ANÁLISIS COMPLETADO")
        print("="*100)
    except Exception as e:
        print(f"❌ Error en análisis de números especiales: {str(e)}")

# ==================== PROCESO PRINCIPAL ====================

def ejecutar_scraping_y_analisis():
    global analisis_texto
    try:
        print("\n🔄 Iniciando análisis...")
        crear_o_validar_archivo_json()
        asegurar_carpeta_static()
        
        with lock:
            print("📂 Cargando histórico...")
            historico = cargar_historial(ruta_archivo)
            
            print("🌐 Consultando loterías...")
            nuevos = obtener_todas_loterias()
            
            print("\n🔗 Combinando datos...")
            combinado = combinar_resultados_acumulativo(historico, nuevos)
            
            print("\n💾 Guardando...")
            with open(ruta_archivo, "w", encoding="utf-8") as f:
                json.dump(combinado, f, indent=2, ensure_ascii=False)
            copiar_json_a_static()
            
            generar_datos_ultimo_sorteo()
            generar_predicciones_diarias()
            analizar_numeros_especiales_probabilidad()
        
        analisis_texto = "✅ Análisis completado exitosamente."
        print("\n✅ ¡Análisis completado!")
    except Exception as e:
        analisis_texto = f"Error: {str(e)}"
        print(f"❌ Error: {str(e)}")

# ==================== RUTAS FLASK ====================

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/start-analysis", methods=["POST"])
def start_analysis():
    """Inicia el análisis en un hilo separado"""
    thread = threading.Thread(target=ejecutar_scraping_y_analisis, daemon=True)
    thread.start()
    return jsonify({"message": "Análisis iniciado."})

@app.route("/get-results", methods=["GET"])
def get_results():
    """Devuelve los resultados del análisis"""
    global analisis_texto
    if analisis_texto:
        return jsonify({"result": analisis_texto})
    else:
        return jsonify({"result": "Resultados aún no disponibles."})

@app.route("/get-sorteos", methods=["GET"])
def get_sorteos():
    """Devuelve datos del último sorteo"""
    return jsonify(datos_ultimo_sorteo)

@app.route("/get-predicciones", methods=["GET"])
def get_predicciones():
    """Devuelve predicciones para HOY"""
    return jsonify(predicciones_diarias)

@app.route("/get-analisis-numeros", methods=["GET"])
def get_analisis_numeros():
    """Devuelve análisis de números especiales"""
    return jsonify(analisis_numeros_especiales)

@app.route('/static/<path:filename>')
def static_files(filename):
    """Sirve archivos estáticos"""
    return send_from_directory(carpeta_static, filename)

@app.route("/get-calendario", methods=["GET"])
def get_calendario():
    """Devuelve calendario de loterías"""
    from collections import OrderedDict
    dias_nombres = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    calendario = OrderedDict()
    
    for dia_nombre in dias_nombres:
        calendario[dia_nombre] = []
    
    for loteria, dias in DIAS_LOTERIA.items():
        for dia in dias:
            dia_nombre = dias_nombres[dia]
            calendario[dia_nombre].append(loteria)
    
    return jsonify(dict(calendario))

@app.route("/obtener-historico", methods=["POST"])
def obtener_historico():
    """API para obtener histórico completo de 5 años"""
    try:
        print("\n🔄 API: Iniciando descarga del histórico...")
        historico = obtener_historico_completo_5anos()
        
        if guardar_historico_json(historico):
            generar_datos_ultimo_sorteo()
            generar_predicciones_diarias()
            analizar_numeros_especiales_probabilidad()
            
            total_registros = sum(len(registros) for registros in historico.values())
            return jsonify({
                "status": "success",
                "message": "Histórico descargado y guardado exitosamente",
                "total_loterias": len(historico),
                "total_registros": total_registros,
                "loterias": {k: len(v) for k, v in historico.items()}
            })
        else:
            return jsonify({"status": "error", "message": "Error al guardar histórico"}), 500
    except Exception as e:
        print(f"❌ Error en API: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/get-estado-historico", methods=["GET"])
def get_estado_historico():
    """API para obtener estado del histórico"""
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

# ==================== INICIO DEL SERVIDOR ====================

if __name__ == "__main__":
    puerto = int(os.environ.get("PORT", 5000))
    hostname = socket.gethostname()
    
    try:
        local_ip = socket.gethostbyname(hostname)
    except:
        local_ip = "127.0.0.1"
    
    print("\n" + "="*70)
    print("🚀 SERVIDOR FLASK - ANÁLISIS DE LOTERÍAS COLOMBIA")
    print("="*70)
    print("\n📅 CALENDARIO DE LOTERÍAS:")
    print("─" * 70)
    
    dias_nombres = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    for idx, dia_nombre in enumerate(dias_nombres):
        loterias_hoy = [lot for lot, dias in DIAS_LOTERIA.items() if idx in dias]
        print(f" {dia_nombre:12s}: {', '.join(loterias_hoy)}")
    
    print("\n✅ Ejecutando en HTTPS (Koyeb)") if os.environ.get("ENVIRONMENT") == "production" else print("\n✅ Ejecutando en HTTP")
    print(f"📍 Local: http://localhost:{puerto}")
    print(f"📱 Red: http://{local_ip}:{puerto}")
    print("\n" + "="*70 + "\n")
    
    app.run(host='0.0.0.0', port=puerto, debug=False, use_reloader=False)
