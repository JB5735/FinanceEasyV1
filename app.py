import os
from datetime import date

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import re
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

# =========================================================
# APP CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="FinanceEasy",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

DATA_FILE = "data/expenses.csv"
BUDGET_FILE = "data/budget.csv"

ANTHROPIC_MODEL = "claude-haiku-4-5"

AI_INPUT_COST_PER_MILLION = 0.50
AI_OUTPUT_COST_PER_MILLION = 2.50

TRANSACTION_COLUMNS = [
    "date",
    "description",
    "category",
    "amount",
    "type",
]

EXPENSE_CATEGORIES = [
    "Food",
    "Transport",
    "Entertainment",
    "Shopping",
    "School",
    "Subscriptions",
    "Health",
    "Housing",
    "Other",
]


# =========================================================
# BASIC STYLING
# =========================================================

st.markdown(
    """
    <style>
        /* Main page spacing */
        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 3rem;
        }

        /* Default Streamlit metric cards */
        [data-testid="stMetric"] {
            border: 1px solid rgba(128, 128, 128, 0.25);
            border-radius: 10px;
            padding: 14px;
        }

        /* Sidebar divider */
        [data-testid="stSidebar"] {
            border-right: 1px solid rgba(128, 128, 128, 0.20);
        }

        /* Custom dashboard metric cards */
        .finance-metric-card {
            border: 1px solid rgba(128, 128, 128, 0.25);
            border-radius: 12px;
            padding: 18px 16px;
            min-height: 105px;
            background: rgba(20, 22, 28, 0.35);
        }

        .finance-metric-label {
            font-size: 0.85rem;
            font-weight: 600;
            margin-bottom: 8px;
        }

        .finance-metric-value {
            font-size: 1.75rem;
            font-weight: 500;
            line-height: 1.2;
        }

        /* Slightly reduce spacing above charts */
        [data-testid="stPlotlyChart"] {
            margin-top: -0.25rem;
        }

        /* Make horizontal dividers slightly softer */
        hr {
            border-color: rgba(128, 128, 128, 0.25);
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# FILE AND DATA FUNCTIONS
# =========================================================

def ensure_data_files_exist() -> None:
    """Create the data folder and starter CSV files if needed."""
    os.makedirs("data", exist_ok=True)

    if not os.path.exists(DATA_FILE):
        empty_transactions = pd.DataFrame(columns=TRANSACTION_COLUMNS)
        empty_transactions.to_csv(DATA_FILE, index=False)

    if not os.path.exists(BUDGET_FILE):
        starter_budget = pd.DataFrame(
            [{"monthly_budget": 800.0}]
        )
        starter_budget.to_csv(BUDGET_FILE, index=False)


def load_transactions() -> pd.DataFrame:
    """Load and clean saved transactions."""
    ensure_data_files_exist()

    try:
        df = pd.read_csv(DATA_FILE)

        for column in TRANSACTION_COLUMNS:
            if column not in df.columns:
                df[column] = ""

        df = df[TRANSACTION_COLUMNS]

        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["amount"] = pd.to_numeric(
            df["amount"],
            errors="coerce",
        ).fillna(0.0)

        df["description"] = df["description"].fillna("")
        df["category"] = df["category"].fillna("Other")
        df["type"] = df["type"].fillna("Expense")

        return df

    except (FileNotFoundError, pd.errors.EmptyDataError):
        return pd.DataFrame(columns=TRANSACTION_COLUMNS)


def save_transactions(df: pd.DataFrame) -> None:
    """Save transactions in a CSV-friendly format."""
    saved_df = df.copy()

    if not saved_df.empty:
        saved_df["date"] = pd.to_datetime(
            saved_df["date"],
            errors="coerce",
        ).dt.strftime("%Y-%m-%d")

    saved_df.to_csv(DATA_FILE, index=False)

def validate_imported_csv(
    imported_df: pd.DataFrame,
) -> tuple[bool, str]:
    """Check whether an imported CSV has the required columns."""

    required_columns = {
        "date",
        "description",
        "category",
        "amount",
        "type",
    }

    imported_columns = set(
        imported_df.columns.str.strip().str.lower()
    )

    missing_columns = (
        required_columns - imported_columns
    )

    if missing_columns:
        missing_text = ", ".join(
            sorted(missing_columns)
        )

        return (
            False,
            f"Missing required columns: {missing_text}",
        )

    return True, ""


def clean_imported_transactions(
    imported_df: pd.DataFrame,
) -> pd.DataFrame:
    """Clean and standardize imported transaction data."""

    cleaned_df = imported_df.copy()

    # Normalize column names
    cleaned_df.columns = (
        cleaned_df.columns
        .str.strip()
        .str.lower()
    )

    # Keep only FinanceEasy columns
    cleaned_df = cleaned_df[
        TRANSACTION_COLUMNS
    ].copy()

    # Clean dates
    cleaned_df["date"] = pd.to_datetime(
        cleaned_df["date"],
        errors="coerce",
    )

    # Clean amounts
    cleaned_df["amount"] = pd.to_numeric(
        cleaned_df["amount"],
        errors="coerce",
    )

    # Clean text
    cleaned_df["description"] = (
        cleaned_df["description"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    cleaned_df["category"] = (
        cleaned_df["category"]
        .fillna("Other")
        .astype(str)
        .str.strip()
    )

    cleaned_df["type"] = (
        cleaned_df["type"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.title()
    )

    # Remove rows with invalid essential data
    cleaned_df = cleaned_df.dropna(
        subset=[
            "date",
            "amount",
        ]
    )

    # Only accept positive amounts
    cleaned_df = cleaned_df[
        cleaned_df["amount"] > 0
    ]

    # Only accept supported transaction types
    cleaned_df = cleaned_df[
        cleaned_df["type"].isin(
            ["Expense", "Income"]
        )
    ]

    cleaned_df = cleaned_df.reset_index(
        drop=True
    )

    return cleaned_df


def import_transactions(
    current_df: pd.DataFrame,
    imported_df: pd.DataFrame,
) -> pd.DataFrame:
    """Merge imported transactions into saved FinanceEasy data."""

    combined_df = pd.concat(
        [
            current_df,
            imported_df,
        ],
        ignore_index=True,
    )

    save_transactions(combined_df)

    return combined_df

def add_transaction(
    df: pd.DataFrame,
    transaction: dict,
) -> pd.DataFrame:
    """Add one transaction and save the updated data."""
    new_row = pd.DataFrame([transaction])

    updated_df = pd.concat(
        [df, new_row],
        ignore_index=True,
    )

    updated_df["date"] = pd.to_datetime(
        updated_df["date"],
        errors="coerce",
    )

    save_transactions(updated_df)

    return updated_df


def delete_transaction(
    df: pd.DataFrame,
    index_to_delete: int,
) -> pd.DataFrame:
    """Delete one transaction and update the CSV."""
    updated_df = df.drop(
        index=index_to_delete
    ).reset_index(drop=True)

    save_transactions(updated_df)

    return updated_df


def load_monthly_budget() -> float:
    """Load the saved monthly budget target."""
    ensure_data_files_exist()

    try:
        budget_df = pd.read_csv(BUDGET_FILE)

        if budget_df.empty:
            return 800.0

        return float(budget_df.loc[0, "monthly_budget"])

    except (
        FileNotFoundError,
        KeyError,
        ValueError,
        pd.errors.EmptyDataError,
    ):
        return 800.0


def save_monthly_budget(monthly_budget: float) -> None:
    """Save the monthly budget target."""
    budget_df = pd.DataFrame(
        [{"monthly_budget": float(monthly_budget)}]
    )

    budget_df.to_csv(BUDGET_FILE, index=False)


# =========================================================
# DATA CALCULATION FUNCTIONS
# =========================================================

def get_month_options(df: pd.DataFrame) -> list[str]:
    """Return available months in YYYY-MM format."""
    current_month = pd.Timestamp.today().strftime("%Y-%m")

    if df.empty or df["date"].dropna().empty:
        return [current_month]

    transaction_months = (
        df["date"]
        .dropna()
        .dt.strftime("%Y-%m")
        .unique()
        .tolist()
    )

    transaction_months = sorted(
        transaction_months,
        reverse=True,
    )

    if current_month not in transaction_months:
        transaction_months.insert(0, current_month)

    return transaction_months


def filter_by_month(
    df: pd.DataFrame,
    selected_month: str,
) -> pd.DataFrame:
    """Filter transactions to one YYYY-MM month."""
    if df.empty:
        return df.copy()

    month_mask = (
        df["date"].dt.strftime("%Y-%m")
        == selected_month
    )

    return df[month_mask].copy()


def calculate_summary(
    full_df: pd.DataFrame,
    monthly_df: pd.DataFrame,
    monthly_budget: float,
) -> dict:
    """Calculate dashboard totals."""
    all_income = full_df[full_df["type"] == "Income"]["amount"].sum()
    all_expenses = full_df[full_df["type"] == "Expense"]["amount"].sum()

    monthly_income = monthly_df[
        monthly_df["type"] == "Income"
    ]["amount"].sum()

    monthly_spending = monthly_df[
        monthly_df["type"] == "Expense"
    ]["amount"].sum()

    total_balance = all_income - all_expenses
    remaining_budget = monthly_budget - monthly_spending

    return {
        "total_balance": total_balance,
        "monthly_income": monthly_income,
        "monthly_spending": monthly_spending,
        "remaining_budget": remaining_budget,
    }


def format_currency(value: float) -> str:
    """Format numbers as dollars."""
    return f"${value:,.2f}"

# =========================================================
# AI FUNCTIONS
# =========================================================

def create_ai_spending_summary(
    transactions_df: pd.DataFrame,
    selected_month: str,
    savings_goal: float,
) -> str:
    """Convert one month of transaction data into an AI-ready summary."""

    if transactions_df.empty:
        return ""

    working_df = transactions_df.copy()

    working_df["date"] = pd.to_datetime(
        working_df["date"],
        errors="coerce",
    )

    working_df["amount"] = pd.to_numeric(
        working_df["amount"],
        errors="coerce",
    ).fillna(0.0)

    monthly_df = working_df[
        working_df["date"].dt.strftime("%Y-%m")
        == selected_month
    ].copy()

    if monthly_df.empty:
        return ""

    income_df = monthly_df[
        monthly_df["type"] == "Income"
    ]

    expense_df = monthly_df[
        monthly_df["type"] == "Expense"
    ]

    total_income = income_df["amount"].sum()
    total_expenses = expense_df["amount"].sum()
    current_surplus = total_income - total_expenses
    savings_difference = current_surplus - savings_goal

    expense_category_totals = (
        expense_df
        .groupby("category")["amount"]
        .sum()
        .sort_values(ascending=False)
    )

    income_category_totals = (
        income_df
        .groupby("category")["amount"]
        .sum()
        .sort_values(ascending=False)
    )

    if expense_category_totals.empty:
        expense_lines = "- No expenses recorded"
    else:
        expense_lines = "\n".join(
            f"- {category}: ${amount:,.2f}"
            for category, amount in expense_category_totals.items()
        )

    if income_category_totals.empty:
        income_lines = "- No income recorded"
    else:
        income_lines = "\n".join(
            f"- {category}: ${amount:,.2f}"
            for category, amount in income_category_totals.items()
        )

    if savings_difference >= 0:
        goal_status = (
            f"The current surplus is "
            f"${savings_difference:,.2f} above the savings goal."
        )
    else:
        goal_status = (
            f"The current surplus is "
            f"${abs(savings_difference):,.2f} below the savings goal."
        )

    return f"""
Analysis month: {selected_month}

Verified totals calculated by FinanceEasy:
- Total income: ${total_income:,.2f}
- Total expenses: ${total_expenses:,.2f}
- Current surplus or deficit: ${current_surplus:,.2f}
- Monthly savings goal: ${savings_goal:,.2f}
- Goal status: {goal_status}

Income by source:
{income_lines}

Expenses by category:
{expense_lines}

Do not recalculate or contradict the verified totals above.
""".strip()


def get_ai_style_instructions(advice_style: str) -> str:
    """Return instructions for the selected recommendation style."""

    styles = {
        "Supportive Coach": (
            "Use an encouraging and nonjudgmental tone. "
            "Prioritize sustainable habits and acknowledge what the "
            "user is already doing well."
        ),
        "Direct Analyst": (
            "Be concise and numbers-focused. Identify the largest "
            "opportunities and give specific dollar-based recommendations."
        ),
        "Goal-Based Planner": (
            "Work backward from the savings goal. Explain which realistic "
            "changes would help close any gap or improve the existing surplus."
        ),
    }

    return styles[advice_style]


def get_ai_spending_advice(
    spending_summary: str,
    advice_style: str,
) -> tuple[str, int, int, float]:
    """Send the financial summary to Claude and return advice and usage."""

    api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY was not found. "
            "Check that your .env file exists."
        )

    if not spending_summary:
        raise ValueError(
            "No transaction data is available for the selected month."
        )

    client = Anthropic(api_key=api_key)

    style_instructions = get_ai_style_instructions(
        advice_style
    )

    message = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=700,
        system=(
            "You are FinanceEasy AI, an educational budgeting assistant "
            "for college students. Use only the supplied financial data. "
            "Do not invent income, expenses, percentages, or personal facts. "
            "Do not contradict the totals calculated by FinanceEasy. "
            "Do not shame the user or recommend eliminating all discretionary "
            "spending. Do not present the response as professional financial, "
            "tax, legal, or investment advice."
            "Follow the requested output structure exactly. "
            "Return plain text only and never use Markdown formatting, "
            "backticks, bold, italics, or code formatting."
        ),
        messages=[
            {
                "role": "user",
                "content": f"""
Analyze the following monthly financial summary:

{spending_summary}

Response style:
{style_instructions}

Use exactly this output format:

Financial Snapshot
One short paragraph.

Areas to Optimize
- First point
- Second point
- Third point if needed

Recommended Changes
1. First recommendation
2. Second recommendation
3. Third recommendation

Estimated Monthly Impact
One short paragraph.

Next Step
One short sentence.

Formatting rules:
- Do not use Markdown heading symbols such as #, ##, or ###.
- Do not use bold text.
- Do not use italics.
- Do not use block quotes.
- Do not use tables.
- Do not use backticks or inline code formatting.
- Return ordinary plain text only.
- Put a normal space between every word.
- Put a space after every period and comma.
- Do not use underscores or asterisks anywhere.
- Do not concatenate numbers, currency values, and words.
- Write dollar amounts like "$400.00", followed by a normal space before the next word.
- Use plain text section titles exactly as written above.
- Use hyphens only for Areas to Optimize.
- Use numbered items only for Recommended Changes.
- Keep spacing consistent with one blank line between sections.
""",
            }
        ],
    )

    response_parts = [
        block.text
        for block in message.content
        if getattr(block, "type", None) == "text"
    ]

    response_text = "\n".join(response_parts)

    input_tokens = message.usage.input_tokens
    output_tokens = message.usage.output_tokens

    input_cost = (
        input_tokens
        / 1_000_000
        * AI_INPUT_COST_PER_MILLION
    )

    output_cost = (
        output_tokens
        / 1_000_000
        * AI_OUTPUT_COST_PER_MILLION
    )

    estimated_cost = input_cost + output_cost

    return (
        response_text,
        input_tokens,
        output_tokens,
        estimated_cost,
    )

def clean_ai_text(text: str) -> str:
    """Clean Markdown and formatting artifacts from AI responses."""

    # Remove Markdown emphasis / code formatting
    text = text.replace("**", "")
    text = text.replace("__", "")
    text = text.replace("*", "")
    text = text.replace("_", "")
    text = text.replace("`", "")

    # Remove Markdown heading markers
    text = re.sub(
        r"^#{1,6}\s*",
        "",
        text,
        flags=re.MULTILINE,
    )

    # Add space when a dollar amount is accidentally joined to a word
    text = re.sub(
        r"(\$\d+(?:,\d{3})*(?:\.\d{1,2})?)([A-Za-z])",
        r"\1 \2",
        text,
    )

    # Add space after punctuation if words become joined
    text = re.sub(
        r"([.!?,;:])([A-Za-z])",
        r"\1 \2",
        text,
    )

    # Normalize spaces, but preserve line breaks
    text = re.sub(
        r"[ \t]+",
        " ",
        text,
    )

    # Reduce excessive blank lines
    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text,
    )

    return text.strip()

def escape_currency_for_streamlit(text: str) -> str:
    """Prevent dollar signs from being interpreted as LaTeX."""
    return text.replace("$", r"\$")

def display_ai_advice(advice: str) -> None:
    """Display AI advice with consistent Streamlit formatting."""

    advice = clean_ai_text(advice)

    section_names = [
        "Financial Snapshot",
        "Areas to Optimize",
        "Recommended Changes",
        "Estimated Monthly Impact",
        "Next Step",
    ]

    sections = {}
    current_section = None

    for line in advice.splitlines():
        stripped_line = line.strip()

        if stripped_line in section_names:
            current_section = stripped_line
            sections[current_section] = []

        elif current_section and stripped_line:
            sections[current_section].append(stripped_line)

    for section_name in section_names:
        if section_name not in sections:
            continue

        st.subheader(section_name)

        section_lines = sections[section_name]

        # Areas to Optimize
        if section_name == "Areas to Optimize":
            for line in section_lines:
                cleaned_line = line.lstrip("- ").strip()

                safe_line = escape_currency_for_streamlit(
                    cleaned_line
                )

                st.write(f"• {safe_line}")

        # Recommended Changes
        elif section_name == "Recommended Changes":
            for line in section_lines:
                safe_line = escape_currency_for_streamlit(
                    line
                )

                st.write(safe_line)

        # Paragraph sections
        else:
            paragraph = " ".join(section_lines)

            safe_paragraph = escape_currency_for_streamlit(
                paragraph
            )

            st.write(safe_paragraph)

# =========================================================
# SESSION STATE
# =========================================================

if "transactions_df" not in st.session_state:
    st.session_state.transactions_df = load_transactions()

if "monthly_budget" not in st.session_state:
    st.session_state.monthly_budget = load_monthly_budget()


# =========================================================
# SIDEBAR NAVIGATION
# =========================================================

with st.sidebar:
    st.title("💰 FinanceEasy")
    st.caption("College finance made simpler")

    page = st.radio(
        "Navigation",
        [
            "Dashboard",
            "Transactions",
            "Budget",
            "Income",
            "Projections",
            "Calculators",
            "AI Advice",
            "Settings",
        ],
        label_visibility="collapsed",
    )

    st.divider()

    st.caption("Local MVP")
    st.caption("Data saved to CSV")


# =========================================================
# CURRENT DATA
# =========================================================

df = st.session_state.transactions_df.copy()

if not df.empty:
    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce",
    )


# =========================================================
# DASHBOARD PAGE
# =========================================================

def show_dashboard() -> None:
    st.title("Dashboard")
    st.caption("Your financial overview in one place.")

    month_options = get_month_options(df)

    # -----------------------------------------------------
    # MONTH SELECTOR
    # -----------------------------------------------------

    title_space, month_column = st.columns([3, 1])

    with month_column:
        selected_month = st.selectbox(
            "Dashboard month",
            month_options,
            key="dashboard_month",
        )

    monthly_df = filter_by_month(
        df,
        selected_month,
    )

    summary = calculate_summary(
        df,
        monthly_df,
        st.session_state.monthly_budget,
    )

    total_balance = summary["total_balance"]
    monthly_income = summary["monthly_income"]
    monthly_spending = summary["monthly_spending"]
    remaining_budget = summary["remaining_budget"]

    # -----------------------------------------------------
    # CUSTOM METRIC CARDS
    # -----------------------------------------------------

    def display_metric_card(
        title: str,
        value: float,
        value_color: str,
    ) -> None:
        """Display a dashboard metric card with a colored value."""

        card_html = (
            f'<div class="finance-metric-card">'
            f'<div class="finance-metric-label">{title}</div>'
            f'<div class="finance-metric-value" '
            f'style="color: {value_color};">'
            f'{format_currency(value)}'
            f'</div>'
            f'</div>'
        )

        st.markdown(
            card_html,
            unsafe_allow_html=True,
        )

    metric1, metric2, metric3, metric4 = st.columns(4)

    with metric1:
        display_metric_card(
            "Total Balance",
            total_balance,
            "#78C850" if total_balance >= 0 else "#FF4B4B",
        )

    with metric2:
        display_metric_card(
            "Income This Month",
            monthly_income,
            "#78C850",
        )

    with metric3:
        display_metric_card(
            "Spent This Month",
            monthly_spending,
            "#FF4B4B",
        )

    with metric4:
        display_metric_card(
            "Remaining Budget",
            remaining_budget,
            "#4AA8FF" if remaining_budget >= 0 else "#FF4B4B",
        )

    st.divider()

    # -----------------------------------------------------
    # PREPARE MONTHLY CHART DATA
    # -----------------------------------------------------

    monthly_income_df = monthly_df[
        monthly_df["type"] == "Income"
    ].copy()

    monthly_expenses_df = monthly_df[
        monthly_df["type"] == "Expense"
    ].copy()

    chart_left, chart_right = st.columns([3, 2])

    # -----------------------------------------------------
    # INCOME VS. SPENDING OVER TIME
    # -----------------------------------------------------

    with chart_left:
        st.subheader("Monthly Cash Flow")
        st.caption("Tracks the total money earned and spent throughout the selected month.")

        if monthly_df.empty:
            st.info(
                "Add income and expense transactions to display "
                "the monthly timeline."
            )

        else:
            # Group every transaction by date and type.
            daily_totals = (
                monthly_df
                .groupby(
                    ["date", "type"],
                    as_index=False,
                )["amount"]
                .sum()
            )

            # Convert the separate income/expense rows into columns.
            daily_pivot = (
                daily_totals
                .pivot(
                    index="date",
                    columns="type",
                    values="amount",
                )
                .fillna(0.0)
                .sort_index()
            )

            # Ensure both columns exist, even if the month only contains
            # income or only contains expenses.
            if "Income" not in daily_pivot.columns:
                daily_pivot["Income"] = 0.0

            if "Expense" not in daily_pivot.columns:
                daily_pivot["Expense"] = 0.0

            # Include every calendar day between the first and last
            # transaction so lines remain continuous.
            start_date = daily_pivot.index.min()
            end_date = daily_pivot.index.max()

            full_date_range = pd.date_range(
                start=start_date,
                end=end_date,
                freq="D",
            )

            daily_pivot = (
                daily_pivot
                .reindex(
                    full_date_range,
                    fill_value=0.0,
                )
                .rename_axis("date")
                .reset_index()
            )

            daily_pivot["cumulative_income"] = (
                daily_pivot["Income"].cumsum()
            )

            daily_pivot["cumulative_spending"] = (
                daily_pivot["Expense"].cumsum()
            )

            daily_pivot["difference"] = (
                daily_pivot["cumulative_income"]
                - daily_pivot["cumulative_spending"]
            )

            comparison_chart = go.Figure()

            # Income line
            comparison_chart.add_trace(
                go.Scatter(
                    x=daily_pivot["date"],
                    y=daily_pivot["cumulative_income"],
                    mode="lines+markers",
                    name="Money Earned",
                    line=dict(
                        color="#78C850",
                        width=3,
                    ),
                    marker=dict(
                        size=7,
                    ),
                    hovertemplate=(
                        "<b>%{x|%b %d, %Y}</b><br>"
                        "Money earned so far: $%{y:,.2f}"
                        "<extra></extra>"
                    ),
                )
            )

            # Spending line
            comparison_chart.add_trace(
                go.Scatter(
                    x=daily_pivot["date"],
                    y=daily_pivot["cumulative_spending"],
                    mode="lines+markers",
                    name="Money Spent",
                    line=dict(
                        color="#FF4B4B",
                        width=3,
                    ),
                    marker=dict(
                        size=7,
                    ),
                    fill="tonexty",
                    fillcolor="rgba(120, 200, 80, 0.10)",
                    hovertemplate=(
                        "<b>%{x|%b %d, %Y}</b><br>"
                        "Money spent so far: $%{y:,.2f}"
                        "<extra></extra>"
                    ),
                )
            )

            comparison_chart.update_layout(
                margin=dict(
                    l=10,
                    r=10,
                    t=15,
                    b=10,
                ),
                height=420,
                hovermode="x unified",
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="left",
                    x=0,
                ),
                xaxis=dict(
                    title="Date",
                    showgrid=False,
                ),
                yaxis=dict(
                    title="Cumulative Amount",
                    tickprefix="$",
                    gridcolor="rgba(128, 128, 128, 0.20)",
                ),
            )

            st.plotly_chart(
                comparison_chart,
                use_container_width=True,
                config={
                    "displayModeBar": False,
                },
            )

    # -----------------------------------------------------
    # SPENDING BY CATEGORY
    # -----------------------------------------------------

    with chart_right:
        st.subheader("Spending by Category")

        if monthly_expenses_df.empty:
            st.info(
                "Add expense transactions to display category totals."
            )

        else:
            category_totals = (
                monthly_expenses_df
                .groupby(
                    "category",
                    as_index=False,
                )["amount"]
                .sum()
                .sort_values(
                    "amount",
                    ascending=False,
                )
            )

            category_chart = px.pie(
                category_totals,
                names="category",
                values="amount",
                hole=0.55,
            )

            category_chart.update_traces(
                textposition="inside",
                textinfo="percent",
                hovertemplate=(
                    "<b>%{label}</b><br>"
                    "Amount: $%{value:,.2f}<br>"
                    "Share: %{percent}"
                    "<extra></extra>"
                ),
            )

            category_chart.update_layout(
                height=420,
                margin=dict(
                    l=10,
                    r=10,
                    t=15,
                    b=10,
                ),
                legend_title_text="Category",
            )

            st.plotly_chart(
                category_chart,
                use_container_width=True,
                config={
                    "displayModeBar": False,
                },
            )

    # -----------------------------------------------------
    # MONTHLY INSIGHT BANNER
    # -----------------------------------------------------

    monthly_difference = monthly_income - monthly_spending

    if monthly_difference > 0:
        st.success(
            f"↗ You earned "
            f"{format_currency(monthly_difference)} more than you "
            f"spent during {selected_month}."
        )

    elif monthly_difference < 0:
        st.error(
            f"↘ You spent "
            f"{format_currency(abs(monthly_difference))} more than "
            f"you earned during {selected_month}."
        )

    else:
        st.info(
            f"Your income and spending were equal during "
            f"{selected_month}."
        )

    st.divider()

    # -----------------------------------------------------
    # BUDGET PROGRESS
    # -----------------------------------------------------

    st.subheader("Monthly Budget Progress")

    budget = st.session_state.monthly_budget
    spent = monthly_spending
    remaining = budget - spent

    if budget > 0:
        progress_value = min(
            spent / budget,
            1.0,
        )
    else:
        progress_value = 0.0

    budget_col1, budget_col2, budget_col3 = st.columns(3)

    budget_col1.metric(
        "Monthly Budget",
        format_currency(budget),
    )

    budget_col2.metric(
        "Spent",
        format_currency(spent),
    )

    budget_col3.metric(
        "Remaining",
        format_currency(remaining),
    )

    st.progress(progress_value)

    if spent > budget:
        st.error(
            f"You are "
            f"{format_currency(spent - budget)} over budget."
        )

    elif budget > 0:
        percentage_used = spent / budget * 100

        st.caption(
            f"{percentage_used:.1f}% of the monthly budget "
            f"has been used."
        )

    st.divider()

    # -----------------------------------------------------
    # RECENT TRANSACTIONS
    # -----------------------------------------------------

    st.subheader("Recent Transactions")

    if monthly_df.empty:
        st.info(
            "No transactions have been recorded for this month."
        )

    else:
        recent_df = (
            monthly_df
            .sort_values(
                "date",
                ascending=False,
            )
            .head(5)
            .copy()
        )

        recent_df["date"] = recent_df[
            "date"
        ].dt.strftime("%Y-%m-%d")

        recent_df["amount"] = recent_df.apply(
            lambda row: (
                row["amount"]
                if row["type"] == "Income"
                else -row["amount"]
            ),
            axis=1,
        )

        st.dataframe(
            recent_df[
                [
                    "date",
                    "description",
                    "category",
                    "type",
                    "amount",
                ]
            ],
            use_container_width=True,
            hide_index=True,
            column_config={
                "date": st.column_config.TextColumn(
                    "Date"
                ),
                "description": st.column_config.TextColumn(
                    "Merchant / Description"
                ),
                "category": st.column_config.TextColumn(
                    "Category"
                ),
                "type": st.column_config.TextColumn(
                    "Type"
                ),
                "amount": st.column_config.NumberColumn(
                    "Amount",
                    format="$%.2f",
                ),
            },
        )

# =========================================================
# TRANSACTIONS PAGE
# =========================================================

def reset_transaction_category() -> None:
    """Clear the old category when transaction type changes."""
    st.session_state.pop("transaction_category", None)

def update_transaction(
    df: pd.DataFrame,
    index_to_update: int,
    updated_transaction: dict,
) -> pd.DataFrame:
    """Update one transaction and save the CSV."""

    updated_df = df.copy()

    for column, value in updated_transaction.items():
        updated_df.at[index_to_update, column] = value

    save_transactions(updated_df)

    return updated_df

def show_manual_transaction_entry() -> None:
    """Display the manual transaction-entry form."""

    with st.expander(
        "➕ Add a Transaction",
        expanded=True,
    ):
        transaction_type = st.selectbox(
            "Type",
            ["Expense", "Income"],
            key="transaction_type",
            on_change=reset_transaction_category,
        )

        if transaction_type == "Income":
            category_options = [
                "Job",
                "Tutoring",
                "Freelancing",
                "Scholarship",
                "Family Support",
                "Refund",
                "Other",
            ]
        else:
            category_options = EXPENSE_CATEGORIES

        with st.form(
            "transaction_form",
            clear_on_submit=True,
        ):
            form_col1, form_col2 = st.columns(2)

            with form_col1:
                transaction_date = st.date_input(
                    "Date",
                    value=date.today(),
                )

                description = st.text_input(
                    "Description / Merchant"
                )

            with form_col2:
                category = st.selectbox(
                    "Category",
                    category_options,
                    key="transaction_category",
                )

                amount = st.number_input(
                    "Amount",
                    min_value=0.0,
                    step=0.01,
                    format="%.2f",
                )

            submitted = st.form_submit_button(
                "Add Transaction",
                use_container_width=True,
            )

            if submitted:
                if not description.strip():
                    st.error(
                        "Please enter a description or merchant."
                    )

                elif amount <= 0:
                    st.error(
                        "Amount must be greater than zero."
                    )

                else:
                    new_transaction = {
                        "date": transaction_date.isoformat(),
                        "description": description.strip(),
                        "category": category,
                        "amount": float(amount),
                        "type": transaction_type,
                    }

                    st.session_state.transactions_df = add_transaction(
                        st.session_state.transactions_df,
                        new_transaction,
                    )

                    st.success(
                        "Transaction added and saved."
                    )

                    st.rerun()
def show_csv_transaction_import() -> None:
    """Display CSV transaction import controls."""

    st.subheader("Import Transactions from CSV")

    st.write(
        "Upload a CSV containing your transaction data. "
        "FinanceEasy will preview and validate the file before importing it."
    )

    st.info(
        "Required columns: date, description, category, amount, type"
    )

    uploaded_file = st.file_uploader(
        "Upload transaction CSV",
        type=["csv"],
        accept_multiple_files=False,
        key="transaction_csv_upload",
    )

    if uploaded_file is None:
        return

    try:
        imported_df = pd.read_csv(uploaded_file)

    except Exception as error:
        st.error(
            f"FinanceEasy could not read this CSV: {error}"
        )
        return

    st.write(f"File: **{uploaded_file.name}**")
    st.write(f"Rows detected: **{len(imported_df)}**")

    with st.expander(
        "Preview uploaded CSV",
        expanded=True,
    ):
        st.dataframe(
            imported_df.head(20),
            use_container_width=True,
            hide_index=True,
        )

    is_valid, validation_message = validate_imported_csv(
        imported_df
    )

    if not is_valid:
        st.error(validation_message)
        return

    cleaned_df = clean_imported_transactions(
        imported_df
    )

    if cleaned_df.empty:
        st.error(
            "No valid transactions remained after validation."
        )
        return

    removed_rows = len(imported_df) - len(cleaned_df)

    st.success(
        f"{len(cleaned_df)} valid transactions are ready to import."
    )

    if removed_rows > 0:
        st.warning(
            f"{removed_rows} row(s) were removed because they "
            f"contained invalid dates, amounts, or transaction types."
        )

    st.subheader("Import Preview")

    preview_df = cleaned_df.copy()

    preview_df["date"] = (
        preview_df["date"]
        .dt.strftime("%Y-%m-%d")
    )

    st.dataframe(
        preview_df,
        use_container_width=True,
        hide_index=True,
    )

    if st.button(
        f"Import {len(cleaned_df)} Transactions",
        type="primary",
        use_container_width=True,
    ):
        st.session_state.transactions_df = import_transactions(
            st.session_state.transactions_df,
            cleaned_df,
        )

        st.success(
            f"Successfully imported {len(cleaned_df)} transactions."
        )

        st.rerun()

def show_transactions() -> None:
    st.title("Transactions")
    st.caption("Add, import, review, filter, and delete transactions.")

    # -----------------------------------------------------
    # ADD TRANSACTION
    # -----------------------------------------------------
    
    entry_method = st.radio(
        "How would you like to add transactions?",
        [
            "Manual Entry",
            "CSV Import",
        ],
        horizontal=True,
        key="transaction_entry_method",
    )

    st.divider()

    if entry_method == "Manual Entry":
        show_manual_transaction_entry()

    else:
        show_csv_transaction_import()

    st.divider()    

    # -----------------------------------------------------
    # LOAD CURRENT TRANSACTION DATA
    # -----------------------------------------------------

    current_df = st.session_state.transactions_df.copy()

    if current_df.empty:
        st.info("No transactions yet.")
        return

    current_df["date"] = pd.to_datetime(
        current_df["date"],
        errors="coerce",
    )

    # -----------------------------------------------------
    # SAVED TRANSACTIONS + FILTERS
    # -----------------------------------------------------

    st.subheader("Saved Transactions")

    filter_col1, filter_col2 = st.columns(2)

    with filter_col1:
        category_filter = st.selectbox(
            "Filter by category",
            ["All"]
            + sorted(
                current_df["category"]
                .dropna()
                .unique()
                .tolist()
            ),
        )

    with filter_col2:
        type_filter = st.selectbox(
            "Filter by type",
            ["All", "Expense", "Income"],
        )

    filtered_df = current_df.copy()

    if category_filter != "All":
        filtered_df = filtered_df[
            filtered_df["category"] == category_filter
        ]

    if type_filter != "All":
        filtered_df = filtered_df[
            filtered_df["type"] == type_filter
        ]

    display_df = (
        filtered_df.copy()
        .sort_values("date", ascending=False)
    )

    display_df["date"] = display_df[
        "date"
    ].dt.strftime("%Y-%m-%d")

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
    )

    st.divider()

    # -----------------------------------------------------
    # EDIT TRANSACTION
    # -----------------------------------------------------

    st.subheader("Edit a Transaction")
    
    edit_options = {
        (
            f"{index} — "
            f"{row['date'].strftime('%Y-%m-%d')} | "
            f"{row['description']} | "
            f"{row['category']} | "
            f"{format_currency(row['amount'])}"
        ): index
        for index, row in current_df.iterrows()
    }

    selected_edit_label = st.selectbox(
        "Select a transaction to edit",
        list(edit_options.keys()),
        key="edit_transaction_selector",
    )

    edit_index = edit_options[selected_edit_label]
    edit_row = current_df.loc[edit_index]

    income_categories = [
        "Job",
        "Tutoring",
        "Freelancing",
        "Scholarship",
        "Family Support",
        "Refund",
        "Other",
    ]

    current_type = edit_row["type"]

    edit_type = st.selectbox(
        "Transaction type",
        ["Expense", "Income"],
        index=0 if current_type == "Expense" else 1,
        key=f"edit_type_{edit_index}",
    )

    if edit_type == "Income":
        edit_category_options = income_categories
    else:
        edit_category_options = EXPENSE_CATEGORIES

    current_category = edit_row["category"]

    if current_category in edit_category_options:
        category_index = edit_category_options.index(
            current_category
        )
    else:
        category_index = 0

    with st.form(
        f"edit_transaction_form_{edit_index}",
    ):
        edit_col1, edit_col2 = st.columns(2)

        with edit_col1:
            edited_date = st.date_input(
                "Date",
                value=edit_row["date"].date(),
                key=f"edit_date_{edit_index}",
            )

            edited_description = st.text_input(
                "Description / Merchant",
                value=str(edit_row["description"]),
                key=f"edit_description_{edit_index}",
            )

        with edit_col2:
            edited_category = st.selectbox(
                "Category",
                edit_category_options,
                index=category_index,
                key=f"edit_category_{edit_index}_{edit_type}",
            )

            edited_amount = st.number_input(
                "Amount",
                min_value=0.0,
                value=float(edit_row["amount"]),
                step=0.01,
                format="%.2f",
                key=f"edit_amount_{edit_index}",
            )

        save_edit_button = st.form_submit_button(
            "Save Changes",
            use_container_width=True,
        )

        if save_edit_button:
            if not edited_description.strip():
                st.error(
                    "Please enter a description or merchant."
                )

            elif edited_amount <= 0:
                st.error(
                    "Amount must be greater than zero."
                )

            else:
                updated_transaction = {
                    "date": edited_date.isoformat(),
                    "description": edited_description.strip(),
                    "category": edited_category,
                    "amount": float(edited_amount),
                    "type": edit_type,
                }

                st.session_state.transactions_df = update_transaction(
                    st.session_state.transactions_df,
                    edit_index,
                    updated_transaction,
                )

                st.success(
                    "Transaction updated and CSV saved."
                )

                st.rerun()

    st.divider()

    # -----------------------------------------------------
    # DELETE TRANSACTION
    # -----------------------------------------------------

    st.subheader("Delete a Transaction")

    delete_options = {
        (
            f"{index} — "
            f"{row['date'].strftime('%Y-%m-%d')} | "
            f"{row['description']} | "
            f"{row['category']} | "
            f"{format_currency(row['amount'])}"
        ): index
        for index, row in current_df.iterrows()
    }

    selected_delete_label = st.selectbox(
    "Select a transaction",
    list(delete_options.keys()),
    key="delete_transaction_selector",
    )

    if st.button(
        "Delete Selected Transaction",
        type="secondary",
    ):
        index_to_delete = delete_options[
            selected_delete_label
        ]

        st.session_state.transactions_df = delete_transaction(
            st.session_state.transactions_df,
            index_to_delete,
        )

        st.success(
            "Transaction deleted and CSV updated."
        )

        st.rerun()

# =========================================================
# BUDGET PAGE
# =========================================================

def show_budget() -> None:
    st.title("Budget")
    st.caption("Set and monitor your monthly spending target.")

    selected_month = st.selectbox(
        "Budget month",
        get_month_options(df),
    )

    monthly_df = filter_by_month(
        df,
        selected_month,
    )

    monthly_expenses = monthly_df[
        monthly_df["type"] == "Expense"
    ]

    monthly_spent = monthly_expenses["amount"].sum()

    with st.form("budget_form"):
        monthly_budget = st.number_input(
            "Monthly budget goal",
            min_value=0.0,
            value=float(st.session_state.monthly_budget),
            step=25.0,
            format="%.2f",
        )

        save_budget_button = st.form_submit_button(
            "Save Monthly Budget"
        )

        if save_budget_button:
            st.session_state.monthly_budget = monthly_budget
            save_monthly_budget(monthly_budget)

            st.success("Monthly budget saved.")
            st.rerun()

    budget = st.session_state.monthly_budget
    remaining = budget - monthly_spent

    metric1, metric2, metric3 = st.columns(3)

    metric1.metric(
        "Budgeted",
        format_currency(budget),
    )

    metric2.metric(
        "Spent",
        format_currency(monthly_spent),
    )

    metric3.metric(
        "Remaining",
        format_currency(remaining),
    )

    progress = (
        min(monthly_spent / budget, 1.0)
        if budget > 0
        else 0.0
    )

    st.progress(progress)

    if monthly_spent > budget:
        st.error(
            f"You are {format_currency(monthly_spent - budget)} over budget."
        )

    elif budget > 0:
        st.success(
            f"You still have {format_currency(remaining)} available."
        )

    st.subheader("Category Breakdown")

    if monthly_expenses.empty:
        st.info(
            "No expenses were recorded for this month."
        )
    else:
        category_summary = (
            monthly_expenses
            .groupby("category", as_index=False)["amount"]
            .sum()
            .sort_values("amount", ascending=False)
        )

        category_summary = category_summary.rename(
            columns={"amount": "spent"}
        )

        st.dataframe(
            category_summary,
            use_container_width=True,
            hide_index=True,
        )


# =========================================================
# INCOME PAGE
# =========================================================

def show_income() -> None:
    st.title("Income")
    st.caption("Review money received from different sources.")

    income_df = df[df["type"] == "Income"].copy()

    if income_df.empty:
        st.info(
            "No income transactions have been recorded."
        )
        return

    total_income = income_df["amount"].sum()

    st.metric(
        "Total Recorded Income",
        format_currency(total_income),
    )

    income_by_source = (
        income_df
        .groupby("category", as_index=False)["amount"]
        .sum()
        .sort_values("amount", ascending=False)
    )

    st.dataframe(
        income_by_source,
        use_container_width=True,
        hide_index=True,
    )


# =========================================================
# PLACEHOLDER PAGES
# =========================================================

def show_placeholder(
    title: str,
    description: str,
    planned_features: list[str],
) -> None:
    st.title(title)
    st.caption(description)

    st.info(
        "This page is part of the FinanceEasy skeleton "
        "and will be completed in a later project week."
    )

    st.subheader("Planned Features")

    for feature in planned_features:
        st.write(f"• {feature}")

def show_projections() -> None:
    show_placeholder(
        "Projections",
        "Estimate future balances and savings progress.",
        [
            "Projected balance",
            "Savings-goal timeline",
            "Spending-reduction scenarios",
        ],
    )


def show_calculators() -> None:
    show_placeholder(
        "Calculators",
        "Use simple college-focused financial tools.",
        [
            "Hourly income calculator",
            "Savings-goal calculator",
            "Budget-split calculator",
            "Income-tax estimate",
        ],
    )


def show_ai_advice() -> None:
    st.title("✨ FinanceEasy AI")
    st.caption(
        "Receive personalized budgeting suggestions based on "
        "your saved transactions."
    )

    transactions_df = (
        st.session_state.transactions_df.copy()
    )

    if transactions_df.empty:
        st.info(
            "Add some income and expense transactions before "
            "requesting an AI analysis."
        )
        return

    transactions_df["date"] = pd.to_datetime(
        transactions_df["date"],
        errors="coerce",
    )

    available_months = (
        transactions_df["date"]
        .dropna()
        .dt.strftime("%Y-%m")
        .unique()
        .tolist()
    )

    available_months = sorted(
        available_months,
        reverse=True,
    )

    if not available_months:
        st.warning(
            "FinanceEasy could not find any valid transaction dates."
        )
        return

    settings_col1, settings_col2 = st.columns(2)

    with settings_col1:
        selected_month = st.selectbox(
            "Month to analyze",
            available_months,
            key="ai_selected_month",
        )

        savings_goal = st.number_input(
            "Monthly savings goal",
            min_value=0.0,
            value=300.0,
            step=25.0,
            format="%.2f",
            key="ai_savings_goal",
        )

    with settings_col2:
        advice_style = st.selectbox(
            "Recommendation style",
            [
                "Supportive Coach",
                "Direct Analyst",
                "Goal-Based Planner",
            ],
            key="ai_advice_style",
        )

        st.write("**Style description**")

        if advice_style == "Supportive Coach":
            st.caption(
                "Encouraging advice focused on sustainable habits."
            )

        elif advice_style == "Direct Analyst":
            st.caption(
                "Concise, numerical recommendations with less filler."
            )

        else:
            st.caption(
                "Recommendations designed around reaching the savings goal."
            )

    spending_summary = create_ai_spending_summary(
        transactions_df,
        selected_month,
        savings_goal,
    )

    st.divider()

    if not spending_summary:
        st.warning(
            "There are no transactions for the selected month."
        )
        return

    with st.expander(
        "Preview the financial summary sent to AI"
    ):
        st.code(
            spending_summary,
            language="text",
        )

    analyze_button = st.button(
        "✨ Analyze My Spending",
        type="primary",
        use_container_width=True,
    )

    if analyze_button:
        try:
            with st.spinner(
                "FinanceEasy AI is reviewing your spending..."
            ):
                (
                    advice,
                    input_tokens,
                    output_tokens,
                    estimated_cost,
                ) = get_ai_spending_advice(
                    spending_summary,
                    advice_style,
                )

            st.session_state.ai_advice = advice
            st.session_state.ai_input_tokens = input_tokens
            st.session_state.ai_output_tokens = output_tokens
            st.session_state.ai_estimated_cost = estimated_cost
            st.session_state.ai_analysis_month = selected_month
            st.session_state.ai_analysis_goal = savings_goal
            st.session_state.ai_analysis_style = advice_style

        except Exception as error:
            st.error(
                "FinanceEasy AI could not complete the analysis: "
                f"{error}"
            )

    if "ai_advice" in st.session_state:
        st.divider()

        st.subheader(
            f"Analysis for "
            f"{st.session_state.ai_analysis_month}"
        )

        st.caption(
            f"Style: {st.session_state.ai_analysis_style} · "
            f"Savings goal: "
            f"{format_currency(st.session_state.ai_analysis_goal)}"
        )

        display_ai_advice(
            st.session_state.ai_advice
        )

        with st.expander("API usage and estimated cost"):
            usage_col1, usage_col2, usage_col3 = st.columns(3)

            usage_col1.metric(
                "Input Tokens",
                st.session_state.ai_input_tokens,
            )

            usage_col2.metric(
                "Output Tokens",
                st.session_state.ai_output_tokens,
            )

            usage_col3.metric(
                "Estimated Cost",
                f"${st.session_state.ai_estimated_cost:.6f}",
            )

        if st.button(
            "Clear AI Analysis",
            type="secondary",
        ):
            keys_to_clear = [
                "ai_advice",
                "ai_input_tokens",
                "ai_output_tokens",
                "ai_estimated_cost",
                "ai_analysis_month",
                "ai_analysis_goal",
                "ai_analysis_style",
            ]

            for key in keys_to_clear:
                st.session_state.pop(key, None)

            st.rerun()

    st.divider()

    st.caption(
        "FinanceEasy AI provides educational budgeting guidance "
        "and is not a substitute for professional financial advice."
    )

def show_settings() -> None:
    st.title("Settings")
    st.caption("Manage local FinanceEasy settings.")

    st.write(
        f"Transaction file: `{DATA_FILE}`"
    )

    st.write(
        f"Budget file: `{BUDGET_FILE}`"
    )

    if st.button("Reload Transactions From CSV"):
        st.session_state.transactions_df = load_transactions()
        st.success("Transactions reloaded.")
        st.rerun()


# =========================================================
# PAGE ROUTING
# =========================================================

if page == "Dashboard":
    show_dashboard()

elif page == "Transactions":
    show_transactions()

elif page == "Budget":
    show_budget()

elif page == "Income":
    show_income()

elif page == "Projections":
    show_projections()

elif page == "Calculators":
    show_calculators()

elif page == "AI Advice":
    show_ai_advice()

elif page == "Settings":
    show_settings()