"""
报告生成模块 - 成果报告 + 过程报告
"""
import json
import logging
from datetime import datetime
from typing import Callable, Optional

logger = logging.getLogger(__name__)


def generate_full_report(session_data: dict) -> str:
    """生成完整的文献综述报告 (Markdown格式)

    Args:
        session_data: 会话数据，包含文献信息、提取结果、评价结果、合成结果

    Returns:
        str: 报告Markdown文本
    """
    papers = session_data.get("papers", [])
    extraction = session_data.get("extraction_results", [])
    rob = session_data.get("rob_results", [])
    synthesis_text = session_data.get("synthesis_text", "")

    now = datetime.now().strftime("%Y年%m月%d日")
    total_papers = len(papers)
    extracted = len([r for r in extraction if "error" not in r])

    lines = [
        "---",
        "title: 文献综述报告",
        f"date: {now}",
        "---",
        "",
        "# 文献综述报告",
        "",
        f"> 由循证分析智能体辅助生成 | 生成日期: {now}",
        "",
        "## 摘要",
        "",
        f"本综述共纳入 {total_papers} 篇文献，完成数据提取 {extracted} 篇。",
        "本报告由AI辅助生成，学生已审核确认提取数据的准确性。",
        "",
        "## 1. 引言",
        "",
        "（请在此补充研究背景和目的）",
        "",
        "## 2. 方法",
        "",
        "### 2.1 文献纳入标准",
        "（请在此补充PICOT和纳入/排除标准）",
        "",
        "### 2.2 检索策略",
        "（请在此补充检索数据库、检索式和检索时间）",
        "",
        "### 2.3 数据提取",
        f"由循证分析智能体按照标准化模板提取数据，学生逐条审核确认。共提取 {extracted}/{total_papers} 篇文献数据。",
        "",
        "### 2.4 质量评价",
        "采用Cochrane偏倚风险评价工具（针对RCT）或相应评价工具（针对非RCT研究），由AI辅助评价，学生审核确认。",
        "",
        "### 2.5 分析方法",
        "（请在此补充使用的分析方法，如叙事性合成/Meta分析等）",
        "",
        "## 3. 结果",
        "",
        "### 3.1 文献筛选结果",
        f"共纳入 {total_papers} 篇文献。",
        "",
        "### 3.2 研究特征",
        "",
    ]

    # 研究特征表
    if extraction:
        lines.append("| 作者/年份 | 研究设计 | 样本量 | 研究对象 | 主要结局指标 |")
        lines.append("|-----------|---------|--------|---------|------------|")
        for r in extraction:
            if "error" in r:
                continue
            lines.append(
                f"| {r.get('author_year', '未知')[:20]} "
                f"| {r.get('study_design', '')[:15]} "
                f"| {r.get('sample_size', '')} "
                f"| {r.get('population', '')[:25]} "
                f"| {r.get('outcome_measures', '')[:25]} |"
            )
        lines.append("")

    # 质量评价
    if rob:
        lines.append("### 3.3 质量评价结果")
        lines.append("")
        lines.append("| 文献 | 总体评价 |")
        lines.append("|------|---------|")
        label = {
            "low": "低偏倚风险", "some_concerns": "有一些担忧", "high": "高偏倚风险",
            "strong": "质量强", "moderate": "质量中等", "weak": "质量弱",
            "unclear": "偏倚风险不清楚",
        }
        for r in rob:
            overall = label.get(r.get("overall", ""), "不清楚")
            lines.append(f"| {r.get('paper_title', '')[:30]} | {overall} |")
        lines.append("")

    # 描述性总结
    if extraction:
        lines.append("### 3.4 描述性总结")
        lines.append("")
        for r in extraction:
            if "error" in r:
                continue
            author = r.get("author_year", r.get("paper", "未知"))
            findings = r.get("main_findings", "")
            lines.append(f"- **{author}**：{findings[:100]}")
        lines.append("")

    # 合成结果
    if synthesis_text:
        lines.append("### 3.5 证据合成结果")
        lines.append("")
        lines.append(synthesis_text[:500])
        lines.append("")

    # 讨论与结论
    lines.extend([
        "## 4. 讨论",
        "",
        "（请在此补充对研究结果的讨论）",
        "",
        "## 5. 结论",
        "",
        "（请在此补充本综述的主要结论）",
        "",
        "## 参考文献",
        "",
    ])

    for idx, r in enumerate(extraction, 1):
        if "error" in r:
            continue
        author = r.get("author_year", r.get("paper", "未知"))
        title = r.get("title", "未报告标题")
        lines.append(f"[{idx}] {author}. {title}.")

    return "\n".join(lines)


