# Goodwill AI Sales Agent

AI-powered voice sales agent for Goodwill Wholesale Company (Qatar). Handles inbound/outbound phone calls from restaurant customers to take orders, provide pricing, cross-sell, and manage complaints. Supports English, Hindi, Malayalam, Bengali, and Arabic.

## Architecture

- **Voice AI**: ElevenLabs Conversational AI (Agent ID: `agent_5201kr6twys3edb8kmthx42wwm3z`)
- **LLM**: Gemini 2.0 Flash, temperature 0.4
- **Voice**: Raju - Natural Conversationalist (Indian accent, ID: `pzxut4zZz4GImZNlqQ3H`)
- **Backend**: FastAPI + SQLite (Python 3.10+)
- **Dashboard**: Jinja2 templates + vanilla JS (dark sidebar theme)
- **Data Source**: Excel files (Phase 1 trial), ERP API (Phase 4)

## Key Credentials

- **ElevenLabs API Key**: `sk_115e5b5e524394da4c833af55324463212a9a63b2a1225cf`
- **ElevenLabs Account**: hr.thatco@gmail.com
- **Agent Widget**: https://elevenlabs.io/app/conversational-ai/agents/agent_5201kr6twys3edb8kmthx42wwm3z

## Webhook Tools (ElevenLabs)

5 standalone tools linked to the agent via `tool_ids`:

| Tool | Tool ID | Endpoint |
|------|---------|----------|
| search_products | tool_9301krayzzwwf6dbpwrb32wqgm9y | POST /api/agent/search_products |
| identify_customer | tool_8301krayzzwxe8rtgedymebw3782 | POST /api/agent/identify_customer |
| create_order | tool_9001krayzzwyfrfbv8nk60tgba1w | POST /api/agent/create_order |
| log_call | tool_4901krayzzwze0ys61mqk7q8fw3r | POST /api/agent/log_call |
| add_customer_phone | tool_6701krayzzx0e8z8crvnkgtpgcw7 | POST /api/agent/add_customer_phone |

Tool URLs must point to a publicly accessible URL (currently via serveo tunnel). Update URLs via:
```
PATCH https://api.elevenlabs.io/v1/convai/agents/{agent_id}
Header: xi-api-key: {api_key}
```

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Set environment variables
```bash
export ELEVENLABS_API_KEY="sk_115e5b5e524394da4c833af55324463212a9a63b2a1225cf"
export BACKEND_URL="http://localhost:8090"
```

### 3. Start the server
```bash
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8090
```

### 4. Expose publicly (for ElevenLabs webhooks)
```bash
ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=60 -R 80:localhost:8090 serveo.net
```
This gives a public HTTPS URL. Update all 5 webhook tool URLs to point to this new URL.

### 5. Update webhook tool URLs
```bash
curl -X PATCH "https://api.elevenlabs.io/v1/convai/tools/{tool_id}" \
  -H "xi-api-key: {api_key}" \
  -H "Content-Type: application/json" \
  -d '{"tool_config":{"type":"webhook","name":"{tool_name}","description":"...","api_schema":{"url":"{new_url}/api/agent/{tool_name}","method":"POST","content_type":"application/json","request_body_schema":{...}}}}'
```

## Files

```
app/
  main.py           - FastAPI application (dashboard + API + webhook endpoints)
  database.py       - SQLite database setup, seeding from Excel files
  __init__.py
  agent/
    setup_agent.py   - ElevenLabs agent creation script (reference only)
  templates/         - Dashboard HTML (Jinja2)
    base.html, dashboard.html, products.html, customers.html, orders.html, calls.html
  static/
    css/style.css    - Dashboard CSS
    js/app.js        - Dashboard JavaScript
data/
  goodwill.db        - SQLite database (auto-created from Excel on first run)
agent_prompt.txt     - Current full agent system prompt (35K+ chars)
agent_config.json    - Agent configuration snapshot
requirements.txt     - Python dependencies
run.sh              - Startup script
```

## Dashboard

Accessible at `http://localhost:8090/` (or via tunnel URL). Shows:
- Orders, calls, customers, products overview
- Real-time stats cards
- Call logs with complaint tracking

## Product Catalog

45+ products across 8 departments: Chicken, Beef, Rice, Spices Powder, Spices Whole, Beverages, Disposables, Chemicals. Product data seeded from `ai worksheet.xlsx`. Prices are in the agent prompt AND the database (both must be in sync).

## Agent Prompt

The full system prompt (~35K chars) is saved in `agent_prompt.txt`. It contains:
- Company info, delivery schedules, payment terms
- Full product catalog with prices
- 5-step call flow (Identify > Price/Order > Cross-sell > Confirm > End)
- Wallet/discount strategy
- 128+ trained scenarios from 7 rounds of Q&A
- Complaint handling, return policy, edge cases
- Internal communication structure (Operations/Accounts/Purchaser)

To update the prompt:
```python
import requests
requests.patch(
    "https://api.elevenlabs.io/v1/convai/agents/agent_5201kr6twys3edb8kmthx42wwm3z",
    headers={"xi-api-key": "sk_115e5b5e524394da4c833af55324463212a9a63b2a1225cf", "Content-Type": "application/json"},
    json={"conversation_config": {"agent": {"prompt": {"prompt": new_prompt, "llm": "gemini-2.0-flash", "temperature": 0.4}}}}
)
```

## Phases

- **Phase 1** (current): Voice AI Trial - ElevenLabs agent + FastAPI backend
- **Phase 2**: WhatsApp AI integration
- **Phase 3**: Email AI
- **Phase 4**: ERP Integration (real-time inventory, pricing, customer data)
