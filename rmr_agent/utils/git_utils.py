import os
import subprocess
import re
import logging
import shutil
from urllib.parse import urlparse
from contextlib import contextmanager
from pathlib import Path
from typing import List


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
                

def get_github_token():
    # Load from .env 
    load_env_file()
    token = os.environ.get('GITHUB_TOKEN')
    if not token:
        env_path = Path('.env')
        guidance = (
            "GitHub token not found in environment variables. To fix this:\n"
            "1. Create or edit your .env file at {}\n"
            "2. Add the line: GITHUB_TOKEN=your_token_here\n"
            "3. Get a Personal Access Token (PAT) from https://github.paypal.com/settings/tokens\n"
            "4. Replace 'your_token_here' with your actual token"
        ).format(env_path.absolute())
        raise EnvironmentError(guidance)
    print('GitHub Token found')
    return token

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
                 token: str,
                 local_dir: str = ".",
                 make_local_dir: bool = True):

        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.local_dir = local_dir
        self.account = account
        self.token = token

        if self.local_dir.startswith("/"):
            raise FileNotFoundError(f"only accept relative directory, the local dir is absolute {self.local_dir}")

        if not os.path.exists(self.local_dir):
            if make_local_dir:
                logging.info(f"make local dir")
                os.makedirs(self.local_dir, exist_ok=True)
            else:
                raise FileNotFoundError(f"The specified dir {self.local_dir} does not exist,"
                                        f" please set make_local_dir by True")
        os.chdir(self.local_dir)

        self.__init_git()

    def __init_git(self):
        # the decipher of encrypted token has been removed, for local development we store PAT as environment variable
        # token = self.__get_github_token()
        url = f"https://{self.account}:{self.token}@github.paypal.com/{self.repo_owner}/{self.repo_name}.git"
        # del token

        self.run_command(["git", "config", "--global", "credential.helper", f'cache --timeout={SECONDS_24h}'])
        if os.path.exists(self.repo_name):
            os.chdir(self.repo_name)
            self.run_command(["git", "remote", "set-url", "origin", url], False)
            print_data(f"git url is reset ")
        else:
            print('cloning repo...')
            self.run_command(["git", "clone", "--depth=1", url], True)
            logging.info(f"git clone is done ")
            os.chdir(self.repo_name)

        del url
    
    def __get_github_token(self):
        self.__load_env_file()
        token = os.environ.get('GITHUB_TOKEN')
        if not token:
            env_path = Path('.env')
            guidance = (
                "GitHub token not found in environment variables. To fix this:\n"
                "1. Create or edit your .env file at {}\n"
                "2. Add the line: GITHUB_TOKEN=your_token_here\n"
                "3. Get a Personal Access Token (PAT) from https://github.paypal.com/settings/tokens\n"
                "4. Replace 'your_token_here' with your actual token"
            ).format(env_path.absolute())
            raise EnvironmentError(guidance)
        return token
    
    def __load_env_file(self):
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

    # Context Manager -----------------------------------------------
    def __enter__(self):
        # anything to init here?
        logging.info("enter github context")
        return self

    def __exit__(self, _type, _value, _tb):
        # anything to clean up here?
        logging.info("exit github context")

    # /Context Manager ----------------------------------------------



