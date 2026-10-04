"""文本处理函数 — 模拟知识源的处理逻辑

这些函数模拟真实 NLP 处理，使用简单规则实现：
- 关键词提取：基于词频和停用词过滤
- 情感分析：基于词典的简单评分
- 总结归纳：基于句子重要性的摘要
"""

import re
from collections import Counter

# 简单中文停用词表
STOP_WORDS = set("的 了 在 是 我 有 和 就 不 人 都 一 一个 上 也 很 到 说 要 去 你 会 着 没有 看 好 自己 这 他 她 它 们 那 些 什么 怎么 如何 可以 因为 所以 但是 而且 或者 如果 虽然 这个 那个 这些 那些 已经 还 又 再 得 把 被 让 给 从 以 与 对 于 用 能 之 其 中 地 时 当 后 前 下 里 内 外 间 比 等 各 同 更 最 太 多 少 大 小 高 低 新 旧 好 坏 长 短 快 慢".split())

# 情感词典
POSITIVE_WORDS = set("好 棒 赞 优秀 出色 完美 精彩 喜欢 爱 开心 快乐 满意 推荐 强大 高效 稳定 简洁 清晰".split())
NEGATIVE_WORDS = set("差 烂 糟糕 失望 无聊 恶心 垃圾 卡顿 慢 错误 崩溃 复杂 混乱 繁琐 难用 痛苦 糟心".split())


def extract_keywords(text: str, top_n: int = 5) -> list[str]:
    """知识源A: 关键词提取

    基于词频统计和停用词过滤，提取文本中的关键词。
    """
    # 中文按字/词分割（简单实现：按标点和空格分词）
    tokens = re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]+', text)
    # 过滤停用词和短词
    filtered = [t for t in tokens if t not in STOP_WORDS and len(t) > 1]
    # 词频统计
    counter = Counter(filtered)
    return [word for word, _ in counter.most_common(top_n)]


def analyze_sentiment(text: str) -> dict:
    """知识源B: 情感分析

    基于情感词典的简单评分，返回情感标签和置信度。
    """
    tokens = re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]+', text)
    pos_count = sum(1 for t in tokens if t in POSITIVE_WORDS)
    neg_count = sum(1 for t in tokens if t in NEGATIVE_WORDS)
    total = pos_count + neg_count

    if total == 0:
        return {"label": "neutral", "confidence": 0.5, "positive": pos_count, "negative": neg_count}

    if pos_count > neg_count:
        confidence = pos_count / total
        return {"label": "positive", "confidence": round(confidence, 2), "positive": pos_count, "negative": neg_count}
    elif neg_count > pos_count:
        confidence = neg_count / total
        return {"label": "negative", "confidence": round(confidence, 2), "positive": pos_count, "negative": neg_count}
    else:
        return {"label": "neutral", "confidence": 0.5, "positive": pos_count, "negative": neg_count}


def generate_summary(text: str, keywords: list[str], sentiment: dict) -> str:
    """知识源C: 总结归纳

    基于关键词和情感分析结果，生成简短摘要。
    """
    # 按句子分割
    sentences = re.split(r'[。！？.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        return "无法生成摘要：输入文本为空。"

    # 选择包含关键词最多的句子作为核心句
    def keyword_score(s):
        return sum(1 for kw in keywords if kw in s)

    scored = [(s, keyword_score(s)) for s in sentences]
    scored.sort(key=lambda x: x[1], reverse=True)
    core_sentence = scored[0][0] if scored else sentences[0]

    # 生成摘要
    sentiment_text = {"positive": "积极", "negative": "消极", "neutral": "中性"}
    label = sentiment_text.get(sentiment["label"], "未知")

    summary = (
        f"【摘要】本文的核心观点为：{core_sentence}。"
        f"\n【关键词】{'、'.join(keywords)}。"
        f"\n【情感倾向】整体情感倾向为{label}（置信度 {sentiment['confidence']}）。"
    )
    return summary
