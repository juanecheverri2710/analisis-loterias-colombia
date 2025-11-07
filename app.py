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
import urllib3
import socket
import time
import warnings

warnings.filterwarnings('ignore')

# ==================== CONFIGURACIÓN ====================
app = Flask(__name__)
app.config['PREFERRED_URL_SCHEME'] = 'https'
app.config['TRUST_REMOTE_ADDR'] = True

# Rutas y variables globales
ruta_archivo = "resultados_loterias.json"
ruta_cache = "cache_loterias.json"
carpeta_static = "static"
archivo_json_static = os.path.join(carpeta_static, ruta_archivo)

# Variables globales con caché
datos_ultimo_sorteo = {}
predicciones_diarias = {}
analisis_numeros_especiales = {}
tiempo_ultima_actualizacion = None
proceso_en_curso = False
lock = threading.Lock()

# Números especiales a analizar
NUMEROS_ESPECIALES = ["0419", "0116", "2710", "1012", "6888"]

DIAS_LOTERIA = {
    "Astro Luna": [0, 1, 2, 3, 4, 5, 6],
    "Astro Sol": [0, 1, 2, 3, 4, 5, 6],
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

def cargar_historico_local():
    """Carga el histórico desde el archivo local (MÁS RÁPIDO)"""
    try:
        with open(ruta_archivo, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def cargar_cache():
    """Carga el caché para mostrar datos anteriores al usuario mientras se actualiza"""
    try:
        with open(ruta_cache, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def guardar_cache(datos):
    """Guarda datos en caché para acceso rápido"""
    try:
        with open(ruta_cache, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False)
    except:
        pass

# ==================== SCRAPING PARALELO ====================

def obtener_resultados_loteria_tabla(nombre, url):
    """Obtiene resultados de una lotería (con timeout reducido)"""
    resultados = []
    try:
        response = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=8,  # Reducido de 10 a 8 segundos
            verify=False
        )
        if response.status_code != 200:
            return resultados
        
        soup = BeautifulSoup(response.text, "html.parser")
        tablas = soup.find_all("table", limit=5)  # Limitar búsqueda
        
        for tabla in tablas:
            encabezados = [th.text.strip() for th in tabla.find_all("th", limit=10)]
            if "# Sorteo" in encabezados and "Fecha" in encabezados and "Resultado" in encabezados:
                filas = tabla.find_all("tr")[1:50]  # Limitar a últimos 50 sorteos
                fecha_limite = datetime.now() - timedelta(days=1825)
                
                for fila in filas:
                    try:
                        celdas = fila.find_all("td", limit=4)
                        if len(celdas) >= 3:
                            fecha_texto = celdas[1].text.strip()
                            fecha = validar_fecha(fecha_texto)
                            
                            if fecha is None or fecha < fecha_limite:
                                continue
                            
                            numero = celdas[2].text.strip().split()[0]
                            serie = "No disponible"
                            
                            resultados.append({
                                "numero": numero.zfill(4),
                                "serie": serie,
                                "fecha": fecha.strftime("%Y-%m-%d")
                            })
                    except:
                        pass
                break
        
        return resultados
    
    except Exception as e:
        return resultados

def obtener_resultados_superastro_rapido(tipo_loteria, fecha_inicio):
    """Versión rápida de Astro Sol/Luna - solo últimos 30 registros"""
    resultados = []
    try:
        url = "https://superastro.com.co/historico.php"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Referer': 'https://superastro.com.co/'
        }
        
        if tipo_loteria.lower() == 'sol':
            payload = {'fecha_sol': fecha_inicio}
            id_tabla = 'home'
        elif tipo_loteria.lower() == 'luna':
            payload = {'fecha_luna': fecha_inicio}
            id_tabla = 'profile'
        else:
            return resultados
        
        response = requests.post(url, data=payload, headers=headers, timeout=10, verify=False)
        
        if response.status_code != 200:
            return resultados
        
        soup = BeautifulSoup(response.text, 'html.parser')
        tab_content = soup.find('div', {'id': id_tabla})
        
        if not tab_content:
            return resultados
        
        tabla = tab_content.find('table')
        if not tabla:
            return resultados
        
        tbody = tabla.find('tbody')
        if not tbody:
            return resultados
        
        filas = tbody.find_all('tr', limit=30)  # Solo últimos 30
        fecha_limite = datetime.now() - timedelta(days=1825)
        
        for fila in filas:
            try:
                celdas = fila.find_all('td', limit=4)
                if len(celdas) >= 4:
                    fecha_str = celdas[0].get_text(strip=True)
                    numero = celdas[1].get_text(strip=True)
                    signo = celdas[2].get_text(strip=True).lower()
                    
                    fecha_obj = validar_fecha(fecha_str)
                    if fecha_obj is None or fecha_obj < fecha_limite:
                        continue
                    
                    numero_limpio = numero.replace(' ', '')
                    if numero_limpio.isdigit() and len(numero_limpio) == 4:
                        resultados.append({
                            "numero": numero_limpio.zfill(4),
                            "serie": signo,
                            "fecha": fecha_obj.strftime('%Y-%m-%d')
                        })
            except:
                pass
        
        return resultados
    
    except Exception as e:
        return resultados

def obtener_historico_paralelo():
    """Obtiene todas las loterías EN PARALELO (mucho más rápido)"""
    print("\n⚡ SCRAPING PARALELO - Consultando todas las loterías simultáneamente...")
    
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
    
    # Usar ThreadPoolExecutor para paralelismo
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(obtener_resultados_loteria_tabla, nombre, url): nombre
            for nombre, url in loterias_urls.items()
        }
        
        for future in as_completed(futures):
            nombre = futures[future]
            try:
                resultados = future.result()
                historico_completo[nombre] = resultados
                print(f"✅ {nombre}: {len(resultados)} registros")
            except Exception as e:
                print(f"⚠️ {nombre}: Error")
                historico_completo[nombre] = []
    
    # Astro Luna y Astro Sol en paralelo
    fecha_inicio = (datetime.now() - timedelta(days=1825)).strftime('%Y-%m-%d')
    
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_luna = executor.submit(obtener_resultados_superastro_rapido, 'luna', fecha_inicio)
        future_sol = executor.submit(obtener_resultados_superastro_rapido, 'sol', fecha_inicio)
        
        try:
            historico_completo["Astro Luna"] = future_luna.result()
            print(f"✅ Astro Luna: {len(historico_completo['Astro Luna'])} registros")
        except:
            historico_completo["Astro Luna"] = []
        
        try:
            historico_completo["Astro Sol"] = future_sol.result()
            print(f"✅ Astro Sol: {len(historico_completo['Astro Sol'])} registros")
        except:
            historico_completo["Astro Sol"] = []
    
    print("✅ Scraping paralelo completado\n")
    return historico_completo

