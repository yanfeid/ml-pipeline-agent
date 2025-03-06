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
    pattern = r"(?:https?://)?(?:www\.)?github\.(?:[\w.]+)/([^/]+)/([^/]+?)(?:\.git)?/?$"
    match = re.match(pattern, url)
    
    if match:
        owner, repo = match.groups()
        return owner, repo
    
    # Second attempt: use URL parsing
    try:
        # Split the path and remove empty strings
        path_parts = [p for p in urlparse(url).path.split('/') if p]
        
        if len(path_parts) >= 2:
            owner = path_parts[-2]
            repo = path_parts[-1].replace('.git', '')
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
            return error_message

    # Context Manager -----------------------------------------------
    def __enter__(self):
        # anything to init here?
        logging.info("enter github context")
        return self

    def __exit__(self, _type, _value, _tb):
        # anything to clean up here?
        logging.info("exit github context")

    # /Context Manager ----------------------------------------------

'''
if __name__ == '__main__':
    with GitHub("GenAI-DE", "datasets", "<your_account_or_sa>", "<your_encrypted_pat>") as gh:
         gh.run_command(["git", "switch", "auto-update-embeddings"])

    # or init this way
    # gh = GitHub("GenAI-DE", "datasets", "<your_account_or_sa>", "<your_encrypted_pat>")
'''


def clone_repo(github_url: str, local_base_dir: str = "repos") -> str:
    """Clone a GitHub repo and checkout a new branch 'rmr_agent'.
    
    Args:
        github_url: The GitHub repository URL.
        local_base_dir: Base directory to store cloned repos.
    
    Returns:
        str: local_repo_path
    """
    # extract repo owner and repo name from url
    repo_owner, repo_name = parse_github_url(github_url)

    # extract github token from environment variables
    token = get_github_token()

    local_repo_path = os.path.join(local_base_dir, repo_name)
    
    if os.path.exists(local_repo_path):
        shutil.rmtree(local_repo_path)

    # clone repo to local directory. This also authenticates with git and safely caches credentials for 24H
    print(f"Changing working directory to {local_base_dir} to clone the repo")
    with temporary_working_directory(local_base_dir):
        gh = GitHub(repo_owner=repo_owner, repo_name=repo_name, account='matjacobs', token=token) # hard coding to my username and PAT for now
        gh.run_command(["git", "checkout", "-b", "rmr_agent"])
    print(f"Changing working directory back to {os.getcwd()}")
    
    return local_repo_path


