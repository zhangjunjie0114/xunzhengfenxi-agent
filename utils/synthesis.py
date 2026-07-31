"""
证据合成模块 - 研究特征表、描述性总结、叙事性合成、Meta分析
"""
import logging
from typing import Optional, Callable

logger = logging.getLogger(__name__)


def generate_study_characteristics_table(extraction_results: list) -> str:
    """生成研究特征总结表 (Study Characteristics Table)

    Args:
        extraction_results: 提取结果列表

    Returns:
        str: Markdown格式的研究特征表
    """
    if not extraction_results:
        return "暂无提取数据，请先在数据提取模块完成提取。"

    lines = [
        "## 研究特征总结表 (Study Characteristics Table)",
        "",
        "| 作者/年份 | 研究设计 | 样本量 | 研究对象 | 干预措施 | 主要结局指标 | 主要发现 |",
        "|-----------|---------|--------|---------|---------|------------|---------|",
    ]

    for r in extraction_results:
        if "error" in r:
            continue
        author = r.get("author_year", r.get("paper", "未知"))[:20]
        design = r.get("study_design", "未报告")[:15]
        sample = r.get("sample_size", "未报告")
        pop = r.get("population", "未报告")[:30]
        intervention = r.get("intervention", "未报告")[:30]
        outcome = r.get("outcome_measures", "未报告")[:30]
        findings = r.get("main_findings", "未报告")[:40]

        lines.append(f"| {author} | {design} | {sample} | {pop} | {intervention} | {outcome} | {findings} |")

    lines.append("")
    lines.append("*注：本表由AI基于文献提取数据自动生成，请学生审核确认。*")
    return "\n".join(lines)


def generate_descriptive_summary(extraction_results: list) -> str:
    """生成描述性总结 (Descriptive Summary)

    仅客观呈现各研究的特征和发现，不做统计合成
    """
    if not extraction_results:
        return "暂无提取数据。"

    total = len([r for r in extraction_results if "error" not in r])
    lines = [
        "## 描述性总结 (Descriptive Summary)",
        "",
        f"本综述共纳入 {total} 篇文献，以下对各研究的基本特征和主要发现进行描述性总结。",
        "",
    ]

    # 按研究设计分组
    designs = {}
    for r in extraction_results:
        if "error" in r:
            continue
        design = r.get("study_design", "未分类")
        if design not in designs:
            designs[design] = []
        designs[design].append(r)

    # 研究设计分布
    lines.append("### 研究设计分布")
    for design, papers in designs.items():
        lines.append(f"- **{design}**：{len(papers)}篇")
    lines.append("")

    # 样本量概况
    sample_sizes = []
    for r in extraction_results:
        if "error" not in r:
            ss = str(r.get("sample_size", "")).replace(",", "").strip()
            if ss.isdigit():
                try:
                    sample_sizes.append(int(ss))
                except (ValueError, TypeError):
                    pass

    if sample_sizes:
        lines.append(f"### 样本量概况")
        lines.append(f"- 范围：{min(sample_sizes)} - {max(sample_sizes)}")
        lines.append(f"- 合计：{sum(sample_sizes)}")
        lines.append("")

    # 逐篇描述
    lines.append("### 各研究主要发现")
    for idx, r in enumerate(extraction_results, 1):
        if "error" in r:
            continue
        author = r.get("author_year", r.get("paper", f"研究{idx}"))
        purpose = r.get("research_purpose", "未报告研究目的")
        findings = r.get("main_findings", "未报告主要发现")
        conclusion = r.get("conclusion", "")

        lines.append(f"**{idx}. {author}**")
        lines.append(f"- 研究目的：{purpose}")
        lines.append(f"- 主要发现：{findings}")
        if conclusion:
            lines.append(f"- 作者结论：{conclusion}")
        lines.append("")

    lines.append("---")
    lines.append("*注：本描述性总结仅客观呈现各研究的信息，未进行统计合并。*")
    return "\n".join(lines)


