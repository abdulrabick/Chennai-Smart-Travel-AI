import os
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq


# ==========================================
# 1. PROJECT CONFIGURATION
# ==========================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

load_dotenv(PROJECT_ROOT / ".env")

api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    raise ValueError(
        "GROQ_API_KEY not found. Check your project's .env file."
    )


# ==========================================
# 2. GROQ CLIENT
# ==========================================

client = Groq(api_key=api_key)

MODEL_NAME = "openai/gpt-oss-20b"


# ==========================================
# 3. RESPONSE EXTRACTION
# ==========================================

def extract_response_text(response):
    """Safely extract text from a Groq response."""

    if not response.choices:
        return "The AI could not generate a response. Please try again."

    message = response.choices[0].message

    content = message.content

    if isinstance(content, str) and content.strip():
        return content.strip()

    # Handle models that return content in reasoning format.
    reasoning = getattr(message, "reasoning", None)

    if isinstance(reasoning, str) and reasoning.strip():
        return (
            "I received reasoning but no final answer. "
            "Please try asking your question again."
        )

    return (
        "The AI returned an empty response. "
        "Please try asking your question again."
    )


# ==========================================
# 4. GENERAL AI RESPONSE
# ==========================================

def generate_response(user_message):
    """Generate a general Chennai transportation response."""

    if not user_message or not user_message.strip():
        return "Please enter a travel question."

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,

            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are Chennai Smart Travel AI, "
                        "a helpful assistant for Chennai transportation. "
                        "Answer in simple English. "
                        "Help users understand buses, local trains, "
                        "metro, share autos and travel planning. "
                        "Do not invent live fares, timings or schedules. "
                        "If you do not know something, say so clearly."
                    )
                },
                {
                    "role": "user",
                    "content": user_message.strip()
                }
            ],

            temperature=0.5,
            max_completion_tokens=1000
        )

        return extract_response_text(response)

    except Exception as error:
        print("Groq API Error:", error)

        return (
            "Sorry, I could not connect to the AI service. "
            "Please check your internet connection and Groq API settings. "
            f"Error: {error}"
        )


# ==========================================
# 5. ROUTE EXPLANATION
# ==========================================

def explain_travel_route(user_question, route_result, budget):
    """Explain a route calculated by the NetworkX engine."""

    route = " -> ".join(route_result["route"])

    steps = []

    for step in route_result["steps"]:
        steps.append(
            f"{step['from']} to {step['to']} using "
            f"{step['transport']}, "
            f"fare Rs.{step['fare']}, "
            f"time {step['time']} minutes"
        )

    journey_details = "\n".join(steps)

    prompt = f"""
User question:
{user_question}

Route-engine result from our sample dataset:

Route: {route}
Total fare: Rs.{route_result['total_fare']}
Travel time: {route_result['total_time']} minutes
Distance: {route_result['total_distance']} km
User budget: Rs.{budget}

Journey breakdown:
{journey_details}

Explain this journey in simple English.

Include:
1. Recommended route.
2. Transport used for each step.
3. Total estimated fare.
4. Estimated travel time.
5. Remaining budget.

IMPORTANT:
- Use only the supplied route information.
- Do not invent routes, fares, timings or transport options.
- Clearly mention that these are prototype dataset estimates.
"""

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,

            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are Chennai Smart Travel AI. "
                        "Explain calculated journey results accurately. "
                        "Never change the supplied route or figures."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],

            temperature=0.2,
            max_completion_tokens=1000
        )

        return extract_response_text(response)

    except Exception as error:
        print("Groq Route Explanation Error:", error)

        return (
            "The route was calculated successfully, but the AI "
            "could not explain it. Please try again. "
            f"Error: {error}"
        )