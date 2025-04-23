
import os
import requests
import json
import time
import warnings
import contextlib
import requests
import litellm
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod
from urllib3.exceptions import InsecureRequestWarning
from typing import Dict, Any, Optional, List
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from dotenv import load_dotenv
load_dotenv() 



open_models = {
    "code-llama-7b" :  "https://aiplatform.dev51.cbf.dev.paypalinc.com/seldon/seldon/codellama-7b-in-3273d/v2/models/codellama-7b-in-3273d/infer", # 'https://aiplatform.dev51.cbf.dev.paypalinc.com/v1/chat/completions'
    "code-llama-13b" : "https://aiplatform.dev51.cbf.dev.paypalinc.com/seldon/seldon/code-llama-13b--5cd35/v2/models/code-llama-13b--5cd35/infer",
    "llama-13b-chat": "https://aiplatform.dev51.cbf.dev.paypalinc.com/seldon/seldon/llama-2-13b-cha-7b9ed/v2/models/llama-2-13b-cha-7b9ed/infer",
    "code-llama-34b" : "https://aiplatform.dev51.cbf.dev.paypalinc.com/seldon/seldon/code-llama-34b--31589/v2/models/code-llama-34b--31589/infer",
    "starcoderbase" : "https://aiplatform.dev51.cbf.dev.paypalinc.com/seldon/seldon/starcoder-e869f/v2/models/starcoder-e869f/infer",
    "mistral-7b": "https://aiplatform.dev51.cbf.dev.paypalinc.com/seldon/seldon/mistral-7b-inst-e0bc1/v2/models/mistral-7b-inst-e0bc1/infer",
    #"deepseek": "https://aiplatform.dev51.cbf.dev.paypalinc.com/seldon/seldon/deepseek-r1-dis-3ad7d/v2/models/deepseek-r1-dis-3ad7d/infer", # # DeepSeek-R1-Distill-Qwen-32B
    "deepseek/deepseek-reasoner": "https://aiplatform.dev52.cbf.dev.paypalinc.com/seldon/seldon/deepseek-r1-dis-9233d/v2/models/deepseek-r1-dis-9233d/infer", # DeepSeek-R1-Distill-Llama-70B
    "code-llama-13b-in" : "https://aiplatform.dev51.cbf.dev.paypalinc.com/seldon/seldon/codellama-13b-in-3273d/v2/models/codellama-13b-in-3273d/infer"
}



def messages_to_prompt(messages: list[dict[str, str]]) -> str:
    """Convert messages to a prompt string."""
    prompt_pieces = []
    
    for message in messages:
        role = message["role"]
        content = message["content"]
        
        if role == "system":
            prompt_pieces.append(f"System: {content}")
        elif role == "user":
            prompt_pieces.append(f"User: {content}")
        elif role == "assistant":
            prompt_pieces.append(f"Assistant: {content}")
            
    return "\n\n".join(prompt_pieces)

print("client_id:", os.getenv("AZURE_CLIENT_ID"))
print("client_secret starts with:", os.getenv("AZURE_CLIENT_SECRET")[:5])


