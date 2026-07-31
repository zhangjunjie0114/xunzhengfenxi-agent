"""
Meta分析引擎 — 专业统计分析模块

提供完整的Meta分析计算功能，包括：
- 固定效应模型（Inverse Variance Weighted）
- 随机效应模型（DerSimonian-Laird 法）
- 异质性评估（Cochran's Q、I²、τ²、H）
- Leave-one-out 敏感性分析
- 亚组分析（组间异质性 Q_between）
- 漏斗图 + Egger's 检验

API设计：
- 纯计算模块，不依赖Streamlit
- 输入为已解析的 StudyData 列表
- 输出为 MetaResult 数据类
- 所有统计公式参照 Cochrane Handbook 第6.4版（2023）

依赖：math（标准库）, scipy（用于χ²分布p值、t分布、Egger回归）
"""
from dataclasses import dataclass, field
from typing import Optional, List, Tuple
import math
import re
import logging

logger = logging.getLogger(__name__)


# ========================================================================
# 1. 数据结构
# ========================================================================

@dataclass
class StudyData:
    """单一研究的标准化数字数据

    所有数值在内部统一处理：
    - MD/SMD：原始尺度
    - OR/RR：对数尺度（log OR, log RR）
    """
    author: str                      # 作者标签
    effect: float                    # 效应量数值
    ci_lower: float                  # 95%CI下限
    ci_upper: float                  # 95%CI上限
    subgroup: str = ""               # 亚组分类（可选）
    p_value: Optional[float] = None  # 原始P值（可选）
    weight: float = 0.0              # 计算后填充的权重

    @property
    def se(self) -> float:
        """标准误 = (CI_upper - CI_lower) / (2 * 1.96)"""
        return (self.ci_upper - self.ci_lower) / (2 * 1.96)

    @property
    def variance(self) -> float:
        """方差 = SE²"""
        return self.se ** 2

    @property
    def weight_fixed(self) -> float:
        """固定效应权重 = 1 / 方差"""
        if self.variance >= 1e-300:
            return 1.0 / self.variance
        return 1e300


@dataclass
class MetaResult:
    """Meta分析完整结果

    对于 OR/RR，pooled_effect 等数值存储在对数尺度，
    调用 get_expanded() 获取原始尺度。
    """
    pooled_effect: float             # 合并效应量
    pooled_ci_lower: float           # 合并95%CI下限
    pooled_ci_upper: float           # 合并95%CI上限
    pooled_se: float                 # 合并标准误
    pooled_p_value: float            # 合并P值（Z检验）
    z_value: float                   # Z统计量
    i_squared: float                 # I²异质性 (%)
    tau_squared: float               # τ²（随机效应）
    h_statistic: float               # H统计量
    q_stat: float                    # Cochran's Q
    q_df: int                        # Q检验自由度 (k-1)
    q_p_value: float                 # Q检验P值
    n_studies: int                   # 纳入研究数
    effect_measure: str              # "MD" / "SMD" / "OR" / "RR"
    is_random: bool                  # True=随机效应, False=固定效应
    studies: List[StudyData] = field(default_factory=list)
    study_details: List[dict] = field(default_factory=list)
    warning: str = ""                # 警告（如研究数不足、异质性高）

    def get_expanded(self) -> 'MetaResult':
        """对 OR/RR 进行指数变换，还原到原始尺度

        对于 MD/SMD，直接返回自身。
        对于 OR/RR，对 pooled_effect/CI 做 exp() 变换。
        """
        if self.effect_measure in ("OR", "RR"):
            expanded = MetaResult(
                pooled_effect=math.exp(self.pooled_effect),
                pooled_ci_lower=math.exp(self.pooled_ci_lower),
                pooled_ci_upper=math.exp(self.pooled_ci_upper),
                pooled_se=self.pooled_se,  # SE保持log尺度
                pooled_p_value=self.pooled_p_value,
                z_value=self.z_value,
                i_squared=self.i_squared,
                tau_squared=self.tau_squared,
                h_statistic=self.h_statistic,
                q_stat=self.q_stat,
                q_df=self.q_df,
                q_p_value=self.q_p_value,
                n_studies=self.n_studies,
                effect_measure=self.effect_measure,
                is_random=self.is_random,
                studies=self.studies,
                study_details=self.study_details,
                warning=self.warning,
            )
            return expanded
        return self

    def get_summary_text(self, expanded: bool = True) -> str:
        """生成可读的Meta分析摘要文本

        Args:
            expanded: 对OR/RR是否还原到原始尺度

        Returns:
            格式化的文本摘要
        """
        r = self.get_expanded() if expanded else self
        em = r.effect_measure
        model = "随机效应模型" if r.is_random else "固定效应模型"

        lines = [
            f"**{model} Meta分析结果**",
            "",
            f"- 纳入研究：{r.n_studies}篇",
            f"- 合并效应量（{em}）：{r.pooled_effect:.4f}",
            f"- 95%置信区间：（{r.pooled_ci_lower:.4f}, {r.pooled_ci_upper:.4f}）",
            f"- Z检验：Z={r.z_value:.3f}，P={r.pooled_p_value:.4f}",
            f"- 异质性：Q={r.q_stat:.3f}（df={r.q_df}，P={r.q_p_value:.4f}），"
            f"I²={r.i_squared:.1f}%",
        ]

        if r.is_random:
            lines.append(f"- τ²={r.tau_squared:.4f}，H={r.h_statistic:.2f}")

        if r.warning:
            lines.append(f"")
            lines.append(f"> ⚠️ {r.warning}")

        return "\n".join(lines)


