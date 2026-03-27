# Genetics Study Assistant

A mobile-first Streamlit app for graduate genetic counseling students. Upload PDFs and Google Docs to your Drive, then ask questions or draft essay responses powered by Claude claude-sonnet-4-20250514.

---

## Features

- **Password-gated access** — simple shared password via `st.secrets`
- **Google Drive integration** — browse folders, select PDFs and Google Docs
- **Two modes:**
  - **Q&A** — ask a question, get a cited answer grounded in your documents
  - **Essay / Drafting** — provide a prompt, get a structured academic response
- **TF-IDF retrieval** — top chunks ranked by cosine similarity, no external vector DB needed
- **Mobile-first UI** — large tap targets, responsive layout, sidebar collapses on mobile
- **Streaming responses** — real-time text output from Claude

---

## Quick Start (local dev)

### 1. Clone & install

```bash
git clone <repo-url>
cd genetics-study-assistant
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure secrets

Create `.streamlit/secrets.toml` (never commit this file):

```toml
app_password = "your-password-here"
ANTHROPIC_API_KEY = "sk-ant-..."
GOOGLE_CLIENT_ID = "xxxx.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET = "GOCSPX-..."
GOOGLE_REDIRECT_URI = "http://localhost:8501"
```

### 3. Run

```bash
streamlit run app.py
```

---

## Setting Up Google Cloud OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/) → **APIs & Services** → **Credentials**
2. Click **Create Credentials** → **OAuth client ID**
3. Set **Application type** to **Web application**
4. Under **Authorized redirect URIs**, add:
   - `http://localhost:8501` (local dev)
   - `https://<your-app>.streamlit.app` (production)
5. Click **Create** — copy the **Client ID** and **Client Secret**
6. Go to **APIs & Services** → **Library** and enable the **Google Drive API**
7. Configure the **OAuth consent screen** (External type is fine for personal use):
   - Add your email as a test user
   - Add the scope: `https://www.googleapis.com/auth/drive.readonly`

---

## Deploying to Streamlit Community Cloud

1. Push your repo to GitHub (make sure `.streamlit/secrets.toml` is in `.gitignore`)
2. Go to [share.streamlit.io](https://share.streamlit.io) → **New app**
3. Select your repo, branch, and `app.py` as the main file
4. Click **Advanced settings** → **Secrets** and paste:

```toml
app_password = "your-password-here"
ANTHROPIC_API_KEY = "sk-ant-..."
GOOGLE_CLIENT_ID = "xxxx.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET = "GOCSPX-..."
GOOGLE_REDIRECT_URI = "https://<your-app-url>.streamlit.app"
```

5. Deploy! After the first deploy, copy the exact app URL and update:
   - `GOOGLE_REDIRECT_URI` in Streamlit secrets
   - The authorized redirect URI in Google Cloud Console (must match exactly)

---

## Project Structure

```
app.py                  # Main Streamlit entry point
requirements.txt        # Pinned dependencies
.env.example            # Template for required environment variables
README.md               # This file
utils/
  auth.py               # Password gate logic
  drive.py              # Google Drive OAuth2 + file fetching
  chunker.py            # Text extraction (PDF, Google Docs) + chunking
  retriever.py          # TF-IDF cosine similarity ranking
  claude.py             # Anthropic API calls + prompt templates
```

---

## Secrets Reference

| Key | Description |
|---|---|
| `app_password` | Shared password for the app login screen |
| `ANTHROPIC_API_KEY` | Your Anthropic API key |
| `GOOGLE_CLIENT_ID` | Google OAuth2 client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth2 client secret |
| `GOOGLE_REDIRECT_URI` | Exact redirect URI (must match Google Cloud Console) |

---

## Notes

- **No vector database required** — retrieval uses scikit-learn TF-IDF, which runs entirely in-process
- **Document chunking** — ~1000 token chunks with 100 token overlap; Q&A uses top 5 chunks, Essay uses top 10
- **PDF support** — uses `pdfplumber` (primary) with `pypdf` as fallback
- **Session persistence** — conversation history, loaded documents, and auth state persist within a Streamlit session but reset on page refresh
- **Model** — `claude-sonnet-4-20250514` via the Anthropic Python SDK
