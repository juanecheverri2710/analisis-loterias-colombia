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
warnings.filterwarnings('ignore')

try:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except:
    pass

app = Flask(__name__)
app.config['PREFERRED_URL_SCHEME'] = 'https'
app.config['TRUST_REMOTE_ADDR'] = True

ruta_archivo = "resultados_loterias.json"
carpeta_static = "static"
archivo_json_static = os.path.join(carpeta_static, ruta_archivo)

analisis_texto = ""
datos_ultimo_sorteo = {}
predicciones_diarias = {}
lock = threading.Lock()
modelo_ia = None

CALENDARIO_LOTERIAS = {
    "lunes": ["Cundinamarca", "Tolima"],
    "martes": ["Cruz Roja", "Huila"],
    "miércoles": ["Manizales", "Valle", "Meta"],
    "jueves": ["Bogotá", "Quindío"],
    "viernes": ["Medellín", "Santander", "Risaralda"],
    "sábado": ["Boyacá", "Cauca"],
    "astro luna": ["todos los días"],
    "astro sol": ["todos los días"],
}

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
    "Santander": [4],
    "Risaralda": [4],
    "Boyacá": [5],
    "Cauca": [5],
    "Astro Luna": [0, 1, 2, 3, 4, 5, 6],
    "Astro Sol": [0, 1, 2, 3, 4, 5, 6]
}

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

def obtener_resultados_loteria_tabla(nombre, url):
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
                fecha = None
                for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y"):
                    try:
                        fecha = datetime.strptime(fecha_texto, fmt)
                        break
                    except ValueError:
                        continue
                if fecha is None or fecha < fecha_limite:
                    continue
                numero = celdas[2].text.strip()
                serie = "No disponible"
                if "serie" in numero.lower():
                    partes = numero.lower().split("serie")
                    numero = partes[0].strip()
                    serie = partes[1].strip()
                resultados.append({
                    "numero": numero,
                    "serie": serie,
                    "fecha": fecha.strftime("%Y-%m-%d")
                })
        print(f"✅ {nombre}: {len(resultados)} resultados")
        return resultados
    except Exception as e:
        print(f"❌ {nombre}: Error")
        return resultados