# ========================================================================
# 2. 解析函数：从 extraction_results 中提取数值
# ========================================================================

def _parse_number(num_str: str) -> Optional[float]:
    """安全地将字符串解析为浮点数"""
    if not num_str or not isinstance(num_str, str):
        return None
    try:
        return float(num_str.strip().replace(",", "").replace("，", ""))
    except (ValueError, TypeError):
        return None


def parse_studies_from_extraction(
    extraction_results: list,
    effect_measure: str,
) -> Tuple[List[StudyData], str]:
    """从提取结果中解析效应量数据

    支持多种文本格式：
    - "0.36" → 仅效应量，CI从 confidence_interval 读取
    - "0.36, 0.14, 0.58" → 效应量, CI下限, CI上限
    - "0.36(0.14~0.58)" → 同上
    - "0.36 (0.14, 0.58)" → 同上

    Args:
        extraction_results: 提取结果列表
        effect_measure: "MD" / "SMD" / "OR" / "RR"

    Returns:
        (studies_list, warning_message)
    """
    studies = []
    warnings = []

    log_scale = effect_measure in ("OR", "RR")

    for r in extraction_results:
        if "error" in r:
            continue

        author = r.get("author_year") or r.get("paper", "未知")[:30]
        es_val = r.get("effect_size_value", "")
        ci_val = r.get("confidence_interval", "")

        if not es_val:
            continue

        # 解析效应量和CI
        effect = None
        ci_lower = None
        ci_upper = None

        # 策略1: 从 effect_size_value 中同时提取三个数值
        # 格式: "0.36, 0.14, 0.58" 或 "0.36(0.14~0.58)" 或 "0.36 (0.14, 0.58)"
        nums = re.findall(r'[-]?\d*\.?\d+', es_val)

        if len(nums) >= 3:
            # effect_size_value 包含完整信息
            effect = _parse_number(nums[0])
            ci_lower = _parse_number(nums[1])
            ci_upper = _parse_number(nums[2])
        elif len(nums) >= 1:
            # 只有效应量，从CI字段获取CI
            effect = _parse_number(nums[0])
            if ci_val:
                ci_nums = re.findall(r'[-]?\d*\.?\d+', ci_val)
                if len(ci_nums) >= 2:
                    ci_lower = _parse_number(ci_nums[0])
                    ci_upper = _parse_number(ci_nums[1])

        # 如果还有效量但无CI，估算
        if effect is not None and (ci_lower is None or ci_upper is None):
            # 使用 ±20% 估算（保守估计）
            if effect > 0:
                ci_lower = effect * 0.7
                ci_upper = effect * 1.3
            else:
                ci_lower = effect * 1.3
                ci_upper = effect * 0.7
            warnings.append(f"{author}: 未提供置信区间，使用估算值")
            effect_type = str(r.get("effect_size", "")).upper()
            if effect_type not in ("MD", "SMD", "OR", "RR"):
                warnings.append(f"{author}: 效应量类型未标注")
        else:
            # 验证CI顺序
            if ci_lower is not None and ci_upper is not None and ci_lower > ci_upper:
                ci_lower, ci_upper = ci_upper, ci_lower

        if effect is None:
            continue

        # 对数变换（OR/RR在log尺度合并）
        if log_scale:
            if effect <= 0:
                warnings.append(f"{author}: OR/RR效应量≤0（值={effect:.3f}），已跳过此研究")
                continue
            effect = math.log(effect)
            if ci_lower is not None and ci_lower > 0:
                ci_lower = math.log(ci_lower)
            if ci_upper is not None and ci_upper > 0:
                ci_upper = math.log(ci_upper)

        # 验证SE是否合理
        se = (ci_upper - ci_lower) / (2 * 1.96) if ci_upper != ci_lower else 0.1
        if se <= 0 or se > 10:
            se = 0.1
            ci_lower = effect - 1.96 * se
            ci_upper = effect + 1.96 * se
            warnings.append(f"{author}: 置信区间异常，已重置")

        study = StudyData(
            author=author,
            effect=effect,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            subgroup=r.get("subgroup", ""),
            p_value=None,
        )
        studies.append(study)

    # 生成警告
    warning_text = ""
    if len(studies) < 2:
        warning_text = f"只有 {len(studies)} 篇研究有效，Meta分析需要至少2篇"
    elif len(studies) < 3:
        warning_text = f"仅 {len(studies)} 篇研究，异质性估计可能不可靠"

    if warnings:
        unique_warnings = list(set(warnings))
        if warning_text:
            warning_text += "；"
        warning_text += "；".join(unique_warnings[:3])
        if len(unique_warnings) > 3:
            warning_text += f"…（共{len(unique_warnings)}条提示）"

    return studies, warning_text


