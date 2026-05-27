from setuptools import setup, find_packages

setup(
    name="flowstate",
    version="2.0.0",
    author="Jeff Green",
    author_email="jeffgreen311@gmail.com",
    description="Dark-themed visual workflow orchestrator with LLM code generation",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/JeffGreen311/eve-agent-v2-unleashed",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=[
        "PyQt6",
        "openpyxl",
        "requests",
        "pytest",
        "ollama",
    ],
    entry_points={
        "console_scripts": [
            "flowstate=flowstate.app:main",
        ],
    },
)