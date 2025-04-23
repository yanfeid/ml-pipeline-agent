import requests

def call_codepal_gpt(prompt, model="gpt-4o", temperature=0, max_tokens=1024, 
                #  frequency_penalty=0, presence_penalty=0, base_url="http://10.183.170.134:8001/api/llm/"):
                frequency_penalty=0, presence_penalty=0, base_url="http://10.183.170.134:8001/api/llm/"):
    headers = {
        "Content-Type": "application/json"
    }
    
    payload = {
        "inputs": prompt,
        "model": model,
        "model_kwargs": {
            "temperature": temperature,
            "max_tokens": max_tokens,
            "frequency_penalty": frequency_penalty,
            "presence_penalty": presence_penalty
        }
    }
    
    try:
        response = requests.post(base_url, headers=headers, json=payload)
        response.raise_for_status()  # Raise an exception for bad status codes
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error making API request: {e}")
        return None
