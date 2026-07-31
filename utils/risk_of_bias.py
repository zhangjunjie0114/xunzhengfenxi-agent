"""
质量评价模块 - Risk of Bias 评估与可视化 (V2重构)
===============================================
V2变更：双工具并行（Cochrane RoB2 + EPHPP）+ 多Outcome累计Traffic Light

工具1: Cochrane RoB2 (Risk of Bias 2.0)
  - 适用范围：仅RCT（随机对照试验）
  - 5个领域：随机化过程、偏离干预、缺失数据、结局测量、选择性报告
  - 评级：Low Risk / Some Concerns / High Risk

工具2: EPHPP (Effective Public Health Practice Project)
  - 适用范围：所有量性研究（不限研究类型）
  - 6个维度A-F：Selection Bias / Study Design / Confounders / Blinding / Data Collection / Withdrawals
  - 评级：Strong / Moderate / Weak
"""
import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# ========================================================================
# 领域/维度定义
# ========================================================================

# --- Cochrane RoB2 五大领域 ---
COCHRANE_ROB2_DOMAINS = [
    {
        "id": "D1",
        "name": "随机化过程",
        "name_en": "Randomization process",
        "description": "评估随机序列生成和分配隐藏是否充分",
        "questions": [
            "随机序列是否真正随机生成？",
            "分配隐藏是否充分？",
            "基线特征是否可比？"
        ]
    },
    {
        "id": "D2",
        "name": "偏离既定干预",
        "name_en": "Deviations from intended interventions",
        "description": "评估是否因干预偏离而影响效应估计",
        "questions": [
            "参与者是否知晓自己的干预分组？",
            "实施者是否知晓参与者的分组？",
            "是否发生了与干预条件相关的偏离？"
        ]
    },
    {
        "id": "D3",
        "name": "结局数据缺失",
        "name_en": "Missing outcome data",
        "description": "评估数据缺失是否可能影响效应估计",
        "questions": [
            "结局数据是否完整？",
            "数据缺失是否与真实结局相关？",
            "缺失数据的处理是否恰当？"
        ]
    },
    {
        "id": "D4",
        "name": "结局测量",
        "name_en": "Measurement of the outcome",
        "description": "评估结局测量的方法是否恰当",
        "questions": [
            "结局测量方法是否恰当？",
            "测量者是否知晓干预分组？",
            "测量方法在不同组之间是否一致？"
        ]
    },
    {
        "id": "D5",
        "name": "选择性报告",
        "name_en": "Selection of the reported result",
        "description": "评估是否存在选择性报告结果",
        "questions": [
            "是否预先注册了研究方案？",
            "报告的结果是否与方案一致？",
            "是否选择性报告了显著结果？"
        ]
    }
]

ROB2_JUDGMENTS = ["low", "some_concerns", "high"]
ROB2_JUDGMENT_LABELS = {"low": "低风险", "some_concerns": "有些担忧", "high": "高风险"}
ROB2_JUDGMENT_COLORS = {"low": "#00B050", "some_concerns": "#FFC000", "high": "#FF0000"}

COCHRANE_TOOL_INFO = {
    "name": "Cochrane RoB2",
    "full_name": "Cochrane Risk of Bias 2.0",
    "reference": "Sterne JAC, Savović J, Page MJ, et al. RoB 2: a revised tool for assessing risk of bias in randomised trials. BMJ 2019; 366: l4898.",
    "url": "https://www.riskofbias.info/welcome/robvis-visualization-tool",
    "applicable_to": "仅适用于随机对照试验（RCT）",
    "domains_count": 5,
    "rating_scale": "低风险 / 有些担忧 / 高风险"
}