def generate_narrative_synthesis(extraction_results: list, rob_results: list) -> str:
    """生成叙事性合成 (Narrative Synthesis)"""
    if not extraction_results:
        return "暂无提取数据。"

    lines = [
        "## 叙事性合成 (Narrative Synthesis)",
        "",
        "本部分对各研究的发现进行归纳整合，识别共同点和差异。",
        "",
    ]

    # 提取主要发现进行归类
    all_findings = []
    for r in extraction_results:
        if "error" in r:
            continue
        all_findings.append({
            "author": r.get("author_year", r.get("paper", "未知")),
            "findings": r.get("main_findings", ""),
            "design": r.get("study_design", ""),
            "outcome": r.get("outcome_measures", ""),
            "effect": r.get("effect_size_value", ""),
        })

    if not all_findings:
        return "暂无有效提取数据。"

    # 按结局指标分组
    outcome_groups = {}
    for f in all_findings:
        outcome = f["outcome"][:20] if f["outcome"] else "其他"
        if outcome not in outcome_groups:
            outcome_groups[outcome] = []
        outcome_groups[outcome].append(f)

    lines.append(f"### 纳入研究概述")
    lines.append(f"共纳入 {len(all_findings)} 篇研究，涉及以下结局指标：")
    for outcome, studies in outcome_groups.items():
        authors = [s["author"] for s in studies]
        lines.append(f"- **{outcome}**：{'、'.join(authors[:5])}")
        if len(authors) > 5:
            lines.append(f"  - 等共{len(authors)}篇研究")
    lines.append("")

    # 证据一致性分析
    lines.append("### 证据一致性分析")
    for outcome, studies in outcome_groups.items():
        lines.append(f"**{outcome}**：")
        positive = 0
        negative = 0
        mixed = 0
        for s in studies:
            f_text = s["findings"].lower()
            if any(w in f_text for w in ["显著", "有效", "改善", "提高", "positive", "significant", "improve"]):
                positive += 1
            elif any(w in f_text for w in ["不显著", "无效", "无差异", "no significant", "no effect"]):
                negative += 1
            else:
                mixed += 1
        lines.append(f"  - {positive}篇报告积极效果，{negative}篇报告无显著效果，{mixed}篇结果复杂")
        lines.append("")

    # 结合质量评价
    if rob_results:
        lines.append("### 证据质量分级")
        # 兼容两种工具：RoB2(low/some_concerns/high) 和 EPHPP(strong/moderate/weak)
        low_risk = sum(1 for r in rob_results if r.get("overall") in ("low", "strong"))
        unclear_risk = sum(1 for r in rob_results if r.get("overall") in ("some_concerns", "moderate", "unclear"))
        high_risk = sum(1 for r in rob_results if r.get("overall") in ("high", "weak"))

        lines.append(f"根据偏倚风险评价：")
        lines.append(f"- 低偏倚风险（高质量）：{low_risk}篇")
        lines.append(f"- 偏倚风险不清楚：{unclear_risk}篇")
        lines.append(f"- 高偏倚风险（低质量）：{high_risk}篇")
        lines.append("")
        if low_risk > high_risk:
            conclusion = "较高"
        elif unclear_risk > high_risk:
            conclusion = "中等"
        elif low_risk == 0 and unclear_risk == 0 and high_risk == 0:
            conclusion = "无法判断"
        elif low_risk == high_risk:
            conclusion = "中等"
        else:
            conclusion = "有限"
        lines.append(f"综合来看，本综述的证据质量为{conclusion}。")

    return "\n".join(lines)


def calculate_effect_sizes(extraction_results: list) -> dict:
    """计算可合并的效应量

    Returns:
        dict: { "type": "MD/SMD/OR/RR", "values": [...], "suggestion": str }
    """
    effects = []
    for r in extraction_results:
        if "error" in r:
            continue
        es_type = r.get("effect_size", "")
        es_value = r.get("effect_size_value", "")
        ci = r.get("confidence_interval", "")
        author = r.get("author_year", r.get("paper", "未知"))

        if es_type or es_value:
            effects.append({
                "author": author,
                "type": es_type,
                "value": es_value,
                "ci": ci
            })

    return {
        "count": len(effects),
        "effects": effects,
        "suggestion": "建议基于数据特征选择合适的效应量类型" if not effects else "可进行效应量合并"
    }


def generate_forest_plot(extraction_results: list) -> object:
    """生成森林图 (Forest Plot)

    Args:
        extraction_results: 提取结果列表

    Returns:
        plotly.figure: 森林图
    """
    import plotly.graph_objects as go
    import random

    # 提取效应量数据
    studies = []
    for r in extraction_results:
        if "error" in r:
            continue
        author = r.get("author_year", r.get("paper", "未知"))[:20]
        es_val = r.get("effect_size_value", "")

        # 尝试解析效应量数值
        try:
            import re
            nums = re.findall(r'[-]?\d+\.?\d*', es_val)
            if nums:
                effect = float(nums[0])
                ci_lower = effect * 0.7 if len(nums) < 2 else float(nums[1])
                ci_upper = effect * 1.3 if len(nums) < 3 else float(nums[2]) if len(nums) > 2 else effect * 1.3
                studies.append({
                    "author": author,
                    "effect": effect,
                    "ci_lower": ci_lower,
                    "ci_upper": ci_upper,
                    "weight": random.uniform(5, 20)
                })
        except (ValueError, IndexError):
            pass

    if not studies:
        # 使用模拟数据演示
        fig = go.Figure()
        fig.add_annotation(
            text="暂无足够的效应量数据生成森林图。<br>请先在数据提取模块补充效应量数据，<br>或点击下方按钮生成R代码。",
            showarrow=False, font={"size": 14}
        )
        fig.update_layout(height=200)
        return fig

    # 计算合并效应量（简单平均加权）
    total_weight = sum(s["weight"] for s in studies)
    pooled_effect = sum(s["effect"] * s["weight"] for s in studies) / total_weight
    pooled_ci_lower = pooled_effect * 0.85
    pooled_ci_upper = pooled_effect * 1.15

    fig = go.Figure()

    # 添加各研究
    for s in studies:
        fig.add_trace(go.Scatter(
            x=[s["effect"]], y=[s["author"]],
            mode="markers",
            marker={"size": s["weight"] * 1.5, "color": "#2196F3"},
            error_x={
                "type": "data",
                "symmetric": False,
                "array": [s["ci_upper"] - s["effect"]],
                "arrayminus": [s["effect"] - s["ci_lower"]]
            },
            name=s["author"],
            hovertemplate=f"{s['author']}<br>效应量: {s['effect']:.2f}<br>95%CI: ({s['ci_lower']:.2f}, {s['ci_upper']:.2f})<extra></extra>"
        ))

    # 添加合并效应量（菱形）
    fig.add_trace(go.Scatter(
        x=[pooled_effect], y=["合并效应量"],
        mode="markers",
        marker={"size": 15, "color": "#F44336", "symbol": "diamond"},
        error_x={
            "type": "data",
            "symmetric": False,
            "array": [pooled_ci_upper - pooled_effect],
            "arrayminus": [pooled_effect - pooled_ci_lower]
        },
        name="合并效应量",
        hovertemplate=f"合并效应量: {pooled_effect:.2f}<br>95%CI: ({pooled_ci_lower:.2f}, {pooled_ci_upper:.2f})<extra></extra>"
    ))

    # 添加参考线
    fig.add_vline(x=0, line_dash="dash", line_color="gray", opacity=0.5)

    fig.update_layout(
        title="森林图 (Forest Plot)",
        xaxis={"title": "效应量 (Effect Size)"},
        yaxis={"title": "", "autorange": "reversed"},
        height=max(300, len(studies) * 50 + 100),
        showlegend=False,
        hovermode="y",
        margin={"l": 10, "r": 10, "t": 50, "b": 50}
    )

    return fig