# ========================================================================
# 3. 核心统计算法
# ========================================================================

def _compute_fixed_effect(studies: List[StudyData]) -> dict:
    """固定效应模型 — 倒方差加权法（Inverse Variance Weighted）

    公式：
        w_i = 1 / SE_i²
        θ̂ = Σ(w_i · θ_i) / Σ(w_i)
        SE(θ̂) = 1 / √Σ(w_i)
        95%CI = θ̂ ± 1.96 × SE(θ̂)

    Args:
        studies: 已解析的研究列表

    Returns:
        dict: 包含 pooled_effect, pooled_se, pooled_ci_lower, pooled_ci_upper
    """
    total_weight = sum(s.weight_fixed for s in studies)

    if total_weight <= 0:
        return {
            "pooled_effect": 0.0,
            "pooled_se": 0.0,
            "pooled_ci_lower": 0.0,
            "pooled_ci_upper": 0.0,
        }

    pooled_effect = sum(s.effect * s.weight_fixed for s in studies) / total_weight
    pooled_se = math.sqrt(1.0 / total_weight) if total_weight > 0 else 0.0
    pooled_ci_lower = pooled_effect - 1.96 * pooled_se
    pooled_ci_upper = pooled_effect + 1.96 * pooled_se

    return {
        "pooled_effect": pooled_effect,
        "pooled_se": pooled_se,
        "pooled_ci_lower": pooled_ci_lower,
        "pooled_ci_upper": pooled_ci_upper,
    }