# --- EPHPP 六大维度 ---
EPHPP_DOMAINS = [
    {
        "id": "A",
        "name": "选择偏倚",
        "name_en": "Selection Bias",
        "description": "评价研究参与者是否可能代表目标人群",
        "criteria": {
            "strong": "所选个体很可能代表目标人群（>80%参与率）",
            "moderate": "所选个体一定程度上代表目标人群（60-80%参与率）",
            "weak": "所选个体不能代表目标人群（<60%参与率或未描述）"
        }
    },
    {
        "id": "B",
        "name": "研究设计",
        "name_en": "Study Design",
        "description": "评价研究设计类型的严谨程度",
        "criteria": {
            "strong": "随机对照试验（RCT）或对照临床试验（CCT）",
            "moderate": "队列分析研究、病例对照研究或中断时间序列",
            "weak": "其他方法或未描述研究设计"
        }
    },
    {
        "id": "C",
        "name": "混杂因素",
        "name_en": "Confounders",
        "description": "评价是否控制了两组间的重要差异",
        "criteria": {
            "strong": "控制了≥80%的相关混杂因素",
            "moderate": "控制了60-79%的相关混杂因素",
            "weak": "控制<60%或未描述混杂因素控制"
        }
    },
    {
        "id": "D",
        "name": "盲法",
        "name_en": "Blinding",
        "description": "评价结局评估者和/或参与者是否知晓干预",
        "criteria": {
            "strong": "结局评估者和参与者均被盲法",
            "moderate": "部分盲法或仅评估者盲法",
            "weak": "未采用盲法或未描述"
        }
    },
    {
        "id": "E",
        "name": "数据收集方法",
        "name_en": "Data Collection Methods",
        "description": "评价数据收集工具的信度和效度",
        "criteria": {
            "strong": "数据收集工具同时具备信度和效度证据",
            "moderate": "数据收集工具具备信度或效度证据之一",
            "weak": "数据收集工具未报告信度和效度"
        }
    },
    {
        "id": "F",
        "name": "退出和失访",
        "name_en": "Withdrawals and Dropouts",
        "description": "评价随访完成率和退出情况",
        "criteria": {
            "strong": "随访率≥80%，退出的原因已报告",
            "moderate": "随访率60-79%，退出的原因部分报告",
            "weak": "随访率<60%或未描述退出情况"
        }
    }
]

EPHPP_JUDGMENTS = ["strong", "moderate", "weak"]
EPHPP_JUDGMENT_LABELS = {"strong": "强", "moderate": "中", "weak": "弱"}
EPHPP_JUDGMENT_COLORS = {"strong": "#00B050", "moderate": "#FFC000", "weak": "#FF0000"}

EPHPP_TOOL_INFO = {
    "name": "EPHPP",
    "full_name": "Effective Public Health Practice Project Quality Assessment Tool",
    "reference": "Thomas BH, Ciliska D, Dobbins M, Micucci S. A process for systematically reviewing the literature: providing the research evidence for public health nursing interventions. Worldviews Evid Based Nurs 2004; 1(3): 176-184.",
    "url": "https://merst.healthsci.mcmaster.ca/ephpp/",
    "applicable_to": "适用于所有量性研究（RCT、横断面、队列、病例对照等）",
    "domains_count": 6,
    "rating_scale": "强 / 中 / 弱"
}

# ========================================================================
# 工具函数
# ========================================================================

def _get_tool_info(tool: str) -> dict:
    """获取工具信息"""
    if tool == "rob2":
        return COCHRANE_TOOL_INFO
    else:
        return EPHPP_TOOL_INFO

def _get_domains(tool: str) -> list:
    """获取评价维度列表"""
    if tool == "rob2":
        return COCHRANE_ROB2_DOMAINS
    else:
        return EPHPP_DOMAINS

def _get_judgment_labels(tool: str) -> dict:
    """获取评价等级标签"""
    if tool == "rob2":
        return ROB2_JUDGMENT_LABELS
    else:
        return EPHPP_JUDGMENT_LABELS

def _get_judgment_colors(tool: str) -> dict:
    """获取评价等级颜色"""
    if tool == "rob2":
        return ROB2_JUDGMENT_COLORS
    else:
        return EPHPP_JUDGMENT_COLORS

# ========================================================================
# LLM提示词
# ========================================================================

def _build_rob2_prompt(domains: list, text: str) -> tuple:
    """构建RoB2评价的LLM提示词"""
    domains_text = ""
    for d in domains:
        domains_text += f"\n## {d['id']}: {d['name']} ({d['name_en']})\n"
        domains_text += f"说明：{d['description']}\n"
        for q in d['questions']:
            domains_text += f"  - 问题：{q}\n"

    system_prompt = """你是一位系统综述方法学专家，精通Cochrane偏倚风险评价工具RoB2。

请对给定的RCT文献进行偏倚风险评价。RoB2包含5个领域，每个领域需根据文献中报告的信息进行判断。

评价等级：
- low（低风险）：方法学正确，不存在偏倚风险
- some_concerns（有些担忧）：方法学存在一些问题但不足以判定为高风险
- high（高风险）：方法学存在明显缺陷

对每个领域，你必须：
1. 给出判断结果（low / some_concerns / high）
2. 提供明确的原文依据（引用文献中的具体描述）
3. 给出判断推理过程

最后给出总体评价：
- low：所有5个领域均为低风险
- some_concerns：至少1个领域为有些担忧，但无高风险
- high：至少1个领域为高风险，或多个领域为有些担忧

请严格返回以下JSON格式（不包含其他文字）：
```json
{
    "overall": "low/some_concerns/high",
    "overall_reasoning": "总体评价的推理过程",
    "domains": {
        "D1": {"judgment": "low/some_concerns/high", "evidence": "文献中的原文依据", "reasoning": "判断推理过程"},
        "D2": {"judgment": "low/some_concerns/high", "evidence": "...", "reasoning": "..."},
        "D3": {"judgment": "low/some_concerns/high", "evidence": "...", "reasoning": "..."},
        "D4": {"judgment": "low/some_concerns/high", "evidence": "...", "reasoning": "..."},
        "D5": {"judgment": "low/some_concerns/high", "evidence": "...", "reasoning": "..."}
    }
}
```"""

    user_content = f"""请使用Cochrane RoB2工具评价以下RCT文献的偏倚风险。

## RoB2评价维度：
{domains_text}

## 评价标准：
- low（低风险）：方法学正确
- some_concerns（有些担忧）：方法学存在一定问题
- high（高风险）：方法学存在明显缺陷

---文献全文---
{text[:35000]}"""

    return system_prompt, user_content