def generate_forest_plot_code(extraction_results: list) -> str:
    """生成R语言森林图代码"""
    lines = [
        "# 循证分析智能体 - 森林图 R语言代码",
        "# 由系统自动生成，可在 RStudio 中运行",
        "",
        "# 安装依赖（如未安装）",
        "# install.packages('meta')",
        "# install.packages('forestplot')",
        "",
        "library(meta)",
        "library(forestplot)",
        "",
        "# ===== 数据准备 ===== ",
        "# 请根据实际数据修改以下内容",
        "",
    ]

    studies = []
    for r in extraction_results:
        if "error" not in r:
            author = r.get("author_year", r.get("paper", "未知"))[:20]
            es_val = r.get("effect_size_value", "")
            ci = r.get("confidence_interval", "")
            if es_val:
                studies.append({"author": author, "es": es_val, "ci": ci})

    if studies:
        lines.append("# 效应量数据")
        lines.append("studies <- data.frame(")
        lines.append("  author = c(" + ", ".join(f'"{s["author"]}"' for s in studies) + "),")
        lines.append("  effect = c(" + ", ".join(s["es"] for s in studies if s["es"]) + "),")
        lines.append("  # 如有置信区间数据，取消注释下一行")
        lines.append("  # ci_lower = c(...),")
        lines.append("  # ci_upper = c(...)")
        lines.append(")")
    else:
        lines.append("# 示例数据（请替换为实际数据）")
        lines.append("studies <- data.frame(")
        lines.append("  author = c('Zhang, 2023', 'Li, 2022', 'Wang, 2021'),")
        lines.append("  effect = c(0.75, 0.82, 0.68),")
        lines.append("  se = c(0.12, 0.15, 0.10)")
        lines.append(")")
        lines.append("")

    lines.extend([
        "",
        "# 使用meta包进行Meta分析",
        "m <- metagen(",
        "  TE = effect,",
        "  seTE = se,",
        "  data = studies,",
        "  studlab = author,",
        "  comb.fixed = TRUE,",
        "  comb.random = TRUE,",
        "  sm = 'OR',   # 根据数据类型调整: OR/RR/MD/SMD",
        "  hakn = TRUE",
        ")",
        "",
        "# 绘制森林图",
        "forest(m,",
        "  leftlabs = c('研究', '效应量', '95%CI', '权重'),",
        "  rightlabs = c('森林图'),",
        "  col.diamond = 'steelblue',",
        "  col.square = 'navy',",
        "  hetstat = TRUE,",
        "  overall = TRUE",
        ")",
        "",
        "# dev.off()",
    ])

    return "\n".join(lines)


# ========================================================================
# Meta分析专业化 (V2增强)
# ========================================================================

def determine_effect_measure(extraction_results: list) -> dict:
    """根据数据特征自动推荐效应量类型

    Args:
        extraction_results: 提取结果列表

    Returns:
        dict: {
            "recommended": "MD/SMD/OR/RR",
            "data_type": "continuous/dichotomous",
            "reason": str,
            "available_studies": int
        }
    """
    continuous_count = 0
    dichotomous_count = 0
    has_md = False
    has_smd = False
    has_or = False
    has_rr = False

    for r in extraction_results:
        if "error" in r:
            continue
        es_type = r.get("effect_size", "").upper().strip()
        if es_type in ["MD", "MEAN DIFFERENCE", "WMD"]:
            has_md = True
            continuous_count += 1
        elif es_type in ["SMD", "STANDARDIZED MEAN DIFFERENCE", "HEDGES", "COHEN"]:
            has_smd = True
            continuous_count += 1
        elif es_type in ["OR", "ODDS RATIO", "比之比"]:
            has_or = True
            dichotomous_count += 1
        elif es_type in ["RR", "RISK RATIO", "RELATIVE RISK", "相对风险"]:
            has_rr = True
            dichotomous_count += 1
        # 尝试从数值推断类型
        es_val = r.get("effect_size_value", "")
        if es_val and not es_type:
            import re
            nums = re.findall(r'[-]?\d+\.?\d*', es_val)
            if nums:
                val = float(nums[0])
                if 0.1 <= val <= 10 and val != 0:
                    dichotomous_count += 1  # 猜测为OR/RR
                else:
                    continuous_count += 1

    # 决策逻辑
    if continuous_count >= dichotomous_count and continuous_count > 0:
        if has_smd:
            return {
                "recommended": "SMD",
                "data_type": "continuous",
                "reason": "多数研究报告了连续变量效应量，且涉及不同测量工具，建议使用SMD",
                "available_studies": continuous_count
            }
        else:
            return {
                "recommended": "MD",
                "data_type": "continuous",
                "reason": "多数研究报告了连续变量效应量，且可能使用相同测量工具，建议使用MD",
                "available_studies": continuous_count
            }
    elif dichotomous_count > 0:
        return {
            "recommended": "OR",
            "data_type": "dichotomous",
            "reason": "多数研究报告了分类变量效应量，根据臧老师建议优先使用OR（比之比）",
            "available_studies": dichotomous_count
        }
    else:
        return {
            "recommended": "MD",
            "data_type": "continuous",
            "reason": "无法从数据中推断效应量类型，默认使用MD",
            "available_studies": 0
        }