def clone_repo(github_url: str, run_id: int, local_base_dir: str = "rmr_agent/repos") -> str:
    """Clone a GitHub repo and checkout a new branch 'rmr_agent'.
    
    Args:
        github_url: The GitHub repository URL.
        run_id: Unique identifier for the run, used to create a unique branch.
        local_base_dir: Base directory to store cloned repos.
    
    Returns:
        str: local_repo_path
    """
    # extract repo owner and repo name from url
    repo_owner, repo_name = parse_github_url(github_url)

    # extract github username and token from environment variables
    account = get_github_username()
    using_service_account = account == 'rmr-agent'
    token = get_github_token()

    local_repo_path = os.path.join(local_base_dir, repo_name)
    
    if os.path.exists(local_repo_path):
        shutil.rmtree(local_repo_path)

    branch_name = f"rmr_agent_{run_id}"

    # clone repo to local directory. This also authenticates with git and safely caches credentials for 24H
    print(f"Changing working directory to {local_base_dir} to clone the repo")
    with temporary_working_directory(local_base_dir):
        try:
            # Clone repo, configure remote URL with token for authentication, and change to the cloned repo directory
            gh = GitHub(repo_owner=repo_owner, repo_name=repo_name, account=account, token=token) 

            # Check if 'dev' branch exists remotely
            dev_branch_exists = False
            try:
                ls_remote_output = gh.run_command(["git", "ls-remote", "--heads", "origin", "dev"])
                if ls_remote_output.decode().strip():
                    dev_branch_exists = True
                    print("Remote 'dev' branch exists.")
            except subprocess.CalledProcessError:
                print("Remote 'dev' branch does not exist.")

            # If 'dev' branch doesn't exist, create and push it
            if not dev_branch_exists and using_service_account:
                print("Creating and pushing 'dev' branch to remote.")
                # Fetch to ensure we have the latest remote state
                gh.run_command(["git", "fetch", "origin"])
                # Determine the default branch (e.g., 'main' or 'master')
                try:
                    default_branch_output = gh.run_command(["git", "symbolic-ref", "refs/remotes/origin/HEAD"])
                    default_branch = default_branch_output.decode().strip().split('/')[-1]
                    print(f"Detected default branch: {default_branch}")
                except subprocess.CalledProcessError:
                    # Fallback to common default branches if symbolic-ref fails
                    default_branch = "main"  
                    print(f"Could not determine default branch, assuming '{default_branch}'.")

                # Checkout the default branch
                gh.run_command(["git", "checkout", default_branch])
                # Create and push the 'dev' branch
                gh.run_command(["git", "checkout", "-b", "dev"])
                try:
                    gh.run_command(["git", "push", "origin", "dev"])
                except subprocess.CalledProcessError as e:
                    error_message = e.output.decode() if e.output else str(e)
                    print(f"Error pushing 'dev' branch: {error_message}")
                    raise RuntimeError(f"Failed to push 'dev' branch: {error_message}. Please ensure the service account (rmr-agent) has permission to push to the repository.")
                print("Successfully created and pushed 'dev' branch.")

            # Create and checkout the rmr_agent branch
            try:
                gh.run_command(["git", "checkout", "-b", branch_name])
                print(f"Created and switched to branch: {branch_name}")
            except subprocess.CalledProcessError as e:
                error_message = e.output.decode() if e.output else str(e)
                print(f"Error creating branch {branch_name}: {error_message}")
                raise RuntimeError(f"Failed to create branch {branch_name}: {error_message}")
        except subprocess.CalledProcessError as e:
            error_message = e.output.decode()
            print(f"Error cloning repo: {error_message}")
            raise e

    print(f"Changing working directory back to {os.getcwd()}")
    
    return local_repo_path


def push_refactored_code(github_url: str, run_id: int, local_base_dir: str = "rmr_agent/repos") -> bool:
    """Push refactored code to the rmr_agent_{run_id} branch in the GitHub repository.

    Args:
        github_url (str): The GitHub repository URL.
        run_id (int): Unique identifier for the run, used to create a unique branch.
        local_base_dir (str): Base directory where the cloned repo is stored.
        
    Returns:
        bool: True if the code was successfully pushed, False otherwise.
    
    """
    # extract repo owner and repo name from url
    repo_owner, repo_name = parse_github_url(github_url)

    # extract github username and token from environment variables
    account = get_github_username()
    using_service_account = account == 'rmr-agent'
    token = get_github_token()

    local_repo_path = os.path.join(local_base_dir, repo_name)

    if not os.path.exists(local_repo_path):
        raise FileNotFoundError(f"The local repository path {local_repo_path} does not exist,"
                                f" cannot push code to remote repository.")
    
    branch_name = f"rmr_agent_{run_id}"
    
    print(f"Changing working directory to {local_base_dir} to push the changes")
    with temporary_working_directory(local_base_dir):
        try:
            gh = GitHub(repo_owner=repo_owner, repo_name=repo_name, account=account, token=token) 
            # Check if branch already exists and handle accordingly
            try:
                gh.run_command(["git", "checkout", branch_name])
                print(f"Switched to existing branch: {branch_name}")
            except subprocess.CalledProcessError:
                # Branch doesn't exist, create it
                gh.run_command(["git", "checkout", "-b", branch_name])
                print(f"Created new branch: {branch_name}")
            
            # Add files with error handling
            files_to_add = []
            
            # Check for notebooks directory
            if os.path.exists("notebooks"):
                notebook_files = [f for f in os.listdir("notebooks") if f.endswith('.ipynb')]
                if notebook_files:
                    gh.run_command(["git", "add", "notebooks/*.ipynb"])
                    files_to_add.extend([f"notebooks/{f}" for f in notebook_files])

            # Check for config files
            config_files = ["config/solution.ini", "config/environment.ini"]
            for config_file in config_files:
                if os.path.exists(config_file):
                    gh.run_command(["git", "add", config_file])
                    files_to_add.append(config_file)

            if not files_to_add:
                raise ValueError("No files found to add. Expected notebooks/, config/")

            print(f"Added files: {', '.join(files_to_add)}")

            # Check if there are any changes to commit
            try:
                status_output = gh.run_command(["git", "status", "--porcelain"])
                if not status_output.strip():
                    print("No changes to commit.")
                    return f"No changes found in branch {branch_name}"
            except:
                # If git status fails, proceed with commit attempt
                pass

            # Commit changes
            gh.run_command(["git", "commit", "-m", "Add notebooks and config files from RMR Agent"])
            success_message = f"Successfully committed changes to branch '{branch_name}'"
            print(success_message)
            
            # Push changes to remote repository
            if using_service_account:
                try:
                    gh.run_command(["git", "push", "origin", branch_name])
                except subprocess.CalledProcessError as e:
                    error_message = e.output.decode() if e.output else str(e)
                    print(f"Error pushing code to branch {branch_name}: {error_message}")
                    raise RuntimeError(f"Failed to push code to branch {branch_name}: {error_message}. Please ensure the service account (rmr-agent) has permission to push to the repository.")

                success_message = f"Successfully pushed code to branch '{branch_name}'"
                print(success_message)

            return success_message

        except subprocess.CalledProcessError as e:
            error_message = e.output.decode()
            print(f"Error pushing code to rmr_agent branch: {error_message}")
            raise e
            
    print(f"Changing working directory back to {os.getcwd()}")