def generate_process_report(session_data: dict) -> str:
    """生成过程性工作报告

    记录学生与AI交互的全过程，供教师评估学习投入度
    """
    log = session_data.get("process_log", [])
    papers = session_data.get("papers", [])
    extraction = session_data.get("extraction_results", [])
    rob = session_data.get("rob_results", [])

    now = datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")

    lines = [
        "# 过程性工作报告",
        "",
        f"> 生成时间: {now}",
        "",
        "## 1. 基本统计",
        "",
        f"- 上传文献数: {len(papers)} 篇",
        f"- 完成提取数: {len([r for r in extraction if 'error' not in r])} 篇",
        f"- 完成质量评价: {len(rob)} 篇",
        f"- 操作记录数: {len(log)} 条",
        "",
        "## 2. 操作时间线",
        "",
    ]

    if log:
        lines.append("| 时间 | 操作 | 详情 |")
        lines.append("|------|------|------|")
        for entry in log:
            t = entry.get("time", "")[:19]
            op = entry.get("operation", "")
            detail = entry.get("detail", "")[:50]
            lines.append(f"| {t} | {op} | {detail} |")
    else:
        lines.append("（无详细操作记录）")
    lines.append("")

    # 提取结果修改记录
    modified = [r for r in extraction if r.get("_student_modified")]
    if modified:
        lines.append(f"## 3. 学生修改记录")
        lines.append("")
        lines.append(f"学生共修改了 {len(modified)} 篇文献的提取数据：")
        for r in modified:
            lines.append(f"- {r.get('paper', '')}")
        lines.append("")

    # 教师评估区
    lines.extend([
        "## 4. 教师评估",
        "",
        "| 评估维度 | 评分 (1-5) | 备注 |",
        "|---------|-----------|------|",
        "| 文献上传完整性 | | |",
        "| 数据审核仔细程度 | | |",
        "| 质量评价参与度 | | |",
        "| 报告撰写质量 | | |",
        "| 总体学习投入度 | | |",
        "",
        "**教师综合评价**：",
        "",
        "（教师在此填写综合评价和建议）",
        "",
        "---",
        "*本报告由循证分析智能体自动生成。*",
    ])

    return "\n".join(lines)


def export_to_markdown(report_text: str) -> bytes:
    """导出为Markdown文件

    Returns:
        bytes: 文件内容的字节数据
    """
    return report_text.encode("utf-8")


def add_process_log(session_data: dict, operation: str, detail: str = ""):
    """向过程日志中添加一条记录"""
    if "process_log" not in session_data:
        session_data["process_log"] = []
    session_data["process_log"].append({
        "time": datetime.now().isoformat(),
        "operation": operation,
        "detail": detail
    })


# ========================================================================
# 引用格式模块 (V2新增)
# ========================================================================

def format_apa_citation(author_year: str, title: str = "", journal: str = "",
                         volume: str = "", pages: str = "", doi: str = "") -> str:
    """生成APA格式参考文献

    APA 7th: Author, A. A., & Author, B. B. (Year). Title of article.
    Journal Name, Volume(Issue), page-page. DOI
    """
    # 解析作者和年份
    import re
    year_match = re.search(r'(\d{4})', author_year)
    year = year_match.group(1) if year_match else "年份不详"

    # 提取作者部分（去掉年份）
    author_part = re.sub(r'\d{4}', '', author_year).strip().rstrip(',').strip()

    if not author_part:
        author_part = "佚名"

    # APA格式：作者 (年份)
    citation = f"{author_part} ({year})"

    if title:
        title_formatted = title.strip()
        if not title_formatted.endswith('.'):
            title_formatted += '.'
        citation += f". {title_formatted}"

    if journal:
        journal_formatted = journal.strip()
        if not journal_formatted.endswith('.'):
            journal_formatted += '.'
        citation += f" *{journal_formatted}*"

    if volume:
        citation += f" *{volume}*"

    if pages:
        pages = pages.strip().strip(':,').strip()
        citation += f", {pages}"

    if doi:
        doi = doi.strip()
        if not doi.startswith('https://'):
            citation += f". https://doi.org/{doi}"
        else:
            citation += f". {doi}"
    else:
        citation += "."

    return citation


def format_chinese_citation(author_year: str, title: str = "", journal: str = "",
                             volume: str = "", pages: str = "", doi: str = "") -> str:
    """生成中文参考文献格式（GB/T 7714风格）

    作者. 题名[J]. 刊名, 年, 卷(期): 页码.
    """
    import re

    # 解析作者和年份
    year_match = re.search(r'(\d{4})', author_year)
    year = year_match.group(1) if year_match else "年份不详"
    author_part = re.sub(r'\d{4}', '', author_year).strip().rstrip(',').strip()

    if not author_part:
        author_part = "佚名"

    # 中文格式
    parts = [f"{author_part}."]

    if title:
        title_clean = title.strip().rstrip('.')
        parts.append(f" {title_clean}[J].")

    if journal:
        journal_clean = journal.strip().rstrip('.')
        parts.append(f" {journal_clean},")

    parts.append(f" {year},")

    if volume:
        parts.append(f" {volume}")
        # 如果有期号
        issue_match = re.search(r'\((\d+)\)', volume)
        if not issue_match:
            pass  # 没有期号

    if pages:
        pages_clean = pages.strip().strip(':,').strip()
        parts.append(f": {pages_clean}.")

    else:
        parts.append(".")

    if doi:
        parts.append(f" {doi}.")

    return "".join(parts)