class TokenManager:
    def __init__(self):
        self._token = None
        self._token_expiry = 0
        self.tenant_id = "fb007914-6020-4374-977e-21bac5f3f4c8"
        self.token_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"

    def get_token(self):
        if self._token and time.time() < self._token_expiry:
            return self._token

        data = {
            "client_id": os.getenv("AZURE_CLIENT_ID"),
            "client_secret": os.getenv("AZURE_CLIENT_SECRET"),
            "scope": "https://cognitiveservices.azure.com/.default",
            "grant_type": "client_credentials"
        }

        if not all(data.values()):
            missing = [k for k, v in data.items() if not v]
            raise EnvironmentError(f"Missing env vars: {', '.join(missing)}")

        res = requests.post(self.token_url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"}, verify=False)

        try:
            res.raise_for_status()
            token_data = res.json()
            self._token = token_data["access_token"]
            self._token_expiry = time.time() + token_data.get("expires_in", 3600)
            return self._token
        except Exception:
            raise RuntimeError(f"Failed to fetch token: {res.status_code} — {res.text}")



# single instance of token manager
token_manager = TokenManager()

old_merge_environment_settings = requests.Session.merge_environment_settings


@contextlib.contextmanager
def no_ssl_verification():
    opened_adapters = set()

    def merge_environment_settings(self, url, proxies, stream, verify, cert):
        # Verification happens only once per connection so we need to close
        # all the opened adapters once we're done. Otherwise, the effects of
        # verify=False persist beyond the end of this context manager.
        opened_adapters.add(self.get_adapter(url))
        settings = old_merge_environment_settings(self, url, proxies, stream, verify, cert)
        settings['verify'] = False
        return settings

    requests.Session.merge_environment_settings = merge_environment_settings

    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', InsecureRequestWarning)
            yield
    finally:
        requests.Session.merge_environment_settings = old_merge_environment_settings

        for adapter in opened_adapters:
            try:
                adapter.close()
            except:
                pass



class LLMHandler(ABC):
    @abstractmethod
    def create_payload(self, **kwargs) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    def extract_response(self, response: requests.Response, model_name: str, input_tokens: int) -> litellm.ModelResponse:
        pass


class OpenSourceLLMHandler(LLMHandler):
    @property
    def needs_prompt_conversion(self) -> bool:
        return True
    
    def create_payload(self, **kwargs) -> Dict[str, Any]:
        prompt = kwargs.get('prompt', '')
        if not prompt:
            raise ValueError('Need to provide prompt to create payload for open source LLM')
        return {
            "inputs": [{
                "name": "input",
                "shape": [1],
                "datatype": "str",
                "data": [prompt]
            }],
            "parameters": {
                "extra": {
                    "max_new_tokens": kwargs.get('max_tokens', 2048),
                    "temperature": kwargs.get('temperature', 0.0),
                    "repetition_penalty": kwargs.get('repetition_penalty', 0.0),
                    "top_p": kwargs.get('top_p', 0.3)
                }
            }
        }
    
    def create_headers(self):
        return {
            'Content-Type': 'application/json',
        }
    
    def create_params(self):
        return {}
    
    def extract_response(self, response: requests.Response,  model_name: str, input_tokens: int) -> litellm.ModelResponse:
        response_text = response.json()['outputs'][0]['data'][0]
        
        # Calculate usage stats
        completion_tokens = litellm.utils.token_counter(text=response_text, model=model_name)
        
        return litellm.utils.ModelResponse(
            id="local-" + str(response.headers.get('X-Request-ID', '')),
            choices=[{
                "finish_reason": "stop",
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response_text
                }
            }],
            created=int(time.time()),
            model=model_name,
            usage={
                "prompt_tokens": input_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": input_tokens + completion_tokens
            }
        )

class AzureGPTHandler(LLMHandler):
    @property
    def needs_prompt_conversion(self) -> bool:
        return False
    
    def create_payload(self, prompt: str = "", messages: list = None, **kwargs) -> Dict[str, Any]:
        if not messages:
            raise ValueError('Need to provide messages to create payload for Azure GPT')
        
        payload = {
            "messages": messages,
            # "model": "gpt-4",  # may be configurable - for now hard coding to gpt-4o
            "temperature": kwargs.get('temperature', 0.0),  
            "max_tokens": kwargs.get('max_tokens', 2048),  
            "top_p": kwargs.get('top_p', 0.3),  
            "frequency_penalty": kwargs.get('frequency_penalty', 0),  
            "presence_penalty": kwargs.get('presence_penalty', 0),  

        }
        return payload 
    
    def create_headers(self):
        token = token_manager.get_token()
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
            'Cookie': 'ApplicationGatewayAffinity=5782715754db1293aaa82867cac4107a; ApplicationGatewayAffinityCORS=5782715754db1293aaa82867cac4107a'
        }
        return headers
    
    def create_params(self):
        params = {
            "api-version": "2024-02-15-preview" # hard coding for gpt-4o for now
        }
        return params
    
    
    def extract_response(self, response: requests.Response, model_name: str, input_tokens: int) -> litellm.ModelResponse:
        response_json = response.json()
        # response_text = response_json["generated_text"]
        response_text = response_json["choices"][0]["message"]["content"]
        
        # Calculate usage stats
        if response_json.get('usage', {}):
            prompt_tokens = response_json['usage']['prompt_tokens']
            completion_tokens = response_json['usage']['completion_tokens']
            total_tokens = response_json['usage']['total_tokens']
        else:
            prompt_tokens = input_tokens
            completion_tokens = litellm.utils.token_counter(text=response_text, model=model_name)
            total_tokens = input_tokens + completion_tokens
        
        return litellm.utils.ModelResponse(
            id=f"gpt-{int(time.time())}", # GPT might have its own ID format
            choices=[{
                "finish_reason": "stop",
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response_text
                }
            }],
            created=int(time.time()),
            model=model_name,
            usage={
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens
            }
        )