def _build_ephpp_prompt(domains: list, text: str) -> tuple:
    """构建EPHPP评价的LLM提示词"""
    domains_text = ""
    for d in domains:
        domains_text += f"\n## {d['id']}: {d['name']} ({d['name_en']})\n"
        domains_text += f"说明：{d['description']}\n"
        for level, criteria in d['criteria'].items():
            level_label = {"strong": "强(Strong)", "moderate": "中(Moderate)", "weak": "弱(Weak)"}
            domains_text += f"  - {level_label[level]}：{criteria}\n"

    system_prompt = """你是一位公共卫生研究方法学专家，精通EPHPP质量评价工具。

EPHPP（Effective Public Health Practice Project）工具适用于评价所有量性研究的方法学质量。
它包含6个维度（A-F），每个维度需要根据文献信息判断为强/中/弱。

评价等级：
- strong（强）：方法学质量高，偏倚风险低
- moderate（中）：方法学质量可接受，存在一些偏倚风险
- weak（弱）：方法学质量低，偏倚风险高

对每个维度，你必须：
1. 给出判断结果（strong / moderate / weak）
2. 提供明确的原文依据
3. 给出判断推理过程

总体评价（Global Rating）：
- strong（强）：所有6个维度中无弱（weak）评价
- moderate（中）：有1个维度为弱（weak）评价
- weak（弱）：有2个及以上维度为弱（weak）评价

请严格返回以下JSON格式（不包含其他文字）：
```json
{
    "overall": "strong/moderate/weak",
    "overall_reasoning": "总体评价推理过程",
    "domains": {
        "A": {"judgment": "strong/moderate/weak", "evidence": "文献中的原文依据", "reasoning": "判断推理过程"},
        "B": {"judgment": "strong/moderate/weak", "evidence": "...", "reasoning": "..."},
        "C": {"judgment": "strong/moderate/weak", "evidence": "...", "reasoning": "..."},
        "D": {"judgment": "strong/moderate/weak", "evidence": "...", "reasoning": "..."},
        "E": {"judgment": "strong/moderate/weak", "evidence": "...", "reasoning": "..."},
        "F": {"judgment": "strong/moderate/weak", "evidence": "...", "reasoning": "..."}
    }
}
```"""

    user_content = f"""请使用EPHPP工具评价以下量性研究文献的方法学质量。

## EPHPP评价维度：
{domains_text}

## 评价标准：
- strong（强）：方法学质量高
- moderate（中）：方法学质量可接受
- weak（弱）：方法学质量低

---文献全文---
{text[:35000]}"""

    return system_prompt, user_content


# ========================================================================
# JSON解析
# ========================================================================

def _parse_rob_response(response: str) -> dict:
    """解析质量评价的JSON响应（多策略健壮解析）"""
    import json, re

    if not response or not response.strip():
        return {"overall": "some_concerns", "domains": {}, "error": "AI返回为空"}

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

    # 策略3: 提取最外层 {...} 结构
    brace_start = response.find('{')
    brace_end = response.rfind('}')
    if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
        try:
            return json.loads(response[brace_start:brace_end + 1])
        except json.JSONDecodeError:
            pass

    # 策略4: 修复常见JSON错误后重试
    fixed = response.strip()
    fixed = re.sub(r"'([^']+)'", r'"\1"', fixed)
    fixed = re.sub(r',(\s*[}\]])', r'\1', fixed)
    brace_start2 = fixed.find('{')
    brace_end2 = fixed.rfind('}')
    if brace_start2 != -1 and brace_end2 != -1 and brace_end2 > brace_start2:
        try:
            return json.loads(fixed[brace_start2:brace_end2 + 1])
        except json.JSONDecodeError:
            pass

    return {"overall": "some_concerns", "domains": {}, "error": "无法解析评价结果"}