def obtener_resultados_superastro_mejorado(tipo_loteria, fecha_inicio, max_intentos=5):
    resultados = []
    try:
        if tipo_loteria.lower() == 'sol':
            nombre_loteria = 'Astro Sol'
            urls = [
                "https://superastro.com.co/resultados-astro-sol",
                "https://resultadodelaloteria.com/colombia/astro-sol",
                "https://www.astrosor.com/astro-sol",
                "https://superastro.co/astro-sol"
            ]
        elif tipo_loteria.lower() == 'luna':
            nombre_loteria = 'Astro Luna'
            urls = [
                "https://superastro.com.co/resultados-astro-luna",
                "https://resultadodelaloteria.com/colombia/astro-luna",
                "https://www.astrosor.com/astro-luna",
                "https://superastro.co/astro-luna"
            ]
        else:
            return resultados
        
        print(f"🔄 {nombre_loteria}: Descargando histórico de 5 años...")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'es-ES,es;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        response = None
        url_exitosa = None
        
        for url in urls:
            print(f"   Intentando: {url}")
            for intento in range(max_intentos):
                try:
                    response = requests.get(url, headers=headers, timeout=20, verify=False, allow_redirects=True)
                    if response.status_code == 200:
                        url_exitosa = url
                        print(f"   ✅ Conexión exitosa a {url}")
                        break
                    elif response.status_code in [301, 302, 303, 307, 308]:
                        print(f"   → Redirigiendo desde {url}")
                        if 'Location' in response.headers:
                            url = response.headers['Location']
                            continue
                    else:
                        print(f"   ⚠️ Error {response.status_code}")
                        time.sleep(1)
                except requests.exceptions.Timeout:
                    print(f"   ⏱️ Timeout (intento {intento+1}/{max_intentos})")
                    time.sleep(2)
                except requests.exceptions.ConnectionError as e:
                    print(f"   🔌 Error de conexión (intento {intento+1}/{max_intentos})")
                    time.sleep(2)
                except Exception as e:
                    print(f"   ❌ Error: {str(e)[:50]}")
                    time.sleep(2)
            
            if response and response.status_code == 200:
                break
        
        if not response or response.status_code != 200:
            print(f"❌ No se pudo conectar a ninguna URL para {nombre_loteria}")
            print(f"   URLs intentadas: {len(urls)}")
            return resultados
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        tablas = soup.find_all('table')
        if not tablas:
            print(f"⚠️ No se encontraron tablas HTML en {url_exitosa}")
            
            divs = soup.find_all('div', class_=lambda x: x and 'resultado' in x.lower())
            if divs:
                print(f"   Intentando parsear divs alternativos...")
                for div in divs[:100]:
                    try:
                        texto = div.get_text(strip=True)
                        partes = texto.split()
                        if len(partes) >= 3:
                            fecha_str = partes[0]
                            numero = partes[1]
                            signo = partes[2].lower() if len(partes) > 2 else "sin signo"
                            
                            try:
                                fecha_obj = datetime.strptime(fecha_str, '%d/%m/%Y')
                            except:
                                continue
                            
                            fecha_limite = datetime.now() - timedelta(days=1825)
                            if fecha_obj < fecha_limite:
                                continue
                            
                            numero_limpio = numero.replace('.', '').strip()
                            if numero_limpio.isdigit() and 3 <= len(numero_limpio) <= 4:
                                resultados.append({
                                    "numero": numero_limpio.zfill(4),
                                    "serie": signo,
                                    "fecha": fecha_obj.strftime('%Y-%m-%d')
                                })
                    except:
                        continue
            
            return resultados
        
        fecha_limite = datetime.now() - timedelta(days=1825)
        contador = 0
        
        for tabla in tablas:
            filas = tabla.find_all('tr')
            if len(filas) < 2:
                continue
            
            for fila in filas[1:]:
                try:
                    celdas = fila.find_all('td')
                    if len(celdas) < 3:
                        continue
                    
                    fecha_str = celdas[0].get_text(strip=True)
                    numero = celdas[1].get_text(strip=True)
                    signo = celdas[2].get_text(strip=True).lower().strip() if len(celdas) > 2 else "sin signo"
                    
                    fecha_obj = None
                    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%d/%m/%y', '%d.%m.%Y'):
                        try:
                            fecha_obj = datetime.strptime(fecha_str, fmt)
                            break
                        except ValueError:
                            continue
                    
                    if not fecha_obj or fecha_obj < fecha_limite:
                        continue
                    
                    fecha_formateada = fecha_obj.strftime('%Y-%m-%d')
                    numero_limpio = numero.replace(' ', '').replace('.', '').replace(',', '').strip()
                    
                    if numero_limpio.isdigit() and 3 <= len(numero_limpio) <= 4:
                        numero_formateado = numero_limpio.zfill(4)
                        resultados.append({
                            "numero": numero_formateado,
                            "serie": signo,
                            "fecha": fecha_formateada
                        })
                        contador += 1
                except Exception as e:
                    continue
        
        if contador > 0:
            print(f"✅ {nombre_loteria}: {contador} resultados descargados (últimos 5 años) desde {url_exitosa}")
        else:
            print(f"⚠️ {nombre_loteria}: Tabla encontrada pero sin datos válidos")
        
        return resultados
    
    except Exception as e:
        print(f"❌ {tipo_loteria.upper()}: Error general - {str(e)[:100]}")
        return resultados

def obtener_todas_loterias():
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
        print(f"Consultando {nombre}...")
        resultados = obtener_resultados_loteria_tabla(nombre, url)
        resultados_totales[nombre] = resultados
    
    fecha_inicio = (datetime.now() - timedelta(days=1825)).strftime('%Y-%m-%d')
    print("\nConsultando Astro Luna...")
    resultados_luna = obtener_resultados_superastro_mejorado('luna', fecha_inicio)
    resultados_totales["Astro Luna"] = resultados_luna
    
    print("\nConsultando Astro Sol...")
    resultados_sol = obtener_resultados_superastro_mejorado('sol', fecha_inicio)
    resultados_totales["Astro Sol"] = resultados_sol
    
    return resultados_totales

def combinar_resultados_acumulativo(historico, nuevos):
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

