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

### Using the Application

1. **Provide research repository `GitHub URL`**
- Your exploratory ML code should be in a public github repo that we can access

2. **Provide `list of files` containing your ML pipeline logic**
- For now, we require you to manually provide the list of files which contain your full end-to-end model development code. 
    - Later we may develop an agent to automatically extract this and ask for your verification
- Files should be relative paths from the root directory of your repository, and separated by new lines. 
- You should specify the files in the order they should be executed in your ML pipeline. 

3. **Specify Run ID (Optional)**
- You can optionally set a Run ID (1, 2, 3, etc.) to:
    - Organize Experiments: Use a unique run ID to create a separate checkpoint folder for each trial, keeping your results and model states isolated and easy to track.
    - Enable Reproducibility: Assigning a run ID ensures you can revisit or resume a specific trial later, preserving its settings and progress for comparison or auditing.

4. **Specify a step to Start From**
- If you have completed some or all steps of the workflow, and have returned to the home page, you can optionally choose a step to start the workflow from. 
- Only those steps which have completed for this particular repository and Run ID will appear as options to Start From. 
- Setting Start From enables:
    - Resume from Checkpoints: Select a completed step from the dropdown menu to start your workflow from a saved checkpoint, saving time by skipping earlier steps.
    - Backtrack Flexibly: Choose a previous step to revisit or adjust part of the workflow without rerunning the entire process, maintaining efficiency and control