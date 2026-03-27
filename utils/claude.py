"""Anthropic Claude API integration and prompt templates for genetics counseling."""

import streamlit as st
import anthropic

MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 4096

# ---------------------------------------------------------------------------
# System prompt — tuned for graduate genetic counseling
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are an expert genetics study assistant designed to support graduate students in genetic counseling programs. Your role is to help students learn, understand, and apply genetics concepts at a graduate academic level.

## Your Expertise
- Molecular genetics, genomics, and cytogenetics
- Mendelian and complex inheritance patterns
- Variant interpretation (ACMG/AMP guidelines, ClinVar, OMIM)
- Genetic testing methodologies (NGS, microarray, FISH, karyotype, biochemical)
- Genetic counseling theory, ethics, and psychosocial principles
- Population genetics and risk calculation
- Prenatal, pediatric, cancer, and adult-onset genetics
- Common syndromes, inborn errors of metabolism, and rare diseases

## Behavior Guidelines

**Accuracy first:** Use precise genetics terminology. Never fabricate gene names, variant classifications, inheritance statistics, or clinical details. If you are uncertain about a specific fact, explicitly say so (e.g., "I'm not certain of the exact penetrance figure — please verify in OMIM or a current reference").

**Citation-aware:** When document context is provided, ground your answers in that material and cite sources as [Source N] inline. At the end of your response, list the sources you referenced.

**Flag uncertainty:** Clearly distinguish between well-established knowledge and areas of active research or clinical debate. Use phrases like "Current evidence suggests...", "This is an area of ongoing research...", or "I am not confident about this specific detail."

**Educational tone:** Explain reasoning, not just answers. Help the student build understanding, not just get a correct answer. Use analogies where helpful.

**Clinical caution:** This app is for educational purposes only. Never provide direct patient management advice. If a question crosses into clinical territory, note: "For actual patient care, consult current guidelines and supervising clinicians."

## Response Format
- Use headers (##) and bullet points for clarity when appropriate
- For Q&A: Lead with a direct answer, then explain reasoning
- For essays: Provide structured academic prose with an introduction, organized body paragraphs, and a conclusion
- Always list sources used at the bottom under "## Sources Used"
"""

QA_USER_TEMPLATE = """## Question
{question}

## Relevant Document Context
{context}

Please answer the question based on the provided context. Cite sources inline as [Source N]. If the context does not contain enough information to fully answer the question, supplement with your knowledge and clearly indicate which parts come from the documents versus your general knowledge."""

ESSAY_USER_TEMPLATE = """## Essay Prompt / Question
{prompt}

## Reference Material
{context}

Please draft a well-structured academic response appropriate for a graduate genetic counseling student. Use the reference material as your primary sources, citing them inline as [Source N]. Organize your response with clear sections. Be thorough but concise — aim for a response that demonstrates graduate-level understanding of the topic."""


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def get_client() -> anthropic.Anthropic:
    """Create an Anthropic client using the API key from st.secrets."""
    try:
        api_key = st.secrets["ANTHROPIC_API_KEY"]
    except KeyError:
        st.error("ANTHROPIC_API_KEY not found in st.secrets.")
        st.stop()
    return anthropic.Anthropic(api_key=api_key)


def ask_question(
    question: str,
    context: str,
    conversation_history: list[dict],
) -> str:
    """
    Send a Q&A request to Claude with document context.

    Args:
        question: The student's question.
        context: Formatted context string from retriever.
        conversation_history: Prior messages in [{role, content}] format.

    Returns:
        Claude's response as a string.
    """
    client = get_client()

    user_message = QA_USER_TEMPLATE.format(
        question=question,
        context=context,
    )

    messages = list(conversation_history) + [
        {"role": "user", "content": user_message}
    ]

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=messages,
    )

    return response.content[0].text


def draft_essay(
    prompt: str,
    context: str,
    conversation_history: list[dict],
) -> str:
    """
    Send an essay/response drafting request to Claude.

    Args:
        prompt: The essay question or writing prompt.
        context: Formatted context string from retriever.
        conversation_history: Prior messages in [{role, content}] format.

    Returns:
        Claude's drafted response as a string.
    """
    client = get_client()

    user_message = ESSAY_USER_TEMPLATE.format(
        prompt=prompt,
        context=context,
    )

    messages = list(conversation_history) + [
        {"role": "user", "content": user_message}
    ]

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=messages,
    )

    return response.content[0].text


def stream_response(
    user_message_content: str,
    conversation_history: list[dict],
) -> str:
    """
    Stream a response from Claude, yielding text chunks to a Streamlit container.
    Returns the full response text.
    """
    client = get_client()

    messages = list(conversation_history) + [
        {"role": "user", "content": user_message_content}
    ]

    full_text = ""
    placeholder = st.empty()

    with client.messages.stream(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=messages,
    ) as stream:
        for text in stream.text_stream:
            full_text += text
            placeholder.markdown(full_text + "▌")

    placeholder.markdown(full_text)
    return full_text
