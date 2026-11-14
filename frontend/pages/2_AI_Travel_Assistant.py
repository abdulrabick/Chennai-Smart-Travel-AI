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

try:
    from genai.llm_service import (
        generate_response,
        explain_travel_route
    )
except Exception as _groq_error:            # no GROQ_API_KEY: the original two tabs show a notice, the new agent tabs still work
    def generate_response(user_message):
        return "Groq is not configured (add GROQ_API_KEY to .env). The Smart Agent tab works without it."

    def explain_travel_route(user_question, route_result, budget):
        return "Groq is not configured, so the AI explanation is unavailable. The route above was still calculated."

from frontend.common import boot
from backend.services import assistant_service
from db import database as _dbm

from genai.agents.travel_agent import (
    get_travel_recommendation
)

from map_engine import create_route_map
from streamlit_folium import st_folium


# ==========================================
# 3. PAGE CONFIGURATION
# ==========================================

st.set_page_config(
    page_title="AI Travel Assistant",
    page_icon="🤖",
    layout="wide"
)


# ==========================================
# 4. PAGE HEADER
# ==========================================

st.title("🤖 Chennai AI Travel Assistant")

st.markdown(
    """
    Your intelligent travel companion for Chennai.

    Explore transportation information and find
    budget-friendly journeys using AI.
    """
)

st.divider()


# ==========================================
# 5. TWO MAIN FEATURES
# ==========================================

boot()

chat_tab, route_tab, agent_tab, multi_tab, kb_tab = st.tabs([
    "💬 General AI Chat",
    "🗺️ Route Recommendation",
    "🛠️ Smart Agent",
    "👥 Multi-Agent Planner",
    "📚 Knowledge Base"
])


# ==========================================
# OPTION 1: GENERAL AI CHAT
# ==========================================

with chat_tab:

    st.subheader("💬 Ask Your Travel Question")

    st.write(
        "Ask anything about Chennai transportation."
    )

    with st.form("general_chat_form"):

        user_question = st.text_area(
            "Enter your question",
            placeholder=(
                "What are the different public transport "
                "options available in Chennai?"
            ),
            height=120
        )

        chat_submit = st.form_submit_button(
            "🤖 Ask AI",
            type="primary",
            use_container_width=True
        )

    if chat_submit:

        if not user_question.strip():

            st.warning("Please enter a question.")

        else:

            try:

                with st.spinner("AI is thinking..."):

                    answer = generate_response(user_question)

                if answer:

                    st.subheader("🤖 AI Response")
                    st.markdown(answer)

                else:

                    st.warning(
                        "AI returned an empty response."
                    )

            except Exception as error:

                st.error("Something went wrong.")
                st.exception(error)


# ==========================================
# OPTION 2: ROUTE RECOMMENDATION
# ==========================================

