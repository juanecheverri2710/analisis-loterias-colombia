import json
import threading
import shutil
import os
from datetime import datetime, timedelta
import pandas as pd
from flask import Flask, render_template, jsonify, send_from_directory

app = Flask(__name__)
app.config['PREFERRED_URL_SCHEME'] = 'https'
app.config['TRUST_REMOTE_ADDR'] = True

ruta_archivo = "resultados_loterias.json"
carpeta_static = "static"
archivo_json_static = os.path.join(carpeta_static, ruta_archivo)

lock = threading.Lock()
datos_ultimo_sorteo = {}
predicciones_diarias = {}
analisis_numeros_especiales = {}
progreso_analisis = {"estado": "inactivo", "mensaje": "", "porcentaje": 0}

# Funciones validación y carga

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

def obtener_actualizaciones_recientes():
    # URLs ficticias; sustituye por URLs reales o implementa scraping
    loterias_urls = {
        "Boyacá": "http://url",
        "Cruz Roja": "http://url",
        "Manizales": "http://url",
        "Cundinamarca": "http://url",
        "Tolima": "http://url",
        "Medellín": "http://url",
        "Santander": "http://url",
        "Huila": "http://url",
        "Risaralda": "http://url",
        "Bogotá": "http://url",
        "Meta": "http://url",
        "Quindío": "http://url",
        "Valle": "http://url",
        "Cauca": "http://url"
    }
    actualizar_progreso("procesando", "Sin scraping para demo...", 20)
    actualizaciones = {lot: [] for lot in loterias_urls}
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

def generar_datos_ultimo_sorteo():
    global datos_ultimo_sorteo
    try:
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
        print(f"✅ Datos último sorteo cargados: {len(datos_ultimo_sorteo)} loterías")
    except Exception as e:
        print(f"⚠️ Error cargando datos últimos sorteos: {e}")

def generar_predicciones_diarias():
    global predicciones_diarias
    try:
        with open(ruta_archivo, 'r', encoding='utf-8') as f:
            datos = json.load(f)
        predicciones_diarias = {}
        for loteria, sorteos in datos.items():
            if sorteos:
                numeros_freq = {}
                for sorteo in sorteos[:10]:
                    num = str(sorteo.get("numero", "0")).strip().zfill(4)
                    numeros_freq[num] = numeros_freq.get(num, 0) + 1
                if numeros_freq:
                    top = sorted(numeros_freq.items(), key=lambda x: x[1], reverse=True)
                    predicciones_diarias[loteria] = {"numero": top[0][0], "frecuencia": top[0][1]}
        print(f"✅ Predicciones diarias generadas: {len(predicciones_diarias)} loterías")
    except Exception as e:
        print(f"⚠️ Error generando predicciones: {e}")

def analizar_numeros_especiales_probabilidad():
    global analisis_numeros_especiales
    try:
        with open(ruta_archivo, 'r', encoding='utf-8') as f:
            datos = json.load(f)
        hoy = datetime.now()
        fecha_limite = hoy - timedelta(days=365)
        analisis_numeros_especiales = {}
        for numero_especial in ["0419", "0116", "2710", "1012", "6888"]:
            numero_info = {
                "numero": numero_especial, "apariciones_total": 0,
                "apariciones_1ano": 0, "loterrias_donde_cayo": {}, "probabilidad": 0
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
                            if fecha_obj >= fecha_limite:
                                numero_info["apariciones_1ano"] += 1
                            numero_info["loterrias_donde_cayo"][loteria] = numero_info["loterrias_donde_cayo"].get(loteria, 0) + 1
            if numero_info["apariciones_total"] > 0:
                numero_info["probabilidad"] = min(100, (numero_info["apariciones_total"] / 5 / 16) * 100)
            analisis_numeros_especiales[numero_especial] = numero_info
        print(f"✅ Análisis números especiales generado")
    except Exception as e:
        print(f"⚠️ Error analizando números especiales: {e}")

def ejecutar_scraping_y_analisis():
    global analisis_texto
    try:
        crear_o_validar_archivo_json()
        asegurar_carpeta_static()
        actualizar_progreso("procesando", "Cargando...", 5)
        with lock:
            historico = cargar_historial(ruta_archivo)
            total = sum(len(v) for v in historico.values()) if historico else 0
            print(f"✅ Histórico: {total} registros")
            actualizaciones = obtener_actualizaciones_recientes()
            total_nuevos = sum(len(v) for v in actualizaciones.values())
            if total_nuevos > 0:
                actualizar_progreso("procesando", f"{total_nuevos} nuevos...", 50)
                combinado = combinar_resultados_acumulativo(historico, actualizaciones)
            else:
                actualizar_progreso("procesando", "Sin actualizaciones", 50)
                combinado = historico
            actualizar_progreso("guardando", "Guardando...", 55)
            with open(ruta_archivo, "w", encoding="utf-8") as f:
                json.dump(combinado, f, indent=2, ensure_ascii=False)
            copiar_json_a_static()
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

if __name__ == "__main__":
    puerto = int(os.environ.get("PORT", 5000))
    print("\n" + "=" * 70)
    print("🚀 ANÁLISIS DE LOTERÍAS - IA OPTIMIZADA")
    print("=" * 70)
    app.run(host='0.0.0.0', port=puerto, debug=False, use_reloader=False, threaded=True)
