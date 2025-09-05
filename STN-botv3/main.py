#!/usr/bin/env python3
"""
STN-bot v3 - Point d'entrée
Usage: streamlit run main.py
"""

from dotenv import load_dotenv
load_dotenv()

from app import STNBot

if __name__ == "__main__":
    app = STNBot()
    app.run()
