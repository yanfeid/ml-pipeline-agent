# setup.py
from setuptools import setup, find_packages

with open(".version", "r") as f:
    version = f.read().strip()

setup(
    name="rmr_agent",
    version=version,
    packages=find_packages(),
    install_requires=["langgraph", "requests", "fastapi", "uvicorn", "streamlit"],  
)