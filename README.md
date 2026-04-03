# 🚀 AI Study Planner

An intelligent full-stack web application that generates **personalized AI-powered study plans** based on user input like subjects, topics, duration, and daily study hours.

---

## ✨ Features

* 🧠 **AI-Powered Study Plans** – Generate structured, day-wise learning schedules
* 🎯 **Topic-Based Planning** – Covers multiple subjects and topics intelligently
* 📊 **Smart Task Breakdown** – Daily learning, practice, and revision tasks
* 🎥 **YouTube Learning Integration** – Curated learning resources
* 📚 **Multi-Subject Support** – Works for school and college-level topics
* 🌙 **Modern UI** – Clean dark-themed responsive interface
* 📄 **Export Options** – Copy, download PDF, or share via WhatsApp/email
* ⚡ **Fast & Scalable Backend** – Built with Flask

---

## 🧠 Powered By

This project is developed using:

* **OpenCode AI (Open Source AI Development Tool)**
  → Used for prompt engineering and backend logic

* **Ollama (Local AI Models)**
  → Running models like `llama3.2` locally

---

## 🛠️ Tech Stack

* **Backend:** Python (Flask)
* **Frontend:** HTML, CSS, JavaScript
* **AI Model:** LLaMA 3.2 (via Ollama)
* **YouTube API:** Google Data API v3
* **PDF Generation:** ReportLab

---

## 📂 Project Structure

```
AI Study Planner/
│
├── app.py
├── setup_api.py
├── requirements.txt
├── README.md
│
├── templates/
│   └── index.html
│
├── static/
│   ├── style.css
│   └── script.js
│
├── .env              (ignored)
├── .gitignore
├── server.log        (ignored)
├── __pycache__/      (ignored)
```

---

## ⚙️ Getting Started

### 🔹 Prerequisites

* Python 3.8+
* pip
* Ollama installed

---

### 🔹 Install Ollama (IMPORTANT)

1. Download from:
   👉 https://ollama.com/

2. Start Ollama:

```bash
ollama serve
```

3. Pull model:

```bash
ollama pull llama3.2
```

---

### 🔹 Installation

```bash
git clone https://github.com/rishabh192000/AI-Study-Planner.git
cd AI-Study-Planner
```

---

### 🔹 Create Virtual Environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

---

### 🔹 Install Dependencies

```bash
pip install -r requirements.txt
```

---

### 🔹 Setup Environment Variables

Create `.env` file:

```
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
YOUTUBE_API_KEY=your_youtube_api_key
```

---

### 🔹 Run the Application

```bash
python app.py
```

Open:

```
http://localhost:5000
```

---

## 🎯 How It Works

1. User enters subjects & topics
2. AI processes input using local LLM (Ollama)
3. Generates structured day-wise study plan
4. Fetches relevant YouTube resources
5. Displays actionable tasks

---

## 🧪 Example Input

```
Name: John Doe
Subjects:
  Mathematics: Calculus, Algebra
  Computer Science: SQL, Programming
Duration: 7 days
Daily Hours: 5 hours
```

---

## ⚠️ Important Notes

* ❌ Do NOT upload `.env` file
* 🔐 Keep API keys private
* ⚠️ Ollama must be running locally
* 🌐 YouTube API has quota limits

---

## 🚀 Future Improvements

* 📊 Progress tracking dashboard
* 🔁 Smart revision system
* 🎯 Goal-based planning
* 📄 Export improvements
* 🔐 User authentication

---

## 👨‍💻 Author

**Rishabh Verma**

---

## ⭐ Support

If you like this project:

👉 Give it a ⭐ on GitHub
👉 Share with others

---

## 📜 License

This project is licensed under the **MIT License**