def format_references(papers: list, style: str = "apa") -> list:
    """批量格式化参考文献，自动处理同名/同年作者的消歧

    Args:
        papers: 文献列表，每篇包含 author_year, title, journal 等字段
        style: "apa" 或 "chinese"

    Returns:
        list: 格式化后的参考文献列表（已消歧）
    """
    # 先格式化所有条目
    refs = []
    paper_data = []

    for p in papers:
        if isinstance(p, dict):
            author_year = p.get("author_year", p.get("paper", "未知"))
            title = p.get("title", "")
            journal = p.get("journal", "")
            volume = p.get("volume", "")
            pages = p.get("pages", "")
            doi = p.get("doi", "")

            if style == "apa":
                ref = format_apa_citation(author_year, title, journal, volume, pages, doi)
            else:
                ref = format_chinese_citation(author_year, title, journal, volume, pages, doi)

            refs.append(ref)
            paper_data.append({"author_year": author_year, "ref": ref})
        else:
            refs.append(str(p))

    # 作者消歧：检测同名+同年作者
    # 规则：第一作者相同且年份相同 → 增加第二作者姓氏 → 若还相同加第三作者…
    # 如果所有作者相同且年份相同 → 年份加 a,b,c,d 上标
    from collections import Counter
    ay_counts = Counter(p.get("author_year", "") for p in papers if isinstance(p, dict))

    author_year_groups = {}
    for p in papers:
        if isinstance(p, dict):
            ay = p.get("author_year", "")
            if ay in ay_counts and ay_counts[ay] > 1:
                if ay not in author_year_groups:
                    author_year_groups[ay] = []
                author_year_groups[ay].append(p)

    # 对每组同名同年进行消歧
    for ay, group in author_year_groups.items():
        if len(group) < 2:
            continue

        # 尝试用更多作者信息区分
        year_match = re.search(r'(\d{4})', ay)
        base_year = year_match.group(1) if year_match else ""

        # 检测是否所有作者姓名相同
        first_authors = []
        for p in group:
            p_ay = p.get("author_year", ay)
            author_part = re.sub(r'\d{4}', '', p_ay).strip().rstrip(',').strip()
            first_authors.append(author_part)

        all_same_author = len(set(first_authors)) == 1

        for idx, p in enumerate(group):
            orig_ay = p.get("author_year", "")
            # 尝试获取更多作者信息从paper title或其它字段
            # 使用 title 的首字母作为辅助区分
            title_first = ""
            if p.get("title"):
                title_first = p.get("title", "").strip()
                # 取标题前2-3个字的拼音首字母

            if all_same_author:
                # 所有作者相同 → 年份加上标 a,b,c,d
                suffix = chr(97 + idx)  # a, b, c, d...
                new_ay = re.sub(r'(\d{4})', rf'\1{suffix}', orig_ay)
            else:
                # 不同第一作者但年份相同 → 已自然区分，不需额外处理
                continue

            # 更新对应参考文献
            for ri, r in enumerate(refs):
                if ri < len(papers) and isinstance(papers[ri], dict):
                    if papers[ri].get("author_year") == orig_ay and papers[ri].get("title") == p.get("title"):
                        # 重新格式化
                        if style == "apa":
                            refs[ri] = format_apa_citation(
                                new_ay, p.get("title", ""), p.get("journal", ""),
                                p.get("volume", ""), p.get("pages", ""), p.get("doi", "")
                            )
                        else:
                            refs[ri] = format_chinese_citation(
                                new_ay, p.get("title", ""), p.get("journal", ""),
                                p.get("volume", ""), p.get("pages", ""), p.get("doi", "")
                            )
                        break

    return refs


def render_references(refs: list, style: str = "apa") -> str:
    """生成参考文献列表的Markdown文本"""
    lines = [
        "## 参考文献",
        "",
        f"> 格式：{'APA 7th' if style == 'apa' else 'GB/T 7714-2015 中文'}",
        "",
    ]

    for i, ref in enumerate(refs, 1):
        lines.append(f"[{i}] {ref}")

    return "\n".join(lines)


# ========================================================================
# Discussion生成 (V2新增)
# ========================================================================

def generate_discussion_outline(session_data: dict,
                                call_llm_func: Callable = None) -> str:
    """生成Discussion大纲

    1. 从提取结果中提取关键词
    2. 调用LLM生成讨论框架
    3. 包含：主要发现总结、与外部证据比较、局限性、未来方向

    Args:
        session_data: 会话数据
        call_llm_func: LLM调用函数（可选）

    Returns:
        str: Discussion Markdown文本
    """
    extraction = session_data.get("extraction_results", [])
    synthesis = session_data.get("synthesis_text", "")
    rob = session_data.get("rob_results", [])

    # 提取关键信息
    n_studies = len([r for r in extraction if "error" not in r])
    designs = set()
    outcomes = set()
    key_findings = []

    for r in extraction:
        if "error" in r:
            continue
        design = r.get("study_design", "")
        if design:
            designs.add(design)
        outcome = r.get("outcome_measures", "")
        if outcome:
            outcomes.add(outcome)
        findings = r.get("main_findings", "")
        if findings:
            key_findings.append(findings[:150])

    # 质量总结
    quality_summary = ""
    if rob:
        low = sum(1 for r in rob if r.get("overall") in ["low", "strong"])
        moderate = sum(1 for r in rob if r.get("overall") in ["some_concerns", "moderate"])
        high = sum(1 for r in rob if r.get("overall") in ["high", "weak"])
        quality_summary = (
            f"\n- 质量评价：{low}篇高质量，{moderate}篇中等质量，{high}篇低质量"
        )

    lines = [
        "## 讨论 (Discussion)",
        "",
        "### 4.1 主要发现总结",
        "",
    ]

    if key_findings:
        # 尝试归纳
        lines.append("本综述纳入了{}篇研究，主要聚焦于{}。".format(
            n_studies,
            "、".join(list(outcomes)[:3]) if outcomes else "相关结局指标"
        ))
        lines.append("")
        lines.append("总体而言，纳入研究的结果表明：")
        lines.append("")
        for f in key_findings[:3]:
            lines.append(f"- {f[:100]}…")
        lines.append("")
    else:
        lines.append("（请在此补充主要发现总结）")
        lines.append("")

    lines.extend([
        "### 4.2 与现有证据的比较",
        "",
        "（💡 **V2功能提示**：点击下方按钮，AI将搜索外部开源文献，",
        "比较本综述发现与其他类似研究的异同。",
        "此过程将排除已纳入本综述的文献。）",
        "",
        "<!-- Discussion自动生成结果将插入此处 -->",
        "",
        "### 4.3 优势与局限性",
        "",
        "#### 优势",
        "- 采用标准化工具进行质量评价（{}）".format(
            "、".join(list(designs)[:2]) if designs else "标准化工具"
        ),
        "- 系统化的数据提取和分析流程",
        "",
        "#### 局限性",
        "- 纳入研究的数量和质量限制",
        "- 可能存在发表偏倚",
        "- （请根据实际情况补充）",
        "",
        "### 4.4 对未来研究的启示",
        "",
        "（请在此补充对未来研究的建议）",
        "",
    ])

    lines.append(quality_summary)
    lines.append("")

    return "\n".join(lines)


