from flask import Flask, jsonify, render_template
import os
import sys

# ==================== CONFIGURATION ====================
app = Flask(__name__)
app.config['PREFERRED_URL_SCHEME'] = 'https'
app.config['TRUST_REMOTE_ADDR'] = True

# ==================== HEALTH ROUTES (MUST BE FIRST) ====================

@app.route('/')
def home():
    try:
        return render_template('index.html'), 200
    except:
        return "<h1>✅ Flask Lottery App Online!</h1>", 200


@app.route('/api/health')
def health():
    return jsonify({"status": "ok", "app": "analisis_loterias"}), 200

# ==================== LAZY LOAD ALL OTHER CODE ====================
# Import the rest ONLY when needed

def load_app_functions():
    """Load heavy functions only when first request comes in"""
    global datos_ultimo_sorteo, predicciones_diarias
    
    # Rutas y variables globales
    # ... ADD REST OF YOUR CODE HERE ...
    
# Initialize variables
datos_ultimo_sorteo = {}
predicciones_diarias = {}

# ==================== END ====================

# ==================== END ROUTES ====================

# 📅 CALENDARIO ACTUALIZADO DE LOTERÍAS
# 0=Lunes, 1=Martes, 2=Miércoles, 3=Jueves, 4=Viernes, 5=Sábado, 6=Domingo
DIAS_LOTERIA = {
    "Astro Luna": [0, 1, 2, 3, 4, 5, 6],    # Todos los días
    "Astro Sol": [0, 1, 2, 3, 4, 5, 6],     # Todos los días
    "Cundinamarca": [0],                     # Lunes
    "Tolima": [0],                           # Lunes
    "Cruz Roja": [1],                        # Martes
    "Huila": [1],                            # Martes
    "Manizales": [2],                        # Miércoles
    "Valle": [2],                            # Miércoles
    "Meta": [2],                             # Miércoles
    "Bogotá": [3],                           # Jueves
    "Quindío": [3],                          # Jueves
    "Medellín": [4],                         # Viernes
    "Risaralda": [4],                        # Viernes
    "Santander": [4],                        # Viernes
    "Boyacá": [5],                           # Sábado
    "Cauca": [5]                             # Sábado
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
    resultados_luna = obtener_resultados_superastro_mejorado('luna', fecha_inicio)
    resultados_totales["Astro Luna"] = resultados_luna

    print("\n🔄 Consultando Astro Sol...")
    resultados_sol = obtener_resultados_superastro_mejorado('sol', fecha_inicio)
    resultados_totales["Astro Sol"] = resultados_sol

    return resultados_totales

# ==================== CONSULTA HISTÓRICA ====================

def obtener_historico_completo_5anos():
    """Obtiene el histórico completo de los últimos 5 años de todas las loterías"""
    print("\n" + "="*100)
    print("📅 CONSULTANDO HISTÓRICO COMPLETO - ÚLTIMOS 5 AÑOS")
    print("="*100)
    
    historico_completo = {}
    
    # URLs de las loterías
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
    
    for nombre, url in loterias_urls.items():
        contador += 1
        print(f"\n[{contador}/{total_loterias}] 📥 Consultando {nombre}...")
        
        try:
            response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15, verify=False)
            
            if response.status_code != 200:
                print(f"    ⚠️ Error HTTP {response.status_code}")
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
                print(f"    ⚠️ Tabla no encontrada")
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
            
            print(f"    ✅ {len(resultados_loteria)} registros obtenidos")
            time.sleep(1)  # Esperar 1 segundo entre solicitudes
            
        except Exception as e:
            print(f"    ❌ Error: {str(e)}")
            historico_completo[nombre] = []
    
    # Obtener Astro Luna y Astro Sol
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
    
    # Resumen
    print("\n📊 RESUMEN DEL HISTÓRICO:")
    print("─" * 100)
    total_registros = 0
    for loteria, registros in historico_completo.items():
        cantidad = len(registros)
        total_registros += cantidad
        print(f"   {loteria:20s}: {cantidad:6d} registros")
    
    print("─" * 100)
    print(f"   {'TOTAL':20s}: {total_registros:6d} registros")
    
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

