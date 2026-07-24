"""
质量评价模块 - Risk of Bias 评估与可视化
"""
import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Cochrane 偏倚风险评价维度（针对RCT）
COCHRANE_DOMAINS = [
    "随机序列生成 (Random sequence generation)",
    "分配隐藏 (Allocation concealment)",
    "盲法 (Blinding of participants and personnel)",
    "结果数据的完整性 (Incomplete outcome data)",
    "选择性报告 (Selective reporting)",
    "其他偏倚 (Other bias)"
]

# 非RCT研究的评价维度
NON_RCT_DOMAINS = [
    "研究对象选择 (Selection of participants)",
    "混杂因素控制 (Confounding factors)",
    "暴露/干预测量 (Exposure/intervention measurement)",
    "结局评估 (Outcome assessment)",
    "随访完整性 (Completeness of follow-up)",
    "报告偏倚 (Reporting bias)"
]


def assess_rob(papers: list, call_llm_func: Callable,
               progress_callback: Optional[Callable] = None) -> list:
    """对文献进行质量评价

    Args:
        papers: 文献列表，每篇包含 { "title", "text", "study_design", "file_name" }
        call_llm_func: LLM调用函数
        progress_callback: 进度回调

    Returns:
        list: 每篇文献的评价结果
    """
    results = []
    total = len(papers)

    for idx, paper in enumerate(papers):
        title = paper.get("title") or paper.get("file_name", f"文献{idx+1}")
        design = paper.get("study_design", "")
        text = paper.get("text", "")

        if progress_callback:
            progress_callback(idx + 1, total, f"正在评价: {title[:30]}...")

        # 根据研究设计选择评价维度
        is_rct = "RCT" in design or "随机" in design or "randomized" in design.lower()
        domains = COCHRANE_DOMAINS if is_rct else NON_RCT_DOMAINS

        result = _assess_single_paper(text, title, domains, call_llm_func)
        result["study_design"] = design
        result["is_rct"] = is_rct
        results.append(result)

    return results


def _assess_single_paper(text: str, title: str, domains: list,
                         call_llm_func: Callable) -> dict:
    """评价单篇文献的质量"""
    max_chars = 40000
    if len(text) > max_chars:
        half = max_chars // 2
        text = text[:half] + "\n\n[中间省略...]\n\n" + text[-half:]

    system_prompt = """你是一位护理研究领域的质量评价专家。请对给定的文献进行偏倚风险(Risk of Bias)评价。

对每个维度，请判断为以下之一：
- "low" (低风险 - 方法学正确)
- "high" (高风险 - 方法学存在明显缺陷)
- "unclear" (不清楚 - 信息不足无法判断)

请返回JSON格式：{
    "overall": "low/high/unclear",
    "domains": {
        "维度名称": {"judgment": "low/high/unclear", "evidence": "判断依据（引用原文）"}
    }
}

请确保每个判断都有明确的原文依据。"""

    domain_text = "\n".join([f"{i+1}. {d}" for i, d in enumerate(domains)])
    user_content = f"请评价以下文献的偏倚风险。\n\n评价维度：\n{domain_text}\n\n---文献内容---\n\n{text[:30000]}"

    try:
        response = call_llm_func(system_prompt, user_content)
        result = _parse_rob_response(response)
        result["paper_title"] = title
        return result
    except Exception as e:
        logger.error(f"质量评价失败: {title} - {e}")
        return {
            "paper_title": title,
            "overall": "unclear",
            "domains": {},
            "error": str(e)
        }


def _parse_rob_response(response: str) -> dict:
    """解析质量评价的JSON响应"""
    import json, re
    code_block = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', response, re.DOTALL)
    if code_block:
        json_str = code_block.group(1).strip()
    else:
        json_str = response.strip()

    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        pass

    brace_match = re.search(r'\{.*\}', json_str, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group())
        except:
            pass

    return {"overall": "unclear", "domains": {}, "error": "无法解析评价结果"}


