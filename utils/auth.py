"""Password gate logic for the genetics study assistant."""

import streamlit as st


def check_password() -> bool:
    """
    Show a password input and validate against st.secrets["app_password"].
    Returns True if authenticated, False otherwise.
    Stores auth state in st.session_state["authenticated"].
    """
    if st.session_state.get("authenticated"):
        return True

    st.markdown(
        """
        <style>
        .auth-container {
            max-width: 400px;
            margin: 10vh auto 0 auto;
            padding: 2rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.container():
        st.markdown("## Genetics Study Assistant")
        st.markdown("Enter your password to access the app.")

        password = st.text_input(
            "Password",
            type="password",
            placeholder="Enter password...",
            key="password_input",
        )
        submit = st.button("Unlock", use_container_width=True, type="primary")

        if submit:
            try:
                correct_password = st.secrets["app_password"]
            except KeyError:
                st.error("App password not configured. Add `app_password` to your secrets.")
                return False

            if password == correct_password:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Incorrect password. Please try again.")

    return False
