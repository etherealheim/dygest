import streamlit as st
import yt_dlp
import requests
import os
import re
from youtube_transcript_api import YouTubeTranscriptApi
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get API key from environment variable
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")

# Anthropic API endpoint
API_ENDPOINT = "https://api.anthropic.com/v1/messages"

# Dictionary of languages with their ISO 639-1 codes
LANGUAGES = {
    "English": "en",
    "German": "de",
    "French": "fr",
    "Spanish": "es",
    "Italian": "it",
    "Japanese": "ja",
    "Korean": "ko",
    "Portuguese": "pt",
    "Russian": "ru",
    "Chinese": "zh"
}

def sanitize_filename(filename):
    sanitized = re.sub(r'[\\/*?:"<>|]', "", filename)
    sanitized = sanitized.replace(' ', '_')
    return sanitized[:200]

def extract_video_id(url):
    if "youtu.be" in url:
        return url.split("/")[-1]
    elif "youtube.com" in url:
        return url.split("v=")[1].split("&")[0]
    else:
        return None

def get_transcript(video_id, lang_code):
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=[lang_code])
        return " ".join([entry['text'] for entry in transcript])
    except Exception as e:
        return f"Error getting transcript: {str(e)}"

def download_video(url, new_title):
    try:
        safe_title = sanitize_filename(new_title)
        ydl_opts = {
            'format': 'mp4',
            'outtmpl': f'{safe_title}.%(ext)s'
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return f'{safe_title}.mp4'
    except Exception as e:
        return f"Error downloading video: {str(e)}"

def get_summary(text, lang):
    headers = {
        "Content-Type": "application/json",
        "x-api-key": CLAUDE_API_KEY,
        "anthropic-version": "2023-06-01"
    }
    data = {
        "model": "claude-3-opus-20240229",
        "messages": [
            {"role": "user", "content": f"Please summarize the following video transcript in {lang}:\n\n{text}"}
        ],
        "max_tokens": 300
    }
    try:
        response = requests.post(API_ENDPOINT, json=data, headers=headers)
        response.raise_for_status()
        return response.json()['content'][0]['text']
    except requests.exceptions.RequestException as e:
        error_message = f"Summary API Error: {str(e)}"
        if hasattr(e, 'response') and e.response is not None:
            error_message += f"\nResponse content: {e.response.text}"
        return error_message

def generate_video_title(summary, lang):
    headers = {
        "Content-Type": "application/json",
        "x-api-key": CLAUDE_API_KEY,
        "anthropic-version": "2023-06-01"
    }
    data = {
        "model": "claude-3-opus-20240229",
        "messages": [
            {"role": "user", "content": f"Based on the following summary, generate a short, descriptive title for the video (EXACTLY 25 characters, including spaces) in {lang}:\n\n{summary}"}
        ],
        "max_tokens": 100
    }
    try:
        response = requests.post(API_ENDPOINT, json=data, headers=headers)
        response.raise_for_status()
        title = response.json()['content'][0]['text'].strip()
        # Ensure the title is exactly 25 characters
        if len(title) > 25:
            title = title[:25]
        elif len(title) < 25:
            title = title.ljust(25)
        return title
    except requests.exceptions.RequestException as e:
        error_message = f"Title Generation Error: {str(e)}"
        if hasattr(e, 'response') and e.response is not None:
            error_message += f"\nResponse content: {e.response.text}"
        return error_message

st.markdown("""
<style>
.small-text {
    font-size: 1.2em;
    color: #666;
}
</style>
""", unsafe_allow_html=True)

st.title('Dygest')
st.markdown('<p class="small-text">Summarize and Download YouTube Videos</p>', unsafe_allow_html=True)

col1, col2 = st.columns([2, 1])

with col1:
    youtube_url = st.text_input('Enter YouTube URL:')

with col2:
    selected_language = st.selectbox('Select Language', list(LANGUAGES.keys()))
    auto_download = st.toggle('Auto Download', value=True)

if st.button('Process Video'):
    if youtube_url:
        video_id = extract_video_id(youtube_url)
        if video_id:
            lang_code = LANGUAGES[selected_language]
            
            # Get transcript
            transcript = get_transcript(video_id, lang_code)
            st.subheader('Video Transcript')
            st.text_area('Transcript', transcript, height=200)

            # Get summary
            if not transcript.startswith("Error"):
                summary = get_summary(transcript, selected_language)
                st.subheader('Video Summary')
                st.text_area('Summary', summary, height=200)

                # Generate new video title
                new_title = generate_video_title(summary, selected_language)
                if not new_title.startswith("Title Generation Error"):
                    st.subheader('Generated Video Title')
                    st.write(new_title)

                    # Download video if auto-download is enabled
                    if auto_download:
                        st.subheader('Video Download')
                        with st.spinner('Downloading video... This may take a while.'):
                            video_path = download_video(youtube_url, new_title)
                            if not video_path.startswith("Error"):
                                st.success(f"Video downloaded successfully as '{video_path}'")
                            else:
                                st.error(video_path)
                    else:
                        st.info("Auto-download is disabled. Video was not downloaded.")
                else:
                    st.error(new_title)
            else:
                st.error("Cannot generate summary due to transcript error.")
        else:
            st.error('Invalid YouTube URL')
    else:
        st.error('Please enter a YouTube URL')