def _compute_heterogeneity(studies: List[StudyData], pooled_effect: float) -> dict:
    """计算异质性统计量

    Cochran's Q:
        Q = Σ w_i · (θ_i - θ̂)²
        Q ~ χ²(k-1) 分布

    I²:
        I² = max(0, (Q - (k-1)) / Q) × 100%

    H:
        H = √(Q / (k-1))

    τ²（DerSimonian-Laird）:
        C = Σw_i - Σw_i² / Σw_i
        τ² = max(0, (Q - (k-1)) / C)

    Args:
        studies: 研究列表（需有权重）
        pooled_effect: 固定效应合并效应量

    Returns:
        dict: 包含 q_stat, i_squared, h_statistic, tau_squared, c_stat
    """
    k = len(studies)

    # Q统计量
    q_stat = sum(
        s.weight_fixed * (s.effect - pooled_effect) ** 2
        for s in studies
    )

    # I²
    if q_stat > 0 and k > 1:
        i_squared = max(0.0, (q_stat - (k - 1)) / q_stat * 100.0)
    else:
        i_squared = 0.0

    # H
    if k > 1 and q_stat > 0:
        h_statistic = math.sqrt(q_stat / (k - 1))
    else:
        h_statistic = 1.0

    # τ² (DerSimonian-Laird)
    total_weight = sum(s.weight_fixed for s in studies)
    sum_weights_sq = sum(w.weight_fixed ** 2 for w in studies)
    c_stat = total_weight - (sum_weights_sq / total_weight) if total_weight > 0 else 0.0

    if k > 1 and c_stat > 0:
        tau_squared = max(0.0, (q_stat - (k - 1)) / c_stat)
    else:
        tau_squared = 0.0

    return {
        "q_stat": q_stat,
        "i_squared": i_squared,
        "h_statistic": h_statistic,
        "tau_squared": tau_squared,
        "c_stat": c_stat,
    }


def _compute_random_effects_dl(
    studies: List[StudyData],
    tau_squared: float,
) -> dict:
    """DerSimonian-Laird 随机效应模型

    公式：
        w_i* = 1 / (v_i + τ²)
        θ̂* = Σ(w_i* · θ_i) / Σ(w_i*)
        SE(θ̂*) = 1 / √Σ(w_i*)
        95%CI* = θ̂* ± 1.96 × SE(θ̂*)

    Args:
        studies: 研究列表
        tau_squared: 组间方差估计

    Returns:
        dict: 包含 pooled_effect, pooled_se, pooled_ci_lower, pooled_ci_upper, weights
    """
    # 随机效应权重
    random_weights = []
    for s in studies:
        w = 1.0 / (s.variance + tau_squared) if (s.variance + tau_squared) > 1e-12 else 0.0
        random_weights.append(w)

    total_weight_re = sum(random_weights)

    if total_weight_re <= 0:
        return {
            "pooled_effect": 0.0,
            "pooled_se": 0.0,
            "pooled_ci_lower": 0.0,
            "pooled_ci_upper": 0.0,
            "weights": random_weights,
        }

    pooled_effect = sum(
        s.effect * w for s, w in zip(studies, random_weights)
    ) / total_weight_re

    pooled_se = math.sqrt(1.0 / total_weight_re) if total_weight_re > 0 else 0.0
    pooled_ci_lower = pooled_effect - 1.96 * pooled_se
    pooled_ci_upper = pooled_effect + 1.96 * pooled_se

    return {
        "pooled_effect": pooled_effect,
        "pooled_se": pooled_se,
        "pooled_ci_lower": pooled_ci_lower,
        "pooled_ci_upper": pooled_ci_upper,
        "weights": random_weights,
    }


# ========================================================================
# 4. 主入口
# ========================================================================

