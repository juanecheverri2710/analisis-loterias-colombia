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
    "Cundinamarca": [0],  # Lunes
    "Tolima": [0],        # Lunes
    "Cruz Roja": [1],     # Martes
    "Huila": [1],         # Martes
    "Manizales": [2],     # Miércoles
    "Valle": [2],         # Miércoles
    "Meta": [2],          # Miércoles
    "Bogotá": [3],        # Jueves
    "Quindío": [3],       # Jueves
    "Medellín": [4],      # Viernes
    "Risaralda": [4],     # Viernes
    "Santander": [4],     # Viernes
    "Boyacá": [5],        # Sábado
    "Cauca": [5]          # Sábado
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

def obtener_resultados_superastro(tipo_loteria, fecha_inicio, max_intentos=5):
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
            id_tabla = 'home'
            nombre = 'Astro Sol'
        elif tipo_loteria.lower() == 'luna':
            payload = {'fecha_luna': fecha_inicio}
            id_tabla = 'profile'
            nombre = 'Astro Luna'
        else:
            return resultados
        
        print(f"🔄 {nombre}: Consultando últimos 5 años...")
        
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
        tab_content = soup.find('div', {'id': id_tabla})
        
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
        
        print(f"✅ {nombre}: {len(resultados)} resultados (5 años)")
        return resultados
    
    except Exception as e:
        print(f"❌ {tipo_loteria.upper()}: Error")
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
    
    # Obtener loterías tradicionales
    for nombre, url in loterias_urls.items():
        print(f"🔄 Consultando {nombre}...")
        resultados = obtener_resultados_loteria_tabla(nombre, url)
        resultados_totales[nombre] = resultados
    
    # Obtener Astro Luna y Astro Sol
    fecha_inicio = (datetime.now() - timedelta(days=1825)).strftime('%Y-%m-%d')
    
    print("\n🔄 Consultando Astro Luna...")
    resultados_luna = obtener_resultados_superastro('luna', fecha_inicio)
    resultados_totales["Astro Luna"] = resultados_luna
    
    print("\n🔄 Consultando Astro Sol...")
    resultados_sol = obtener_resultados_superastro('sol', fecha_inicio)
    resultados_totales["Astro Sol"] = resultados_sol
    
    return resultados_totales

# ==================== CONSULTA HISTÓRICA ====================

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
            
            # Ordenar por fecha descendente
            resultados_loteria.sort(key=lambda x: x["fecha"], reverse=True)
            historico_completo[nombre] = resultados_loteria
            print(f" ✅ {len(resultados_loteria)} registros obtenidos")
            time.sleep(1)  # Esperar 1 segundo entre solicitudes
        
        except Exception as e:
            print(f" ❌ Error: {str(e)}")
            historico_completo[nombre] = []
    
    # Obtener Astro Luna y Astro Sol
    print(f"\n[{total_loterias + 1}/{total_loterias + 2}] 📥 Consultando Astro Luna...")
    fecha_inicio = (datetime.now() - timedelta(days=1825)).strftime('%Y-%m-%d')
    resultados_luna = obtener_resultados_superastro('luna', fecha_inicio)
    historico_completo["Astro Luna"] = resultados_luna
    
    print(f"[{total_loterias + 2}/{total_loterias + 2}] 📥 Consultando Astro Sol...")
    resultados_sol = obtener_resultados_superastro('sol', fecha_inicio)
    historico_completo["Astro Sol"] = resultados_sol
    
    print("\n" + "="*100)
    print("✅ CONSULTA HISTÓRICA COMPLETADA")
    print("="*100)
    
    # Resumen
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