def guardar_resultado_loteria(nuevo_resultado):
    try:
        datos = {}
        if os.path.exists(ruta_archivo):
            with open(ruta_archivo, 'r', encoding='utf-8') as f:
                datos = json.load(f)
        
        for loteria, lista_resultados in nuevo_resultado.items():
            if loteria not in datos:
                datos[loteria] = []
            
            numeros_existentes = {(r['numero'], r['fecha']) for r in datos[loteria]}
            datos[loteria] = lista_resultados + [r for r in datos[loteria] 
                                                 if (r['numero'], r['fecha']) not in {(nr['numero'], nr['fecha']) for nr in lista_resultados}]
        
        with open(ruta_archivo, 'w', encoding='utf-8') as f:
            json.dump(datos, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Datos guardados correctamente en {ruta_archivo}")
    except Exception as e:
        print(f"❌ Error guardando datos: {str(e)}")

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
                    "numero": ultimo.get("numero", "N/A"),
                    "signo": ultimo.get("serie", "N/A"),
                    "fecha": ultimo.get("fecha", "N/A")
                }
        print(f"✅ Datos del último sorteo cargados: {len(datos_ultimo_sorteo)} loterías")
    except Exception as e:
        print(f"⚠️ Error cargando datos: {str(e)}")

def generar_predicciones_diarias():
    global predicciones_diarias
    try:
        with open(ruta_archivo, 'r', encoding='utf-8') as f:
            datos = json.load(f)
        
        hoy_dia = datetime.now().weekday()
        predicciones_diarias = {}
        
        for loteria_key, dias_juega in DIAS_LOTERIA.items():
            if hoy_dia not in dias_juega:
                continue
            
            loteria_nombre = None
            for key in datos.keys():
                if key.lower() == loteria_key.lower():
                    loteria_nombre = key
                    break
            
            if not loteria_nombre or loteria_nombre not in datos:
                continue
            
            sorteos = datos[loteria_nombre]
            if not sorteos or len(sorteos) < 5:
                continue
            
            numeros_freq = {}
            signos_freq = {}
            
            for sorteo in sorteos:
                numero = str(sorteo.get("numero", "0")).strip().lstrip('0') or "0"
                numeros_freq[numero] = numeros_freq.get(numero, 0) + 1
                
                if "Astro" in loteria_nombre:
                    signo = str(sorteo.get("serie", "")).strip().lower()
                    if signo and signo != "no disponible":
                        signos_freq[signo] = signos_freq.get(signo, 0) + 1
            
            if numeros_freq:
                top_numeros = sorted(numeros_freq.items(), key=lambda x: x[1], reverse=True)
                numero_predicho = str(top_numeros[0][0]).zfill(4)
                
                if "Astro" in loteria_nombre and signos_freq:
                    top_signos = sorted(signos_freq.items(), key=lambda x: x[1], reverse=True)
                    signo_predicho = top_signos[0][0]
                    predicciones_diarias[loteria_nombre] = {
                        "numero": numero_predicho,
                        "signo": signo_predicho,
                        "apariciones": top_numeros[0][1]
                    }
                    print(f"🎯 {loteria_nombre}: Número {numero_predicho} (Signo: {signo_predicho}) - {top_numeros[0][1]} apariciones")
                else:
                    predicciones_diarias[loteria_nombre] = {
                        "numero": numero_predicho,
                        "signo": "N/A",
                        "apariciones": top_numeros[0][1]
                    }
                    print(f"🎯 {loteria_nombre}: Número {numero_predicho} - {top_numeros[0][1]} apariciones")
        
        print(f"\n✅ Predicciones generadas para HOY ({datetime.now().strftime('%A')})")
        print(f" Loterías que juegan hoy: {len(predicciones_diarias)}")
    except Exception as e:
        print(f"⚠️ Error generando predicciones: {str(e)}")
        import traceback
        traceback.print_exc()

def cargar_a_dataframe(nombre_archivo):
    try:
        with open(nombre_archivo, 'r', encoding='utf-8') as f:
            datos = json.load(f)
    except:
        return pd.DataFrame()
    filas = []
    for loteria, sorteos in datos.items():
        for r in sorteos:
            filas.append({
                'loteria': loteria,
                'numero': r['numero'].strip().lstrip('0'),
                'serie': r.get('serie', 'No disponible'),
                'fecha': r['fecha']
            })
    if not filas:
        return pd.DataFrame()
    df = pd.DataFrame(filas)
    df['fecha'] = pd.to_datetime(df['fecha'])
    df['numero'] = df['numero'].astype(str)
    return df

