"""
LLM调用封装模块 - 统一接口，支持多种Provider
"""
import json
import logging

logger = logging.getLogger(__name__)


def call_llm(system_prompt: str, user_content: str, **kwargs) -> str:
    """统一的LLM调用接口
    
    从 streamlit.session_state 读取配置，支持四种 Provider。
    也可直接传入参数覆盖 session_state 中的配置。
    
    Args:
        system_prompt: 系统提示词
        user_content: 用户消息内容
        **kwargs: 可覆盖的配置参数: provider, api_key, model, api_base
    
    Returns:
        str: 模型回复内容
    """
    import streamlit as st
    
    # 读取配置（优先使用kwargs，其次 session_state），最后用默认值
    provider = kwargs.get("provider") or st.session_state.get("provider", "Claude (Anthropic)")
    api_key = kwargs.get("api_key") or st.session_state.get("api_key", "")
    model = kwargs.get("model") or st.session_state.get("model", "claude-sonnet-4-20250514")
    api_base = kwargs.get("api_base") or st.session_state.get("api_base", "")
    
    if not api_key and "Ollama" not in provider:
        return "【错误】未配置 API Key，请在左侧边栏的配置面板中输入。"
    
    try:
        if "Claude" in provider:
            return _call_claude(system_prompt, user_content, api_key, model)
        elif "OpenAI" in provider:
            return _call_openai(system_prompt, user_content, api_key, model)
        elif "DeepSeek" in provider or "第三方" in provider:
            return _call_openai(system_prompt, user_content, api_key, model, api_base)
        elif "Ollama" in provider:
            return _call_ollama(system_prompt, user_content, model)
        else:
            return f"【错误】不支持的 Provider: {provider}"
    except Exception as e:
        error_msg = str(e)
        logger.error(f"LLM调用失败: {error_msg}")
        return f"【API调用失败】{error_msg}\n\n请检查 API Key 是否正确、网络是否通畅。"


def test_connection(provider: str, api_key: str, model: str, api_base: str = "") -> tuple:
    """测试与LLM API的连接
    
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        test_prompt = "请回复'连接成功'四个字，不要有其他内容。"
        if "Ollama" in provider:
            response = _call_ollama("", test_prompt, model)
        elif "Claude" in provider:
            response = _call_claude("", test_prompt, api_key, model)
        elif "DeepSeek" in provider:
            response = _call_openai("", test_prompt, api_key, model, api_base)
        else:
            response = _call_openai("", test_prompt, api_key, model, api_base)
        
        if "连接成功" in response:
            return (True, f"✅ 连接成功！使用模型: {model}")
        else:
            return (True, f"✅ 连接成功（返回: {response[:50]}）")
    except Exception as e:
        return (False, f"❌ 连接失败: {str(e)}")


def _call_claude(system_prompt: str, user_content: str, api_key: str, model: str) -> str:
    """调用 Claude (Anthropic) API"""
    import anthropic
    
    client = anthropic.Anthropic(api_key=api_key)
    
    messages = [{"role": "user", "content": user_content}]
    kwargs = {"model": model, "max_tokens": 8192, "messages": messages}
    if system_prompt:
        kwargs["system"] = system_prompt
    
    response = client.messages.create(**kwargs)
    return response.content[0].text


def _call_openai(system_prompt: str, user_content: str, api_key: str, model: str, 
                 base_url: str = "https://api.openai.com/v1") -> str:
    """调用 OpenAI 兼容格式的 API"""
    from openai import OpenAI
    
    client = OpenAI(api_key=api_key, base_url=base_url)
    
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_content})
    
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=8192
    )
    return response.choices[0].message.content


def _call_ollama(system_prompt: str, user_content: str, model: str) -> str:
    """调用本地 Ollama 模型"""
    import requests
    
    prompt = user_content
    if system_prompt:
        prompt = f"{system_prompt}\n\n{user_content}"
    
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False
        },
        timeout=120
    )
    response.raise_for_status()
    return response.json()["response"]


# Provider 配置映射
PROVIDER_MODELS = {
    "Claude (Anthropic) - 推荐": [
        "claude-sonnet-4-20250514",
        "claude-haiku-4-5-20251001",
        "claude-opus-4-20250514"
    ],
    "OpenAI (GPT)": [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-o3-mini"
    ],
    "DeepSeek V4 (本地代理)": [
        "deepseek-v4-flash",
        "deepseek-chat"
    ],
    "兼容OpenAI格式的第三方": [
        "deepseek-chat",
        "deepseek-reasoner",
        "qwen-max",
        "qwen-plus"
    ],
    "Ollama (本地模型，免费)": [
        "qwen2.5:14b",
        "qwen2.5:7b",
        "llama3.1:8b",
        "mistral:7b"
    ]
}

DEFAULT_MODELS = {
    "DeepSeek V4 (本地代理)": "deepseek-v4-flash",
    "Claude (Anthropic) - 推荐": "claude-sonnet-4-20250514",
    "OpenAI (GPT)": "gpt-4o",
    "兼容OpenAI格式的第三方": "deepseek-chat",
    "Ollama (本地模型，免费)": "qwen2.5:14b"
}
