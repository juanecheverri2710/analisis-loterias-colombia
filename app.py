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
import urllib3
import socket
import time
import warnings
from scipy import stats

warnings.filterwarnings('ignore')

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

# 📅 CALENDARIO ACTUALIZADO DE LOTERÍAS
# 0=Lunes, 1=Martes, 2=Miércoles, 3=Jueves, 4=Viernes, 5=Sábado, 6=Domingo
DIAS_LOTERIA = {
    "Astro Luna": [0, 1, 2, 3, 4, 5, 6],  # Todos los días
    "Astro Sol": [0, 1, 2, 3, 4, 5, 6],   # Todos los días
    "Cundinamarca": [0],                   # Lunes
    "Tolima": [0],                         # Lunes
    "Cruz Roja": [1],                      # Martes
    "Huila": [1],                          # Martes
    "Manizales": [2],                      # Miércoles ✅ AGREGADO
    "Valle": [2],                          # Miércoles ✅ AGREGADO
    "Meta": [2],                           # Miércoles ✅ AGREGADO
    "Bogotá": [3],                         # Jueves
    "Quindío": [3],                        # Jueves
    "Medellín": [4],                       # Viernes
    "Risaralda": [4],                      # Viernes
    "Santander": [4],                      # Viernes
    "Boyacá": [5],                         # Sábado ✅ AGREGADO
    "Cauca": [5]                           # Sábado ✅ AGREGADO
}

# Números especiales a analizar
NUMEROS_ESPECIALES = ["0419", "0116", "2710", "1012", "6888"]

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

def cargar_historial(ruta):
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

# ==================== SCRAPING DE LOTERÍAS ====================
def obtener_resultados_loteria_tabla(nombre, url):
    """Obtiene resultados de loterías tradicionales desde resultadodelaloteria.com"""
    resultados = []
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10, verify=False)
        if response.status_code != 200:
            print(f"⚠️ {nombre}: Error HTTP {response.status_code}")
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
            return resultados

        filas = tabla_deseada.find_all("tr")[1:]
        fecha_limite = datetime.now() - timedelta(days=1825)

        for fila in filas:
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

                resultados.append({
                    "numero": numero.zfill(4),
                    "serie": serie,
                    "fecha": fecha.strftime("%Y-%m-%d")
                })

        print(f"✅ {nombre}: {len(resultados)} resultados")
        return resultados

    except Exception as e:
        print(f"❌ {nombre}: Error")
        return resultados

