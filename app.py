#!/usr/bin/env python3
"""
Survey Problem Rating Dashboard - Google Sheets Version

Allows human experts to rate the severity of identified survey problems.
Stores ratings in Google Sheets for multi-user access.
"""

import streamlit as st
import pandas as pd
from pathlib import Path
import gspread
from google.oauth2.service_account import Credentials

# File paths
PROBLEMS_FILE = 'problems.csv'

# Rating scale
RATING_SCALE = {
    1: "Not a problem, no modifications needed",
    2: "Potentially a small problem but no modification needed",
    3: "Moderate problem, modification recommended",
    4: "Significant problem, modification essential",
    5: "Very significant problem, modification essential"
}

@st.cache_resource
def init_gsheet():
    """Initialize Google Sheets connection"""
    try:
        # Check if secrets are configured
        if "gcp_service_account" not in st.secrets:
            st.error("Google Sheets credentials not found. Please configure secrets in Streamlit Cloud.")
            return None

        if "google_sheets" not in st.secrets:
            st.error("Google Sheets URL not found. Please configure secrets in Streamlit Cloud.")
            return None

        # Get credentials from Streamlit secrets
        credentials = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
            ]
        )

        client = gspread.authorize(credentials)

        # Open the spreadsheet by URL from secrets
        sheet = client.open_by_url(st.secrets["google_sheets"]["spreadsheet_url"])
        worksheet = sheet.worksheet("Ratings")

        return worksheet
    except KeyError as e:
        st.error(f"Missing configuration in secrets: {e}")
        st.info("Please ensure both 'gcp_service_account' and 'google_sheets' are configured in Streamlit secrets.")
        return None
    except Exception as e:
        st.error(f"Error connecting to Google Sheets: {e}")
        st.info("Please check your Google Sheets setup and credentials.")
        return None

def load_problems():
    """Load the problems CSV"""
    try:
        return pd.read_csv(PROBLEMS_FILE)
    except FileNotFoundError:
        st.error(f"Cannot find problems file at: {PROBLEMS_FILE}")
        st.info(f"Current working directory: {Path.cwd()}")
        st.info(f"Files in current directory: {list(Path.cwd().iterdir())}")
        st.stop()
    except Exception as e:
        st.error(f"Error loading problems: {e}")
        st.stop()

def load_ratings():
    """Load existing ratings from Google Sheet"""
    try:
        worksheet = init_gsheet()
        if worksheet is None:
            return pd.DataFrame(columns=['problem_index', 'question_id', 'rating', 'rater_id'])

        # Get all values
        data = worksheet.get_all_records()

        if not data:
            return pd.DataFrame(columns=['problem_index', 'question_id', 'rating', 'rater_id'])

        df = pd.DataFrame(data)

        # Ensure correct data types
        if 'problem_index' in df.columns:
            df['problem_index'] = pd.to_numeric(df['problem_index'], errors='coerce')
        if 'rating' in df.columns:
            df['rating'] = pd.to_numeric(df['rating'], errors='coerce')

        return df
    except Exception as e:
        st.error(f"Error loading ratings: {e}")
        return pd.DataFrame(columns=['problem_index', 'question_id', 'rating', 'rater_id'])

def save_rating(problem_index, question_id, rating, rater_id):
    """Save a rating to Google Sheet"""
    try:
        worksheet = init_gsheet()
        if worksheet is None:
            st.error("Cannot save - Google Sheets not connected")
            return None

        # Load current data
        ratings_df = load_ratings()

        # Check if this problem has already been rated by this rater
        mask = (ratings_df['problem_index'] == problem_index) & (ratings_df['rater_id'] == rater_id)

        if mask.any():
            # Update existing rating - find row number
            row_idx = ratings_df[mask].index[0]
            row_num = row_idx + 2  # +2 because sheets are 1-indexed and have header row

            worksheet.update(f'C{row_num}', [[rating]])
        else:
            # Add new rating
            worksheet.append_row([problem_index, question_id, rating, rater_id])

        return load_ratings()

    except Exception as e:
        st.error(f"Error saving rating: {e}")
        return None

def get_rating_for_problem(problem_index, rater_id):
    """Get existing rating for a problem by this rater"""
    ratings_df = load_ratings()
    mask = (ratings_df['problem_index'] == problem_index) & (ratings_df['rater_id'] == rater_id)

    if mask.any():
        return int(ratings_df.loc[mask, 'rating'].values[0])
    return None