def guardar_historico_json(historico):
    """Guarda el histórico en el archivo JSON"""
    try:
        with open(ruta_archivo, "w", encoding="utf-8") as f:
            json.dump(historico, f, indent=2, ensure_ascii=False)
        copiar_json_a_static()
        guardar_cache(historico)  # Guardar en caché también
        return True
    except Exception as e:
        return False

# ==================== GENERACIÓN DE DATOS RÁPIDA ====================

def generar_datos_ultimo_sorteo():
    """Genera datos del último sorteo (RÁPIDO)"""
    global datos_ultimo_sorteo
    try:
        with open(ruta_archivo, 'r', encoding='utf-8') as f:
            datos = json.load(f)
        
        datos_ultimo_sorteo = {}
        for loteria, sorteos in datos.items():
            if sorteos:
                ultimo = sorteos[0]
                datos_ultimo_sorteo[loteria] = {
                    "numero": ultimo.get("numero", "N/A"),
                    "signo": ultimo.get("serie", "N/A"),
                    "fecha": ultimo.get("fecha", "N/A")
                }
    except:
        pass

def generar_predicciones_diarias():
    """Genera predicciones rápidas para hoy"""
    global predicciones_diarias
    try:
        with open(ruta_archivo, 'r', encoding='utf-8') as f:
            datos = json.load(f)
        
        hoy = datetime.now()
        hoy_dia = hoy.weekday()
        
        predicciones_diarias = {}
        
        for loteria, sorteos in datos.items():
            if loteria in DIAS_LOTERIA and hoy_dia in DIAS_LOTERIA[loteria]:
                if sorteos:
                    fecha_limite = hoy - timedelta(days=365)
                    sorteos_validos = []
                    
                    for sorteo in sorteos:
                        fecha_str = sorteo.get("fecha", "")
                        if fecha_str:
                            fecha_obj = validar_fecha(fecha_str)
                            if fecha_obj and fecha_obj >= fecha_limite:
                                sorteos_validos.append(sorteo)
                    
                    if sorteos_validos:
                        numeros_freq = {}
                        for sorteo in sorteos_validos[:30]:  # Solo últimos 30
                            num = sorteo.get("numero", "0").strip().lstrip('0') or "0"
                            numeros_freq[num] = numeros_freq.get(num, 0) + 1
                        
                        top_numeros = sorted(numeros_freq.items(), key=lambda x: x[1], reverse=True)[:5]
                        
                        if top_numeros:
                            numero_predicho = top_numeros[0][0].zfill(4)
                            signo = sorteos_validos[0].get("serie", "No disponible")
                            
                            predicciones_diarias[loteria] = {
                                "numero": numero_predicho,
                                "signo": signo,
                                "confianza": round((top_numeros[0][1] / min(30, len(sorteos_validos))) * 100, 2),
                                "juega_hoy": True,
                                "top_5": [num.zfill(4) for num, _ in top_numeros]
                            }
    except:
        pass