def search_external_evidence(extraction_results: list, call_llm_func: Callable) -> str:
    """搜索外部开源文献并生成比较分析

    使用LLM内部知识模拟外部文献搜索（因实际API访问受限）
    实际部署时可接入OpenAlex/CrossRef等学术搜索API

    Args:
        extraction_results: 提取结果列表
        call_llm_func: LLM调用函数

    Returns:
        str: 外部证据比较结果
    """
    # 提取PICOT和关键词
    outcomes = set()
    populations = set()
    interventions = set()
    author_list = []

    for r in extraction_results:
        if "error" in r:
            continue
        outcome = r.get("outcome_measures", "")
        if outcome:
            outcomes.add(outcome)
        pop = r.get("population", "")
        if pop:
            populations.add(pop[:50])
        intervention = r.get("intervention", "")
        if intervention:
            interventions.add(intervention[:50])
        author = r.get("author_year", "")
        if author:
            author_list.append(author[:30])

    # 用LLM生成外部证据比较
    system_prompt = """你是一名系统综述方法学专家。你的任务是根据已纳入综述的文献信息，
搜索你知识库中类似的开源研究/综述，进行证据比较。

要求：
1. 排除已纳入的文献（用户提供列表）
2. 基于你的训练知识，生成类似于Discussion中"与现有证据比较"的段落
3. 如果找到了类似的综述，比较它们的发现与本综述的异同
4. 指明本综述在整个证据链中的定位
5. 附上你能确认的参考文献（作者、年份）

注意：不要编造不存在的文献。如果无法确定具体文献，就说"据已有知识"。"""

    user_prompt = (
        f"本综述已纳入以下文献（请排除这些）：\n{', '.join(author_list)}\n\n"
        f"研究人群：{'、'.join(list(populations)[:3])}\n"
        f"干预措施：{'、'.join(list(interventions)[:3])}\n"
        f"结局指标：{'、'.join(list(outcomes)[:3])}\n\n"
        f"请生成一段Discussion的外部证据比较内容。"
    )

    try:
        if call_llm_func:
            result = call_llm_func(system_prompt, user_prompt)
            return result if result else "（外部证据搜索暂不可用，请补充手动搜索）"
        else:
            return "（需配置API Key后方可进行外部证据搜索）"
    except Exception as e:
        logger.warning(f"外部证据搜索失败: {e}")
        return "（外部证据搜索失败，请检查API配置后重试）"


# ========================================================================
# 润色功能 (V2新增)
# ========================================================================

def polish_text(text: str, style: str = "academic", call_llm_func: Callable = None) -> str:
    """对文本进行学术润色

    Args:
        text: 待润色的文本
        style: "academic"（学术）或 "concise"（简洁）
        call_llm_func: LLM调用函数

    Returns:
        str: 润色后的文本
    """
    if not call_llm_func:
        return "润色功能需要配置API Key"

    system_prompt = """你是一名学术写作编辑专家。请对以下文本进行润色。

润色原则：
1. 保持原意不变，不添加新信息
2. 提升语言流畅度和专业性
3. 修正语法和表达问题
4. 保持学术写作风格
5. 不要改变专业术语"""

    if style == "concise":
        system_prompt += "\n6. 在保持原意的前提下尽量精简"

    user_prompt = f"请润色以下文本：\n\n{text}"

    try:
        result = call_llm_func(system_prompt, user_prompt)
        return result if result else text
    except Exception as e:
        logger.warning(f"润色失败: {e}")
        return text


# ========================================================================
# 文献综述总结 (V2调整) — 基于提取数据生成高度凝练的综述段落
# ========================================================================