# ==================== ANÁLISIS DE NÚMEROS ESPECIALES ====================

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

            # Calcular frecuencia global (veces que cae por año promedio)
            apariciones_total = numero_info["apariciones_total"]
            if apariciones_total > 0:
                frecuencia_anual = (apariciones_total / 5)  # 5 años de datos
                numero_info["probabilidad"] = min(100, (frecuencia_anual / 16) * 100)  # Normalizado a 100

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

                        # Predicción de próxima aparición
                        ultima_fecha = todas_fechas[0][0]
                        proxima_fecha_estimada = ultima_fecha + timedelta(days=promedio_dias)
                        numero_info["proxima_prediccion"] = proxima_fecha_estimada.strftime("%Y-%m-%d")

                print(f"\n✅ APARICIONES TOTALES: {apariciones_total}")
                print(f"   • Último año (365 días): {numero_info['apariciones_1ano']}")
                print(f"   • Últimos 2 años (730 días): {numero_info['apariciones_2anos']}")
                print(f"   • Últimos 3 años (1095 días): {numero_info['apariciones_3anos']}")

                print(f"\n🎰 LOTERÍAS DONDE MÁS HA CAÍDO:")
                print("─" * 100)
                sorted_loterias = sorted(numero_info["loterrias_donde_cayo"].items(), 
                                        key=lambda x: x[1], reverse=True)
                for loteria, veces in sorted_loterias[:5]:
                    porcentaje = (veces / apariciones_total) * 100
                    barra = "█" * int(porcentaje / 3)
                    print(f"   {loteria:20s}: {veces:3d}x ({porcentaje:5.1f}%) {barra}")

                print(f"\n📅 ÚLTIMAS APARICIONES:")
                print("─" * 100)
                for fecha, loteria in numero_info["ultimas_fechas"]:
                    print(f"   {fecha} → {loteria}")

                if "dias_entre_apariciones" in numero_info and numero_info["dias_entre_apariciones"]:
                    print(f"\n⏱️ ANÁLISIS DE INTERVALO:")
                    print("─" * 100)
                    dias_info = numero_info["dias_entre_apariciones"]
                    print(f"   Promedio entre apariciones: {dias_info['promedio']} días")
                    print(f"   Mínimo: {dias_info['minimo']} días")
                    print(f"   Máximo: {dias_info['maximo']} días")
                    print(f"   🎯 Próxima predicción: {numero_info['proxima_prediccion']}")

                print(f"\n📊 PROBABILIDAD ESTIMADA: {numero_info['probabilidad']:.1f}%")

            analisis_numeros_especiales[numero_especial] = numero_info

        print("\n" + "="*100)
        print("✅ ANÁLISIS COMPLETADO")
        print("="*100)

    except Exception as e:
        print(f"❌ Error en análisis de números especiales: {str(e)}")
        import traceback
        traceback.print_exc()

def generar_predicciones_diarias():
    """Genera predicciones de números ganadores según el día de hoy con validación de fechas"""
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
                            num = sorteo.get("numero", "0").strip().lstrip('0') or "0"
                            signo = sorteo.get("serie", "No disponible")
                            numeros_freq[num] = numeros_freq.get(num, 0) + 1
                            
                            # Para Astro Luna y Astro Sol, guardar signos
                            if loteria in ["Astro Luna", "Astro Sol"]:
                                if num not in signos_freq:
                                    signos_freq[num] = {}
                                signos_freq[num][signo] = signos_freq[num].get(signo, 0) + 1

                        # Ordenar por frecuencia y tomar el más probable
                        top_numeros = sorted(numeros_freq.items(), key=lambda x: x[1], reverse=True)[:5]

                        # Seleccionar el número con mayor frecuencia
                        if top_numeros:
                            numero_predicho = top_numeros[0][0].zfill(4)
                            
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
                                    "frecuencia": top_numeros[0][1]
                                }
                                print(f"🎯 {loteria}: {numero_predicho} ({signo_top}) - {top_numeros[0][1]} apariciones")
                            else:
                                predicciones_diarias[loteria] = {
                                    "numero": numero_predicho,
                                    "signo": "N/A",
                                    "frecuencia": top_numeros[0][1]
                                }
                                print(f"🎯 {loteria}: {numero_predicho} - {top_numeros[0][1]} apariciones")

        print(f"\n✅ Predicciones generadas para HOY ({dias_nombres[hoy_dia]})")
        print(f"   Loterías que juegan hoy: {len(predicciones_diarias)}")

    except Exception as e:
        print(f"⚠️ Error generando predicciones: {str(e)}")
        import traceback
        traceback.print_exc()