def analizar_patrones(nombre_archivo):
    df = cargar_a_dataframe(nombre_archivo)
    if df.empty:
        return
    print("\n" + "="*80)
    print("📊 ANÁLISIS GENERAL (ÚLTIMOS 5 AÑOS)")
    print("="*80)
    print(f"\n📈 Total de registros: {len(df)}")
    print(f"📅 Período: 1825 días (5 años)")
    print(f"🎰 Total de loterías: {df['loteria'].nunique()}")
    print("\n🎯 RESULTADOS POR LOTERÍA:")
    print("─" * 80)
    conteo = df.groupby("loteria").size().sort_values(ascending=False)
    for idx, (loteria, cantidad) in enumerate(conteo.items(), 1):
        porcentaje = (cantidad / len(df)) * 100
        barra = "█" * int(porcentaje / 3)
        print(f" {idx:2d}. {loteria:20s} │ {cantidad:4d} │ {porcentaje:5.1f}% {barra}")
    print("\n🏆 TOP 15 NÚMEROS MÁS COMUNES:")
    print("─" * 80)
    top = df["numero"].value_counts().head(15)
    for i, (num, cnt) in enumerate(top.items(), 1):
        loteria_top = df[df["numero"] == num]["loteria"].value_counts().idxmax()
        signo_top = df[df["numero"] == num]["serie"].mode()[0] if not df[df["numero"] == num]["serie"].empty else "N/A"
        print(f" {i:2d}. {num.zfill(4)} │ {cnt:3d}x │ Lotería: {loteria_top:15s} │ Signo: {signo_top}")

def analizar_todos_numeros(nombre_archivo):
    df = cargar_a_dataframe(nombre_archivo)
    if df.empty:
        return
    print("\n" + "="*80)
    print("📊 ESTADÍSTICAS DE NÚMEROS (0000-9999)")
    print("="*80)
    total_posibles = 10000
    numeros_unicos = df["numero"].unique()
    numeros_que_cayeron = len(numeros_unicos)
    numeros_que_no_cayeron = total_posibles - numeros_que_cayeron
    print(f"\n✅ Números que han salido: {numeros_que_cayeron} ({numeros_que_cayeron/total_posibles*100:.2f}%)")
    print(f"❌ Números que NO han salido: {numeros_que_no_cayeron} ({numeros_que_no_cayeron/total_posibles*100:.2f}%)")
    print("\n🔥 TOP 20 NÚMEROS MÁS REPETITIVOS:")
    print("─" * 80)
    top_20 = df["numero"].value_counts().head(20)
    for idx, (numero, freq) in enumerate(top_20.items(), 1):
        df_num = df[df["numero"] == numero]
        loteria_freq = df_num["loteria"].value_counts()
        loteria_top = loteria_freq.idxmax()
        loteria_count = loteria_freq.max()
        signo_freq = df_num[df_num["serie"] != "No disponible"]["serie"].value_counts()
        if len(signo_freq) > 0:
            signo_top = signo_freq.idxmax()
            signo_count = signo_freq.max()
        else:
            signo_top = "N/A"
            signo_count = 0
        print(f" {idx:2d}. {numero.zfill(4)}: {freq:3d}x │ Lotería: {loteria_top:12s}({loteria_count:2d}) │ Signo: {signo_top:10s}({signo_count:2d})")

def analizar_numeros_especificos(nombre_archivo):
    df = cargar_a_dataframe(nombre_archivo)
    if df.empty:
        return
    print("\n" + "="*80)
    print("🎯 ANÁLISIS DETALLADO DE NÚMEROS ESPECÍFICOS")
    print("="*80)
    numeros_objetivo = ["419", "116", "2710", "1012", "6888"]
    for numero in numeros_objetivo:
        df_num = df[df["numero"] == numero]
        if df_num.empty:
            print(f"\n❌ NÚMERO: {numero.zfill(4)} - No encontrado en histórico")
            continue
        total_apariciones = len(df_num)
        print(f"\n{'═'*80}")
        print(f"✅ NÚMERO: {numero.zfill(4)}")
        print(f"{'═'*80}")
        print(f"📊 Apariciones totales: {total_apariciones}")
        print(f"\n🎰 FRECUENCIA POR LOTERÍA:")
        print("─" * 80)
        freq_loteria = df_num["loteria"].value_counts().sort_values(ascending=False)
        for loteria, cnt in freq_loteria.items():
            porcentaje = (cnt / total_apariciones) * 100
            barra = "█" * int(porcentaje / 4)
            print(f" • {loteria:20s} │ {cnt:3d}x │ {porcentaje:5.1f}% {barra}")
        df_signos = df_num[df_num["serie"] != "No disponible"]
        if not df_signos.empty:
            print(f"\n♈ SIGNOS ZODIACALES PARA {numero.zfill(4)}:")
            print("─" * 80)
            freq_signos = df_signos["serie"].value_counts()
            for signo, cnt in freq_signos.items():
                porcentaje = (cnt / len(df_signos)) * 100
                print(f" ♈ {signo:15s} │ {cnt:3d}x │ {porcentaje:5.1f}%")