with route_tab:

    st.subheader("🗺️ Find Your Best Route")

    st.write(
        """
        Select your starting location, destination,
        and budget to discover a suitable journey.
        """
    )

    # Locations available in the prototype dataset

    locations = [
        "Washermenpet",
        "Egmore",
        "Chennai Central",
        "Broadway",
        "Nungambakkam",
        "T Nagar",
        "Guindy",
        "Airport",
        "Tambaram"
    ]

    # --------------------------------------
    # ROUTE INPUT FORM
    # --------------------------------------

    with st.form("route_recommendation_form"):

        col1, col2 = st.columns(2)

        with col1:

            start_location = st.selectbox(
                "📍 Starting Location",
                locations,
                index=0
            )

        with col2:

            destination = st.selectbox(
                "🏁 Destination",
                locations,
                index=6
            )

        budget = st.number_input(
            "💰 Your Travel Budget (₹)",
            min_value=1,
            value=30,
            step=10
        )

        route_submit = st.form_submit_button(
            "🔍 Find My Route",
            type="primary",
            use_container_width=True
        )

    # --------------------------------------
    # PROCESS ROUTE REQUEST
    # --------------------------------------

    if route_submit:

        if start_location == destination:

            st.warning(
                "Starting location and destination "
                "cannot be the same."
            )

        else:

            try:

                with st.spinner(
                    "Finding the best route for you..."
                ):

                    question = (
                        f"I want to travel from "
                        f"{start_location} to {destination}. "
                        f"My budget is ₹{int(budget)}."
                    )

                    # STEP 1: TRAVEL AGENT

                    result = get_travel_recommendation(question)

                if result["success"]:

                    # STEP 2: GET CALCULATED ROUTE

                    route_result = result["route_result"]

                    # STEP 3: GROQ AI EXPLANATION

                    with st.spinner(
                        "Preparing your AI travel explanation..."
                    ):

                        answer = explain_travel_route(
                            question,
                            route_result,
                            int(budget)
                        )

                    # SUCCESS MESSAGE

                    st.success(
                        "Your route recommendation is ready!"
                    )

                    # AI ROUTE EXPLANATION

                    st.subheader(
                        "🤖 AI Travel Recommendation"
                    )

                    st.markdown(answer)

                    # JOURNEY SUMMARY

                    st.divider()

                    st.subheader("📊 Journey Summary")

                    col1, col2, col3 = st.columns(3)

                    with col1:

                        st.metric(
                            "Estimated Fare",
                            f"₹{route_result['total_fare']:.0f}"
                        )

                    with col2:

                        st.metric(
                            "Travel Time",
                            f"{route_result['total_time']:.0f} min"
                        )

                    with col3:

                        st.metric(
                            "Distance",
                            f"{route_result['total_distance']:.1f} km"
                        )

                    # REMAINING BUDGET

                    remaining_budget = (
                        int(budget)
                        - route_result["total_fare"]
                    )

                    st.info(
                        f"💰 Remaining Budget: "
                        f"₹{remaining_budget:.2f}"
                    )

                    # JOURNEY BREAKDOWN

                    st.divider()

                    st.subheader("🚆 Journey Breakdown")

                    for index, step in enumerate(
                        route_result["steps"],
                        start=1
                    ):

                        with st.container(border=True):

                            st.markdown(
                                f"### Step {index}: "
                                f"{step['from']} → {step['to']}"
                            )

                            col1, col2, col3 = st.columns(3)

                            with col1:

                                st.write(
                                    f"🚆 {step['transport']}"
                                )

                            with col2:

                                st.write(
                                    f"⏱️ {step['time']:.0f} minutes"
                                )

                            with col3:

                                st.write(
                                    f"💰 ₹{step['fare']:.0f}"
                                )

                            st.caption(
                                f"Distance: "
                                f"{step['distance']:.1f} km"
                            )

                    # INTERACTIVE ROUTE MAP

                    st.divider()

                    st.subheader(
                        "🗺️ Interactive Chennai Route Map"
                    )

                    try:

                        route_map = create_route_map(
                            route_result["route"],
                            route_result["steps"]
                        )

                        st_folium(
                            route_map,
                            width=None,
                            height=500,
                            use_container_width=True,
                            key="ai_travel_route_map"
                        )

                    except Exception as map_error:

                        st.error(
                            "Unable to display the route map."
                        )

                        st.exception(map_error)

                else:

                    st.warning(result["message"])

            except Exception as error:

                st.error(
                    "Something went wrong while "
                    "processing your route."
                )

                st.exception(error)


# ==========================================
# 6. FOOTER
# ==========================================

st.divider()

st.caption(
    """
    Chennai Smart Travel AI | Powered by Python,
    NetworkX, Groq LLM, Streamlit and Folium.

    Prototype transport data is illustrative.
    Fares, distances, travel times and map routes
    are not verified live information.
    """
)


# ==========================================
# OPTION 3: SMART AGENT (tool calling)
# ==========================================