def obtener_resultados_superastro_mejorado(tipo_loteria, fecha_inicio, max_intentos=5):
    """Obtiene resultados de Astro Sol y Astro Luna desde superastro.com.co"""
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
            id_tabla_resultados = 'home'
            nombre_loteria = 'Astro Sol'
        elif tipo_loteria.lower() == 'luna':
            payload = {'fecha_luna': fecha_inicio}
            id_tabla_resultados = 'profile'
            nombre_loteria = 'Astro Luna'
        else:
            return resultados

        print(f"🔄 {nombre_loteria}: Consultando últimos 5 años...")

        response = None
        for intento in range(max_intentos):
            try:
                response = requests.post(url, data=payload, headers=headers, timeout=20, verify=False)
                if response.status_code == 200:
                    break
                time.sleep(2)
            except:
                time.sleep(2)

        if not response or response.status_code != 200:
            return resultados

        soup = BeautifulSoup(response.text, 'html.parser')
        tab_content = soup.find('div', {'id': id_tabla_resultados})

        if not tab_content:
            return resultados

        tabla = tab_content.find('table')
        if not tabla:
            return resultados

        tbody = tabla.find('tbody')
        if not tbody:
            return resultados

        filas = tbody.find_all('tr')
        fecha_limite = datetime.now() - timedelta(days=1825)

        for fila in filas:
            celdas = fila.find_all('td')
            if len(celdas) >= 4:
                try:
                    fecha_str = celdas[0].get_text(strip=True)
                    numero = celdas[1].get_text(strip=True)
                    signo = celdas[2].get_text(strip=True).lower()

                    fecha_obj = validar_fecha(fecha_str)
                    if fecha_obj is None:
                        continue

                    if fecha_obj < fecha_limite:
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

        print(f"✅ {nombre_loteria}: {len(resultados)} resultados (5 años)")
        return resultados

    except Exception as e:
        print(f"❌ {tipo_loteria.upper()}: Error")
        return resultados

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

    total_loterias = len(loterias_urls)
    contador = 0
    historico_completo = {}

    for nombre, url in loterias_urls.items():
        contador += 1
        print(f"\n[{contador}/{total_loterias}] 📥 Consultando {nombre}...")
        try:
            response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15, verify=False)
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

                        resultados_loteria.append({
                            "numero": numero.zfill(4),
                            "serie": serie,
                            "fecha": fecha.strftime("%Y-%m-%d")
                        })

                except Exception as e:
                    continue

            resultados_loteria.sort(key=lambda x: x["fecha"], reverse=True)
            historico_completo[nombre] = resultados_loteria

            print(f" ✅ {len(resultados_loteria)} registros obtenidos")
            time.sleep(1)

        except Exception as e:
            print(f" ❌ Error: {str(e)}")
            historico_completo[nombre] = []

    print(f"\n[{total_loterias + 1}/{total_loterias + 2}] 📥 Consultando Astro Luna...")
    fecha_inicio = (datetime.now() - timedelta(days=1825)).strftime('%Y-%m-%d')
    resultados_luna = obtener_resultados_superastro_mejorado('luna', fecha_inicio)
    historico_completo["Astro Luna"] = resultados_luna

    print(f"[{total_loterias + 2}/{total_loterias + 2}] 📥 Consultando Astro Sol...")
    resultados_sol = obtener_resultados_superastro_mejorado('sol', fecha_inicio)
    historico_completo["Astro Sol"] = resultados_sol

    print("\n" + "="*100)
    print("✅ CONSULTA HISTÓRICA COMPLETADA")
    print("="*100)

    print("\n📊 RESUMEN DEL HISTÓRICO:")
    print("─" * 100)

    total_registros = 0

    for loteria, registros in historico_completo.items():
        cantidad = len(registros)
        total_registros += cantidad
        print(f" {loteria:20s}: {cantidad:6d} registros")

    print("─" * 100)
    print(f" {'TOTAL':20s}: {total_registros:6d} registros")

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
def generar_datos_ultimo_sorteo():
    """Genera datos del último sorteo de cada lotería"""
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

        print(f"✅ Datos del último sorteo cargados: {len(datos_ultimo_sorteo)} loterías")

    except Exception as e:
        print(f"⚠️ Error cargando datos: {str(e)}")

# ==================== ANÁLISIS DE NÚMEROS ESPECIALES ====================
def analizar_numeros_especiales_probabilidad():
    """Análisis simplificado de números especiales con predicción"""
    global analisis_numeros_especiales
    try:
        with open(ruta_archivo, 'r', encoding='utf-8') as f:
            datos = json.load(f)

        hoy = datetime.now()
        fecha_limite_1ano = hoy - timedelta(days=365)

        analisis_numeros_especiales = {}

        print("\n" + "="*100)
        print("🎯 ANÁLISIS DE NÚMEROS ESPECIALES - PREDICCIÓN")
        print("="*100)

        for numero_especial in NUMEROS_ESPECIALES:
            print(f"\n{'='*100}")
            print(f"📊 NÚMERO: {numero_especial}")
            print(f"{'='*100}")

            numero_info = {
                "numero": numero_especial,
                "apariciones_total": 0,
                "apariciones_1ano": 0,
                "loteria_favorita": "No disponible",
                "ultima_aparicion": "No disponible",
                "proxima_prediccion": "No disponible"
            }

            # Analizar en todas las loterías
            todas_apariciones = []
            loterrias_donde_cayo = {}

            for loteria, sorteos in datos.items():
                for sorteo in sorteos:
                    numero_sorteo = sorteo.get("numero", "").strip()
                    if not numero_sorteo:
                        numero_sorteo = "0"
                    
                    numero_sorteo_limpio = numero_sorteo.lstrip('0') or "0"
                    numero_especial_limpio = numero_especial.lstrip('0') or "0"

                    if numero_sorteo_limpio == numero_especial_limpio:
                        fecha_str = sorteo.get("fecha", "")
                        fecha_obj = validar_fecha(fecha_str)

                        if fecha_obj:
                            numero_info["apariciones_total"] += 1
                            todas_apariciones.append((fecha_obj, loteria))

                            if fecha_obj >= fecha_limite_1ano:
                                numero_info["apariciones_1ano"] += 1

                            if loteria not in loterrias_donde_cayo:
                                loterrias_donde_cayo[loteria] = 0
                            loterrias_donde_cayo[loteria] += 1

            # Obtener lotería favorita
            if loterrias_donde_cayo:
                loteria_favorita = max(loterrias_donde_cayo, key=loterrias_donde_cayo.get)
                numero_info["loteria_favorita"] = f"{loteria_favorita} ({loterrias_donde_cayo[loteria_favorita]}x)"

            # Última aparición y predicción
            if todas_apariciones:
                todas_apariciones.sort(reverse=True)
                ultima_fecha, ultima_loteria = todas_apariciones[0]
                numero_info["ultima_aparicion"] = f"{ultima_fecha.strftime('%Y-%m-%d')} en {ultima_loteria}"

                # Calcular promedio de días entre apariciones
                if len(todas_apariciones) > 1:
                    dias_lista = []
                    for i in range(len(todas_apariciones) - 1):
                        dias = (todas_apariciones[i][0] - todas_apariciones[i+1][0]).days
                        if dias > 0:
                            dias_lista.append(dias)

                    if dias_lista:
                        promedio_dias = int(np.mean(dias_lista))
                        proxima_fecha = ultima_fecha + timedelta(days=promedio_dias)
                        numero_info["proxima_prediccion"] = proxima_fecha.strftime('%Y-%m-%d')

            print(f"\n✅ APARICIONES: {numero_info['apariciones_total']} veces")
            print(f"   • Último año: {numero_info['apariciones_1ano']} veces")
            print(f"\n🎰 LOTERÍA FAVORITA: {numero_info['loteria_favorita']}")
            print(f"\n📅 ÚLTIMA APARICIÓN: {numero_info['ultima_aparicion']}")
            print(f"\n🎯 PRÓXIMA PREDICCIÓN: {numero_info['proxima_prediccion']}")

            analisis_numeros_especiales[numero_especial] = numero_info

        print("\n" + "="*100)
        print("✅ ANÁLISIS COMPLETADO")
        print("="*100)

    except Exception as e:
        print(f"❌ Error en análisis de números especiales: {str(e)}")
        import traceback
        traceback.print_exc()