def generate_literature_summary(session_data: dict,
                                 call_llm_func: Callable = None) -> str:
    """基于提取数据和合成结果，生成高度凝练的文献综述总结段落

    取代原有的列举式(bullet-point)呈现方式，输出一段连贯的学术综述段落。
    适用于论文的「文献综述」或「讨论」部分。

    Args:
        session_data: 会话数据，需包含 extraction_results、synthesis_text
        call_llm_func: LLM调用函数

    Returns:
        str: 文献综述总结段落
    """
    extraction = session_data.get("extraction_results", [])
    synthesis_text = session_data.get("synthesis_text", "")

    if not extraction:
        return "暂无提取数据，无法生成文献综述总结。"

    if not call_llm_func:
        return "文献综述总结功能需要配置API Key。"

    # 构建结构化研究摘要
    study_summaries = []
    for r in extraction:
        if "error" in r:
            continue
        study_summaries.append(
            f"- {r.get('author_year', '未知作者')} "
            f"({r.get('study_design', '未知设计')}, "
            f"n={r.get('sample_size', '未报告')}): "
            f"对象={r.get('population', '未报告')} | "
            f"干预={r.get('intervention', '未报告')} | "
            f"结局={r.get('outcome_measures', '未报告')} | "
            f"发现={r.get('main_findings', '未报告')[:200]}"
        )

    studies_text = "\n".join(study_summaries)
    n_studies = len([r for r in extraction if "error" not in r])

    system_prompt = """你是一名护理学领域的系统综述方法学与学术写作专家。

你的任务：将多篇纳入研究的提取数据，改写为**一段高度凝练的文献综述总结段落**。

绝对规则：
1. 输出必须是**一段连贯的学术段落**（约300-500字中文），而非列举或bullet points
2. 按主题逻辑组织，而非按文献顺序罗列
3. 归纳各研究的共同发现、差异和整体趋势
4. 必须涵盖：研究设计特征、人群、关键结局、核心发现的一致性/差异性
5. 语言精炼、学术化，直接可复制到论文的"文献综述"部分
6. 不要添加原始数据中不存在的信息
7. 不要用表格、不要用序号、不要用分段标题
8. 如果存在效应量数据（MD/SMD/OR/RR），适当提及数值范围

输出风格示例："本综述共纳入X项研究，涵盖Y种研究设计。在[主题A]方面，多数研究（如张三等，2023；李四等，2022）报告了[共同发现]；然而，[主题B]的结果存在一定异质性……总体而言，现有证据表明……"
"""

    user_prompt = (
        f"以下是本综述纳入的 {n_studies} 篇研究的提取数据摘要。\n"
        f"请生成一段高度凝练的文献综述总结段落。\n\n"
        f"【各研究数据】\n{studies_text}\n\n"
    )

    if synthesis_text:
        user_prompt += (
            f"【已有合成结果（参考）】\n{synthesis_text[:500]}\n\n"
        )

    user_prompt += "请直接输出一段连贯、精炼的文献综述总结段落："

    try:
        result = call_llm_func(system_prompt, user_prompt)
        if result and not result.startswith("【"):
            return result
        else:
            return _build_fallback_summary(extraction)
    except Exception as e:
        logger.warning(f"文献综述总结生成失败: {e}")
        return _build_fallback_summary(extraction)


def _build_fallback_summary(extraction_results: list) -> str:
    """当LLM调用失败时，手动构建一个简单的综述总结"""
    valid = [r for r in extraction_results if "error" not in r]
    n = len(valid)

    if n == 0:
        return "暂无有效提取数据。"

    designs = set()
    outcomes = set()
    populations = set()
    for r in valid:
        if r.get("study_design"):
            designs.add(r["study_design"])
        if r.get("outcome_measures"):
            outcomes.add(r["outcome_measures"])
        if r.get("population"):
            populations.add(r["population"])

    parts = [f"本综述共纳入{n}篇研究，"]
    if designs:
        parts.append(f"涵盖{'、'.join(list(designs)[:3])}等研究设计。")
    if populations:
        parts.append(f"研究对象包括{list(populations)[0]}等群体。")
    if outcomes:
        parts.append(f"主要结局指标涉及{list(outcomes)[0]}等方面。")

    parts.append("各研究的具体发现如下：")
    for r in valid:
        author = r.get("author_year", r.get("paper", "未知"))
        findings = r.get("main_findings", "")
        if findings:
            parts.append(f"{author}的研究发现：{findings[:150]}")

    return " ".join(parts)


# ========================================================================
# V3 完整论文生成框架 — 分步骤生成系统评价/综述全文
# ========================================================================

def _build_study_context(extraction_results: list) -> str:
    """构建研究数据摘要，供LLM各章节生成使用"""
    valid = [r for r in extraction_results if "error" not in r]
    if not valid:
        return "暂无有效提取数据。"

    n = len(valid)
    designs = set()
    populations = set()
    outcomes = set()
    interventions = set()
    study_lines = []

    for r in valid:
        designs.add(r.get("study_design", "未报告"))
        populations.add(r.get("population", "未报告")[:40])
        outcomes.add(r.get("outcome_measures", "未报告")[:40])
        if r.get("intervention"):
            interventions.add(r["intervention"][:40])
        author = r.get("author_year", r.get("paper", "未知"))
        study_lines.append(
            f"- {author}：{r.get('study_design', '?')}，"
            f"n={r.get('sample_size', '?')}，"
            f"人群={r.get('population', '未报告')[:50]}，"
            f"干预={r.get('intervention', '未报告')[:50]}，"
            f"对照={r.get('comparator', '未报告')[:30]}，"
            f"结局={r.get('outcome_measures', '未报告')[:50]}，"
            f"发现={r.get('main_findings', '未报告')[:150]}"
        )

    context = (
        f"本综述共纳入 {n} 篇研究。\n"
        f"研究设计：{'、'.join(list(designs)[:4])}\n"
        f"研究对象：{'、'.join(list(populations)[:2])}\n"
        f"干预措施：{'、'.join(list(interventions)[:2])}\n"
        f"结局指标：{'、'.join(list(outcomes)[:2])}\n\n"
        f"【各研究详细数据】\n" + "\n".join(study_lines)
    )
    return context


