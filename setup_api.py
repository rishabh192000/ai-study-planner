"""
API Setup Helper for Smart AI Study Planner
===========================================
This file helps you set up Ollama for local AI.
"""

def setup_ollama():
    print("=" * 50)
    print("SMART AI STUDY PLANNER - OLLAMA SETUP")
    print("=" * 50)
    print()
    
    print("Follow these steps to set up Ollama:")
    print()
    print("1. Download Ollama from: https://ollama.com/")
    print("2. Install Ollama on your computer")
    print("3. Open a terminal and run: ollama serve")
    print("4. Download a model: ollama pull llama3.2")
    print("   (or try: ollama pull mistral)")
    print()
    print("The app will use http://localhost:11434 as the API endpoint.")
    print()
    
    input("Press Enter after you've set up Ollama...")
    
    # Test the connection
    print("Testing Ollama connection...")
    import requests
    
    payload = {
        "model": "llama3.2",
        "messages": [{"role": "user", "content": "Reply with 'OK'"}],
        "stream": False
    }
    
    try:
        response = requests.post(
            "http://localhost:11434/api/chat",
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            print("SUCCESS! Ollama is working!")
            return True
        else:
            print(f"ERROR: {response.status_code}")
            print(response.text[:200])
            return False
    except requests.exceptions.ConnectionError:
        print("ERROR: Cannot connect to Ollama.")
        print("Make sure Ollama is running (run 'ollama serve' in terminal)")
        return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False

if __name__ == "__main__":
    setup_ollama()
