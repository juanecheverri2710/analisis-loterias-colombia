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
    10x más rápido que obtener 5 años de datos.
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
                # ⭐ SOLO tomar la PRIMERA FILA (último resultado)
                filas = tabla.find_all("tr")[1:2]  # Solo primera fila de datos
                
                if filas:
                    celdas = filas[0].find_all("td")
                    if len(celdas) >= 3:
                        fecha_texto = celdas[1].text.strip()
                        fecha = validar_fecha(fecha_texto)
                        
                        # ⭐ Verificar si es NUEVO
                        if fecha and fecha > fecha_limite:
                            numero = celdas[2].text.strip()
                            serie = "No disponible"
                            
                            if "serie" in numero.lower():
                                partes = numero.lower().split("serie")
                                numero = partes[0].strip()
                                serie = partes[1].strip()
                            
                            numero_limpio = str(int(numero.lstrip('0') or '0')).zfill(4)
                            
                            print(f"✅ {nombre}: Nuevo resultado {numero_limpio} ({fecha.strftime('%Y-%m-%d')})")
                            return {
                                "numero": numero_limpio,
                                "serie": serie,
                                "fecha": fecha.strftime("%Y-%m-%d")
                            }
                        else:
                            print(f"ℹ️ {nombre}: Sin actualizaciones (último: {fecha.strftime('%Y-%m-%d') if fecha else 'N/A'})")
                            return None
                
        print(f"⚠️ {nombre}: Tabla no encontrada")
        return None
        
    except Exception as e:
        print(f"❌ {nombre}: Error - {str(e)}")
        return None


def obtener_actualizaciones_recientes():
    """
    ⚡ OPTIMIZADO: Obtiene SOLO los resultados nuevos (posteriores a los que ya tenemos).
    MUCHO más rápido que obtener 5 años completos.
    """
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
    
    print("\n📅 Verificando actualizaciones recientes...")
    actualizar_progreso("procesando", "Verificando actualizaciones...", 10)
    
    # ⭐ Cargar fechas más recientes del JSON
    historico = cargar_historial(ruta_archivo)
    fechas_limite = {}
    
    for loteria, sorteos in historico.items():
        if sorteos and len(sorteos) > 0:
            # Obtener la fecha más reciente
            fecha_str = sorteos[0].get("fecha", "")
            fecha_obj = validar_fecha(fecha_str)
            if fecha_obj:
                fechas_limite[loteria] = fecha_obj
                print(f"  {loteria}: Última fecha {fecha_obj.strftime('%Y-%m-%d')}")
            else:
                fechas_limite[loteria] = datetime.now() - timedelta(days=30)
        else:
            fechas_limite[loteria] = datetime.now() - timedelta(days=30)
    
    # ⭐ Buscar SOLO nuevos resultados (EN PARALELO)
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
            
            for futuro in as_completed(futuros, timeout=60):  # Timeout más corto
                nombre = futuros[futuro]
                contador += 1
                try:
                    resultado = futuro.result(timeout=3)
                    if resultado:
                        actualizaciones[nombre] = [resultado]  # Lista con 1 elemento
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
    
    print(f"\n⏱️ Verificación completada en {tiempo_total:.2f} segundos")
    print(f"📊 Resultados nuevos encontrados: {total_nuevos}")
    
    return actualizaciones


def obtener_historico_completo_5anos():
    """Función original para descargar todo el histórico (5 años)"""
    print("\n" + "="*100)
    print("📅 CONSULTANDO HISTÓRICO COMPLETO - ÚLTIMOS 5 AÑOS")
    print("="*100)
    
    # Reutiliza la función original de scraping
    # (Esta función se usa solo cuando se presiona el botón "Descargar Histórico")
    from datetime import timedelta
    
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
    fecha_limite = datetime.now() - timedelta(days=1825)

    actualizar_progreso("descargando_historico", "Iniciando descarga histórica...", 15)

    for nombre, url in loterias_urls.items():
        contador += 1
        try:
            response = SESSION.get(url, timeout=15, verify=True)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                tablas = soup.find_all("table")
                resultados = []
                
                for tabla in tablas:
                    encabezados = [th.text.strip() for th in tabla.find_all("th")]
                    if "# Sorteo" in encabezados and "Fecha" in encabezados and "Resultado" in encabezados:
                        filas = tabla.find_all("tr")[1:]
                        
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

                                    resultados.append({
                                        "numero": numero_limpio,
                                        "serie": serie,
                                        "fecha": fecha.strftime("%Y-%m-%d")
                                    })
                            except Exception:
                                continue
                        break
                
                historico_completo[nombre] = sorted(resultados, key=lambda x: x["fecha"], reverse=True)
                porcentaje = 15 + int((contador / total_loterias) * 50)
                actualizar_progreso("descargando_historico", f"✅ {nombre}: {len(resultados)}", porcentaje)
                print(f" ✅ {nombre}: {len(resultados)} registros")
            else:
                historico_completo[nombre] = []
                print(f" ❌ {nombre}: Error HTTP {response.status_code}")
                
        except Exception as e:
            print(f" ❌ {nombre}: Error - {str(e)}")
            historico_completo[nombre] = []

    print("\n" + "="*100)
    print("✅ DESCARGA HISTÓRICA COMPLETADA")
    print("="*100)

    total_registros = sum(len(registros) for registros in historico_completo.values())
    print(f"Total registros: {total_registros}")

    return historico_completo


