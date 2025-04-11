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

# === USER CONFIG ===
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]  # Store this in .streamlit/secrets.toml
CAPACITIES_SPACE_ID = "b50fd297-0053-4975-bd95-805920f11d1d"
JOURNAL_OBJECT_TYPE_ID = "e0d4f9f7-87f1-4cef-98d1-fcb1308b8458"

# === INIT GEMINI ===
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-pro-preview-03-25")

st.set_page_config(page_title="Nysh GPT", page_icon="📱", layout="centered", initial_sidebar_state="collapsed")

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
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        border-radius: 4px;
        font-weight: 500;
    }
    .stTabs [aria-selected="true"] {
        background-color: rgba(128, 90, 213, 0.1);
        border-bottom-color: rgb(128, 90, 213);
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
tab1, tab2, tab3, tab4 = st.tabs(["📓 Journal", "📂 View Entries","💬 Chat", "⏰ Reminders", ])

# === JOURNAL TAB ===
with tab1:
    st.title("🧠 Reflective Journal")
    st.markdown("##### Your personal space for reflection and growth")
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
    st.title("📂 Saved Journal Entries")
    st.markdown("Browse and filter your past journal entries")
    
    try:
        import sqlite3
        import plotly.express as px
        import pandas as pd
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
            # Gantt chart visualization
            with st.expander("📊 Timeline View", expanded=True):
                # Prepare data for visualization
                df = pd.DataFrame(entries, columns=["timestamp", "entry", "mood", "tags"])
                df["date"] = pd.to_datetime(df["timestamp"]).dt.date
                df["count"] = 1
                
                # Group by date and mood
                grouped = df.groupby(["date", "mood"])["count"].sum().reset_index()
                
                # Create Gantt-like timeline
                fig = px.timeline(
                    grouped, 
                    x_start="date", 
                    x_end="date", 
                    y="mood",
                    color="mood",
                    color_discrete_map={
                        "😄 Great": "#4CAF50",
                        "🙂 Okay": "#8BC34A",
                        "😐 Neutral": "#FFC107",
                        "😔 Low": "#FF9800",
                        "😣 Anxious": "#F44336"
                    },
                    title="Journal Entries Timeline",
                    labels={"mood": "Mood", "date": "Date"},
                    height=400
                )
                fig.update_layout(showlegend=False)
                fig.update_traces(width=0.5)
                st.plotly_chart(fig, use_container_width=True)
                
                # Show daily entry count
                daily_count = df.groupby("date")["count"].sum().reset_index()
                st.markdown("**Daily Entry Count**")
                st.dataframe(daily_count, hide_index=True, use_container_width=True)
            
            # Individual entries display
            st.markdown("**Individual Entries**")
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
            "Addiction Recovery": "Can you suggest some strategies for overcoming addiction habits?",
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

# === REMINDERS TAB ===
with tab4:
    st.title("⏰ Journal Reminders")
    st.markdown("##### Schedule regular journaling sessions")
    
    # Create a card-like container
    with st.container():
        st.markdown("---")
        st.subheader("Create New Reminder")
        
        # Initialize voice input for reminders
        if "reminder_name_voice" not in st.session_state:
            st.session_state.reminder_name_voice = "Journal Writing Time"
        
        if "reminder_notes_voice" not in st.session_state:
            st.session_state.reminder_notes_voice = "Time to reflect on your day and write in your journal."
        
        # Voice input for reminder details
        st.markdown("##### Voice Input")
        st.markdown("Use voice to set reminder details")
        
        voice_tabs = st.tabs(["🏷️ Name", "📝 Notes"])
        
        with voice_tabs[0]:
            st.markdown("Record reminder name")
            
            def update_reminder_name(text):
                st.session_state.reminder_name_voice = text
                st.rerun()
            
            voice_input_button("reminder_name", callback=update_reminder_name)
            
            if st.button("🔊 Listen to Name"):
                text_to_speech(st.session_state.reminder_name_voice)
        
        with voice_tabs[1]:
            st.markdown("Record reminder notes")
            
            def update_reminder_notes(text):
                st.session_state.reminder_notes_voice = text
                st.rerun()
            
            voice_input_button("reminder_notes", callback=update_reminder_notes)
            
            if st.button("🔊 Listen to Notes"):
                text_to_speech(st.session_state.reminder_notes_voice)
        
        # Reminder form with mobile-friendly layout
        with st.form("reminder_form"):
            reminder_name = st.text_input("Reminder Name", value=st.session_state.reminder_name_voice)
            
            # Use columns for date and time to save space
            col1, col2 = st.columns([1, 1])
            with col1:
                reminder_date = st.date_input("Start Date", datetime.date.today())
            with col2:
                reminder_time = st.time_input("Time", datetime.time(20, 0))
            
            # Add visual indicators for frequency selection
            st.markdown("##### Frequency")
            freq_col1, freq_col2, freq_col3 = st.columns([1, 1, 1])
            with freq_col1:
                daily = st.checkbox("Daily")
            with freq_col2:
                weekly = st.checkbox("Weekly")
            with freq_col3:
                monthly = st.checkbox("Monthly")
            
            # Determine frequency based on checkboxes
            frequency = "Daily" if daily else "Weekly" if weekly else "Monthly" if monthly else "Once"
            
            reminder_notes = st.text_area("Notes (optional)", 
                                         value=st.session_state.reminder_notes_voice, 
                                         height=100)
            
            # Full-width button with better styling
            create_reminder = st.form_submit_button("📅 Create Calendar Event", 
                                                  use_container_width=True,
                                                  type="primary")
    
    # Add a visual separator
    st.markdown("---")
    
    # Put tips in a visually appealing container
    with st.container():
        st.subheader("📝 Tips for Consistent Journaling")
        
        # Create a more visual tips section with columns and icons
        tip_col1, tip_col2 = st.columns(2)
        
        with tip_col1:
            st.markdown("##### ⏰ Set a specific time")
            st.markdown("Try to journal at the same time each day to build a habit")
            
            st.markdown("##### 📱 Keep it accessible")
            st.markdown("Have your journal ready where you'll use it")
            
        with tip_col2:
            st.markdown("##### 🌱 Start small")
            st.markdown("Even 5 minutes of journaling is better than none")
            
            st.markdown("##### 🧘 Don't seek perfection")
            st.markdown("Just write what comes to mind")