def main():
    st.set_page_config(page_title="Survey Problem Rating", layout="wide")

    # Load data
    problems_df = load_problems()
    total_problems = len(problems_df)

    # Sidebar for rater ID and navigation
    st.sidebar.title("Rating Dashboard")

    # Rater assignment
    # Group 1: First half of problems (0-58)
    # Group 2: Second half of problems (59-117)
    # Patrick: All problems (0-117)
    RATER_ASSIGNMENTS = {
        "Tom": "first_half",
        "Caroline": "first_half",
        "Becky": "second_half",
        "Alice": "second_half",
        "Patrick": "all"
    }

    # Rater ID dropdown
    if 'rater_id' not in st.session_state:
        st.session_state.rater_id = ""

    rater_id = st.sidebar.selectbox(
        "Select your name:",
        options=[""] + list(RATER_ASSIGNMENTS.keys()),
        index=0 if st.session_state.rater_id == "" else list(RATER_ASSIGNMENTS.keys()).index(st.session_state.rater_id) + 1 if st.session_state.rater_id in RATER_ASSIGNMENTS else 0,
        help="Select your name to begin rating your assigned problems"
    )

    if rater_id:
        st.session_state.rater_id = rater_id
    else:
        st.warning("⚠️ Please select your name in the sidebar to begin rating.")
        return

    # Get assignment for this rater
    assignment = RATER_ASSIGNMENTS[rater_id]
    half_point = total_problems // 2

    if assignment == "first_half":
        assigned_problems = list(range(0, half_point))
        st.sidebar.info(f"📋 You are assigned problems 1-{half_point} (first half)")
    elif assignment == "second_half":
        assigned_problems = list(range(half_point, total_problems))
        st.sidebar.info(f"📋 You are assigned problems {half_point + 1}-{total_problems} (second half)")
    else:  # "all"
        assigned_problems = list(range(0, total_problems))
        st.sidebar.info(f"📋 You are assigned ALL problems (1-{total_problems})")

    # Initialize current problem index to start of assigned problems
    if 'current_index' not in st.session_state:
        st.session_state.current_index = assigned_problems[0]

    # Ensure current index is within assigned problems
    if st.session_state.current_index not in assigned_problems:
        st.session_state.current_index = assigned_problems[0]

    # Progress tracking (only for assigned problems)
    ratings_df = load_ratings()
    if len(ratings_df) > 0:
        rater_ratings = ratings_df[(ratings_df['rater_id'] == rater_id) &
                                   (ratings_df['problem_index'].isin(assigned_problems))]
        num_rated = len(rater_ratings)
    else:
        num_rated = 0

    num_assigned = len(assigned_problems)

    # Navigation
    st.sidebar.subheader("Navigation")

    # Jump to problem (within assigned range)
    min_problem = assigned_problems[0] + 1
    max_problem = assigned_problems[-1] + 1
    current_problem_num = st.session_state.current_index + 1

    jump_to = st.sidebar.number_input(
        f"Jump to problem ({min_problem}-{max_problem}):",
        min_value=min_problem,
        max_value=max_problem,
        value=current_problem_num
    )
    if st.sidebar.button("Go"):
        st.session_state.current_index = jump_to - 1
        st.rerun()

    # Show unrated problems only toggle
    show_unrated_only = st.sidebar.checkbox("Show unrated problems only")

    # Filter to unrated problems if requested (within assigned problems)
    if show_unrated_only:
        unrated_indices = [i for i in assigned_problems
                          if get_rating_for_problem(i, rater_id) is None]
        if unrated_indices:
            if st.session_state.current_index not in unrated_indices:
                st.session_state.current_index = unrated_indices[0]
        else:
            st.success(f"🎉 All your assigned problems have been rated! ({num_assigned} problems)")
            return

    # Current problem
    current_idx = st.session_state.current_index
    problem = problems_df.iloc[current_idx]

    # Main content - compact layout
    st.markdown(f"## Problem {current_idx + 1} of {total_problems}")

    # Question display - more compact
    st.info(f"**{problem['question_id']}:** {problem['question_text']}\n\n**Response options:** {problem['response_options']}")

    # Problem description - more compact
    st.warning(f"**Problem Identified:** {problem['problem_description']}")

    # Rating interface
    st.markdown("**How would you rate the severity of this problem?**")

    # Get existing rating if any
    existing_rating = get_rating_for_problem(current_idx, rater_id)

    # Create rating buttons
    cols = st.columns(5)

    for i, (rating_num, rating_label) in enumerate(RATING_SCALE.items()):
        with cols[i]:
            button_type = "primary" if existing_rating == rating_num else "secondary"
            if st.button(
                f"**{rating_num}**",
                key=f"rating_{rating_num}",
                use_container_width=True,
                type=button_type
            ):
                # Save rating
                with st.spinner("Saving..."):
                    result = save_rating(current_idx, problem['question_id'], rating_num, rater_id)

                if result is not None:
                    st.success(f"✅ Rated as: {rating_num}")

                    # Auto-advance to next problem (within assigned problems)
                    current_position = assigned_problems.index(current_idx)
                    if current_position < len(assigned_problems) - 1:
                        st.session_state.current_index = assigned_problems[current_position + 1]
                        st.rerun()
                    else:
                        st.balloons()
                        st.success(f"🎉 All your assigned problems rated! ({num_assigned} problems)")

            st.caption(rating_label)

    # Show current rating if exists
    if existing_rating:
        st.success(f"✅ Current rating: **{existing_rating}** - {RATING_SCALE[existing_rating]}")

    # Navigation buttons at bottom (within assigned problems)
    col1, col2, col3 = st.columns([1, 2, 1])

    current_position = assigned_problems.index(current_idx)
    is_first = current_position == 0
    is_last = current_position == len(assigned_problems) - 1

    with col1:
        if st.button("⬅️ Previous", disabled=is_first, use_container_width=True):
            st.session_state.current_index = assigned_problems[current_position - 1]
            st.rerun()

    with col3:
        if st.button("Next ➡️", disabled=is_last, use_container_width=True):
            st.session_state.current_index = assigned_problems[current_position + 1]
            st.rerun()

    # Show progress in sidebar
    st.sidebar.markdown("---")
    st.sidebar.metric("Your Progress", f"{num_rated} / {num_assigned}")
    st.sidebar.progress(num_rated / num_assigned if num_assigned > 0 else 0)

if __name__ == "__main__":
    main()
