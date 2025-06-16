import os
import subprocess
import re
import logging
import shutil
import requests
import time
import json
from urllib.parse import urlparse
from contextlib import contextmanager
from pathlib import Path
from typing import List, Tuple


def parse_github_url(url: str) -> tuple[str, str]:
    """
    Extract repository owner and name from a GitHub URL.
    
    Args:
        url (str): GitHub repository URL (https://github.paypal.com/owner/repo_name.git)
        
    Returns:
        tuple[str, str]: A tuple containing (owner, repository_name)
        
    Examples:
        >>> parse_github_url("https://github.paypal.com/owner/repo_name.git")
        ('owner', 'repo_name')
        >>> parse_github_url("https://github.com/owner/repo_name")
        ('owner', 'repo_name')
    """
    # First attempt: use regex pattern
    pattern = r"(?:https?://)?(?:www\.)?github\.(?:[\w.]+)/([^/]+)/([^/]+?)(?:\.git|/tree/|/blob/|/commit/|/pull/|/issues/)?(?:/.*)?$"
    match = re.match(pattern, url)
    
    if match:
        owner, repo = match.groups()
        return owner, repo
    
    # Second attempt: use URL parsing
    try:
        # Parse the URL and get the path
        parsed_url = urlparse(url)
        # Split the path and remove empty strings
        path_parts = [p for p in parsed_url.path.split('/') if p]
        
        if len(path_parts) >= 2:
            owner = path_parts[0]
            repo = path_parts[1].replace('.git', '')
            return owner, repo
            
    except Exception as e:
        raise ValueError(f"Could not parse GitHub URL: {url}") from e
        
    raise ValueError(f"Invalid GitHub URL format: {url}")
    


@contextmanager
def temporary_working_directory(path: str):
    """A context manager to temporarily change the working directory."""
    original_path = os.getcwd()  # Save the current working directory
    logging.debug(f"Changing working directory from {original_path} to {path}")
    if not os.path.exists(path):
        available_files = ', '.join(os.listdir(original_path))
        raise FileNotFoundError(f"The specified path {path} does not exist. "
                                f"Available files in {original_path}: {available_files}")
    os.chdir(path)  # Change to the new working directory
    try:
        yield
    finally:
        logging.debug(f"Reverting working directory to {original_path}")
        os.chdir(original_path)  # Revert back to the original directory
        
def load_env_file():
    # Assuming .env is in the current working directory
    env_path = Path('.env')
    if not env_path.exists():
        raise FileNotFoundError(
            f"No .env file found at {env_path.absolute()}. "
            "Please create one with GITHUB_TOKEN=your_token_here"
        )
    
    # Read and parse the .env file
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()
                

def get_github_username():
    # Load from .env 
    load_env_file()
    username = os.environ.get('GITHUB_USERNAME')
    if not username:
        env_path = Path('.env')
        guidance = (
            "GitHub username not found in environment variables. To fix this:\n"
            "1. Create or edit your .env file at {}\n"
            "2. Add the line: GITHUB_USERNAME=your_username_here\n"
        ).format(env_path.absolute())
        raise EnvironmentError(guidance)
    print('GitHub Username found')
    return username


SECONDS_24h = 86400


def print_data(msg: str, display: bool = True):
    def func(msg: str):
        print(msg)
        logging.info(msg)

    if display:
        func(msg)
    else:
        func("skip the sensitive log...")