# ==================== ANÁLISIS DE DATOS ====================

def cargar_a_dataframe(nombre_archivo):
    """Carga datos del JSON a DataFrame de pandas"""
    try:
        with open(nombre_archivo, 'r', encoding='utf-8') as f:
            datos = json.load(f)
    except:
        return pd.DataFrame()

    filas = []
    for loteria, sorteos in datos.items():
        for r in sorteos:
            numero_limpio = r['numero'].strip().lstrip('0') if r['numero'].strip().lstrip('0') else '0'
            filas.append({
                'loteria': loteria,
                'numero': numero_limpio,
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
    """Análisis general de patrones en los datos"""
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
        print(f"  {idx:2d}. {loteria:20s} │ {cantidad:4d} │ {porcentaje:5.1f}% {barra}")

    print("\n🏆 TOP 15 NÚMEROS MÁS COMUNES:")
    print("─" * 80)
    top = df["numero"].value_counts().head(15)
    for i, (num, cnt) in enumerate(top.items(), 1):
        loteria_top = df[df["numero"] == num]["loteria"].value_counts().idxmax()
        signo_top = df[df["numero"] == num]["serie"].mode()[0] if not df[df["numero"] == num]["serie"].empty else "N/A"
        print(f"  {i:2d}. {num.zfill(4)} │ {cnt:3d}x │ Lotería: {loteria_top:15s} │ Signo: {signo_top}")

def analizar_todos_numeros(nombre_archivo):
    """Estadísticas de todos los números posibles"""
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

        print(f"  {idx:2d}. {numero.zfill(4)}: {freq:3d}x │ Lotería: {loteria_top:12s}({loteria_count:2d}) │ Signo: {signo_top:10s}({signo_count:2d})")

def analizar_numeros_especificos(nombre_archivo):
    """Análisis detallado de números específicos"""
    df = cargar_a_dataframe(nombre_archivo)
    if df.empty:
        return

    print("\n" + "="*80)
    print("🎯 ANÁLISIS DETALLADO DE NÚMEROS TOP 5")
    print("="*80)

    # Analizar los TOP 5 números más frecuentes
    top_numeros = df["numero"].value_counts().head(5).index.tolist()

    for numero in top_numeros:
        df_num = df[df["numero"] == numero]
        if df_num.empty:
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
            print(f"  • {loteria:20s} │ {cnt:3d}x │ {porcentaje:5.1f}% {barra}")

        df_signos = df_num[df_num["serie"] != "No disponible"]
        if not df_signos.empty:
            print(f"\n♈ SIGNOS ZODIACALES PARA {numero.zfill(4)}:")
            print("─" * 80)
            freq_signos = df_signos["serie"].value_counts()
            for signo, cnt in freq_signos.items():
                porcentaje = (cnt / len(df_signos)) * 100
                print(f"  ♈ {signo:15s} │ {cnt:3d}x │ {porcentaje:5.1f}%")

# ==================== MODELO DE INTELIGENCIA ARTIFICIAL ====================

def entrenar_modelo_loteria_mejorado(df_ml):
    """Entrena modelo XGBoost con balanceo SMOTE"""
    try:
        X = df_ml[['numero', 'loteria_encoded', 'fecha_ordinal']]
        y = df_ml['label']

        print("\n" + "="*80)
        print("🤖 MODELO DE IA - XGBOOST CON BALANCEO")
        print("="*80)

        print(f"\n📊 DISTRIBUCIÓN DE DATOS:")
        print(f"   Clase 0 (No saldrá): {(y==0).sum():,}")
        print(f"   Clase 1 (Saldrá): {(y==1).sum():,}")
        print(f"   Ratio: 1:{(y==0).sum() / max((y==1).sum(), 1):.1f}")

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
        print(f"   Clase 0: {class_weights[0]:.3f}")
        print(f"   Clase 1: {class_weights[1]:.3f}")
        print(f"   Scale pos weight: {scale_pos_weight:.3f}")

        print(f"\n🔄 Aplicando SMOTE...")
        smote = SMOTE(random_state=42, k_neighbors=3)
        X_train_balanced, y_train_balanced = smote.fit_resample(X_train_scaled, y_train)

        print(f"   ✅ Datos antes: {len(y_train):,}")
        print(f"   ✅ Datos después: {len(y_train_balanced):,}")
        print(f"      Clase 0: {(y_train_balanced==0).sum():,}")
        print(f"      Clase 1: {(y_train_balanced==1).sum():,}")

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

        modelo.fit(X_train_balanced, y_train_balanced, verbose=False)

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
        print(f"   True Negatives: {cm[0,0]:,}")
        print(f"   False Positives: {cm[0,1]:,}")
        print(f"   False Negatives: {cm[1,0]:,}")
        print(f"   True Positives: {cm[1,1]:,}")

        print(f"\n🎯 BÚSQUEDA DE THRESHOLD ÓPTIMO:")
        print("─" * 80)
        precisions, recalls, thresholds = precision_recall_curve(y_test, y_pred_proba)
        f1_scores = 2 * (precisions * recalls) / (precisions + recalls + 1e-10)
        best_idx = np.argmax(f1_scores)
        best_threshold = thresholds[best_idx] if best_idx < len(thresholds) else 0.5

        print(f"   Threshold óptimo: {best_threshold:.3f}")
        print(f"   F1-Score: {f1_scores[best_idx]:.3f}")

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
            print(f"   {name:12s}: {imp:.3f} {bar}")

        return modelo, best_threshold

    except Exception as e:
        print(f"❌ Error en modelo: {str(e)}")
        import traceback
        traceback.print_exc()
        return None, 0.5

def analisis_con_modelo_mejorado():
    """Prepara datos y entrena el modelo de IA"""
    global modelo_ia
    try:
        with open(ruta_archivo, 'r', encoding='utf-8') as f:
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
                        'numero': int(num) if num.isdigit() else 0,
                        'loteria_encoded': lot_code,
                        'fecha_ordinal': fecha_actual.toordinal(),
                        'label': label
                    })

        df_ml = pd.DataFrame(data_ml)

        if len(df_ml) >= 100:
            modelo_ia, threshold = entrenar_modelo_loteria_mejorado(df_ml)
            if modelo_ia:
                print(f"\n💾 Modelo entrenado exitosamente")
                print(f"   Threshold óptimo: {threshold:.3f}")

    except Exception as e:
        print(f"❌ Error: {str(e)}")

# ==================== PROCESO PRINCIPAL ====================

def ejecutar_scraping_y_analisis():
    """Proceso principal: scraping, análisis y entrenamiento del modelo"""
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

            # Capturar análisis en texto
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

@app.route('/static/<path:filename>')
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

    print("\n" + "="*70)
    print("🚀 SERVIDOR FLASK - ANÁLISIS DE LOTERÍAS COLOMBIA")
    print("="*70)
    
    print("\n📅 CALENDARIO DE LOTERÍAS:")
    print("─" * 70)
    dias_nombres = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    for idx, dia_nombre in enumerate(dias_nombres):
        loterias_hoy = [lot for lot, dias in DIAS_LOTERIA.items() if idx in dias]
        print(f"  {dia_nombre:12s}: {', '.join(loterias_hoy)}")
    
    print("\n✅ Ejecutando en HTTP")
    print(f"📍 Local: http://localhost:{puerto}")
    print(f"📱 Red: http://{local_ip}:{puerto}")
    print("\n🌐 PARA NGROK (NUEVA TERMINAL):")
    print("   ngrok http 5000")
    print("\n" + "="*70 + "\n")

   app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)import os
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)




