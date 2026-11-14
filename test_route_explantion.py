from genai.llm_service import explain_travel_route
from genai.agents.travel_agent import get_travel_recommendation


question = (
    "I want to travel from Washermenpet "
    "to Guindy. My budget is ₹30."
)

# Step 1: Calculate route using NetworkX
result = get_travel_recommendation(question)

if result["success"]:

    # Step 2: Get calculated route details
    route_result = result["route_result"]
    budget = result["details"]["budget"]

    # Step 3: Ask Groq to explain the result
    answer = explain_travel_route(
        question,
        route_result,
        budget
    )

    print("\n========== AI ROUTE EXPLANATION ==========\n")
    print(answer)

else:
    print(result["message"])