# ========================================================================
# 评估函数
# ========================================================================

def assess_rob2(papers: list, call_llm_func: Callable,
                progress_callback: Optional[Callable] = None) -> list:
    """使用Cochrane RoB2评估RCT文献

    Args:
        papers: 文献列表 [{ "title", "text", "file_name" }]
        call_llm_func: LLM调用函数
        progress_callback: 进度回调 (current, total, message)

    Returns:
        list: 每篇文献的评价结果
    """
    results = []
    total = len(papers)
    domains = COCHRANE_ROB2_DOMAINS

    for idx, paper in enumerate(papers):
        title = paper.get("title") or paper.get("file_name", f"文献{idx+1}")
        text = paper.get("text", "")

        if progress_callback:
            progress_callback(idx + 1, total, f"RoB2评价: {title[:30]}...")

        # 截断长文本
        max_chars = 40000
        if len(text) > max_chars:
            half = max_chars // 2
            text = text[:half] + "\n\n[中间内容省略...]\n\n" + text[-half:]

        system_prompt, user_content = _build_rob2_prompt(domains, text)

        try:
            response = call_llm_func(system_prompt, user_content)
            result = _parse_rob_response(response)
            result["paper_title"] = title
            result["file_name"] = paper.get("file_name", "")
            result["tool"] = "rob2"
            result["tool_name"] = "Cochrane RoB2"
            result["judgment_system"] = "low / some_concerns / high"
        except Exception as e:
            logger.error(f"RoB2评价失败: {title} - {e}")
            result = {
                "paper_title": title,
                "file_name": paper.get("file_name", ""),
                "overall": "some_concerns",
                "domains": {},
                "tool": "rob2",
                "tool_name": "Cochrane RoB2",
                "error": str(e)
            }

        results.append(result)

    return results


def assess_ephpp(papers: list, call_llm_func: Callable,
                 progress_callback: Optional[Callable] = None) -> list:
    """使用EPHPP评估量性研究文献（不限研究类型）

    Args:
        papers: 文献列表 [{ "title", "text", "file_name" }]
        call_llm_func: LLM调用函数
        progress_callback: 进度回调 (current, total, message)

    Returns:
        list: 每篇文献的评价结果
    """
    results = []
    total = len(papers)
    domains = EPHPP_DOMAINS

    for idx, paper in enumerate(papers):
        title = paper.get("title") or paper.get("file_name", f"文献{idx+1}")
        text = paper.get("text", "")

        if progress_callback:
            progress_callback(idx + 1, total, f"EPHPP评价: {title[:30]}...")

        # 截断长文本
        max_chars = 40000
        if len(text) > max_chars:
            half = max_chars // 2
            text = text[:half] + "\n\n[中间内容省略...]\n\n" + text[-half:]

        system_prompt, user_content = _build_ephpp_prompt(domains, text)

        try:
            response = call_llm_func(system_prompt, user_content)
            result = _parse_rob_response(response)
            result["paper_title"] = title
            result["file_name"] = paper.get("file_name", "")
            result["tool"] = "ephpp"
            result["tool_name"] = "EPHPP"
            result["judgment_system"] = "strong / moderate / weak"
        except Exception as e:
            logger.error(f"EPHPP评价失败: {title} - {e}")
            result = {
                "paper_title": title,
                "file_name": paper.get("file_name", ""),
                "overall": "moderate",
                "domains": {},
                "tool": "ephpp",
                "tool_name": "EPHPP",
                "error": str(e)
            }

        results.append(result)

    return results


def assess_rob(papers: list, call_llm_func: Callable,
               progress_callback: Optional[Callable] = None,
               tool: str = "rob2") -> list:
    """统一的入口：根据选择的工具进行质量评价

    Args:
        papers: 文献列表
        call_llm_func: LLM调用函数
        progress_callback: 进度回调
        tool: "rob2" 或 "ephpp"

    Returns:
        list: 评价结果
    """
    if tool == "rob2":
        return assess_rob2(papers, call_llm_func, progress_callback)
    else:
        return assess_ephpp(papers, call_llm_func, progress_callback)


# ========================================================================
# 可视化 - Traffic Light 图
# ========================================================================

