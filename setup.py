# setup.py
from setuptools import setup, find_packages

setup(
    name="rmr_agent",
    version="0.1.0",
    packages=find_packages(),
    install_requires=["langgraph", "requests", "fastapi", "uvicorn"],  
)