def guardar_historico_json(historico):
    """Guarda el histórico en el archivo JSON"""
    try:
        print("\n💾 Guardando histórico en archivo JSON...")
        actualizar_progreso("guardando", "Guardando datos...", 80)
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
        actualizar_progreso("analizando", "Generando datos de últimos sorteos...", 85)
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
        actualizar_progreso("analizando", "Analizando números especiales...", 90)
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

            analisis_numeros_especiales[numero_especial] = numero_info

        print("✅ ANÁLISIS COMPLETADO")
    except Exception as e:
        print(f"❌ Error en análisis de números especiales: {str(e)}")

def ejecutar_scraping_y_analisis():
    """
    ⚡ VERSIÓN OPTIMIZADA: Solo busca actualizaciones recientes.
    """
    global analisis_texto
    try:
        print("\n🔄 Iniciando análisis optimizado...")
        crear_o_validar_archivo_json()
        asegurar_carpeta_static()

        actualizar_progreso("procesando", "Cargando datos existentes...", 5)

        with lock:
            print("📂 Cargando histórico...")
            historico = cargar_historial(ruta_archivo)
            
            if historico and len(historico) > 0:
                total_registros = sum(len(v) for v in historico.values())
                print(f"✅ Histórico: {total_registros} registros")
            else:
                print("⚠️ No hay histórico previo")
                historico = {}

            # ⭐ BUSCAR SOLO ACTUALIZACIONES RECIENTES
            print("\n🔍 Buscando actualizaciones recientes...")
            actualizaciones = obtener_actualizaciones_recientes()
            
            total_nuevos = sum(len(v) for v in actualizaciones.values())
            
            if total_nuevos > 0:
                print(f"\n✅ {total_nuevos} resultados nuevos encontrados")
                print("🔗 Agregando al histórico...")
                actualizar_progreso("procesando", f"Agregando {total_nuevos} nuevos...", 60)
                
                # Combinar SOLO si hay nuevos
                combinado = combinar_resultados_acumulativo(historico, actualizaciones)
            else:
                print("\n✅ No hay actualizaciones nuevas")
                actualizar_progreso("procesando", "Sin actualizaciones", 60)
                combinado = historico

            # Guardar
            print("\n💾 Guardando...")
            actualizar_progreso("guardando", "Guardando...", 70)
            with open(ruta_archivo, "w", encoding="utf-8") as f:
                json.dump(combinado, f, indent=2, ensure_ascii=False)
            copiar_json_a_static()

            # Generar predicciones
            print("\n🎯 Generando análisis...")
            generar_datos_ultimo_sorteo()
            generar_predicciones_diarias()
            analizar_numeros_especiales_probabilidad()

        analisis_texto = f"✅ Análisis completado. {total_nuevos} actualizaciones."
        actualizar_progreso("completado", "✅ ¡Completado!", 100)
        print(f"✅ [100%] Análisis COMPLETO - {total_nuevos} nuevos registros")
        
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

@app.route("/get-progreso", methods=["GET"])
def get_progreso():
    """Devuelve el progreso actual del análisis"""
    with lock:
        return jsonify(progreso_analisis)

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

@app.route('/get-calendario', methods=['GET'])
def get_calendario():
    """Retorna el calendario ordenado correctamente"""
    return jsonify(calendario)

@app.route("/obtener-historico", methods=["POST"])
def obtener_historico():
    """API para obtener histórico completo de 5 años"""
    try:
        print("\n🔄 API: Iniciando descarga del histórico...")
        actualizar_progreso("descargando_historico", "Descargando 5 años de histórico...", 15)

        historico = obtener_historico_completo_5anos()

        if guardar_historico_json(historico):
            generar_datos_ultimo_sorteo()
            generar_predicciones_diarias()
            analizar_numeros_especiales_probabilidad()

            total_registros = sum(len(registros) for registros in historico.values())
            actualizar_progreso("completado", "Histórico descargado completamente", 100)

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
        actualizar_progreso("error", str(e), 0)
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
    print("🚀 SERVIDOR FLASK - ANÁLISIS DE LOTERÍAS COLOMBIA (OPTIMIZADO)")
    print("="*70)
    print("\n📅 CALENDARIO DE LOTERÍAS:")
    print("─" * 70)

    dias_nombres = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    for idx, dia_nombre in enumerate(dias_nombres):
        loterias_hoy = [lot for lot, dias in DIAS_LOTERIA.items() if idx in dias]
        print(f" {dia_nombre:12s}: {', '.join(loterias_hoy)}")

    print("\n⚡ OPTIMIZACIONES ACTIVADAS:")
    print("  ✅ Scraping inteligente (solo busca actualizaciones nuevas)")
    print("  ✅ Timeout optimizado (60s)")
    print("  ✅ SSL verification activo")
    print("  ✅ Sistema de progreso en tiempo real")
    print("  ✅ Calendario ordenado (Domingo → Sábado)")

    print("\n✅ Ejecutando en HTTPS (Koyeb)") if os.environ.get("ENVIRONMENT") == "production" else print("\n✅ Ejecutando en HTTP")
    print(f"📍 Local: http://localhost:{puerto}")
    print(f"📱 Red: http://{local_ip}:{puerto}")
    print("\n" + "="*70 + "\n")

    app.run(host='0.0.0.0', port=puerto, debug=False, use_reloader=False, threaded=True)
