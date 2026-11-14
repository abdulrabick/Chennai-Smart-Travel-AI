import re

from transport_engine import find_route_within_budget


# ==========================================
# 1. EXTRACT TRAVEL DETAILS
# ==========================================

def extract_travel_details(user_question):

    question = user_question.lower()

    # Extract starting location
    start_match = re.search(
        r"from\s+([a-zA-Z ]+?)\s+to\s+",
        question
    )

    # Extract destination
    destination_match = re.search(
        r"\bto\s+([a-zA-Z ]+?)(?:\s+my budget|\s+budget|[?.!,]|$)",
        question
    )

    # Extract budget
    budget_match = re.search(
        r"(?:budget\s+(?:is\s+)?|under\s+|below\s+|within\s+)₹?\s*(\d+)",
        question
    )

    start = (
        start_match.group(1).strip().title()
        if start_match else None
    )

    destination = (
        destination_match.group(1).strip().title()
        if destination_match else None
    )

    budget = (
        int(budget_match.group(1))
        if budget_match else None
    )

    # Clean destination
    if destination and start:
        destination = re.sub(
            rf"^travel\s+from\s+{re.escape(start)}\s+to\s+",
            "",
            destination,
            flags=re.IGNORECASE
        )

    return {
        "start": start,
        "destination": destination,
        "budget": budget
    }


# ==========================================
# 2. GET BUDGET-BASED ROUTE
# ==========================================

def get_travel_recommendation(user_question):
    """Extract travel details and calculate an affordable route."""

    details = extract_travel_details(user_question)

    start = details["start"]
    destination = details["destination"]
    budget = details["budget"]

    # Validate user input
    if not start or not destination:
        return {
            "success": False,
            "message": (
                "Please provide both starting location "
                "and destination."
            )
        }

    if budget is None:
        return {
            "success": False,
            "message": "Please provide your travel budget."
        }

    # Calculate route using NetworkX
    result = find_route_within_budget(
        start,
        destination,
        budget
    )

    if result is None:
        return {
            "success": False,
            "message": (
                f"No available route was found within "
                f"your budget of ₹{budget}."
            ),
            "details": details
        }

    return {
        "success": True,
        "details": details,
        "route_result": result
    }