class GitHub:
    def __init__(self,
                 repo_owner: str,
                 repo_name: str,
                 account: str,
                 local_dir: str = ".",
                 env_path: Path = Path(".env")
                 ):

        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.local_dir = local_dir
        self.account = account
        self.env_path = env_path

        # API URLs are constructed on the fly in methods
        print(f"GitHub API client initialized for upstream '{repo_owner}/{repo_name}' on behalf of account '{account}'.")
    
    def __get_github_token(self):
        self.__load_env_file()
        token = os.environ.get('GITHUB_TOKEN')
        if not token:
            guidance = (
                "GitHub token not found in environment variables. To fix this:\n"
                "1. Create or edit your .env file at {}\n"
                "2. Add the line: GITHUB_TOKEN=your_token_here\n"
                "3. Get a Personal Access Token (PAT) from https://github.paypal.com/settings/tokens\n"
                "4. Replace 'your_token_here' with your actual token"
            ).format(self.env_path.absolute())
            raise EnvironmentError(guidance)
        return token
    
    def __load_env_file(self):
        if not self.env_path.exists():
            raise FileNotFoundError(
                f"No .env file found at {self.env_path.absolute()}. "
                "Please create one with GITHUB_TOKEN=your_token_here"
            )
        # Read and parse the .env file
        with open(self.env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

    def run_command(self, command: List[str], print_log: bool = True) -> str:
        command_str = ' '.join(command)
        try:
            print_data(f"Running command: '{command_str}' ", print_log)
            p = subprocess.run(command, check=True,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT,
                               env=os.environ.copy())
            print_data("-------cmd stdout--------")
            print_data(p.stdout, print_log)
            return p.stdout
        except subprocess.CalledProcessError as e:
            error_message = e.output.decode()
            print_data(f"Error running command: '{command_str}': {error_message}", print_log)
            raise e
        
    # --- Repository Info Method ---

    def _get_branch(self, branch_name: str) -> dict | None:
        """(Internal) Tries to get details for a specific branch. Returns None if not found."""
        api_url = f"https://github.paypal.com/api/v3/repos/{self.repo_owner}/{self.repo_name}/branches/{branch_name}"
        headers = {"Authorization": f"token {self.__get_github_token()}"}
        response = requests.get(api_url, headers=headers)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            return None
        else:
            response.raise_for_status()

    def get_default_branch(self) -> str:
        """Gets the default branch name (e.g., 'main') for the upstream repository."""
        print("Finding the default branch of the upstream repository...")
        api_url = f"https://github.paypal.com/api/v3/repos/{self.repo_owner}/{self.repo_name}"
        headers = {"Authorization": f"token {self.__get_github_token()}"}
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()
        default_branch = response.json()["default_branch"]
        print(f"Found default branch: '{default_branch}'")
        return default_branch
    
    def get_target_branch(self) -> str:
        """
        Determines the best target branch for a PR. Prefers 'dev', falls back to default.
        """
        print("Determining the best target branch for the pull request...")
        if self._get_branch("dev"):
            print("Found 'dev' branch. It will be used as the target.")
            return "dev"
        else:
            print("'dev' branch not found. Falling back to the repository's default branch.")
            default_branch = self.get_default_branch()
            print(f"Found default branch: '{default_branch}'")
            return default_branch
    
    # --- Forking Methods ---

    def _get_repo(self, owner: str, repo: str) -> dict | None:
        """(Internal) Gets data for a specific repository. Returns None if not found."""
        api_url = f"https://github.paypal.com/api/v3/repos/{owner}/{repo}"
        headers = {
            "Authorization": f"token {self.__get_github_token()}",
            "Accept": "application/vnd.github.v3+json"
        }
        response = requests.get(api_url, headers=headers)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            return None
        response.raise_for_status()

    def _create_fork(self) -> dict:
        """
        (Internal) Creates a fork of the repository with a prefixed name.
        
        This can be a long-running operation on GitHub's side.
        """
        # The API endpoint to create a fork is on the original ("upstream") repository
        forks_api_url = f"https://github.paypal.com/api/v3/repos/{self.repo_owner}/{self.repo_name}/forks"
        
        headers = {
            "Authorization": f"token {self.__get_github_token()}",
            "Accept": "application/vnd.github.v3+json"
        }

        print(f"Creating a fork of '{self.repo_owner}/{self.repo_name}' ... This may take a moment.")
        response = requests.post(forks_api_url, headers=headers, json={})

        # A 202 Accepted status means GitHub has started the forking process in the background
        if response.status_code == 202:
            print("Forking process initiated successfully.")
            return response.json()
        else:
            raise Exception(f"Failed to create fork: {response.status_code} - {response.text}")

    def ensure_fork_exists(self) -> dict:
        """
        Checks if a fork exists, creates it if not, and waits for it to be ready.
        Handles the same-owner case by returning the original repo details. You cannot fork your own repo.
        
        Returns:
            dict: The API details of the available fork.
        
        Raises:
            TimeoutError: If the fork is not available within the max wait time.
        """
        # --- Smart Same-Owner Check ---
        if self.repo_owner.lower() == self.account.lower():
            print("Running in 'Same-Owner' mode. Treating original repo as the 'fork'.")
            repo_details = self._get_repo(self.repo_owner, self.repo_name)
            if not repo_details:
                raise FileNotFoundError(f"Could not find the repository {self.repo_owner}/{self.repo_name}.")
            return repo_details
        
        # --- Standard Forking Workflow ---
        fork_details = self._get_repo(self.account, self.repo_name)
        if fork_details:
            parent_full_name = fork_details.get("parent", {}).get("full_name")
            if fork_details.get("fork") and parent_full_name == f"{self.repo_owner}/{self.repo_name}":
                 print(f"Found existing fork: {fork_details['full_name']}")
                 return fork_details

        # If no fork, create it and then poll until it's ready
        print(f"Fork '{self.account}/{self.repo_name}' not found or invalid. Creating a new one...")
        self._create_fork()

        print("Polling to check when fork is ready...")
        max_wait_seconds = 180
        poll_interval_seconds = 10
        start_time = time.time()

        while time.time() - start_time < max_wait_seconds:
            fork_details = self._get_repo(self.account, self.repo_name)
            if fork_details:
                print("✅ Fork is now available on GitHub.")
                # Add a short, final delay to allow the git backend to become ready for cloning.
                print("Adding a brief 5-second delay to ensure repository is cloneable...")
                time.sleep(5)
                return fork_details
            print(f"Fork not yet available. Waiting {poll_interval_seconds} more seconds...")
            time.sleep(poll_interval_seconds)
        
        raise TimeoutError(
            f"Fork for '{self.account}/{self.repo_name}' was not created within {max_wait_seconds} seconds."
        )
    
    # --- PR Methods ---

    def create_pull_request(
        self,
        title: str,
        body: str,
        head: str,
        base: str
    ) -> str:
        """
        Creates a pull request on the GitHub Enterprise repository.
        Automatically formats the 'head' parameter based on whether it's a fork or a same-owner repository.

        Args:
            title (str): The title of the pull request.
            body (str): The body/description of the pull request.
            head (str): The name of the branch where your changes are implemented.
            base (str): The name of the branch you want to merge the changes into.

        Returns:
            str: The HTML URL of the created pull request (viewable in a browser).

        Raises:
            Exception: If the pull request could not be created (non-201 response).
        """

        pulls_api_url = f"https://github.paypal.com/api/v3/repos/{self.repo_owner}/{self.repo_name}/pulls"
        
        headers = {
            "Authorization": f"token {self.__get_github_token()}",
            "Accept": "application/vnd.github.v3+json"
        }

        # --- Smart Head Formatting ---
        # If the upstream owner is different from the agent's account, it's a fork.
        if self.repo_owner.lower() != self.account.lower():
            formatted_head = f"{self.account}:{head}"
        else:
            # Otherwise, it's a branch in the same repository.
            formatted_head = head
        # --------------------------

        payload = {
            "title": title,
            "body": body,
            "head": formatted_head,  # Use the correctly formatted head
            "base": base
        }

        response = requests.post(pulls_api_url, headers=headers, json=payload)

        if response.status_code == 201:
            return response.json()["html_url"]
        else:
            raise Exception(f"Failed to create PR: {response.status_code} - {response.text}")
        

    def list_pull_requests(self, head: str, base: str, state: str = "open") -> list:
        """
        Lists pull requests for the repository.

        Args:
            head (str): Filter pulls by head user and branch name in the format 'user:ref-name'.
            base (str): Filter pulls by base branch name.
            state (str): Either `open`, `closed`, or `all`. Defaults to `open`.

        Returns:
            list: A list of pull request objects from the API.
        """
        pulls_api_url = f"https://github.paypal.com/api/v3/repos/{self.repo_owner}/{self.repo_name}/pulls"

        headers = {
            "Authorization": f"token {self.__get_github_token()}",
            "Accept": "application/vnd.github.v3+json"
        }

        # --- Smart Head Formatting ---
        # If the upstream owner is different from the agent's account, it's a fork.
        if self.repo_owner.lower() != self.account.lower():
            formatted_head = f"{self.account}:{head}"
        else:
            # Otherwise, it's a branch in the same repository.
            formatted_head = head
        # --------------------------

        params = {
            "state": state,
            "head": formatted_head,  # Use the correctly formatted head
            "base": base
        }

        print(f"Searching for existing PRs with head='{formatted_head}' and base='{base}'...")
        response = requests.get(pulls_api_url, headers=headers, params=params)
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
        return response.json()


    # Context Manager -----------------------------------------------
    def __enter__(self):
        # anything to init here?
        logging.info("enter github context")
        return self

    def __exit__(self, _type, _value, _tb):
        # anything to clean up here?
        logging.info("exit github context")

    # /Context Manager ----------------------------------------------



def fork_and_clone_repo(github_url: str, run_id: int, local_base_dir: str = "rmr_agent/repos") -> Tuple[str, str]:
    """
    Orchestrates the entire repository setup using a forking model.
    1. Ensures a fork of the upstream repository exists on GitHub using the API.
    2. Performs a shallow clone of that fork.
    3. Configures an 'upstream' remote pointing to the original repository.
    4. Creates and checks out a new branch based on the latest upstream code.

    Args:
        github_url: The HTTPS URL of the ORIGINAL ("upstream") repository.
        run_id: Unique identifier for the run, used for the branch name.
        local_base_dir: The base directory where the local repository will be cloned.

    Returns:
        Tuple[str, str]: The local path to the cloned repository, and the clone URL of the fork.
    """
    # --- 1. Initial Setup and API Interaction ---
    print("--- Step 1: Initializing and Ensuring Fork Exists ---")
    # extract repo owner and repo name from url
    upstream_owner, repo_name = parse_github_url(github_url)
    account = get_github_username()

    # Retrieve full path to the .env file before we change the working directory
    env_path = Path('.env').resolve()

    # Ensure the fork exists under the authenticated user's account
    gh_api_client = GitHub(
        repo_owner=upstream_owner, 
        repo_name=repo_name, 
        account=account,
        env_path=env_path
    )
    fork_details = gh_api_client.ensure_fork_exists()
    fork_clone_url = fork_details["clone_url"]

    # --- 2. Local Repository Setup ---
    local_repo_path = os.path.join(local_base_dir, repo_name)
    branch_name = f"rmr_agent_{run_id}"
    if os.path.exists(local_repo_path):
        print(f"Removing existing local repository at '{local_repo_path}'...")
        shutil.rmtree(local_repo_path)
    os.makedirs(local_base_dir, exist_ok=True)

    # # --- 3. Clone repo to local directory ---
    print(f"Performing a shallow clone of your fork from '{fork_clone_url}'...")
    print(f"Changing working directory temporarily to {local_base_dir} to clone the repo")
    # Change into the base directory where we want to clone the repo into
    with temporary_working_directory(local_base_dir):
        try:
            # Clone repo, configure remote URL with token for authentication, and change to the cloned repo directory
            gh_local_runner = GitHub(
                repo_owner=account, # The owner of the fork is the current account
                repo_name=repo_name, 
                account=account,
                env_path=env_path # Pass the absolute path
            )

            # Clone the fork repository with a depth of 1 to avoid downloading the entire history
            gh_local_runner.run_command(["git", "clone", "--depth", "1", fork_clone_url])

            # Change directory into the newly cloned repo
            os.chdir(repo_name)

            # Configure the upstream remote
            # Only add an upstream remote if we are in a true forking workflow
            source_remote = "origin"
            if upstream_owner.lower() != account.lower():
                print(f"Adding original repository '{github_url}' as 'upstream' remote...")
                gh_local_runner.run_command(["git", "remote", "add", "upstream", github_url])
                # Fetch the latest commit from the upstream remote - ensure we are working with the latest code from the research repository
                gh_local_runner.run_command(["git", "fetch", "--depth", "1", "upstream"])
                source_remote = "upstream"
            else:
                gh_local_runner.run_command(["git", "fetch", "--depth", "1", "origin"])

            # Use the API client to reliably get the default branch name
            print("Using API to find default branch...")
            default_branch = gh_api_client.get_default_branch()

            # --- Robust Branch Creation/Reset --
            print(f"Ensuring branch '{branch_name}' is based on latest '{source_remote}/{default_branch}'...")
            try:
                # Attempt to create the new branch from the latest upstream code
                gh_local_runner.run_command(["git", "checkout", "-b", branch_name, f"{source_remote}/{default_branch}"])
                print(f"Created new branch '{branch_name}'.")
            except subprocess.CalledProcessError as e:
                # If the branch already exists, check it out and reset it to the latest upstream
                if "already exists" in e.stderr:
                    print(f"Branch '{branch_name}' already exists. Switching to it and resetting to latest upstream code.")
                    gh_local_runner.run_command(["git", "checkout", branch_name])
                    gh_local_runner.run_command(["git", "reset", "--hard", f"{source_remote}/{default_branch}"])
                else:
                    # If it's a different git error, re-raise it
                    raise

        except subprocess.CalledProcessError as e:
            # Capture more specific error details from the process
            error_message = e.stderr if hasattr(e, 'stderr') and e.stderr else str(e)
            raise RuntimeError(f"An error occurred during the git process: {error_message}") from e

    print(f"\n✅ Successfully set up repository and created branch '{branch_name}' at '{local_repo_path}'.")
    return local_repo_path, fork_clone_url


def push_refactored_code(github_url: str, run_id: int, local_base_dir: str = "rmr_agent/repos") -> bool:
    """
    Adds, commits, and pushes refactored code to the specified branch on the agent's fork.
    This function assumes 'fork_and_clone_repo' has already been successfully executed.

    Args:
        github_url (str): The GitHub repository URL of the UPSTREAM repository.
        run_id (int): Unique identifier for the run, matching the branch name.
        local_base_dir (str): Base directory where the cloned repo is stored.
        
    Returns:
        bool: True if new code was successfully pushed, False otherwise.
    """
    # extract repo owner and repo name from url
    upstream_owner, repo_name = parse_github_url(github_url)
    account = get_github_username()

    local_repo_path = os.path.join(local_base_dir, repo_name)
    branch_name = f"rmr_agent_{run_id}"
    if not os.path.exists(local_repo_path):
        raise FileNotFoundError(f"The local repository path {local_repo_path} does not exist. Please run 'fork_and_clone_repo' first.")
    
    # Retrieve full path to the .env file before we change the working directory
    env_path = Path('.env').resolve()

    # --- Configurable list of paths to add to git ---
    # To add more files or directories later, just add them to this list.
    paths_to_add = [
        "notebooks/",
        "config/",
        "rmr_agent_results.md" # Summary of agent contributions should be included
    ]
    # ---------------------------------------------------

    print(f"Changing working directory to {local_base_dir} and checking out branch {branch_name} to push the changes")
    # We change into the actual repository path to run git commands
    with temporary_working_directory(local_repo_path):
        try:
            # This GitHub instance is for running local commands inside the fork's clone.
            gh = GitHub(
                repo_owner=account, # The owner of the fork is the current account
                repo_name=repo_name, 
                account=account, 
                env_path=env_path
            ) 

            # Ensure we are on the correct branch. 'fork_and_clone_repo' already created it.
            print(f"Ensuring we are on branch '{branch_name}'...")
            gh.run_command(["git", "checkout", branch_name])

            # Add all changes in the specified directories
            print("Adding refactored files to git staging area...")
            for path in paths_to_add:
                if os.path.exists(path):
                    print(f"  Adding '{path}'...")
                    gh.run_command(["git", "add", path])
                else:
                    print(f"  Skipping non-existent path: '{path}'")

            # Attempt to commit. It's okay if this fails because there's nothing new.
            try:
                commit_message = f"RMR Agent Run {run_id}: Add refactored notebooks and config"
                gh.run_command(["git", "commit", "-m", commit_message])
                print(f"Successfully committed new changes to branch '{branch_name}'.")
            except subprocess.CalledProcessError as e:
                output_str = (e.stdout or b'').decode('utf-8', errors='ignore')
                stderr_str = (e.stderr or b'').decode('utf-8', errors='ignore')
                full_output = (output_str + stderr_str).lower()
                if "nothing to commit" in full_output:
                    print("No new changes to commit. Proceeding to push existing state.")
                else:
                    # A different, unexpected commit error occurred.
                    raise

            # Fetch the latest state of the remote before pushing to avoid 'stale info' errors.
            print("Fetching latest state from remote 'origin'...")
            gh.run_command(["git", "fetch", "origin"])

            # Force push changes to 'origin', which is the agent's fork.
            # This ensures the agent's work is the source of truth for its own branch.
            # Always attempt to push. Git will handle the "already up-to-date" case.
            print(f"Pushing changes to remote 'origin' (the fork)...")
            gh.run_command(["git", "push", "--force", "origin", branch_name])
            print(f"✅ Successfully pushed code to branch '{branch_name}' on the agent's fork.")
            return True

        except subprocess.CalledProcessError as e:
            # If the push fails because the branch is already up-to-date, it's not a true failure.
            error_str = e.stderr.lower() if e.stderr else ""
            if "already up-to-date" in error_str or "no changes" in error_str:
                print("No new commits to push; branch is already up-to-date.")
                return False
            
            # For all other errors, raise them
            raise RuntimeError(f"Failed to push code to branch {branch_name}: {error_str}") from e    


def create_rmr_agent_pull_request(github_url: str, pr_body_text: str, run_id: int) -> str:
    """
    Creates a pull request from the agent's fork to the upstream repository's target branch.
    It prefers to target 'dev', but falls back to the default branch.
    If a PR already exists, it fetches and returns its URL.

    Args:
        github_url (str): The GitHub repository URL of the UPSTREAM repository.
        pr_body_text (str): The body content for the pull request.
        run_id (int): Unique identifier for the run, matching the branch name.
        
    Returns:
        str: The URL of the created or existing pull request.
    """
    print("\n--- Creating Pull Request ---")
    # extract repo owner and repo name from url
    upstream_owner, repo_name = parse_github_url(github_url)
    account = get_github_username()
    branch_name = f"rmr_agent_{run_id}"

    # Initialize the GitHub client to interact with the UPSTREAM repository's API
    gh = GitHub(
        repo_owner=upstream_owner, 
        repo_name=repo_name, 
        account=account
    )
    
    pr_url = None
    try:
        # 1. Dynamically find the best target branch ('dev' or default)
        base_branch = gh.get_target_branch()

        # 2. Attempt to create the pull request
        pr_title = f"RMR Agent Refactor - Run {run_id}"
        print(f"Attempting to create PR from '{account}:{branch_name}' to '{upstream_owner}:{base_branch}'...")
        
        pr_output = gh.create_pull_request(
            title=pr_title,
            body=pr_body_text,
            head=branch_name,
            base=base_branch
        )
        pr_details = pr_output if isinstance(pr_output, dict) else json.loads(pr_output or '{}')
        pr_url = pr_details.get("html_url") or pr_details.get("url")
        if not pr_url:
            raise ValueError(f"Could not find 'html_url' or 'url' in the pull request response: {pr_details}")
        print(f"✅ Pull Request created successfully: {pr_url}")
        return pr_url

    except Exception as e:
        error_text = str(e).lower()
        # 3. If it already exists, find and return its URL
        if "already exists" in error_text:
            print("A pull request for this branch already exists. Fetching its URL...")
            try:
                # We need the target branch again to search for the existing PR
                base_branch = gh.get_target_branch()
                existing_prs_output = gh.list_pull_requests(head=branch_name, base=base_branch)
                if isinstance(existing_prs_output, str):
                    existing_prs = json.loads(existing_prs_output)
                else:
                    existing_prs = existing_prs_output

                if existing_prs:
                    # The response is a list, so we take the first element
                    pr_url = existing_prs[0].get("html_url") or existing_prs[0].get("url")
                    if not pr_url:
                        raise ValueError(f"Could not find 'html_url' or 'url' in existing PR data: {existing_prs[0]}")
                    print(f"✅ Found existing PR: {pr_url}")
                    return pr_url
                else:
                    print("Could not find the existing PR, though creation failed. Please check GitHub.")
            except Exception as list_e:
                print(f"Failed to list existing pull requests: {list_e}")
        raise RuntimeError(f"Failed to create or find pull request: {e}") from e