def generate_paper_abstract(extraction_results: list,
                            call_llm_func: Callable = None) -> dict:
    """生成中英文结构式摘要 + 关键词

    Returns:
        dict: {"abstract_cn": str, "abstract_en": str, "keywords_cn": str, "keywords_en": str}
    """
    result = {
        "abstract_cn": "",
        "abstract_en": "",
        "keywords_cn": "",
        "keywords_en": ""
    }

    valid = [r for r in extraction_results if "error" not in r]
    if not valid:
        return result

    context = _build_study_context(extraction_results)

    system_prompt = """你是一名系统评价与Meta分析领域的学术写作专家。

你的任务：根据系统评价纳入的研究数据，生成**结构式中英文摘要**。

结构式摘要格式：
【目的】一句话阐明研究目的
【方法】检索数据库、纳入标准、质量评价工具、分析方法
【结果】纳入研究数量、关键效应量（如有）、主要发现
【结论】一句话结论

要求：
1. 中英文内容对应
2. 中英文关键词各4-8个
3. 语言精炼、学术规范
4. 不编造数据，仅基于提供的材料
5. 关键词用全角分号；分隔

输出格式：
===中文摘要===
...
===英文摘要===
...
===关键词===
...
===Keywords===
..."""

    user_prompt = f"请基于以下研究数据生成结构式摘要：\n\n{context}"

    try:
        if call_llm_func:
            response = call_llm_func(system_prompt, user_prompt)
            if response:
                parts = response.split("===")
                for i, part in enumerate(parts):
                    part = part.strip()
                    if part.startswith("中文摘要"):
                        result["abstract_cn"] = part.replace("中文摘要", "", 1).strip()
                    elif part.startswith("英文摘要"):
                        result["abstract_en"] = part.replace("英文摘要", "", 1).strip()
                    elif part.startswith("关键词"):
                        result["keywords_cn"] = part.replace("关键词", "", 1).strip()
                    elif part.startswith("Keywords"):
                        result["keywords_en"] = part.replace("Keywords", "", 1).strip()
                # Fallback: if parsing failed, use raw response
                if not result["abstract_cn"]:
                    result["abstract_cn"] = response[:500]
    except Exception as e:
        logger.warning(f"摘要生成失败: {e}")
        # Manual fallback
        n = len(valid)
        designs = set(r.get("study_design", "") for r in valid)
        result["abstract_cn"] = (
            f"【目的】系统评价相关干预在目标人群中的应用效果。"
            f"【方法】系统检索多个中英文数据库，纳入相关研究，"
            f"采用标准化工具进行质量评价。"
            f"【结果】共纳入{n}篇研究，涵盖{'、'.join(list(designs)[:3])}等设计类型。"
            f"【结论】现有证据表明相关干预具有一定效果，但仍需更多高质量研究验证。"
        )
        result["abstract_en"] = (
            f"Objective: To systematically evaluate the effects of relevant interventions. "
            f"Methods: Multiple databases were searched. "
            f"Results: {n} studies were included. "
            f"Conclusions: Current evidence suggests potential benefits, but more research is needed."
        )

    return result


def generate_paper_introduction(extraction_results: list,
                                call_llm_func: Callable = None) -> str:
    """生成前言部分：背景→概念→理论→研究空白→目的"""
    valid = [r for r in extraction_results if "error" not in r]
    if not valid:
        return "（请在此补充研究背景和目的）"

    context = _build_study_context(extraction_results)
    n = len(valid)

    system_prompt = """你是一名系统评价领域的学术写作专家。

你的任务：基于系统评价纳入的研究数据，撰写**前言（Introduction）**部分。

前言结构（约800-1200字中文）：
1. **研究背景与疾病负担**：该临床问题/疾病的流行病学数据、严重性
2. **核心概念界定**：明确关键概念的定义和范围
3. **干预/暴露的理论依据**：为什么该干预可能有效（生物学/心理学机制）
4. **现有证据的局限与本综述目的**：前人研究的不足，本综述要回答的问题

要求：
1. 语言学术化、规范化
2. 适当引用纳入文献作为背景支撑（标注 [1], [2] 等占位符）
3. 逻辑递进：从大到小、从已知到未知
4. 最后一段明确写出本综述的研究目的（PICOS）
5. 字数800-1200字
6. 不编造数据，基于提供的材料进行合理推演"""

    user_prompt = (
        f"本综述纳入了 {n} 篇相关研究。\n\n"
        f"以下是这些研究的提取数据摘要，请据此撰写前言：\n\n{context}"
    )

    try:
        if call_llm_func:
            response = call_llm_func(system_prompt, user_prompt)
            if response and not response.startswith("【"):
                return response
    except Exception as e:
        logger.warning(f"前言生成失败: {e}")

    return (
        "（前言待AI生成）\n\n"
        f"本综述拟系统评价相关干预在目标人群中的效果，"
        f"共纳入{n}篇研究进行综合分析。"
    )


