from setuptools import setup, find_packages
from pathlib import Path

here = Path(__file__).parent
long_description = (here / "README.md").read_text(encoding="utf-8")

about = {}
exec((here / "__init__.py").read_text(encoding="utf-8"), about)

setup(
    name="clawmemory",
    version=about["__version__"],
    description="AI Agent 终身记忆系统 - 四层记忆架构 · 知识图谱 · 多模态支持",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/opok-ops/ClawMemory",
    author="ClawMemory Project",
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
    packages=find_packages(exclude=["tests", "tests.*", "website", "examples"]),
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
            "clawmemory=cli.main:main",
        ],
    },
    project_urls={
        "Bug Reports": "https://github.com/opok-ops/ClawMemory/issues",
        "Source": "https://github.com/opok-ops/ClawMemory",
        "Homepage": "https://opok-ops.github.io/ClawMemory/",
    },
)