def generate_rob_chart(rob_results: list) -> object:
    """生成Cochrane风格偏倚风险图

    Args:
        rob_results: 质量评价结果列表

    Returns:
        plotly.figure: 偏倚风险总结图
    """
    import plotly.graph_objects as go
    import plotly.express as px

    # 颜色映射
    color_map = {"low": "#4CAF50", "high": "#F44336", "unclear": "#FFC107"}

    # 整理数据结构
    papers = []
    all_domains = set()
    paper_domains = {}

    for r in rob_results:
        pname = r.get("paper_title", "未知文献")[:30]
        papers.append(pname)
        domains_data = r.get("domains", {})
        paper_domains[pname] = {}
        for dname, dval in domains_data.items():
            # 简化维度名称
            short = dname.split("(")[0].strip()[:20]
            all_domains.add(short)
            judgment = dval.get("judgment", "unclear") if isinstance(dval, dict) else "unclear"
            paper_domains[pname][short] = judgment

    all_domains = sorted(list(all_domains))

    if not papers or not all_domains:
        # 无数据时返回空图
        fig = go.Figure()
        fig.add_annotation(text="暂无质量评价数据", showarrow=False)
        return fig

    # 构建矩阵
    z_values = []
    text_values = []
    for p in papers:
        row_z = []
        row_t = []
        for d in all_domains:
            j = paper_domains.get(p, {}).get(d, "unclear")
            color_val = {"low": 0, "unclear": 1, "high": 2}.get(j, 1)
            row_z.append(color_val)
            label_map = {"low": "低风险", "unclear": "不清楚", "high": "高风险"}
            row_t.append(label_map.get(j, j))
        z_values.append(row_z)
        text_values.append(row_t)

    fig = go.Figure(data=go.Heatmap(
        z=z_values,
        x=list(all_domains),
        y=papers,
        text=text_values,
        texttemplate="%{text}",
        textfont={"size": 10},
        colorscale=[
            [0.0, "#4CAF50"],
            [0.5, "#FFC107"],
            [1.0, "#F44336"]
        ],
        zmin=0, zmax=2,
        showscale=False,
        hovertemplate="文献: %{y}<br>维度: %{x}<br>评价: %{text}<extra></extra>"
    ))

    fig.update_layout(
        title="偏倚风险总结图 (Risk of Bias Summary)",
        xaxis={"side": "bottom", "tickangle": -30},
        yaxis={"autorange": "reversed"},
        height=max(300, len(papers) * 60 + 100),
        margin={"l": 10, "r": 10, "t": 50, "b": 80}
    )

    return fig


def generate_rob_code(rob_results: list) -> str:
    """生成R语言代码用于在R中复现偏倚风险图"""
    lines = [
        "# 循证分析智能体 - 偏倚风险图 R语言代码",
        "# 由系统自动生成，可在 RStudio 中运行",
        "",
        "# 安装依赖（如未安装）",
        "# install.packages(c('ggplot2', 'reshape2'))",
        "",
        "library(ggplot2)",
        "library(reshape2)",
        "",
        "# 数据准备",
        "rob_data <- data.frame(",
    ]

    papers = []
    all_domains = set()
    paper_data = {}

    for r in rob_results:
        pname = r.get("paper_title", "未知文献")[:30]
        papers.append(pname)
        domains_data = r.get("domains", {})
        paper_data[pname] = {}
        for dname, dval in domains_data.items():
            short = dname.split("(")[0].strip()[:20]
            all_domains.add(short)
            judgment = dval.get("judgment", "unclear") if isinstance(dval, dict) else "unclear"
            paper_data[pname][short] = judgment

    all_domains = sorted(list(all_domains))

    # 构建R数据框
    values_text = []
    for p in papers:
        for d in all_domains:
            j = paper_data.get(p, {}).get(d, "unclear")
            val = {"low": 0, "unclear": 1, "high": 2}.get(j, 1)
            values_text.append(f'  {val}, # {p} - {d}')

    lines.append("  Paper = c(" + ", ".join(f'"{p}"' for p in papers) + "),")
    for d in all_domains:
        vals = []
        for p in papers:
            j = paper_data.get(p, {}).get(d, "unclear")
            vals.append(f'"{j}"')
        lines.append(f'  `{d}` = c({", ".join(vals)}),')

    lines.append("  stringsAsFactors = FALSE")
    lines.append(")")
    lines.append("")
    lines.append("# 转换为长格式")
    lines.append("rob_long <- melt(rob_data, id.vars='Paper',")
    lines.append("  variable.name='Domain', value.name='Judgment')")
    lines.append("")
    lines.append("# 设置评价等级为有序因子")
    lines.append("rob_long$Judgment <- factor(rob_long$Judgment,")
    lines.append("  levels = c('low', 'unclear', 'high'),")
    lines.append("  labels = c('低风险', '不清楚', '高风险'),")
    lines.append("  ordered = TRUE)")
    lines.append("")
    lines.append("# 绘制热图")
    lines.append("ggplot(rob_long, aes(x=Domain, y=Paper, fill=Judgment)) +")
    lines.append("  geom_tile(color='white', size=1) +")
    lines.append("  geom_text(aes(label=Judgment), size=3) +")
    lines.append("  scale_fill_manual(")
    lines.append("    values = c('低风险'='#4CAF50', '不清楚'='#FFC107', '高风险'='#F44336'),")
    lines.append("    name = '偏倚风险'")
    lines.append("  ) +")
    lines.append("  theme_minimal() +")
    lines.append("  theme(")
    lines.append("    axis.text.x = element_text(angle=30, hjust=1),")
    lines.append("    panel.grid = element_blank()")
    lines.append("  ) +")
    lines.append("  labs(title='偏倚风险总结图', x='评价维度', y='文献')")

    return "\n".join(lines)
