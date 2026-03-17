#!/usr/bin/env python3
"""
Survey Problem Rating Dashboard - Session State Version

Stores ratings in browser session, raters download their CSV when done.
"""

import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime
import json

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

RATERS = ["Tom", "Caroline", "Becky", "Alice", "Patrick"]

def load_problems():
    """Load the problems CSV"""
    return pd.read_csv(PROBLEMS_FILE)

def main():
    st.set_page_config(page_title="Survey Problem Rating", layout="wide")

    # Load data
    problems_df = load_problems()
    total_problems = len(problems_df)
    assigned_problems = list(range(total_problems))

    # Sidebar for rater ID and navigation
    st.sidebar.title("Rating Dashboard")

    # Rater ID dropdown
    if 'rater_id' not in st.session_state:
        st.session_state.rater_id = ""

    rater_id = st.sidebar.selectbox(
        "Select your name:",
        options=[""] + RATERS,
        help="Select your name to begin rating"
    )

    if rater_id:
        st.session_state.rater_id = rater_id
    else:
        st.warning("⚠️ Please select your name in the sidebar to begin rating.")
        return

    st.sidebar.info(f"📋 {total_problems} problems to rate")

    # Initialize ratings storage in session state
    if 'ratings' not in st.session_state:
        st.session_state.ratings = {}

    # Initialize current problem index
    if 'current_index' not in st.session_state:
        st.session_state.current_index = 0

    # Progress tracking
    num_rated = len([p for p in assigned_problems if p in st.session_state.ratings])

    # Navigation
    st.sidebar.subheader("Navigation")

    jump_to = st.sidebar.number_input(
        f"Jump to problem (1-{total_problems}):",
        min_value=1,
        max_value=total_problems,
        value=st.session_state.current_index + 1
    )
    if st.sidebar.button("Go"):
        st.session_state.current_index = jump_to - 1
        st.rerun()

    # Show unrated problems only toggle
    show_unrated_only = st.sidebar.checkbox("Show unrated problems only")

    # Filter to unrated problems if requested
    if show_unrated_only:
        unrated_indices = [i for i in assigned_problems if i not in st.session_state.ratings]
        if unrated_indices:
            if st.session_state.current_index not in unrated_indices:
                st.session_state.current_index = unrated_indices[0]
        else:
            st.success(f"🎉 All {total_problems} problems have been rated!")
            st.info("👇 Download your ratings below!")

            ratings_list = []
            for prob_idx in assigned_problems:
                if prob_idx in st.session_state.ratings:
                    problem = problems_df.iloc[prob_idx]
                    ratings_list.append({
                        'problem_index': prob_idx,
                        'question_id': problem['question_id'],
                        'source': problem.get('source', ''),
                        'code_label': problem.get('code_label', ''),
                        'rating': st.session_state.ratings[prob_idx],
                        'rater_id': rater_id
                    })

            if ratings_list:
                df_download = pd.DataFrame(ratings_list)
                csv = df_download.to_csv(index=False)
                st.download_button(
                    label="📥 Download Your Ratings (CSV)",
                    data=csv,
                    file_name=f"{rater_id}_ratings_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            return

    # Current problem
    current_idx = st.session_state.current_index
    problem = problems_df.iloc[current_idx]

    # Main content
    st.markdown(f"## Problem {current_idx + 1} of {total_problems}")

    # Question display
    st.info(f"**{problem['question_id']}:** {problem['question_text']}\n\n**Response options:** {problem['response_options']}")

    # Problem code and description (source model hidden from raters)
    label = problem.get('code_label', '')
    st.warning(f"**{label}**\n\n{problem['problem_description']}")

    # Rating interface
    st.markdown("**How would you rate the severity of this problem?**")

    # Get existing rating if any
    existing_rating = st.session_state.ratings.get(current_idx)

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
                st.session_state.ratings[current_idx] = rating_num

                current_position = assigned_problems.index(current_idx)
                if current_position < len(assigned_problems) - 1:
                    st.session_state.current_index = assigned_problems[current_position + 1]
                    st.rerun()
                else:
                    st.balloons()
                    st.success(f"🎉 All {total_problems} problems rated!")
                    st.rerun()

            st.caption(rating_label)

    # Show current rating if exists
    if existing_rating:
        st.success(f"✅ Current rating: **{existing_rating}** - {RATING_SCALE[existing_rating]}")

    # Navigation buttons at bottom
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

    # Progress in sidebar
    st.sidebar.markdown("---")
    st.sidebar.metric("Progress", f"{num_rated} / {total_problems}")
    st.sidebar.progress(num_rated / total_problems if total_problems > 0 else 0)

    # Download button in sidebar
    st.sidebar.markdown("---")
    if num_rated > 0:
        st.sidebar.markdown("### Download Ratings")

        ratings_list = []
        for prob_idx in assigned_problems:
            if prob_idx in st.session_state.ratings:
                problem = problems_df.iloc[prob_idx]
                ratings_list.append({
                    'problem_index': prob_idx,
                    'question_id': problem['question_id'],
                    'source': problem.get('source', ''),
                    'code_label': problem.get('code_label', ''),
                    'rating': st.session_state.ratings[prob_idx],
                    'rater_id': rater_id
                })

        if ratings_list:
            df_download = pd.DataFrame(ratings_list)
            csv = df_download.to_csv(index=False)
            st.sidebar.download_button(
                label="📥 Download CSV",
                data=csv,
                file_name=f"{rater_id}_ratings_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
            st.sidebar.caption(f"{num_rated} rating(s) ready to download")

if __name__ == "__main__":
    main()