class LLMClient:
    def __init__(self, model_name: str):
        self.model_name = model_name

        open_url = open_models.get(model_name, "")
        if open_url:
            self.handler = OpenSourceLLMHandler()
            self.url = open_url
        else:
            self.handler = AzureGPTHandler()
            self.url = "https://genai-wus2-tdz01.paypalcorp.com/brebot/openai/deployments/gpt-4o/chat/completions"  # "http://10.183.170.134:8001/api/llm/" # "http://10.183.170.134:8001/api/llm/" # codepal LLM endpoint  # "http://host.docker.internal:8001/api/llm/"
    
    def call_llm(self, 
                 prompt: str = "",
                 messages: List[Dict[str, str]] = [],
                 input_tokens: int = 0,
                 **kwargs) -> litellm.types.utils.ModelResponse:
        
        if not prompt and not messages:
            raise ValueError("Please provide either a single prompt string or list of messages")
        elif prompt and messages:
            raise ValueError("Please provide either a prompt string or a list of messages, not both")

        if prompt:
            messages = [
                {"role": "user", "content": prompt}
            ]

        if self.handler.needs_prompt_conversion:
            kwargs['prompt'] = messages_to_prompt(messages) if not prompt else prompt
        else:
            kwargs['messages'] = messages

        if input_tokens == 0:
            input_tokens: int = litellm.utils.token_counter(messages=messages, model=self.model_name) # defaults to tiktoken general token counter if that model name does not match
            
        # Create request components
        payload = self.handler.create_payload(**kwargs)
        headers = self.handler.create_headers()
        params = self.handler.create_params()
        
        # Call LLM without SSL verification
        with no_ssl_verification():
            session = requests.Session()
            response = session.post(self.url, json=payload, params=params, headers=headers)
            #response = requests.post(self.url, json=payload, params=params, headers=headers, verify=False)
            
        if response.status_code != 200:
            raise Exception(f'Failed to send POST request. Status code: {response.status_code}, Response text: {response.text}')
            
        return self.handler.extract_response(response, self.model_name, input_tokens)
    


if __name__ == "__main__":
    #model_name = "deepseek"
    #model_name = "gpt-4-turbo"
    model_name = "gpt-4o"

    def _history_to_messages(history):
        def get_role(history_item) -> str:
            #if history_item["role"] == "system":
            #    return "user" if self.args.convert_system_to_user else "system"
            return history_item["role"]

        messages = []
        for history_item in history:
            role = get_role(history_item)
            if role == "tool":
                messages.append(
                    {
                        "role": role,
                        "content": history_item["content"],
                        # Only one tool call per observations
                        "tool_call_id": history_item["tool_call_ids"][0],  # type: ignore
                    }
                )
            elif "tool_calls" in history_item:
                messages.append(
                    {"role": role, "content": history_item["content"], "tool_calls": history_item["tool_calls"]}
                )
            else:
                messages.append({"role": role, "content": history_item["content"]})
        return messages

    history = [
        {
            "message_type": "system_prompt",
            "role": "system",
            "content": "SETTING: You are an autonomous programmer, ...",
            "agent": "primary"
        },
        {
            "message_type": "observation",
            "role": "user",
            "content": "How to list files? \nbash-$",
            "agent": "primary"
        },
        ]
    
    messages = _history_to_messages(history)
    print(messages_to_prompt(messages))

    input_tokens: int = litellm.utils.token_counter(messages=messages, model=model_name) # defaults to tiktoken general token counter if that model name does not match
    print("input tokens:", input_tokens)
    #exit()

    llm_client = LLMClient(model_name=model_name)
    response = llm_client.call_llm(
        #messages=messages,
        prompt="hello",
        max_tokens=100,
        temperature=0.7,
        repetition_penalty=1.0,
        top_p=0.3,
        input_tokens=input_tokens
    )
    print(response)
    choices: litellm.types.utils.Choices = response.choices
    response_text = choices[0].message.content or ""
    print(response_text)
