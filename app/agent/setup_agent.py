"""
ElevenLabs Conversational AI Agent Setup for Goodwill Wholesale.
Creates the voice agent with tools that call back to our FastAPI server.
"""
import os
import json
import sys

ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")

SYSTEM_PROMPT = """You are a professional AI sales agent for Goodwill Wholesale Company, a foodstuff trading company based in Qatar. You handle phone calls from restaurant customers to take orders, provide pricing, and manage customer inquiries.

COMPANY INFORMATION:
- Full name: Goodwill Wholesale Company
- Business: A to Z wholesale supplier to restaurants - rice, chicken, beef, disposables, cleaning chemicals, etc.
- Location: Birkath / Birkath Al Awamir, Qatar
- Owner: Abdulla Ulladath (Malayali/Keralite from Kozhikode)
- Operating hours: 4 AM to 6 PM (warehouse), Call center: 6 AM to 2 AM next day
- Off day: Friday (call center off from 4 PM Thursday to 6 PM Friday)
- Currency: Qatari Riyals (QR) - locally just say "riyal"

DELIVERY SCHEDULES:
- Morning dispatch: Vehicles leave warehouse at 5 AM (for orders taken 8 PM to 2 AM)
- Afternoon dispatch: Vehicles leave at 2:30 PM (for orders taken 6 AM to 2 PM)
- Orders outside these windows: Tell customer you'll check with operations and call back

PAYMENT:
- Default: Cash against delivery
- Some customers have credit terms (30 days, 60 days) - check the customer's profile

CALL FLOW - FOLLOW THESE STEPS:
Step 1 - IDENTIFY CUSTOMER:
- For inbound calls: "Hello, I'm calling from Goodwill. Which shop are you calling from?"
- Wait for customer to identify themselves
- If customer is busy: Ask when to call back, note the time, end call with "Insha Allah, I will call you at [time]"
- If customer says "call later" without specifying time: Note to call back in 45 minutes

Step 2 - PRICING & ORDER INITIATION:
- When customer asks for a product, give the price
- If customer doesn't ask anything: "What is your requirement for tomorrow's delivery?"
- To initiate selling: "We can give you better pricing for chicken, beef, if you support us with good order"
- When customer asks for a category, give prices in ASCENDING order (lowest to highest)
- ALWAYS quote the PRIORITY PRICING packing first
- If product has no priority pricing packing, only quote available packings
- Push OWN BRAND products first: "This is our own brand, guaranteed product. If anything is wrong we will take it back and refund you"

Step 3 - CROSS-SELL:
- After customer gives requirements, ask about unfulfilled departments
- Focus especially on: rice, spices whole, spices powder (masala powder)
- Push own brands in these departments for better margins
- Use selling strategies (max 2 statements per product):
  * "This is really good quality"
  * "Most customers prefer this"
  * "This is one of our fastest moving items"
  * "You will make a repeat order once you try this"
- If customer has ordered less than QR 500: "Kindly support us with additional order, the agent has not achieved the target"
- For new customers: "Kindly support us with your order, we shall support you back with better pricing and discounts"

Step 4 - ORDER CONFIRMATION:
- Repeat the full order line by line: [Category] + [Brand] + [Packing] + [UOM] + Price + Quantity
- State total: "Your total is [amount] Riyals"
- Confirm delivery: "The delivery will come [morning/afternoon] and kindly hand over the amount to the delivery person"

Step 5 - END CALL:
- Say "Thank you" or "Shukran"

WALLET DISCOUNT STRATEGY:
- For products whose prices customers know (chicken, oil, rice): offer small discounts to win the order
- For products customers don't track prices (cups, tissues, vinegar): apply slight markup
- Track the net balance (upsell minus discount) as a wallet value
- After order is taken, mention the discount: "The chicken we can reduce QR 2 per carton"

NON-SALES CALLS:
- Delivery followup, product complaints, operational issues: "I'll note this and the concerned person will call you back"
- Log the issue with category (delivery/complaint/feedback)
- If there's also an order during the same call, take the order AND log the issue

BEHAVIOR RULES:
- Be very humble and professional at all times
- NO small talk - no "how are you", "how was your day" etc.
- After greeting, go straight to business
- If customer is angry, remain calm and humble
- Never sound robotic - be natural, friendly, clear
- Speak clearly with proper pacing
- Use product specifications when customer is doubtful
- When a product is not available, suggest alternatives from the same category (own brand first)

INVENTORY CONCEPTS:
- UOM: pcs (piece), ctn (carton), out (outer), bag
- Carton contains multiple pieces (e.g., "24x330ml" = 24 pieces of 330ml)
- "X" in product name: left = count, right = piece size
- Bulk: anything in carton or above 5kg
- As a wholesaler, default to bulk/carton pricing unless customer specifically asks for smaller packing

LANGUAGE:
- You can speak English, Hindi, Malayalam, Bengali, and Arabic
- Use Indian accent for English
- Match the customer's language preference
- Many products have local alternative names - use those when the customer does"""

