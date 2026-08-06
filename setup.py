from setuptools import setup, find_packages
from pathlib import Path
import re

here = Path(__file__).parent
long_description = (here / "README.md").read_text(encoding="utf-8")

# 直接从 __init__.py 读取版本号，避免 exec 导入问题
init_content = (here / "__init__.py").read_text(encoding="utf-8")
version_match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', init_content, re.M)
version = version_match.group(1) if version_match else "0.0.0"

setup(
    name="MindForge",
    version=version,
    description="AI Agent 终身记忆系统 - 四层记忆架构 · 知识图谱 · 多模态支持",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/opok-ops/MindForge",
    author="MindForge Project",
    license="MIT",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    keywords="ai agent memory knowledge-graph llm",
    packages=find_packages(
        exclude=["tests", "tests.*", "website", "examples", "data"]
    ),
    python_requires=">=3.9",
    install_requires=[],
    extras_require={
        "dev": [
            "pytest",
            "pytest-cov",
        ],
    },
    entry_points={
        "console_scripts": [
            "MindForge=cli.main:main",
            "MindForge-mcp=mcp.server:main",
        ],
    },
    project_urls={
        "Bug Reports": "https://github.com/opok-ops/MindForge/issues",
        "Source": "https://github.com/opok-ops/MindForge",
        "Homepage": "https://opok-ops.github.io/MindForge/",
    },
)
