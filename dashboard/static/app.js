// AI Velora Dashboard - Frontend Logic

const API_BASE = '';
const REFRESH_INTERVAL = 10000; // 10 seconds

// Chart instances
let outcomesChart = null;
let hourlyChart = null;
let intentsChart = null;
let upsellChart = null;

// --- Charts ---

function initCharts() {
    const outcomesCtx = document.getElementById('outcomes-chart').getContext('2d');
    outcomesChart = new Chart(outcomesCtx, {
        type: 'doughnut',
        data: {
            labels: ['Venta', 'Upsell Exitoso', 'Problema Resuelto',
                     'Consulta Resuelta', 'Escalada', 'Abandonada', 'En Curso'],
            datasets: [{
                data: [0, 0, 0, 0, 0, 0, 0],
                backgroundColor: [
                    '#16a34a', '#22c55e', '#2563eb',
                    '#60a5fa', '#d97706', '#dc2626', '#94a3b8'
                ],
                borderWidth: 0,
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { position: 'bottom', labels: { font: { size: 11 }, padding: 12 } }
            },
            cutout: '55%',
        }
    });

    const hourlyCtx = document.getElementById('hourly-chart').getContext('2d');
    hourlyChart = new Chart(hourlyCtx, {
        type: 'line',
        data: {
            labels: Array.from({length: 24}, (_, i) => `${i}:00`),
            datasets: [{
                label: 'Conversaciones',
                data: new Array(24).fill(0),
                borderColor: '#2563eb',
                backgroundColor: 'rgba(37, 99, 235, 0.1)',
                fill: true,
                tension: 0.3,
                pointRadius: 2,
                pointHoverRadius: 5,
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: { beginAtZero: true, ticks: { stepSize: 1 } },
                x: { ticks: { maxTicksLimit: 12, font: { size: 10 } } }
            },
            plugins: { legend: { display: false } }
        }
    });

    const intentsCtx = document.getElementById('intents-chart').getContext('2d');
    intentsChart = new Chart(intentsCtx, {
        type: 'bar',
        data: {
            labels: [],
            datasets: [{
                label: 'Mensajes',
                data: [],
                backgroundColor: '#2563eb',
                borderRadius: 4,
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            scales: {
                x: { beginAtZero: true, ticks: { stepSize: 1 } },
                y: { ticks: { font: { size: 11 } } }
            },
            plugins: { legend: { display: false } }
        }
    });

    const upsellCtx = document.getElementById('upsell-chart').getContext('2d');
    upsellChart = new Chart(upsellCtx, {
        type: 'bar',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'Ofrecidos',
                    data: [],
                    backgroundColor: '#94a3b8',
                    borderRadius: 4,
                },
                {
                    label: 'Aceptados',
                    data: [],
                    backgroundColor: '#16a34a',
                    borderRadius: 4,
                }
            ]
        },
        options: {
            responsive: true,
            scales: {
                y: { beginAtZero: true, ticks: { stepSize: 1 } }
            },
            plugins: { legend: { position: 'bottom', labels: { font: { size: 11 } } } }
        }
    });
}

function updateCharts(data) {
    // Outcomes doughnut
    if (data.outcomes && outcomesChart) {
        const o = data.outcomes;
        outcomesChart.data.datasets[0].data = [
            o.venta, o.upsell_exitoso, o.problema_resuelto,
            o.consulta_resuelta, o.escalada, o.abandonada, o.en_curso
        ];
        outcomesChart.update();
    }

    // Hourly line
    if (data.hourly_distribution && hourlyChart) {
        hourlyChart.data.datasets[0].data =
            data.hourly_distribution.map(h => h.count);
        hourlyChart.update();
    }

    // Intents bar
    if (data.top_intents && intentsChart) {
        intentsChart.data.labels =
            data.top_intents.map(i => formatIntent(i.intent));
        intentsChart.data.datasets[0].data =
            data.top_intents.map(i => i.count);
        intentsChart.update();
    }

    // Upsell by offer
    if (data.upsell_by_offer && upsellChart) {
        upsellChart.data.labels =
            data.upsell_by_offer.map(u => u.offer_name);
        upsellChart.data.datasets[0].data =
            data.upsell_by_offer.map(u => u.offered_count);
        upsellChart.data.datasets[1].data =
            data.upsell_by_offer.map(u => u.accepted_count);
        upsellChart.update();
    }
}

// --- Metrics ---

async function fetchMetrics() {
    try {
        const res = await fetch(`${API_BASE}/api/metrics`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        // Conversations today
        document.getElementById('total-conversations').textContent = data.total_conversations_today;

        // Auto-resolved percentage
        document.getElementById('auto-resolved-pct-value').textContent = `${data.auto_resolved_pct}%`;
        document.getElementById('auto-resolved-sub').textContent =
            `${data.auto_resolved_today} de ${data.total_conversations_today}`;

        // Avg response time
        document.getElementById('avg-response').textContent = data.avg_response_time_ms > 0
            ? `${data.avg_response_time_ms}ms`
            : 'N/A';

        // Financial KPIs
        if (data.financial) {
            document.getElementById('booking-revenue').textContent =
                `$${data.financial.booking_revenue.toLocaleString('es-AR')}`;
            document.getElementById('upsell-revenue').textContent =
                `$${data.financial.upsell_revenue.toLocaleString('es-AR')}`;
            document.getElementById('upsell-rate-sub').textContent =
                `${data.upsell_conversion_rate}% conversion`;
            document.getElementById('estimated-savings').textContent =
                `$${data.financial.estimated_savings.toLocaleString('es-AR')}`;
            document.getElementById('savings-sub').textContent =
                `a $${data.financial.cost_per_escalation}/interaccion`;
        }

        // Update charts
        updateCharts(data);
    } catch (err) {
        console.error('Error fetching metrics:', err);
    }
}

// --- Conversations List ---

async function fetchConversations() {
    try {
        const res = await fetch(`${API_BASE}/api/conversations`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        const tbody = document.getElementById('conversations-body');

        if (data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="loading">No hay conversaciones aun. Inicia una conversacion con el bot de Telegram!</td></tr>';
            return;
        }

        tbody.innerHTML = data.map(conv => `
            <tr onclick="openConversation('${conv.id}')">
                <td><span class="short-id">${conv.id.substring(0, 8)}...</span></td>
                <td>${escapeHtml(conv.guest_phone)}</td>
                <td>${conv.platform}</td>
                <td><span class="badge badge-${conv.status}">${conv.status}</span></td>
                <td><span class="badge badge-${conv.outcome || 'en_curso'}">${formatOutcome(conv.outcome)}</span></td>
                <td>${conv.message_count}</td>
                <td>${formatDate(conv.last_message_at)}</td>
            </tr>
        `).join('');
    } catch (err) {
        console.error('Error fetching conversations:', err);
    }
}

// --- Conversation Detail ---

async function openConversation(id) {
    try {
        const res = await fetch(`${API_BASE}/api/conversations/${id}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        // Hide list and charts, show detail
        document.querySelector('.conversations-section').style.display = 'none';
        document.querySelector('.metrics').style.display = 'none';
        document.getElementById('charts-section').style.display = 'none';
        const detail = document.getElementById('conversation-detail');
        detail.style.display = 'block';

        document.getElementById('detail-title').textContent = `Conversacion - ${data.guest_phone}`;
        document.getElementById('detail-status').innerHTML =
            `<span class="badge badge-${data.status}">${data.status}</span>`;

        const chat = document.getElementById('chat-container');
        chat.innerHTML = data.messages.map(msg => `
            <div class="chat-message ${msg.role}">
                <div>${escapeHtml(msg.content)}</div>
                <div class="chat-meta">
                    ${formatDate(msg.created_at)}
                    ${msg.intent ? ` &middot; Intent: ${formatIntent(msg.intent)}` : ''}
                    ${msg.metadata && msg.metadata.latency_ms ? ` &middot; ${msg.metadata.latency_ms}ms` : ''}
                </div>
            </div>
        `).join('');

        // Scroll to bottom
        chat.scrollTop = chat.scrollHeight;
    } catch (err) {
        console.error('Error fetching conversation detail:', err);
    }
}

function closeDetail() {
    document.getElementById('conversation-detail').style.display = 'none';
    document.querySelector('.conversations-section').style.display = 'block';
    document.querySelector('.metrics').style.display = 'grid';
    document.getElementById('charts-section').style.display = 'grid';
}

// --- Helpers ---

function formatIntent(intent) {
    const labels = {
        'booking_info': 'Reserva',
        'new_booking': 'Nueva Reserva',
        'amenities_query': 'Amenities',
        'service_request': 'Pedido',
        'faq_general': 'FAQ',
        'greeting': 'Saludo',
        'upselling': 'Upselling',
        'out_of_scope': 'Fuera de alcance',
        'error': 'Error',
    };
    return labels[intent] || intent;
}

function formatOutcome(outcome) {
    const labels = {
        'venta': 'Venta',
        'upsell_exitoso': 'Upsell',
        'problema_resuelto': 'Problema Resuelto',
        'consulta_resuelta': 'Consulta Resuelta',
        'escalada': 'Escalada',
        'abandonada': 'Abandonada',
        'en_curso': 'En Curso',
    };
    return labels[outcome] || outcome || '-';
}

function formatDate(isoStr) {
    if (!isoStr) return '-';
    try {
        const d = new Date(isoStr);
        return d.toLocaleString('es-AR', {
            day: '2-digit',
            month: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
        });
    } catch {
        return isoStr;
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// --- Init ---

document.addEventListener('DOMContentLoaded', () => {
    initCharts();
    fetchMetrics();
    fetchConversations();

    // Auto-refresh
    setInterval(() => {
        fetchMetrics();
        fetchConversations();
    }, REFRESH_INTERVAL);
});