def generar_predicciones_diarias():
    """Genera predicciones de números ganadores según el día de hoy"""
    global predicciones_diarias
    try:
        with open(ruta_archivo, 'r', encoding='utf-8') as f:
            datos = json.load(f)

        hoy = datetime.now()
        hoy_dia = hoy.weekday()  # 0=Lunes, 6=Domingo

        dias_nombres = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

        predicciones_diarias = {}

        for loteria, sorteos in datos.items():
            # Verificar si la lotería juega hoy
            if loteria in DIAS_LOTERIA and hoy_dia in DIAS_LOTERIA[loteria]:
                if sorteos:
                    # VALIDAR FECHAS: Filtrar solo sorteos válidos del último año
                    fecha_limite = hoy - timedelta(days=365)
                    sorteos_validos = []

                    for sorteo in sorteos:
                        fecha_str = sorteo.get("fecha", "")
                        if fecha_str:
                            fecha_obj = validar_fecha(fecha_str)
                            if fecha_obj and fecha_obj >= fecha_limite:
                                sorteos_validos.append(sorteo)

                    if sorteos_validos:
                        # Obtener TOP 5 números más frecuentes
                        numeros_freq = {}
                        signos_freq = {}

                        for sorteo in sorteos_validos:
                            num = sorteo.get("numero", "").strip()
                            if not num:
                                num = "0"
                            
                            num_limpio = num.lstrip('0') or "0"
                            signo = sorteo.get("serie", "No disponible")

                            numeros_freq[num_limpio] = numeros_freq.get(num_limpio, 0) + 1

                            # Para Astro Luna y Astro Sol, guardar signos
                            if loteria in ["Astro Luna", "Astro Sol"]:
                                if num_limpio not in signos_freq:
                                    signos_freq[num_limpio] = {}
                                signos_freq[num_limpio][signo] = signos_freq[num_limpio].get(signo, 0) + 1

                        # Ordenar por frecuencia y tomar el más probable
                        top_numeros = sorted(numeros_freq.items(), key=lambda x: x[1], reverse=True)[:5]

                        # Seleccionar el número con mayor frecuencia
                        if top_numeros:
                            numero_predicho = top_numeros[0][0].zfill(4)
                            freq = top_numeros[0][1]

                            # Para Astro Luna y Astro Sol, agregar signo
                            if loteria in ["Astro Luna", "Astro Sol"] and numero_predicho.lstrip('0') or "0" in signos_freq:
                                signo_freq = signos_freq.get(numero_predicho.lstrip('0') or "0", {})
                                if signo_freq:
                                    signo_top = max(signo_freq, key=signo_freq.get)
                                else:
                                    signo_top = "N/A"

                                predicciones_diarias[loteria] = {
                                    "numero": numero_predicho,
                                    "signo": signo_top,
                                    "frecuencia": freq
                                }

                            else:
                                predicciones_diarias[loteria] = {
                                    "numero": numero_predicho,
                                    "signo": "N/A",
                                    "frecuencia": freq
                                }

                            print(f"🎯 {loteria}: {numero_predicho} - {freq} apariciones")

        print(f"\n✅ Predicciones generadas para HOY ({dias_nombres[hoy_dia]})")
        print(f" Loterías que juegan hoy: {len(predicciones_diarias)}")

    except Exception as e:
        print(f"⚠️ Error generando predicciones: {str(e)}")
        import traceback
        traceback.print_exc()

