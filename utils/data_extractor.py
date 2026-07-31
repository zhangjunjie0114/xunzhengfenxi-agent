"""
数据提取模块 - 基于LLM从文献中提取结构化数据
"""
import json
import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)


def load_template(template_path: str) -> list:
    """加载提取模板"""
    import os
    if not os.path.exists(template_path):
        logger.warning(f"模板文件不存在: {template_path}")
        return _default_template()
    with open(template_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def format_template_prompt(template: list) -> str:
    """将模板格式化为LLM提示词"""
    lines = ["请按以下字段从文献中提取数据，以JSON格式返回："]
    for field in template:
        req = "【必填】" if field.get("required") else "【选填】"
        lines.append(f"  - {field['label']} ({field['field_name']}) {req}: {field['description']}")
    lines.append("")
    lines.append("请严格返回以下JSON格式（不要包含其他文字）：")
    lines.append("```json")
    lines.append("{")
    field_names = [f'    "{f["field_name"]}": ""' for f in template]
    lines.append(",\n".join(field_names))
    lines.append("}")
    lines.append("```")
    lines.append("注意：")
    lines.append("1. 如果某字段在原文中找不到信息，请填 '未报告'")
    lines.append("2. 每个字段的值应简洁准确，直接引用原文")
    lines.append("3. 不要编造数据，不确定的填 '不清楚'")
    return "\n".join(lines)


def extract_from_single_paper(text: str, template: list,
                              call_llm_func: Callable,
                              paper_title: str = "",
                              max_chars: int = 120000) -> dict:
    """提取单篇文献的数据

    Args:
        text: 文献全文
        template: 提取模板
        call_llm_func: LLM调用函数
        paper_title: 文献标题
        max_chars: 截断阈值，默认120000字符
    """
    field_prompt = format_template_prompt(template)

    # 截断文本防止超出上下文窗口限制
    if len(text) > max_chars:
        half = max_chars // 2
        text = text[:half] + "\n\n[中间内容省略...]\n\n" + text[-half:]

    system_prompt = """你是一位护理研究领域的文献数据提取专家。你的任务是从给定的文献全文中提取结构化数据。

绝对规则：
1. 严格只提取文献中明确陈述的信息，不要推断或编造
2. 必须返回纯JSON对象，不要任何其他文字、说明或markdown
3. 不要使用```json```包裹，直接返回 { 开头
4. 对于数值数据务必精确提取
5. 如果某字段在原文中找不到，填"未报告"
6. 字段名必须与用户指定的完全一致

输出示例: {"author_year": "Zhang, 2023", "title": "..."}"""

    user_content = f"以下是文献全文，请提取指定字段的数据。\n\n{field_prompt}\n\n---文献全文---\n\n{text}"
    response = call_llm_func(system_prompt, user_content)

    result = _parse_json_response(response)
    result["_source_paper"] = paper_title
    result["_raw_response"] = response if not result else ""
    return result


def extract_from_papers(papers: list, template_source,
                        call_llm_func: Callable,
                        progress_callback: Optional[Callable] = None,
                        max_retries: int = 2) -> list:
    """批量提取多篇文献数据"""
    if isinstance(template_source, str):
        template = load_template(template_source)
    else:
        template = template_source
    results = []
    total = len(papers)

    for idx, paper in enumerate(papers):
        title = paper.get("title") or paper.get("file_name", f"文献{idx+1}")
        text = paper.get("text", "")

        if progress_callback:
            progress_callback(idx + 1, total, f"正在提取: {title[:30]}...")

        if not text:
            results.append({
                "paper": title, "_source_paper": title,
                "error": "文献文本为空，无法提取"
            })
            continue

        last_error = ""
        for attempt in range(max_retries + 1):
            try:
                result = extract_from_single_paper(text, template, call_llm_func, title)
                result["paper"] = title
                result["file_name"] = paper.get("file_name", "")
                if "error" not in result:
                    results.append(result)
                    break
                else:
                    last_error = result["error"]
            except Exception as e:
                last_error = str(e)
                logger.warning(f"提取失败 (尝试{attempt+1}): {title} - {e}")
                if attempt < max_retries:
                    continue

        if last_error:
            results.append({
                "paper": title, "_source_paper": title,
                "error": f"提取失败: {last_error}"
            })

    return results


def _parse_json_response(response: str) -> dict:
    """从LLM回复中解析JSON（多策略健壮解析）"""
    import re, json

    if not response or not response.strip():
        return {"error": "AI返回为空", "raw": ""}

    # 如果返回明显是错误信息，直接返回
    if response.strip().startswith("【"):
        return {"error": response.strip()[:200], "raw": response[:500]}

    # 策略1: 提取 ```json ... ``` 或 ``` ... ``` 块
    code_block = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', response, re.DOTALL)
    if code_block:
        json_str = code_block.group(1).strip()
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass

    # 策略2: 尝试直接解析整个响应
    try:
        return json.loads(response.strip())
    except json.JSONDecodeError:
        pass

    # 策略3: 提取最外层 {...} 结构（查找第一个{到最后一个}）
    brace_start = response.find('{')
    brace_end = response.rfind('}')
    if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
        try:
            return json.loads(response[brace_start:brace_end+1])
        except json.JSONDecodeError:
            pass

    # 策略4: 尝试修复常见JSON格式错误
    fixed = response.strip()
    fixed = re.sub(r"'([^']+)'", r'"\1"', fixed)  # 单引号转双引号
    fixed = re.sub(r',(\s*[}\]])', r'\1', fixed)   # 移除多余的逗号
    brace_start2 = fixed.find('{')
    brace_end2 = fixed.rfind('}')
    if brace_start2 != -1 and brace_end2 != -1 and brace_end2 > brace_start2:
        try:
            return json.loads(fixed[brace_start2:brace_end2+1])
        except json.JSONDecodeError:
            pass

    raw_preview = response[:300]
    return {"error": f"无法解析AI返回的JSON格式。原始回复: {raw_preview}", "raw": response[:500]}


def _default_template() -> list:
    """默认模板"""
    return [
        {"field_name": "author_year", "label": "作者/年份", "required": True, "type": "text",
         "description": "第一作者+年份"},
        {"field_name": "title", "label": "文献标题", "required": True, "type": "text",
         "description": "完整标题"},
        {"field_name": "study_design", "label": "研究设计类型", "required": True, "type": "text",
         "description": "RCT/横断面/质性研究等"},
        {"field_name": "sample_size", "label": "样本量", "required": True, "type": "text",
         "description": "总样本量"},
        {"field_name": "population", "label": "研究对象", "required": True, "type": "text",
         "description": "人群描述"},
        {"field_name": "intervention", "label": "干预措施", "required": False, "type": "text",
         "description": "干预组措施"},
        {"field_name": "outcome_measures", "label": "主要的结局", "required": True, "type": "text",
         "description": "结局指标（如：焦虑水平、生活质量、血压值）"},
        {"field_name": "measurement_tools", "label": "测量工具/量表", "required": True, "type": "text",
         "description": "测量工具名称及信效度（如：SAS焦虑量表、SF-36）"},
        {"field_name": "main_findings", "label": "主要研究发现", "required": True, "type": "text",
         "description": "主要结果"},
        {"field_name": "conclusion", "label": "作者结论", "required": False, "type": "text",
         "description": "结论"},
    ]


def results_to_dataframe(results: list, template: list):
    """将提取结果转换为pandas DataFrame"""
    import pandas as pd
    rows = []
    field_names = [f["field_name"] for f in template]
    field_labels = [f["label"] for f in template]

    for r in results:
        if "error" in r:
            row = {"文献": r.get("paper", "未知"), "状态": "❌ " + r["error"]}
            for fn, fl in zip(field_names, field_labels):
                row[fl] = ""
            rows.append(row)
            continue

        row = {"文献": r.get("paper", "未知"), "状态": "✅"}
        for fn, fl in zip(field_names, field_labels):
            val = r.get(fn, "")
            if isinstance(val, list):
                val = "; ".join(str(v) for v in val)
            row[fl] = str(val) if val else ""
        rows.append(row)

    return pd.DataFrame(rows)


def dataframe_to_results(edited_df, template, original_results: list) -> list:
    """将用户编辑后的DataFrame转换回提取结果列表(list[dict])

    自动检测修改过的行并设置 _student_modified 标记。
    是 results_to_dataframe() 的逆向操作。

    Args:
        edited_df: 用户编辑后的DataFrame (中文label列)
        template: 提取模板 (list[dict] 含 field_name, label)
        original_results: 原始提取结果，用于保留元数据字段

    Returns:
        list[dict]: 更新后的提取结果列表
    """
    import pandas as pd

    # 构建 label → field_name 映射
    field_map = {f["label"]: f["field_name"] for f in template}
    updated_results = []

    for idx, (_, row) in enumerate(edited_df.iterrows()):
        paper_label = str(row.get("文献", ""))
        status_val = str(row.get("状态", ""))

        # 错误行原样保留
        if "❌" in status_val:
            if idx < len(original_results) and "error" in original_results[idx]:
                updated_results.append(dict(original_results[idx]))
            else:
                updated_results.append({"paper": paper_label, "error": status_val})
            continue

        result = {}
        is_modified = False

        # 继承元数据（DataFrame中没有的字段）
        if idx < len(original_results):
            orig = original_results[idx]
            for meta_key in ["paper", "file_name", "_source_paper", "_raw_response"]:
                if meta_key in orig:
                    result[meta_key] = orig[meta_key]
            if orig.get("_student_modified"):
                is_modified = True

        if "paper" not in result:
            result["paper"] = paper_label

        # 映射数据列：label → field_name
        for chinese_label, field_name in field_map.items():
            if chinese_label in edited_df.columns:
                cell_value = row.get(chinese_label, "")
                if pd.isna(cell_value):
                    cell_value = ""
                else:
                    cell_value = str(cell_value)
                result[field_name] = cell_value

                # 检测修改
                if not is_modified and idx < len(original_results):
                    orig_value = original_results[idx].get(field_name, "")
                    if str(cell_value) != str(orig_value):
                        is_modified = True

        if is_modified:
            result["_student_modified"] = True

        updated_results.append(result)

    return updated_results
