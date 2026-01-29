from setuptools import setup, find_packages

setup(
    name="youtube-clipper",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "yt-dlp>=2024.1.0",
        "openai-whisper>=20231117",
        "click>=8.0.0",
    ],
    entry_points={
        "console_scripts": [
            "clipper=cli:cli",
        ],
    },
    python_requires=">=3.8",
    author="Kish Parikh",
    description="Extract, crop, and caption YouTube video clips",
)