def generar_predicciones_diarias():
    """Genera predicciones de números ganadores para las loterías que juegan HOY"""
    global predicciones_diarias
    try:
        with open(ruta_archivo, 'r', encoding='utf-8') as f:
            datos = json.load(f)
        
        hoy = datetime.now()
        hoy_dia = hoy.weekday()  # 0=Lunes, 6=Domingo
        dias_nombres = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
        
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
                        for sorteo in sorteos_validos:
                            num = sorteo.get("numero", "0").strip().lstrip('0') or "0"
                            numeros_freq[num] = numeros_freq.get(num, 0) + 1
                        
                        top_numeros = sorted(numeros_freq.items(), key=lambda x: x[1], reverse=True)[:5]
                        
                        if top_numeros:
                            numero_predicho = top_numeros[0][0].zfill(4)
                            signo = sorteos_validos[0].get("serie", "No disponible")
                            
                            predicciones_diarias[loteria] = {
                                "numero": numero_predicho,
                                "signo": signo,
                                "confianza": round((top_numeros[0][1] / len(sorteos_validos)) * 100, 2),
                                "juega_hoy": True,
                                "top_5": [num.zfill(4) for num, _ in top_numeros]
                            }
        
        print(f"✅ Predicciones generadas para {len(predicciones_diarias)} loterías")
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
            
            # Analizar en todas las loterías
            for loteria, sorteos in datos.items():
                apariciones_loteria = []
                fechas_loteria = []
                
                for sorteo in sorteos:
                    numero_sorteo = sorteo.get("numero", "").strip().lstrip('0') or "0"
                    numero_check = numero_especial.lstrip('0') or "0"
                    
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
            
            # Calcular probabilidad
            apariciones_total = numero_info["apariciones_total"]
            if apariciones_total > 0:
                frecuencia_anual = (apariciones_total / 5)
                numero_info["probabilidad"] = min(100, (frecuencia_anual / 16) * 100)
            
            # Obtener últimas fechas
            todas_fechas = []
            for loteria, sorteos in datos.items():
                for sorteo in sorteos:
                    numero_sorteo = sorteo.get("numero", "").strip().lstrip('0') or "0"
                    numero_check = numero_especial.lstrip('0') or "0"
                    
                    if numero_sorteo == numero_check:
                        fecha_str = sorteo.get("fecha", "")
                        fecha_obj = validar_fecha(fecha_str)
                        if fecha_obj:
                            todas_fechas.append((fecha_obj, loteria))
            
            todas_fechas.sort(reverse=True)
            numero_info["ultimas_fechas"] = [(f.strftime("%Y-%m-%d"), l) for f, l in todas_fechas[:5]]
            
            # Calcular promedio de días entre apariciones
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
            print(f" • Último año (365 días): {numero_info['apariciones_1ano']}")
            print(f" • Últimos 2 años (730 días): {numero_info['apariciones_2anos']}")
            print(f" • Últimos 3 años (1095 días): {numero_info['apariciones_3anos']}")
            
            print(f"\n📊 PROBABILIDAD ESTIMADA: {numero_info['probabilidad']:.1f}%")
            
            analisis_numeros_especiales[numero_especial] = numero_info
        
        print("\n" + "="*100)
        print("✅ ANÁLISIS COMPLETADO")
        print("="*100)
    
    except Exception as e:
        print(f"❌ Error en análisis de números especiales: {str(e)}")

def ejecutar_scraping_y_analisis():
    """Función principal que ejecuta todo el proceso de scraping y análisis"""
    try:
        print("\n🚀 INICIANDO SCRAPING Y ANÁLISIS...")
        
        # Obtener histórico
        historico = obtener_historico_completo_5anos()
        
        # Guardar el histórico
        if guardar_historico_json(historico):
            # Actualizar datos globales
            generar_datos_ultimo_sorteo()
            generar_predicciones_diarias()
            analizar_numeros_especiales_probabilidad()
            
            print("\n✅ TODO COMPLETADO EXITOSAMENTE")
        else:
            print("\n❌ Error al guardar el histórico")
    
    except Exception as e:
        print(f"\n❌ Error en scraping y análisis: {str(e)}")

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
    """Devuelve datos del último sorteo de cada lotería"""
    return jsonify(datos_ultimo_sorteo)

@app.route("/get-predicciones", methods=["GET"])
def get_predicciones():
    """Devuelve predicciones de números ganadores para las loterías que juegan HOY"""
    return jsonify(predicciones_diarias)

@app.route("/get-analisis-numeros", methods=["GET"])
def get_analisis_numeros():
    """Devuelve análisis de probabilidad de números especiales"""
    return jsonify(analisis_numeros_especiales)

@app.route('/static/')
def static_files(filename):
    """Sirve archivos estáticos"""
    return send_from_directory(carpeta_static, filename)

@app.route("/get-calendario", methods=["GET"])
def get_calendario():
    """Devuelve el calendario de loterías por día"""
    dias_nombres = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    calendario = {}
    
    for loteria, dias in DIAS_LOTERIA.items():
        for dia in dias:
            dia_nombre = dias_nombres[dia]
            if dia_nombre not in calendario:
                calendario[dia_nombre] = []
            calendario[dia_nombre].append(loteria)
    
    return jsonify(calendario)

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
                "message": "Histórico descargado y guardado exitosamente",
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
    
    # Inicializar archivos
    crear_o_validar_archivo_json()
    generar_datos_ultimo_sorteo()
    generar_predicciones_diarias()
    analizar_numeros_especiales_probabilidad()
    
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
