from genai.agents.travel_agent import get_travel_recommendation


question = (
    "I want to travel from Washermenpet "
    "to Guindy. My budget is ₹30."
)

result = get_travel_recommendation(question)


print("\n========== AI TRAVEL RECOMMENDATION ==========\n")

if result["success"]:

    details = result["details"]
    route = result["route_result"]

    print("Starting Location:", details["start"])
    print("Destination:", details["destination"])
    print("Budget: ₹", details["budget"])

    print("\nRecommended Route:")
    print(" → ".join(route["route"]))

    print("\nTravel Time:", route["total_time"], "minutes")
    print("Fare: ₹", route["total_fare"])
    print("Distance:", route["total_distance"], "km")

else:

    print("Message:", result["message"])