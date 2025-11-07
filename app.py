import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime, timedelta
from collections import Counter
import pandas as pd
import numpy as np
from flask import Flask, jsonify
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier
from imblearn.over_sampling import SMOTE

# ✅ ADICIÓN 1: Inicializar Flask
app = Flask(__name__)

def obtener_resultados_loteria_tabla(nombre, url):
    resultados = []
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        if response.status_code != 200:
            print(f"Error HTTP en {nombre}: {response.status_code}")
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
            print(f"No se encontró tabla de resultados para {nombre}")
            return resultados
        
        filas = tabla_deseada.find_all("tr")[1:]
        fecha_limite = datetime.now().replace(year=datetime.now().year - 5)
        
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
                    "fecha": fecha.strftime("%Y-%m-%d")  # Formato uniforme ISO
                })

        print(f"{nombre}: {len(resultados)} resultados obtenidos (últimos 5 años, tabla)")
        return resultados

    except Exception as e:
        print(f"Error procesando {nombre}: {e}")
        return resultados

def obtener_resultados_loteria_risaralda(nombre, url):
    return obtener_resultados_loteria_tabla(nombre, url)

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
        if nombre == "Risaralda":
            resultados = obtener_resultados_loteria_risaralda(nombre, url)
        else:
            resultados = obtener_resultados_loteria_tabla(nombre, url)
        resultados_totales[nombre] = resultados

    return resultados_totales

# Función para analizar patrones estadísticos de los datos extraídos
def analizar_patrones(nombre_archivo):
    with open(nombre_archivo, "r", encoding="utf-8") as f:
        datos = json.load(f)
    
    todos_los_numeros = []
    secuencias = {}
    
    for loteria, sorteos in datos.items():
        secuencia = []
        for resultado in sorteos:
            numero = resultado["numero"].strip().lstrip("0")
            if numero.isdigit():
                todos_los_numeros.append(numero)
                secuencia.append(numero)
        secuencias[loteria] = secuencia[-5:]

    frecuencias = Counter(todos_los_numeros)
    print("Top 10 números más repetidos:")
    for numero, repeticiones in frecuencias.most_common(10):
        print(f"{numero}: {repeticiones} veces")
    
    for loteria, ultimos_numeros in secuencias.items():
        print(f"Últimas 5 secuencias de {loteria}: {ultimos_numeros}")

# Carga los resultados a un DataFrame de pandas para análisis más avanzado
def cargar_a_dataframe(nombre_archivo):
    with open(nombre_archivo, "r", encoding="utf-8") as f:
        datos = json.load(f)
    filas = []
    for loteria, sorteos in datos.items():
        for resultado in sorteos:
            filas.append({
                "loteria": loteria,
                "numero": resultado["numero"].strip().lstrip("0"),
                "fecha": resultado["fecha"]
            })
    return pd.DataFrame(filas)

def top_numeros_pandas(df, top=10):
    print(df["numero"].value_counts().head(top))

# ✅ ADICIÓN 2: Machine Learning con XGBoost
def entrenar_modelo_ia(nombre_archivo):
    """Entrena modelo XGBoost con balanceo SMOTE"""
    try:
        with open(nombre_archivo, "r", encoding="utf-8") as f:
            datos = json.load(f)

        filas = []
        for loteria, resultados in datos.items():
            for r in resultados:
                num_limpio = r['numero'].lstrip('0') if r['numero'].lstrip('0') else '0'
                filas.append({
                    "numero": num_limpio,
                    "loteria": loteria,
                    "fecha": pd.to_datetime(r['fecha'])
                })

        df = pd.DataFrame(filas)

        if df.empty or len(df) < 100:
            print("\n⚠️ Datos insuficientes para entrenar modelo")
            return None

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
                        'numero': int(num) if num.isdigit() else 0,
                        'loteria_encoded': lot_code,
                        'fecha_ordinal': fecha_actual.toordinal(),
                        'label': label
                    })

        df_ml = pd.DataFrame(data_ml)

        if len(df_ml) >= 100:
            X = df_ml[['numero', 'loteria_encoded', 'fecha_ordinal']]
            y = df_ml['label']

            print(f"\n📊 DISTRIBUCIÓN DE DATOS:")
            print(f" Clase 0 (No saldrá): {(y==0).sum():,}")
            print(f" Clase 1 (Saldrá): {(y==1).sum():,}")

            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.3, random_state=42, stratify=y
            )

            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)

            print(f"\n🔄 Aplicando SMOTE...")
            smote = SMOTE(random_state=42, k_neighbors=3)
            X_train_balanced, y_train_balanced = smote.fit_resample(X_train_scaled, y_train)

            print(f" ✅ Datos antes: {len(y_train):,}")
            print(f" ✅ Datos después: {len(y_train_balanced):,}")

            print(f"\n🚀 Entrenando modelo XGBoost...")
            modelo = XGBClassifier(
                n_estimators=300,
                max_depth=6,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=42,
                verbosity=0,
                n_jobs=-1
            )

            modelo.fit(X_train_balanced, y_train_balanced, verbose=False)

            y_pred = modelo.predict(X_test_scaled)
            accuracy = (y_pred == y_test).mean()

            print(f"\n📈 Precisión del modelo: {accuracy:.2%}")
            print(f"✅ Modelo entrenado exitosamente")

            return modelo

    except Exception as e:
        print(f"❌ Error en modelo: {str(e)}")
        return None

# ✅ ADICIÓN 3: Rutas Flask para API
@app.route("/get-patrones", methods=["GET"])
def get_patrones():
    """API para obtener patrones"""
    try:
        return jsonify({
            "status": "success",
            "message": "Patrones disponibles"
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/get-modelo", methods=["GET"])
def get_modelo():
    """API para obtener info del modelo IA"""
    try:
        return jsonify({
            "status": "success",
            "modelo": "XGBoost con SMOTE",
            "estado": "Entrenado"
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    # Primero obtenemos y guardamos los resultados
    print("📥 Descargando datos...")
    resultados = obtener_todas_loterias()
    with open("resultados_loterias.json", "w", encoding="utf-8") as f:
        json.dump(resultados, f, indent=2, ensure_ascii=False)
    print("Resultados guardados en resultados_loterias.json")

    # Luego analizamos patrones simples
    print("\n📊 Analizando patrones...")
    analizar_patrones("resultados_loterias.json")

    # Análisis avanzado con pandas
    print("\n📈 Cargando en DataFrame...")
    df = cargar_a_dataframe("resultados_loterias.json")
    print("\nTop 10 números más comunes según pandas:")
    top_numeros_pandas(df)

    # ✅ ADICIÓN 4: Entrenar modelo IA
    print("\n🤖 Entrenando modelo de IA...")
    modelo = entrenar_modelo_ia("resultados_loterias.json")

    # ✅ ADICIÓN 5: Iniciar servidor Flask
    print("\n🚀 Iniciando servidor Flask...")
    app.run(host='0.0.0.0', port=5000, debug=False)