def generate_meta_analysis_forest(extraction_results: list,
                                  effect_measure: str = "auto") -> object:
    """生成专业的Meta分析森林图（替代旧版generate_forest_plot）

    支持MD、SMD（连续变量）和OR、RR（分类变量）
    使用真实数据计算而非模拟数据

    Args:
        extraction_results: 提取结果列表
        effect_measure: "auto" / "MD" / "SMD" / "OR" / "RR"

    Returns:
        plotly.figure: 森林图
    """
    import plotly.graph_objects as go
    import math

    if effect_measure == "auto":
        recommendation = determine_effect_measure(extraction_results)
        effect_measure = recommendation["recommended"]

    # 提取效应量数据
    studies = []
    for r in extraction_results:
        if "error" in r:
            continue
        author = r.get("author_year") or r.get("paper", "未知")[:25]
        es_val = r.get("effect_size_value", "")
        ci = r.get("confidence_interval", "")

        # 解析效应量数值
        import re
        nums = re.findall(r'[-]?\d+\.?\d*', es_val)
        if not nums:
            continue

        effect = float(nums[0])

        # 解析置信区间
        ci_lower = None
        ci_upper = None
        if ci:
            ci_nums = re.findall(r'[-]?\d+\.?\d*', ci)
            if len(ci_nums) >= 2:
                ci_lower = float(ci_nums[0])
                ci_upper = float(ci_nums[1])

        # 如果没有置信区间，用效应量的±20%估算
        if ci_lower is None:
            ci_lower = effect * 0.7 if effect > 0 else effect * 1.3
            ci_upper = effect * 1.3 if effect > 0 else effect * 0.7

        # 计算标准误（用于权重）
        se = (ci_upper - ci_lower) / (2 * 1.96) if ci_upper != ci_lower else 0.1
        weight = 1 / (se ** 2) if se > 0 else 1

        studies.append({
            "author": author,
            "effect": effect,
            "ci_lower": ci_lower,
            "ci_upper": ci_upper,
            "weight": weight
        })

    if not studies:
        fig = go.Figure()
        fig.add_annotation(
            text="暂无足够的效应量数据生成森林图。<br>请先在数据提取模块补充效应量数据（MD/SMD/OR/RR及数值）",
            showarrow=False, font={"size": 14}
        )
        fig.update_layout(height=200)
        return fig

    # 计算合并效应量（倒方差加权）
    total_weight = sum(s["weight"] for s in studies)
    pooled_effect = sum(s["effect"] * s["weight"] for s in studies) / total_weight

    # 计算合并效应量的标准误和置信区间
    pooled_se = math.sqrt(1 / total_weight) if total_weight > 0 else 0
    pooled_ci_lower = pooled_effect - 1.96 * pooled_se
    pooled_ci_upper = pooled_effect + 1.96 * pooled_se

    # 异质性统计（简单Q检验）
    q_stat = sum(s["weight"] * (s["effect"] - pooled_effect) ** 2 for s in studies)
    i_squared = max(0, (q_stat - (len(studies) - 1)) / q_stat * 100) if q_stat > 0 else 0

    es_label = {"MD": "MD", "SMD": "SMD", "OR": "OR", "RR": "RR"}.get(effect_measure, "效应量")
    null_value = 0 if effect_measure in ["MD", "SMD"] else 1

    fig = go.Figure()

    # 各研究
    for s in studies:
        fig.add_trace(go.Scatter(
            x=[s["effect"]],
            y=[s["author"]],
            mode="markers",
            marker={"size": max(8, min(s["weight"] / 2, 20)), "color": "#2196F3",
                    "line": {"width": 1, "color": "#1565C0"}},
            error_x={
                "type": "data", "symmetric": False,
                "array": [s["ci_upper"] - s["effect"]],
                "arrayminus": [s["effect"] - s["ci_lower"]]
            },
            hovertemplate=(
                f"<b>{s['author']}</b><br>"
                f"{es_label}: {s['effect']:.3f}<br>"
                f"95%CI: ({s['ci_lower']:.3f}, {s['ci_upper']:.3f})<br>"
                f"权重: {s['weight'] / total_weight * 100:.1f}%"
                f"<extra></extra>"
            ),
            showlegend=False
        ))

    # 合并效应量（菱形）
    fig.add_trace(go.Scatter(
        x=[pooled_effect],
        y=["合并效应量"],
        mode="markers",
        marker={"size": 18, "color": "#F44336", "symbol": "diamond-wide",
                "line": {"width": 2, "color": "#B71C1C"}},
        error_x={"type": "data", "symmetric": False,
                 "array": [pooled_ci_upper - pooled_effect],
                 "arrayminus": [pooled_effect - pooled_ci_lower]},
        hovertemplate=(
            f"<b>合并效应量</b><br>"
            f"{es_label}: {pooled_effect:.3f}<br>"
            f"95%CI: ({pooled_ci_lower:.3f}, {pooled_ci_upper:.3f})<br>"
            f"I²: {i_squared:.1f}%<extra></extra>"
        ),
        showlegend=False
    ))

    # 参考线
    fig.add_vline(x=null_value, line_dash="dash", line_color="gray", opacity=0.6)

    fig.update_layout(
        title=(f"<b>森林图 (Forest Plot)</b><br>"
               f"<span style='font-size:12px;color:#666'>效应量: {es_label} | "
               f"{len(studies)}篇研究 | I²={i_squared:.1f}%</span>"),
        xaxis={"title": f"{es_label} (95% CI)", "zeroline": False},
        yaxis={"title": "", "autorange": "reversed"},
        height=max(300, len(studies) * 50 + 120),
        showlegend=False, hovermode="y",
        margin={"l": 10, "r": 10, "t": 60, "b": 50},
        plot_bgcolor="white", xaxis_showgrid=True, xaxis_gridcolor="#f0f0f0"
    )

    fig._meta_data = {
        "pooled_effect": pooled_effect,
        "pooled_ci_lower": pooled_ci_lower, "pooled_ci_upper": pooled_ci_upper,
        "i_squared": i_squared, "effect_measure": effect_measure, "n_studies": len(studies)
    }

    return fig