def entrenar_modelo_loteria_mejorado(df_ml):
    try:
        X = df_ml[['numero', 'loteria_encoded', 'fecha_ordinal']]
        y = df_ml['label']
        print("\n" + "="*80)
        print("🤖 MODELO DE IA - XGBOOST CON BALANCEO")
        print("="*80)
        print(f"\n📊 DISTRIBUCIÓN DE DATOS:")
        print(f" Clase 0 (No saldrá): {(y==0).sum():,}")
        print(f" Clase 1 (Saldrá): {(y==1).sum():,}")
        print(f" Ratio: 1:{(y==0).sum() / max((y==1).sum(), 1):.1f}")
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.3, random_state=42, stratify=y
        )
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        class_weights = compute_class_weight(
            'balanced',
            classes=np.unique(y_train),
            y=y_train
        )
        scale_pos_weight = class_weights[1] / class_weights[0]
        print(f"\n⚖️ PESOS DE CLASE:")
        print(f" Clase 0: {class_weights[0]:.3f}")
        print(f" Clase 1: {class_weights[1]:.3f}")
        print(f" Scale pos weight: {scale_pos_weight:.3f}")
        print(f"\n🔄 Aplicando SMOTE...")
        smote = SMOTE(random_state=42, k_neighbors=3)
        X_train_balanced, y_train_balanced = smote.fit_resample(X_train_scaled, y_train)
        print(f" ✅ Datos antes: {len(y_train):,}")
        print(f" ✅ Datos después: {len(y_train_balanced):,}")
        print(f" Clase 0: {(y_train_balanced==0).sum():,}")
        print(f" Clase 1: {(y_train_balanced==1).sum():,}")
        print(f"\n🚀 Entrenando modelo XGBoost optimizado...")
        modelo = XGBClassifier(
            n_estimators=300,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            scale_pos_weight=scale_pos_weight,
            min_child_weight=1,
            gamma=1,
            reg_alpha=0.5,
            reg_lambda=1.0,
            random_state=42,
            verbosity=0,
            n_jobs=-1
        )
        modelo.fit(
            X_train_balanced, y_train_balanced,
            verbose=False
        )
        y_pred = modelo.predict(X_test_scaled)
        y_pred_proba = modelo.predict_proba(X_test_scaled)[:, 1]
        print(f"\n📈 RESULTADOS DEL MODELO:")
        print("─" * 80)
        print(classification_report(y_test, y_pred,
            target_names=['No saldrá', 'Saldrá'],
            zero_division=0))
        cm = confusion_matrix(y_test, y_pred)
        print(f"\n📊 MATRIZ DE CONFUSIÓN:")
        print("─" * 80)
        print(f" True Negatives: {cm[0,0]:,}")
        print(f" False Positives: {cm[0,1]:,}")
        print(f" False Negatives: {cm[1,0]:,}")
        print(f" True Positives: {cm[1,1]:,}")
        print(f"\n🎯 BÚSQUEDA DE THRESHOLD ÓPTIMO:")
        print("─" * 80)
        precisions, recalls, thresholds = precision_recall_curve(y_test, y_pred_proba)
        f1_scores = 2 * (precisions * recalls) / (precisions + recalls + 1e-10)
        best_idx = np.argmax(f1_scores)
        best_threshold = thresholds[best_idx] if best_idx < len(thresholds) else 0.5
        print(f" Threshold óptimo: {best_threshold:.3f}")
        print(f" F1-Score: {f1_scores[best_idx]:.3f}")
        y_pred_optimized = (y_pred_proba >= best_threshold).astype(int)
        print(f"\n✅ RESULTADOS CON THRESHOLD ÓPTIMO ({best_threshold:.3f}):")
        print("─" * 80)
        print(classification_report(y_test, y_pred_optimized,
            target_names=['No saldrá', 'Saldrá'],
            zero_division=0))
        print(f"\n🎯 IMPORTANCIA DE CARACTERÍSTICAS:")
        print("─" * 80)
        feature_names = ['Número', 'Lotería', 'Fecha']
        importances = modelo.feature_importances_
        for name, imp in sorted(zip(feature_names, importances),
            key=lambda x: x[1], reverse=True):
            bar = "█" * int(imp * 50)
            print(f" {name:12s}: {imp:.3f} {bar}")
        return modelo, best_threshold
    except Exception as e:
        print(f"❌ Error en modelo: {str(e)}")
        import traceback
        traceback.print_exc()
        return None, 0.5

