import json

path = '/Users/gechunfa1/.openhands/settings.json'
with open(path, 'r') as f:
    data = json.load(f)

llm = data.get('agent_settings', {}).get('llm', {})

# Match Qwen3 32K context window
llm['max_input_tokens'] = 32000
llm['max_output_tokens'] = 32000
llm['timeout'] = 600

# Qwen does not support OpenAI reasoning_effort
llm['reasoning_effort'] = None

# Anthropic-only features, disable for Qwen
llm['enable_encrypted_reasoning'] = False
llm['extended_thinking_budget'] = None

# OpenAI-only features, disable for Qwen
llm['prompt_cache_retention'] = None
llm['caching_prompt'] = False

data['agent_settings']['llm'] = llm

# Reduce condenser max_size to fit 32K context better
condenser = data.get('agent_settings', {}).get('condenser', {})
condenser['max_size'] = 200
data['agent_settings']['condenser'] = condenser

with open(path, 'w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print('settings.json updated successfully!')
