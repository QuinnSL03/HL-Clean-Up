from gemini_client import ask_gemini

print("--- Running your_application.py ---")

# Define your question
my_question = "Is Norman L. Rosenthal & Associates, Inc. a Subsidiary of NORMA Group Holding? explain how"

# Call the ask_gemini function from gemini_client
ai_response = ask_gemini(my_question)

if ai_response:
    print(f"\nYour Question: '{my_question}'")
    print(f"AI's Answer: {ai_response}")
else:
    print("\nCould not get an answer from the AI.")

print("\n--- End of your_application.py ---")