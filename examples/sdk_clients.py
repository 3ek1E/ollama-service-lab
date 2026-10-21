"""Optional SDK examples: pip install ollama openai anthropic

All three SDKs target our own Ollama gateway, not paid cloud inference.
"""
import os

base = os.environ.get('SERVICE_BASE_URL', 'http://127.0.0.1:8088').rstrip('/')
key = os.environ['SERVICE_API_KEY']
model = os.environ.get('OLLAMA_MODEL', 'qwen3.5:0.8b')
messages = [{'role': 'user', 'content': '用一句中文介绍自己。'}]

if __name__ == '__main__':
    import ollama
    from openai import OpenAI
    from anthropic import Anthropic

    native = ollama.Client(host=base, headers={'Authorization': f'Bearer {key}'})
    print(native.chat(model=model, messages=messages, think=False).message.content)

    openai = OpenAI(base_url=base+'/v1', api_key=key)
    print(openai.chat.completions.create(model=model, messages=messages, reasoning_effort='none').choices[0].message.content)
    print(openai.responses.create(model=model, input='用一句中文介绍自己。', extra_body={'think': False}).output_text)

    anthropic = Anthropic(base_url=base, api_key=key)
    response = anthropic.messages.create(model=model, max_tokens=128, messages=messages, thinking={'type': 'disabled'})
    print(''.join(block.text for block in response.content if block.type == 'text'))
