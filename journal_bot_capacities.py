import streamlit as st
import datetime
import os
import google.generativeai as genai
import requests
import time
from ics import Calendar, Event  # You'll need to install this: pip install ics

# === USER CONFIG ===
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]  # Store this in .streamlit/secrets.toml
CAPACITIES_SPACE_ID = "b50fd297-0053-4975-bd95-805920f11d1d"
JOURNAL_OBJECT_TYPE_ID = "e0d4f9f7-87f1-4cef-98d1-fcb1308b8458"

# === INIT GEMINI ===
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-pro-preview-03-25")

st.set_page_config(page_title="Nysh GPT", page_icon="📱", layout="wide", initial_sidebar_state="collapsed")

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
</style>
""", unsafe_allow_html=True)

# === APP TABS ===
tab1, tab2, tab3 = st.tabs(["📓 Journal", "💬 Chat", "⏰ Reminders"])

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
            # Mobile-friendly text area with smaller height
            entry = st.text_area("What's on your mind today?", height=150, 
                                placeholder="Write freely about your thoughts, experiences, or challenges...")
            
            # Use columns for form elements to save vertical space
            col1, col2 = st.columns([1, 1])
            with col1:
                mood = st.selectbox("How do you feel?", 
                                   ["😄 Great", "🙂 Okay", "😐 Neutral", "😔 Low", "😣 Anxious"])
            with col2:
                tags = st.text_input("Tags (comma separated)", 
                                    placeholder="study, focus, progress...")
                
            # Full-width button with better styling
            submitted = st.form_submit_button("✨ Reflect and Save", 
                                             use_container_width=True, 
                                             type="primary")

# === CHAT TAB ===
with tab2:
    st.title("💬 Chat with Gemini")
    st.markdown("##### Interactive AI assistant for personalized guidance")
    
    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
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
    
    # Chat input
    if prompt := st.chat_input("Ask me anything...", key="chat_input"):
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
                
            except Exception as e:
                st.error(f"Error generating response: {e}")
                st.session_state.messages.append({"role": "assistant", "content": f"I'm sorry, I encountered an error: {e}"})
    
    # Add a button to clear chat history
    if st.button("Clear Chat History"):
        st.session_state.messages = []
        st.rerun()

# === REMINDERS TAB ===
with tab3:
    st.title("⏰ Journal Reminders")
    st.markdown("##### Schedule regular journaling sessions")
    
    # Create a card-like container
    with st.container():
        st.markdown("---")
        st.subheader("Create New Reminder")
        
        # Reminder form with mobile-friendly layout
        with st.form("reminder_form"):
            reminder_name = st.text_input("Reminder Name", "Journal Writing Time")
            
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
                                         "Time to reflect on your day and write in your journal.", 
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
