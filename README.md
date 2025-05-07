# RMR Agent
Agentic AI for Converting ML Code into Production Pipelines

For background and solution architecture, please see our [confluence page](https://paypal.atlassian.net/wiki/spaces/~matjacobs/pages/1112741635/Day+Zero+RMR+-+Agentic+AI+for+Converting+ML+Code+into+Production+Pipelines)

## How to run
Follow these steps to set up and run the project locally.

### Setup Instructions

1. **Clone the Repository**
```bash
git clone https://github.paypal.com/FOCUS-ML/rmr_agent.git
cd rmr_agent
```

2. **Create and Activate a Virtual Environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows, use: venv\Scripts\activate
```

3. **Install Dependencies**
```bash
pip install -r requirements.txt
```

4. **Set Up Environment Variables**
Copy the .env.example file to create a .env file:
```bash
cp .env.example .env
```
Edit the .env file to populate the required values:
- GitHub Credentials:
    - GITHUB_USERNAME: Your GitHub username.
    - GITHUB_TOKEN: A GitHub personal access token. Generate one at https://github.paypal.com/settings/tokens with appropriate scopes (e.g., repo).
- Azure Credentials:
    - AZURE_CLIENT_ID and other Azure variables: Contact the project maintainer (matjacobs@paypal.com or yanfdai@paypal.com) to obtain these credentials, as they are specific to the project’s Azure infrastructure.
- Model Configuration:
    - MODEL_NAME: Defaults to gpt-4o. Will share list of supported models later, for now you should leave this as gpt-4o. 

Important: Do not commit your .env file to the repository, as it contains sensitive credentials. The .gitignore file excludes it by default.


### Running the Application
The project consists of a backend API and a Streamlit frontend UI. You’ll need to run each in separate terminal sessions.


1. **Start the Backend API**
```bash
python run_api.py
```
The API should start on http://localhost:8000

2. **Run the Streamlit Frontend UI**
```bash
python run_ui.py
```
The Streamlit UI should open in your default browser at http://localhost:8501.


View checkpoints stored locally at `rmr_agent/checkpoints/`