def analisis_con_modelo_mejorado():
    global modelo_ia
    try:
        with open(ruta_archivo, 'r', encoding='utf-8') as f:
            datos = json.load(f)
        filas = []
        for loteria, resultados in datos.items():
            for r in resultados:
                filas.append({
                    "numero": r['numero'].lstrip('0'),
                    "loteria": loteria,
                    "fecha": pd.to_datetime(r['fecha'])
                })
        df = pd.DataFrame(filas)
        if df.empty or len(df) < 100:
            print("\n⚠️ Datos insuficientes para entrenar modelo")
            return
        loteria_encoder = {lot: idx for idx, lot in enumerate(df['loteria'].unique())}
        df['loteria_encoded'] = df['loteria'].map(loteria_encoder)
        numeros = df['numero'].unique()
        fechas_ordenadas = sorted(df['fecha'].unique())
        data_ml = []
        print("\n🔄 Preparando dataset para modelo...")
        for i in range(len(fechas_ordenadas) - 1):
            fecha_actual = fechas_ordenadas[i]
            fecha_limite = fecha_actual + timedelta(days=30)
            df_proximos = df[(df['fecha'] > fecha_actual) & (df['fecha'] <= fecha_limite)]
            for num in numeros:
                for loteria, lot_code in loteria_encoder.items():
                    label = 1 if ((df_proximos['numero'] == num) &
                        (df_proximos['loteria'] == loteria)).any() else 0
                    data_ml.append({
                        'numero': int(num),
                        'loteria_encoded': lot_code,
                        'fecha_ordinal': fecha_actual.toordinal(),
                        'label': label
                    })
        df_ml = pd.DataFrame(data_ml)
        if len(df_ml) >= 100:
            modelo_ia, threshold = entrenar_modelo_loteria_mejorado(df_ml)
            if modelo_ia:
                print(f"\n💾 Modelo entrenado exitosamente")
                print(f" Threshold óptimo: {threshold:.3f}")
    except Exception as e:
        print(f"❌ Error: {str(e)}")

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
            guardar_resultado_loteria(combinado)
            copiar_json_a_static()
            generar_datos_ultimo_sorteo()
            generar_predicciones_diarias()
            import io
            import sys
            buffer = io.StringIO()
            old_stdout = sys.stdout
            sys.stdout = buffer
            analizar_patrones(ruta_archivo)
            analizar_todos_numeros(ruta_archivo)
            analizar_numeros_especificos(ruta_archivo)
            analisis_con_modelo_mejorado()
            sys.stdout = old_stdout
            analisis_texto = buffer.getvalue()
        print("\n✅ ¡Completado!")
    except Exception as e:
        analisis_texto = f"Error: {str(e)}"

@app.route('/health')
def health():
    return jsonify({"status": "ok"}), 200

@app.route("/")
def index():
    return render_template("index.html", calendario=CALENDARIO_LOTERIAS)

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

@app.route("/get-sorteos", methods=["GET"])
def get_sorteos():
    return jsonify(datos_ultimo_sorteo)

@app.route("/get-predicciones", methods=["GET"])
def get_predicciones():
    generar_predicciones_diarias()
    predicciones_formateadas = {}
    for loteria, pred in predicciones_diarias.items():
        if isinstance(pred, dict):
            predicciones_formateadas[loteria] = f"{pred['numero']} {pred['signo']}" if pred['signo'] != 'N/A' else pred['numero']
        else:
            predicciones_formateadas[loteria] = pred
    return jsonify(predicciones_formateadas)

@app.route("/get-calendario", methods=["GET"])
def get_calendario():
    return jsonify(CALENDARIO_LOTERIAS)

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory(carpeta_static, filename)

if __name__ == "__main__":
    crear_o_validar_archivo_json()
    asegurar_carpeta_static()
    copiar_json_a_static()
    puerto = int(os.environ.get('PORT', 8000))
    print("\n" + "="*70)
    print("🚀 SERVIDOR FLASK - KOYEB READY")
    print("="*70)
    print(f"\n✅ Puerto: {puerto}")
    print(f"✅ Health check: /health")
    print(f"✅ Modo: Production (HTTP)")
    print("\n" + "="*70 + "\n")
    app.run(host="0.0.0.0", port=puerto, debug=False)