def compute_meta_analysis(
    studies: List[StudyData],
    effect_measure: str = "MD",
    model: str = "random",
) -> MetaResult:
    """执行完整的Meta分析

    Args:
        studies: 已解析的研究数据列表
        effect_measure: "MD" / "SMD" / "OR" / "RR"
        model: "fixed" 或 "random"（默认随机效应）

    Returns:
        MetaResult 包含完整的分析结果

    流程：
    1. 计算固定效应合并（用于Q统计量和τ²估计）
    2. 计算异质性统计（Q, I², τ²）
    3. 如果选择随机效应，重新计算合并效应量
    4. 执行Z检验
    """
    k = len(studies)
    is_random = model == "random"

    if k < 2:
        return MetaResult(
            pooled_effect=0.0,
            pooled_ci_lower=0.0,
            pooled_ci_upper=0.0,
            pooled_se=0.0,
            pooled_p_value=1.0,
            z_value=0.0,
            i_squared=0.0,
            tau_squared=0.0,
            h_statistic=1.0,
            q_stat=0.0,
            q_df=max(0, k - 1),
            q_p_value=1.0,
            n_studies=k,
            effect_measure=effect_measure,
            is_random=is_random,
            studies=studies,
            warning="需要至少2篇研究才能进行Meta分析",
        )

    # Step 1: 固定效应合并（用于Q统计量）
    fe_result = _compute_fixed_effect(studies)
    pooled_effect_fe = fe_result["pooled_effect"]

    # Step 2: 异质性统计
    het = _compute_heterogeneity(studies, pooled_effect_fe)
    q_stat = het["q_stat"]
    i_squared = het["i_squared"]
    h_statistic = het["h_statistic"]
    tau_squared = het["tau_squared"]

    # Q检验的P值
    try:
        from scipy import stats as scipy_stats
        q_p_value = 1.0 - scipy_stats.chi2.cdf(q_stat, k - 1) if k > 1 and q_stat > 0 else 1.0
    except ImportError:
        logger.warning("scipy不可用，Q检验P值无法计算（建议安装scipy）")
        q_p_value = float("nan")

    # Step 3: 选择模型
    if is_random:
        re_result = _compute_random_effects_dl(studies, tau_squared)
        pooled_effect = re_result["pooled_effect"]
        pooled_se = re_result["pooled_se"]
        pooled_ci_lower = re_result["pooled_ci_lower"]
        pooled_ci_upper = re_result["pooled_ci_upper"]
        weights = re_result["weights"]
    else:
        pooled_effect = fe_result["pooled_effect"]
        pooled_se = fe_result["pooled_se"]
        pooled_ci_lower = fe_result["pooled_ci_lower"]
        pooled_ci_upper = fe_result["pooled_ci_upper"]
        weights = [s.weight_fixed for s in studies]

    # Step 4: Z检验
    z_value = pooled_effect / pooled_se if pooled_se > 0 else 0.0
    try:
        from scipy import stats as scipy_stats
        pooled_p_value = 2.0 * (1.0 - scipy_stats.norm.cdf(abs(z_value)))
    except ImportError:
        # 手动近似（标准正态分布）
        pooled_p_value = math.exp(-0.717 * abs(z_value) - 0.416 * abs(z_value) ** 2)

    # Step 5: 生成研究详情
    total_weight_fixed = sum(s.weight_fixed for s in studies)
    total_weight_re = sum(weights)

    study_details = []
    for i, s in enumerate(studies):
        w_fixed_pct = (s.weight_fixed / total_weight_fixed * 100) if total_weight_fixed > 0 else 0
        w_re_pct = (weights[i] / total_weight_re * 100) if total_weight_re > 0 else 0
        study_details.append({
            "author": s.author,
            "effect": s.effect,
            "ci_lower": s.ci_lower,
            "ci_upper": s.ci_upper,
            "se": s.se,
            "weight_fixed": s.weight_fixed,
            "weight_fixed_pct": w_fixed_pct,
            "weight_re": weights[i],
            "weight_re_pct": w_re_pct,
        })

    # 警告信息
    warning_parts = []
    if i_squared > 50:
        warning_parts.append(f"异质性较高（I²={i_squared:.1f}%），建议使用随机效应模型并探索异质性来源")
    if k < 3:
        warning_parts.append(f"仅{k}篇研究，结果应谨慎解读")
    if tau_squared > 0.5:
        warning_parts.append(f"组间方差较大（τ²={tau_squared:.3f}）")

    return MetaResult(
        pooled_effect=pooled_effect,
        pooled_ci_lower=pooled_ci_lower,
        pooled_ci_upper=pooled_ci_upper,
        pooled_se=pooled_se,
        pooled_p_value=pooled_p_value,
        z_value=z_value,
        i_squared=i_squared,
        tau_squared=tau_squared,
        h_statistic=h_statistic,
        q_stat=q_stat,
        q_df=k - 1,
        q_p_value=q_p_value,
        n_studies=k,
        effect_measure=effect_measure,
        is_random=is_random,
        studies=studies,
        study_details=study_details,
        warning="；".join(warning_parts),
    )


