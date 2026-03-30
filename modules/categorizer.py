"""
ClawMemory 分类管理模块
===========================
支持：
- 层级分类体系（树形结构）
- 自动分类建议（基于内容关键词/embedding）
- 分类统计与可视化
- 动态标签提取
"""

import json
import re
from typing import List, Dict, Optional, Set
from dataclasses import dataclass
from pathlib import Path

DEFAULT_TAXONOMY = {
    "life": {
        "label": "生活",
        "color": "green",
        "icon": "🏠",
        "subcategories": ["daily", "health", "hobby", "family", "social"],
    },
    "work": {
        "label": "工作",
        "color": "blue",
        "icon": "💼",
        "subcategories": ["project", "meeting", "task", "client", "finance"],
    },
    "learning": {
        "label": "学习",
        "color": "yellow",
        "icon": "📚",
        "subcategories": ["course", "book", "note", "skill", "research"],
    },
    "idea": {
        "label": "创意/想法",
        "color": "purple",
        "icon": "💡",
        "subcategories": ["concept", "plan", "prototype", "feedback"],
    },
    "fact": {
        "label": "事实/记录",
        "color": "gray",
        "icon": "📝",
        "subcategories": ["person", "place", "event", "document", "url"],
    },
    "emotion": {
        "label": "情感/感受",
        "color": "red",
        "icon": "❤️",
        "subcategories": ["joy", "gratitude", "reflection", "challenge"],
    },
    "general": {
        "label": "通用",
        "color": "default",
        "icon": "📌",
        "subcategories": [],
    },
}

AUTO_CLASSIFY_KEYWORDS = {
    "work": ["项目", "会议", "任务", "客户", "工作", "报告", " deadline", "project", "meeting", "task"],
    "learning": ["学习", "课程", "书", "知识", "技能", "研究", "course", "study", "book"],
    "idea": ["想法", "创意", "计划", "idea", "think", "concept", "创新"],
    "fact": ["地址", "电话", "账号", "密码", "URL", "链接", "事实", "记录"],
    "life": ["生活", "家庭", "健康", "爱好", "life", "home", "family", "health"],
    "emotion": ["感受", "情绪", "心情", "感谢", "开心", "难过", "feel", "happy", "grateful"],
}


@dataclass
class CategoryNode:
    id: str
    label: str
    icon: str
    color: str
    subcategories: List[str]
    memory_count: int = 0

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "label": self.label,
            "icon": self.icon,
            "color": self.color,
            "subcategories": self.subcategories,
            "memory_count": self.memory_count,
        }


class TaxonomyManager:
    """| 分类体系管理器 |"""

    def __init__(self, taxonomy_path: Optional[Path] = None):
        self._taxonomy_path = taxonomy_path
        self._taxonomy: Dict = {}
        self._load_taxonomy()

    def _load_taxonomy(self):
        if self._taxonomy_path and self._taxonomy_path.exists():
            with open(self._taxonomy_path, "r", encoding="utf-8") as f:
                self._taxonomy = json.load(f)
        else:
            self._taxonomy = DEFAULT_TAXONOMY.copy()

    def save_taxonomy(self):
        if self._taxonomy_path:
            self._taxonomy_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._taxonomy_path, "w", encoding="utf-8") as f:
                json.dump(self._taxonomy, f, ensure_ascii=False, indent=2)

    def suggest_category(self, text: str) -> str:
        """| 基于关键词自动建议分类 |"""
        text_lower = text.lower()
        scores: Dict[str, int] = {}

        for category, keywords in AUTO_CLASSIFY_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw.lower() in text_lower)
            if score > 0:
                scores[category] = score

        if not scores:
            return "general"

        # Pick the highest scoring category
        return max(scores, key=scores.get)

    def suggest_tags(self, text: str, existing_tags: List[str] = None) -> List[str]:
        """| 基于内容自动提取标签 |"""
        if existing_tags is None:
            existing_tags = []
        existing_set = set(existing_tags)

        tags: Set[str] = set(existing_tags)

        # Extract mentions (@user, #topic)
        mention_tags = re.findall(r"[@#](\w+)", text)
        tags.update(m.lower() for m in mention_tags)

        # Extract dates (ISO format)
        date_tags = re.findall(r"\d{4}[-/]\d{2}[-/]\d{2}", text)
        tags.update("date:" + d for d in date_tags)

        # Extract URLs as tags
        url_tags = re.findall(r"https?://[^\s]+", text)
        tags.update("url:" + u[:30] for u in url_tags)

        # Topic extraction (simple keyword-based)
        topic_keywords = {
            "ai": ["AI", "人工智能", "大模型", "LLM", "模型"],
            "code": ["代码", "编程", "code", "python", "javascript"],
            "health": ["健康", "运动", "饮食", "health", "exercise"],
            "finance": ["财务", "投资", "股票", "money", "invest", "stock"],
            "travel": ["旅行", "旅游", "出差", "travel", "trip"],
        }
        for topic, keywords in topic_keywords.items():
            if any(kw in text for kw in keywords):
                tags.add(topic)

        return list(tags)[:10]  # Max 10 tags

    def get_categories(self) -> List[CategoryNode]:
        """| 获取所有分类节点 |"""
        nodes = []
        for cat_id, cat_data in self._taxonomy.items():
            nodes.append(CategoryNode(
                id=cat_id,
                label=cat_data.get("label", cat_id),
                icon=cat_data.get("icon", "📌"),
                color=cat_data.get("color", "default"),
                subcategories=cat_data.get("subcategories", []),
            ))
        return nodes

    def add_category(
        self,
        category_id: str,
        label: str,
        icon: str = "📌",
        color: str = "default",
        subcategories: Optional[List[str]] = None,
    ):
        """| 添加新分类 |"""
        self._taxonomy[category_id] = {
            "label": label,
            "icon": icon,
            "color": color,
            "subcategories": subcategories or [],
        }
        self.save_taxonomy()

    def get_category_info(self, category_id: str) -> Optional[Dict]:
        return self._taxonomy.get(category_id)

    def get_color_emoji(self, category_id: str) -> str:
        cat = self._taxonomy.get(category_id, {})
        return cat.get("icon", "📌")