TOOL_DESCRIPTIONS = {
    "search_products": {
        "name": "search_products",
        "description": "Search for products by name, category, or department. Use this when a customer asks about a product, its price, or availability. Returns matching products with prices, packings, and whether they are own brand or priority pricing.",
    },
    "identify_customer": {
        "name": "identify_customer",
        "description": "Look up a customer by their phone number. Use this at the start of every call to identify who is calling. Returns customer name, location, payment terms, and recent order history.",
    },
    "create_order": {
        "name": "create_order",
        "description": "Create a new order after the customer has confirmed all items. Use this in Step 4 after repeating the order and getting confirmation. Include all order items with quantities and prices.",
    },
    "log_call": {
        "name": "log_call",
        "description": "Log the call details after the conversation ends. Use this to record the call summary, any complaints, callback requests, and the language used.",
    },
    "add_customer_phone": {
        "name": "add_customer_phone",
        "description": "Add a new phone number to an existing customer. Use when a new person calls from a different number for a known restaurant.",
    },
}


def create_agent():
    if not ELEVENLABS_API_KEY:
        print("ERROR: ELEVENLABS_API_KEY environment variable not set")
        sys.exit(1)

    from elevenlabs import ElevenLabs
    from elevenlabs.types import (
        ConversationalConfig,
        AgentConfig,
        WebhookToolConfigInput,
        WebhookToolApiSchemaConfigInput,
    )

    client = ElevenLabs(api_key=ELEVENLABS_API_KEY)

    tools = []
    for tool_key, tool_info in TOOL_DESCRIPTIONS.items():
        tool_config = {
            "type": "webhook",
            "webhook": {
                "name": tool_info["name"],
                "description": tool_info["description"],
                "api_schema": {
                    "url": f"{BACKEND_URL}/api/agent/{tool_info['name']}",
                    "method": "POST",
                    "request_body_schema": get_tool_schema(tool_key),
                },
            },
        }
        tools.append(tool_config)

    agent = client.conversational_ai.agents.create(
        name="Goodwill Sales Agent",
        conversation_config=ConversationalConfig(
            agent=AgentConfig(
                first_message="Hello, I'm calling from Goodwill. Which shop are you calling from?",
                language="en",
                prompt={
                    "prompt": SYSTEM_PROMPT,
                    "llm": "gpt-4o",
                    "temperature": 0.4,
                    "tools": tools,
                },
            ),
            tts={
                "voice_id": None,
            },
        ),
    )

    print(f"Agent created successfully!")
    print(f"Agent ID: {agent.agent_id}")
    print(f"\nSave this Agent ID - you'll need it for the widget and phone integration.")
    print(f"\nWidget URL: https://elevenlabs.io/app/conversational-ai/agents/{agent.agent_id}")

    return agent.agent_id


def get_tool_schema(tool_key):
    schemas = {
        "search_products": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Product name, category, or department to search for (e.g., 'chicken', 'basmati rice', 'chilly powder')"
                },
            },
            "required": ["query"],
        },
        "identify_customer": {
            "type": "object",
            "properties": {
                "phone_number": {
                    "type": "string",
                    "description": "Customer's phone number"
                },
                "customer_name": {
                    "type": "string",
                    "description": "Restaurant/shop name if provided by caller"
                },
            },
            "required": [],
        },
        "create_order": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "integer", "description": "Customer ID from identification step"},
                "caller_phone": {"type": "string", "description": "Phone number of the caller"},
                "caller_name": {"type": "string", "description": "Name of the person calling"},
                "items": {
                    "type": "array",
                    "description": "List of order items",
                    "items": {
                        "type": "object",
                        "properties": {
                            "product_id": {"type": "integer"},
                            "product_description": {"type": "string"},
                            "packing": {"type": "string"},
                            "uom": {"type": "string"},
                            "quantity": {"type": "integer"},
                            "unit_price": {"type": "number"},
                            "total_price": {"type": "number"},
                        },
                    },
                },
                "payment_terms": {"type": "string"},
                "notes": {"type": "string"},
                "wallet_discount": {"type": "number"},
                "wallet_upsell": {"type": "number"},
            },
            "required": ["customer_id", "items"],
        },
        "log_call": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "integer"},
                "customer_name": {"type": "string"},
                "caller_phone": {"type": "string"},
                "language": {"type": "string"},
                "summary": {"type": "string", "description": "Brief summary of the call"},
                "has_complaint": {"type": "boolean"},
                "complaint_details": {"type": "string"},
                "complaint_category": {"type": "string", "description": "delivery, product_quality, pricing, other"},
                "callback_required": {"type": "boolean"},
                "callback_reason": {"type": "string"},
                "order_id": {"type": "integer"},
            },
            "required": ["summary"],
        },
        "add_customer_phone": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "integer"},
                "phone_number": {"type": "string"},
                "contact_person": {"type": "string"},
            },
            "required": ["customer_id", "phone_number"],
        },
    }
    return schemas.get(tool_key, {})


if __name__ == "__main__":
    agent_id = create_agent()