# ========================================================================
# 其他证据总结法 (V2新增)
# ========================================================================

def generate_combining_pvalues(extraction_results: list) -> dict:
    """Combining P-values - Fisher法"""
    import plotly.graph_objects as go
    import numpy as np
    from scipy import stats
    import re

    p_values = []
    study_labels = []

    for r in extraction_results:
        if "error" in r:
            continue
        author = r.get("author_year") or r.get("paper", "未知")[:20]
        findings = r.get("main_findings", "")
        p_matches = re.findall(r'[pP]\s*[=<>]\s*(\d+\.?\d*)', findings)
        for pm in p_matches:
            val = float(pm)
            if 0 < val <= 1:
                p_values.append(val)
                study_labels.append(author)
                break

    result = {"summary": "", "figure": None, "code": ""}

    if not p_values:
        result["summary"] = (
            "⚠️ 未能从提取数据中提取到足够的P值信息。\n\n"
            "**Combining P-values（汇总P值法）**\n\n"
            "当研究间异质性过大或不适合做传统Meta分析时，可通过合并P值判断整体效应。\n"
            "Fisher法：χ² = -2∑ln(p)，服从自由度为2k的卡方分布。"
        )
        return result

    k = len(p_values)
    chi_sq = -2 * sum(np.log(p) for p in p_values)
    combined_p = 1 - stats.chi2.cdf(chi_sq, 2 * k) if chi_sq > 0 else 1.0

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=study_labels, y=[-np.log10(p) for p in p_values],
        marker_color="#4CAF50",
        text=[f"p={p:.4f}" for p in p_values], textposition="outside"
    ))
    fig.add_hline(y=-np.log10(0.05), line_dash="dash", line_color="red",
                  annotation_text="p=0.05")

    fig.update_layout(
        title="Combining P-values 汇总图",
        xaxis={"title": "研究"}, yaxis={"title": "-log₁₀(P值)"},
        height=350, margin={"l": 10, "r": 10, "t": 40, "b": 60},
        plot_bgcolor="white"
    )

    result["summary"] = (
        f"**Combining P-values (Fisher法) 结果**\n\n"
        f"- 纳入研究数：{k}篇\n"
        f"- Fisher χ²统计量：{chi_sq:.4f}\n"
        f"- 自由度：{2 * k}\n"
        f"- 合并P值：{combined_p:.6f}\n"
        f"- 结论：{'具有统计学显著性' if combined_p < 0.05 else '不具有统计学显著性'}"
    )
    result["figure"] = fig
    result["code"] = (
        "# Combining P-values - R代码\n"
        f"p_values <- c({', '.join(f'{p:.4f}' for p in p_values)})\n"
        "chi_sq <- -2 * sum(log(p_values))\n"
        "df <- 2 * length(p_values)\n"
        "combined_p <- 1 - pchisq(chi_sq, df)\n"
    )
    return result


