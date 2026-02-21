// AI Velora Dashboard - Frontend Logic

const API_BASE = '';
const REFRESH_INTERVAL = 10000; // 10 seconds

// --- Metrics ---

async function fetchMetrics() {
    try {
        const res = await fetch(`${API_BASE}/api/metrics`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        document.getElementById('total-conversations').textContent = data.total_conversations_today;
        document.getElementById('auto-resolved').textContent = data.auto_resolved_today;
        document.getElementById('auto-resolved-pct').textContent = `${data.auto_resolved_pct}% del total`;
        document.getElementById('avg-response').textContent = data.avg_response_time_ms > 0
            ? `${data.avg_response_time_ms}ms`
            : 'N/A';

        if (data.top_intents && data.top_intents.length > 0) {
            const top = data.top_intents[0];
            document.getElementById('top-intent').textContent = formatIntent(top.intent);
        } else {
            document.getElementById('top-intent').textContent = 'N/A';
        }
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
            tbody.innerHTML = '<tr><td colspan="6" class="loading">No hay conversaciones aun. Inicia una conversacion con el bot de Telegram!</td></tr>';
            return;
        }

        tbody.innerHTML = data.map(conv => `
            <tr onclick="openConversation('${conv.id}')">
                <td><span class="short-id">${conv.id.substring(0, 8)}...</span></td>
                <td>${conv.guest_phone}</td>
                <td>${conv.platform}</td>
                <td><span class="badge badge-${conv.status}">${conv.status}</span></td>
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

        // Hide list, show detail
        document.querySelector('.conversations-section').style.display = 'none';
        document.querySelector('.metrics').style.display = 'none';
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
}

// --- Helpers ---

function formatIntent(intent) {
    const labels = {
        'booking_info': 'Reserva',
        'amenities_query': 'Amenities',
        'service_request': 'Pedido',
        'faq_general': 'FAQ',
        'greeting': 'Saludo',
        'out_of_scope': 'Fuera de alcance',
        'error': 'Error',
    };
    return labels[intent] || intent;
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
    fetchMetrics();
    fetchConversations();

    // Auto-refresh
    setInterval(() => {
        fetchMetrics();
        fetchConversations();
    }, REFRESH_INTERVAL);
});