def generate_traffic_light(rob_results: list, tool: str = "rob2",
                           outcome_name: str = "主要结局") -> object:
    """生成Cochrane风格红绿灯图（单Outcome）

    Args:
        rob_results: 质量评价结果列表
        tool: "rob2" 或 "ephpp"
        outcome_name: 结局名称

    Returns:
        plotly.figure: Traffic Light图
    """
    import plotly.graph_objects as go

    colors = _get_judgment_colors(tool)
    labels = _get_judgment_labels(tool)
    domains_config = _get_domains(tool)

    # 提取数据
    papers = []
    all_domain_ids = [d["id"] for d in domains_config]
    domain_names = {}  # id -> short name
    for d in domains_config:
        domain_names[d["id"]] = d["name"]

    paper_data = {}  # {paper: {domain_id: judgment}}
    paper_overall = {}  # {paper: overall}

    for r in rob_results:
        pname = r.get("paper_title", "未知文献")[:25]
        papers.append(pname)
        paper_data[pname] = {}
        paper_overall[pname] = r.get("overall", "some_concerns" if tool == "rob2" else "moderate")

        domains_data = r.get("domains", {})
        for d in domains_config:
            did = d["id"]
            domain_info = domains_data.get(did, {})
            judgment = domain_info.get("judgment", "some_concerns" if tool == "rob2" else "moderate")
            if isinstance(domain_info, dict):
                judgment = domain_info.get("judgment", judgment)
            elif isinstance(domain_info, str):
                judgment = domain_info
            paper_data[pname][did] = judgment

    if not papers:
        fig = go.Figure()
        fig.add_annotation(text="暂无质量评价数据", showarrow=False, font={"size": 14})
        fig.update_layout(height=300)
        return fig

    # 构建显示矩阵（每行一个研究，每列一个维度）
    # 使用Scatter绘制圆点
    fig = go.Figure()

    n_papers = len(papers)
    n_domains = len(all_domain_ids)

    # 添加每个维度的圆点
    for di, did in enumerate(all_domain_ids):
        for pi, pname in enumerate(papers):
            judgment = paper_data[pname].get(did, "some_concerns" if tool == "rob2" else "moderate")
            judgment = str(judgment).lower()
            # 标准化judgment key
            if judgment in ["low", "high", "some_concerns"]:
                pass  # RoB2 keys
            elif judgment in ("strong", "weak"):
                pass  # EPHPP keys
            elif judgment == "moderate":
                judgment = "moderate"
            else:
                judgment = "some_concerns" if tool == "rob2" else "moderate"

            color = colors.get(judgment, "#808080")
            label = labels.get(judgment, judgment)

            # 获取证据文本用于hover
            domains_data = {}
            for r in rob_results:
                if r.get("paper_title", "")[:25] == pname:
                    domains_data = r.get("domains", {})
                    break
            evidence = ""
            if did in domains_data:
                if isinstance(domains_data[did], dict):
                    evidence = domains_data[did].get("evidence", "")
                elif isinstance(domains_data[did], str):
                    evidence = domains_data[did]
            evidence = str(evidence)[:120] if evidence else ""

            fig.add_trace(go.Scatter(
                x=[di],
                y=[pi],
                mode="markers",
                marker={
                    "size": 28,
                    "color": color,
                    "line": {"width": 1, "color": "#555"},
                    "symbol": "circle"
                },
                name=f"{pname} - {domain_names[did]}",
                text=f"<b>{pname}</b><br><b>{domain_names[did]}</b><br>评价: {label}<br>{evidence}",
                hoverinfo="text",
                showlegend=False,
                hovertemplate="%{text}<extra></extra>"
            ))

    # 添加总体评价列（最后一列）
    overall_x = n_domains
    for pi, pname in enumerate(papers):
        overall = str(paper_overall.get(pname, "some_concerns" if tool == "rob2" else "moderate")).lower()
        if overall in ("low", "high", "some_concerns", "strong", "weak", "moderate"):
            pass
        else:
            overall = "some_concerns" if tool == "rob2" else "moderate"

        color = colors.get(overall, "#808080")
        label = labels.get(overall, overall)

        fig.add_trace(go.Scatter(
            x=[overall_x],
            y=[pi],
            mode="markers",
            marker={
                "size": 28,
                "color": color,
                "line": {"width": 2, "color": "#333"},
                "symbol": "diamond-wide"
            },
            name=f"{pname} - 总体",
            text=f"<b>{pname}</b><br>总体评价: {label}",
            hoverinfo="text",
            showlegend=False,
            hovertemplate="%{text}<extra></extra>"
        ))

    # 设置版式
    domain_labels = [d["name"] for d in domains_config] + ["总体"]

    fig.update_layout(
        title=f"<b>偏倚风险综合评价</b><br><span style='font-size:12px;color:#666'>{outcome_name} | "
              f"{_get_tool_info(tool)['name']}</span>",
        xaxis={
            "tickmode": "array",
            "tickvals": list(range(len(domain_labels))),
            "ticktext": domain_labels,
            "side": "bottom",
            "tickangle": 0,
            "tickfont": {"size": 11}
        },
        yaxis={
            "tickmode": "array",
            "tickvals": list(range(n_papers)),
            "ticktext": papers,
            "autorange": "reversed",
            "tickfont": {"size": 11}
        },
        height=max(120, n_papers * 55 + 100),
        margin={"l": 10, "r": 10, "t": 60, "b": 40, "pad": 4},
        plot_bgcolor="white",
        hovermode="closest",
        xaxis_showgrid=False,
        yaxis_showgrid=False,
    )

    return fig