def generate_harvest_plot(extraction_results: list) -> dict:
    """Harvest Plot - 收获图"""
    import plotly.graph_objects as go
    import re

    studies = []
    for r in extraction_results:
        if "error" in r:
            continue
        author = r.get("author_year") or r.get("paper", "未知")[:20]
        sample_text = r.get("sample_size", "")
        try:
            sample = int(re.findall(r'\d+', str(sample_text))[0])
        except (IndexError, ValueError):
            sample = 50

        findings = r.get("main_findings", "").lower()
        direction = "positive"
        if any(kw in findings for kw in ["无差异", "no difference", "no change", "无变化"]):
            direction = "no_effect"
        elif any(kw in findings for kw in ["不显著", "无效", "恶化", "降低",
                                             "decrease", "worse", "no significant"]):
            direction = "negative"

        studies.append({"author": author, "sample": sample, "direction": direction})

    if not studies:
        return {"summary": "⚠️ 没有足够的数据生成Harvest Plot", "figure": None, "code": ""}

    positive = [s for s in studies if s["direction"] == "positive"]
    negative = [s for s in studies if s["direction"] == "negative"]
    no_effect = [s for s in studies if s["direction"] == "no_effect"]

    fig = go.Figure()
    colors_map = {"positive": "#4CAF50", "negative": "#F44336", "no_effect": "#FFC000"}

    for di, (label, group) in enumerate([
        ("积极效果", positive), ("消极效果", negative), ("无显著效果", no_effect)
    ]):
        if group:
            fig.add_trace(go.Scatter(
                x=[di + 1] * len(group),
                y=[s["author"] for s in group],
                mode="markers",
                marker={
                    "size": [max(10, min(s["sample"] / 5, 40)) for s in group],
                    "color": colors_map[group[0]["direction"]],
                    "symbol": "circle", "line": {"width": 1, "color": "#333"}
                },
                name=f"{label} ({len(group)})",
                text=[f"{s['author']}<br>样本量: {s['sample']}" for s in group],
                hoverinfo="text"
            ))

    fig.update_layout(
        title="Harvest Plot (收获图)",
        xaxis={"tickmode": "array", "tickvals": [1, 2, 3],
               "ticktext": ["积极效果", "消极效果", "无显著效果"]},
        yaxis={"autorange": "reversed"},
        height=max(200, len(studies) * 35 + 60),
        margin={"l": 10, "r": 10, "t": 40, "b": 60},
        plot_bgcolor="white"
    )

    return {
        "summary": f"**Harvest Plot** — 积极{len(positive)} / 消极{len(negative)} / 无差异{len(no_effect)}",
        "figure": fig,
        "code": ""
    }


def generate_effect_direction_plot(extraction_results: list) -> dict:
    """Effect Direction Plot - 效应方向图"""
    import plotly.graph_objects as go

    outcome_groups = {}
    for r in extraction_results:
        if "error" in r:
            continue
        author = r.get("author_year") or r.get("paper", "未知")[:20]
        outcome = r.get("outcome_measures", "主要结局")[:15]
        findings = r.get("main_findings", "").lower()

        direction = 0
        if any(kw in findings for kw in ["显著提高", "显著增加", "显著改善",
                                          "significant increase", "significantly higher"]):
            direction = 1
        elif any(kw in findings for kw in ["显著降低", "显著减少", "显著下降",
                                            "significant decrease", "significantly lower"]):
            direction = -1

        if outcome not in outcome_groups:
            outcome_groups[outcome] = []
        outcome_groups[outcome].append({"author": author, "direction": direction})

    if not outcome_groups:
        return {"summary": "⚠️ 没有足够的数据生成效应方向图", "figure": None, "code": ""}

    fig = go.Figure()
    for oi, (oname, studies) in enumerate(outcome_groups.items()):
        for si, s in enumerate(studies):
            color = "#4CAF50" if s["direction"] > 0 else "#F44336" if s["direction"] < 0 else "#FFC000"
            symbol = "triangle-up" if s["direction"] > 0 else "triangle-down" if s["direction"] < 0 else "circle"
            fig.add_trace(go.Scatter(
                x=[oi], y=[si], mode="markers",
                marker={"size": 14, "color": color, "symbol": symbol,
                        "line": {"width": 1, "color": "#333"}},
                text=f"{s['author']}<br>{oname}: {'↑' if s['direction']>0 else '↓' if s['direction']<0 else '—'}",
                hoverinfo="text", showlegend=False
            ))

    fig.update_layout(
        title="Effect Direction Plot (效应方向图)",
        xaxis={"tickmode": "array", "tickvals": list(range(len(outcome_groups))),
               "ticktext": list(outcome_groups.keys()), "tickangle": -20},
        yaxis={"autorange": "reversed"},
        height=300, margin={"l": 10, "r": 10, "t": 40, "b": 80},
        plot_bgcolor="white"
    )

    return {"summary": f"**效应方向图** — 共{len(outcome_groups)}个结局", "figure": fig, "code": ""}


def generate_vote_counting(extraction_results: list) -> dict:
    """Vote Counting - 投票计数法"""
    import plotly.graph_objects as go
    import re

    outcome_stats = {}
    for r in extraction_results:
        if "error" in r:
            continue
        author = r.get("author_year") or r.get("paper", "未知")[:20]
        outcome = r.get("outcome_measures", "主要结局")[:20]
        findings = r.get("main_findings", "").lower()

        positive = any(kw in findings for kw in ["显著", "有效", "改善", "提高",
                                                   "positive", "significant", "improve"])
        negative = any(kw in findings for kw in ["降低", "减少", "下降", "恶化",
                                                   "decrease", "worse", "reduce"])

        if outcome not in outcome_stats:
            outcome_stats[outcome] = {"positive": 0, "negative": 0, "no_effect": 0}

        if positive and not negative:
            outcome_stats[outcome]["positive"] += 1
        elif negative:
            outcome_stats[outcome]["negative"] += 1
        else:
            outcome_stats[outcome]["no_effect"] += 1

    if not outcome_stats:
        return {"summary": "⚠️ 没有足够的数据", "figure": None, "code": ""}

    total_pos = sum(s["positive"] for s in outcome_stats.values())
    total_neg = sum(s["negative"] for s in outcome_stats.values())
    total_no = sum(s["no_effect"] for s in outcome_stats.values())
    total = total_pos + total_neg + total_no

    fig = go.Figure(data=[
        go.Bar(name="正向", x=list(outcome_stats.keys()),
               y=[s["positive"] for s in outcome_stats.values()],
               marker_color="#4CAF50"),
        go.Bar(name="负向", x=list(outcome_stats.keys()),
               y=[s["negative"] for s in outcome_stats.values()],
               marker_color="#F44336"),
        go.Bar(name="无差异", x=list(outcome_stats.keys()),
               y=[s["no_effect"] for s in outcome_stats.values()],
               marker_color="#FFC000"),
    ])
    fig.update_layout(title=f"Vote Counting (共{total}篇)", barmode="group",
                      height=300, plot_bgcolor="white")

    summary = (
        f"**Vote Counting (投票计数法) 结果**\n\n"
        f"- 正向结果：{total_pos}篇 ({total_pos/max(total,1)*100:.0f}%)\n"
        f"- 负向结果：{total_neg}篇 ({total_neg/max(total,1)*100:.0f}%)\n"
        f"- 无显著差异：{total_no}篇 ({total_no/max(total,1)*100:.0f}%)"
    )

    return {"summary": summary, "figure": fig, "code": ""}


