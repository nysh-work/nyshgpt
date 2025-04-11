import streamlit as st
import datetime
import os
import google.generativeai as genai
import requests
import time
from ics import Calendar, Event
import speech_recognition as sr
import pyttsx3
from gtts import gTTS
import tempfile
import threading
import queue
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# === USER CONFIG ===
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]  # Store this in .streamlit/secrets.toml
CAPACITIES_SPACE_ID = "b50fd297-0053-4975-bd95-805920f11d1d"
JOURNAL_OBJECT_TYPE_ID = "e0d4f9f7-87f1-4cef-98d1-fcb1308b8458"

# === INIT GEMINI ===
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-pro-preview-03-25")

st.set_page_config(page_title="Nysh GPT", page_icon="📱", layout="centered", initial_sidebar_state="collapsed")

# Add app title with custom styling
st.markdown("""
<style>
    .app-title {
        font-size: 2.5rem;
        font-weight: 800;
        color: #805AD5;
        text-align: center;
        margin-bottom: 1.5rem;
        background: linear-gradient(90deg, #805AD5, #4F46E5);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<h1 class="app-title">Nysh GPT</h1>', unsafe_allow_html=True)

# Add custom CSS for better styling
st.markdown("""
<style>
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    h1 {
        font-weight: 700;
        margin-bottom: 0.5rem;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
        padding: 0 1rem;
        margin-bottom: 1.5rem;
        display: flex;
        justify-content: center;
    }
    .stTabs [data-baseweb="tab"] {
        height: 60px;
        white-space: pre-wrap;
        border-radius: 8px;
        font-weight: 600;
        font-size: 1rem;
        padding: 0 1.5rem;
        transition: all 0.2s ease;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .stTabs [data-baseweb="tab"]:hover {
        background-color: rgba(128, 90, 213, 0.05);
        transform: translateY(-2px);
    }
    .stTabs [aria-selected="true"] {
        background-color: rgba(128, 90, 213, 0.15);
        border-bottom: 3px solid rgb(128, 90, 213);
        color: #805AD5;
    }
    .stButton button {
        border-radius: 4px;
        font-weight: 500;
    }
    .stTextArea textarea {
        border-radius: 4px;
    }
    .stAlert {
        border-radius: 4px;
    }
    .css-1y4p8pa {
        max-width: 900px;
    }
    .voice-btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        background-color: #f0f2f6;
        border-radius: 50%;
        width: 40px;
        height: 40px;
        cursor: pointer;
        margin: 0 5px;
        transition: all 0.2s;
    }
    .voice-btn:hover {
        background-color: #e6e9ef;
    }
    .voice-btn.recording {
        background-color: #ff4b4b;
        animation: pulse 1.5s infinite;
    }
    @keyframes pulse {
        0% { box-shadow: 0 0 0 0 rgba(255, 75, 75, 0.7); }
        70% { box-shadow: 0 0 0 10px rgba(255, 75, 75, 0); }
        100% { box-shadow: 0 0 0 0 rgba(255, 75, 75, 0); }
    }
    .voice-controls {
        display: flex;
        align-items: center;
        margin: 10px 0;
    }
    .voice-status {
        margin-left: 10px;
        font-size: 14px;
        color: #666;
    }
</style>
""", unsafe_allow_html=True)

# === VOICE FUNCTIONALITY ===
# Initialize speech recognition
recognizer = sr.Recognizer()

# Initialize text-to-speech engines
def init_pyttsx3():
    engine = pyttsx3.init()
    return engine

# Queue for handling TTS in background
tts_queue = queue.Queue()
tts_active = threading.Event()
tts_active.set()

# Initialize TTS engine in a separate thread to avoid UI blocking
tts_engine = None
def initialize_tts_engine():
    global tts_engine
    tts_engine = init_pyttsx3()

# Start TTS engine initialization in background
tts_thread = threading.Thread(target=initialize_tts_engine)
tts_thread.daemon = True
tts_thread.start()

# Function to process TTS queue
def tts_worker():
    while tts_active.is_set():
        try:
            text = tts_queue.get(timeout=0.5)
            if text:
                # Use gTTS for better quality voice
                with tempfile.NamedTemporaryFile(delete=True, suffix='.mp3') as fp:
                    tts = gTTS(text=text, lang='en')
                    tts.save(fp.name)
                    st.audio(fp.name, format='audio/mp3')
            tts_queue.task_done()
        except queue.Empty:
            pass
        except Exception as e:
            st.error(f"TTS Error: {e}")

# Start TTS worker thread
tts_worker_thread = threading.Thread(target=tts_worker)
tts_worker_thread.daemon = True
tts_worker_thread.start()

# Function to capture voice input
def voice_to_text():
    with sr.Microphone() as source:
        st.session_state.voice_status = "Listening..."
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        try:
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
            st.session_state.voice_status = "Processing..."
            text = recognizer.recognize_google(audio)
            st.session_state.voice_status = "Done"
            return text
        except sr.WaitTimeoutError:
            st.session_state.voice_status = "No speech detected"
            return ""
        except sr.UnknownValueError:
            st.session_state.voice_status = "Could not understand audio"
            return ""
        except sr.RequestError as e:
            st.session_state.voice_status = f"Error: {e}"
            return ""
        except Exception as e:
            st.session_state.voice_status = f"Error: {e}"
            return ""

# Function to speak text
def text_to_speech(text):
    if not text:
        return
    tts_queue.put(text)

# Initialize voice status in session state
if "voice_status" not in st.session_state:
    st.session_state.voice_status = "Ready"

# Voice input button component
def voice_input_button(key, target_input_key=None, callback=None):
    col1, col2 = st.columns([1, 10])
    with col1:
        st.markdown(f"""
        <div class="voice-btn" id="{key}-btn" onclick="
            if (document.getElementById('{key}-btn').classList.contains('recording')) {{
                document.getElementById('{key}-btn').classList.remove('recording');
                document.getElementById('{key}-status').innerText = 'Stopped';
            }} else {{
                document.getElementById('{key}-btn').classList.add('recording');
                document.getElementById('{key}-status').innerText = 'Recording...';
            }}
        ">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
                <path d="M8 1a2 2 0 0 1 2 2v4a2 2 0 1 1-4 0V3a2 2 0 0 1 2-2zm0 9.5a3 3 0 0 0 3-3V5.5a3 3 0 1 0-6 0V6.5a3 3 0 0 0 3 3z"/>
                <path d="M14 1a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H2a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1h12zM2 0a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V2a2 2 0 0 0-2-2H2z"/>
            </svg>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="voice-status" id="{key}-status">Click to record</div>', unsafe_allow_html=True)
    
    if st.button("🎤 Record", key=f"voice_btn_{key}"):
        text = voice_to_text()
        if text and target_input_key:
            st.session_state[target_input_key] = text
        if callback and text:
            callback(text)
        return text
    return None

# Voice output button component
def voice_output_button(text, key):
    if st.button("🔊 Listen", key=f"voice_out_{key}"):
        text_to_speech(text)

# === APP TABS ===
tab1, tab2, tab3 = st.tabs(["📓 Journal", "📂 View Entries", "💬 Chat"])

# === JOURNAL TAB ===
with tab1:
    st.title("🧠 Reflective Journal")
    st.markdown("##### Your personal space for reflection and growth")
    
    # Habit tracking section
    with st.expander("🔥 Habit Tracking", expanded=True):
        st.markdown("##### Your Journaling Streaks")
        
        try:
            import sqlite3
            db_path = os.path.join(os.path.dirname(__file__), "journal_entries.db")
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Get current streak
            cursor.execute("""
            WITH dates AS (
                SELECT date(timestamp) as entry_date
                FROM journal_entries
                ORDER BY timestamp DESC
            ),
            grouped AS (
                SELECT 
                    entry_date,
                    julianday(entry_date) - julianday(LAG(entry_date) OVER (ORDER BY entry_date DESC)) as day_diff
                FROM dates
            ),
            streaks AS (
                SELECT 
                    entry_date,
                    SUM(CASE WHEN day_diff = 1 THEN 0 ELSE 1 END) OVER (ORDER BY entry_date DESC) as streak_group
                FROM grouped
            )
            SELECT COUNT(*) as current_streak
            FROM streaks
            WHERE streak_group = 0
            """)
            current_streak = cursor.fetchone()[0] or 0
            
            # Get longest streak
            cursor.execute("""
            WITH dates AS (
                SELECT date(timestamp) as entry_date
                FROM journal_entries
                ORDER BY timestamp DESC
            ),
            grouped AS (
                SELECT 
                    entry_date,
                    julianday(entry_date) - julianday(LAG(entry_date) OVER (ORDER BY entry_date DESC)) as day_diff
                FROM dates
            ),
            streaks AS (
                SELECT 
                    entry_date,
                    SUM(CASE WHEN day_diff = 1 THEN 0 ELSE 1 END) OVER (ORDER BY entry_date DESC) as streak_group
                FROM grouped
            )
            SELECT streak_group, COUNT(*) as streak_length
            FROM streaks
            GROUP BY streak_group
            ORDER BY streak_length DESC
            LIMIT 1
            """)
            longest_streak = cursor.fetchone()
            longest_streak_length = longest_streak[1] if longest_streak else 0
            
            # Display streak info
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Current Streak", f"{current_streak} days", 
                         help="Number of consecutive days you've journaled")
            with col2:
                st.metric("Longest Streak", f"{longest_streak_length} days", 
                         help="Your longest journaling streak")
            
            # Weekly consistency
            cursor.execute("""
            SELECT 
                strftime('%w', date(timestamp)) as weekday,
                COUNT(*) as count
            FROM journal_entries
            GROUP BY weekday
            ORDER BY weekday
            """)
            weekly_counts = cursor.fetchall()
            
            if weekly_counts:
                days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
                counts = [0]*7
                for day_num, count in weekly_counts:
                    counts[int(day_num)] = count
                
                fig = px.bar(x=days, y=counts, 
                            labels={"x": "Day of Week", "y": "Entries"},
                            title="Weekly Journaling Consistency")
                st.plotly_chart(fig, use_container_width=True)
            
        except Exception as e:
            st.error(f"Error loading habit data: {e}")
        finally:
            if 'conn' in locals():
                conn.close()
       # Create a card-like container for the form
    with st.container():
        st.markdown("---")
        # === JOURNAL FORM ===
        with st.form("journal_form"):
            st.subheader("New Entry")
            
            # Add voice input for journal entry
            if "journal_entry" not in st.session_state:
                st.session_state.journal_entry = ""
            
            # Voice input for journal entry
            st.markdown("##### Voice Input")
            st.markdown("Record your thoughts instead of typing")
            voice_col1, voice_col2 = st.columns([1, 1])
            with voice_col1:
                if st.form_submit_button("🎤 Record Journal Entry"):
                    st.info("Please click the Record button outside the form after submitting")
                    st.session_state.show_voice_journal = True
            with voice_col2:
                if st.form_submit_button("🔊 Listen to Entry"):
                    if st.session_state.journal_entry:
                        text_to_speech(st.session_state.journal_entry)
            
            # Mobile-friendly text area with smaller height
            entry = st.text_area("What's on your mind today?", 
                               value=st.session_state.journal_entry,
                               height=150, 
                               placeholder="Write freely about your thoughts, experiences, or challenges...",
                               key="journal_text_area")
            
            # Use columns for form elements to save vertical space
            col1, col2 = st.columns([1, 1])
            with col1:
                mood = st.selectbox("How do you feel?", 
                                   ["😄 Great", "🙂 Okay", "😐 Neutral", "😔 Low", "😣 Anxious",
                                    "😊 Happy", "😌 Relaxed", "😟 Worried", "😠 Angry", "😴 Tired"])
            with col2:
                tags = st.text_input("Tags (comma separated)", 
                                    placeholder="study, focus, progress...")
                
            # Full-width button with better styling
            submitted = st.form_submit_button("✨ Reflect and Save", 
                                             use_container_width=True, 
                                             type="primary")
            
            if submitted:
                try:
                    import sqlite3
                    # Initialize database connection
                    db_path = os.path.join(os.path.dirname(__file__), "journal_entries.db")
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    
                    # Create table if it doesn't exist
                    cursor.execute("""
                    CREATE TABLE IF NOT EXISTS journal_entries (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        entry TEXT NOT NULL,
                        mood TEXT NOT NULL,
                        tags TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                    """)
                    
                    # Insert new entry
                    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    cursor.execute(
                        "INSERT INTO journal_entries (timestamp, entry, mood, tags) VALUES (?, ?, ?, ?)",
                        (timestamp, entry, mood, tags)
                    )
                    conn.commit()
                    
                    st.success("Journal entry saved to database!")
                    st.session_state.journal_entry = ""  # Clear the entry
                except Exception as e:
                    st.error(f"Error saving journal entry: {e}")
                finally:
                    if 'conn' in locals():
                        conn.close()
        
        # Voice recording outside the form
        if st.session_state.get("show_voice_journal", False):
            st.markdown("##### Record Your Journal Entry")
            st.markdown("Speak clearly into your microphone")
            
            def update_journal_entry(text):
                st.session_state.journal_entry = text
                st.session_state.journal_text_area = text
                st.rerun()
            
            voice_text = voice_input_button("journal_voice", callback=update_journal_entry)
            if voice_text:
                st.success(f"Recorded: {voice_text}")
                st.session_state.journal_entry = voice_text