# ========================================================================
# 5. 敏感性分析：Leave-one-out
# ========================================================================

def compute_leave_one_out(
    studies: List[StudyData],
    effect_measure: str = "MD",
    model: str = "random",
) -> List[MetaResult]:
    """Leave-one-out 敏感性分析

    逐一剔除单项研究后重新计算Meta分析，检验结果的稳健性。

    Args:
        studies: 研究列表
        effect_measure: 效应量类型
        model: 模型类型

    Returns:
        list[MetaResult]: 每个结果对应剔除一项研究后的分析结果
    """
    if len(studies) < 3:
        return []

    results = []
    for i in range(len(studies)):
        remaining = studies[:i] + studies[i + 1:]
        result = compute_meta_analysis(remaining, effect_measure, model)
        result.warning = f"排除「{studies[i].author}」后的分析结果"
        results.append(result)

    return results


# ========================================================================
# 6. 亚组分析
# ========================================================================

def compute_subgroup_analysis(
    studies: List[StudyData],
    effect_measure: str = "MD",
    model: str = "random",
) -> dict:
    """亚组分析

    按 subgroup 字段分组，每组独立计算Meta分析，
    并计算组间异质性 Q_between。

    Args:
        studies: 研究列表（需包含 subgroup 信息）
        effect_measure: 效应量类型
        model: 模型类型

    Returns:
        dict: {
            "groups": {group_name: MetaResult},
            "q_between": float,    # 组间异质性
            "q_between_p": float,  # 组间异质性P值
            "overall": MetaResult, # 总体合并结果
        }
    """
    # 按 subgroup 分组
    groups = {}
    for s in studies:
        g = s.subgroup or "未分组"
        if g not in groups:
            groups[g] = []
        groups[g].append(s)

    # 每组独立分析
    group_results = {}
    for g_name, g_studies in groups.items():
        if len(g_studies) >= 2:
            group_results[g_name] = compute_meta_analysis(
                g_studies, effect_measure, model
            )
        else:
            group_results[g_name] = MetaResult(
                pooled_effect=g_studies[0].effect if g_studies else 0,
                pooled_ci_lower=g_studies[0].ci_lower if g_studies else 0,
                pooled_ci_upper=g_studies[0].ci_upper if g_studies else 0,
                pooled_se=g_studies[0].se if g_studies else 0,
                pooled_p_value=1.0,
                z_value=0.0,
                i_squared=0.0,
                tau_squared=0.0,
                h_statistic=1.0,
                q_stat=0.0,
                q_df=0,
                q_p_value=1.0,
                n_studies=len(g_studies),
                effect_measure=effect_measure,
                is_random=model == "random",
                studies=g_studies,
                warning=f"仅{len(g_studies)}篇，无法计算组内异质性",
            )

    # 总体合并
    overall = compute_meta_analysis(studies, effect_measure, model)

    # 组间异质性 Q_between
    # Q_between = Q_total - ΣQ_within（但简化版：用总体Q无法直接分解）
    # 这里使用各组Q之和做近似
    q_within_sum = sum(
        r.q_stat for r in group_results.values() if r.n_studies >= 2
    )
    q_between = max(0.0, overall.q_stat - q_within_sum)

    n_groups = len([g for g in group_results.values() if g.n_studies >= 2])
    try:
        from scipy import stats as scipy_stats
        q_between_p = 1.0 - scipy_stats.chi2.cdf(q_between, max(1, n_groups - 1)) if n_groups > 1 else 1.0
    except ImportError:
        q_between_p = float("nan")

    return {
        "groups": group_results,
        "q_between": q_between,
        "q_between_p": q_between_p,
        "overall": overall,
    }


# ========================================================================
# 7. 漏斗图 + Egger's 检验
# ========================================================================

