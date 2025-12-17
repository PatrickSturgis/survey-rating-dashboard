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

def load_problems():
    """Load the problems CSV"""
    return pd.read_csv(PROBLEMS_FILE)

def main():
    st.set_page_config(page_title="Survey Problem Rating", layout="wide")

    # Load data
    problems_df = load_problems()
    total_problems = len(problems_df)

    # Sidebar for rater ID and navigation
    st.sidebar.title("Rating Dashboard")

    # Rater assignment
    RATER_ASSIGNMENTS = {
        "Tom": "first_half",
        "Caroline": "first_half",
        "Becky": "second_half",
        "Alice": "second_half",
        "Patrick - First Half": "first_half",
        "Patrick - Second Half": "second_half"
    }

    # Rater ID dropdown
    if 'rater_id' not in st.session_state:
        st.session_state.rater_id = ""

    rater_id = st.sidebar.selectbox(
        "Select your name:",
        options=[""] + list(RATER_ASSIGNMENTS.keys()),
        help="Select your name to begin rating your assigned problems"
    )

    if rater_id:
        st.session_state.rater_id = rater_id
    else:
        st.warning("⚠️ Please select your name in the sidebar to begin rating.")
        return

    # Initialize ratings storage in session state
    if 'ratings' not in st.session_state:
        st.session_state.ratings = {}

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

    # Initialize current problem index
    if 'current_index' not in st.session_state:
        st.session_state.current_index = assigned_problems[0]

    # Ensure current index is within assigned problems
    if st.session_state.current_index not in assigned_problems:
        st.session_state.current_index = assigned_problems[0]

    # Progress tracking
    num_rated = len([p for p in assigned_problems if p in st.session_state.ratings])
    num_assigned = len(assigned_problems)

    # Warning about session storage and periodic reminders
    if num_rated == 0:
        st.sidebar.warning("⚠️ **Important:** Download your ratings regularly! If the app refreshes, you'll lose unsaved progress.")
    elif num_rated > 0 and num_rated % 20 == 0:
        st.sidebar.info(f"💾 You've rated {num_rated} problems. Consider downloading your CSV as a backup!")

    # Navigation
    st.sidebar.subheader("Navigation")

    # Jump to problem
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

    # Filter to unrated problems if requested
    if show_unrated_only:
        unrated_indices = [i for i in assigned_problems if i not in st.session_state.ratings]
        if unrated_indices:
            if st.session_state.current_index not in unrated_indices:
                st.session_state.current_index = unrated_indices[0]
        else:
            st.success(f"🎉 All your assigned problems have been rated! ({num_assigned} problems)")
            st.info("👇 Download your ratings below!")

            # Show download button
            ratings_list = []
            for prob_idx in assigned_problems:
                if prob_idx in st.session_state.ratings:
                    problem = problems_df.iloc[prob_idx]
                    ratings_list.append({
                        'problem_index': prob_idx,
                        'question_id': problem['question_id'],
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

    # Problem description
    st.warning(f"**Problem Identified:** {problem['problem_description']}")

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
                # Save rating
                st.session_state.ratings[current_idx] = rating_num

                # Auto-advance to next problem
                current_position = assigned_problems.index(current_idx)
                if current_position < len(assigned_problems) - 1:
                    st.session_state.current_index = assigned_problems[current_position + 1]
                    st.rerun()
                else:
                    st.balloons()
                    st.success(f"🎉 All your assigned problems rated! ({num_assigned} problems)")
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
    st.sidebar.metric("Your Progress", f"{num_rated} / {num_assigned}")
    st.sidebar.progress(num_rated / num_assigned if num_assigned > 0 else 0)

    # Download button in sidebar (even if not finished)
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