# === VIEW ENTRIES TAB ===
with tab2:
    st.title("📊 Dashboard & Journal Entries")
    st.markdown("Visualize your mood trends and browse past entries")
    
    # AI Insights section
    st.markdown("### 🤖 AI-Powered Insights")
    st.markdown("##### Journal Entry Analysis")
    
    if st.button("🔍 Analyze My Entries"):
        with st.spinner("Analyzing your journal entries..."):
            try:
                import sqlite3
                db_path = os.path.join(os.path.dirname(__file__), "journal_entries.db")
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                # Get all entries
                cursor.execute("SELECT entry, mood, tags FROM journal_entries ORDER BY timestamp DESC")
                entries = cursor.fetchall()
                
                if entries:
                    # Prepare data for analysis
                    all_text = " ".join([entry[0] for entry in entries])
                    moods = [entry[1] for entry in entries]
                    tags = [entry[2] for entry in entries if entry[2]]
                    
                    # Generate insights with Gemini
                    prompt = f"""Analyze these journal entries and provide insights:
                    
                    Journal Entries: {all_text[:10000]}
                    
                    Please provide:
                    1. Key themes and patterns
                    2. Emotional trends based on moods: {', '.join(set(moods))}
                    3. Suggestions for improvement or areas to focus on
                    4. Any notable changes over time
                    
                    Format as a clear, bullet-point summary."""
                    
                    response = model.generate_content(prompt)
                    with st.container():
                        st.markdown(response.text)
                    
                    # Additional analysis for common tags
                    if tags:
                        prompt = f"""Analyze these journal tags and suggest habits:
                        
                        Tags: {', '.join(tags)}
                        
                        Suggest 3 habits that could help based on these tags."""
                        response = model.generate_content(prompt)
                        st.markdown("### Suggested Habits")
                        st.markdown(response.text)
                else:
                    st.info("No entries found to analyze.")
            except Exception as e:
                st.error(f"Error analyzing entries: {e}")
            finally:
                if 'conn' in locals():
                    conn.close()
    
    try:
        import sqlite3
        import plotly.express as px
        import pandas as pd
        import plotly.express as px
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
        db_path = os.path.join(os.path.dirname(__file__), "journal_entries.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Add filters
        col1, col2 = st.columns([1, 1])
        with col1:
            date_filter = st.date_input("Filter by date")
        with col2:
            mood_filter = st.selectbox("Filter by mood", 
                                     ["All", "😄 Great", "🙂 Okay", "😐 Neutral", "😔 Low", "😣 Anxious"])
        
        # Build query
        query = "SELECT timestamp, entry, mood, tags FROM journal_entries WHERE 1=1"
        params = []
        
        if date_filter:
            query += " AND date(timestamp) = date(?)"
            params.append(date_filter.strftime('%Y-%m-%d'))
        if mood_filter != "All":
            query += " AND mood = ?"
            params.append(mood_filter)
        
        query += " ORDER BY timestamp DESC"
        
        # Execute query
        cursor.execute(query, params)
        entries = cursor.fetchall()
        
        if entries:
            # Prepare data for visualizations
            df = pd.DataFrame(entries, columns=["timestamp", "entry", "mood", "tags"])
            df["date"] = pd.to_datetime(df["timestamp"]).dt.date
            df["count"] = 1
            df["weekday"] = pd.to_datetime(df["date"]).dt.day_name()
            df["hour"] = pd.to_datetime(df["timestamp"]).dt.hour
            
            # Mood distribution pie chart
            with st.expander("📈 Mood Distribution", expanded=True):
                mood_counts = df["mood"].value_counts().reset_index()
                mood_counts.columns = ["mood", "count"]
                
                fig = px.pie(mood_counts, values="count", names="mood", 
                            color="mood",
                            color_discrete_map={
                                "😄 Great": "#4CAF50",
                                "🙂 Okay": "#8BC34A",
                                "😐 Neutral": "#FFC107",
                                "😔 Low": "#FF9800",
                                "😣 Anxious": "#F44336"
                            },
                            title="Mood Distribution")
                st.plotly_chart(fig, use_container_width=True)
                
                # Weekly patterns
                weekly_patterns = df.groupby(["weekday", "mood"])["count"].sum().unstack().fillna(0)
                weekly_patterns = weekly_patterns.reindex(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])
                
                fig = px.bar(weekly_patterns, 
                            title="Weekly Mood Patterns",
                            labels={"value": "Entries", "weekday": "Day of Week"},
                            color_discrete_map={
                                "😄 Great": "#4CAF50",
                                "🙂 Okay": "#8BC34A",
                                "😐 Neutral": "#FFC107",
                                "😔 Low": "#FF9800",
                                "😣 Anxious": "#F44336"
                            })
                st.plotly_chart(fig, use_container_width=True)
                
                # Time of day patterns
                hourly_patterns = df.groupby(["hour", "mood"])["count"].sum().unstack().fillna(0)
                fig = px.bar(hourly_patterns, 
                            title="Time of Day Patterns",
                            labels={"value": "Entries", "hour": "Hour of Day"},
                            color_discrete_map={
                                "😄 Great": "#4CAF50",
                                "🙂 Okay": "#8BC34A",
                                "😐 Neutral": "#FFC107",
                                "😔 Low": "#FF9800",
                                "😣 Anxious": "#F44336"
                            })
                st.plotly_chart(fig, use_container_width=True)
            
            # Individual entries display
            with st.expander("📂 View Individual Entries", expanded=True):
                for entry in entries:
                    with st.expander(f"{entry[0]} - {entry[2]}"):
                        st.markdown(f"**Mood:** {entry[2]}")
                        if entry[3]:
                            st.markdown(f"**Tags:** {entry[3]}")
                        st.markdown(f"**Entry:**\n{entry[1]}")
        else:
            st.info("No entries found matching your filters.")
        
    except Exception as e:
        st.error(f"Error loading journal entries: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

# === CHAT TAB ===
with tab3:
    st.title("💬 Chat with Gemini")
    st.markdown("Search across all tabs using the search box below")
    
    # Cross-tab search functionality
    search_query = st.text_input("🔍 Search across all tabs", "", 
                                placeholder="Search journal entries, chats, etc.")
    
    if search_query:
        with st.expander("🔍 Search Results", expanded=True):
            try:
                import sqlite3
                db_path = os.path.join(os.path.dirname(__file__), "journal_entries.db")
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                # Search journal entries
                cursor.execute("""
                SELECT timestamp, entry, mood 
                FROM journal_entries 
                WHERE entry LIKE ? 
                ORDER BY timestamp DESC
                LIMIT 5
                """, (f"%{search_query}%",))
                journal_results = cursor.fetchall()
                
                if journal_results:
                    st.markdown("### Journal Entries")
                    for result in journal_results:
                        with st.expander(f"{result[0]} - {result[2]}"):
                            st.markdown(result[1])
                else:
                    st.info("No matching journal entries found.")
                
                # Search chat history
                if "messages" in st.session_state and st.session_state.messages:
                    chat_results = [msg for msg in st.session_state.messages 
                                   if search_query.lower() in msg["content"].lower()]
                    
                    if chat_results:
                        st.markdown("### Chat History")
                        for msg in chat_results[:5]:  # Limit to 5 results
                            with st.chat_message(msg["role"]):
                                st.markdown(msg["content"])
                    else:
                        st.info("No matching chat messages found.")
                
            except Exception as e:
                st.error(f"Search error: {e}")
            finally:
                if 'conn' in locals():
                    conn.close()
    st.markdown("##### Interactive AI assistant for personalized guidance")
    
    # Initialize chat history and voice mode
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    if "voice_mode" not in st.session_state:
        st.session_state.voice_mode = False
    
    # Voice mode toggle
    voice_mode = st.checkbox("🎤 Enable Voice Mode", value=st.session_state.voice_mode)
    if voice_mode != st.session_state.voice_mode:
        st.session_state.voice_mode = voice_mode
        st.rerun()
    
    if st.session_state.voice_mode:
        st.info("Voice mode enabled. Your messages will be read aloud, and you can speak to the assistant.")
    
    # Initialize voice input for chat
    if "voice_input" not in st.session_state:
        st.session_state.voice_input = ""
    
    # Move templates to an expander with better styling
    with st.expander("📋 Quick Start Templates", expanded=False):
        st.markdown("Select a template to quickly start a conversation on a specific topic:")
        
        # Create a more visual template selector with columns
        templates = {
            "Study Plan": "Help me create a study plan for CA Finals. I need to cover these topics: ",
            "Focus Techniques": "What are some techniques to improve focus and concentration?",
            "Motivation and Inspiration": "What are some motivational quotes and phrases I can use?",
            "Productivity Tips": "What are some productivity tips for staying organized and efficient?",
            "Time Management": "How can I manage my time more effectively?",
            "Health and Wellness": "What are some tips for maintaining a healthy lifestyle?",
            "Relationships": "How can I improve my relationships with friends and family?",
            "Financial Planning": "What are some financial planning strategies I can use?",
            "Travel Tips": "What are some tips for traveling safely and efficiently?",
            "Hobbies and Interests": "What are some hobbies and interests I can explore?",
            "Career and Professional Development": "What are some career and professional development strategies I can use?",
            "Personal Branding": "How can I create a personal brand that reflects my values and personality?",
            "Daily Reflection": "Help me reflect on my day. I want to analyze what went well and what I could improve.",
            "Motivation Boost": "I'm feeling unmotivated today. Can you help me get back on track?"
        }
        
        # Create a 2-column layout for template buttons
        template_cols = st.columns(2)
        
        # Add template buttons in a grid
        for i, (template_name, template_text) in enumerate(templates.items()):
            with template_cols[i % 2]:
                if st.button(f"📝 {template_name}", key=f"template_{i}", use_container_width=True):
                    # Use the template
                    st.session_state.messages.append({"role": "user", "content": template_text})
                    with st.chat_message("user"):
                        st.markdown(template_text)
                    
                    # Process template with Gemini
                    with st.chat_message("assistant"):
                        with st.spinner("Thinking..."):
                            try:
                                chat = model.start_chat(history=[
                                    {"role": m["role"], "parts": [m["content"]]} 
                                    for m in st.session_state.messages[:-1]
                                ])
                                
                                response = chat.send_message(template_text)
                                st.markdown(response.text)
                                
                                # Add assistant response to chat history
                                st.session_state.messages.append({"role": "assistant", "content": response.text})
                            except Exception as e:
                                error_msg = f"I'm sorry, I encountered an error: {e}"
                                st.error(error_msg)
                                st.session_state.messages.append({"role": "assistant", "content": error_msg})
                    
                    st.rerun()
    
    # Add a visual separator
    st.markdown("---")
    
    # Display chat history with better styling
    st.markdown("##### Conversation")
    chat_container = st.container()
    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"], avatar="🧑‍💻" if message["role"] == "user" else "🤖"):
                st.markdown(message["content"])
    
    # Mobile-friendly button layout with better styling
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("💾 Save Chat", use_container_width=True):
            try:
                # Create chats directory if it doesn't exist
                chat_dir = os.path.join(os.path.dirname(__file__), "chats")
                os.makedirs(chat_dir, exist_ok=True)
                
                # Create filename with timestamp
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                filename = f"chat_{timestamp}.md"
                filepath = os.path.join(chat_dir, filename)
                
                # Format content
                content = f"# Chat Session - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                
                for msg in st.session_state.messages:
                    role = "User" if msg["role"] == "user" else "Gemini"
                    content += f"## {role}\n{msg['content']}\n\n"
                
                # Write to file
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)
                
                st.success(f"Chat saved to: {filepath}")
            except Exception as e:
                st.error(f"Error saving chat: {e}")
    
    # Voice input for chat
    if st.session_state.voice_mode:
        st.markdown("##### Voice Input")
        st.markdown("Speak to the assistant")
        
        def process_voice_input(text):
            st.session_state.voice_input = text
            st.rerun()
        
        voice_text = voice_input_button("chat_voice", callback=process_voice_input)
        if voice_text:
            st.success(f"Recorded: {voice_text}")
            st.session_state.voice_input = voice_text
    
    # Process voice input if available
    if st.session_state.voice_input:
        prompt = st.session_state.voice_input
        st.session_state.voice_input = ""  # Clear for next use
    else:
        # Regular chat input
        prompt = st.chat_input("Ask me anything...", key="chat_input")
    
    if prompt:
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Display assistant response with streaming
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""
            
            try:
                # Create a streaming response
                chat = model.start_chat(history=[
                    {"role": m["role"], "parts": [m["content"]]} 
                    for m in st.session_state.messages[:-1]  # Exclude the latest user message
                ])
                
                response = chat.send_message(
                    prompt,
                    stream=True
                )
                
                # Simulate streaming by incrementally revealing the response
                for chunk in response:
                    if hasattr(chunk, 'text'):
                        text_chunk = chunk.text
                        full_response += text_chunk
                        message_placeholder.markdown(full_response + "▌")
                        time.sleep(0.01)  # Small delay to simulate typing
                
                # Display the final response
                message_placeholder.markdown(full_response)
                
                # Add assistant response to chat history
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                
                # Read response aloud if voice mode is enabled
                if st.session_state.voice_mode:
                    text_to_speech(full_response)
                
            except Exception as e:
                st.error(f"Error generating response: {e}")
                st.session_state.messages.append({"role": "assistant", "content": f"I'm sorry, I encountered an error: {e}"})
    
    # Voice controls for past messages
    if st.session_state.voice_mode and st.session_state.messages:
        st.markdown("---")
        st.markdown("##### Voice Playback")
        st.markdown("Listen to previous messages")
        
        # Create a dropdown to select which message to play
        message_options = [f"{i+1}. {m['role'].capitalize()}: {m['content'][:50]}..." 
                          for i, m in enumerate(st.session_state.messages)]
        
        selected_message = st.selectbox("Select a message to play", 
                                      options=message_options,
                                      index=len(message_options)-1 if message_options else 0)
        
        if selected_message:
            selected_index = message_options.index(selected_message)
            message_content = st.session_state.messages[selected_index]['content']
            
            if st.button("🔊 Play Selected Message"):
                text_to_speech(message_content)
    
    # Add a button to clear chat history
    if st.button("Clear Chat History"):
        st.session_state.messages = []
        st.rerun()