def generate_multi_outcome_traffic_light(rob_results_by_outcome: dict,
                                         tool: str = "rob2") -> object:
    """生成多Outcome累计红绿灯图（多个Outcome垂直堆叠）

    Args:
        rob_results_by_outcome: {outcome_name: [rob_results]}
        tool: "rob2" 或 "ephpp"

    Returns:
        plotly.figure: 多Outcome堆叠的Traffic Light图
    """
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    if not rob_results_by_outcome:
        fig = go.Figure()
        fig.add_annotation(text="暂无质量评价数据", showarrow=False, font={"size": 14})
        fig.update_layout(height=300)
        return fig

    colors = _get_judgment_colors(tool)
    labels = _get_judgment_labels(tool)
    domains_config = _get_domains(tool)
    domain_labels = [d["name"] for d in domains_config] + ["总体"]
    n_domains = len(domains_config)

    n_outcomes = len(rob_results_by_outcome)
    outcome_names = list(rob_results_by_outcome.keys())

    # 计算每个Outcome有多少篇文献
    n_papers_list = []
    for oname, results in rob_results_by_outcome.items():
        n_papers_list.append(len(results))

    max_papers = max(n_papers_list) if n_papers_list else 0

    # 每个子图高度（px）
    height_per_paper = 55
    subplot_height = max(120, max_papers * height_per_paper + 40)
    total_height = subplot_height * n_outcomes + 40

    # 创建子图：垂直排列，共享x轴和y轴范围
    fig = make_subplots(
        rows=n_outcomes,
        cols=1,
        subplot_titles=[f"<b>{oname}</b>" for oname in outcome_names],
        vertical_spacing=0.12 / max(1, n_outcomes),
        shared_xaxes=True,
    )

    for oi, (oname, results) in enumerate(rob_results_by_outcome.items(), 1):
        papers = []
        paper_data = {}
        paper_overall = {}

        for r in results:
            pname = r.get("paper_title", "未知文献")[:25]
            papers.append(pname)
            paper_data[pname] = {}
            paper_overall[pname] = r.get("overall", "some_concerns" if tool == "rob2" else "moderate")

            domains_data = r.get("domains", {})
            for d in domains_config:
                did = d["id"]
                domain_info = domains_data.get(did, {})
                if isinstance(domain_info, dict):
                    judgment = domain_info.get("judgment", "some_concerns" if tool == "rob2" else "moderate")
                elif isinstance(domain_info, str):
                    judgment = domain_info
                else:
                    judgment = "some_concerns" if tool == "rob2" else "moderate"
                paper_data[pname][did] = judgment

        n_papers = len(papers)

        # 添加维度圆点
        for di, did in enumerate([d["id"] for d in domains_config]):
            for pi, pname in enumerate(papers):
                judgment = str(paper_data[pname].get(did, "some_concerns" if tool == "rob2" else "moderate")).lower()
                color = colors.get(judgment, "#808080")
                label = labels.get(judgment, judgment)

                evidence = ""
                for r in results:
                    if r.get("paper_title", "")[:25] == pname:
                        d_info = r.get("domains", {}).get(did, {})
                        if isinstance(d_info, dict):
                            evidence = str(d_info.get("evidence", ""))[:120]
                        break

                fig.add_trace(go.Scatter(
                    x=[di],
                    y=[pi],
                    mode="markers",
                    marker={"size": 24, "color": color,
                            "line": {"width": 1, "color": "#555"},
                            "symbol": "circle"},
                    text=f"<b>{pname}</b><br>{domains_config[di]['name']}<br>评价: {label}<br>{evidence}",
                    hoverinfo="text",
                    showlegend=False,
                    hovertemplate="%{text}<extra></extra>"
                ), row=oi, col=1)

        # 添加总体评价
        for pi, pname in enumerate(papers):
            overall = str(paper_overall.get(pname, "some_concerns" if tool == "rob2" else "moderate")).lower()
            color = colors.get(overall, "#808080")
            label = labels.get(overall, overall)

            fig.add_trace(go.Scatter(
                x=[n_domains],
                y=[pi],
                mode="markers",
                marker={"size": 24, "color": color,
                        "line": {"width": 2, "color": "#333"},
                        "symbol": "diamond-wide"},
                text=f"<b>{pname}</b><br>总体评价: {label}",
                hoverinfo="text",
                showlegend=False,
                hovertemplate="%{text}<extra></extra>"
            ), row=oi, col=1)

        # 设置子图样式
        fig.update_xaxes(
            tickmode="array",
            tickvals=list(range(len(domain_labels))),
            ticktext=domain_labels if oi == n_outcomes else [],
            tickfont={"size": 10},
            side="bottom",
            showgrid=False,
            row=oi, col=1
        )
        fig.update_yaxes(
            tickmode="array",
            tickvals=list(range(n_papers)),
            ticktext=papers,
            autorange="reversed",
            tickfont={"size": 10},
            showgrid=False,
            row=oi, col=1
        )

    tool_info = _get_tool_info(tool)
    fig.update_layout(
        title=f"<b>多结局累积偏倚风险图</b><br><span style='font-size:12px;color:#666'>"
              f"{tool_info['name']} | 绿色=低风险 黄色=中等 红色=高风险</span>",
        height=total_height,
        margin={"l": 10, "r": 10, "t": 60, "b": 30, "pad": 4},
        plot_bgcolor="white",
        hovermode="closest",
    )

    return fig


