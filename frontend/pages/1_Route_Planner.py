import streamlit as st
import sys
from pathlib import Path


# ==========================================
# 1. PROJECT CONFIGURATION
# ==========================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


# ==========================================
# 2. IMPORTS
# ==========================================

from transport_engine import (
    find_best_route,
    load_transport_data,
    compare_routes,
    find_route_within_budget
)

from map_engine import create_route_map
from streamlit_folium import st_folium


# ==========================================
# 3. PAGE CONFIGURATION
# ==========================================

st.set_page_config(
    page_title="Smart Route Planner",
    page_icon="🗺️",
    layout="wide"
)


# ==========================================
# 4. PAGE HEADER
# ==========================================

st.title("🗺️ Chennai Smart Travel AI")

st.markdown(
    "Find the best passenger journey across Chennai "
    "using multiple transportation options."
)

st.caption("Powered by NetworkX route optimization")


# ==========================================
# 5. PLAN YOUR JOURNEY
# ==========================================

st.subheader("📍 Plan Your Journey")

# Load location names

try:

    initial_transport_data = load_transport_data(
        fare_type="regular"
    )

    locations = sorted(
        set(initial_transport_data["start"].unique())
        | set(initial_transport_data["destination"].unique())
    )

except Exception as error:

    st.error(f"Unable to load transport locations: {error}")
    st.stop()


col1, col2 = st.columns(2)

with col1:

    start = st.selectbox(
        "Starting Location",
        locations,
        key="route_start"
    )

with col2:

    destination_options = [
        location for location in locations
        if location != start
    ]

    destination = st.selectbox(
        "Destination",
        destination_options,
        key="route_destination"
    )


# ==========================================
# 6. SELECT YOUR TRANSPORT
# ==========================================

st.divider()

st.subheader("🚍 Select Your Transport")

transport_options = [
    "All",
    "Local Train",
    "MTC Bus",
    "Metro",
    "Share Auto",
    "Rapido Bike Taxi",
    "Cab",
    "Pink Auto"
]

transport_mode = st.selectbox(
    "Choose your preferred transport mode",
    transport_options,
    index=0,
    key="transport_mode"
)

selected_mode = (
    None if transport_mode == "All"
    else transport_mode
)

if transport_mode == "All":

    st.info(
        "All available transport modes will be considered "
        "when calculating your route."
    )

else:

    st.info(
        f"Route recommendations will use only: {transport_mode}"
    )


# ==========================================
# 7. CONDITIONAL METRO FARE SELECTION
# ==========================================

fare_type = "regular"

if transport_mode in ["All", "Metro"]:

    st.divider()

    st.subheader("🎫 Metro Fare Selection")

    fare_option = st.radio(
        "Choose your Metro fare type",
        [
            "Regular Fare",
            "20% Discounted Fare"
        ],
        horizontal=True,
        key="metro_fare_option"
    )

    fare_type = (
        "discounted"
        if fare_option == "20% Discounted Fare"
        else "regular"
    )

    if fare_type == "discounted":

        st.info(
            "Discounted Metro fares are subject to CMRL "
            "eligibility and applicable terms."
        )

    else:

        st.caption("Showing regular Metro fares.")


# ==========================================
# 8. LOAD TRANSPORT DATA
# ==========================================

try:

    transport_data = load_transport_data(
        fare_type=fare_type
    )

except Exception as error:

    st.error(f"Unable to load transport dataset: {error}")
    st.stop()


# ==========================================
# 9. SESSION STATE
# ==========================================

session_defaults = {
    "route_result": None,
    "route_comparison": None,
    "budget_result": None,
    "last_fare_type": fare_type,
    "last_transport_mode": transport_mode,
    "budget_search_done": False
}

for key, default_value in session_defaults.items():

    if key not in st.session_state:

        st.session_state[key] = default_value


# Clear previous results when fare type changes

if st.session_state["last_fare_type"] != fare_type:

    st.session_state["route_result"] = None
    st.session_state["route_comparison"] = None
    st.session_state["budget_result"] = None
    st.session_state["budget_search_done"] = False

    st.session_state["last_fare_type"] = fare_type


# Clear previous results when transport mode changes

if st.session_state["last_transport_mode"] != transport_mode:

    st.session_state["route_result"] = None
    st.session_state["route_comparison"] = None
    st.session_state["budget_result"] = None
    st.session_state["budget_search_done"] = False

    st.session_state["last_transport_mode"] = transport_mode


# ==========================================
# 10. SHOW AVAILABLE FARES FOR ALL MODES
# ==========================================

