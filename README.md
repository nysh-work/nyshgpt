# Nysh GPT - Personal AI Assistant

![Nysh GPT](https://img.shields.io/badge/Nysh-GPT-805AD5?style=for-the-badge)
![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)
![Gemini](https://img.shields.io/badge/Gemini-AI-blue?style=for-the-badge)

A personal AI assistant built with Streamlit and Google's Gemini AI that helps you journal, chat, and manage reminders.

## 🌟 Features

### 📓 Reflective Journal
- Create and save journal entries with mood tracking
- Tag entries for better organization
- AI-powered reflection on your thoughts

### 💬 Chat with Gemini
- Interactive conversations with Google's Gemini AI
- Quick-start templates for common topics
- Save and export chat history
- Streaming responses for a natural conversation feel

### ⏰ Journal Reminders
- Schedule regular journaling sessions
- Create calendar events with customizable frequency
- Get tips for consistent journaling habits

## 🚀 Potential Enhancements

### 📊 Data Visualization
- Mood tracking visualization to identify patterns over time
- Journal activity calendar view
- Progress tracking for personal goals

### 🎤 Voice Capabilities
- Voice-to-text for hands-free journaling
- Text-to-speech for listening to past entries
- Voice commands for navigating the application

### 🔄 Integration Options
- Calendar app synchronization (Google Calendar, Outlook)
- Cloud storage for journal backup (Google Drive, Dropbox)
- Task management integration (Todoist, Trello)

### 🧠 Personal Knowledge Base
- AI-powered insights from journal entries
- Topic extraction and categorization
- Personalized recommendations based on journal content

### 📤 Export & Sharing
- Multiple export formats (PDF, DOCX, HTML)
- Selective sharing of journal insights
- Email digests of journal highlights

## 📋 Requirements

- Python 3.7+
- Streamlit
- Google Generative AI library
- Requests
- ICS (for calendar functionality)

## 🚀 Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/nyshgpt.git
   cd nyshgpt
   ```

2. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up your API keys:
   - Create a `.streamlit/secrets.toml` file with your Gemini API key:
     ```toml
     GEMINI_API_KEY = "your-api-key-here"
     ```

## 🔧 Configuration

The application uses the following configuration variables:

- `GEMINI_API_KEY`: Your Google Gemini API key (stored in secrets.toml)
- `CAPACITIES_SPACE_ID`: ID for the Capacities space (if using that service)
- `JOURNAL_OBJECT_TYPE_ID`: ID for journal object type

## 🖥️ Usage

Run the Streamlit app:

```bash
streamlit run personal_assisstant.py
```

The application will open in your default web browser with three main tabs:

1. **Journal**: Write and save your thoughts with mood tracking
2. **Chat**: Interact with Gemini AI for guidance and assistance
3. **Reminders**: Set up regular journaling reminders

## 📱 Mobile-Friendly

The app is designed with a responsive interface that works well on both desktop and mobile devices.

## 📂 File Structure

```
nyshgpt/
├── personal_assisstant.py  # Main application file
├── requirements.txt        # Python dependencies
├── .streamlit/            # Streamlit configuration
│   └── secrets.toml       # API keys and secrets (create this file)
└── journal/               # Directory for saved journal entries
```

## 🔒 Privacy

All journal entries are saved locally. Chat conversations with Gemini AI are processed through Google's API.

## 📄 License

[MIT License](LICENSE)

---

Built with ❤️ using Streamlit and Google Gemini AI