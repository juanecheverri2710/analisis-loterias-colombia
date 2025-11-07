<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="Análisis avanzado de loterías colombianas con IA - Predicciones basadas en 5 años de datos">
    <title>Análisis de Loterías Colombia - IA Predicciones</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
</head>
<body>
    <!-- NAVBAR -->
    <nav class="navbar">
        <div class="navbar-content">
            <span class="navbar-logo">🎰</span>
            <span>Análisis de Loterías Colombia</span>
        </div>
    </nav>

    <!-- CONTAINER PRINCIPAL -->
    <div class="container">
        <!-- HEADER -->
        <header class="header">
            <h1 class="main-title">Análisis de Loterías Colombianas</h1>
            <p class="subtitle">Predicciones con Inteligencia Artificial | 14 Loterías | 5 Años de Datos</p>
        </header>

        <!-- MAIN CONTENT -->
        <main class="main">
            <!-- ESTADÍSTICAS -->
            <section class="section-stats">
                <div class="stat-box">
                    <span class="stat-value">14</span>
                    <span class="stat-text">Loterías</span>
                </div>
                <div class="stat-box">
                    <span class="stat-value">5</span>
                    <span class="stat-text">Años</span>
                </div>
                <div class="stat-box">
                    <span class="stat-value">10K</span>
                    <span class="stat-text">Números</span>
                </div>
                <div class="stat-box">
                    <span class="stat-value">🤖</span>
                    <span class="stat-text">IA</span>
                </div>
            </section>

            <!-- CALENDARIO DE LOTERÍAS -->
            <section class="section-calendario">
                <h2 class="section-title">📅 Calendario de Loterías</h2>
                <div id="calendario" class="calendario-grid"></div>
            </section>

            <!-- SECCIÓN DE ACCIÓN -->
            <section class="section-action">
                <button id="btnAnalizar" class="btn-large">🚀 Iniciar Análisis Completo</button>
                <div class="status-msg" id="statusMsg"></div>
            </section>

            <!-- LOADING -->
            <section id="loadingSection" class="section-loading" style="display:none;">
                <div class="loading-box">
                    <div class="spinner-large"></div>
                    <div class="loading-title">Analizando Loterías...</div>
                    <div class="loading-desc">Procesando datos históricos y generando predicciones</div>
                    <div class="progress-bar-container">
                        <div class="progress-bar-fill" id="progressBar"></div>
                    </div>
                    <div class="loading-time" id="loadingTime">0 segundos</div>
                </div>
            </section>

            <!-- RESULTADOS DEL ÚLTIMO SORTEO -->
            <section id="sorteos" class="section-sorteos" style="display:none;">
                <h2 class="section-title">🎯 Últimos Sorteos</h2>
                <div id="sorteoGrid" class="sorteos-grid"></div>
            </section>

            <!-- PREDICCIONES DIARIAS -->
            <section id="predicciones" class="section-predicciones" style="display:none;">
                <h2 class="section-title">🎲 Predicciones para Hoy</h2>
                <p class="section-subtitle">Números recomendados según el análisis de frecuencia e IA</p>
                <div id="prediccionesGrid" class="predicciones-grid"></div>
            </section>

            <!-- NÚMEROS ESPECIALES -->
            <section id="numerosEspeciales" class="section-numeros-especiales" style="display:none;">
                <h2 class="section-title">✨ Análisis de Números Especiales</h2>
                <p class="section-subtitle">Probabilidad y estadísticas detalladas de números clave</p>
                <div id="numerosGrid" class="numeros-especiales-grid"></div>
            </section>

            <!-- RESULTADOS -->
            <section id="results" class="section-results" style="display:none;">
                <div class="results-header">
                    <h2 class="section-title">📊 Resultados Detallados</h2>
                    <a id="downloadLink" href="#" class="btn-download">📥 Descargar JSON</a>
                </div>
                <div class="results-box">
                    <pre id="resultsText"></pre>
                </div>
            </section>

            <!-- CARACTERÍSTICAS - AL FINAL -->
            <section class="section-features">
                <h2 class="section-title">✨ Características</h2>
                <div class="features-list">
                    <p><strong>14 Loterías Colombianas:</strong> Boyacá, Cruz Roja, Manizales, Cundinamarca, Tolima, Medellín, Santander, Huila, Risaralda, Bogotá, Meta, Quindío, Valle, Cauca</p>
                    <p><strong>Predicciones Inteligentes:</strong> Basadas en análisis de frecuencia del JSON histórico</p>
                    <p><strong>Modelo XGBoost:</strong> Algoritmo de Machine Learning con balanceo SMOTE</p>
                    <p><strong>5 Años de Datos:</strong> Más de 1,825 días de histórico analizado</p>
                    <p><strong>Análisis de Números:</strong> Probabilidad estimada, últimas apariciones e intervalo promedio</p>
                    <p><strong>Balanceo SMOTE:</strong> Para mejorar precisión en predicciones</p>
                    <p><strong>Predicciones Diarias:</strong> Según el día de juego de cada lotería (calendario actualizado)</p>
                </div>
            </section>
        </main>
    </div>

    <!-- FOOTER -->
    <footer class="footer">
        <p>🎰 Análisis de Loterías Colombia © 2025 | Datos procesados y analizados con IA avanzada</p>
    </footer>

    <script>
        const btnAnalizar = document.getElementById('btnAnalizar');
        const statusMsg = document.getElementById('statusMsg');
        const loadingSection = document.getElementById('loadingSection');
        const sorteoSection = document.getElementById('sorteos');
        const prediccionesSection = document.getElementById('predicciones');
        const numerosSection = document.getElementById('numerosEspeciales');
        const resultsSection = document.getElementById('results');
        const sorteoGrid = document.getElementById('sorteoGrid');
        const prediccionesGrid = document.getElementById('prediccionesGrid');
        const numerosGrid = document.getElementById('numerosGrid');
        const resultsText = document.getElementById('resultsText');
        const progressBar = document.getElementById('progressBar');
        const loadingTime = document.getElementById('loadingTime');

        // Calendario
        async function cargarCalendario() {
            try {
                const response = await fetch('/get-calendario');
                const calendario = await response.json();

                const calendarioDiv = document.getElementById('calendario');
                calendarioDiv.innerHTML = '';

                for (const [dia, loterias] of Object.entries(calendario)) {
                    const card = document.createElement('div');
                    card.className = 'calendario-card';
                    card.innerHTML = `
                        <h3>${dia}</h3>
                        <div class="loteria-badges-container">
                            ${loterias.map(l => `<span class="loteria-badge">${l}</span>`).join('')}
                        </div>
                    `;
                    calendarioDiv.appendChild(card);
                }
            } catch (error) {
                console.error('Error cargando calendario:', error);
            }
        }

        // Iniciar análisis
        btnAnalizar.addEventListener('click', async () => {
            btnAnalizar.disabled = true;
            statusMsg.textContent = '⏳ Iniciando análisis...';
            loadingSection.style.display = 'flex';
            sorteoSection.style.display = 'none';
            prediccionesSection.style.display = 'none';
            numerosSection.style.display = 'none';
            resultsSection.style.display = 'none';

            let startTime = Date.now();
            let progressValue = 0;

            const progressInterval = setInterval(() => {
                progressValue += Math.random() * 30;
                if (progressValue > 90) progressValue = 90;
                progressBar.style.width = progressValue + '%';

                const elapsed = Math.floor((Date.now() - startTime) / 1000);
                loadingTime.textContent = elapsed + ' segundos';
            }, 500);

            try {
                const response = await fetch('/start-analysis', { method: 'POST' });
                
                // Esperar a que se completen los resultados
                let intentos = 0;
                const maxIntentos = 60;

                const checkResults = setInterval(async () => {
                    intentos++;
                    const resultsResponse = await fetch('/get-results');
                    const data = await resultsResponse.json();

                    if (data.result && data.result !== 'Resultados aún no disponibles.') {
                        clearInterval(checkResults);
                        clearInterval(progressInterval);
                        progressBar.style.width = '100%';

                        // Cargar sorteos
                        const sorteosResponse = await fetch('/get-sorteos');
                        const sorteos = await sorteosResponse.json();
                        mostrarSorteos(sorteos);

                        // Cargar predicciones
                        const prediccionesResponse = await fetch('/get-predicciones');
                        const predicciones = await prediccionesResponse.json();
                        mostrarPredicciones(predicciones);

                        // Cargar análisis de números
                        const numerosResponse = await fetch('/get-analisis-numeros');
                        const numeros = await numerosResponse.json();
                        mostrarNumerosEspeciales(numeros);

                        // Mostrar resultados
                        resultsText.textContent = data.result;
                        resultsSection.style.display = 'block';

                        loadingSection.style.display = 'none';
                        statusMsg.textContent = '✅ ¡Análisis completado!';
                        btnAnalizar.disabled = false;
                    } else if (intentos >= maxIntentos) {
                        clearInterval(checkResults);
                        clearInterval(progressInterval);
                        statusMsg.textContent = '⚠️ Análisis en progreso. Intenta nuevamente en unos momentos.';
                        btnAnalizar.disabled = false;
                        loadingSection.style.display = 'none';
                    }
                }, 1000);

            } catch (error) {
                clearInterval(progressInterval);
                console.error('Error:', error);
                statusMsg.textContent = '❌ Error en el análisis';
                btnAnalizar.disabled = false;
                loadingSection.style.display = 'none';
            }
        });

        function mostrarSorteos(sorteos) {
            sorteoGrid.innerHTML = '';
            for (const [loteria, datos] of Object.entries(sorteos)) {
                const card = document.createElement('div');
                card.className = 'sorteo-card';
                card.innerHTML = `
                    <div class="sorteo-card-num">${datos.numero}</div>
                    <div class="sorteo-card-name">${loteria}</div>
                    <div class="sorteo-card-signo">${datos.signo}</div>
                    <div class="sorteo-card-fecha">${datos.fecha}</div>
                `;
                sorteoGrid.appendChild(card);
            }
            sorteoSection.style.display = 'block';
        }

        function mostrarPredicciones(predicciones) {
            prediccionesGrid.innerHTML = '';
            if (Object.keys(predicciones).length === 0) {
                prediccionesGrid.innerHTML = '<p style="grid-column: 1/-1; text-align: center; color: #999;">No hay predicciones para hoy</p>';
            } else {
                for (const [loteria, datos] of Object.entries(predicciones)) {
                    const card = document.createElement('div');
                    card.className = 'prediccion-card';
                    card.innerHTML = `
                        <div class="prediccion-loteria">${loteria}</div>
                        <div class="prediccion-numero">${datos.numero}</div>
                        <div class="prediccion-label">Predicción</div>
                        <div class="prediccion-frecuencia">${datos.frecuencia}x en 1 año</div>
                    `;
                    prediccionesGrid.appendChild(card);
                }
            }
            prediccionesSection.style.display = 'block';
        }

        function mostrarNumerosEspeciales(numeros) {
            numerosGrid.innerHTML = '';
            for (const [numero, datos] of Object.entries(numeros)) {
                const card = document.createElement('div');
                card.className = 'numero-especial-card';
                
                let loteriasHTML = '';
                if (Object.keys(datos.loterrias_donde_cayo).length > 0) {
                    loteriasHTML = '<strong>Donde más ha caído:</strong>' +
                        Object.entries(datos.loterrias_donde_cayo)
                            .sort((a, b) => b[1] - a[1])
                            .slice(0, 3)
                            .map(([lot, veces]) => `<div class="loteria-top">${lot}: ${veces}x</div>`)
                            .join('');
                }

                let intervaloHTML = '';
                if (datos.dias_entre_apariciones && datos.dias_entre_apariciones.promedio) {
                    intervaloHTML = `
                        <div class="numero-especial-intervalo">
                            <div>⏱️ Promedio: ${datos.dias_entre_apariciones.promedio} días</div>
                            <div style="font-size: 0.85em; opacity: 0.8;">Min: ${datos.dias_entre_apariciones.minimo}d | Max: ${datos.dias_entre_apariciones.maximo}d</div>
                        </div>
                    `;
                }

                card.innerHTML = `
                    <div class="numero-especial-header">
                        <div class="numero-especial-numero">${numero}</div>
                        <div class="numero-especial-prob" style="color: ${datos.probabilidad > 60 ? '#51cf66' : '#ff6b6b'};">${datos.probabilidad.toFixed(1)}%</div>
                    </div>
                    <div class="numero-especial-stats">
                        <div class="stat-item">
                            <span class="stat-label">Total</span>
                            <span class="stat-value">${datos.apariciones_total}</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-label">1 Año</span>
                            <span class="stat-value">${datos.apariciones_1ano}</span>
                        </div>
                    </div>
                    <div class="numero-especial-loterias">
                        ${loteriasHTML}
                    </div>
                    ${intervaloHTML}
                `;
                numerosGrid.appendChild(card);
            }
            numerosSection.style.display = 'block';
        }

        // Cargar calendario al iniciar
        cargarCalendario();
    </script>
</body>
</html>