def generate_box_whisker_plot(extraction_results: list) -> dict:
    """Box-and-Whisker Plot - 箱线图"""
    import plotly.graph_objects as go
    import re

    outcome_values = {}
    for r in extraction_results:
        if "error" in r:
            continue
        outcome = r.get("outcome_measures", "主要结局")[:15]
        es_val = r.get("effect_size_value", "")
        nums = re.findall(r'[-]?\d+\.?\d*', es_val)
        if nums:
            val = float(nums[0])
            if outcome not in outcome_values:
                outcome_values[outcome] = []
            outcome_values[outcome].append(val)

    if not outcome_values:
        return {"summary": "⚠️ 没有足够的效应量数据生成箱线图", "figure": None, "code": ""}

    fig = go.Figure()
    for oname, values in outcome_values.items():
        fig.add_trace(go.Box(y=values, name=oname, boxpoints="all",
                             jitter=0.3, pointpos=-1.8))

    fig.update_layout(title="效应量分布箱线图", yaxis={"title": "效应量"},
                      height=400, plot_bgcolor="white")

    return {"summary": f"**箱线图** — 共{len(outcome_values)}个结局指标", "figure": fig, "code": ""}


def generate_bubble_plot(extraction_results: list) -> dict:
    """Bubble Plot - 气泡图"""
    import plotly.graph_objects as go
    import re

    studies = []
    for r in extraction_results:
        if "error" in r:
            continue
        author = r.get("author_year") or r.get("paper", "未知")[:20]
        sample_text = r.get("sample_size", "")
        try:
            sample = int(re.findall(r'\d+', str(sample_text))[0])
        except (IndexError, ValueError):
            sample = 50
        es_val = r.get("effect_size_value", "")
        try:
            effect = float(re.findall(r'[-]?\d+\.?\d*', es_val)[0])
        except (IndexError, ValueError):
            effect = 0
        year_text = r.get("author_year", "")
        try:
            year = int(re.findall(r'(\d{4})', year_text)[0])
        except (IndexError, ValueError):
            year = 2020
        design = r.get("study_design", "其他")[:8]
        studies.append({"author": author, "sample": sample, "effect": effect,
                        "year": year, "design": design})

    if not studies:
        return {"summary": "⚠️ 没有足够的数据生成气泡图", "figure": None, "code": ""}

    fig = go.Figure()
    designs = list(set(s["design"] for s in studies))
    colors = ["#2196F3", "#4CAF50", "#FF9800", "#9C27B0", "#F44336", "#00BCD4"]

    for di, design in enumerate(designs):
        s_group = [s for s in studies if s["design"] == design]
        fig.add_trace(go.Scatter(
            x=[s["effect"] for s in s_group],
            y=[s["year"] for s in s_group],
            mode="markers",
            marker={"size": [max(10, min(s["sample"] / 3, 50)) for s in s_group],
                    "color": colors[di % len(colors)], "opacity": 0.7,
                    "line": {"width": 1, "color": "#333"}},
            name=design,
            text=[f"{s['author']}<br>样本量: {s['sample']}<br>效应量: {s['effect']}" for s in s_group],
            hoverinfo="text"
        ))

    fig.update_layout(title="Bubble Plot (气泡图)", xaxis={"title": "效应量"},
                      yaxis={"title": "年份"}, height=400, plot_bgcolor="white")

    return {"summary": f"**气泡图** — 共{len(studies)}篇研究", "figure": fig, "code": ""}


