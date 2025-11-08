import json
import threading
import shutil
import os
import pickle
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template, jsonify, send_from_directory
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from collections import OrderedDict
import socket
import time
import warnings

warnings.filterwarnings('ignore')

# ==================== CONFIGURACIÓN ====================
app = Flask(__name__)
app.config['PREFERRED_URL_SCHEME'] = 'https'
app.config['TRUST_REMOTE_ADDR'] = True

# Rutas
ruta_archivo = "resultados_loterias.json"
carpeta_static = "static"
archivo_json_static = os.path.join(carpeta_static, ruta_archivo)
modelo_pkl = "modelo_ia.pkl"
analisis_texto = ""
datos_ultimo_sorteo = {}
predicciones_diarias = {}
analisis_numeros_especiales = {}
lock = threading.Lock()
modelo_ia = None
progreso_analisis = {"estado": "inactivo", "mensaje": "", "porcentaje": 0}

SESSION = requests.Session()
SESSION.headers.update({'User-Agent': 'Mozilla/5.0'})

# CALENDARIO
DIAS_LOTERIA = {
    "Cundinamarca": [0], "Tolima": [0], "Cruz Roja": [1], "Huila": [1],
    "Manizales": [2], "Valle": [2], "Meta": [2], "Bogotá": [3], "Quindío": [3],
    "Medellín": [4], "Risaralda": [4], "Santander": [4], "Boyacá": [5], "Cauca": [5]
}

calendario = OrderedDict([
    ('Domingo', []), ('Lunes', ['Cundinamarca', 'Tolima']),
    ('Martes', ['Cruz Roja', 'Huila']), ('Miércoles', ['Manizales', 'Valle', 'Meta']),
    ('Jueves', ['Bogotá', 'Quindío']), ('Viernes', ['Medellín', 'Risaralda', 'Santander']),
    ('Sábado', ['Boyacá', 'Cauca'])
])

NUMEROS_ESPECIALES = ["0419", "0116", "2710", "1012", "6888"]

# ==================== FUNCIONES ====================

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
        shutil.copy(ruta_archivo, archivo_json_static)

def cargar_historial(ruta):
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def actualizar_progreso(estado, mensaje, porcentaje):
    global progreso_analisis
    with lock:
        progreso_analisis = {"estado": estado, "mensaje": mensaje, "porcentaje": min(100, max(0, porcentaje))}
    print(f"📊 [{porcentaje}%] {mensaje}")

# ==================== SCRAPING OPTIMIZADO ====================

def obtener_solo_ultimo_resultado(nombre, url, fecha_limite):
    try:
        response = SESSION.get(url, timeout=10, verify=True)
        if response.status_code != 200:
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
                            return {"numero": numero_limpio, "serie": serie, "fecha": fecha.strftime("%Y-%m-%d")}
        return None
    except:
        return None

def obtener_actualizaciones_recientes():
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
    
    actualizar_progreso("procesando", "Verificando...", 10)
    historico = cargar_historial(ruta_archivo)
    fechas_limite = {}
    
    for loteria, sorteos in historico.items():
        if sorteos:
            fecha_str = sorteos[0].get("fecha", "")
            fecha_obj = validar_fecha(fecha_str)
            fechas_limite[loteria] = fecha_obj if fecha_obj else datetime.now() - timedelta(days=30)
        else:
            fechas_limite[loteria] = datetime.now() - timedelta(days=30)
    
    actualizaciones = {}
    contador = 0
    total = len(loterias_urls)
    
    try:
        with ThreadPoolExecutor(max_workers=5) as executor:
            futuros = {executor.submit(obtener_solo_ultimo_resultado, nombre, url, 
                      fechas_limite.get(nombre, datetime.now() - timedelta(days=7))): nombre 
                      for nombre, url in loterias_urls.items()}
            for futuro in as_completed(futuros, timeout=60):
                nombre = futuros[futuro]
                contador += 1
                try:
                    resultado = futuro.result(timeout=3)
                    actualizaciones[nombre] = [resultado] if resultado else []
                    actualizar_progreso("procesando", f"{contador}/{total}", 10 + int((contador/total)*40))
                except:
                    actualizaciones[nombre] = []
    except TimeoutError:
        pass
    
    return actualizaciones

def combinar_resultados_acumulativo(historico, nuevos):
    actualizar_progreso("procesando", "Combinando...", 55)
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

# ==================== IA OPTIMIZADA (SIN SMOTE) ====================

