import os
import time
from dotenv import load_dotenv
import google.generativeai as genai
import streamlit as st
import wikipedia
import requests
import json
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from textwrap import wrap
import re
import asyncio
import aiohttp
import streamlit_lottie as st_lottie
from gtts import gTTS

# Register Unicode font for Indian language support
font_path = os.path.join(os.path.dirname(__file__), 'NotoSans-Regular.ttf')
if not os.path.exists(font_path):
    st.error("Font file 'NotoSans-Regular.ttf' not found! Please add it to the project directory for PDF export.")
else:
    pdfmetrics.registerFont(TTFont('NotoSans', font_path))

# Load environment variables from .env
load_dotenv()

# API Keys
gemini_api_key = st.secrets["GEMINI_API_KEY"]
serper_api_key = st.secrets["SERPER_API_KEY"]
gemini_model = "gemini-2.5-flash-preview-04-17"

# Configure Gemini
genai.configure(api_key=gemini_api_key)

# Set Streamlit page config
st.set_page_config(
    page_title="Agentic AI",
    page_icon="🧠",
    layout="wide",  # Changed from 'centered' to 'wide' for full screen
    initial_sidebar_state="expanded"
)

# Set multicolor background using custom CSS
st.markdown(
    """
    <style>
    body {
        background: linear-gradient(135deg, #f5d020 0%, #f53803 25%, #21d4fd 50%, #b721ff 75%, #fdc830 100%);
        background-attachment: fixed;
        animation: gradientBG 10s ease-in-out infinite;
        background-size: 400% 400%;
    }
    @keyframes gradientBG {
        0% {background-position: 0% 50%;}
        50% {background-position: 100% 50%;}
        100% {background-position: 0% 50%;}
    }
    .stApp {
        background: transparent;
    }
    .main-title {
        font-size: 2.8rem;
        font-weight: bold;
        color: #fff;
        text-shadow: 2px 2px 8px #00000055;
        margin-bottom: 0.5em;
        text-align: center;
        letter-spacing: 2px;
    }
    .subtitle {
        font-size: 1.3rem;
        color: #fff;
        text-align: center;
        margin-bottom: 1.5em;
        text-shadow: 1px 1px 6px #00000033;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Lottie animation
def load_lottieurl(url: str):
    r = requests.get(url)
    if r.status_code != 200:
        return None
    return r.json()

lottie_ai = load_lottieurl("https://assets2.lottiefiles.com/packages/lf20_kyu7xb1v.json")

st_lottie.st_lottie(
    lottie_ai,
    speed=1,
    reverse=False,
    loop=True,
    quality="high",
    height=200,
    key="ai-animation"
)

# Title
st.markdown('<div class="main-title">🔍 Agentic AI: Research & Writing Agent</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Gemini API configured successfully' if gemini_api_key else '❌ Missing Gemini API Key' + '</div>', unsafe_allow_html=True)

# Language instruction mapping
language_map = {
    "English": "Write in English.",
    "Hindi": "Write in Hindi.",
    "Tamil": "Write in Tamil.",
    "Telugu": "Write in Telugu.",
    "Bengali": "Write in Bengali.",
    "Marathi": "Write in Marathi.",
    "Kannada": "Write in Kannada.",
    "Gujarati": "Write in Gujarati.",
    "Malayalam": "Write in Malayalam.",
    "Punjabi": "Write in Punjabi."
}

# Research Functions
def search_wikipedia(topic):
    try:
        # Try searching with underscores (Wikipedia expects underscores for multi-word topics)
        topic_query = topic.replace(' ', '_')
        summary = wikipedia.summary(topic_query, sentences=5)
        page = wikipedia.page(topic_query)
        image_url = page.images[0] if page.images else None
        return summary, [page.url], image_url, None
    except wikipedia.exceptions.DisambiguationError as e:
        # Provide the first suggested topic's summary if possible
        try:
            first_option = e.options[0]
            summary = wikipedia.summary(first_option, sentences=5)
            page = wikipedia.page(first_option)
            image_url = page.images[0] if page.images else None
            info_msg = f"Disambiguation: Showing results for '{first_option}' instead of ambiguous topic '{topic}'."
            return f"{info_msg}\n\n{summary}", [page.url], image_url, None
        except Exception:
            return None, [], None, f"Disambiguation error: The topic '{topic}' is ambiguous. Please be more specific."
    except wikipedia.exceptions.PageError:
        # Try again with the original topic (spaces) as a fallback
        try:
            summary = wikipedia.summary(topic, sentences=5)
            page = wikipedia.page(topic)
            image_url = page.images[0] if page.images else None
            return summary, [page.url], image_url, None
        except Exception:
            # Try to search for related topics and return the first found
            search_results = wikipedia.search(topic)
            if search_results:
                try:
                    first_result = search_results[0]
                    summary = wikipedia.summary(first_result, sentences=5)
                    page = wikipedia.page(first_result)
                    image_url = page.images[0] if page.images else None
                    info_msg = f"No exact page found. Showing results for related topic '{first_result}'."
                    return f"{info_msg}\n\n{summary}", [page.url], image_url, None
                except Exception:
                    pass
            return "No Wikipedia page found, and no close matches found. Please try a different or more specific topic.", [], None, None
    except Exception as e:
        return None, [], None, f"Error: {str(e)}"

def search_serper(topic):
    headers = {"X-API-KEY": serper_api_key}
    payload = {"q": topic, "gl": "in"}
    try:
        res = requests.post("https://google.serper.dev/search",
                            headers=headers,
                            json=payload)
        data = res.json()
        results = data.get("organic", [])
        if results:
            summary = results[0].get("snippet", "No summary available.")
            links = [item["link"] for item in results[:3]]
            # Try to get an image from the first result
            image_url = results[0].get("imageUrl") if results[0].get("imageUrl") else None
            return summary, links, image_url, None
        return "No results found.", [], None, None
    except Exception as e:
        return None, [], None, f"Error: {str(e)}"

def search_duckduckgo(topic):
    try:
        res = requests.get(f"https://api.duckduckgo.com/?q={topic}&format=json")
        data = res.json()
        summary = data.get("AbstractText", "").strip()
        link = data.get("AbstractURL", "")
        image_url = data.get("Image", None)
        return summary, [link] if link else [], image_url, None
    except Exception as e:
        return None, [], None, f"Error: {str(e)}"

# Async Research Functions
async def async_search_wikipedia(topic):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, search_wikipedia, topic)

async def async_search_serper(topic):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, search_serper, topic)

async def async_search_duckduckgo(topic):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, search_duckduckgo, topic)

# Citation generator (APA style)
def generate_apa_citation(title, url):
    year = str(time.localtime().tm_year)
    return f"{title}. ({year}). Retrieved from {url}"

# Agents
def create_subtopics(topic, language):
    with st.spinner("🧠 Planning subtopics..."):
        try:
            model = genai.GenerativeModel(gemini_model)
            response = model.generate_content(
                f"Break '{topic}' into 3-5 sub-topics in {language}. Numbered list only."
            )
            return [line for line in response.text.split("\n") if line.strip()]
        except Exception as e:
            st.error(f"Planning Agent Error: {str(e)}")
            return []

def reflect_on_article(article, language):
    with st.spinner("🔍 Reviewing article..."):
        try:
            model = genai.GenerativeModel(gemini_model)
            prompt = f"""Review this {language} article for:
            1. Missing citations
            2. Structural issues
            3. Length adequacy
            Return IMPROVED VERSION only:\n\n{article}"""
            return model.generate_content(prompt).text
        except Exception as e:
            st.error(f"Reflection Agent Error: {str(e)}")
            return article

def create_summary(article, language):
    with st.spinner("📝 Generating summary..."):
        try:
            model = genai.GenerativeModel(gemini_model)
            prompt = f"Summarize this {article} article into 3-4 engaging sentences:\n\n in {language} language"
            return model.generate_content(prompt).text
        except Exception as e:
            st.error(f"Summary Agent Error: {str(e)}")
            return "Summary generation failed"

def create_related_topics(topic, language):
    with st.spinner("🧠 Suggesting related topics..."):
        try:
            model = genai.GenerativeModel(gemini_model)
            prompt = f"Suggest 3 related topics for '{topic}' in {language}."
            response = model.generate_content(prompt)
            return [line.strip() for line in response.text.split("\n") if line.strip()]
        except Exception as e:
            st.error(f"Related Topics Agent Error: {str(e)}")
            return []

# Input validation function
def validate_topic(topic):
    if not topic or len(topic.strip()) < 3:
        return "Topic is too short. Please enter a more descriptive topic."
    if len(topic.strip()) > 100:
        return "Topic is too long. Please shorten your topic."
    if re.search(r'[^\w\s\-.,]', topic):
        return "Topic contains special characters. Please use only letters, numbers, spaces, hyphens, commas, and periods."
    if topic.lower() in ["test", "sample", "topic", "subject"]:
        return "Topic is too generic. Please enter a more specific topic."
    return None

# UI Inputs
with st.container():
    st.subheader("Welcome to the AI Research Assistant!")
    st.write("This tool helps you generate research content based on your preferences.")
    col1, col2 = st.columns([2, 1])
    with col1:
        topic = st.text_input("Enter your topic:", placeholder="e.g., Braion rot")
        depth = st.radio("Choose research depth:", ["Basic", "Detailed"], horizontal=True)
        style = st.radio("Choose writing style:", ["Informative", "Opinionated"], horizontal=True)
    with col2:
        language = st.selectbox("Select language:", list(language_map.keys()))
        search_engine = st.selectbox("Choose a search engine:", ["Wikipedia", "Serper", "DuckDuckGo"])
        theme = st.radio("Theme", ["Light", "Dark"], index=0, horizontal=True, key="theme_radio_main")
        if theme == "Dark":
            st.markdown(
                """
                <style>
                body, .stApp {
                    background: #181818 !important;
                    color: #f5f5f5 !important;
                }
                .main-title, .subtitle {
                    color: #f5d020 !important;
                }
                </style>
                """,
                unsafe_allow_html=True
            )

progress = st.empty()

if st.button("🚀 Run Agentic AI") and topic:
    # Input validation
    validation_error = validate_topic(topic)
    if validation_error:
        st.warning(validation_error)
        st.stop()
    with st.status("🔍 Starting research process...", expanded=True) as status:
        try:
            progress.progress(0, text="Researching...")
            st.write("## Phase 1: Research")
            # Async research
            async def do_research():
                if search_engine == "Wikipedia":
                    return await async_search_wikipedia(topic)
                elif search_engine == "Serper":
                    return await async_search_serper(topic)
                else:
                    return await async_search_duckduckgo(topic)
            try:
                summary, links, image_url, error = asyncio.run(do_research())
            except Exception as e:
                st.error(f"Async error: {str(e)}. Try restarting the app or check your internet connection.")
                st.stop()
            if error:
                if "API key" in error:
                    st.error("API key error: Please check your .env file and ensure your API key is valid.")
                elif "ambiguous" in error:
                    st.warning(error + " Try specifying your topic further.")
                elif "No Wikipedia page found" in error:
                    st.warning(error + " Try a different or more specific topic.")
                elif "network" in error.lower() or "connection" in error.lower():
                    st.error("Network error: Please check your internet connection and try again.")
                else:
                    st.error(f"Research error: {error}")
                st.stop()
            progress.progress(25, text="Planning subtopics...")
            st.write("## Phase 2: Planning")
            subtopics = create_subtopics(topic, language)
            st.write(f"**Subtopics:**\n{chr(10).join(subtopics)}")
            progress.progress(50, text="Writing article...")
            st.write("## Phase 3: Writing")
            writing_prompt = f"""
            {language_map[language]}
            Write a {depth.lower()} article with these sub-topics:
            {chr(10).join(subtopics)}
            Style: {style.lower()}
            Include these research points: {summary}
            """
            model = genai.GenerativeModel(gemini_model)
            article = model.generate_content(writing_prompt).text
            progress.progress(75, text="Refining article...")
            st.write("## Phase 4: Refining")
            article = reflect_on_article(article, language)
            progress.progress(90, text="Summarizing article...")
            st.write("## Phase 5: Summarizing")
            final_summary = create_summary(article, language)
            st.session_state['article'] = article
            st.session_state['summary'] = final_summary
            st.session_state['links'] = links
            st.session_state['image_url'] = image_url
            progress.progress(100, text="Done!")
            # Related topics
            related_topics = create_related_topics(topic, language)
            st.session_state['related_topics'] = related_topics
            status.update(label="✅ Process Complete!", state="complete")
        except Exception as e:
            st.error(f"System Error: {str(e)}. If this persists, check your API keys, internet connection, or try again later.")
            st.stop()

# Retrieve from session state
article = st.session_state.get('article', '')
summary = st.session_state.get('summary', '')
links = st.session_state.get('links', [])
image_url = st.session_state.get('image_url', None)
related_topics = st.session_state.get('related_topics', [])

if article:
    with st.container():
        st.markdown("### 📝 Final Article")
        # Show image if available
        if image_url:
            st.image(image_url, use_column_width=True)
        with st.expander("Show/Hide Article", expanded=True):
            st.write(article)
            # Voice reader for article
            if st.button("🔊 Listen to Article"):
                tts = gTTS(article)
                audio_bytes = BytesIO()
                tts.write_to_fp(audio_bytes)
                audio_bytes.seek(1)
                st.audio(audio_bytes, format='audio/mp3')
        st.markdown("### 📌 Executive Summary")
        with st.expander("Show/Hide Summary", expanded=False):
            st.write(summary)
            # Voice reader for summary
            if summary and st.button("🔊 Listen to Summary"):
                tts_sum = gTTS(summary)
                audio_bytes_sum = BytesIO()
                tts_sum.write_to_fp(audio_bytes_sum)
                audio_bytes_sum.seek(1)
                st.audio(audio_bytes_sum, format='audio/mp3')
        if links:
            st.markdown("### 📚 References")
            with st.expander("Show/Hide References", expanded=False):
                for link in links:
                    # Try to fetch the Wikipedia page title for citation, fallback to URL
                    try:
                        page_title = wikipedia.page(link).title if 'wikipedia.org' in link else link
                    except Exception:
                        page_title = link
                    citation = generate_apa_citation(page_title, link)
                    st.markdown(f"- [{link}]({link})\n    <br><span style='font-size:0.9em;color:#888;'>APA: {citation}</span>", unsafe_allow_html=True)
        if related_topics:
            st.markdown("### 🔗 Related Topics")
            st.write("\n".join(related_topics))
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                "⬇️ Download as Text File",
                article,
                file_name=f"{topic.replace(' ', '_')}_article.txt",
                mime="text/plain"
            )
else:
    st.info("🧠 Enter a topic and run the agent to generate article content.")

if not gemini_api_key:
    st.error("Gemini API key missing! Check .env file")
if not serper_api_key and search_engine == "Serper":
    st.error("Serper API key missing! Check .env file")