def generate_paper_methods(extraction_results: list,
                           rob_results: list = None,
                           call_llm_func: Callable = None) -> str:
    """生成方法部分：PICOS→检索→筛选→提取→质量评价→统计分析"""
    valid = [r for r in extraction_results if "error" not in r]

    # 收集设计类型
    designs = set()
    for r in valid:
        d = r.get("study_design", "")
        if d:
            designs.add(d)

    n = len(valid)
    has_rct = "RCT" in str(designs) or "随机" in str(designs)

    # 质量评价工具
    quality_tool = "Cochrane RoB 2" if has_rct else "EPHPP / 相应质量评价工具"

    # 纳排标准从提取数据推断
    populations = set()
    interventions = set()
    outcomes = set()
    for r in valid:
        if r.get("population"):
            populations.add(r["population"][:40])
        if r.get("intervention"):
            interventions.add(r["intervention"][:40])
        if r.get("outcome_measures"):
            outcomes.add(r["outcome_measures"][:40])

    system_prompt = """你是一名系统评价方法学专家。

你的任务：撰写系统评价的**方法（Methods）部分**。

方法部分结构：
1. **研究方案与注册**：遵循PRISMA 2020声明，注册信息
2. **纳入与排除标准（PICOS）**：人群、干预、对照、结局、研究设计
3. **检索策略**：检索数据库、检索词、检索时限
4. **文献筛选与数据提取**：双人独立筛选、标准化提取
5. **质量评价**：使用的评价工具及方法
6. **统计分析方法**：效应量选择、异质性评估、亚组/敏感性分析计划

要求：
1. 基于提供的研究数据撰写，使描述符合实际纳入研究
2. 语言学术化、规范化
3. 方法描述应详尽到可被重复
4. 字数600-1000字
5. 如果提供了具体检索词，请包含；否则留占位符"""

    context = (
        f"纳入研究：{n}篇\n"
        f"研究设计：{'、'.join(list(designs)[:4])}\n"
        f"研究对象：{'、'.join(list(populations)[:2])}\n"
        f"干预措施：{'、'.join(list(interventions)[:2])}\n"
        f"结局指标：{'、'.join(list(outcomes)[:2])}\n"
        f"适用质量工具：{quality_tool}\n"
    )

    if rob_results:
        done = len(rob_results)
        context += f"已完成质量评价：{done}篇\n"

    user_prompt = f"请基于以下研究特征撰写方法部分：\n\n{context}"

    try:
        if call_llm_func:
            response = call_llm_func(system_prompt, user_prompt)
            if response and not response.startswith("【"):
                return response
    except Exception as e:
        logger.warning(f"方法部分生成失败: {e}")

    return (
        "（方法待AI生成）\n\n"
        f"### 2.1 纳入与排除标准\n"
        f"研究对象：{'、'.join(list(populations)[:2])}…\n"
        f"干预措施：{'、'.join(list(interventions)[:2])}…\n"
        f"结局指标：{'、'.join(list(outcomes)[:2])}…\n"
        f"### 2.2 检索策略\n（请补充检索数据库和检索式）\n"
        f"### 2.3 质量评价\n采用{quality_tool}进行偏倚风险评估。\n"
    )


def generate_paper_results(extraction_results: list,
                           meta_text: str = "",
                           grade_text: str = "",
                           prisma_data: dict = None,
                           call_llm_func: Callable = None) -> str:
    """生成结果部分：文献筛选→特征→质量→Meta分析结果"""
    valid = [r for r in extraction_results if "error" not in r]
    n = len(valid)

    # 构建研究特征表（Markdown格式）
    char_rows = []
    for r in valid:
        char_rows.append(
            f"| {r.get('author_year', '未知')[:20]} "
            f"| {r.get('study_design', '')[:15]} "
            f"| {r.get('sample_size', '')} "
            f"| {r.get('population', '')[:30]} "
            f"| {r.get('intervention', '')[:30]} "
            f"| {r.get('outcome_measures', '')[:30]} |"
        )

    char_table = "| 作者/年份 | 研究设计 | 样本量 | 研究对象 | 干预措施 | 结局指标 |\n"
    char_table += "|-----------|---------|--------|---------|---------|---------|\n"
    char_table += "\n".join(char_rows)

    context = (
        f"纳入研究数：{n}篇\n\n"
        f"【研究特征表】\n{char_table}\n\n"
        f"【Meta分析结果】\n{meta_text if meta_text else '未进行Meta分析'}\n\n"
        f"【GRADE分级】\n{grade_text if grade_text else '未进行GRADE分级'}\n"
    )

    if prisma_data:
        context += (
            f"\n【文献筛选数据】\n"
            f"初筛记录：{prisma_data.get('identified', '?')}条\n"
            f"纳入定性合成：{prisma_data.get('qualitative', '?')}篇\n"
            f"纳入定量合成：{prisma_data.get('quantitative', '?')}篇\n"
        )

    system_prompt = """你是一名系统评价领域的学术写作专家。

你的任务：撰写系统评价的**结果（Results）部分**。

结果部分结构：
1. **文献筛选结果**：PRISMA流程概括（检索→筛选→纳入）
2. **纳入研究特征**：研究数量、发表年份、国家、设计类型、样本量范围等概括
3. **质量评价结果**：总体偏倚风险概况
4. **Meta分析结果**（如有）：合并效应量、异质性、亚组/敏感性分析
5. **GRADE分级结果**（如有）

要求：
1. 只描述结果，不解释原因（那是讨论部分的工作）
2. 用数据说话（纳入多少、效应量多少、I²多少）
3. 基于提供的特征表和Meta结果撰写
4. 语言学术化、规范化
5. 字数600-1000字
6. 研究特征部分须包含各研究的关键信息"""

    user_prompt = f"请基于以下研究数据撰写结果部分：\n\n{context}"

    try:
        if call_llm_func:
            response = call_llm_func(system_prompt, user_prompt)
            if response and not response.startswith("【"):
                return response
    except Exception as e:
        logger.warning(f"结果部分生成失败: {e}")

    return (
        "（结果待AI生成）\n\n"
        f"### 3.1 文献筛选结果\n"
        f"共纳入{n}篇研究进行综合分析。\n\n"
        f"### 3.2 纳入研究特征\n"
        f"{char_table}\n"
    )