def entrenar_modelo_xgboost_simple(df):
    """🤖 XGBoost SIMPLE (sin SMOTE) - Ultra rápido"""
    global modelo_ia
    
    print("\n🤖 ENTRENANDO MODELO IA (XGBoost - SIN SMOTE)")
    actualizar_progreso("entrenando", "Preparando datos...", 60)
    
    df['numero_int'] = df['numero'].astype(int)
    features, labels = [], []
    
    # Generar secuencias de 5 números
    for loteria in df['loteria'].unique():
        df_lot = df[df['loteria'] == loteria].sort_values('fecha')
        for i in range(5, min(len(df_lot), 100)):  # Limitar a 100 por lotería
            ultimos_5 = df_lot.iloc[i-5:i]['numero_int'].values
            features.append(list(ultimos_5))
            labels.append(df_lot.iloc[i]['numero_int'])
    
    if len(features) < 30:
        print("⚠️ Datos insuficientes")
        return None
    
    X, y = np.array(features), np.array(labels)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    actualizar_progreso("entrenando", "Entrenando XGBoost...", 70)
    
    # ⚡ XGBoost MUY REDUCIDO
    modelo = XGBClassifier(
        n_estimators=30,      # Solo 30 árboles
        max_depth=3,          # Profundidad baja
        learning_rate=0.1,
        random_state=42,
        n_jobs=1,             # Solo 1 core
        verbosity=0
    )
    
    modelo.fit(X_train, y_train)
    score = modelo.score(X_test, y_test)
    
    print(f"✅ Modelo entrenado - Precisión: {score*100:.2f}%")
    
    # Guardar modelo
    try:
        with open(modelo_pkl, 'wb') as f:
            pickle.dump(modelo, f)
        print("💾 Modelo guardado en disco")
    except:
        pass
    
    modelo_ia = modelo
    return modelo

def cargar_o_entrenar_modelo(df):
    """Carga modelo o entrena uno nuevo"""
    global modelo_ia
    
    # Verificar modelo existente (24 horas)
    if os.path.exists(modelo_pkl):
        try:
            tiempo_modelo = os.path.getmtime(modelo_pkl)
            if (time.time() - tiempo_modelo) < 86400:
                print("✅ Cargando modelo guardado...")
                actualizar_progreso("cargando_modelo", "Cargando IA...", 65)
                with open(modelo_pkl, 'rb') as f:
                    modelo_ia = pickle.load(f)
                print("✅ Modelo cargado desde disco")
                return modelo_ia
        except:
            pass
    
    # Entrenar nuevo modelo
    return entrenar_modelo_xgboost_simple(df)

def analizar_patrones_basico(df):
    """Análisis estadístico simple en consola"""
    print("\n" + "="*80)
    print("📊 ANÁLISIS ESTADÍSTICO")
    print("="*80)
    print(f"Total sorteos: {len(df)}")
    print(f"Rango: {df['fecha'].min()} a {df['fecha'].max()}")
    print("\nTop 10 números:")
    top = df['numero'].value_counts().head(10)
    for num, freq in top.items():
        print(f"  {num}: {freq}x")
    print("="*80)

def generar_datos_ultimo_sorteo():
    global datos_ultimo_sorteo
    try:
        actualizar_progreso("analizando", "Generando datos...", 85)
        with open(ruta_archivo, 'r', encoding='utf-8') as f:
            datos = json.load(f)
        datos_ultimo_sorteo = {}
        for loteria, sorteos in datos.items():
            if sorteos:
                ultimo = sorteos[0]
                datos_ultimo_sorteo[loteria] = {
                    "numero": str(ultimo.get("numero", "N/A")).zfill(4),
                    "signo": str(ultimo.get("serie", "N/A")),
                    "fecha": str(ultimo.get("fecha", "N/A"))
                }
        return True
    except:
        return False

def generar_predicciones_diarias():
    global predicciones_diarias
    try:
        with open(ruta_archivo, 'r', encoding='utf-8') as f:
            datos = json.load(f)
        hoy_dia = datetime.now().weekday()
        predicciones_diarias = {}
        for loteria, sorteos in datos.items():
            if loteria in DIAS_LOTERIA and hoy_dia in DIAS_LOTERIA[loteria]:
                if sorteos:
                    sorteos_recientes = sorteos[:10]
                    numeros_freq = {}
                    for sorteo in sorteos_recientes:
                        num = str(sorteo.get("numero", "0")).strip().zfill(4)
                        numeros_freq[num] = numeros_freq.get(num, 0) + 1
                    if numeros_freq:
                        top = sorted(numeros_freq.items(), key=lambda x: x[1], reverse=True)
                        predicciones_diarias[loteria] = {"numero": top[0][0], "frecuencia": top[0][1]}
    except:
        pass

