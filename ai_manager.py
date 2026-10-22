import json
import os
import requests
from typing import Optional, List, Dict, Any, Generator

# API keys are stored in the OS keyring, never in the plaintext settings file.
_AI_KEYRING_SERVICE = "NorthStar.AIProvider"

try:
    import keyring as _keyring
    _KEYRING_OK = True
except Exception:
    _keyring = None
    _KEYRING_OK = False


def _secret_set(provider: str, key: str, value: str) -> None:
    if not _KEYRING_OK or not value:
        return
    try:
        _keyring.set_password(_AI_KEYRING_SERVICE, f"{provider}.{key}", value)
    except Exception:
        pass


def _secret_get(provider: str, key: str) -> str:
    if not _KEYRING_OK:
        return ""
    try:
        return _keyring.get_password(_AI_KEYRING_SERVICE, f"{provider}.{key}") or ""
    except Exception:
        return ""

class AIProvider:
    """Base interface for AI providers."""
    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def generate_stream(self, prompt: str, system: str = "", context: str = "", options: Dict[str, Any] = None) -> Generator[str, None, None]:
        """Generate a streaming response. Should yield tokens."""
        raise NotImplementedError

    def get_name(self) -> str:
        raise NotImplementedError

class OllamaProvider(AIProvider):
    def get_name(self) -> str:
        return "Ollama"

    def generate_stream(self, prompt: str, system: str = "", context: str = "", options: Dict[str, Any] = None) -> Generator[str, None, None]:
        url = self.config.get("url", "http://localhost:11434/api/generate")
        model = self.config.get("model", "gemma2:2b")
        
        full_prompt = f"{context}\n\nUser: {prompt}" if context else prompt
        
        payload = {
            "model": model,
            "prompt": full_prompt,
            "system": system,
            "stream": True,
            "options": options or {"num_predict": 512, "temperature": 0.6}
        }
        
        try:
            resp = requests.post(url, json=payload, stream=True, timeout=30)
            resp.raise_for_status()
            for line in resp.iter_lines():
                if line:
                    data = json.loads(line.decode())
                    token = data.get("response", "")
                    if token:
                        yield token
                    if data.get("done"):
                        break
        except Exception as e:
            yield f"Error: {str(e)}"

class OpenAICompatibleProvider(AIProvider):
    """Base for OpenAI, Groq, and other compatible APIs."""
    def get_name(self) -> str:
        return self.config.get("provider_name", "OpenAI-Compatible")

    def generate_stream(self, prompt: str, system: str = "", context: str = "", options: Dict[str, Any] = None) -> Generator[str, None, None]:
        url = self.config.get("url")
        api_key = self.config.get("api_key")
        model = self.config.get("model")
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        if context:
            messages.append({"role": "user", "content": f"Context: {context}"})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": model,
            "messages": messages,
            "stream": True
        }
        if options:
            payload.update(options)

        try:
            resp = requests.post(url, json=payload, headers=headers, stream=True, timeout=30)
            resp.raise_for_status()
            for line in resp.iter_lines():
                if line:
                    line_str = line.decode('utf-8')
                    if line_str.startswith("data: "):
                        data_content = line_str[6:]
                        if data_content.strip() == "[DONE]":
                            break
                        try:
                            data = json.loads(data_content)
                            token = data['choices'][0]['delta'].get('content', '')
                            if token:
                                yield token
                        except (json.JSONDecodeError, ValueError):
                            continue
        except Exception as e:
            yield f"Error: {str(e)}"

class AIManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AIManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized: return
        self.config_file = os.path.join(self._get_data_dir(), "leo_ai_config.json")
        self.settings = self._load_settings()
        self.providers = {
            "Ollama": OllamaProvider,
            "OpenAI": OpenAICompatibleProvider,
            "Groq": OpenAICompatibleProvider,
            "Custom": OpenAICompatibleProvider
        }
        self.current_provider_name = self.settings.get("current_provider", "Ollama")
        self._initialized = True

    def _get_data_dir(self) -> str:
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        d = os.path.join(base, "NorthStar")
        os.makedirs(d, exist_ok=True)
        return d

    def _load_settings(self) -> Dict[str, Any]:
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r") as f:
                    data = json.load(f)
                # Pull secrets from the OS keyring (never stored in plaintext JSON)
                for name, cfg in data.get("providers", {}).items():
                    if isinstance(cfg, dict) and "api_key" in cfg:
                        cfg["api_key"] = _secret_get(name, "api_key")
                return data
            except:
                pass
        return {
            "current_provider": "Ollama",
            "providers": {
                "Ollama": {"url": "http://localhost:11434/api/generate", "model": "gemma2:2b"},
                "OpenAI": {"url": "https://api.openai.com/v1/chat/completions", "model": "gpt-3.5-turbo", "api_key": ""},
                "Groq": {"url": "https://api.groq.com/openai/v1/chat/completions", "model": "llama3-8b-8192", "api_key": ""},
                "Custom": {"url": "", "model": "", "api_key": ""}
            }
        }

    def save_settings(self):
        # Persist keys to the OS keyring and strip them from the on-disk copy
        for name, cfg in self.settings.get("providers", {}).items():
            if isinstance(cfg, dict) and cfg.get("api_key"):
                _secret_set(name, "api_key", cfg["api_key"])
        safe = {
            k: {
                kk: vv for kk, vv in v.items() if kk != "api_key"
            } if isinstance(v, dict) else v
            for k, v in self.settings.items()
        }
        with open(self.config_file, "w") as f:
            json.dump(safe, f, indent=2)

    def get_current_provider(self) -> AIProvider:
        p_name = self.settings.get("current_provider", "Ollama")
        p_config = self.settings["providers"].get(p_name, {})
        p_config["provider_name"] = p_name
        return self.providers[p_name](p_config)

    def set_provider(self, name: str):
        if name in self.providers:
            self.settings["current_provider"] = name
            self.save_settings()

    def update_provider_config(self, name: str, config: Dict[str, Any]):
        if name in self.settings["providers"]:
            self.settings["providers"][name].update(config)
            self.save_settings()

    def get_all_providers(self) -> List[str]:
        return list(self.providers.keys())

    def get_provider_config(self, name: str) -> Dict[str, Any]:
        return self.settings["providers"].get(name, {})

    def get_ollama_models(self) -> List[str]:
        """Fetch available models from local Ollama instance."""
        try:
            url = self.settings["providers"].get("Ollama", {}).get("url", "http://localhost:11434/api/generate")
            # Convert generate URL to tags URL
            base_url = url.split("/api/")[0]
            tags_url = f"{base_url}/api/tags"
            resp = requests.get(tags_url, timeout=5)
            resp.raise_for_status()
            models = resp.json().get("models", [])
            return [m["name"] for m in models]
        except Exception as e:
            print(f"Error fetching Ollama models: {e}")
            return []