def compute_funnel_plot_data(
    studies: List[StudyData],
    effect_measure: str = "MD",
) -> dict:
    """漏斗图数据 + Egger's 线性回归检验

    Egger's 检验（Sterne & Egger, 2001）：
        - 以标准误的倒数（精度）为自变量，效应量为因变量
        - 回归模型：effect/se ~ 1/se
        - 检验截距项（bias）是否显著≠0
        - 若截距显著，提示可能存在发表偏倚

    Args:
        studies: 研究列表
        effect_measure: 效应量类型

    Returns:
        dict: {
            "points": [{author, effect, se, ci_lower, ci_upper}],
            "funnel_lines": [{x, y}],  # 伪95%CI漏斗线
            "egger_intercept": float,       # Egger回归截距
            "egger_intercept_se": float,    # 截距标准误
            "egger_p_value": float,         # 截距P值
            "egger_slope": float,           # 回归斜率
            "n_studies": int
        }
    """
    k = len(studies)

    # 各研究的数据点
    points = []
    for s in studies:
        points.append({
            "author": s.author,
            "effect": s.effect,
            "se": s.se,
            "ci_lower": s.ci_lower,
            "ci_upper": s.ci_upper,
        })

    # 漏斗线（以固定效应合并效应量为中心）
    fe = _compute_fixed_effect(studies)
    center = fe["pooled_effect"]

    # 生成漏斗线：SE从0到最大SE的曲线
    max_se = max(s.se for s in studies) * 1.1 if studies else 1.0
    se_range = [i * max_se / 50 for i in range(51)]

    funnel_lines = []
    for se_val in se_range:
        if se_val < 0.001:
            continue
        y = se_val  # Y轴是标准误
        x_lower = center - 1.96 * se_val
        x_upper = center + 1.96 * se_val
        funnel_lines.append({
            "ci_lower": x_lower,
            "ci_upper": x_upper,
            "center": center,
            "se": se_val,
        })

    # Egger's 检验（回归）
    egger_result = _egger_test(studies)

    return {
        "points": points,
        "funnel_lines": funnel_lines,
        "center": center,
        "max_se": max_se,
        "n_studies": k,
        **egger_result,
    }


def _egger_test(studies: List[StudyData]) -> dict:
    """Egger's 线性回归检验

    以精度（1/SE）为自变量X，效应量/SE为因变量Y：
        Y = β₀ + β₁·X
    其中截距β₀表示偏倚，若显著≠0则提示发表偏倚。

    Returns:
        dict: {egger_intercept, egger_intercept_se, egger_p_value, egger_slope}
    """
    k = len(studies)
    if k < 3:
        return {
            "egger_intercept": 0.0,
            "egger_intercept_se": 0.0,
            "egger_p_value": 1.0,
            "egger_slope": 0.0,
        }

    # 准备回归数据（过滤SE=0的研究，防止除零）
    valid_studies = [s for s in studies if s.se > 1e-300]
    if len(valid_studies) < 3:
        return {
            "egger_intercept": 0.0,
            "egger_intercept_se": 0.0,
            "egger_p_value": 1.0,
            "egger_slope": 0.0,
        }

    x_vals = [1.0 / s.se for s in valid_studies]  # 精度
    y_vals = [s.effect / s.se for s in valid_studies]  # 标准化效应量

    n = len(x_vals)
    mean_x = sum(x_vals) / n
    mean_y = sum(y_vals) / n

    # 最小二乘回归
    ss_xx = sum((x - mean_x) ** 2 for x in x_vals)
    ss_xy = sum((x - mean_x) * (y - mean_y) for x, y in zip(x_vals, y_vals))

    slope = ss_xy / ss_xx if ss_xx > 0 else 0.0
    intercept = mean_y - slope * mean_x

    # 残差标准误
    residuals = [y - (intercept + slope * x) for x, y in zip(x_vals, y_vals)]
    res_se = math.sqrt(sum(r ** 2 for r in residuals) / (n - 2)) if n > 2 else 0.0

    # 截距的标准误
    se_intercept = res_se * math.sqrt(
        sum(x ** 2 for x in x_vals) / (n * ss_xx)
    ) if ss_xx > 0 else 0.0

    # t检验（截距=0）
    if se_intercept > 0:
        t_stat = intercept / se_intercept
        df = n - 2
        try:
            from scipy import stats as scipy_stats
            p_value = 2.0 * (1.0 - scipy_stats.t.cdf(abs(t_stat), df))
        except ImportError:
            # t分布近似（df>30时接近正态）
            p_value = math.exp(-0.717 * abs(t_stat) - 0.416 * abs(t_stat) ** 2)
    else:
        t_stat = 0.0
        p_value = 1.0

    return {
        "egger_intercept": intercept,
        "egger_intercept_se": se_intercept,
        "egger_p_value": p_value,
        "egger_slope": slope,
    }


