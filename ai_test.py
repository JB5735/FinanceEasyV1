import os

from anthropic import Anthropic
from dotenv import load_dotenv

# =========================================================
# CONFIGURATION
# =========================================================

MODEL_NAME = "claude-haiku-4-5"

INPUT_COST_PER_MILLION = 0.50
OUTPUT_COST_PER_MILLION = 2.50

# =========================================================
# LOAD API KEY
# =========================================================

load_dotenv()

api_key = os.getenv("ANTHROPIC_API_KEY")

if not api_key:
    raise ValueError(
        "ANTHROPIC_API_KEY was not found.\n"
        "Check that your .env file exists and contains your API key."
    )

client = Anthropic(api_key=api_key)

# =========================================================
# SAMPLE FINANCIAL DATA
# =========================================================

financial_summary = """
You are a budgeting assistant for a college student.

Monthly Financial Summary

Income
-------
Job: $800
Tutoring: $250

Expenses
--------
Food: $320
Entertainment: $140
Transportation: $85
School: $90
Subscriptions: $25

Savings Goal
------------
$300

Please provide:

1. A short financial summary.
2. The biggest spending category.
3. Two realistic ways to reduce spending.
4. An estimate of how much money could be saved.
5. One encouraging next step.

Keep the response under 300 words.
"""

# =========================================================
# SEND REQUEST
# =========================================================

try:

    message = client.messages.create(
        model=MODEL_NAME,
        max_tokens=700,
        system=(
            "You are FinanceEasy AI, a practical and supportive "
            "budgeting assistant for college students. "
            "Only use the financial data provided. "
            "Do not invent numbers. "
            "Do not claim to be a financial advisor."
        ),
        messages=[
            {
                "role": "user",
                "content": financial_summary,
            }
        ],
    )

    response = message.content[0].text

    print("\n==============================")
    print(" FINANCEEASY AI RESPONSE")
    print("==============================\n")

    print(response)

    print("\n==============================")
    print(" TOKEN USAGE")
    print("==============================\n")

    input_tokens = message.usage.input_tokens
    output_tokens = message.usage.output_tokens

    print(f"Input Tokens : {input_tokens}")
    print(f"Output Tokens: {output_tokens}")

    # Cost estimation
    input_cost = (
        input_tokens / 1_000_000
    ) * INPUT_COST_PER_MILLION

    output_cost = (
        output_tokens / 1_000_000
    ) * OUTPUT_COST_PER_MILLION

    total_cost = input_cost + output_cost

    print(f"\nEstimated Cost: ${total_cost:.6f}")

except Exception as error:

    print("\nAn error occurred while contacting Anthropic.\n")
    print(error)