def extract_pr_url_from_json_output(output: bytes) -> str:
    """
    Extract PR URL from GitHub CLI output.
    
    The gh pr create command typically outputs the PR URL on the last line.
    Example output: "https://github.com/owner/repo/pull/123"
    """
    if not output:
        raise ValueError("No output received from PR creation command")
    
    # Split by lines and get the last non-empty line
    lines = [line.strip() for line in output.strip().split('\n') if line.strip()]
    
    if not lines:
        raise ValueError("No valid output lines found")
    
    # The PR URL is typically on the last line
    potential_url = lines[-1]
    
    # Validate that it looks like a GitHub PR URL
    github_pr_pattern = r'https://github\.com/[^/]+/[^/]+/pull/\d+'
    
    if re.match(github_pr_pattern, potential_url):
        return potential_url
    
    # If the last line doesn't match, search through all lines
    for line in reversed(lines):
        if re.match(github_pr_pattern, line):
            return line
    
    # If no URL pattern found, return the last line (might be PR number or other info)
    raise ValueError(f"Could not extract PR URL from output: {output}")


def create_pull_request(github_url: str, pr_body_text: str, local_base_dir: str = "rmr_agent/repos") -> str:
    # extract repo owner and repo name from url
    repo_owner, repo_name = parse_github_url(github_url)

    # extract github username and token from environment variables
    account = get_github_username()
    token = get_github_token()

    local_repo_path = os.path.join(local_base_dir, repo_name)

    if not os.path.exists(local_repo_path):
        raise FileNotFoundError(f"The local repository path {local_repo_path} does not exist,"
                                f" cannot create PR.")
    
    print(f"Changing working directory to {local_base_dir} to create the PR")
    with temporary_working_directory(local_base_dir):
        try:
            gh = GitHub(repo_owner=repo_owner, repo_name=repo_name, account=account, token=token) 
            gh.run_command(["git", "checkout", "-b", "rmr_agent"])
            # Create PR
            pr_output = gh.run_command(["gh", "pr", "create", 
                            "--base", "main", # allow this base branch (main) to be configurable? 
                            "--head", "rmr_agent",
                            "--title", "Add notebooks and config files from RMR Agent",
                            "--body", pr_body_text,
                            "--json", "url"  # Returns JSON with just the URL
                            ])
            # Extract PR URL from the JSON output
            pr_url = extract_pr_url_from_json_output(pr_output)
        except subprocess.CalledProcessError as e:
            error_message = e.output.decode()
            print(f"Error creating PR: {error_message}")
            raise e
            

    print(f"✅ Pull Request created: {pr_url}")
    return pr_url