def _rating_form(prefix):
    """Optional thumbs rating saved to the SQL feedback table."""
    with st.expander("Rate this answer"):
        stars = st.slider("Rating", 1, 5, 4, key=f"{prefix}_stars")
        note = st.text_input("Comment (optional)", key=f"{prefix}_note")
        if st.button("Submit rating", key=f"{prefix}_submit"):
            _dbm.add_feedback(stars, note)
            st.success("Thanks for the feedback!")


with agent_tab:

    st.subheader("🛠️ Ask anything about a journey")
    st.caption(assistant_service.llm_status())
    st.write(
        "The agent picks the right tools (route planner, delay predictor, best-time finder, fares, knowledge base) "
        "and answers from their results. Try: *best way from Egmore to Tambaram at 9 am in heavy rain*, "
        "*when should I leave from Egmore to Guindy on Monday evening?*, *will a bus be late at 6 pm in the rain?*"
    )

    if "agent_history" not in st.session_state:
        st.session_state["agent_history"] = []

    with st.form("agent_form"):
        agent_question = st.text_input("Your question")
        agent_go = st.form_submit_button("Ask the agent", type="primary", use_container_width=True)

    if agent_go and agent_question.strip():
        with st.spinner("Agent is working..."):
            st.session_state["agent_last"] = assistant_service.ask(
                agent_question, "agent", st.session_state["agent_history"]
            )
        st.session_state["agent_history"] += [
            {"role": "user", "content": agent_question},
            {"role": "assistant", "content": st.session_state["agent_last"]["answer"]},
        ]

    last = st.session_state.get("agent_last")
    if last:
        st.markdown(last["answer"])
        st.caption("Answered with the Groq LLM" if last["used_llm"] else "Answered with the offline rule-based agent")
        if last.get("error"):
            st.warning(last["error"])
        with st.expander(f"🔧 Tools used ({len(last.get('steps', []))})"):
            for step in last.get("steps", []):
                st.markdown(f"**{step['tool']}**")
                st.json({"arguments": step["arguments"], "result": step["result"]}, expanded=False)
        _rating_form("agent")


# ==========================================
# OPTION 4: MULTI-AGENT PLANNER
# ==========================================

with multi_tab:

    st.subheader("👥 Planner → Route Analyst → Critic → Explainer")
    st.write(
        "Four cooperating agents plan a trip: the Planner reads your request, the Route Analyst gathers fastest, cheapest and "
        "timing options, the Critic checks budget, rain and rush-hour risks, and the Explainer writes the recommendation."
    )
    with st.form("multi_form"):
        multi_question = st.text_input(
            "Describe your trip",
            value="I need to go from Egmore to Tambaram at 6 pm in heavy rain, budget 60"
        )
        multi_go = st.form_submit_button("Plan with agents", type="primary", use_container_width=True)

    if multi_go and multi_question.strip():
        with st.spinner("Agents are collaborating..."):
            st.session_state["multi_last"] = assistant_service.ask(multi_question, "multi")

    result = st.session_state.get("multi_last")
    if result:
        st.markdown(result["answer"])
        with st.expander("🗣️ Agent conversation"):
            for message in result["transcript"]:
                st.markdown(f"**{message['sender']} → {message['recipient']}:** {message['content']}")
        _rating_form("multi")


# ==========================================
# OPTION 5: KNOWLEDGE BASE (RAG)
# ==========================================

with kb_tab:

    st.subheader("📚 Ask the transport knowledge base")
    st.write(
        "Retrieval-augmented answers from your own data (metro network, fare slabs, mode comparison, how the system works) "
        "and any documents you add to `data/knowledge/`."
    )
    with st.form("kb_form"):
        kb_question = st.text_input("Question", placeholder="Which stations are interchanges? What is the discounted metro fare?")
        kb_go = st.form_submit_button("Search", type="primary", use_container_width=True)

    if kb_go and kb_question.strip():
        kb_result = assistant_service.ask(kb_question, "rag")
        st.markdown(kb_result["answer"])
        with st.expander("Sources"):
            for passage in kb_result.get("sources", []):
                st.markdown(f"**{passage['title']}** (score {passage['score']})")
                st.caption(passage["text"])