def generate_rob_summary_bar(rob_results: list, tool: str = "rob2") -> object:
    """生成偏倚风险汇总柱状图（各维度分布）

    Args:
        rob_results: 评价结果列表
        tool: "rob2" 或 "ephpp"

    Returns:
        plotly.figure: 汇总柱状图
    """
    import plotly.graph_objects as go

    colors = _get_judgment_colors(tool)
    labels = _get_judgment_labels(tool)
    domains_config = _get_domains(tool)
    all_judgments = list(colors.keys())

    # 统计每个维度各评级的数量
    domain_stats = {}
    for d in domains_config:
        did = d["id"]
        domain_stats[did] = {j: 0 for j in all_judgments}

    for r in rob_results:
        domains_data = r.get("domains", {})
        for d in domains_config:
            did = d["id"]
            info = domains_data.get(did, {})
            if isinstance(info, dict):
                j = info.get("judgment", all_judgments[1])
            elif isinstance(info, str):
                j = info
            else:
                j = all_judgments[1]
            if j not in domain_stats[did]:
                j = all_judgments[1]
            domain_stats[did][j] += 1

    fig = go.Figure()
    domain_names = [d["name"] for d in domains_config]

    for j in all_judgments:
        counts = [domain_stats[d["id"]][j] for d in domains_config]
        fig.add_trace(go.Bar(
            name=labels[j],
            x=domain_names,
            y=counts,
            marker_color=colors[j],
            text=counts,
            textposition="inside",
        ))

    n_total = len(rob_results)
    fig.update_layout(
        title=f"偏倚风险汇总 (共{n_total}篇)",
        barmode="stack",
        height=300,
        margin={"l": 10, "r": 10, "t": 40, "b": 40},
        plot_bgcolor="white",
        hovermode="x",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1}
    )

    return fig


# ========================================================================
# R代码生成
# ========================================================================