if transport_mode == "All":

    st.markdown("### 💰 Available Transport Fare Estimates")

    direct_fares = transport_data[
        (transport_data["start"] == start)
        & (transport_data["destination"] == destination)
    ]

    if not direct_fares.empty:

        fare_rows = (
            direct_fares[
                [
                    "transport_mode",
                    "estimated_fare_inr",
                    "estimated_time_min",
                    "distance_km"
                ]
            ]
            .drop_duplicates(subset=["transport_mode"])
            .sort_values("estimated_fare_inr")
        )

        fare_rows = fare_rows.rename(
            columns={
                "transport_mode": "Transport Mode",
                "estimated_fare_inr": "Estimated Fare (₹)",
                "estimated_time_min": "Estimated Time (min)",
                "distance_km": "Distance (km)"
            }
        )

        st.dataframe(
            fare_rows,
            use_container_width=True,
            hide_index=True
        )

        st.caption(
            "These are direct-route estimates from the prototype "
            "dataset. They are not live fares."
        )

    else:

        st.info(
            "No direct fare estimates are available for this "
            "location pair. The route engine may still find "
            "a journey through intermediate locations."
        )


# ==========================================
# 11. COMPARE ALL ROUTES
# ==========================================

st.divider()

st.subheader("📊 Compare All Routes")

st.write(
    "Compare the fastest, cheapest and shortest available "
    "journeys for your selected transport mode."
)

if st.button(
    "📈 Compare Fastest, Cheapest & Shortest",
    use_container_width=True
):

    try:

        with st.spinner("Comparing available routes..."):

            comparison = compare_routes(
                start=start,
                destination=destination,
                fare_type=fare_type,
                transport_mode=selected_mode
            )

            st.session_state["route_comparison"] = comparison

            st.session_state["budget_result"] = None
            st.session_state["budget_search_done"] = False

            st.session_state["route_result"] = None

    except Exception as error:

        st.error(f"Unable to compare routes: {error}")


comparison = st.session_state.get("route_comparison")

if comparison:

    fastest = comparison["Fastest"]
    cheapest = comparison["Cheapest"]
    shortest = comparison["Shortest"]

    st.markdown("### 🏆 Route Comparison Cards")

    col1, col2, col3 = st.columns(3)

    route_cards = [
        ("⚡ Fastest", fastest),
        ("💰 Cheapest", cheapest),
        ("📍 Shortest", shortest)
    ]

    for column, (title, route_data) in zip(
        [col1, col2, col3],
        route_cards
    ):

        with column:

            with st.container(border=True):

                st.markdown(f"### {title}")

                if route_data:

                    st.metric(
                        "Travel Time",
                        f"{route_data['total_time']:.0f} min"
                    )

                    st.metric(
                        "Fare",
                        f"₹{route_data['total_fare']:.0f}"
                    )

                    st.metric(
                        "Distance",
                        f"{route_data['total_distance']:.1f} km"
                    )

                    st.caption(
                        " → ".join(route_data["route"])
                    )

                else:

                    st.warning("No route available.")

    st.markdown("### 📋 Detailed Route Comparison")

    comparison_rows = []

    for route_priority, route_data in comparison.items():

        if route_data:

            comparison_rows.append({

                "Priority": route_priority,

                "Route": " → ".join(route_data["route"]),

                "Time (min)": round(
                    route_data["total_time"], 1
                ),

                "Fare (₹)": round(
                    route_data["total_fare"], 2
                ),

                "Distance (km)": round(
                    route_data["total_distance"], 2
                )

            })

    if comparison_rows:

        st.dataframe(
            comparison_rows,
            use_container_width=True,
            hide_index=True
        )

    else:

        st.warning("No routes available for comparison.")


# ==========================================
# 12. ROUTE OPTIMIZATION
# ==========================================

st.divider()

st.subheader("🚦 Route Optimization")

priority = st.radio(
    "Choose Your Travel Priority",
    ["Fastest", "Cheapest", "Shortest"],
    horizontal=True,
    key="route_priority"
)

if st.button(
    "🔍 Find Best Route",
    type="primary",
    use_container_width=True
):

    try:

        with st.spinner("Calculating the optimal journey..."):

            result = find_best_route(
                start=start,
                destination=destination,
                priority=priority,
                fare_type=fare_type,
                transport_mode=selected_mode
            )

            st.session_state["route_result"] = result

            st.session_state["route_comparison"] = None
            st.session_state["budget_result"] = None
            st.session_state["budget_search_done"] = False

    except Exception as error:

        st.error(f"Unable to calculate route: {error}")


# ==========================================
# 13. DISPLAY SELECTED ROUTE
# ==========================================

result = st.session_state.get("route_result")