# ==================== RUTAS FLASK ====================
@app.route('/')
def index():
    """Página principal"""
    return render_template('index.html')

@app.route('/api/generar-datos', methods=['POST'])
def generar_datos():
    """Genera datos iniciales y predicciones"""
    try:
        generar_datos_ultimo_sorteo()
        generar_predicciones_diarias()
        analizar_numeros_especiales_probabilidad()

        return jsonify({
            "status": "success",
            "datos_ultimo_sorteo": datos_ultimo_sorteo,
            "predicciones_diarias": predicciones_diarias,
            "numeros_especiales": analisis_numeros_especiales
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/descargar-json', methods=['GET'])
def descargar_json():
    """Descarga el archivo JSON"""
    try:
        if os.path.exists(archivo_json_static):
            return send_from_directory(carpeta_static, ruta_archivo, as_attachment=True)
        else:
            return jsonify({"status": "error", "message": "Archivo no encontrado"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/obtener-historico", methods=["POST"])
def obtener_historico():
    """API para obtener el histórico completo de 5 años y guardarlo en JSON"""
    try:
        print("\n🔄 API: Iniciando descarga del histórico...")
        historico = obtener_historico_completo_5anos()

        # Guardar en el archivo JSON
        if guardar_historico_json(historico):
            # Actualizar las variables globales
            generar_datos_ultimo_sorteo()
            generar_predicciones_diarias()
            analizar_numeros_especiales_probabilidad()

            total_registros = sum(len(registros) for registros in historico.values())

            return jsonify({
                "status": "success",
                "message": f"Histórico descargado y guardado exitosamente",
                "total_loterias": len(historico),
                "total_registros": total_registros,
                "loterias": {k: len(v) for k, v in historico.items()}
            })

        else:
            return jsonify({
                "status": "error",
                "message": "Error al guardar el histórico"
            }), 500

    except Exception as e:
        print(f"❌ Error en API: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route("/get-estado-historico", methods=["GET"])
def get_estado_historico():
    """API para obtener el estado actual del histórico"""
    try:
        if os.path.exists(ruta_archivo):
            with open(ruta_archivo, 'r', encoding='utf-8') as f:
                datos = json.load(f)

            total_registros = sum(len(registros) for registros in datos.values())

            # Obtener la fecha más antigua y más reciente
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
            return jsonify({
                "status": "success",
                "tiene_datos": False,
                "message": "No hay datos aún"
            })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

# ==================== INICIO DEL SERVIDOR ====================
if __name__ == "__main__":
    puerto = 5000
    hostname = socket.gethostname()
    try:
        local_ip = socket.gethostbyname(hostname)
    except:
        local_ip = "127.0.0.1"

    crear_o_validar_archivo_json()

    print("\n" + "="*70)
    print("🚀 SERVIDOR FLASK - ANÁLISIS DE LOTERÍAS COLOMBIA")
    print("="*70)

    print("\n📅 CALENDARIO DE LOTERÍAS:")
    print("─" * 70)

    dias_nombres = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

    for idx, dia_nombre in enumerate(dias_nombres):
        loterias_hoy = [lot for lot, dias in DIAS_LOTERIA.items() if idx in dias]
        print(f" {dia_nombre:12s}: {', '.join(loterias_hoy)}")

    print("\n✅ Ejecutando en HTTP")
    print(f"📍 Local: http://localhost:{puerto}")
    print(f"📱 Red: http://{local_ip}:{puerto}")

    print("\n🌐 PARA NGROK (NUEVA TERMINAL):")
    print(" ngrok http 5000")

    print("\n" + "="*70 + "\n")

    app.run(host='0.0.0.0', port=puerto, debug=True, use_reloader=False)