def generate_paper_discussion(extraction_results: list,
                              meta_text: str = "",
                              call_llm_func: Callable = None) -> str:
    """生成讨论部分：主要发现→比较→机制→临床意义→局限性→未来方向"""
    valid = [r for r in extraction_results if "error" not in r]
    n = len(valid)

    context = _build_study_context(extraction_results)
    if meta_text:
        context += f"\n【Meta分析结果参考】\n{meta_text}\n"

    system_prompt = """你是一名系统评价领域的学术写作专家。

你的任务：撰写系统评价的**讨论（Discussion）部分**和**结论（Conclusion）**。

讨论部分结构（约1000-1500字）：
1. **主要发现总结**：本研究最重要的发现（关键效应量和方向）
2. **与既往研究的比较**：本研究的发现与已发表综述/研究的异同
3. **可能的机制解释**：为什么会出现这样的结果（生物学/临床机制）
4. **临床意义**：对临床实践或护理的启示
5. **优势与局限性**：本系统评价的方法学优势和不足
6. **对未来研究的启示**：基于本研究的发现提出未来研究方向

结论：一段精炼的总结（3-5句话）

要求：
1. 讨论要深入，不要简单重复结果
2. 与既往研究的比较要具体（如：与XXX等[ref]的系统评价相比…）
3. 局限性要诚实全面
4. 语言学术化、规范化
5. 不编造数据，不编造参考文献"""

    user_prompt = (
        f"本综述纳入了{n}篇研究。\n\n"
        f"请撰写讨论和结论部分：\n\n{context}"
    )

    try:
        if call_llm_func:
            response = call_llm_func(system_prompt, user_prompt)
            if response and not response.startswith("【"):
                return response
    except Exception as e:
        logger.warning(f"讨论部分生成失败: {e}")

    return (
        "（讨论待AI生成）\n\n"
        f"### 4.1 主要发现\n"
        f"本系统评价共纳入{n}篇研究…\n\n"
        f"### 4.2 局限性\n"
        f"纳入研究数量有限、质量参差不齐…\n\n"
        f"## 5 结论\n"
        f"现有证据表明…但仍需更多高质量研究验证。\n"
    )


def generate_full_paper_draft(session_data: dict,
                              section: str = "all",
                              call_llm_func: Callable = None) -> dict:
    """完整论文生成主入口

    分步生成系统评价全文。每次调用生成指定章节。

    Args:
        session_data: 会话数据
        section: 要生成的章节 ("abstract" / "introduction" / "methods" / "results" / "discussion" / "all")
        call_llm_func: LLM调用函数

    Returns:
        dict: {"section_name": "content", ...} 包含所有已生成章节
    """
    extraction = session_data.get("extraction_results", [])
    rob = session_data.get("rob_results", [])
    meta_text = session_data.get("meta_text", "")
    grade_text = session_data.get("grade_text", "")
    prisma_data = session_data.get("prisma_data")

    result = {}

    if section in ("abstract", "all"):
        abstract_data = generate_paper_abstract(extraction, call_llm_func)
        result["abstract_cn"] = abstract_data.get("abstract_cn", "")
        result["abstract_en"] = abstract_data.get("abstract_en", "")
        result["keywords_cn"] = abstract_data.get("keywords_cn", "")
        result["keywords_en"] = abstract_data.get("keywords_en", "")

    if section in ("introduction", "all"):
        result["introduction"] = generate_paper_introduction(extraction, call_llm_func)

    if section in ("methods", "all"):
        result["methods"] = generate_paper_methods(extraction, rob, call_llm_func)

    if section in ("results", "all"):
        result["results"] = generate_paper_results(
            extraction, meta_text, grade_text, prisma_data, call_llm_func
        )

    if section in ("discussion", "all"):
        result["discussion"] = generate_paper_discussion(extraction, meta_text, call_llm_func)

    return result


def merge_full_paper(paper_sections: dict,
                     extraction_results: list = None,
                     citation_style: str = "apa") -> str:
    """将分步生成的章节合并为完整的Markdown论文

    Args:
        paper_sections: 各章节内容字典
        extraction_results: 提取结果（用于生成参考文献）
        citation_style: 引用格式

    Returns:
        str: 完整论文Markdown
    """
    lines = [
        "# 系统评价与Meta分析",
        "",
        f"> 由循证分析智能体辅助生成 | {datetime.now().strftime('%Y年%m月%d日')}",
        "",
        "---",
        "",
    ]

    # 摘要
    abstract_cn = paper_sections.get("abstract_cn", "")
    abstract_en = paper_sections.get("abstract_en", "")
    keywords_cn = paper_sections.get("keywords_cn", "")
    keywords_en = paper_sections.get("keywords_en", "")

    if abstract_cn:
        lines.extend(["## 摘要", "", abstract_cn, ""])
    if keywords_cn:
        lines.extend([f"**关键词**：{keywords_cn}", ""])
    if abstract_en:
        lines.extend(["## Abstract", "", abstract_en, ""])
    if keywords_en:
        lines.extend([f"**Keywords**：{keywords_en}", ""])

    if abstract_cn or abstract_en:
        lines.append("---")
        lines.append("")

    # 各章节
    section_map = [
        ("introduction", "1 前言"),
        ("methods", "2 资料与方法"),
        ("results", "3 结果"),
        ("discussion", "4 讨论"),
    ]

    for key, heading in section_map:
        content = paper_sections.get(key, "")
        if content:
            # 如果内容已经包含标题，就不加标题前缀
            if content.startswith("#") or content.startswith("##"):
                lines.append(content)
            else:
                lines.append(f"## {heading}")
                lines.append("")
                lines.append(content)
            lines.append("")

    # 参考文献
    if extraction_results:
        refs = format_references(extraction_results, citation_style)
        lines.append(render_references(refs, citation_style))

    return "\n".join(lines)