if result:

    st.success("Optimal route calculated successfully!")

    st.subheader("📊 Selected Journey Summary")

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Estimated Travel Time",
        f"{result['total_time']:.0f} min"
    )

    col2.metric(
        "Estimated Fare",
        f"₹{result['total_fare']:.0f}"
    )

    col3.metric(
        "Total Distance",
        f"{result['total_distance']:.1f} km"
    )

    st.subheader("🛣️ Recommended Journey")

    st.info(" → ".join(result["route"]))

    # Fare breakdown

    st.subheader("💰 Fare Breakdown")

    fare_summary = {
        "Local Train": 0,
        "MTC Bus": 0,
        "Metro": 0,
        "Share Auto": 0,
        "Rapido Bike Taxi": 0,
        "Cab": 0,
        "Pink Auto": 0
    }

    for step in result["steps"]:

        transport = step["transport"]

        if transport in fare_summary:

            fare_summary[transport] += step["fare"]

    fare_columns = st.columns(4)

    for index, (transport, fare) in enumerate(
        fare_summary.items()
    ):

        with fare_columns[index % 4]:

            st.metric(
                label=transport,
                value=f"₹{fare:.0f}"
            )

    st.success(
        f"💰 Total Journey Fare: ₹{result['total_fare']:.0f}"
    )

    # Journey breakdown

    st.subheader("🚆 Journey Breakdown")

    for index, step in enumerate(
        result["steps"],
        start=1
    ):

        with st.container(border=True):

            st.markdown(
                f"### Step {index}: "
                f"{step['from']} → {step['to']}"
            )

            col1, col2, col3 = st.columns(3)

            col1.write(f"🚍 {step['transport']}")

            col2.write(f"⏱️ {step['time']:.0f} minutes")

            col3.write(f"💰 ₹{step['fare']:.0f}")

            st.caption(
                f"Distance: {step['distance']:.1f} km"
            )

    # Interactive map

    st.subheader("🗺️ Interactive Route Map")

    try:

        route_map = create_route_map(
            result["route"],
            result["steps"]
        )

        st_folium(
            route_map,
            width=None,
            height=500,
            use_container_width=True,
            key="chennai_route_map"
        )

    except Exception as error:

        st.error(
            f"Unable to display route map: {error}"
        )


# ==========================================
# 14. BUDGET-BASED ROUTE FINDER
# ==========================================

st.divider()

st.subheader("💰 Budget-Based Route Finder")

st.write(
    "Enter your travel budget. The system will search "
    "for a route that fits within your budget."
)

budget = st.number_input(
    "Your maximum travel budget (₹)",
    min_value=1,
    max_value=10000,
    value=100,
    step=10,
    key="travel_budget"
)

if st.button(
    "💸 Find Route Within My Budget",
    use_container_width=True
):

    try:

        with st.spinner(
            "Searching for routes within your budget..."
        ):

            budget_result = find_route_within_budget(
                start=start,
                destination=destination,
                budget=budget,
                fare_type=fare_type,
                transport_mode=selected_mode
            )

            st.session_state["budget_result"] = budget_result

            st.session_state["budget_search_done"] = True

            st.session_state["route_result"] = None
            st.session_state["route_comparison"] = None

    except Exception as error:

        st.error(
            f"Unable to find a budget-friendly route: {error}"
        )


# Display budget result

budget_result = st.session_state.get("budget_result")

if budget_result:

    st.success("A route within your budget was found!")

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Estimated Fare",
        f"₹{budget_result['total_fare']:.0f}"
    )

    col2.metric(
        "Travel Time",
        f"{budget_result['total_time']:.0f} min"
    )

    col3.metric(
        "Distance",
        f"{budget_result['total_distance']:.1f} km"
    )

    st.markdown("### 🛣️ Budget-Friendly Journey")

    st.info(" → ".join(budget_result["route"]))

    st.write(
        f"Remaining budget: "
        f"₹{budget - budget_result['total_fare']:.0f}"
    )

    st.markdown("### Journey Details")

    for index, step in enumerate(
        budget_result["steps"],
        start=1
    ):

        with st.container(border=True):

            st.markdown(
                f"**Step {index}: "
                f"{step['from']} → {step['to']}**"
            )

            col1, col2, col3 = st.columns(3)

            col1.write(f"🚍 {step['transport']}")

            col2.write(f"⏱️ {step['time']:.0f} minutes")

            col3.write(f"💰 ₹{step['fare']:.0f}")

elif st.session_state.get("budget_search_done"):

    st.warning(
        "No route was found within your budget "
        "for the selected transport mode."
    )


# ==========================================
# 15. FOOTER
# ==========================================

st.divider()

st.caption(
    """
    Chennai Smart Travel AI | Prototype using illustrative
    transport data. Fares, distances and travel times are
    not verified live estimates. Online booking and live
    availability are not yet integrated.
    """
)