def analizar_numeros_especiales_rapido():
    """Análisis rápido de números especiales (optimizado)"""
    global analisis_numeros_especiales
    try:
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
                "ultimas_fechas": []
            }
            
            todas_fechas = []
            
            for loteria, sorteos in datos.items():
                apariciones_loteria = 0
                
                for sorteo in sorteos[:50]:  # Solo últimos 50 para rapidez
                    numero_sorteo = sorteo.get("numero", "").strip().lstrip('0') or "0"
                    numero_check = numero_especial.lstrip('0') or "0"
                    
                    if numero_sorteo == numero_check:
                        fecha_str = sorteo.get("fecha", "")
                        fecha_obj = validar_fecha(fecha_str)
                        
                        if fecha_obj:
                            numero_info["apariciones_total"] += 1
                            apariciones_loteria += 1
                            
                            if fecha_obj >= fecha_limite_1ano:
                                numero_info["apariciones_1ano"] += 1
                            
                            todas_fechas.append((fecha_obj, loteria))
                
                if apariciones_loteria > 0:
                    numero_info["loterrias_donde_cayo"][loteria] = apariciones_loteria
            
            if numero_info["apariciones_total"] > 0:
                numero_info["probabilidad"] = min(100, (numero_info["apariciones_1ano"] / 365) * 100)
            
            todas_fechas.sort(reverse=True)
            numero_info["ultimas_fechas"] = [(f.strftime("%Y-%m-%d"), l) for f, l in todas_fechas[:5]]
            
            analisis_numeros_especiales[numero_especial] = numero_info
    
    except Exception as e:
        print(f"Error análisis: {str(e)}")

