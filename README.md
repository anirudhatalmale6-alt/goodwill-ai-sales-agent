# Goodwill AI Sales Agent

AI-powered voice sales agent for Goodwill Wholesale Company (Qatar). Handles phone orders, pricing inquiries, and customer management in English, Hindi, Malayalam, Bengali, and Arabic.

## Features

- **Voice AI Agent** - ElevenLabs Conversational AI with multilingual support
- **Product Search** - 45+ products across 8 departments with priority pricing and own brands
- **Customer Identification** - Phone number-based recognition with multi-contact support
- **Order Management** - Automated order creation with wallet discount tracking
- **Dashboard** - Real-time stats, call logs, order tracking, complaint management
- **Smart Selling** - Own brand push, cross-sell prompts, wallet discount strategy

## Setup

```bash
pip install -r requirements.txt
chmod +x run.sh
./run.sh
```

## Environment Variables

- `ELEVENLABS_API_KEY` - Your ElevenLabs API key
- `BACKEND_URL` - Backend URL for ElevenLabs webhook tools (default: http://localhost:8000)

## Architecture

- **Backend**: FastAPI + SQLite
- **Voice AI**: ElevenLabs Conversational AI
- **Dashboard**: Jinja2 templates + vanilla JS
- **Data Source**: Excel files (Phase 1 trial), ERP API (Phase 4)
