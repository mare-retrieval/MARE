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
        "fastembed": ["fastembed>=0.7.0"],
        "unstructured": ["unstructured[pdf]>=0.16.0"],
        "integrations": [
            "fastembed>=0.7.0",
            "qdrant-client[fastembed]>=1.14.1",
            "unstructured[pdf]>=0.16.0",
            "docling>=2.70.0; python_version >= '3.10'",
        ],
    },
    entry_points={
        "console_scripts": [
            "mare-demo=mare.demo:main",
            "mare-ingest=mare.ingest:main",
            "mare-ask=mare.ask:main",
            "mare-ui=mare.streamlit_app:main",
        ]
    },
)
