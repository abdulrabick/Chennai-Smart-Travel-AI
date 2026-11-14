from genai.llm_service import generate_response

question = "What are the transport options available in Chennai?"

answer = generate_response(question)

print("\n========== GROQ AI RESPONSE ==========\n")
print(repr(answer))