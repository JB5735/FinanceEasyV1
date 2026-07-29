import os
from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st


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
        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 3rem;
        }

        [data-testid="stMetric"] {
            border: 1px solid rgba(128, 128, 128, 0.25);
            border-radius: 10px;
            padding: 14px;
        }

        [data-testid="stSidebar"] {
            border-right: 1px solid rgba(128, 128, 128, 0.20);
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
            "CSV Import",
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

    top_left, top_right = st.columns([3, 1])

    with top_right:
        selected_month = st.selectbox(
            "Dashboard month",
            month_options,
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

    metric1, metric2, metric3, metric4 = st.columns(4)

    metric1.metric(
        "Total Balance",
        format_currency(summary["total_balance"]),
    )

    metric2.metric(
        "Income This Month",
        format_currency(summary["monthly_income"]),
    )

    metric3.metric(
        "Spent This Month",
        format_currency(summary["monthly_spending"]),
    )

    remaining_value = summary["remaining_budget"]

    metric4.metric(
        "Remaining Budget",
        format_currency(remaining_value),
    )

    st.divider()

    chart_left, chart_right = st.columns([3, 2])

    monthly_expenses = monthly_df[
        monthly_df["type"] == "Expense"
    ].copy()

    # ---------- Spending Over Time ----------
    with chart_left:
        st.subheader("Spending Over Time")

        if monthly_expenses.empty:
            st.info(
                "Add expense transactions to display the timeline."
            )
        else:
            daily_spending = (
                monthly_expenses
                .groupby("date", as_index=False)["amount"]
                .sum()
                .sort_values("date")
            )

            daily_spending["cumulative_spending"] = (
                daily_spending["amount"].cumsum()
            )

            timeline_chart = px.line(
                daily_spending,
                x="date",
                y="cumulative_spending",
                markers=True,
                labels={
                    "date": "Date",
                    "cumulative_spending": "Cumulative Spending",
                },
            )

            timeline_chart.update_layout(
                margin=dict(l=10, r=10, t=20, b=10),
                yaxis_tickprefix="$",
                showlegend=False,
            )

            st.plotly_chart(
                timeline_chart,
                use_container_width=True,
            )

    # ---------- Spending by Category ----------
    with chart_right:
        st.subheader("Spending by Category")

        if monthly_expenses.empty:
            st.info(
                "Add expense transactions to display category totals."
            )
        else:
            category_totals = (
                monthly_expenses
                .groupby("category", as_index=False)["amount"]
                .sum()
                .sort_values("amount", ascending=False)
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
            )

            category_chart.update_layout(
                margin=dict(l=10, r=10, t=20, b=10),
                legend_title_text="Category",
            )

            st.plotly_chart(
                category_chart,
                use_container_width=True,
            )

    st.divider()

    # ---------- Budget Progress ----------
    st.subheader("Monthly Budget Progress")

    budget = st.session_state.monthly_budget
    spent = summary["monthly_spending"]
    remaining = budget - spent

    if budget > 0:
        progress_value = min(spent / budget, 1.0)
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
            f"You are {format_currency(spent - budget)} over budget."
        )
    elif budget > 0:
        percentage_used = spent / budget * 100

        st.caption(
            f"{percentage_used:.1f}% of the monthly budget has been used."
        )

    st.divider()

    # ---------- Recent Transactions ----------
    st.subheader("Recent Transactions")

    if df.empty:
        st.info("No transactions have been recorded.")
    else:
        recent_df = (
            df.sort_values("date", ascending=False)
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
        )


# =========================================================
# TRANSACTIONS PAGE
# =========================================================

def show_transactions() -> None:
    st.title("Transactions")
    st.caption("Add, review, filter, and delete transactions.")

    with st.expander(
        "➕ Add a Transaction",
        expanded=True,
    ):
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
                transaction_type = st.selectbox(
                    "Type",
                    ["Expense", "Income"],
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

                category = st.selectbox(
                    "Category",
                    category_options,
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

    current_df = st.session_state.transactions_df.copy()

    if current_df.empty:
        st.info("No transactions yet.")
        return

    current_df["date"] = pd.to_datetime(
        current_df["date"],
        errors="coerce",
    )

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

    display_df = filtered_df.copy()
    display_df["date"] = display_df[
        "date"
    ].dt.strftime("%Y-%m-%d")

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
    )

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

    selected_label = st.selectbox(
        "Select a transaction",
        list(delete_options.keys()),
    )

    if st.button(
        "Delete Selected Transaction",
        type="secondary",
    ):
        index_to_delete = delete_options[selected_label]

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


def show_csv_import() -> None:
    show_placeholder(
        "CSV Import",
        "Import transactions from a spreadsheet.",
        [
            "Upload CSV file",
            "Preview imported rows",
            "Validate required columns",
            "Merge transactions with saved data",
        ],
    )


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
    show_placeholder(
        "AI Advice",
        "Generate personalized recommendations from spending data.",
        [
            "Analyze category spending",
            "Consider savings goals",
            "Suggest realistic reductions",
            "Display actionable next steps",
        ],
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

elif page == "CSV Import":
    show_csv_import()

elif page == "Projections":
    show_projections()

elif page == "Calculators":
    show_calculators()

elif page == "AI Advice":
    show_ai_advice()

elif page == "Settings":
    show_settings()