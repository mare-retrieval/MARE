from pathlib import Path

from setuptools import find_packages, setup

README = Path(__file__).with_name("README.md").read_text(encoding="utf-8")


setup(
    name="mare-retrieval",
    version="0.3.0",
    description="Evidence-first PDF retrieval library that returns the best page, exact snippet, and visual evidence for a query.",
    long_description=README,
    long_description_content_type="text/markdown",
    author="Saisandeep Kantareddy",
    url="https://github.com/SaiSandeepKantareddy/MARE",
    package_dir={"": "src"},
    packages=find_packages("src"),
    python_requires=">=3.9",
    install_requires=["pypdf>=4.0", "pypdfium2>=4.30.0"],
    extras_require={
        "dev": ["pytest>=8.0"],
        "ui": ["streamlit>=1.12,<2.0", "altair<5"],
        "docling": ["docling>=2.70.0; python_version >= '3.10'"],
        "faiss": ["faiss-cpu>=1.8.0"],
        "langchain": ["langchain-core>=0.3.0"],
        "langgraph": ["langchain-core>=0.3.0", "langgraph>=0.3.0"],
        "llamaindex": ["llama-index-core>=0.12.0"],
        "paddleocr": ["paddleocr>=3.3.0"],
        "sentence-transformers": ["sentence-transformers>=3.0.0"],
        "surya": ["surya-ocr>=0.17.0", "pillow>=10.0.0"],
        "fastembed": ["fastembed>=0.7.0"],
        "unstructured": ["unstructured[pdf]>=0.16.0"],
        "integrations": [
            "faiss-cpu>=1.8.0",
            "langchain-core>=0.3.0",
            "langgraph>=0.3.0",
            "llama-index-core>=0.12.0",
            "paddleocr>=3.3.0",
            "sentence-transformers>=3.0.0",
            "surya-ocr>=0.17.0",
            "pillow>=10.0.0",
            "fastembed>=0.7.0",
            "qdrant-client[fastembed]>=1.14.1",
            "unstructured[pdf]>=0.16.0",
            "docling>=2.70.0; python_version >= '3.10'",
        ],
    },
    entry_points={
        "console_scripts": [
            "mare-demo=mare.demo:main",
            "mare-eval=mare.eval:main",
            "mare-ingest=mare.ingest:main",
            "mare-ask=mare.ask:main",
            "mare-ui=mare.streamlit_app:main",
        ]
    },
)
