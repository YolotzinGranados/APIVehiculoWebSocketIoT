(() => {
  'use strict';

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const state = {
    role: null,
    vehicles: [],
    vehicle: null,
    vehicleId: null,
    commands: [],
    demos: [],
    history: [],
    selectedDemoId: null,
    selectedDemoMoves: [],
    ws: null,
    wsVehicleId: null,
    wsPing: null,
    wsRetry: null,
    healthTimer: null,
    events: [],
    page: 'control',
  };

  const COMMAND_ALIASES = {
    AVANZAR: ['AVANZAR', 'ADELANTE'],
    RETROCEDER: ['RETROCEDER', 'ATRAS', 'ATRÁS'],
    IZQUIERDA: ['IZQUIERDA', 'GIRAR_IZQUIERDA'],
    DERECHA: ['DERECHA', 'GIRAR_DERECHA'],
    SUBIR_PALA: ['SUBIR_PALA', 'SUBIR_BRAZO'],
    BAJAR_PALA: ['BAJAR_PALA', 'BAJAR_BRAZO'],
    PALA_IZQUIERDA: ['PALA_IZQUIERDA', 'ABRIR_PALA'],
    PALA_DERECHA: ['PALA_DERECHA', 'CERRAR_PALA'],
    MUTE: ['MUTE', 'MUTEAR', 'MUTEAR_SONIDO'],
    LUCES: ['LUCES'],
    VELOCIDAD: ['VELOCIDAD', 'CAMBIO_VELOCIDAD'],
    ALEATORIO: ['ALEATORIO', 'MOVIMIENTO_ALEATORIO', 'BOTON_ALEATORIO'],
    DETENER: ['DETENER', 'DETENER_TODO', 'STOP'],
  };

  const PAGE_NAMES = {
    control: 'Control del vehículo',
    demos: 'Secuencias DEMO',
    history: 'Historial de movimientos',
    admin: 'Administración',
  };

  function normalize(value) {
    return String(value ?? '')
      .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
      .trim().toUpperCase().replace(/[\s-]+/g, '_');
  }

  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, (char) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[char]));
  }

  function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    $('#toast-region').appendChild(toast);
    window.setTimeout(() => toast.remove(), 3800);
  }

  async function api(path, options = {}) {
    const headers = new Headers(options.headers || {});
    const config = { ...options, headers, credentials: 'same-origin' };
    if (config.body && typeof config.body !== 'string') {
      headers.set('Content-Type', 'application/json');
      config.body = JSON.stringify(config.body);
    }
    const response = await fetch(path, config);
    const contentType = response.headers.get('content-type') || '';
    const data = contentType.includes('application/json') ? await response.json() : null;
    if (!response.ok) {
      const message = data?.error?.mensaje || data?.detail || `Error HTTP ${response.status}`;
      if (response.status === 401 && !path.startsWith('/dashboard/auth/')) {
        showLogin('Tu sesión expiró. Inicia sesión nuevamente.');
      }
      throw new Error(message);
    }
    return data;
  }

  function showLogin(message = '') {
    closeSocket();
    $('#app-shell').hidden = true;
    $('#login-screen').hidden = false;
    $('#login-error').textContent = message;
    $('#api-key-input').value = '';
  }

  function showApp(role) {
    state.role = role;
    $('#login-screen').hidden = true;
    $('#app-shell').hidden = false;
    $('#role-label').textContent = role === 'admin' ? 'Administrador' : 'Control';
    $$('.admin-only').forEach((element) => { element.hidden = role !== 'admin'; });
  }

  function setApiStatus(ok, text) {
    const element = $('#api-status');
    element.innerHTML = `<span class="status-dot ${ok ? 'green' : 'red'}"></span><span>${escapeHtml(text)}</span>`;
    $('#metric-api').textContent = ok ? 'En línea' : 'Sin conexión';
    $('#metric-api-foot').textContent = ok ? 'API y base de datos disponibles' : 'No se pudo consultar /health';
  }

  function setWsStatus(ok, text) {
    $('#ws-status').innerHTML = `<span class="status-dot ${ok ? 'green' : 'red'}"></span><span>${escapeHtml(text)}</span>`;
  }

  function formatDate(value) {
    if (!value) return '—';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return new Intl.DateTimeFormat('es-MX', { dateStyle: 'short', timeStyle: 'medium' }).format(date);
  }

  function relativeTime(value) {
    if (!value) return 'Sin registro';
    return formatDate(value);
  }

  function currentVehicle() {
    return state.vehicle || state.vehicles.find((vehicle) => vehicle.id_vehiculo === state.vehicleId) || null;
  }

  function findCommand(key) {
    const aliases = COMMAND_ALIASES[key] || [key];
    const normalizedAliases = aliases.map(normalize);
    return state.commands.find((command) => command.activo && normalizedAliases.includes(normalize(command.nombre)));
  }

  function renderVehicleSelector() {
    const select = $('#vehicle-select');
    if (!state.vehicles.length) {
      select.innerHTML = '<option value="">No hay vehículos registrados</option>';
      return;
    }
    select.innerHTML = state.vehicles.map((vehicle) =>
      `<option value="${vehicle.id_vehiculo}" ${vehicle.id_vehiculo === state.vehicleId ? 'selected' : ''}>${escapeHtml(vehicle.nombre)} · #${vehicle.id_vehiculo}</option>`
    ).join('');
  }

  async function loadVehicles(preferredId = null) {
    state.vehicles = await api('/vehiculos?incluir_detalle=true');
    if (!Array.isArray(state.vehicles)) state.vehicles = [];
    const selected = state.vehicles.find((vehicle) => vehicle.id_vehiculo === preferredId)
      || state.vehicles.find((vehicle) => vehicle.id_vehiculo === state.vehicleId)
      || state.vehicles[0]
      || null;
    renderVehicleSelector();
    if (selected) await selectVehicle(selected.id_vehiculo);
    else renderNoVehicle();
  }

  function renderNoVehicle() {
    state.vehicle = null;
    state.vehicleId = null;
    state.commands = [];
    state.demos = [];
    state.history = [];
    renderVehicleSelector();
    $('#metric-device').textContent = 'Sin vehículo';
    $('#metric-command').textContent = '—';
    $('#metric-commands').textContent = '0';
    $('#vehicle-name-visual').textContent = 'Sin vehículo';
    $('#vehicle-model-visual').textContent = 'Registra un vehículo para comenzar';
    $('#catalog-list').innerHTML = '<div class="empty-state small-empty">No hay comandos disponibles.</div>';
    $('#demo-list').innerHTML = '<div class="empty-state">No hay secuencias registradas.</div>';
    $('#history-body').innerHTML = '<tr><td colspan="4" class="table-empty">No hay vehículo seleccionado.</td></tr>';
    updateControlAvailability();
    closeSocket();
  }

  async function selectVehicle(id) {
    const numericId = Number(id);
    if (!numericId || numericId === state.vehicleId && state.vehicle) return;
    state.vehicleId = numericId;
    state.events = [];
    renderEvents();
    const cached = state.vehicles.find((vehicle) => vehicle.id_vehiculo === numericId);
    state.vehicle = cached || null;
    renderVehicleSelector();
    closeSocket();
    try {
      const [vehicle, commands, demos, history, status] = await Promise.all([
        api(`/vehiculos/${numericId}`),
        api(`/vehiculos/${numericId}/comandos`),
        api(`/vehiculos/${numericId}/demos`),
        api(`/vehiculos/${numericId}/historial`),
        api(`/vehiculos/${numericId}/estado`),
      ]);
      if (state.vehicleId !== numericId) return;
      state.vehicle = vehicle;
      state.commands = Array.isArray(commands) ? commands : [];
      state.demos = Array.isArray(demos) ? demos : [];
      state.history = history?.movimientos || [];
      state.vehicle.estado = status;
      renderVehicle();
      renderCommands();
      renderHistory();
      renderDemos();
      renderAdminCommands();
      connectSocket(numericId);
    } catch (error) {
      showToast(`No se pudo cargar el vehículo: ${error.message}`, 'error');
    }
  }

  function renderVehicle() {
    const vehicle = currentVehicle();
    if (!vehicle) return;
    const status = vehicle.estado || {};
    $('#vehicle-name-visual').textContent = vehicle.nombre || 'Vehículo IoT';
    $('#vehicle-model-visual').textContent = vehicle.modelo || vehicle.descripcion || 'Vehículo remoto';
    $('#vehicle-subtitle').textContent = vehicle.descripcion || 'Información del vehículo seleccionado.';
    $('#device-mcu').textContent = vehicle.microcontrolador || 'No especificado';
    $('#device-id').textContent = `#${vehicle.id_vehiculo}`;
    $('#device-updated').textContent = relativeTime(status.fecha_actualizacion);
    $('#metric-device').textContent = status.conectado ? 'Conectado' : 'Desconectado';
    $('#metric-device-foot').textContent = status.fecha_actualizacion ? `Actualizado ${formatDate(status.fecha_actualizacion)}` : 'Sin estado registrado';
    $('#metric-command').textContent = status.comando || '—';
    $('#metric-command-foot').textContent = status.fecha_actualizacion ? formatDate(status.fecha_actualizacion) : 'Esperando actividad';
    $('#metric-commands').textContent = String(state.commands.filter((command) => command.activo).length);
  }

  function renderCommands() {
    const active = state.commands.filter((command) => command.activo);
    $('#catalog-count').textContent = `${state.commands.length} comandos`;
    if (!state.commands.length) {
      $('#catalog-list').innerHTML = '<div class="empty-state small-empty">Este vehículo todavía no tiene comandos.</div>';
    } else {
      $('#catalog-list').innerHTML = state.commands.map((command) => `
        <div class="catalog-chip ${command.activo ? '' : 'inactive'}">
          <span class="code">${escapeHtml(command.codigo)}</span>
          <span>${escapeHtml(command.nombre)}</span>
          ${command.activo ? `<button class="catalog-send" type="button" data-send-command-id="${command.id_comando}">Enviar</button>` : '<span>· inactivo</span>'}
        </div>`).join('');
      $$('[data-send-command-id]').forEach((button) => button.addEventListener('click', () => sendCommandById(Number(button.dataset.sendCommandId))));
    }
    $('#metric-commands').textContent = String(active.length);
    updateControlAvailability();
  }

  function updateControlAvailability() {
    $$('[data-command]').forEach((button) => {
      const command = findCommand(button.dataset.command);
      button.disabled = !command || !state.vehicleId;
      button.title = command ? `Enviar ${command.nombre}` : `No existe un comando activo para ${button.dataset.command}`;
    });
  }

  async function sendCommand(key) {
    if (!state.vehicleId) return showToast('Selecciona un vehículo primero.', 'error');
    const command = findCommand(key);
    if (!command) return showToast(`No hay un comando activo para ${key}. Revisa el catálogo.`, 'error');
    await sendCommandById(command.id_comando, command);
  }

  async function sendCommandById(commandId, knownCommand = null) {
    if (!state.vehicleId) return showToast('Selecciona un vehículo primero.', 'error');
    const command = knownCommand || state.commands.find((item) => item.id_comando === commandId && item.activo);
    if (!command) return showToast('El comando no está disponible o está inactivo.', 'error');
    const buttons = $$(`[data-send-command-id="${commandId}"]`);
    buttons.forEach((button) => { button.disabled = true; });
    try {
      const result = await api(`/vehiculos/${state.vehicleId}/movimientos`, {
        method: 'POST',
        body: { id_comando: command.id_comando, origen: 'DASHBOARD' },
      });
      showToast(`${command.nombre}: solicitud aceptada. Clientes WebSocket notificados: ${result.clientes_notificados ?? 0}.`);
      await refreshVehicleData(false);
    } catch (error) {
      showToast(error.message, 'error');
    } finally {
      updateControlAvailability();
      buttons.forEach((button) => { button.disabled = false; });
    }
  }

  async function refreshVehicleData(refreshSocket = false) {
    if (!state.vehicleId) return;
    const id = state.vehicleId;
    const [vehicle, commands, history] = await Promise.all([
      api(`/vehiculos/${id}`),
      api(`/vehiculos/${id}/comandos`),
      api(`/vehiculos/${id}/historial`),
    ]);
    if (id !== state.vehicleId) return;
    state.vehicle = vehicle;
    state.commands = commands || [];
    state.history = history?.movimientos || [];
    renderVehicle();
    renderCommands();
    renderHistory();
    renderAdminCommands();
    if (refreshSocket) connectSocket(id);
  }

  function closeSocket() {
    if (state.wsPing) window.clearInterval(state.wsPing);
    if (state.wsRetry) window.clearTimeout(state.wsRetry);
    state.wsPing = null;
    state.wsRetry = null;
    state.wsVehicleId = null;
    if (state.ws) {
      const old = state.ws;
      state.ws = null;
      old.onclose = null;
      try { old.close(); } catch (_) { /* cierre preventivo */ }
    }
    setWsStatus(false, 'WebSocket desconectado');
  }

  function connectSocket(vehicleId) {
    closeSocket();
    const scheme = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const socketUrl = `${scheme}//${window.location.host}/ws/vehiculos/${vehicleId}`;
    const socket = new WebSocket(socketUrl);
    state.ws = socket;
    state.wsVehicleId = vehicleId;
    setWsStatus(false, 'Conectando WebSocket');

    socket.onopen = () => {
      if (state.ws !== socket) return;
      setWsStatus(true, 'WebSocket activo');
      state.wsPing = window.setInterval(() => {
        if (socket.readyState === WebSocket.OPEN) socket.send('ping');
      }, 20000);
      addEvent({ tipo: 'conexión', comando: 'Dashboard conectado al canal del vehículo', marca_temporal: new Date().toISOString() });
    };

    socket.onmessage = (event) => {
      let message;
      try { message = JSON.parse(event.data); } catch (_) { return; }
      if (message.tipo === 'pong') return;
      handleSocketEvent(message);
    };

    socket.onerror = () => setWsStatus(false, 'Error WebSocket');
    socket.onclose = () => {
      if (state.ws !== socket) return;
      if (state.wsPing) window.clearInterval(state.wsPing);
      state.wsPing = null;
      state.ws = null;
      setWsStatus(false, 'WebSocket desconectado');
      if (state.vehicleId === vehicleId) {
        state.wsRetry = window.setTimeout(() => connectSocket(vehicleId), 4000);
      }
    };
  }

  function handleSocketEvent(message) {
    addEvent(message);
    if (message.tipo === 'estado_inicial') {
      if (state.vehicle) {
        state.vehicle.estado = {
          ...(state.vehicle.estado || {}),
          conectado: Boolean(message.conectado),
          comando: message.comando,
          codigo: message.codigo,
          fecha_actualizacion: message.fecha_actualizacion,
        };
        renderVehicle();
      }
    }
    if (message.tipo === 'movimiento' || message.tipo.startsWith('demo_')) {
      if (message.comando) $('#metric-command').textContent = message.comando;
      $('#metric-command-foot').textContent = formatDate(message.marca_temporal);
      if (message.tipo === 'demo_fin' || message.tipo === 'demo_cancelada' || message.tipo === 'demo_error') {
        loadDemos().catch(() => {});
      }
      if (message.tipo === 'movimiento') loadHistory().catch(() => {});
    }
  }

  function addEvent(message) {
    state.events.unshift(message);
    state.events = state.events.slice(0, 15);
    renderEvents();
  }

  function renderEvents() {
    $('#event-count').textContent = String(state.events.length);
    if (!state.events.length) {
      $('#event-list').innerHTML = '<div class="empty-state small-empty"><span>⌁</span><strong>Sin eventos todavía</strong><small>La actividad aparecerá aquí.</small></div>';
      return;
    }
    const labels = {
      conexión: 'Conexión del dashboard', estado_inicial: 'Estado inicial recibido', movimiento: 'Movimiento recibido',
      demo_inicio: 'DEMO iniciada', demo_movimiento: 'Paso de DEMO', demo_fin: 'DEMO finalizada',
      demo_cancelada: 'DEMO cancelada', demo_error: 'Error en DEMO', error: 'Error WebSocket',
    };
    const icons = { movimiento: '↗', demo_movimiento: '▤', demo_inicio: '▶', demo_fin: '✓', demo_cancelada: 'Ⅱ', demo_error: '!', conexión: '●' };
    $('#event-list').innerHTML = state.events.map((event) => {
      const title = labels[event.tipo] || event.tipo || 'Evento';
      const detail = event.comando || event.demo || event.mensaje || event.accion || (event.total_movimientos ? `${event.total_movimientos} movimientos` : 'Evento recibido');
      const time = event.marca_temporal ? new Date(event.marca_temporal).toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '';
      return `<div class="event-item"><div class="event-symbol">${icons[event.tipo] || '⌁'}</div><div class="event-copy"><strong>${escapeHtml(title)}</strong><small>${escapeHtml(detail)}</small></div><span class="event-time">${escapeHtml(time)}</span></div>`;
    }).join('');
  }

  async function loadHealth() {
    try {
      const health = await api('/health');
      setApiStatus(health?.estado === 'ok', health?.estado === 'ok' ? 'API / RDS en línea' : 'API con incidencias');
    } catch (_) {
      setApiStatus(false, 'API sin conexión');
    }
  }

  async function loadHistory() {
    if (!state.vehicleId) return;
    const data = await api(`/vehiculos/${state.vehicleId}/historial`);
    state.history = data?.movimientos || [];
    renderHistory(data?.total ?? state.history.length);
  }

  function renderHistory(total = state.history.length) {
    $('#history-total').textContent = `${total} registros`;
    if (!state.history.length) {
      $('#history-body').innerHTML = '<tr><td colspan="4" class="table-empty">Todavía no hay movimientos individuales registrados.</td></tr>';
      return;
    }
    $('#history-body').innerHTML = state.history.map((item) => `
      <tr><td><div class="command-cell"><i></i><strong>${escapeHtml(item.comando || 'Sin comando')}</strong></div></td>
      <td>${escapeHtml(item.codigo ?? '—')}</td>
      <td><span class="origin-badge">${escapeHtml(item.origen || '—')}</span></td>
      <td>${escapeHtml(formatDate(item.fecha_hora))}</td></tr>`).join('');
  }

  async function loadDemos() {
    if (!state.vehicleId) return;
    state.demos = await api(`/vehiculos/${state.vehicleId}/demos`);
    if (!Array.isArray(state.demos)) state.demos = [];
    if (!state.demos.some((demo) => demo.id_demo === state.selectedDemoId)) {
      state.selectedDemoId = state.demos[0]?.id_demo ?? null;
    }
    renderDemos();
    if (state.selectedDemoId) await selectDemo(state.selectedDemoId);
  }

  function renderDemos() {
    const list = $('#demo-list');
    if (!state.demos.length) {
      list.innerHTML = '<div class="empty-state"><span>▤</span><strong>No hay secuencias DEMO</strong><small>Un administrador puede crear la primera.</small></div>';
      $('#demo-detail-title').textContent = 'Sin secuencia seleccionada';
      $('#demo-detail-description').textContent = 'Crea una DEMO para configurar sus movimientos.';
      $('#demo-detail-content').innerHTML = '<div class="empty-state"><span>＋</span><strong>Sin movimientos</strong><small>Las secuencias aparecerán aquí.</small></div>';
      $('#demo-step-count').textContent = '0 pasos';
      return;
    }
    list.innerHTML = state.demos.map((demo) => `
      <div class="demo-card ${demo.id_demo === state.selectedDemoId ? 'selected' : ''}" data-demo-id="${demo.id_demo}">
        <div class="demo-card-top"><strong>${escapeHtml(demo.nombre)}</strong><span class="demo-state ${demo.activo ? '' : 'off'}">${demo.activo ? 'ACTIVA' : 'INACTIVA'}</span></div>
        <p>${escapeHtml(demo.descripcion || 'Sin descripción')}</p>
      </div>`).join('');
    $$('[data-demo-id]').forEach((card) => card.addEventListener('click', () => selectDemo(Number(card.dataset.demoId))));
  }

  async function selectDemo(id) {
    state.selectedDemoId = Number(id);
    renderDemos();
    const demo = state.demos.find((item) => item.id_demo === state.selectedDemoId);
    if (!demo) return;
    $('#demo-detail-title').textContent = demo.nombre;
    $('#demo-detail-description').textContent = demo.descripcion || 'Secuencia de movimientos del vehículo.';
    $('#demo-detail-content').innerHTML = '<div class="empty-state small-empty">Cargando movimientos...</div>';
    try {
      state.selectedDemoMoves = await api(`/vehiculos/${state.vehicleId}/demos/${demo.id_demo}/movimientos`);
      renderDemoDetail(demo);
    } catch (error) {
      $('#demo-detail-content').innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
    }
  }

  function renderDemoDetail(demo) {
    const moves = state.selectedDemoMoves || [];
    $('#demo-step-count').textContent = `${moves.length} pasos`;
    const canControl = state.role === 'admin' || state.role === 'control';
    const admin = state.role === 'admin';
    const commandOptions = state.commands.filter((command) => command.activo).map((command) =>
      `<option value="${command.id_comando}">${escapeHtml(command.nombre)} · ${escapeHtml(command.codigo)}</option>`
    ).join('');
    const steps = moves.length ? moves.map((move) => `
      <div class="demo-step"><div class="step-number">${move.orden}</div><div class="step-copy"><strong>${escapeHtml(move.comando)}</strong><small>Duración ${move.duracion_ms} ms · Pausa ${move.pausa_ms} ms</small></div><span class="step-duration">${(move.duracion_ms / 1000).toFixed(2)} s</span></div>`).join('') : '<div class="empty-state small-empty"><strong>Esta DEMO no tiene movimientos.</strong><small>Agrega el primer paso para configurarla.</small></div>';
    const actions = `
      <div class="demo-actions">
        ${canControl ? '<button class="primary-button" id="run-demo" type="button">▶ Iniciar DEMO</button><button class="secondary-button" id="cancel-demo" type="button">Ⅱ Cancelar ejecución</button>' : ''}
        ${admin ? '<button class="secondary-button" id="delete-demo" type="button">Eliminar DEMO</button>' : ''}
      </div>`;
    const addForm = admin ? `
      <form class="add-step-form" id="add-step-form">
        <label>Comando<select name="id_comando" required>${commandOptions || '<option value="">Sin comandos activos</option>'}</select></label>
        <label>Duración (ms)<input name="duracion_ms" type="number" min="1" max="600000" value="300" required></label>
        <label>Pausa (ms)<input name="pausa_ms" type="number" min="0" max="600000" value="100" required></label>
        <button class="primary-button" type="submit" ${commandOptions ? '' : 'disabled'}>＋ Agregar paso</button>
      </form>` : '';
    $('#demo-detail-content').innerHTML = `${actions}<div class="demo-steps">${steps}</div>${addForm}`;
    $('#run-demo')?.addEventListener('click', runSelectedDemo);
    $('#cancel-demo')?.addEventListener('click', cancelRunningDemo);
    $('#delete-demo')?.addEventListener('click', deleteSelectedDemo);
    $('#add-step-form')?.addEventListener('submit', addDemoStep);
  }

  async function runSelectedDemo() {
    if (!state.selectedDemoId) return;
    try {
      const result = await api(`/vehiculos/${state.vehicleId}/demos/${state.selectedDemoId}/iniciar`, { method: 'POST' });
      showToast(`DEMO aceptada: ${result.total_movimientos} movimientos. Sigue el avance en Actividad en vivo.`);
    } catch (error) { showToast(error.message, 'error'); }
  }

  async function cancelRunningDemo() {
    if (!state.vehicleId) return;
    try {
      await api(`/vehiculos/${state.vehicleId}/demos/cancelar`, { method: 'POST' });
      showToast('Solicitud de cancelación enviada.');
    } catch (error) { showToast(error.message, 'error'); }
  }

  async function addDemoStep(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const nextOrder = state.selectedDemoMoves.reduce((max, move) => Math.max(max, Number(move.orden) || 0), 0) + 1;
    try {
      await api(`/vehiculos/${state.vehicleId}/demos/${state.selectedDemoId}/movimientos`, {
        method: 'POST',
        body: {
          id_comando: Number(form.get('id_comando')),
          orden: nextOrder,
          duracion_ms: Number(form.get('duracion_ms')),
          pausa_ms: Number(form.get('pausa_ms')),
        },
      });
      showToast('Movimiento agregado a la DEMO.');
      await selectDemo(state.selectedDemoId);
    } catch (error) { showToast(error.message, 'error'); }
  }

  async function deleteSelectedDemo() {
    if (!state.selectedDemoId || !window.confirm('¿Eliminar esta DEMO y todos sus movimientos?')) return;
    try {
      await api(`/vehiculos/${state.vehicleId}/demos/${state.selectedDemoId}/eliminar`, { method: 'POST' });
      showToast('DEMO eliminada.');
      state.selectedDemoId = null;
      await loadDemos();
    } catch (error) { showToast(error.message, 'error'); }
  }

  function openDemoModal() {
    $('#demo-modal').hidden = false;
    $('#demo-form-error').textContent = '';
    $('#demo-form').reset();
  }

  function closeDemoModal() { $('#demo-modal').hidden = true; }

  async function createDemo(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      const demo = await api(`/vehiculos/${state.vehicleId}/demos`, {
        method: 'POST', body: { nombre: form.get('nombre'), descripcion: form.get('descripcion') || null },
      });
      closeDemoModal();
      showToast('Secuencia DEMO creada.');
      await loadDemos();
      if (demo?.id_demo) await selectDemo(demo.id_demo);
    } catch (error) { $('#demo-form-error').textContent = error.message; }
  }

  function renderAdminCommands() {
    const container = $('#admin-command-list');
    if (!container) return;
    if (!state.commands.length) {
      container.innerHTML = '<div class="empty-state small-empty">No hay comandos registrados.</div>';
      return;
    }
    container.innerHTML = state.commands.map((command) => `
      <div class="admin-command-row">
        <div><strong>${escapeHtml(command.nombre)}</strong><small>${escapeHtml(command.descripcion || 'Sin descripción')}</small></div>
        <div class="admin-command-meta"><small>Código</small><strong>${escapeHtml(command.codigo)}</strong></div>
        <div class="admin-command-meta"><small>Estado</small><strong>${command.activo ? 'Activo' : 'Inactivo'}</strong></div>
        <div class="row-actions"><button class="mini-action" data-toggle-command="${command.id_comando}" data-active="${command.activo}">${command.activo ? 'Desactivar' : 'Activar'}</button> <button class="mini-action danger" data-delete-command="${command.id_comando}">Eliminar</button></div>
      </div>`).join('');
    $$('[data-toggle-command]').forEach((button) => button.addEventListener('click', () => toggleCommand(Number(button.dataset.toggleCommand), button.dataset.active === 'true')));
    $$('[data-delete-command]').forEach((button) => button.addEventListener('click', () => deleteCommand(Number(button.dataset.deleteCommand))));
  }

  async function toggleCommand(id, isActive) {
    try {
      await api(`/vehiculos/${state.vehicleId}/comandos/${id}/actualizar`, { method: 'POST', body: { activo: !isActive } });
      showToast(`Comando ${isActive ? 'desactivado' : 'activado'}.`);
      await refreshVehicleData();
    } catch (error) { showToast(error.message, 'error'); }
  }

  async function deleteCommand(id) {
    if (!window.confirm('¿Eliminar este comando? Si está en uso en una DEMO, la API rechazará la operación.')) return;
    try {
      await api(`/vehiculos/${state.vehicleId}/comandos/${id}/eliminar`, { method: 'POST' });
      showToast('Comando eliminado.');
      await refreshVehicleData();
    } catch (error) { showToast(error.message, 'error'); }
  }

  async function createVehicle(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const errorElement = $('#vehicle-form-error');
    errorElement.textContent = '';
    try {
      const result = await api('/vehiculos', {
        method: 'POST',
        body: {
          nombre: form.get('nombre'),
          modelo: form.get('modelo') || null,
          microcontrolador: form.get('microcontrolador') || null,
          descripcion: form.get('descripcion') || null,
        },
      });
      event.currentTarget.reset();
      showToast('Vehículo registrado.');
      await loadVehicles(result.id_vehiculo);
    } catch (error) { errorElement.textContent = error.message; }
  }

  async function createCommand(event) {
    event.preventDefault();
    if (!state.vehicleId) return showToast('Selecciona un vehículo primero.', 'error');
    const form = new FormData(event.currentTarget);
    const errorElement = $('#command-form-error');
    errorElement.textContent = '';
    try {
      await api(`/vehiculos/${state.vehicleId}/comandos`, {
        method: 'POST',
        body: {
          nombre: form.get('nombre'),
          codigo: Number(form.get('codigo')),
          descripcion: form.get('descripcion') || null,
        },
      });
      event.currentTarget.reset();
      showToast('Comando creado.');
      await refreshVehicleData();
    } catch (error) { errorElement.textContent = error.message; }
  }

  function setPage(page) {
    if (page === 'admin' && state.role !== 'admin') return;
    state.page = page;
    $$('.page').forEach((section) => section.classList.toggle('active', section.id === `page-${page}`));
    $$('.nav-item').forEach((button) => button.classList.toggle('active', button.dataset.page === page));
    $('#breadcrumb-current').textContent = PAGE_NAMES[page] || 'Dashboard';
    $('#sidebar').classList.remove('open');
    if (page === 'history') loadHistory().catch((error) => showToast(error.message, 'error'));
    if (page === 'demos') loadDemos().catch((error) => showToast(error.message, 'error'));
    if (page === 'admin') renderAdminCommands();
  }

  async function login(event) {
    event.preventDefault();
    const error = $('#login-error');
    error.textContent = '';
    const localHost = ['localhost', '127.0.0.1', '::1'].includes(window.location.hostname);
    if (window.location.protocol !== 'https:' && !localHost) {
      error.textContent = 'Por seguridad, el inicio de sesión solo está permitido mediante HTTPS en una dirección pública. No se enviará tu clave por HTTP.';
      $('#api-key-input').value = '';
      return;
    }
    const key = $('#api-key-input').value;
    const submit = $('#login-form button[type="submit"]');
    submit.disabled = true;
    submit.textContent = 'Validando…';
    try {
      const result = await api('/dashboard/auth/login', { method: 'POST', body: { api_key: key } });
      $('#api-key-input').value = '';
      let session;
      try {
        session = await api('/dashboard/auth/me');
      } catch (_) {
        throw new Error('La clave fue validada, pero el navegador no guardó la sesión. Abre el dashboard mediante HTTPS; las cookies seguras no funcionan sobre HTTP público.');
      }
      $('#api-key-input').value = '';
      showApp(session.role || result.role);
      await initializeDashboard();
    } catch (err) {
      error.textContent = err.message;
    } finally {
      $('#api-key-input').value = '';
      submit.disabled = false;
      submit.innerHTML = 'Entrar al centro de control <span>→</span>';
    }
  }

  async function logout() {
    try { await api('/dashboard/auth/logout', { method: 'POST' }); } catch (_) { /* limpia la vista aunque la sesión ya haya expirado */ }
    showLogin('');
  }

  async function initializeDashboard() {
    await loadHealth();
    try {
      await loadVehicles();
    } catch (error) {
      showToast(`No se pudieron cargar los vehículos: ${error.message}`, 'error');
    }
    if (state.healthTimer) window.clearInterval(state.healthTimer);
    state.healthTimer = window.setInterval(loadHealth, 15000);
  }

  async function restoreSession() {
    try {
      const session = await api('/dashboard/auth/me');
      showApp(session.role);
      await initializeDashboard();
    } catch (_) {
      showLogin('');
    }
  }

  function bindEvents() {
    $('#login-form').addEventListener('submit', login);
    $('#toggle-key').addEventListener('click', () => {
      const input = $('#api-key-input');
      input.type = input.type === 'password' ? 'text' : 'password';
    });
    $('#logout-button').addEventListener('click', logout);
    $('#vehicle-select').addEventListener('change', (event) => selectVehicle(event.target.value));
    $$('[data-command]').forEach((button) => button.addEventListener('click', () => sendCommand(button.dataset.command)));
    $$('.nav-item').forEach((button) => button.addEventListener('click', () => setPage(button.dataset.page)));
    $('#mobile-menu').addEventListener('click', () => $('#sidebar').classList.toggle('open'));
    $('#refresh-history').addEventListener('click', () => loadHistory().then(() => showToast('Historial actualizado.')).catch((error) => showToast(error.message, 'error')));
    $('#new-demo-button').addEventListener('click', openDemoModal);
    $('#close-demo-modal').addEventListener('click', closeDemoModal);
    $('#cancel-demo-modal').addEventListener('click', closeDemoModal);
    $('#demo-form').addEventListener('submit', createDemo);
    $('#vehicle-form').addEventListener('submit', createVehicle);
    $('#command-form').addEventListener('submit', createCommand);
  }

  bindEvents();
  restoreSession();
})();