def analizar_numeros_especiales_probabilidad():
    global analisis_numeros_especiales
    try:
        actualizar_progreso("analizando", "Analizando...", 90)
        with open(ruta_archivo, 'r', encoding='utf-8') as f:
            datos = json.load(f)
        hoy = datetime.now()
        fecha_limite = hoy - timedelta(days=365)
        analisis_numeros_especiales = {}
        for numero_especial in NUMEROS_ESPECIALES:
            numero_info = {"numero": numero_especial, "apariciones_total": 0, "apariciones_1ano": 0, 
                          "loterrias_donde_cayo": {}, "probabilidad": 0}
            for loteria, sorteos in datos.items():
                for sorteo in sorteos:
                    numero_sorteo = str(sorteo.get("numero", "0")).strip().zfill(4)
                    numero_check = str(int(numero_especial.lstrip('0') or '0')).zfill(4)
                    if numero_sorteo == numero_check:
                        fecha_str = sorteo.get("fecha", "")
                        fecha_obj = validar_fecha(fecha_str)
                        if fecha_obj:
                            numero_info["apariciones_total"] += 1
                            if fecha_obj >= fecha_limite:
                                numero_info["apariciones_1ano"] += 1
                            numero_info["loterrias_donde_cayo"][loteria] = \
                                numero_info["loterrias_donde_cayo"].get(loteria, 0) + 1
            if numero_info["apariciones_total"] > 0:
                numero_info["probabilidad"] = min(100, (numero_info["apariciones_total"] / 5 / 16) * 100)
            analisis_numeros_especiales[numero_especial] = numero_info
    except:
        pass

def ejecutar_scraping_y_analisis():
    global analisis_texto
    try:
        print("\n🔄 Iniciando análisis...")
        crear_o_validar_archivo_json()
        asegurar_carpeta_static()
        actualizar_progreso("procesando", "Cargando...", 5)
        
        with lock:
            historico = cargar_historial(ruta_archivo)
            if historico:
                total = sum(len(v) for v in historico.values())
                print(f"✅ Histórico: {total} registros")
            
            # Scraping optimizado
            actualizaciones = obtener_actualizaciones_recientes()
            total_nuevos = sum(len(v) for v in actualizaciones.values())
            
            if total_nuevos > 0:
                actualizar_progreso("procesando", f"{total_nuevos} nuevos...", 50)
                combinado = combinar_resultados_acumulativo(historico, actualizaciones)
            else:
                actualizar_progreso("procesando", "Sin actualizaciones", 50)
                combinado = historico
            
            # Guardar
            actualizar_progreso("guardando", "Guardando...", 55)
            with open(ruta_archivo, "w", encoding="utf-8") as f:
                json.dump(combinado, f, indent=2, ensure_ascii=False)
            copiar_json_a_static()
            
            # ⚡ IA OPTIMIZADA (SIN SMOTE)
            df_completo = []
            for lot, sorteos in combinado.items():
                for sorteo in sorteos:
                    df_completo.append({'loteria': lot, 'numero': sorteo['numero'], 
                                       'serie': sorteo['serie'], 'fecha': sorteo['fecha']})
            if df_completo:
                df = pd.DataFrame(df_completo)
                analizar_patrones_basico(df)
                cargar_o_entrenar_modelo(df)
            
            generar_datos_ultimo_sorteo()
            generar_predicciones_diarias()
            analizar_numeros_especiales_probabilidad()
        
        analisis_texto = f"✅ Análisis completo con IA. {total_nuevos} actualizaciones."
        actualizar_progreso("completado", "✅ Completado!", 100)
        print("✅ [100%] COMPLETO")
    except Exception as e:
        analisis_texto = f"Error: {str(e)}"
        actualizar_progreso("error", str(e), 0)
        print(f"❌ {str(e)}")

# ==================== RUTAS FLASK ====================

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/start-analysis", methods=["POST"])
def start_analysis():
    thread = threading.Thread(target=ejecutar_scraping_y_analisis, daemon=True)
    thread.start()
    return jsonify({"message": "Análisis iniciado."})

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

@app.route("/descargar-json", methods=["GET"])
def descargar_json():
    try:
        if os.path.exists(ruta_archivo):
            return send_from_directory(directory=os.getcwd(), path=ruta_archivo, as_attachment=True,
                                      download_name=f"resultados_{datetime.now().strftime('%Y%m%d')}.json")
        return jsonify({"error": "No encontrado"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==================== INICIO ====================

if __name__ == "__main__":
    puerto = int(os.environ.get("PORT", 5000))
    print("\n" + "="*70)
    print("🚀 ANÁLISIS DE LOTERÍAS - IA OPTIMIZADA (SIN SMOTE)")
    print("="*70)
    print("  ✅ XGBoost (30 estimadores)")
    print("  ✅ Sin SMOTE (80% más rápido)")
    print("  ✅ Modelo guardado")
    print("  ✅ Scraping solo nuevos")
    print("="*70 + "\n")
    app.run(host='0.0.0.0', port=puerto, debug=False, use_reloader=False, threaded=True)