def ejecutar_scraping_y_analisis():
    """Función principal OPTIMIZADA"""
    global proceso_en_curso, tiempo_ultima_actualizacion
    
    with lock:
        if proceso_en_curso:
            return
        proceso_en_curso = True
    
    try:
        print("\n🚀 INICIANDO ACTUALIZACIÓN RÁPIDA...")
        tiempo_inicio = time.time()
        
        # Obtener histórico en paralelo
        historico = obtener_historico_paralelo()
        
        # Guardar
        if guardar_historico_json(historico):
            # Generar datos rápidamente
            generar_datos_ultimo_sorteo()
            generar_predicciones_diarias()
            analizar_numeros_especiales_rapido()
            
            tiempo_final = time.time()
            tiempo_transcurrido = round(tiempo_final - tiempo_inicio, 2)
            
            with lock:
                tiempo_ultima_actualizacion = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            print(f"✅ ACTUALIZACIÓN COMPLETADA EN {tiempo_transcurrido}s")
        else:
            print("❌ Error al guardar")
    
    except Exception as e:
        print(f"❌ Error: {str(e)}")
    
    finally:
        with lock:
            proceso_en_curso = False

# ==================== RUTAS FLASK ====================

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/start-analysis", methods=["POST"])
def start_analysis():
    """Inicia actualización en hilo separado"""
    if not proceso_en_curso:
        thread = threading.Thread(target=ejecutar_scraping_y_analisis, daemon=True)
        thread.start()
        return jsonify({"message": "Actualización iniciada", "status": "running"})
    else:
        return jsonify({"message": "Ya hay una actualización en curso", "status": "already_running"})

@app.route("/get-sorteos", methods=["GET"])
def get_sorteos():
    """Devuelve últimos resultados (caché - RÁPIDO)"""
    if not datos_ultimo_sorteo:
        # Si no hay datos en memoria, cargar del caché
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
    """Devuelve predicciones rápido"""
    return jsonify({
        "data": predicciones_diarias,
        "ultimo_update": tiempo_ultima_actualizacion,
        "en_proceso": proceso_en_curso
    })

@app.route("/get-analisis-numeros", methods=["GET"])
def get_analisis_numeros():
    """Devuelve análisis de números especiales"""
    return jsonify({
        "data": analisis_numeros_especiales,
        "ultimo_update": tiempo_ultima_actualizacion,
        "en_proceso": proceso_en_curso
    })

@app.route("/get-calendario", methods=["GET"])
def get_calendario():
    """Devuelve calendario de loterías"""
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
    """Estado actual del sistema"""
    try:
        if os.path.exists(ruta_archivo):
            with open(ruta_archivo, 'r', encoding='utf-8') as f:
                datos = json.load(f)
            
            total_registros = sum(len(registros) for registros in datos.values())
            
            return jsonify({
                "status": "success",
                "tiene_datos": True,
                "total_loterias": len(datos),
                "total_registros": total_registros,
                "ultimo_update": tiempo_ultima_actualizacion,
                "en_proceso": proceso_en_curso,
                "loterias": {k: len(v) for k, v in datos.items()}
            })
        else:
            return jsonify({
                "status": "success",
                "tiene_datos": False,
                "mensaje": "Sin datos aún"
            })
    
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ==================== INICIO ====================

if __name__ == "__main__":
    puerto = 5000
    
    try:
        local_ip = socket.gethostbyname(socket.gethostname())
    except:
        local_ip = "127.0.0.1"
    
    crear_o_validar_archivo_json()
    generar_datos_ultimo_sorteo()
    generar_predicciones_diarias()
    analizar_numeros_especiales_rapido()
    
    print("\n" + "="*70)
    print("🚀 SERVIDOR FLASK OPTIMIZADO - ANÁLISIS DE LOTERÍAS")
    print("="*70)
    print(f"📍 Local: http://localhost:{puerto}")
    print(f"📱 Red: http://{local_ip}:{puerto}")
    print("="*70 + "\n")
    
    app.run(host='0.0.0.0', port=puerto, debug=False, use_reloader=False)