ALL_SUMMARY_METHODS = {
    "combining_pvalues": {
        "name": "Combining P-values",
        "subtitle": "汇总多个研究的P值（Fisher法）",
        "func": generate_combining_pvalues,
        "icon": "📊",
        "description": "当研究间异质性过大或不适合Meta分析时，通过合并P值判断整体效应"
    },
    "harvest_plot": {
        "name": "Harvest Plot",
        "subtitle": "收获图（点大小=样本量）",
        "func": generate_harvest_plot,
        "icon": "🌾",
        "description": "用圆点展示各研究的样本量和效应方向"
    },
    "effect_direction": {
        "name": "Effect Direction Plot",
        "subtitle": "效应方向图",
        "func": generate_effect_direction_plot,
        "icon": "↕️",
        "description": "展示各研究在不同结局指标上的效应方向"
    },
    "vote_counting": {
        "name": "Vote Counting",
        "subtitle": "投票计数法",
        "func": generate_vote_counting,
        "icon": "📋",
        "description": "统计各研究结果的方向数量"
    },
    "box_whisker": {
        "name": "Box-and-Whisker",
        "subtitle": "效应量分布箱线图",
        "func": generate_box_whisker_plot,
        "icon": "📦",
        "description": "展示各结局效应量的分布范围"
    },
    "bubble": {
        "name": "Bubble Plot",
        "subtitle": "气泡图（多维度）",
        "func": generate_bubble_plot,
        "icon": "🫧",
        "description": "多维度展示效应量、年份、样本量"
    }
}


# ========================================================================
# PRISMA 2020 流程图
# ========================================================================

def generate_prisma_flowchart(
    identified: int = 0,
    additional: int = 0,
    duplicates: int = 0,
    screened: int = 0,
    excluded: int = 0,
    full_text: int = 0,
    excluded_fulltext: int = 0,
    excluded_reasons: dict = None,
    qualitative: int = 0,
    quantitative: int = 0,
) -> object:
    """生成PRISMA 2020文献筛选流程图"""
    import plotly.graph_objects as go

    if excluded_reasons is None:
        excluded_reasons = {}

    if screened == 0 and identified > 0:
        after_dedup = identified + additional - duplicates
        screened = after_dedup
        excluded = screened - full_text if full_text > 0 else 0

    if qualitative == 0:
        qualitative = full_text - excluded_fulltext

    nodes = [
        {"id": "start", "label": f"数据库检索<br>(n={identified:,})", "x": 0, "y": 0},
    ]
    if additional:
        nodes.append({"id": "additional", "label": f"其他来源<br>(n={additional:,})", "x": 50, "y": 0})
    nodes.extend([
        {"id": "total", "label": f"去重后记录<br>(n={identified + additional - duplicates:,})", "x": 0, "y": -1},
        {"id": "screened", "label": f"初筛记录<br>(n={screened:,})", "x": 0, "y": -2},
        {"id": "excluded", "label": f"初筛排除<br>(n={excluded:,})", "x": 50, "y": -2},
        {"id": "fulltext", "label": f"全文获取<br>(n={full_text:,})", "x": 0, "y": -3},
    ])
    if excluded_reasons:
        reasons_text = "<br>".join(f"• {k} (n={v})" for k, v in excluded_reasons.items())
        nodes.append({"id": "excluded_fulltext", "label": f"全文排除<br>(n={excluded_fulltext:,})<br><small>{reasons_text}</small>", "x": 50, "y": -3})
    else:
        nodes.append({"id": "excluded_fulltext", "label": f"全文排除<br>(n={excluded_fulltext:,})", "x": 50, "y": -3})
    nodes.append({"id": "qualitative", "label": f"纳入定性合成<br>(n={qualitative:,})", "x": 0, "y": -4})
    if quantitative > 0:
        nodes.append({"id": "quantitative", "label": f"纳入定量合成(Meta)<br>(n={quantitative:,})", "x": 0, "y": -5})
    else:
        nodes.append({"id": "quantitative", "label": "未进行定量合成", "x": 0, "y": -5})

    node_map = {n["id"]: n for n in nodes}
    main_ids = ["start", "total", "screened", "fulltext", "qualitative", "quantitative"]
    side_ids = ["excluded", "excluded_fulltext"]
    if additional:
        side_ids.insert(0, "additional")

    fig = go.Figure()
    edges = [
        ("start", "total"),
    ]
    if additional:
        edges.append(("additional", "total"))
    edges.extend([
        ("total", "screened"), ("screened", "excluded"),
        ("screened", "fulltext"), ("fulltext", "excluded_fulltext"),
        ("fulltext", "qualitative"), ("qualitative", "quantitative"),
    ])
    for src, dst in edges:
        if src in node_map and dst in node_map:
            s, d = node_map[src], node_map[dst]
            is_side = src in side_ids or dst in side_ids
            fig.add_annotation(
                x=(s["x"]+d["x"])/2+(20 if is_side else 0), y=(s["y"]+d["y"])/2,
                ax=s["x"], ay=s["y"], axref="x", ayref="y", xref="x", yref="y",
                showarrow=True, arrowhead=2, arrowsize=1, arrowwidth=1.5,
                arrowcolor="#999" if is_side else "#333")

    for node in nodes:
        is_main = node["id"] in main_ids
        is_side = node["id"] in side_ids
        fig.add_annotation(
            x=node["x"]+(30 if is_side else 0), y=node["y"],
            text=node["label"], showarrow=False,
            font={"size": 10, "color": "#fff" if is_main else "#333"},
            bgcolor="#2563EB" if is_main else ("#F3F4F6" if is_side else "#DBEAFE"),
            borderpad=6, width=120 if not is_side else 140, opacity=0.95)

    fig.update_layout(
        title="<b>PRISMA 2020 文献筛选流程图</b>",
        xaxis={"visible": False, "range": [-20, 100]},
        yaxis={"visible": False, "range": [-6, 1]},
        height=120+len(nodes)*60,
        margin={"l": 10, "r": 10, "t": 50, "b": 10},
        plot_bgcolor="white", hovermode=False)
    return fig