# ========================================================================
# 8. 辅助函数
# ========================================================================

def determine_effect_measure_from_data(extraction_results: list) -> str:
    """根据数据自动推荐效应量类型（增强版）

    与 synthesis.py 中的 determine_effect_measure 类似，
    但只返回字符串，简化调用。

    Returns:
        "MD" / "SMD" / "OR" / "RR"
    """
    has_continuous = False
    has_dichotomous = False

    for r in extraction_results:
        if "error" in r:
            continue
        es_type = str(r.get("effect_size", "")).upper().strip()
        if es_type in ("MD", "SMD", "WMD", "HEDGES", "COHEN", "MEAN DIFFERENCE",
                       "STANDARDIZED MEAN DIFFERENCE"):
            has_continuous = True
        elif es_type in ("OR", "RR", "ODDS RATIO", "RISK RATIO"):
            has_dichotomous = True

        # 从数值推断
        if not es_type:
            es_val = r.get("effect_size_value", "")
            nums = re.findall(r'[-]?\d*\.?\d+', es_val)
            if nums:
                val = float(nums[0])
                if 0.1 <= val <= 10 and val != 0:
                    has_dichotomous = True
                else:
                    has_continuous = True

    if has_dichotomous and not has_continuous:
        return "OR"
    elif has_continuous and not has_dichotomous:
        return "SMD"
    elif has_continuous and has_dichotomous:
        # 两者都有，取多数
        continuous_count = sum(1 for r in extraction_results if "error" not in r
                               and r.get("effect_size", "").upper() in
                               ("MD", "SMD", "WMD", "HEDGES", "COHEN"))
        dichotomous_count = sum(1 for r in extraction_results if "error" not in r
                                and r.get("effect_size", "").upper() in ("OR", "RR"))
        return "SMD" if continuous_count >= dichotomous_count else "OR"
    else:
        return "SMD"  # 默认


def prepare_meta_data_for_report(meta_result: MetaResult) -> dict:
    """将Meta分析结果转换为报告生成器可用的格式

    生成包含关键数字的文本摘要，供 report_generator.py 使用。

    Returns:
        dict: {
            "meta_summary": str,   # 文本摘要
            "meta_figure": None,   # 占位（后续可传Figure对象）
            "pooled_effect": float,
            "pooled_ci": str,
            "i_squared": float,
        }
    """
    r = meta_result.get_expanded()
    em = r.effect_measure
    model = "随机效应模型" if r.is_random else "固定效应模型"

    lines = [
        f"{model}分析结果：",
        f"合并效应量（{em}）={r.pooled_effect:.3f}，",
        f"95%CI（{r.pooled_ci_lower:.3f}, {r.pooled_ci_upper:.3f}），",
        f"Z={r.z_value:.3f}，P={r.pooled_p_value:.4f}。",
        f"异质性检验：Q={r.q_stat:.3f}，I²={r.i_squared:.1f}%，",
    ]

    if r.is_random:
        lines.append(f"τ²={r.tau_squared:.4f}。")

    lines.append(f"纳入研究：{r.n_studies}篇。")

    return {
        "meta_summary": "".join(lines),
        "meta_figure": None,
        "pooled_effect": r.pooled_effect,
        "pooled_ci": f"({r.pooled_ci_lower:.3f}, {r.pooled_ci_upper:.3f})",
        "i_squared": r.i_squared,
    }
