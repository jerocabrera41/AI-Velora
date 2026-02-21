# AI Velora - Hotel Agent MVP

Agente de IA para hoteles que automatiza la comunicacion con huespedes via Telegram. Responde preguntas sobre reservas, amenities, procesa pedidos de servicio y escala a recepcion cuando es necesario.

**Stack:** Python 3.11+ | FastAPI | LangGraph | Claude API | SQLite | python-telegram-bot

## Quick Start

### 1. Clonar y configurar

```bash
git clone https://github.com/jerocabrera41/AI-Velora.git
cd AI-Velora
cp .env.example .env
```

### 2. Obtener tokens

**Telegram Bot Token:**
1. Abri [@BotFather](https://t.me/BotFather) en Telegram
2. Envia `/newbot` y segui las instrucciones
3. Copia el token y pegalo en `.env` como `TELEGRAM_BOT_TOKEN`

**Anthropic API Key:**
1. Registrate en [console.anthropic.com](https://console.anthropic.com)
2. Crea una API key en Settings > API Keys
3. Pegala en `.env` como `ANTHROPIC_API_KEY`

### 3. Correr con Docker

```bash
docker compose up --build
```

Esto levanta:
- **API + Dashboard:** http://localhost:8000/dashboard
- **Telegram Bot:** escuchando mensajes automaticamente
- **Health check:** http://localhost:8000/health

### 4. Correr localmente (sin Docker)

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

pip install -r requirements.txt
python -m src.main
```

## Uso

1. Busca tu bot en Telegram (el nombre que le diste en BotFather)
2. Envia `/start`
3. Escribe tu consulta en espanol

### Comandos del bot
- `/start` - Inicia la conversacion
- `/help` - Muestra capacidades del bot
- `/reset` - Reinicia la conversacion (borra contexto)

### Reservas de ejemplo (para testing)
| Huesped | Confirmacion | Habitacion | Estado |
|---------|-------------|------------|--------|
| Juan Perez | PLR-2024-001 | Deluxe | Confirmada |
| Maria Gonzalez | PLR-2024-002 | Suite | Confirmada |
| Carlos Rodriguez | PLR-2024-003 | Standard | Checked-in |

### Preguntas de ejemplo
- "Hola, mi confirmacion es PLR-2024-001"
- "A que hora es el check-in?"
- "Tienen WiFi? Cual es la clave?"
- "Necesito toallas extra"
- "Como llego desde el aeropuerto?"

## Dashboard

Accede a http://localhost:8000/dashboard para ver:
- Metricas en tiempo real (conversaciones, % resolucion, tiempo promedio)
- Lista de conversaciones
- Detalle de cada conversacion con mensajes y metadata

## Tests

```bash
pip install -r requirements.txt
pytest -v
```

## Estructura del Proyecto

```
AI-Velora/
├── src/
│   ├── main.py              # Entry point (FastAPI + Bot)
│   ├── bot.py               # Telegram bot handlers
│   ├── config.py            # Variables de entorno
│   ├── agent/               # Agente LangGraph
│   │   ├── core.py          # Orquestacion del agente
│   │   ├── prompts.py       # System prompts
│   │   ├── intents.py       # Clasificacion de intenciones
│   │   └── tools.py         # Herramientas del LLM
│   ├── database/            # SQLAlchemy models + seed
│   ├── services/            # Logica de negocio
│   └── api/                 # REST API + schemas
├── dashboard/               # Frontend HTML/CSS/JS
├── tests/                   # pytest tests
├── docker-compose.yml
└── Dockerfile
```

## Limitaciones (MVP)

- Solo soporta Telegram (WhatsApp en Fase 2)
- Un solo hotel (Hotel Palermo Soho)
- Sin autenticacion de usuarios en el dashboard
- FAQ search por keywords (no semantico)
- Sin upselling ni revenue management
- Sin persistencia de sesion del bot entre reinicios del servidor

## Roadmap - Fase 2

- [ ] WhatsApp Business API integration
- [ ] Multi-hotel support con autenticacion
- [ ] Upselling automatico (upgrades, servicios premium)
- [ ] Revenue management basico
- [ ] Busqueda semantica en FAQs (embeddings)
- [ ] Demand intelligence (integracion Despegar)
- [ ] MCP Server para integracion con otros sistemas
- [ ] Metricas avanzadas y reportes exportables