def generate_rob_code(rob_results: list, tool: str = "rob2") -> str:
    """生成R语言代码，适配双工具

    Args:
        rob_results: 评价结果列表
        tool: "rob2" 或 "ephpp"

    Returns:
        str: R代码
    """
    labels = _get_judgment_labels(tool)
    domains_config = _get_domains(tool)
    tool_info = _get_tool_info(tool)

    domain_ids = [d["id"] for d in domains_config]

    lines = [
        f"# 循证分析智能体 - {tool_info['name']} 偏倚风险图 R语言代码",
        "# 由系统自动生成，可在 RStudio 中运行",
        "# 如需使用robvis包生成更美观的图，请安装：install.packages('robvis')",
        "",
        "# ===== 数据准备 ===== ",
        "",
    ]

    # 构建数据
    papers = []
    paper_judgments = {}

    for r in rob_results:
        pname = r.get("paper_title", "未知文献")
        papers.append(pname)
        paper_judgments[pname] = {}
        domains_data = r.get("domains", {})
        for d in domains_config:
            did = d["id"]
            info = domains_data.get(did, {})
            if isinstance(info, dict):
                j = info.get("judgment", "")
            elif isinstance(info, str):
                j = info
            else:
                j = ""
            paper_judgments[pname][did] = j
        paper_judgments[pname]["overall"] = r.get("overall", "")

    if papers:
        lines.append("# 创建数据框")
        lines.append("rob_data <- data.frame(")
        lines.append(f"  Study = c({', '.join(f'\"{p}\"' for p in papers)}),")
        for d in domains_config:
            vals = []
            for p in papers:
                j = paper_judgments.get(p, {}).get(d["id"], "")
                vals.append(f'"{j}"')
            lines.append(f"  `{d['id']}` = c({', '.join(vals)}),")
        overall_vals = [f'"{paper_judgments.get(p, {}).get("overall", "")}"' for p in papers]
        lines.append(f"  Overall = c({', '.join(overall_vals)}),")
        lines.append("  stringsAsFactors = FALSE")
        lines.append(")")
        lines.append("")
        lines.append("# 方法1：使用 robvis 包生成红绿灯图")
        lines.append("library(robvis)")
        lines.append(f"rob_traffic_light(rob_data, tool = '{'ROB2' if tool == 'rob2' else 'Generic'}')")
        lines.append("")
        lines.append("# 方法2：使用 ggplot2 自定义绘制")
        lines.append("library(ggplot2)")
        lines.append("library(tidyr)")
        lines.append("")
        lines.append("rob_long <- rob_data %>%")
        lines.append("  pivot_longer(cols = -Study, names_to = 'Domain', values_to = 'Judgment')")
        lines.append("")
        lines.append(f"rob_long$Judgment <- factor(rob_long$Judgment,")
        if tool == "rob2":
            lines.append("  levels = c('low', 'some_concerns', 'high'),")
            lines.append(f"  labels = c('{labels['low']}', '{labels['some_concerns']}', '{labels['high']}'),")
        else:
            lines.append("  levels = c('strong', 'moderate', 'weak'),")
            lines.append(f"  labels = c('{labels['strong']}', '{labels['moderate']}', '{labels['weak']}'),")
        lines.append("  ordered = TRUE)")
        lines.append("")
        lines.append("ggplot(rob_long, aes(x = Domain, y = Study, fill = Judgment)) +")
        lines.append("  geom_point(aes(color = Judgment), size = 6) +")
        if tool == "rob2":
            lines.append("  scale_color_manual(values = c('低风险' = '#00B050', '有些担忧' = '#FFC000', '高风险' = '#FF0000')) +")
        else:
            lines.append("  scale_color_manual(values = c('强' = '#00B050', '中' = '#FFC000', '弱' = '#FF0000')) +")
        lines.append("  theme_minimal() +")
        lines.append("  theme(")
        lines.append("    axis.text.x = element_text(angle = 0, hjust = 0.5),")
        lines.append("    panel.grid = element_blank(),")
        lines.append("    legend.position = 'bottom'")
        lines.append("  ) +")
        lines.append("  labs(title = '偏倚风险评价 Traffic Light 图',")
        lines.append(f"       subtitle = '工具: {tool_info['name']}')")
    else:
        lines.append("# 示例数据（请替换为实际数据）")
        lines.append("rob_data <- data.frame(")
        lines.append("  Study = c('Study1', 'Study2', 'Study3'),")
        for d in domains_config:
            lines.append(f"  `{d['id']}` = c('low', 'some_concerns', 'low'),")
        lines.append("  Overall = c('low', 'some_concerns', 'low'),")
        lines.append("  stringsAsFactors = FALSE")
        lines.append(")")
        lines.append("# 后续代码同上...")

    return "\n".join(lines)


# ========================================================================
# 兼容旧版本接口
# ========================================================================

def generate_rob_chart(rob_results: list) -> object:
    """兼容V1接口：默认使用RoB2生成热力图

    V2中推荐使用 generate_traffic_light() 替代
    """
    import plotly.graph_objects as go
    from plotly import colors as pcolors

    # 尝试判断是旧格式还是新格式
    tool = "rob2"
    if rob_results:
        sample = rob_results[0]
        if isinstance(sample, dict):
            tool = sample.get("tool", "rob2")

    return generate_traffic_light(rob_results, tool=tool)
